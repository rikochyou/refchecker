"""RefChecker — AI 幻觉引用与参考文献元数据核验."""
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests

from .utils import strip_latex, clean_doi, title_similarity, extract_year, truncate
from .author import (
    parse_author_name, author_display_list,
    first_author_lastname, compare_author_lists,
    candidate_score,
)

# --------------------------- API 结果构造 ---------------------------

def crossref_author_list(item: dict) -> list[dict]:
    authors = []
    for a in item.get("author", []) or []:
        if a.get("family") or a.get("given"):
            authors.append(parse_author_name(given=a.get("given", ""), family=a.get("family", "")))
        elif a.get("name"):
            authors.append(parse_author_name(a.get("name", "")))
    return authors


def openalex_author_list(item: dict) -> list[dict]:
    authors = []
    for authorship in item.get("authorships", []) or []:
        author = authorship.get("author", {}) or {}
        name = author.get("display_name", "")
        if name:
            authors.append(parse_author_name(name))
    return authors


def semantic_scholar_author_list(item: dict) -> list[dict]:
    authors = []
    for author in item.get("authors", []) or []:
        name = author.get("name", "") if isinstance(author, dict) else str(author)
        if name:
            authors.append(parse_author_name(name))
    return authors


def arxiv_author_list(entry: ET.Element, ns: dict[str, str]) -> list[dict]:
    authors = []
    for author_el in entry.findall("atom:author", ns):
        name = (author_el.findtext("atom:name", default="", namespaces=ns) or "").strip()
        if name:
            authors.append(parse_author_name(name))
    return authors


def pubmed_author_list(item: dict) -> list[dict]:
    authors = []
    for author in item.get("authors", []) or []:
        if not isinstance(author, dict):
            continue
        name = author.get("name") or " ".join(
            part for part in [author.get("lastname", ""), author.get("initials", "")]
            if part
        )
        if name:
            authors.append(parse_author_name(name))
    return authors


def springer_author_list(item: dict) -> list[dict]:
    authors = []
    for creator in item.get("creators", []) or []:
        if isinstance(creator, dict):
            name = creator.get("creator", "")
        else:
            name = str(creator)
        if name:
            authors.append(parse_author_name(name))
    return authors


def ieee_author_list(item: dict) -> list[dict]:
    raw = item.get("authors", {}) or {}
    if isinstance(raw, dict):
        raw = raw.get("authors", [])
    if isinstance(raw, str):
        raw = [raw]
    authors = []
    for author in raw or []:
        if isinstance(author, dict):
            name = author.get("full_name") or author.get("name") or ""
        else:
            name = str(author)
        if name:
            authors.append(parse_author_name(name))
    return authors


def core_author_list(item: dict) -> list[dict]:
    raw = item.get("authors", []) or []
    if isinstance(raw, str):
        raw = [raw]
    authors = []
    for author in raw:
        if isinstance(author, dict):
            name = author.get("name") or author.get("displayName") or ""
        else:
            name = str(author)
        if name:
            authors.append(parse_author_name(name))
    return authors


def dblp_author_list(info: dict) -> list[dict]:
    raw = (info.get("authors") or {}).get("author", [])
    if isinstance(raw, dict):
        raw = [raw]
    if isinstance(raw, str):
        raw = [raw]

    authors = []
    for a in raw or []:
        if isinstance(a, dict):
            name = a.get("text") or a.get("#text") or a.get("name") or ""
        else:
            name = str(a)
        if name:
            authors.append(parse_author_name(name))
    return authors


def build_crossref_result(item: dict, title: str, source: str = "CrossRef") -> dict:
    item_title = " ".join(item.get("title", []) or [])
    authors = crossref_author_list(item)
    issued = item.get("issued", {}).get("date-parts", [[None]])
    year = issued[0][0] if issued and issued[0] else ""
    return {
        "similarity": title_similarity(title, item_title) if title and item_title else 0.0,
        "matched_title": item_title,
        "author_list": authors,
        "authors": author_display_list(authors, limit=3),
        "year": year or "",
        "venue": (item.get("container-title") or [""])[0],
        "type": item.get("type", ""),
        "doi": item.get("DOI", ""),
        "url": item.get("URL", ""),
        "source": source,
    }


