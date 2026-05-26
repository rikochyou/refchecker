"""Utilities for checking browser-rendered links captured by the extension.

LLM web UIs often render a short label such as "arxiv" or "PNAS" while the
actual ``href`` points somewhere else.  Plain selected text cannot expose that
hidden URL, so the browser extension sends link context to the local service and
this module performs lightweight, deterministic checks.
"""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
import xml.etree.ElementTree as ET

import requests

from .utils import clean_doi, extract_year, title_similarity


KNOWN_LABEL_DOMAINS: dict[str, list[str]] = {
    "arxiv": ["arxiv.org"],
    "arxiv.org": ["arxiv.org"],
    "pnas": ["pnas.org", "doi.org"],
    "doi": ["doi.org"],
    "doi.org": ["doi.org"],
    "pubmed": ["pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov"],
    "pmid": ["pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov"],
    "crossref": ["crossref.org", "doi.org"],
    "openalex": ["openalex.org"],
    "semantic scholar": ["semanticscholar.org"],
    "semanticscholar": ["semanticscholar.org"],
    "dblp": ["dblp.org"],
    "nature": ["nature.com", "doi.org"],
    "springer": ["springer.com", "springerlink.com", "doi.org"],
    "ieee": ["ieee.org", "ieeecomputer.org", "doi.org"],
    "acm": ["acm.org", "doi.org"],
    "science": ["science.org", "doi.org"],
    "cell": ["cell.com", "doi.org"],
    "sciencedirect": ["sciencedirect.com", "doi.org"],
    "github": ["github.com"],
    "huggingface": ["huggingface.co"],
}

UNSAFE_SCHEMES = {"javascript", "data", "vbscript", "file"}
TRACKING_QUERY_KEYS = ("url", "u", "q", "target", "to", "redirect", "redirect_url")
HTTP_TIMEOUT = 12


def _safe_text(value: Any, limit: int = 1000) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _host(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.netloc or "").lower().split("@")[-1].split(":")[0]


def _scheme(url: str) -> str:
    return (urlparse(url).scheme or "").lower()


def _host_matches(host: str, domains: list[str]) -> bool:
    host = host.lower()
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _visible_url_host(text: str) -> str:
    match = re.search(r"https?://[^\s<>)\"']+", text, flags=re.I)
    if not match:
        return ""
    return _host(match.group(0))


