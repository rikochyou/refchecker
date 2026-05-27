"""LLM-assisted reference parsing.

This module is intentionally limited to extracting structured fields from raw
reference strings.  It must not decide whether a reference is real, correct, or
trustworthy; verification remains the responsibility of the database/DOI
pipeline.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from .author import normalize_author_field
from .utils import clean_doi, extract_year


LLM_PARSE_OFF = "off"
LLM_PARSE_AUTO = "auto"
LLM_PARSE_ALWAYS = "always"
LLM_PARSE_MODES = {LLM_PARSE_OFF, LLM_PARSE_AUTO, LLM_PARSE_ALWAYS}
DEFAULT_LLM_PROVIDER = "openai-compatible"
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_LLM_TIMEOUT = 45


def normalize_llm_parse_mode(value: str | None) -> str:
    mode = str(value or LLM_PARSE_OFF).strip().lower()
    return mode if mode in LLM_PARSE_MODES else LLM_PARSE_OFF


def normalize_llm_provider(value: str | None) -> str:
    provider = str(value or DEFAULT_LLM_PROVIDER).strip().lower()
    if provider in {"openai", "openai-compatible", "compatible"}:
        return DEFAULT_LLM_PROVIDER
    return DEFAULT_LLM_PROVIDER


def resolve_llm_config(
    *,
    llm_parse_mode: str = LLM_PARSE_OFF,
    llm_provider: str = DEFAULT_LLM_PROVIDER,
    llm_model: str = "",
    llm_base_url: str = "",
    llm_api_key: str = "",
    llm_timeout: int | float | str | None = None,
) -> dict[str, Any]:
    """Normalize LLM parsing options and fill environment fallbacks."""
    timeout = DEFAULT_LLM_TIMEOUT
    if llm_timeout not in (None, ""):
        try:
            timeout = max(5, min(180, int(float(llm_timeout))))
        except Exception:
            timeout = DEFAULT_LLM_TIMEOUT
    return {
        "mode": normalize_llm_parse_mode(llm_parse_mode or os.getenv("REFCHECKER_LLM_PARSE_MODE", "")),
        "provider": normalize_llm_provider(llm_provider or os.getenv("REFCHECKER_LLM_PROVIDER", "")),
        "model": (llm_model or os.getenv("REFCHECKER_LLM_MODEL", "") or DEFAULT_LLM_MODEL).strip(),
        "base_url": (llm_base_url or os.getenv("REFCHECKER_LLM_BASE_URL", "") or DEFAULT_LLM_BASE_URL).strip(),
        "api_key": (llm_api_key or os.getenv("REFCHECKER_LLM_API_KEY", "")).strip(),
        "timeout": timeout,
    }


def _is_doi_or_url_only(text: str, doi: str = "") -> bool:
    value = (text or "").strip()
    if not value:
        return False
    if re.fullmatch(r"https?://(?:dx\.)?doi\.org/10\.\S+", value, re.I):
        return True
    if doi and clean_doi(value) == clean_doi(doi):
        return True
    return bool(re.fullmatch(r"(?:doi:\s*)?10\.\d{4,9}/\S+", value, re.I))


def reference_needs_llm_parse(ref: dict[str, Any]) -> bool:
    """Heuristic that identifies references whose rule parse looks weak.

    Kept as a diagnostic/backward-compatible helper.  The main application now
    treats any user-selected LLM mode as LLM-first and falls back to rule fields
    only when the LLM returns no usable value for a field or a row.
    """
    raw = str(ref.get("text") or "").strip()
    title = str(ref.get("title") or "").strip()
    doi = str(ref.get("doi") or "").strip()
    if not raw:
        return False
    if _is_doi_or_url_only(raw, doi):
        return False
    if not title:
        return True
    if title == raw and len(raw) > 40:
        return True
    if re.fullmatch(r"https?://\S+", title, re.I):
        return True
    if re.fullmatch(r"(?:doi:\s*)?10\.\d{4,9}/\S+", title, re.I):
        return True
    if len(title) < 12 and len(raw) > 40 and not doi:
        return True
    if not ref.get("year") and not doi and len(raw.split()) >= 8:
        return True
    return False


def _chat_completions_url(base_url: str) -> str:
    base = (base_url or DEFAULT_LLM_BASE_URL).strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _system_prompt() -> str:
    return (
        "You extract structured bibliographic fields from reference strings. "
        "First identify the citation style, then parse according to that style. "
        "Only extract information explicitly present in the provided text. "
        "Do not invent or infer missing DOI, authors, year, URL, journal, or title. "
        "The title must be the work title only; exclude journal/conference/book title, "
        "volume, issue, pages, publisher, DOI, URL, and arXiv identifiers. "
        "Do not judge whether the reference is real. "
        "Return JSON only."
    )


def _user_prompt(blocks: list[dict[str, Any]]) -> str:
    return json.dumps(
        {
            "task": "Extract reference fields. Return an object with key 'references'.",
            "schema": {
                "references": [
                    {
                        "input_index": "integer copied from input",
                        "citation_style": "string; likely style such as apa, ieee, vancouver, mla, chicago, bibtex, ris, unknown",
                        "title": "string; explicit title only",
                        "authors": "string or array; all explicit authors in citation order, preferably as 'Family, Given' entries joined by ' and '",
                        "year": "string; 4-digit year only",
                        "doi": "string; DOI only, no URL prefix",
                        "url": "string; explicit URL if present",
                        "confidence": "number from 0 to 1",
                        "warning": "string if the input is ambiguous or fields are missing",
                    }
                ]
            },
            "rules": [
                "For each input, first identify its citation style before extracting fields.",
                "For APA-like references, authors are before the parenthesized year; the title starts after the year and ends before the container/source such as journal, conference, proceedings, book title, volume, issue, pages, DOI, URL, or arXiv link.",
                "For IEEE/Vancouver-like references, preserve every explicitly listed author in order; do not collapse multiple authors into one string if separators are clear.",
                "Return every explicitly listed author. Do not replace names with et al. unless et al. is literally the only information present.",
                "Return authors normalized as a BibTeX-compatible 'and' list when possible, for example: 'Vaswani, A. and Shazeer, N. and Parmar, N.'.",
                "Never include DOI, URL, arXiv ID, venue/container, volume, issue, or pages in the title.",
                "Never fabricate missing fields.",
                "If a field is not explicit, return an empty string for that field.",
                "Do not include explanations outside JSON.",
            ],
            "inputs": blocks,
        },
        ensure_ascii=False,
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("LLM returned empty content.")
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I).strip()
        raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(raw[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("LLM JSON response must be an object.")
    return payload


def call_openai_compatible_parser(blocks: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    if not blocks:
        return []
    api_key = str(config.get("api_key") or "").strip()
    if not api_key:
        raise ValueError("LLM API key is not configured.")
    url = _chat_completions_url(str(config.get("base_url") or DEFAULT_LLM_BASE_URL))
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.get("model") or DEFAULT_LLM_MODEL,
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _user_prompt(blocks)},
            ],
            "temperature": 0,
        },
        timeout=config.get("timeout") or DEFAULT_LLM_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    content = (
        ((payload.get("choices") or [{}])[0].get("message") or {}).get("content")
        if isinstance(payload, dict)
        else ""
    )
    decoded = _extract_json_object(content or "")
    refs = decoded.get("references")
    if not isinstance(refs, list):
        raise ValueError("LLM response missing references array.")
    return [item for item in refs if isinstance(item, dict)]


def _string_field(item: dict[str, Any], name: str) -> str:
    value = item.get(name)
    if isinstance(value, list):
        parts = []
        for entry in value:
            if isinstance(entry, dict):
                family = str(
                    entry.get("family")
                    or entry.get("last")
                    or entry.get("last_name")
                    or entry.get("surname")
                    or ""
                ).strip()
                given = str(
                    entry.get("given")
                    or entry.get("first")
                    or entry.get("first_name")
                    or entry.get("initials")
                    or ""
                ).strip()
                name = str(entry.get("name") or entry.get("raw") or "").strip()
                if family:
                    text = f"{family}, {given}".strip().rstrip(",")
                else:
                    text = name
            else:
                text = str(entry).strip()
            if text:
                parts.append(text)
        value = " and ".join(parts)
    return str(value or "").strip()


def _sanitize_llm_item(item: dict[str, Any]) -> dict[str, Any]:
    title = _string_field(item, "title").strip().strip('"“”')
    title = re.sub(r"\s+", " ", title)
    doi = clean_doi(_string_field(item, "doi"))
    year = extract_year(_string_field(item, "year"))
    url = _string_field(item, "url")
    url_match = re.search(r"https?://[^\s\"'<>]+", url)
    url = url_match.group(0).strip().rstrip(".,;，。；、)") if url_match else ""
    confidence = item.get("confidence", "")
    try:
        confidence = round(float(confidence), 3)
    except Exception:
        confidence = ""
    citation_style = _string_field(item, "citation_style").strip().lower()
    citation_style = re.sub(r"[^a-z0-9_-]+", "-", citation_style).strip("-")
    return {
        "title": "" if _is_doi_or_url_only(title, doi) else title,
        "authors": normalize_author_field(_string_field(item, "authors")),
        "year": year,
        "doi": doi,
        "url": url,
        "parser_citation_style": citation_style,
        "parser_confidence": confidence,
        "parser_warning": _string_field(item, "warning"),
    }


def _merge_llm_fields(ref: dict[str, Any], llm_item: dict[str, Any], *, mode: str) -> dict[str, Any]:
    parsed = _sanitize_llm_item(llm_item)
    merged = dict(ref)
    used_fields: list[str] = []
    for field in ["title", "authors", "year", "doi", "url"]:
        value = parsed.get(field)
        if value:
            merged[field] = value
            used_fields.append(field)
    if used_fields:
        merged["parser"] = "llm"
        style_note = f"; detected style: {parsed['parser_citation_style']}" if parsed.get("parser_citation_style") else ""
        merged["parser_note"] = f"LLM-first parsing ({mode}){style_note}; extracted: {', '.join(used_fields)}"
    else:
        merged.setdefault("parser", "rules")
        merged["parser_note"] = f"LLM-first parsing ({mode}) returned no usable fields; kept rule parser output."
    if parsed.get("parser_citation_style"):
        merged["parser_citation_style"] = parsed["parser_citation_style"]
    if parsed.get("parser_confidence") != "":
        merged["parser_confidence"] = parsed["parser_confidence"]
    if parsed.get("parser_warning"):
        merged["parser_warning"] = parsed["parser_warning"]
    return merged


def apply_llm_parsing(
    refs: list[dict[str, Any]],
    *,
    llm_parse_mode: str = LLM_PARSE_OFF,
    llm_provider: str = DEFAULT_LLM_PROVIDER,
    llm_model: str = "",
    llm_base_url: str = "",
    llm_api_key: str = "",
    llm_timeout: int | float | str | None = None,
    log=None,
) -> list[dict[str, Any]]:
    """Return refs with optional LLM-extracted fields merged in.

    When the user enables an LLM mode, parsing is LLM-first: every non-empty
    reference is sent to the LLM, and the existing rule-parsed fields are kept
    only as the fallback for fields/rows the LLM cannot parse.
    """
    config = resolve_llm_config(
        llm_parse_mode=llm_parse_mode,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_timeout=llm_timeout,
    )
    mode = config["mode"]
    prepared = [{**ref, "parser": ref.get("parser") or "rules"} for ref in refs]
    if mode == LLM_PARSE_OFF or not prepared:
        return prepared

    targets: list[dict[str, Any]] = []
    for pos, ref in enumerate(prepared):
        raw = str(ref.get("text") or ref.get("title") or "").strip()
        if raw and not _is_doi_or_url_only(raw, str(ref.get("doi") or "")):
            targets.append({"input_index": pos, "text": raw[:4000]})

    if not targets:
        return prepared
    if not config.get("api_key"):
        warning = "LLM parsing requested but REFCHECKER_LLM_API_KEY / llm_api_key is not configured; kept rule parser output."
        if log:
            log(f"LLM parsing skipped: missing API key ({len(targets)} item(s))")
        for target in targets:
            prepared[target["input_index"]]["parser_warning"] = warning
        return prepared

    if config.get("provider") != DEFAULT_LLM_PROVIDER:
        raise ValueError(f"Unsupported LLM provider: {config.get('provider')}")

    if log:
        log(f"LLM-first parsing: {len(targets)} item(s), mode {mode}, model {config.get('model')}")

    llm_items: list[dict[str, Any]] = []
    chunk_size = 20
    for start in range(0, len(targets), chunk_size):
        chunk = targets[start : start + chunk_size]
        llm_items.extend(call_openai_compatible_parser(chunk, config))

    by_index: dict[int, dict[str, Any]] = {}
    for item in llm_items:
        try:
            index = int(item.get("input_index"))
        except Exception:
            continue
        by_index[index] = item

    for target in targets:
        index = int(target["input_index"])
        if index in by_index:
            prepared[index] = _merge_llm_fields(prepared[index], by_index[index], mode=mode)
        else:
            prepared[index]["parser_warning"] = "LLM parser did not return this reference; kept rule parser output."
    return prepared