def build_openalex_result(item: dict, title: str) -> dict:
    item_title = item.get("title") or item.get("display_name") or ""
    authors = openalex_author_list(item)
    host = item.get("primary_location", {}) or {}
    source = (host.get("source") or {}).get("display_name", "") if host else ""
    return {
        "similarity": title_similarity(title, item_title) if title and item_title else 0.0,
        "matched_title": item_title,
        "author_list": authors,
        "authors": author_display_list(authors, limit=3),
        "year": item.get("publication_year", ""),
        "venue": source,
        "type": item.get("type", ""),
        "doi": clean_doi((item.get("doi") or "").replace("https://doi.org/", "")),
        "url": item.get("id", ""),
        "source": "OpenAlex",
    }


def build_semantic_scholar_result(item: dict, title: str) -> dict:
    item_title = item.get("title") or ""
    authors = semantic_scholar_author_list(item)
    external_ids = item.get("externalIds") or {}
    doi = clean_doi(external_ids.get("DOI", ""))
    paper_id = item.get("paperId") or ""
    pub_types = item.get("publicationTypes") or []
    return {
        "similarity": title_similarity(title, item_title) if title and item_title else 0.0,
        "matched_title": item_title,
        "author_list": authors,
        "authors": author_display_list(authors, limit=3),
        "year": item.get("year", ""),
        "venue": item.get("venue", ""),
        "type": ", ".join(pub_types) if pub_types else "paper",
        "doi": doi,
        "url": item.get("url", "") or (f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else ""),
        "source": "Semantic Scholar",
    }


def build_arxiv_result(entry: ET.Element, title: str, ns: dict[str, str]) -> dict:
    item_title = " ".join((entry.findtext("atom:title", default="", namespaces=ns) or "").split())
    authors = arxiv_author_list(entry, ns)
    published = entry.findtext("atom:published", default="", namespaces=ns) or ""
    arxiv_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
    doi = ""
    for link in entry.findall("atom:link", ns):
        if link.attrib.get("title") == "doi" or link.attrib.get("rel") == "related":
            href = link.attrib.get("href", "")
            if "doi.org/" in href:
                doi = clean_doi(href)
                break
    return {
        "similarity": title_similarity(title, item_title) if title and item_title else 0.0,
        "matched_title": item_title,
        "author_list": authors,
        "authors": author_display_list(authors, limit=3),
        "year": extract_year(published),
        "venue": "arXiv",
        "type": "preprint",
        "doi": doi,
        "url": arxiv_id,
        "source": "arXiv",
    }


def build_pubmed_result(item: dict, title: str) -> dict:
    item_title = item.get("title") or ""
    item_title = re.sub(r"\.$", "", item_title).strip()
    authors = pubmed_author_list(item)
    article_ids = item.get("articleids") or []
    doi = ""
    for article_id in article_ids:
        if isinstance(article_id, dict) and article_id.get("idtype") == "doi":
            doi = clean_doi(article_id.get("value", ""))
            break
    uid = str(item.get("uid") or "")
    journal = item.get("fulljournalname") or item.get("source") or ""
    return {
        "similarity": title_similarity(title, item_title) if title and item_title else 0.0,
        "matched_title": item_title,
        "author_list": authors,
        "authors": author_display_list(authors, limit=3),
        "year": extract_year(item.get("pubdate", "")),
        "venue": journal,
        "type": "journal-article",
        "doi": doi,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/" if uid else "",
        "source": "PubMed",
    }


def build_springer_result(item: dict, title: str) -> dict:
    item_title = item.get("title") or ""
    authors = springer_author_list(item)
    urls = item.get("url", []) or []
    url = ""
    if isinstance(urls, list) and urls:
        first = urls[0]
        url = first.get("value", "") if isinstance(first, dict) else str(first)
    publication_name = item.get("publicationName") or item.get("publisher") or ""
    return {
        "similarity": title_similarity(title, item_title) if title and item_title else 0.0,
        "matched_title": item_title,
        "author_list": authors,
        "authors": author_display_list(authors, limit=3),
        "year": extract_year(item.get("publicationDate", "")),
        "venue": publication_name,
        "type": item.get("contentType", "springer-record"),
        "doi": clean_doi(item.get("doi", "")),
        "url": url,
        "source": "Springer Nature",
    }