def _label_tokens(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip(" \t\r\n:：[]()【】<>")


def _expected_domains(label: str) -> tuple[str, list[str]]:
    normalized = _label_tokens(label)
    if not normalized:
        return "", []
    for key, domains in KNOWN_LABEL_DOMAINS.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", normalized):
            return key, domains
    return "", []


def _extract_redirect_target(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in TRACKING_QUERY_KEYS:
        for value in query.get(key, []):
            value = unquote(value).strip()
            if value.startswith(("http://", "https://")):
                return value
    return ""


def _collapse(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def _arxiv_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.netloc.lower().endswith("arxiv.org"):
        return ""
    match = re.search(r"/(?:abs|pdf|html)/([^/?#]+)", parsed.path, flags=re.I)
    if not match:
        return ""
    arxiv_id = match.group(1).removesuffix(".pdf")
    arxiv_id = re.sub(r"v\d+$", "", arxiv_id, flags=re.I)
    return arxiv_id


def _fetch_arxiv_metadata(url: str) -> dict[str, Any]:
    arxiv_id = _arxiv_id_from_url(url)
    if not arxiv_id:
        return {}
    response = requests.get(
        "https://export.arxiv.org/api/query",
        params={"id_list": arxiv_id},
        headers={"User-Agent": "RefChecker/1.2 link-target-check"},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    atom = "{http://www.w3.org/2005/Atom}"
    entry = root.find(f"{atom}entry")
    if entry is None:
        return {}
    title = _collapse(entry.findtext(f"{atom}title", default=""))
    authors = [
        _collapse(author.findtext(f"{atom}name", default=""))
        for author in entry.findall(f"{atom}author")
    ]
    published = entry.findtext(f"{atom}published", default="")
    return {
        "source": "arXiv",
        "id": arxiv_id,
        "title": title,
        "authors": [a for a in authors if a],
        "year": extract_year(published),
        "url": url,
    }


def _doi_from_url_or_text(value: str) -> str:
    parsed = urlparse(value)
    if parsed.netloc.lower().endswith("doi.org"):
        return clean_doi(unquote(parsed.path.lstrip("/")))
    match = re.search(r"10\.\d{4,9}/[^\s\"'<>，。；;、)）\]】]+", value, flags=re.I)
    return clean_doi(match.group(0)) if match else ""


def _fetch_crossref_metadata(url: str) -> dict[str, Any]:
    doi = _doi_from_url_or_text(url)
    if not doi:
        return {}
    response = requests.get(
        f"https://api.crossref.org/works/{doi}",
        headers={"User-Agent": "RefChecker/1.2 link-target-check"},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    message = response.json().get("message") or {}
    title = _collapse((message.get("title") or [""])[0])
    authors = []
    for author in message.get("author") or []:
        name = " ".join(
            part for part in [author.get("given", ""), author.get("family", "")]
            if part
        ).strip()
        if name:
            authors.append(name)
    year_parts = (
        ((message.get("published-print") or {}).get("date-parts") or [[]])[0]
        or ((message.get("published-online") or {}).get("date-parts") or [[]])[0]
        or ((message.get("issued") or {}).get("date-parts") or [[]])[0]
    )
    return {
        "source": "CrossRef",
        "id": doi,
        "title": title,
        "authors": authors,
        "year": str(year_parts[0]) if year_parts else "",
        "url": message.get("URL") or url,
    }


def _meta_content(markup: str, *names: str) -> list[str]:
    values: list[str] = []
    for name in names:
        pattern = (
            r'<meta[^>]+(?:name|property)=["\']'
            + re.escape(name)
            + r'["\'][^>]+content=["\']([^"\']+)["\'][^>]*>'
        )
        values.extend(re.findall(pattern, markup, flags=re.I))
        pattern_reverse = (
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\']'
            + re.escape(name)
            + r'["\'][^>]*>'
        )
        values.extend(re.findall(pattern_reverse, markup, flags=re.I))
    return [_collapse(v) for v in values if _collapse(v)]


def _fetch_html_metadata(url: str) -> dict[str, Any]:
    host = _host(url)
    response = requests.get(
        url,
        headers={"User-Agent": "RefChecker/1.2 link-target-check"},
        timeout=HTTP_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower() and "<html" not in response.text[:1000].lower():
        return {}
    markup = response.text[:300_000]
    title_values = _meta_content(markup, "citation_title", "dc.title", "og:title", "twitter:title")
    title = title_values[0] if title_values else ""
    if not title:
        match = re.search(r"<title[^>]*>(.*?)</title>", markup, flags=re.I | re.S)
        title = _collapse(re.sub(r"<[^>]+>", " ", match.group(1))) if match else ""
    authors = _meta_content(markup, "citation_author", "dc.creator", "article:author")
    year_values = _meta_content(markup, "citation_publication_date", "dc.date", "article:published_time")
    return {
        "source": host or "Web",
        "id": "",
        "title": title,
        "authors": authors[:12],
        "year": extract_year(year_values[0]) if year_values else "",
        "url": response.url or url,
    }


def _fetch_target_metadata(url: str) -> dict[str, Any]:
    if not url.startswith(("http://", "https://")):
        return {}
    try:
        if _arxiv_id_from_url(url):
            return _fetch_arxiv_metadata(url)
        if _doi_from_url_or_text(url):
            return _fetch_crossref_metadata(url)
        return _fetch_html_metadata(url)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _title_candidates(*values: str) -> list[str]:
    candidates: list[str] = []
    for value in values:
        for line in re.split(r"[\r\n]+", value or ""):
            line = re.sub(r"https?://\S+", " ", line)
            line = re.sub(r"\bdoi\s*:\s*\S+", " ", line, flags=re.I)
            line = re.sub(r"^[\s\-*•·]+", "", line).strip(" ：:，,。.;；")
            if not (12 <= len(line) <= 260):
                continue
            if line.lower() in KNOWN_LABEL_DOMAINS:
                continue
            if line.lower().startswith(("authors", "doi ", "doi:", "url ", "链接", "作者")):
                continue
            if not re.search(r"[A-Za-z\u4e00-\u9fff]", line):
                continue
            if line not in candidates:
                candidates.append(line)
    return candidates[:8]


def _best_title_match(target_title: str, candidates: list[str]) -> tuple[str, float]:
    if not target_title or not candidates:
        return "", 0.0
    scored = [(candidate, title_similarity(target_title, candidate)) for candidate in candidates]
    return max(scored, key=lambda item: item[1])


def check_browser_link(link: dict[str, Any], *, fetch_target: bool = False) -> dict[str, Any]:
    label = _safe_text(link.get("text") or link.get("label"), 240)
    href = _safe_text(link.get("href"), 2000)
    title = _safe_text(link.get("title"), 240)
    aria_label = _safe_text(link.get("ariaLabel") or link.get("aria_label"), 240)
    surrounding_text = _safe_text(link.get("surroundingText") or link.get("surrounding_text"), 600)

    host = _host(href)
    scheme = _scheme(href)
    expected_label, expected_domains = _expected_domains(" ".join([label, title, aria_label]))
    visible_host = _visible_url_host(label)
    redirect_target = _extract_redirect_target(href)
    redirect_host = _host(redirect_target) if redirect_target else ""

    status = "ok"
    risk_level = "low"
    issue = ""
    message = "显示文本与真实链接未发现明显冲突。"
    suggestion = "仍建议打开 DOI/出版商页面做最终人工确认。"

    effective_host = redirect_host or host

    if not href:
        status = "warning"
        risk_level = "medium"
        issue = "missing_href"
        message = "页面上看起来像链接，但没有可读取的真实 href。"
        suggestion = "不要直接信任该链接，请复制可见文本后重新核查。"
    elif scheme in UNSAFE_SCHEMES:
        status = "warning"
        risk_level = "high"
        issue = "unsafe_scheme"
        message = f"真实链接使用了不安全或不可核查的协议：{scheme}。"
        suggestion = "不要点击该链接，优先使用数据库返回的 DOI/出版商链接。"
    elif visible_host and not _host_matches(effective_host, [visible_host]):
        status = "warning"
        risk_level = "high"
        issue = "visible_url_mismatch"
        message = f"可见 URL 域名是 {visible_host}，但真实链接指向 {effective_host or host}。"
        suggestion = "这是典型的“显示链接”和“实际链接”不一致，建议按高风险处理。"
    elif expected_domains and not _host_matches(effective_host, expected_domains):
        status = "warning"
        risk_level = "high"
        issue = "label_domain_mismatch"
        expected = " / ".join(expected_domains)
        message = f"链接显示为 {expected_label}，但真实链接域名是 {effective_host or host}，不在预期域名 {expected} 内。"
        suggestion = "不要直接点击；用 RefChecker 返回的正确 DOI/URL 或到对应数据库重新搜索标题。"
    elif redirect_target and redirect_host and redirect_host != host:
        status = "warning"
        risk_level = "medium"
        issue = "redirect_wrapper"
        message = f"真实链接先到 {host}，并在参数中跳转到 {redirect_host}。"
        suggestion = "建议核对最终跳转目标是否为论文数据库或出版商官网。"

    target_url = redirect_target or href
    target_metadata: dict[str, Any] = {}
    expected_title = ""
    target_title_similarity = 0.0
    # Fetching target metadata can be slow. Do it only for explicit pasted-link
    # checks, not for every auto-collected page link in a selected paragraph.
    if fetch_target and href and issue not in {"visible_url_mismatch", "label_domain_mismatch", "unsafe_scheme"}:
        target_metadata = _fetch_target_metadata(target_url)
        target_title = _safe_text(target_metadata.get("title"), 400)
        if target_title:
            candidates = _title_candidates(label, title, aria_label, surrounding_text)
            expected_title, target_title_similarity = _best_title_match(target_title, candidates)
            if expected_title and target_title_similarity < 0.55:
                status = "warning"
                risk_level = "high"
                issue = "target_title_mismatch"
                message = (
                    "链接域名看起来正确，但目标页面实际论文标题与网页显示内容不一致。"
                    f"目标标题：{target_title}"
                )
                suggestion = "这是“链接指向另一篇论文”的高风险情况；请用标题重新检索，或复制正确 arXiv/DOI 链接替换。"
            elif expected_title and not issue:
                message = f"真实链接目标标题与网页显示内容基本一致：{target_title}"
                suggestion = "仍建议打开目标页面做最终人工确认。"
            elif not issue:
                message = f"已读取真实链接目标标题：{target_title}"
                suggestion = "当前没有足够的网页显示标题用于自动比对；请人工确认它是否就是目标论文。"
        elif target_metadata.get("error") and not issue:
            message = f"链接域名未发现明显问题，但读取目标论文元数据失败：{target_metadata['error']}"
            suggestion = "建议打开链接人工核对标题、作者和年份。"

    return {
        "label": label,
        "href": href,
        "host": host,
        "status": status,
        "risk_level": risk_level,
        "issue": issue,
        "message": message,
        "suggestion": suggestion,
        "expected_label": expected_label,
        "expected_domains": expected_domains,
        "visible_url_host": visible_host,
        "redirect_target": redirect_target,
        "redirect_host": redirect_host,
        "target_metadata": target_metadata,
        "target_title": _safe_text(target_metadata.get("title"), 400),
        "target_authors": target_metadata.get("authors") or [],
        "target_year": target_metadata.get("year", ""),
        "target_source": target_metadata.get("source", ""),
        "target_error": target_metadata.get("error", ""),
        "expected_title": expected_title,
        "target_title_similarity": round(target_title_similarity, 3) if target_title_similarity else 0,
        "title": title,
        "aria_label": aria_label,
        "surrounding_text": surrounding_text,
    }


def check_browser_links(links: Any, *, fetch_targets: bool = False, max_links: int | None = None) -> list[dict[str, Any]]:
    if not isinstance(links, list):
        return []

    checked: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    limit = max_links if max_links is not None else (5 if fetch_targets else 20)
    for raw in links[:limit]:
        if not isinstance(raw, dict):
            continue
        key = (_safe_text(raw.get("text") or raw.get("label"), 240), _safe_text(raw.get("href"), 2000))
        if key in seen:
            continue
        seen.add(key)
        checked.append(check_browser_link(raw, fetch_target=fetch_targets))
    return checked
