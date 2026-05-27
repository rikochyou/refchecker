"""Minimal MCP stdio server for Claude Desktop.

This module intentionally has no dependency on the optional MCP Python SDK.
It implements the small JSON-RPC surface Claude Desktop needs for local tools:

* initialize
* tools/list
* tools/call

Run it with:

    python -m refchecker.mcp_server
"""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import sys
from datetime import datetime
from typing import Any, Callable

from .batch import verify_bib_file, verify_docx_file, verify_text
from .config import (
    build_source_order,
    parse_source_selection,
    source_selected,
    test_api_keys,
)
from .custom_rest import load_profiles_file
from .version import APP_VERSION

SERVER_NAME = "refchecker"
PROTOCOL_VERSION = "2025-06-18"


ToolHandler = Callable[[dict[str, Any]], str]


def _text_schema(description: str = "") -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string"}
    if description:
        schema["description"] = description
    return schema


TOOLS: list[dict[str, Any]] = [
    {
        "name": "check_reference_file",
        "description": (
            "Verify a local .bib, .docx, or .txt reference file with RefChecker. "
            "Returns a concise summary and writes report.md/result.csv to an output directory."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": _text_schema("Absolute or relative path to a .bib, .docx, or .txt file."),
                "output_dir": _text_schema("Optional output directory. Defaults to a timestamped folder next to the file."),
                "threshold": {
                    "type": "number",
                    "description": "Title similarity threshold from 0 to 1. Default: 0.85.",
                    "default": 0.85,
                },
                "delay": {
                    "type": "number",
                    "description": "Delay in seconds between checks. Values below 0.5 are clamped by RefChecker.",
                    "default": 0.5,
                },
                "email": _text_schema("Optional email used in API User-Agent/mailto fields."),
                "sources": _text_schema(
                    "Optional comma-separated source priority, e.g. crossref,openalex,semantic-scholar,arxiv,pubmed,dblp,url."
                ),
                "search_mode": {
                    "type": "string",
                    "enum": ["strict", "parallel"],
                    "description": "Search mode. strict queries sources in order and stops on high-confidence hits; parallel queries sources concurrently.",
                    "default": "strict",
                },
                "doi_check": {
                    "type": "string",
                    "enum": ["auto", "off"],
                    "description": "DOI exact-check strategy. auto checks DOI metadata before the search chain; off disables it.",
                    "default": "auto",
                },
                "llm_parse_mode": {
                    "type": "string",
                    "enum": ["off", "auto", "always"],
                    "description": "LLM field extraction mode. Any non-off mode is LLM-first and falls back to rule-parsed fields only when the LLM cannot parse a field/row. The LLM only extracts fields and does not judge authenticity.",
                    "default": "off",
                },
                "llm_provider": _text_schema("LLM provider. Currently supports openai-compatible."),
                "llm_model": _text_schema("LLM model name. Falls back to REFCHECKER_LLM_MODEL."),
                "llm_base_url": _text_schema("OpenAI-compatible API base URL. Falls back to REFCHECKER_LLM_BASE_URL."),
                "llm_api_key": _text_schema("Optional LLM API key. Falls back to REFCHECKER_LLM_API_KEY."),
                "disabled_sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional sources to disable, e.g. ['url', 'openalex'].",
                    "default": [],
                },
                "springer_api_key": _text_schema("Optional Springer Nature API key. Falls back to REFCHECKER_SPRINGER_API_KEY."),
                "ieee_api_key": _text_schema("Optional IEEE Xplore API key. Falls back to REFCHECKER_IEEE_API_KEY."),
                "core_api_key": _text_schema("Optional CORE API key. Falls back to REFCHECKER_CORE_API_KEY."),
                "custom_rest_profiles": _text_schema("Optional JSON file path with custom REST API profiles."),
            },
            "required": ["file_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_reference_text",
        "description": (
            "Verify pasted reference text with RefChecker. Returns a concise summary "
            "and writes report.md/result.csv to an output directory."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": _text_schema("Reference text to verify. Multiple references can be separated by blank lines."),
                "output_dir": _text_schema("Optional output directory. Defaults to ./refchecker_mcp_output/<timestamp>."),
                "threshold": {
                    "type": "number",
                    "description": "Title similarity threshold from 0 to 1. Default: 0.85.",
                    "default": 0.85,
                },
                "delay": {
                    "type": "number",
                    "description": "Delay in seconds between checks. Values below 0.5 are clamped by RefChecker.",
                    "default": 0.5,
                },
                "email": _text_schema("Optional email used in API User-Agent/mailto fields."),
                "sources": _text_schema("Optional comma-separated source priority."),
                "search_mode": {
                    "type": "string",
                    "enum": ["strict", "parallel"],
                    "description": "Search mode. strict queries sources in order and stops on high-confidence hits; parallel queries sources concurrently.",
                    "default": "strict",
                },
                "doi_check": {
                    "type": "string",
                    "enum": ["auto", "off"],
                    "description": "DOI exact-check strategy. auto checks DOI metadata before the search chain; off disables it.",
                    "default": "auto",
                },
                "llm_parse_mode": {
                    "type": "string",
                    "enum": ["off", "auto", "always"],
                    "description": "LLM field extraction mode. Any non-off mode is LLM-first and falls back to rule-parsed fields only when the LLM cannot parse a field/row. The LLM only extracts fields and does not judge authenticity.",
                    "default": "off",
                },
                "llm_provider": _text_schema("LLM provider. Currently supports openai-compatible."),
                "llm_model": _text_schema("LLM model name. Falls back to REFCHECKER_LLM_MODEL."),
                "llm_base_url": _text_schema("OpenAI-compatible API base URL. Falls back to REFCHECKER_LLM_BASE_URL."),
                "llm_api_key": _text_schema("Optional LLM API key. Falls back to REFCHECKER_LLM_API_KEY."),
                "disabled_sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional sources to disable, e.g. ['url', 'openalex'].",
                    "default": [],
                },
                "springer_api_key": _text_schema("Optional Springer Nature API key. Falls back to REFCHECKER_SPRINGER_API_KEY."),
                "ieee_api_key": _text_schema("Optional IEEE Xplore API key. Falls back to REFCHECKER_IEEE_API_KEY."),
                "core_api_key": _text_schema("Optional CORE API key. Falls back to REFCHECKER_CORE_API_KEY."),
                "custom_rest_profiles": _text_schema("Optional JSON file path with custom REST API profiles."),
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "test_reference_api_keys",
        "description": "Test configured Springer Nature / IEEE Xplore / CORE / custom REST API keys.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sources": _text_schema("Optional comma-separated sources to test, e.g. springer,ieee,core."),
                "springer_api_key": _text_schema("Optional Springer Nature API key. Falls back to REFCHECKER_SPRINGER_API_KEY."),
                "ieee_api_key": _text_schema("Optional IEEE Xplore API key. Falls back to REFCHECKER_IEEE_API_KEY."),
                "core_api_key": _text_schema("Optional CORE API key. Falls back to REFCHECKER_CORE_API_KEY."),
                "custom_rest_profiles": _text_schema("Optional JSON file path with custom REST API profiles."),
            },
            "additionalProperties": False,
        },
    },
]