def build_ieee_result(item: dict, title: str) -> dict:
    item_title = item.get("title") or item.get("article_title") or ""
    item_title = strip_latex(re.sub(r"<[^>]+>", " ", item_title))
    authors = ieee_author_list(item)
    return {
        "similarity": title_similarity(title, item_title) if title and item_title else 0.0,
        "matched_title": item_title,
        "author_list": authors,
        "authors": author_display_list(authors, limit=3),
        "year": item.get("publication_year", "") or item.get("publication_date", ""),
        "venue": item.get("publication_title", "") or item.get("publisher", "IEEE"),
        "type": item.get("content_type", "ieee-article"),
        "doi": clean_doi(item.get("doi", "")),
        "url": item.get("html_url", "") or item.get("abstract_url", ""),
        "source": "IEEE Xplore",
    }


def build_core_result(item: dict, title: str) -> dict:
    item_title = item.get("title") or ""
    authors = core_author_list(item)
    doi = clean_doi(item.get("doi", ""))
    url = (
        item.get("downloadUrl")
        or item.get("fullTextLink")
        or item.get("oaiPmhUrl")
        or item.get("publisher")
        or ""
    )
    if not url:
        urls = item.get("sourceFulltextUrls") or item.get("fullTextLinks") or []
        if isinstance(urls, list) and urls:
            url = str(urls[0])
    return {
        "similarity": title_similarity(title, item_title) if title and item_title else 0.0,
        "matched_title": item_title,
        "author_list": authors,
        "authors": author_display_list(authors, limit=3),
        "year": item.get("yearPublished", "") or extract_year(item.get("publishedDate", "")),
        "venue": item.get("publisher", "") or item.get("repository", ""),
        "type": item.get("documentType", "open-access-work"),
        "doi": doi,
        "url": url,
        "source": "CORE",
    }


def build_dblp_result(info: dict, title: str) -> dict:
    item_title = strip_latex(info.get("title", "")).rstrip(".")
    authors = dblp_author_list(info)
    return {
        "similarity": title_similarity(title, item_title) if title and item_title else 0.0,
        "matched_title": item_title,
        "author_list": authors,
        "authors": author_display_list(authors, limit=3),
        "year": info.get("year", ""),
        "venue": info.get("venue", ""),
        "type": info.get("type", "conference/journal"),
        "doi": clean_doi(info.get("doi", "")),
        "url": info.get("url", "") or info.get("ee", ""),
        "source": "DBLP",
    }


# --------------------------- CrossRef ---------------------------

def search_crossref_by_doi(doi: str, title: str, email: str = "") -> dict:
    """优先用 DOI 精确查 CrossRef。"""
    doi = clean_doi(doi)
    if not doi:
        return {"found": False, "reason": "BibTeX 未提供 DOI"}

    headers = {
        "User-Agent": f"BibChecker/1.1 ({'mailto:' + email if email else 'https://example.com'})"
    }

    try:
        r = requests.get(
            f"https://api.crossref.org/works/{quote(doi, safe='')}",
            headers=headers,
            timeout=20,
        )
        r.raise_for_status()
        item = r.json().get("message", {})
    except Exception as e:
        return {"found": False, "reason": f"CrossRef DOI 查询失败: {type(e).__name__}: {e}"}

    if not item:
        return {"found": False, "reason": "CrossRef DOI 查询无返回结果"}

    result = build_crossref_result(item, title, source="CrossRef(DOI)")
    result["doi_exact_query"] = True
    return result


