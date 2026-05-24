"""RefChecker — AI 幻觉引用与参考文献元数据核验."""
import os
import re
import sys
import time

import requests

SOURCE_ALIASES = {
    "crossref": "crossref",
    "openalex": "openalex",
    "semantic": "semantic-scholar",
    "semanticscholar": "semantic-scholar",
    "semantic-scholar": "semantic-scholar",
    "s2": "semantic-scholar",
    "arxiv": "arxiv",
    "pubmed": "pubmed",
    "springer": "springer",
    "springer-nature": "springer",
    "ieee": "ieee",
    "ieee-xplore": "ieee",
    "core": "core",
    "dblp": "dblp",
    "url": "url",

}


def parse_source_selection(value: str | None) -> list[str] | None:
    if not value or not value.strip():
        return None
    selected: list[str] = []
    invalid = []
    for raw in re.split(r"[,，\s]+", value.strip().lower()):
        if not raw:
            continue
        normalized = raw if raw.startswith("custom:") else SOURCE_ALIASES.get(raw)
        if normalized:
            if normalized not in selected:
                selected.append(normalized)
        else:
            invalid.append(raw)
    if invalid:
        valid = ", ".join(sorted(set(SOURCE_ALIASES.values())))
        raise ValueError(f"未知数据源: {', '.join(invalid)}。可选: {valid}")
    return selected


DEFAULT_SOURCE_ORDER = [
    "crossref", "openalex", "semantic-scholar", "arxiv", "pubmed",
    "springer", "ieee", "core", "dblp",
]


def build_source_order(selection: list[str] | None, extra_sources: list[str] | None = None) -> list[str]:
    extra_sources = extra_sources or []
    if selection is None:
        return list(DEFAULT_SOURCE_ORDER) + [s for s in extra_sources if s not in DEFAULT_SOURCE_ORDER]
    order = list(selection)
    for name in DEFAULT_SOURCE_ORDER:
        if name not in order:
            order.append(name)
    for name in extra_sources:
        if name not in order:
            order.append(name)
    return [n for n in order if n != "url"]


def source_selected(selection: list[str] | None, name: str, default: bool = True) -> bool:
    return default if selection is None else (name in selection or default)


API_KEY_TEST_QUERY = "machine learning"
API_KEY_TEST_TIMEOUT = 15


def _api_key_test_result(source: str, name: str, endpoint: str, *,
                         ok: bool, status: str, message: str,
                         status_code: int | str = "", records: int | str = "") -> dict:
    return {
        "source": source,
        "name": name,
        "endpoint": endpoint,
        "ok": ok,
        "status": status,
        "message": message,
        "status_code": status_code,
        "records": records,
    }


def _extract_api_error(payload) -> str:
    if not isinstance(payload, dict):
        return ""
    candidates = [
        payload.get("error"),
        payload.get("message"),
        payload.get("apiMessage"),
        payload.get("api_message"),
        payload.get("status"),
    ]
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        candidates.append(errors[0])
    for item in candidates:
        if isinstance(item, dict):
            item = item.get("message") or item.get("detail") or item.get("error")
        if item:
            return str(item)
    return ""