def _normalize_path(value: str | os.PathLike[str]) -> Path:
    raw = str(value).strip().strip('"').strip("'")
    if not raw:
        raise ValueError("Path is empty.")
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _prepare_output_dir(output_dir: str | None, *, base_file: Path | None = None) -> Path:
    if output_dir:
        path = _normalize_path(output_dir)
    elif base_file is not None:
        path = base_file.parent / f"refchecker_mcp_output_{_timestamp()}"
    else:
        path = Path.cwd() / "refchecker_mcp_output" / _timestamp()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _as_float(args: dict[str, Any], name: str, default: float) -> float:
    value = args.get(name, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number.") from None


def _disabled_sources(args: dict[str, Any]) -> set[str]:
    raw = args.get("disabled_sources") or []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        raise ValueError("disabled_sources must be an array of source names.")
    disabled: set[str] = set()
    for item in raw:
        parsed = parse_source_selection(str(item))
        if parsed:
            disabled.update(parsed)
    return disabled


def _common_verify_kwargs(args: dict[str, Any]) -> dict[str, Any]:
    selected_sources = parse_source_selection(str(args.get("sources") or ""))
    disabled = _disabled_sources(args)
    custom_rest_path = str(args.get("custom_rest_profiles") or "").strip()
    custom_rest_profiles = load_profiles_file(custom_rest_path) if custom_rest_path else []
    custom_source_keys = [p["sourceKey"] for p in custom_rest_profiles]
    if selected_sources is not None:
        custom_rest_profiles = [
            p for p in custom_rest_profiles if p["sourceKey"] in selected_sources
        ]
        custom_source_keys = [p["sourceKey"] for p in custom_rest_profiles]

    def enabled(name: str, default: bool = True) -> bool:
        return name not in disabled and source_selected(selected_sources, name, default)

    springer_key = str(args.get("springer_api_key") or os.getenv("REFCHECKER_SPRINGER_API_KEY", "")).strip()
    ieee_key = str(args.get("ieee_api_key") or os.getenv("REFCHECKER_IEEE_API_KEY", "")).strip()
    core_key = str(args.get("core_api_key") or os.getenv("REFCHECKER_CORE_API_KEY", "")).strip()
    search_mode = str(args.get("search_mode") or "strict").strip().lower()
    if search_mode not in {"strict", "parallel"}:
        raise ValueError("search_mode must be 'strict' or 'parallel'.")
    doi_check = str(args.get("doi_check") or "auto").strip().lower()
    if doi_check not in {"auto", "off"}:
        raise ValueError("doi_check must be 'auto' or 'off'.")
    llm_parse_mode = str(args.get("llm_parse_mode") or os.getenv("REFCHECKER_LLM_PARSE_MODE", "off")).strip().lower()
    if llm_parse_mode not in {"off", "auto", "always"}:
        raise ValueError("llm_parse_mode must be 'off', 'auto', or 'always'.")
    llm_provider = str(args.get("llm_provider") or os.getenv("REFCHECKER_LLM_PROVIDER", "openai-compatible")).strip()
    llm_model = str(args.get("llm_model") or os.getenv("REFCHECKER_LLM_MODEL", "")).strip()
    llm_base_url = str(args.get("llm_base_url") or os.getenv("REFCHECKER_LLM_BASE_URL", "")).strip()
    llm_api_key = str(args.get("llm_api_key") or os.getenv("REFCHECKER_LLM_API_KEY", "")).strip()

    return {
        "threshold": _as_float(args, "threshold", 0.85),
        "delay": _as_float(args, "delay", 0.5),
        "email": str(args.get("email") or ""),
        "use_crossref": enabled("crossref", True),
        "use_openalex": enabled("openalex", True),
        "use_dblp": enabled("dblp", True),
        "use_semantic_scholar": enabled("semantic-scholar", True),
        "use_arxiv": enabled("arxiv", True),
        "use_pubmed": enabled("pubmed", True),
        "use_springer": enabled("springer", bool(springer_key)),
        "use_ieee": enabled("ieee", bool(ieee_key)),
        "use_core": enabled("core", bool(core_key)),
        "springer_api_key": springer_key,
        "ieee_api_key": ieee_key,
        "core_api_key": core_key,
        "use_url_verify": enabled("url", True),
        "source_order": build_source_order(selected_sources, custom_source_keys),
        "custom_rest_profiles": custom_rest_profiles,
        "search_mode": search_mode,
        "doi_check": doi_check,
        "llm_parse_mode": llm_parse_mode,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "llm_base_url": llm_base_url,
        "llm_api_key": llm_api_key,
        "app_version": APP_VERSION,
        "jsonl_progress": False,
        "human_output": False,
    }


def _capture_backend_call(func: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Run RefChecker without leaking progress logs onto MCP stdout."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        result = func(*args, **kwargs)
    result["_captured_stdout"] = stdout.getvalue()
    result["_captured_stderr"] = stderr.getvalue()
    return result


def _format_summary(result: dict[str, Any], *, title: str) -> str:
    summary = result.get("summary") or {}
    rows = result.get("results") or []
    lines = [
        f"# {title}",
        "",
        f"- Total: **{summary.get('total', len(rows))}**",
        f"- Found: **{summary.get('found', 0)}**",
        f"- Not found: **{summary.get('not_found', 0)}**",
        f"- Needs review: **{summary.get('needs_review', 0)}**",
        (
            "- Risk levels: "
            f"high **{summary.get('high_risk', 0)}**, "
            f"medium **{summary.get('medium_risk', 0)}**, "
            f"low **{summary.get('low_risk', 0)}**"
        ),
        f"- Search mode: **{summary.get('search_mode', 'strict')}**",
        f"- Source order: **{summary.get('source_order', '') or 'default'}**",
        f"- DOI check: **{summary.get('doi_check_status', 'not_provided')}**",
        f"- Parser: **{summary.get('parser_summary', '') or 'rules'}** (LLM mode: **{summary.get('llm_parse_mode', 'off')}**)",
    ]
    if summary.get("report_summary"):
        lines.extend(["", "## Report summary", str(summary["report_summary"])])
    output_dir = summary.get("output_dir")
    report_path = summary.get("markdown_path")
    csv_path = summary.get("csv_path")
    citation_path = summary.get("citation_consistency_path")
    if output_dir or report_path or csv_path or citation_path:
        lines.append("")
        lines.append("## Output files")
        if output_dir:
            lines.append(f"- Output directory: `{output_dir}`")
        if report_path:
            lines.append(f"- Markdown report: `{report_path}`")
        if csv_path:
            lines.append(f"- CSV: `{csv_path}`")
        if citation_path:
            lines.append(f"- Citation consistency JSON: `{citation_path}`")

    priority = [
        row
        for row in rows
        if row.get("risk_level") in {"high", "medium"} or row.get("status") == "not_found"
    ][:10]
    if priority:
        lines.extend(["", "## Priority items"])
        for row in priority:
            label = row.get("key") or row.get("title") or "<unknown>"
            risk = row.get("risk_level") or row.get("status") or ""
            action = row.get("suggested_action") or row.get("reason") or ""
            source = row.get("source") or ""
            lines.append(f"- `{label}` [{risk}] {source}: {action}")
    return "\n".join(lines)


def check_reference_file(args: dict[str, Any]) -> str:
    file_path = _normalize_path(args.get("file_path", ""))
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Not a file: {file_path}")
    output_dir = _prepare_output_dir(args.get("output_dir"), base_file=file_path)
    kwargs = _common_verify_kwargs(args)
    kwargs.update({"output_dir": str(output_dir)})
    ext = file_path.suffix.lower()
    if ext == ".docx":
        result = _capture_backend_call(verify_docx_file, str(file_path), **kwargs)
    elif ext == ".txt":
        text = file_path.read_text(encoding="utf-8")
        result = _capture_backend_call(verify_text, text, **kwargs)
    elif ext == ".bib":
        result = _capture_backend_call(verify_bib_file, str(file_path), **kwargs)
    else:
        raise ValueError("Unsupported file type. Please provide .bib, .docx, or .txt.")
    return _format_summary(result, title=f"RefChecker result for {file_path.name}")


def check_reference_text(args: dict[str, Any]) -> str:
    text = str(args.get("text") or "").strip()
    if not text:
        raise ValueError("text is required.")
    output_dir = _prepare_output_dir(args.get("output_dir"), base_file=None)
    kwargs = _common_verify_kwargs(args)
    kwargs.update({"output_dir": str(output_dir)})
    result = _capture_backend_call(verify_text, text, **kwargs)
    return _format_summary(result, title="RefChecker result for pasted text")


def test_reference_api_keys(args: dict[str, Any]) -> str:
    selected = parse_source_selection(str(args.get("sources") or ""))
    custom_rest_path = str(args.get("custom_rest_profiles") or "").strip()
    custom_rest_profiles = load_profiles_file(custom_rest_path) if custom_rest_path else []
    result = _capture_backend_call(
        test_api_keys,
        selected_sources=set(selected) if selected is not None else None,
        springer_api_key=str(args.get("springer_api_key") or os.getenv("REFCHECKER_SPRINGER_API_KEY", "")),
        ieee_api_key=str(args.get("ieee_api_key") or os.getenv("REFCHECKER_IEEE_API_KEY", "")),
        core_api_key=str(args.get("core_api_key") or os.getenv("REFCHECKER_CORE_API_KEY", "")),
        custom_rest_profiles=custom_rest_profiles,
        jsonl_progress=False,
        human_output=False,
    )
    summary = result.get("summary") or {}
    lines = [
        "# RefChecker API key test",
        "",
        f"- Total: **{summary.get('total', 0)}**",
        f"- OK: **{summary.get('ok', 0)}**",
        f"- Failed: **{summary.get('failed', 0)}**",
        f"- Not configured: **{summary.get('skipped', 0)}**",
    ]
    if summary.get("message"):
        lines.extend(["", str(summary["message"])])
    if result.get("results"):
        lines.extend(["", "## Details"])
        for item in result["results"]:
            lines.append(
                f"- {item.get('name') or item.get('source')}: "
                f"{item.get('status')} / {item.get('message')}"
            )
    return "\n".join(lines)


HANDLERS: dict[str, ToolHandler] = {
    "check_reference_file": check_reference_file,
    "check_reference_text": check_reference_text,
    "test_reference_api_keys": test_reference_api_keys,
}


def _response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_result(text: str, *, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    # Notifications do not require a response.
    if request_id is None and method and method.startswith("notifications/"):
        return None

    if method == "initialize":
        client_version = params.get("protocolVersion") or PROTOCOL_VERSION
        return _response(
            request_id,
            {
                "protocolVersion": client_version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": APP_VERSION},
            },
        )
    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(request_id, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if handler is None:
            return _error(request_id, -32602, f"Unknown tool: {name}")
        if not isinstance(arguments, dict):
            return _error(request_id, -32602, "Tool arguments must be an object.")
        try:
            return _response(request_id, _tool_result(handler(arguments)))
        except Exception as exc:  # Return tool errors as MCP tool results, not protocol crashes.
            return _response(request_id, _tool_result(f"{type(exc).__name__}: {exc}", is_error=True))
    if method is None:
        return None
    return _error(request_id, -32601, f"Method not found: {method}")


def send_message(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> None:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            if isinstance(message, list):
                for item in message:
                    if isinstance(item, dict):
                        response = handle_message(item)
                        if response is not None:
                            send_message(response)
                continue
            if not isinstance(message, dict):
                send_message(_error(None, -32700, "Invalid JSON-RPC message."))
                continue
            response = handle_message(message)
            if response is not None:
                send_message(response)
        except json.JSONDecodeError as exc:
            send_message(_error(None, -32700, f"Parse error: {exc}"))
        except Exception as exc:
            print(f"RefChecker MCP server error: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            send_message(_error(None, -32603, f"Internal error: {exc}"))


if __name__ == "__main__":
    main()