def search_crossref(title: str, author: str = "", year: str = "",
                    threshold: float = 0.85, email: str = "") -> dict:
    """在 CrossRef 中按标题搜索，返回最佳匹配。"""
    headers = {
        "User-Agent": f"BibChecker/1.1 ({'mailto:' + email if email else 'https://example.com'})"
    }
    params = {
        "query.bibliographic": title,
        "rows": 10,
        # 只取核查所需字段，减少 CrossRef 返回体体积。
        "select": "DOI,title,author,issued,container-title,type,URL",
    }
    if author:
        params["query.author"] = first_author_lastname(author)

    try:
        r = requests.get("https://api.crossref.org/works",
                         params=params, headers=headers, timeout=20)
        r.raise_for_status()
        items = r.json().get("message", {}).get("items", [])
    except Exception as e:
        return {"found": False, "reason": f"CrossRef 请求失败: {type(e).__name__}: {e}"}

    if not items:
        return {"found": False, "reason": "CrossRef 无返回结果"}

    best = {"similarity": 0.0, "_score": -999.0}
    for item in items:
        candidate = build_crossref_result(item, title)
        candidate["_score"] = candidate_score(candidate, author, year)
        if candidate["_score"] > best["_score"]:
            best = candidate

    if best["similarity"] >= threshold:
        best["found"] = True
        return best

    best["found"] = False
    best["reason"] = f"CrossRef 最高相似度仅 {best['similarity']:.0%}"
    return best


# --------------------------- OpenAlex ---------------------------

def search_openalex(title: str, author: str = "", year: str = "", threshold: float = 0.85,
                    email: str = "") -> dict:
    """OpenAlex 兜底搜索，对无 DOI、预印本和部分会议论文覆盖更好。"""
    params = {"search": title, "per-page": 5}
    if email:
        params["mailto"] = email

    try:
        r = requests.get("https://api.openalex.org/works",
                         params=params, timeout=20)
        r.raise_for_status()
        items = r.json().get("results", [])
    except Exception as e:
        return {"found": False, "reason": f"OpenAlex 请求失败: {type(e).__name__}: {e}"}

    if not items:
        return {"found": False, "reason": "OpenAlex 无返回结果"}

    best = {"similarity": 0.0, "_score": -999.0}
    for item in items:
        candidate = build_openalex_result(item, title)
        candidate["_score"] = candidate_score(candidate, author, year)
        if candidate["_score"] > best["_score"]:
            best = candidate

    if best["similarity"] >= threshold:
        best["found"] = True
        return best

    best["found"] = False
    best["reason"] = f"OpenAlex 最高相似度仅 {best['similarity']:.0%}"
    return best


# --------------------------- Semantic Scholar ---------------------------

def search_semantic_scholar(title: str, author: str = "", year: str = "",
                            threshold: float = 0.85, email: str = "") -> dict:
    """Semantic Scholar Graph API 兜底搜索，覆盖跨学科论文和预印本。"""
    headers = {"User-Agent": f"RefChecker/1.2 ({email or 'no-email'})"}
    params = {
        "query": title,
        "limit": 5,
        "fields": "title,authors,year,venue,publicationTypes,externalIds,url",
    }
    try:
        r = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params=params,
            headers=headers,
            timeout=20,
        )
        if r.status_code == 429:
            return {"found": False, "reason": "Semantic Scholar 请求受限（429）"}
        r.raise_for_status()
        items = r.json().get("data", [])
    except Exception as e:
        return {"found": False, "reason": f"Semantic Scholar 请求失败: {type(e).__name__}: {e}"}

    if not items:
        return {"found": False, "reason": "Semantic Scholar 无返回结果"}

    best = {"similarity": 0.0, "_score": -999.0}
    for item in items:
        candidate = build_semantic_scholar_result(item, title)
        candidate["_score"] = candidate_score(candidate, author, year)
        if candidate["_score"] > best["_score"]:
            best = candidate

    if best["similarity"] >= threshold:
        best["found"] = True
        return best

    best["found"] = False
    best["reason"] = f"Semantic Scholar 最高相似度仅 {best['similarity']:.0%}"
    return best


# --------------------------- arXiv ---------------------------

