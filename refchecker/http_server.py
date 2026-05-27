"""Local HTTP bridge for the Claude web browser extension.

The extension runs inside the browser and cannot import Python modules directly,
so it sends selected reference text to this localhost service.

Run:

    python -m refchecker.http_server --port 8765
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import json
import os
import re
import threading
import time
from pathlib import Path
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from ctypes import wintypes

from .batch import verify_text
from .custom_rest import load_profiles_file
from .link_context import check_browser_links
from .mcp_server import _capture_backend_call, _common_verify_kwargs
from .utils import clean_doi
from .version import APP_VERSION


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
SERVER_SEARCH_MODE = "strict"
SERVER_DOI_CHECK = "auto"
SERVER_LLM_PARSE_MODE = "off"
SERVER_LLM_PROVIDER = "openai-compatible"
SERVER_LLM_MODEL = ""
SERVER_LLM_BASE_URL = ""
SERVER_PARENT_PID = 0
SERVER_PARENT_HEARTBEAT = ""
PARENT_HEARTBEAT_TIMEOUT_SECONDS = 6.0
SERVER_CUSTOM_REST_PROFILES = ""


def _timestamped_output_dir(base: str | None = None) -> Path:
    from datetime import datetime

    root = Path(base).expanduser().resolve() if base else Path.cwd() / "refchecker_web_output"
    path = root / datetime.now().strftime("%Y%m%d_%H%M%S")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _apply_server_custom_rest_defaults(payload: dict[str, Any]) -> None:
    """Attach desktop-configured custom REST profiles to browser checks."""
    if not SERVER_CUSTOM_REST_PROFILES:
        return
    if not _safe_text(payload.get("custom_rest_profiles")):
        payload["custom_rest_profiles"] = SERVER_CUSTOM_REST_PROFILES
    try:
        custom_keys = [p.get("sourceKey") for p in load_profiles_file(SERVER_CUSTOM_REST_PROFILES)]
    except Exception:
        custom_keys = []
    custom_keys = [key for key in custom_keys if key]
    if not custom_keys:
        return
    sources = _safe_text(payload.get("sources"))
    if not sources:
        return
    existing = {part.strip() for part in re.split(r"[,\s]+", sources) if part.strip()}
    missing = [key for key in custom_keys if key not in existing]
    if missing:
        payload["sources"] = ",".join([sources, *missing])


def _correct_url(row: dict[str, Any]) -> str:
    doi = _safe_text(row.get("matched_doi") or row.get("doi"))
    if row.get("doi_check_status") == "mismatch":
        bib_doi = clean_doi(_safe_text(row.get("bib_doi")))
        if doi and bib_doi and clean_doi(doi) == bib_doi:
            return ""
    if doi:
        return f"https://doi.org/{doi}"
    return _safe_text(row.get("url"))


def _link_issue(row: dict[str, Any]) -> str:
    if row.get("doi_check_status") == "mismatch":
        return "input_doi_mismatch"
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
        "input_url": row.get("bib_url", ""),
        "matched_url": row.get("url", ""),
        "bib_year": row.get("bib_year", ""),
        "matched_year": row.get("matched_year", "") or row.get("year", ""),
        "bib_authors": row.get("bib_authors", ""),
        "matched_authors": row.get("matched_authors", "") or row.get("authors", ""),
        "missing_authors": row.get("missing_authors", ""),
        "extra_authors": row.get("extra_authors", ""),
        "bib_author_count": row.get("bib_author_count", ""),
        "matched_author_count": row.get("matched_author_count", ""),
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
        "search_mode": row.get("search_mode", ""),
        "source_order": row.get("source_order", ""),
        "actual_query_trace": row.get("actual_query_trace", ""),
        "query_trace": row.get("query_trace", ""),
        "adopted_source": row.get("adopted_source", "") or row.get("source", ""),
        "doi_check_status": row.get("doi_check_status", ""),
        "doi_check_message": row.get("doi_check_message", ""),
        "doi_resolved_url": row.get("doi_resolved_url", ""),
        "doi_target_title": row.get("doi_target_title", ""),
        "doi_target_authors": row.get("doi_target_authors", ""),
        "doi_target_year": row.get("doi_target_year", ""),
        "parser": row.get("parser", ""),
        "parser_note": row.get("parser_note", ""),
        "parser_confidence": row.get("parser_confidence", ""),
        "parser_warning": row.get("parser_warning", ""),
        "llm_parse_mode": row.get("llm_parse_mode", ""),
        "web_evidence": row.get("web_evidence", ""),
        "evidence_kind": row.get("evidence_kind", ""),
        "web_evidence_note": row.get("web_evidence_note", ""),
        "web_evidence_links": row.get("web_evidence_links", ""),
        "web_evidence_results": row.get("web_evidence_results", []),
        "snippet": row.get("snippet", ""),
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
    payload = dict(payload)
    payload.setdefault("search_mode", SERVER_SEARCH_MODE)
    payload.setdefault("doi_check", SERVER_DOI_CHECK)
    payload.setdefault("llm_parse_mode", SERVER_LLM_PARSE_MODE)
    payload.setdefault("llm_provider", SERVER_LLM_PROVIDER)
    payload.setdefault("llm_model", SERVER_LLM_MODEL)
    payload.setdefault("llm_base_url", SERVER_LLM_BASE_URL)
    _apply_server_custom_rest_defaults(payload)
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

    doi_like_text = bool(re.search(r"(?:doi\.org/|(?:^|\s)10\.\d{4,9}/)", text, re.I))
    if links_only and not doi_like_text:
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
            "search_mode": payload.get("search_mode") or SERVER_SEARCH_MODE,
            "source_order": "",
            "actual_query_trace": "",
            "doi_check_status": "not_provided",
            "doi_resolved_url": "",
            "llm_parse_mode": payload.get("llm_parse_mode") or SERVER_LLM_PARSE_MODE,
            "parser_summary": "",
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
            "search_mode": summary.get("search_mode", "strict"),
            "source_order": summary.get("source_order", ""),
            "actual_query_trace": summary.get("actual_query_trace", ""),
            "doi_check_status": summary.get("doi_check_status", ""),
            "doi_resolved_url": summary.get("doi_resolved_url", ""),
            "llm_parse_mode": summary.get("llm_parse_mode", payload.get("llm_parse_mode", "off")),
            "parser_summary": summary.get("parser_summary", ""),
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
            self._send_json(HTTPStatus.OK, {
                "ok": True,
                "service": "refchecker",
                "version": APP_VERSION,
                "pid": os.getpid(),
                "parent_pid": SERVER_PARENT_PID,
                "parent_heartbeat": bool(SERVER_PARENT_HEARTBEAT),
                "search_mode": SERVER_SEARCH_MODE,
                "doi_check": SERVER_DOI_CHECK,
                "llm_parse_mode": SERVER_LLM_PARSE_MODE,
                "llm_provider": SERVER_LLM_PROVIDER,
                "llm_model": SERVER_LLM_MODEL,
                "llm_base_url": SERVER_LLM_BASE_URL,
                "custom_rest_profiles": bool(SERVER_CUSTOM_REST_PROFILES),
            })
            return
        if self.path.rstrip("/") == "/shutdown":
            self._send_json(HTTPStatus.OK, {"ok": True, "message": "shutdown scheduled", "pid": os.getpid()})
            _schedule_server_shutdown(self.server)
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
            if path == "/shutdown":
                self._send_json(HTTPStatus.OK, {"ok": True, "message": "shutdown scheduled", "pid": os.getpid()})
                _schedule_server_shutdown(self.server)
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
        except Exception as exc:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": type(exc).__name__, "message": str(exc)},
            )


def _schedule_server_shutdown(server) -> None:
    def stop() -> None:
        time.sleep(0.15)
        _force_process_exit_later()
        server.shutdown()

    threading.Thread(target=stop, name="refchecker-http-shutdown", daemon=True).start()


def _force_process_exit_later(delay: float = 4.0, code: int = 0) -> None:
    """Hard-stop this helper if serve_forever does not return promptly.

    The HTTP bridge is a disposable child process of the desktop app.  On
    Windows, especially with PyInstaller one-file builds, a graceful shutdown
    can occasionally leave the helper around long enough to lock its exe.  This
    fallback only affects the local HTTP helper process.
    """

    def force_exit() -> None:
        time.sleep(delay)
        os._exit(code)

    threading.Thread(
        target=force_exit,
        name="refchecker-http-force-exit",
        daemon=True,
    ).start()


def _parent_heartbeat_alive(path: str) -> bool:
    if not path:
        return True
    try:
        stat = os.stat(path)
    except OSError:
        return False
    return (time.time() - stat.st_mtime) <= PARENT_HEARTBEAT_TIMEOUT_SECONDS


def _parent_exit_reason(parent_pid: int | None = None, heartbeat_path: str | None = None) -> str:
    pid_to_check = SERVER_PARENT_PID if parent_pid is None else int(parent_pid or 0)
    heartbeat_to_check = SERVER_PARENT_HEARTBEAT if heartbeat_path is None else str(heartbeat_path or "")
    if pid_to_check > 0 and not _parent_process_alive(pid_to_check):
        return f"parent pid {pid_to_check} is gone"
    if heartbeat_to_check and not _parent_heartbeat_alive(heartbeat_to_check):
        return f"parent heartbeat is missing or stale: {heartbeat_to_check}"
    return ""


def _parent_process_alive(parent_pid: int) -> bool:
    if parent_pid <= 0:
        return True
    if os.name == "nt":
        # SYNCHRONIZE is enough for WaitForSingleObject and avoids requiring PROCESS_TERMINATE.
        synchronize = 0x00100000
        wait_timeout = 0x00000102
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(synchronize, False, int(parent_pid))
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == wait_timeout
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(parent_pid, 0)
        return True
    except OSError as exc:
        return exc.errno not in {errno.ESRCH}


def _start_parent_monitor(server, parent_pid: int, heartbeat_path: str = "") -> None:
    if parent_pid <= 0 and not heartbeat_path:
        return

    def monitor() -> None:
        while True:
            time.sleep(1.0)
            reason = _parent_exit_reason(parent_pid, heartbeat_path)
            if reason:
                print(
                    f"RefChecker local HTTP server parent is gone ({reason}); shutting down.",
                    flush=True,
                )
                _force_process_exit_later(delay=2.0)
                server.shutdown()
                return

    threading.Thread(target=monitor, name="refchecker-http-parent-monitor", daemon=True).start()


class RefCheckerThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer with an in-loop parent/heartbeat watchdog."""

    def service_actions(self) -> None:
        reason = _parent_exit_reason()
        if reason:
            print(
                f"RefChecker local HTTP server parent is gone ({reason}); exiting.",
                flush=True,
            )
            os._exit(0)


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
               search_mode: str = "strict", doi_check: str = "auto",
               llm_parse_mode: str = "off", llm_provider: str = "openai-compatible",
               llm_model: str = "", llm_base_url: str = "",
               parent_pid: int = 0, parent_heartbeat: str = "",
               custom_rest_profiles: str = "") -> None:
    global SERVER_SEARCH_MODE, SERVER_DOI_CHECK, SERVER_LLM_PARSE_MODE
    global SERVER_LLM_PROVIDER, SERVER_LLM_MODEL, SERVER_LLM_BASE_URL, SERVER_PARENT_PID
    global SERVER_PARENT_HEARTBEAT
    global SERVER_CUSTOM_REST_PROFILES
    SERVER_SEARCH_MODE = search_mode if search_mode in {"strict", "parallel"} else "strict"
    SERVER_DOI_CHECK = doi_check if doi_check in {"auto", "off"} else "auto"
    SERVER_LLM_PARSE_MODE = llm_parse_mode if llm_parse_mode in {"off", "auto", "always"} else "off"
    SERVER_LLM_PROVIDER = llm_provider or "openai-compatible"
    SERVER_LLM_MODEL = llm_model or ""
    SERVER_LLM_BASE_URL = llm_base_url or ""
    SERVER_PARENT_PID = int(parent_pid or 0)
    SERVER_PARENT_HEARTBEAT = parent_heartbeat or ""
    SERVER_CUSTOM_REST_PROFILES = custom_rest_profiles or ""
    httpd = RefCheckerThreadingHTTPServer((host, port), RefCheckerHttpHandler)
    _start_parent_monitor(httpd, SERVER_PARENT_PID, SERVER_PARENT_HEARTBEAT)
    print(
        f"RefChecker local HTTP server listening on http://{host}:{port} "
        f"(search_mode={SERVER_SEARCH_MODE}, doi_check={SERVER_DOI_CHECK}, "
        f"llm_parse_mode={SERVER_LLM_PARSE_MODE}, "
        f"custom_rest={'yes' if SERVER_CUSTOM_REST_PROFILES else 'no'}, "
        f"parent_pid={SERVER_PARENT_PID or 'none'}, "
        f"parent_heartbeat={'yes' if SERVER_PARENT_HEARTBEAT else 'no'})",
        flush=True,
    )
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RefChecker local HTTP server for browser extension.")
    parser.add_argument("--host", default=os.getenv("REFCHECKER_HTTP_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.getenv("REFCHECKER_HTTP_PORT", DEFAULT_PORT)))
    parser.add_argument("--search-mode", choices=["strict", "parallel"],
                        default=os.getenv("REFCHECKER_SEARCH_MODE", "strict"))
    parser.add_argument("--doi-check", choices=["auto", "off"],
                        default=os.getenv("REFCHECKER_DOI_CHECK", "auto"))
    parser.add_argument("--llm-parse-mode", choices=["off", "auto", "always"],
                        default=os.getenv("REFCHECKER_LLM_PARSE_MODE", "off"))
    parser.add_argument("--llm-provider", default=os.getenv("REFCHECKER_LLM_PROVIDER", "openai-compatible"))
    parser.add_argument("--llm-model", default=os.getenv("REFCHECKER_LLM_MODEL", ""))
    parser.add_argument("--llm-base-url", default=os.getenv("REFCHECKER_LLM_BASE_URL", ""))
    parser.add_argument("--custom-rest-profiles", default=os.getenv("REFCHECKER_CUSTOM_REST_PROFILES", ""),
                        help="Optional custom REST API profile JSON file used by browser-extension checks.")
    parser.add_argument("--parent-pid", type=int, default=int(os.getenv("REFCHECKER_PARENT_PID", "0") or "0"),
                        help="Optional desktop app PID. The HTTP server exits automatically when this parent process is gone.")
    parser.add_argument("--parent-heartbeat", default=os.getenv("REFCHECKER_PARENT_HEARTBEAT", ""),
                        help="Optional heartbeat file updated by the desktop app. The HTTP server exits when it disappears or becomes stale.")
    args = parser.parse_args()
    run_server(
        args.host,
        args.port,
        args.search_mode,
        args.doi_check,
        args.llm_parse_mode,
        args.llm_provider,
        args.llm_model,
        args.llm_base_url,
        args.parent_pid,
        args.parent_heartbeat,
        args.custom_rest_profiles,
    )


if __name__ == "__main__":
    main()
