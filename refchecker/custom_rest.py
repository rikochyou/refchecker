"""Configurable REST API source adapter for advanced RefChecker users."""

from __future__ import annotations

import json
from typing import Any

import requests

from .author import parse_author_name, author_display_list, candidate_score
from .utils import clean_doi, extract_year, title_similarity


DEFAULT_TIMEOUT = 20


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _json_object(value: Any) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
        return dict(parsed) if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _render_template(value: Any, variables: dict[str, str]) -> Any:
    if isinstance(value, str):
        rendered = value
        for key, replacement in variables.items():
            rendered = rendered.replace("{" + key + "}", replacement or "")
        return rendered
    if isinstance(value, dict):
        return {k: _render_template(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_render_template(v, variables) for v in value]
    return value


def _path_get(data: Any, path: str | None, default: Any = "") -> Any:
    if not path:
        return default
    cur = data
    for raw_part in str(path).split("."):
        part = raw_part.strip()
        if not part:
            continue
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except Exception:
                return default
        elif isinstance(cur, dict):
            if part not in cur:
                return default
            cur = cur[part]
        else:
            return default
    return cur


def _first_value(item: dict, paths: list[str]) -> Any:
    for path in paths:
        value = _path_get(item, path, None)
        if value not in (None, "", [], {}):
            return value
    return ""


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(_as_text(v) for v in value if _as_text(v))
    if isinstance(value, dict):
        for key in ("name", "full_name", "displayName", "display_name", "title", "value"):
            if value.get(key):
                return _as_text(value.get(key))
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _author_list(raw: Any) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, str):
        pieces = [p.strip() for p in raw.replace(" and ", ",").split(",") if p.strip()]
    elif isinstance(raw, list):
        pieces = raw
    else:
        pieces = [raw]
    authors = []
    for item in pieces:
        name = _as_text(item)
        if name:
            authors.append(parse_author_name(name))
    return authors


def _list_results(payload: Any, results_path: str) -> list:
    value = _path_get(payload, results_path, None) if results_path else None
    if value is None:
        for path in ("results", "records", "items", "data", "articles", "works"):
            value = _path_get(payload, path, None)
            if isinstance(value, list):
                break
    if isinstance(value, list):
        return value
    if isinstance(payload, list):
        return payload
    return []


def custom_source_id(profile: dict) -> str:
    raw = profile.get("id") or profile.get("key") or profile.get("name") or "custom"
    safe = "".join(
        ch.lower() if (ch.isalnum() or ch in "_-") else "-"
        for ch in str(raw)
    ).strip("-")
    return f"custom:{safe or 'custom'}"


def normalize_profiles(profiles: Any) -> list[dict]:
    if isinstance(profiles, str):
        if not profiles.strip():
            return []
        try:
            profiles = json.loads(profiles)
        except Exception:
            return []
    if isinstance(profiles, dict):
        profiles = [profiles]
    if not isinstance(profiles, list):
        return []
    normalized = []
    for index, profile in enumerate(profiles):
        if not isinstance(profile, dict):
            continue
        item = dict(profile)
        item.setdefault("id", f"custom-{index + 1}")
        item.setdefault("name", f"Custom REST {index + 1}")
        item.setdefault("method", "GET")
        item.setdefault("authType", "none")
        item.setdefault("apiKeyParam", "api_key")
        item.setdefault("apiKeyHeader", "Authorization")
        item.setdefault("queryParams", '{"q":"{title}"}')
        item.setdefault("headers", "{}")
        item.setdefault("resultsPath", "results")
        item.setdefault("titlePath", "title")
        item.setdefault("authorsPath", "authors")
        item.setdefault("yearPath", "year")
        item.setdefault("doiPath", "doi")
        item.setdefault("urlPath", "url")
        item.setdefault("venuePath", "venue")
        item.setdefault("typePath", "type")
        item["sourceKey"] = custom_source_id(item)
        if _as_bool(item.get("enabled"), True) and item.get("endpoint"):
            normalized.append(item)
    return normalized


def load_profiles_file(path: str | None) -> list[dict]:
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as f:
        return normalize_profiles(json.load(f))


def profile_map(profiles: list[dict] | None) -> dict[str, dict]:
    return {p.get("sourceKey") or custom_source_id(p): p for p in normalize_profiles(profiles or [])}