def search_arxiv(title: str, author: str = "", year: str = "",
                 threshold: float = 0.85) -> dict:
    """arXiv API 兜底搜索，主要用于预印本。"""
    params = {
        "search_query": f'ti:"{title}"',
        "start": 0,
        "max_results": 5,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    try:
        r = requests.get("https://export.arxiv.org/api/query", params=params, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception as e:
        return {"found": False, "reason": f"arXiv 请求失败: {type(e).__name__}: {e}"}

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns)
    if not entries:
        return {"found": False, "reason": "arXiv 无返回结果"}

    best = {"similarity": 0.0, "_score": -999.0}
    for entry in entries:
        candidate = build_arxiv_result(entry, title, ns)
        candidate["_score"] = candidate_score(candidate, author, year)
        if candidate["_score"] > best["_score"]:
            best = candidate

    if best["similarity"] >= threshold:
        best["found"] = True
        return best

    best["found"] = False
    best["reason"] = f"arXiv 最高相似度仅 {best['similarity']:.0%}"
    return best


# --------------------------- PubMed ---------------------------

def search_pubmed(title: str, author: str = "", year: str = "", threshold: float = 0.85,
                  email: str = "") -> dict:
    """PubMed / NCBI E-utilities 兜底搜索，主要用于生物医学论文。"""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    common = {"tool": "RefChecker", "retmode": "json"}
    if email:
        common["email"] = email
    try:
        search_params = {
            **common,
            "db": "pubmed",
            "term": f'"{title}"[Title]',
            "retmax": 5,
        }
        r = requests.get(f"{base}/esearch.fcgi", params=search_params, timeout=20)
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            search_params["term"] = f"{title}[Title]"
            r = requests.get(f"{base}/esearch.fcgi", params=search_params, timeout=20)
            r.raise_for_status()
            ids = r.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        return {"found": False, "reason": f"PubMed 搜索失败: {type(e).__name__}: {e}"}

    if not ids:
        return {"found": False, "reason": "PubMed 无返回结果"}

    try:
        summary_params = {
            **common,
            "db": "pubmed",
            "id": ",".join(ids[:5]),
        }
        r = requests.get(f"{base}/esummary.fcgi", params=summary_params, timeout=20)
        r.raise_for_status()
        payload = r.json().get("result", {})
    except Exception as e:
        return {"found": False, "reason": f"PubMed 摘要请求失败: {type(e).__name__}: {e}"}

    best = {"similarity": 0.0, "_score": -999.0}
    for uid in payload.get("uids", ids[:5]):
        item = payload.get(str(uid), {})
        if not item:
            continue
        item["uid"] = str(uid)
        candidate = build_pubmed_result(item, title)
        candidate["_score"] = candidate_score(candidate, author, year)
        if candidate["_score"] > best["_score"]:
            best = candidate

    if best.get("_score", -999.0) == -999.0:
        return {"found": False, "reason": "PubMed 摘要为空"}

    if best["similarity"] >= threshold:
        best["found"] = True
        return best

    best["found"] = False
    best["reason"] = f"PubMed 最高相似度仅 {best['similarity']:.0%}"
    return best


# --------------------------- API-key enhanced sources ---------------------------

def search_springer(title: str, author: str = "", year: str = "", threshold: float = 0.85,
                    api_key: str = "") -> dict:
    """Springer Nature Metadata API，需要用户提供 API Key。"""
    if not api_key:
        return {"found": False, "reason": "Springer Nature 未配置 API Key"}
    params = {
        "q": f'title:"{title}"',
        "p": 5,
        "api_key": api_key,
    }
    try:
        r = requests.get("https://api.springernature.com/meta/v2/json", params=params, timeout=20)
        r.raise_for_status()
        records = r.json().get("records", [])
    except Exception as e:
        return {"found": False, "reason": f"Springer Nature 请求失败: {type(e).__name__}: {e}"}

    if not records:
        return {"found": False, "reason": "Springer Nature 无返回结果"}

    best = {"similarity": 0.0, "_score": -999.0}
    for item in records:
        candidate = build_springer_result(item, title)
        candidate["_score"] = candidate_score(candidate, author, year)
        if candidate["_score"] > best["_score"]:
            best = candidate

    if best["similarity"] >= threshold:
        best["found"] = True
        return best

    best["found"] = False
    best["reason"] = f"Springer Nature 最高相似度仅 {best['similarity']:.0%}"
    return best


def search_ieee(title: str, author: str = "", year: str = "", threshold: float = 0.85,
                api_key: str = "") -> dict:
    """IEEE Xplore API，需要用户提供 API Key。"""
    if not api_key:
        return {"found": False, "reason": "IEEE Xplore 未配置 API Key"}
    params = {
        "apikey": api_key,
        "format": "json",
        "max_records": 5,
        "article_title": title,
    }
    try:
        r = requests.get(
            "https://ieeexploreapi.ieee.org/api/v1/search/articles",
            params=params,
            timeout=20,
        )
        r.raise_for_status()
        articles = r.json().get("articles", [])
    except Exception as e:
        return {"found": False, "reason": f"IEEE Xplore 请求失败: {type(e).__name__}: {e}"}

    if not articles:
        return {"found": False, "reason": "IEEE Xplore 无返回结果"}

    best = {"similarity": 0.0, "_score": -999.0}
    for item in articles:
        candidate = build_ieee_result(item, title)
        candidate["_score"] = candidate_score(candidate, author, year)
        if candidate["_score"] > best["_score"]:
            best = candidate

    if best["similarity"] >= threshold:
        best["found"] = True
        return best

    best["found"] = False
    best["reason"] = f"IEEE Xplore 最高相似度仅 {best['similarity']:.0%}"
    return best


def search_core(title: str, author: str = "", year: str = "", threshold: float = 0.85,
                api_key: str = "") -> dict:
    """CORE API，需要用户提供 API Key。"""
    if not api_key:
        return {"found": False, "reason": "CORE 未配置 API Key"}
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"q": f'title:"{title}"', "limit": 5}
    try:
        r = requests.get("https://api.core.ac.uk/v3/search/works", params=params,
                         headers=headers, timeout=20)
        r.raise_for_status()
        payload = r.json()
        records = payload.get("results", []) if isinstance(payload, dict) else []
    except Exception as e:
        return {"found": False, "reason": f"CORE 请求失败: {type(e).__name__}: {e}"}

    if not records:
        return {"found": False, "reason": "CORE 无返回结果"}

    best = {"similarity": 0.0, "_score": -999.0}
    for item in records:
        candidate = build_core_result(item, title)
        candidate["_score"] = candidate_score(candidate, author, year)
        if candidate["_score"] > best["_score"]:
            best = candidate

    if best["similarity"] >= threshold:
        best["found"] = True
        return best

    best["found"] = False
    best["reason"] = f"CORE 最高相似度仅 {best['similarity']:.0%}"
    return best


# --------------------------- DBLP ---------------------------

def search_dblp(title: str, author: str = "", year: str = "", threshold: float = 0.85) -> dict:
    """DBLP 兜底搜索，主要用于计算机科学论文。"""
    params = {"q": title, "format": "json", "h": 5}

    try:
        r = requests.get("https://dblp.org/search/publ/api",
                         params=params, timeout=20)
        r.raise_for_status()
        hits = (
            r.json()
            .get("result", {})
            .get("hits", {})
            .get("hit", [])
        )
    except Exception as e:
        return {"found": False, "reason": f"DBLP 请求失败: {type(e).__name__}: {e}"}

    if isinstance(hits, dict):
        hits = [hits]

    if not hits:
        return {"found": False, "reason": "DBLP 无返回结果"}

    best = {"similarity": 0.0, "_score": -999.0}
    for hit in hits:
        info = hit.get("info", {}) or {}
        candidate = build_dblp_result(info, title)
        candidate["_score"] = candidate_score(candidate, author, year)
        if candidate["_score"] > best["_score"]:
            best = candidate

    if best["similarity"] >= threshold:
        best["found"] = True
        return best

    best["found"] = False
    best["reason"] = f"DBLP 最高相似度仅 {best['similarity']:.0%}"
    return best
