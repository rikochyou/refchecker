"""Local HTTP bridge for the Claude web browser extension.

The extension runs inside the browser and cannot import Python modules directly,
so it sends selected reference text to this localhost service.

Run:

    python -m refchecker.http_server --port 8765
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .batch import verify_text
from .link_context import check_browser_links
from .mcp_server import _capture_backend_call, _common_verify_kwargs
from .version import APP_VERSION


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _timestamped_output_dir(base: str | None = None) -> Path:
    from datetime import datetime

    root = Path(base).expanduser().resolve() if base else Path.cwd() / "refchecker_web_output"
    path = root / datetime.now().strftime("%Y%m%d_%H%M%S")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _correct_url(row: dict[str, Any]) -> str:
    doi = _safe_text(row.get("matched_doi") or row.get("doi"))
    if doi:
        return f"https://doi.org/{doi}"
    return _safe_text(row.get("url"))


def _link_issue(row: dict[str, Any]) -> str:
    doi_check = row.get("doi_check")
    if doi_check == "mismatch":
        return "input_doi_mismatch"
    if doi_check == "missing_in_bib" and row.get("matched_doi"):
        return "doi_missing_in_input"
    if row.get("status") == "not_found":
        return "not_found"
    if row.get("risk_level") in {"high", "medium"}:
        return "needs_review"
    return ""


def _simplify_result(row: dict[str, Any]) -> dict[str, Any]:
    corrected_apa = _safe_text(row.get("standard_citation_apa"))
    corrected_bibtex = _safe_text(row.get("standard_citation_bibtex"))
    return {
        "key": row.get("key", ""),
        "input_title": row.get("title", ""),
        "matched_title": row.get("matched_title", ""),
        "status": row.get("status", ""),
        "risk_level": row.get("risk_level", ""),
        "confidence_score": row.get("confidence_score", ""),
        "source": row.get("source", ""),
        "similarity": row.get("similarity", ""),
        "bib_doi": row.get("bib_doi", ""),
        "matched_doi": row.get("matched_doi", ""),
        "input_url": row.get("url", ""),
        "correct_url": _correct_url(row),
        "link_issue": _link_issue(row),
        "doi_check": row.get("doi_check", ""),
        "doi_reason": row.get("doi_reason", ""),
        "author_check": row.get("author_check", ""),
        "author_reason": row.get("author_reason", ""),
        "year_check": row.get("year_check", ""),
        "year_reason": row.get("year_reason", ""),
        "suggested_action": row.get("fix_suggestion") or row.get("suggested_action", ""),
        "evidence_basis": row.get("fix_suggestion_basis", ""),
        "corrected_apa": corrected_apa,
        "corrected_bibtex": corrected_bibtex,
        "standard_citation_available": row.get("standard_citation_available", ""),
    }


def _build_corrected_references(items: list[dict[str, Any]]) -> str:
    references = [
        item["corrected_apa"]
        for item in items
        if item.get("corrected_apa") and item.get("standard_citation_available") == "Yes"
    ]
    return "\n\n".join(references)


def check_text_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Verify selected text and return browser-friendly JSON."""
    text = _safe_text(payload.get("text"))
    raw_links = payload.get("links")
    has_links = isinstance(raw_links, list) and bool(raw_links)
    links_only = bool(payload.get("links_only")) and has_links
    link_checks = check_browser_links(
        raw_links,
        fetch_targets=links_only,
        max_links=5 if links_only else 20,
    )
    link_alerts = [item for item in link_checks if item.get("status") != "ok"]
    if not text and not link_checks:
        raise ValueError("text or links are required")

    output_dir_arg = _safe_text(payload.get("output_dir"))
    output_dir = Path(output_dir_arg).expanduser().resolve() if output_dir_arg else _timestamped_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    if links_only:
        summary = {
            "total": 0,
            "found": 0,
            "not_found": 0,
            "needs_review": 0,
            "high_risk": 0,
            "medium_risk": 0,
            "low_risk": 0,
            "output_dir": str(output_dir),
            "markdown_path": "",
            "csv_path": "",
            "citation_consistency_path": "",
            "report_summary": "已完成网页真实链接核查；本次选择内容像 arxiv/PNAS 这类链接标签，未把标签文字当作文献题名核验。",
        }
        items: list[dict[str, Any]] = []
        priority_items: list[dict[str, Any]] = []
    else:
        kwargs = _common_verify_kwargs(payload)
        kwargs.update({"output_dir": str(output_dir)})
        result = _capture_backend_call(verify_text, text, **kwargs)
        summary = result.get("summary") or {}
        rows = result.get("results") or []
        items = [_simplify_result(row) for row in rows]
        priority_items = [
            item
            for item in items
            if item.get("link_issue") or item.get("risk_level") in {"high", "medium"}
        ]

    return {
        "ok": True,
        "app_version": APP_VERSION,
        "summary": {
            "total": summary.get("total", len(items)),
            "found": summary.get("found", 0),
            "not_found": summary.get("not_found", 0),
            "needs_review": summary.get("needs_review", 0),
            "high_risk": summary.get("high_risk", 0),
            "medium_risk": summary.get("medium_risk", 0),
            "low_risk": summary.get("low_risk", 0),
            "link_checks": len(link_checks),
            "link_alerts": len(link_alerts),
            "report_summary": summary.get("report_summary", ""),
        },
        "paths": {
            "output_dir": summary.get("output_dir", str(output_dir)),
            "markdown_path": summary.get("markdown_path", ""),
            "csv_path": summary.get("csv_path", ""),
            "citation_consistency_path": summary.get("citation_consistency_path", ""),
        },
        "items": items,
        "priority_items": priority_items,
        "link_checks": link_checks,
        "corrected_references": _build_corrected_references(items),
    }


class RefCheckerHttpHandler(BaseHTTPRequestHandler):
    server_version = f"RefCheckerHTTP/{APP_VERSION}"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[RefChecker HTTP] {self.address_string()} - {fmt % args}")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib hook name
        self._send_json(HTTPStatus.NO_CONTENT, {})

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
        if self.path.rstrip("/") == "/health":
            self._send_json(HTTPStatus.OK, {"ok": True, "service": "refchecker", "version": APP_VERSION})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
        try:
            content_length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw) if raw.strip() else {}
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            path = self.path.rstrip("/")
            if path == "/check-text":
                self._send_json(HTTPStatus.OK, check_text_payload(payload))
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
        except Exception as exc:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": type(exc).__name__, "message": str(exc)},
            )


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    httpd = ThreadingHTTPServer((host, port), RefCheckerHttpHandler)
    print(f"RefChecker local HTTP server listening on http://{host}:{port}", flush=True)
    httpd.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RefChecker local HTTP server for browser extension.")
    parser.add_argument("--host", default=os.getenv("REFCHECKER_HTTP_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.getenv("REFCHECKER_HTTP_PORT", DEFAULT_PORT)))
    args = parser.parse_args()
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