def _classify_api_key_response(source: str, name: str, endpoint: str,
                               response, payload, record_count: int | None) -> dict:
    status_code = getattr(response, "status_code", "")
    if status_code in (401, 403):
        return _api_key_test_result(
            source, name, endpoint,
            ok=False,
            status="invalid_key",
            status_code=status_code,
            records=record_count if record_count is not None else "",
            message=f"{name} 拒绝访问（HTTP {status_code}），请检查 API Key 是否正确或是否有访问权限。",
        )
    if status_code == 429:
        return _api_key_test_result(
            source, name, endpoint,
            ok=False,
            status="rate_limited",
            status_code=status_code,
            records=record_count if record_count is not None else "",
            message=f"{name} 请求受限（HTTP 429），Key/网络可能可用，但当前触发了限流。",
        )
    if isinstance(status_code, int) and not (200 <= status_code < 300):
        return _api_key_test_result(
            source, name, endpoint,
            ok=False,
            status="http_error",
            status_code=status_code,
            records=record_count if record_count is not None else "",
            message=f"{name} 接口返回 HTTP {status_code}，请稍后重试或检查服务权限。",
        )

    api_error = _extract_api_error(payload)
    if api_error:
        lower_error = api_error.lower()
        error_like = any(token in lower_error for token in [
            "error", "invalid", "unauthorized", "forbidden", "denied",
            "missing", "exceed", "limit", "failed", "failure",
        ])
        if not error_like:
            api_error = ""
    if api_error:
        lower_error = api_error.lower()
        auth_error = any(token in lower_error for token in [
            "api key", "apikey", "key", "token", "auth",
            "unauthorized", "forbidden", "invalid",
        ])
        return _api_key_test_result(
            source, name, endpoint,
            ok=False,
            status="invalid_key" if auth_error else "api_error",
            status_code=status_code,
            records=record_count if record_count is not None else "",
            message=f"{name} 接口返回错误：{api_error}",
        )

    return _api_key_test_result(
        source, name, endpoint,
        ok=True,
        status="ok",
        status_code=status_code,
        records=record_count if record_count is not None else "",
        message=f"{name} 连通成功，API Key 已被接口接受"
                + (f"，样例查询返回 {record_count} 条记录。" if record_count is not None else "。"),
    )


def test_springer_api_key(api_key: str) -> dict:
    endpoint = "https://api.springernature.com/meta/v2/json"
    name = "Springer Nature"
    source = "springer"
    if not api_key:
        return _api_key_test_result(
            source, name, endpoint,
            ok=False,
            status="not_configured",
            message="未配置 Springer Nature API Key。",
        )
    try:
        response = requests.get(
            endpoint,
            params={"q": API_KEY_TEST_QUERY, "p": 1, "api_key": api_key},
            timeout=API_KEY_TEST_TIMEOUT,
        )
        try:
            payload = response.json()
        except Exception:
            payload = None
        records = payload.get("records", []) if isinstance(payload, dict) else []
        record_count = len(records) if isinstance(records, list) else None
        return _classify_api_key_response(source, name, endpoint, response, payload, record_count)
    except Exception as exc:
        return _api_key_test_result(
            source, name, endpoint,
            ok=False,
            status="network_error",
            message=f"{name} 连接失败：{type(exc).__name__}: {exc}",
        )


def test_ieee_api_key(api_key: str) -> dict:
    endpoint = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
    name = "IEEE Xplore"
    source = "ieee"
    if not api_key:
        return _api_key_test_result(
            source, name, endpoint,
            ok=False,
            status="not_configured",
            message="未配置 IEEE Xplore API Key。",
        )
    try:
        response = requests.get(
            endpoint,
            params={
                "apikey": api_key,
                "format": "json",
                "max_records": 1,
                "querytext": API_KEY_TEST_QUERY,
            },
            timeout=API_KEY_TEST_TIMEOUT,
        )
        try:
            payload = response.json()
        except Exception:
            payload = None
        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        record_count = len(articles) if isinstance(articles, list) else None
        return _classify_api_key_response(source, name, endpoint, response, payload, record_count)
    except Exception as exc:
        return _api_key_test_result(
            source, name, endpoint,
            ok=False,
            status="network_error",
            message=f"{name} 连接失败：{type(exc).__name__}: {exc}",
        )


def test_core_api_key(api_key: str) -> dict:
    endpoint = "https://api.core.ac.uk/v3/search/works"
    name = "CORE"
    source = "core"
    if not api_key:
        return _api_key_test_result(
            source, name, endpoint,
            ok=False,
            status="not_configured",
            message="未配置 CORE API Key。",
        )
    try:
        response = requests.get(
            endpoint,
            params={"q": API_KEY_TEST_QUERY, "limit": 1},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=API_KEY_TEST_TIMEOUT,
        )
        try:
            payload = response.json()
        except Exception:
            payload = None
        records = payload.get("results", []) if isinstance(payload, dict) else []
        record_count = len(records) if isinstance(records, list) else None
        return _classify_api_key_response(source, name, endpoint, response, payload, record_count)
    except Exception as exc:
        return _api_key_test_result(
            source, name, endpoint,
            ok=False,
            status="network_error",
            message=f"{name} 连接失败：{type(exc).__name__}: {exc}",
        )