def test_custom_rest_profile(profile: dict, query: str = "machine learning",
                             email: str = "") -> dict:
    """Probe one custom REST profile with a safe generic query."""
    normalized = normalize_profiles([profile])
    if not normalized:
        name = profile.get("name") or "Custom REST API"
        endpoint = profile.get("endpoint") or ""
        return {
            "source": custom_source_id(profile),
            "name": name,
            "endpoint": endpoint,
            "ok": False,
            "status": "not_configured",
            "message": f"{name} 未配置 endpoint 或 Profile 未启用。",
            "status_code": "",
            "records": "",
        }

    item = normalized[0]
    name = item.get("name") or "Custom REST API"
    endpoint = (item.get("endpoint") or "").strip()
    source = item.get("sourceKey") or custom_source_id(item)
    variables = {
        "title": query,
        "author": "",
        "year": "",
        "email": email or "",
    }
    params = _render_template(_json_object(item.get("queryParams")), variables)
    headers = _render_template(_json_object(item.get("headers")), variables)
    method = (item.get("method") or "GET").upper()
    api_key = item.get("apiKey") or ""
    auth_type = (item.get("authType") or "none").lower()
    if api_key:
        if auth_type == "query":
            params[item.get("apiKeyParam") or "api_key"] = api_key
        elif auth_type == "header":
            headers[item.get("apiKeyHeader") or "X-API-Key"] = api_key
        elif auth_type == "bearer":
            headers[item.get("apiKeyHeader") or "Authorization"] = f"Bearer {api_key}"

    try:
        if method == "POST":
            response = requests.post(endpoint, json=params, headers=headers, timeout=DEFAULT_TIMEOUT)
        else:
            response = requests.get(endpoint, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
        status_code = response.status_code
        try:
            payload = response.json()
        except Exception:
            payload = None
        record_count = None
        if payload is not None:
            records = _list_results(payload, item.get("resultsPath") or "")
            record_count = len(records)

        if status_code in (401, 403):
            return {
                "source": source,
                "name": name,
                "endpoint": endpoint,
                "ok": False,
                "status": "invalid_key",
                "message": f"{name} 拒绝访问（HTTP {status_code}），请检查 API Key / authType / Header 或 Query 参数。",
                "status_code": status_code,
                "records": record_count if record_count is not None else "",
            }
        if status_code == 429:
            return {
                "source": source,
                "name": name,
                "endpoint": endpoint,
                "ok": False,
                "status": "rate_limited",
                "message": f"{name} 请求受限（HTTP 429），配置可能可用但当前触发了限流。",
                "status_code": status_code,
                "records": record_count if record_count is not None else "",
            }
        if not (200 <= status_code < 300):
            return {
                "source": source,
                "name": name,
                "endpoint": endpoint,
                "ok": False,
                "status": "http_error",
                "message": f"{name} 返回 HTTP {status_code}，请检查 endpoint、参数模板或服务权限。",
                "status_code": status_code,
                "records": record_count if record_count is not None else "",
            }
        if payload is None:
            return {
                "source": source,
                "name": name,
                "endpoint": endpoint,
                "ok": False,
                "status": "invalid_response",
                "message": f"{name} 已连通，但响应不是可解析的 JSON。",
                "status_code": status_code,
                "records": "",
            }
        message = f"{name} 连通成功，REST Profile 已返回 JSON。"
        if record_count is not None:
            message += f" 按当前 resultsPath 解析到 {record_count} 条记录。"
        return {
            "source": source,
            "name": name,
            "endpoint": endpoint,
            "ok": True,
            "status": "ok",
            "message": message,
            "status_code": status_code,
            "records": record_count if record_count is not None else "",
        }
    except Exception as exc:
        return {
            "source": source,
            "name": name,
            "endpoint": endpoint,
            "ok": False,
            "status": "network_error",
            "message": f"{name} 连接失败：{type(exc).__name__}: {exc}",
            "status_code": "",
            "records": "",
        }


def search_custom_rest(profile: dict, title: str, author: str, year: str,
                       threshold: float, email: str = "") -> dict:
    name = profile.get("name") or "Custom REST"
    endpoint = (profile.get("endpoint") or "").strip()
    if not endpoint:
        return {"found": False, "reason": f"{name} 未配置 endpoint", "source": name}

    variables = {"title": title or "", "author": author or "", "year": year or "", "email": email or ""}
    params = _render_template(_json_object(profile.get("queryParams")), variables)
    headers = _render_template(_json_object(profile.get("headers")), variables)
    method = (profile.get("method") or "GET").upper()
    api_key = profile.get("apiKey") or ""
    auth_type = (profile.get("authType") or "none").lower()
    if api_key:
        if auth_type == "query":
            params[profile.get("apiKeyParam") or "api_key"] = api_key
        elif auth_type == "header":
            headers[profile.get("apiKeyHeader") or "X-API-Key"] = api_key
        elif auth_type == "bearer":
            headers[profile.get("apiKeyHeader") or "Authorization"] = f"Bearer {api_key}"

    try:
        if method == "POST":
            response = requests.post(endpoint, json=params, headers=headers, timeout=DEFAULT_TIMEOUT)
        else:
            response = requests.get(endpoint, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {
            "found": False,
            "status": "not_found",
            "matched_title": "",
            "similarity": 0.0,
            "source": name,
            "reason": f"{name} 请求失败: {type(exc).__name__}: {exc}",
        }

    results = _list_results(payload, profile.get("resultsPath") or "")
    candidates: list[dict] = []
    for item in results[:10]:
        if not isinstance(item, dict):
            continue
        item_title = _as_text(_first_value(item, [profile.get("titlePath") or "", "title", "name"]))
        authors = _author_list(_first_value(item, [profile.get("authorsPath") or "", "authors", "creators"]))
        item_year = extract_year(_as_text(_first_value(item, [profile.get("yearPath") or "", "year", "publicationYear", "published"])))
        candidate = {
            "found": False,
            "status": "not_found",
            "similarity": title_similarity(title, item_title) if title and item_title else 0.0,
            "matched_title": item_title,
            "author_list": authors,
            "authors": author_display_list(authors, limit=3),
            "year": item_year,
            "venue": _as_text(_first_value(item, [profile.get("venuePath") or "", "venue", "journal", "publisher"])),
            "type": _as_text(_first_value(item, [profile.get("typePath") or "", "type", "documentType"])),
            "doi": clean_doi(_as_text(_first_value(item, [profile.get("doiPath") or "", "doi", "DOI"]))),
            "url": _as_text(_first_value(item, [profile.get("urlPath") or "", "url", "link"])),
            "source": name,
        }
        candidates.append(candidate)

    if not candidates:
        return {
            "found": False,
            "status": "not_found",
            "matched_title": "",
            "similarity": 0.0,
            "source": name,
            "reason": f"{name} 未返回可解析记录",
        }

    best = max(candidates, key=lambda c: candidate_score(c, author, year))
    best["found"] = best.get("similarity", 0) >= threshold
    best["status"] = "found" if best["found"] else "not_found"
    if not best["found"]:
        best["reason"] = f"{name} 最高标题相似度 {best.get('similarity', 0):.0%}"
    return best