def test_api_keys(*, selected_sources: set[str] | None = None,
                  springer_api_key: str = "", ieee_api_key: str = "",
                  core_api_key: str = "", use_springer: bool = True,
                  use_ieee: bool = True, use_core: bool = True,
                  custom_rest_profiles: list[dict] | None = None,
                  jsonl_progress: bool = False,
                  human_output: bool = True) -> dict:
    """测试 API Key 增强源的接口连通性与鉴权方式，不核验文献文件。"""
    log_stream = sys.stderr if jsonl_progress else sys.stdout

    def log(message: str = "") -> None:
        if human_output:
            print(message, file=log_stream, flush=True)

    def event(event_type: str, **payload) -> None:
        if jsonl_progress:
            from .verifier import emit_jsonl

            emit_jsonl(event_type, **payload)

    configs = [
        ("springer", "Springer Nature", springer_api_key.strip(), use_springer, test_springer_api_key),
        ("ieee", "IEEE Xplore", ieee_api_key.strip(), use_ieee, test_ieee_api_key),
        ("core", "CORE", core_api_key.strip(), use_core, test_core_api_key),
    ]

    selected_configs = []
    for source, name, key, enabled, tester in configs:
        if not enabled:
            continue
        if selected_sources is None:
            if key:
                selected_configs.append((source, name, lambda key=key, tester=tester: tester(key)))
        elif source in selected_sources:
            selected_configs.append((source, name, lambda key=key, tester=tester: tester(key)))

    if custom_rest_profiles:
        from .custom_rest import normalize_profiles, test_custom_rest_profile

        for profile in normalize_profiles(custom_rest_profiles):
            source = profile.get("sourceKey")
            name = profile.get("name") or source or "Custom REST API"
            if selected_sources is not None and source not in selected_sources:
                continue
            selected_configs.append(
                (source, name, lambda profile=profile: test_custom_rest_profile(profile))
            )

    event("api_key_test_started", total=len(selected_configs))
    if not selected_configs:
        message = "未配置需要测试的 API。请先填写 Springer / IEEE / CORE API Key，或为自定义 REST Profile 配置 endpoint。"
        log(f"ℹ️ {message}")
        summary = {"total": 0, "ok": 0, "failed": 0, "skipped": 0, "message": message}
        event("api_key_test_summary", **summary, results=[])
        return {"results": [], "summary": summary}

    log("🔐 开始测试 API 连通性（不会输出 Key 明文）...")
    results = []
    for index, (source, name, tester) in enumerate(selected_configs, start=1):
        event("api_key_test_source_started", index=index, total=len(selected_configs),
              source=source, name=name)
        result = tester()
        results.append(result)
        icon = "✅" if result.get("ok") else ("⚠️" if result.get("status") == "not_configured" else "❌")
        status_code = result.get("status_code", "")
        suffix = f" (HTTP {status_code})" if status_code != "" else ""
        log(f"{icon} {name}: {result.get('message', '')}{suffix}")
        event("api_key_test_result", index=index, total=len(selected_configs), result=result)

    ok_count = sum(1 for item in results if item.get("ok"))
    skipped_count = sum(1 for item in results if item.get("status") == "not_configured")
    failed_count = len(results) - ok_count - skipped_count
    summary = {
        "total": len(results),
        "ok": ok_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "message": f"API Key 测试完成：成功 {ok_count}，失败 {failed_count}，未配置 {skipped_count}。",
    }
    log(summary["message"])
    event("api_key_test_summary", **summary, results=results)
    return {"results": results, "summary": summary}

