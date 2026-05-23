#!/usr/bin/env python3
"""
检查 BibTeX 文献的真实性与元数据一致性。

核查维度:
    1. DOI：如果 BibTeX 中有 DOI，优先尝试 CrossRef DOI 精确查询
    2. 标题：基于 CrossRef / OpenAlex / DBLP 返回标题计算相似度
    3. 年份：比较 BibTeX 年份与数据库年份
    4. 作者：比较 BibTeX 作者列表与数据库作者列表，发现省略、顺序异常或额外作者

用法:
    pip install bibtexparser requests
    python check_bib_crossref.py refs.bib
    python check_bib_crossref.py refs.bib --output report.md --csv result.csv
    python check_bib_crossref.py refs.bib --email you@example.com
    python check_bib_crossref.py refs.bib --no-openalex --no-dblp

说明:
    - CrossRef 适合 DOI 元数据完善的期刊/会议论文。
    - OpenAlex 覆盖范围更广，可补充部分无 DOI、预印本或会议论文。
    - DBLP 对计算机科学文献尤其有用，因此默认作为最后兜底源。
    - 作者核查是“元数据一致性检查”，不能 100% 证明作者虚构；数据库本身也可能缺失或有误。
"""

import argparse
import contextlib
import csv
import json
import os
import re
import sys
import time
import traceback
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import quote

try:
    # 某些环境中 bibtexparser 与 pyparsing 版本不完全匹配：
    # bibtexparser 期望 pyparsing.DelimitedList，而旧版 pyparsing 只提供 delimitedList。
    import pyparsing as _pyparsing
    if not hasattr(_pyparsing, "DelimitedList") and hasattr(_pyparsing, "delimitedList"):
        _pyparsing.DelimitedList = _pyparsing.delimitedList
except Exception:
    pass

try:
    import bibtexparser
except ImportError:
    sys.exit("请先安装: pip install bibtexparser")

try:
    import requests
except ImportError:
    sys.exit("请先安装: pip install requests")

for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# --------------------------- 文本规范化 ---------------------------

NAME_PARTICLES = {
    "da", "de", "del", "della", "der", "di", "dos", "du",
    "la", "le", "van", "von", "den", "ten", "ter",
}

NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def strip_latex(text: str) -> str:
    """粗略去除常见 BibTeX/LaTeX 标记，保留可比较文本。"""
    if not text:
        return ""
    t = str(text).replace("\n", " ").replace("\r", " ")
    # 将 \emph{abc} 之类替换为 abc；对嵌套命令不做复杂解析
    t = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", t)
    # 处理常见 LaTeX 重音写法，如 {\"o} / \'e
    t = re.sub(r"\\['`\"^~=.uvHtcdbk]\s*\{?([A-Za-z])\}?", r"\1", t)
    t = re.sub(r"\\[a-zA-Z]+", " ", t)
    t = t.replace("{", "").replace("}", "").replace("~", " ")
    return " ".join(t.split())


def normalize_ascii(text: str) -> str:
    """转小写、去重音、去标点，得到便于相似度比较的文本。"""
    t = strip_latex(text)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s-]", " ", t)
    t = t.replace("-", " ")
    return " ".join(t.split())


def normalize_title(title: str) -> str:
    return normalize_ascii(title)


def title_similarity(t1: str, t2: str) -> float:
    return SequenceMatcher(None, normalize_title(t1), normalize_title(t2)).ratio()


def extract_year(value) -> str:
    """从 BibTeX 年份字段或数据库年份字段中提取 4 位年份。"""
    if value is None:
        return ""
    m = re.search(r"(18|19|20|21)\d{2}", str(value))
    return m.group(0) if m else ""


def clean_doi(doi: str) -> str:
    """规范化 DOI，去除 URL 前缀、doi: 前缀和多余标点。"""
    if not doi:
        return ""
    d = strip_latex(str(doi)).strip()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d, flags=re.I)
    d = re.sub(r"^doi:\s*", "", d, flags=re.I)
    d = d.strip().strip(".;,")
    return d.lower()


def truncate(text: str, n: int = 80) -> str:
    text = text or ""
    return text[:n] + ("..." if len(text) > n else "")


# --------------------------- 作者解析与比较 ---------------------------

def parse_author_name(raw: str = "", given: str = "", family: str = "") -> dict:
    """将作者名解析成 given / family / initials / normalized forms。"""
    raw = strip_latex(raw or "")
    given = strip_latex(given or "")
    family = strip_latex(family or "")

    if not (given or family):
        if "," in raw:
            parts = [p.strip() for p in raw.split(",")]
            family = parts[0]
            given = " ".join(parts[1:]).strip()
        else:
            tokens = raw.split()
            while tokens and normalize_ascii(tokens[-1]) in NAME_SUFFIXES:
                tokens.pop()
            if len(tokens) == 1:
                family = tokens[0] if tokens else ""
                given = ""
            elif len(tokens) > 1:
                # 粗略处理 van der Waals / de Souza 之类姓氏粒子
                family_tokens = [tokens[-1]]
                idx = len(tokens) - 2
                while idx >= 0 and normalize_ascii(tokens[idx]) in NAME_PARTICLES:
                    family_tokens.insert(0, tokens[idx])
                    idx -= 1
                family = " ".join(family_tokens)
                given = " ".join(tokens[: idx + 1])

    family_tokens = family.split()
    while family_tokens and normalize_ascii(family_tokens[-1]) in NAME_SUFFIXES:
        family_tokens.pop()
    family = " ".join(family_tokens)

    given_norm = normalize_ascii(given)
    family_norm = normalize_ascii(family)
    full = " ".join(part for part in [given, family] if part).strip() or raw
    full_norm = normalize_ascii(full)
    initials = "".join(token[0] for token in given_norm.split() if token)

    return {
        "raw": raw or full,
        "given": given,
        "family": family,
        "given_norm": given_norm,
        "family_norm": family_norm,
        "full_norm": full_norm,
        "initials": initials,
        "display": full,
    }


def split_bibtex_author_field(author_field: str) -> tuple[list[dict], bool]:
    """
    解析 BibTeX author 字段。

    返回:
        authors: 作者列表
        truncated: 是否使用 others / et al. 表示省略
    """
    if not author_field:
        return [], False

    text = str(author_field).replace("\n", " ").replace("\r", " ")
    parts = [p.strip() for p in re.split(r"\s+and\s+", text) if p.strip()]

    authors = []
    truncated = False
    for part in parts:
        clean = strip_latex(part).strip()
        if re.fullmatch(r"(?i)(others|et\.?\s*al\.?)", clean):
            truncated = True
            continue
        authors.append(parse_author_name(clean))
    return authors, truncated


def first_author_lastname(author_field: str) -> str:
    """从 BibTeX author 字段抽出第一作者的姓，用于辅助检索。"""
    authors, _ = split_bibtex_author_field(author_field)
    return authors[0]["family"] if authors else ""


def author_display_list(authors: list[dict], limit: int | None = None) -> str:
    selected = authors if limit is None else authors[:limit]
    names = [a.get("display") or a.get("raw") or "" for a in selected]
    names = [n for n in names if n]
    text = "; ".join(names)
    if limit is not None and len(authors) > limit:
        text += f"; ... (+{len(authors) - limit})"
    return text


def family_matches(a: dict, b: dict) -> bool:
    af = a.get("family_norm", "")
    bf = b.get("family_norm", "")
    if not af or not bf:
        return False
    if af == bf:
        return True
    af_tokens = af.split()
    bf_tokens = bf.split()
    # 数据源有时只保留复合姓氏的最后一段，例如 "Mohammadzadeh Asl" vs "Asl"。
    if af_tokens and bf_tokens and af_tokens[-1] == bf_tokens[-1]:
        if len(af_tokens) > 1 or len(bf_tokens) > 1:
            return True
    if len(af) >= 5 and len(bf) >= 5 and (af in bf or bf in af):
        return True
    return SequenceMatcher(None, af, bf).ratio() >= 0.88


def initials_compatible(a: dict, b: dict) -> bool:
    ai = a.get("initials", "")
    bi = b.get("initials", "")
    # 数据库或 BibTeX 只有姓氏时，不因缺少名缩写直接判错
    if not ai or not bi:
        return True
    return ai.startswith(bi) or bi.startswith(ai)


def author_matches(a: dict, b: dict) -> bool:
    return family_matches(a, b) and initials_compatible(a, b)


def match_indices(left: list[dict], right: list[dict]) -> set[int]:
    matched_right = set()
    for a in left:
        for j, b in enumerate(right):
            if j in matched_right:
                continue
            if author_matches(a, b):
                matched_right.add(j)
                break
    return matched_right


def compare_author_lists(bib_author_field: str, db_authors: list[dict]) -> dict:
    """比较 BibTeX 作者列表与数据库作者列表。"""
    bib_authors, bib_truncated = split_bibtex_author_field(bib_author_field)

    if not bib_authors:
        return {
            "status": "unknown",
            "reason": "BibTeX 缺少 author 字段，无法核查作者",
            "bib_author_count": 0,
            "matched_author_count": len(db_authors),
            "bib_authors": "",
            "matched_authors": author_display_list(db_authors),
            "missing_authors": "",
            "extra_authors": "",
            "order_mismatch": False,
            "first_author_match": "",
        }

    if not db_authors:
        return {
            "status": "unknown",
            "reason": "数据库返回记录缺少作者元数据，无法核查作者",
            "bib_author_count": len(bib_authors),
            "matched_author_count": 0,
            "bib_authors": author_display_list(bib_authors),
            "matched_authors": "",
            "missing_authors": "",
            "extra_authors": "",
            "order_mismatch": False,
            "first_author_match": "",
        }

    first_ok = author_matches(bib_authors[0], db_authors[0])
    ordered_prefix_ok = all(
        author_matches(bib_authors[i], db_authors[i])
        for i in range(min(len(bib_authors), len(db_authors)))
    )
    exact_order_ok = (
        len(bib_authors) == len(db_authors)
        and all(author_matches(bib_authors[i], db_authors[i]) for i in range(len(bib_authors)))
    )

    matched_db_indices = match_indices(bib_authors, db_authors)
    matched_bib_indices = match_indices(db_authors, bib_authors)

    missing_authors = [
        db_authors[i] for i in range(len(db_authors)) if i not in matched_db_indices
    ]
    extra_authors = [
        bib_authors[i] for i in range(len(bib_authors)) if i not in matched_bib_indices
    ]

    same_author_set = not missing_authors and not extra_authors
    order_mismatch = same_author_set and not exact_order_ok

    if exact_order_ok:
        status = "exact"
        reason = "作者数量、顺序与姓名基本一致"
    elif bib_truncated and ordered_prefix_ok and len(bib_authors) <= len(db_authors):
        status = "partial"
        reason = (
            f"BibTeX 使用 others/et al. 省略作者；前 {len(bib_authors)} 位作者与数据库一致，"
            f"数据库共 {len(db_authors)} 位作者"
        )
        # 这种情况下缺少的作者是预期省略，不视为可疑
        missing_authors = []
    elif not first_ok:
        status = "mismatch"
        reason = (
            "第一作者不一致："
            f"BibTeX 为 {bib_authors[0].get('display', '')}，"
            f"数据库为 {db_authors[0].get('display', '')}"
        )
    elif order_mismatch:
        status = "mismatch"
        reason = "作者集合基本相同，但作者顺序与数据库不一致"
    elif missing_authors or extra_authors:
        status = "mismatch"
        bits = []
        if len(bib_authors) != len(db_authors):
            bits.append(f"作者数量不一致：BibTeX {len(bib_authors)} 位，数据库 {len(db_authors)} 位")
        if missing_authors:
            bits.append("BibTeX 可能省略: " + author_display_list(missing_authors, limit=5))
        if extra_authors:
            bits.append("BibTeX 可能额外/可疑: " + author_display_list(extra_authors, limit=5))
        reason = "；".join(bits)
    else:
        status = "partial"
        reason = "作者姓名存在格式差异，建议人工复核"

    return {
        "status": status,
        "reason": reason,
        "bib_author_count": len(bib_authors),
        "matched_author_count": len(db_authors),
        "bib_authors": author_display_list(bib_authors),
        "matched_authors": author_display_list(db_authors),
        "missing_authors": author_display_list(missing_authors),
        "extra_authors": author_display_list(extra_authors),
        "order_mismatch": order_mismatch,
        "first_author_match": "Yes" if first_ok else "No",
    }


def candidate_score(candidate: dict, bib_author: str = "", bib_year: str = "") -> float:
    """
    给候选结果打分。

    标题相似度仍是主指标；当多个候选标题完全相同时，优先选择年份和作者更一致的记录。
    这能减少 CrossRef 中同题转载、预印本、书籍条目把原始论文“挤掉”的情况。
    """
    score = candidate.get("similarity", 0.0)

    by = extract_year(bib_year)
    my = extract_year(candidate.get("year", ""))
    if by and my:
        diff = abs(int(by) - int(my))
        if diff == 0:
            score += 0.08
        elif diff == 1:
            score -= 0.015
        elif diff <= 3:
            score -= 0.04
        else:
            score -= 0.08

    if bib_author and candidate.get("author_list"):
        author_check = compare_author_lists(bib_author, candidate.get("author_list", []))
        if author_check["status"] == "exact":
            score += 0.05
        elif author_check["status"] == "partial":
            score += 0.02
        elif author_check["status"] == "mismatch":
            score -= 0.04
            if author_check.get("first_author_match") == "No":
                score -= 0.06

    if candidate.get("doi"):
        score += 0.005

    return score


# --------------------------- 年份 / DOI 比较 ---------------------------

def compare_year(bib_year: str, matched_year: str) -> dict:
    by = extract_year(bib_year)
    my = extract_year(matched_year)
    if not by:
        return {"status": "unknown", "reason": "BibTeX 缺少年份", "bib_year": "", "matched_year": my}
    if not my:
        return {"status": "unknown", "reason": "数据库缺少年份", "bib_year": by, "matched_year": ""}
    if by == my:
        return {"status": "exact", "reason": "年份一致", "bib_year": by, "matched_year": my}
    return {
        "status": "mismatch",
        "reason": f"年份不一致：BibTeX {by}，数据库 {my}",
        "bib_year": by,
        "matched_year": my,
    }


def compare_doi(bib_doi: str, matched_doi: str) -> dict:
    bd = clean_doi(bib_doi)
    md = clean_doi(matched_doi)
    if not bd and not md:
        return {"status": "unknown", "reason": "BibTeX 和数据库均未提供 DOI", "bib_doi": "", "matched_doi": ""}
    if not bd and md:
        return {"status": "missing_in_bib", "reason": f"BibTeX 缺少 DOI，数据库 DOI 为 {md}", "bib_doi": "", "matched_doi": md}
    if bd and not md:
        return {"status": "unknown", "reason": "BibTeX 有 DOI，但数据库结果未提供 DOI", "bib_doi": bd, "matched_doi": ""}
    if bd == md:
        return {"status": "exact", "reason": "DOI 一致", "bib_doi": bd, "matched_doi": md}
    return {
        "status": "mismatch",
        "reason": f"DOI 不一致：BibTeX {bd}，数据库 {md}",
        "bib_doi": bd,
        "matched_doi": md,
    }


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


# --------------------------- URL 资源验证 ---------------------------

def detect_url_platform(url: str) -> str:
    """根据 URL 域名识别平台类型。"""
    if not url:
        return "none"
    u = url.lower()
    if "huggingface.co" in u:
        return "huggingface"
    if "github.com" in u:
        return "github"
    return "general"


def _parse_author_from_org(org_name: str) -> list[dict]:
    """将组织名称（如 Meta / NVIDIA Corporation）转为 author_list 兼容格式。"""
    org = strip_latex(org_name).strip("{}").strip()
    if not org:
        return []
    return [parse_author_name(org)]


def _hf_api_headers() -> dict:
    return {"User-Agent": "RefChecker/1.2"}


def _extract_hf_path(url: str) -> tuple[str, str] | None:
    """从 HuggingFace URL 中提取 (org, repo_name)。

    支持:
        https://huggingface.co/{org}/{name}
        https://huggingface.co/{org}/{name}/tree/main
        https://huggingface.co/datasets/{org}/{name}
    """
    m = re.search(r"huggingface\.co/(?:datasets/)?([^/]+)/([^/?#]+)", url)
    if m:
        return m.group(1), m.group(2)
    return None


def verify_huggingface(url: str, title: str, author: str, year: str) -> dict:
    """通过 HuggingFace Hub API 验证模型/数据集页面是否存在并比对元数据。"""
    path_parts = _extract_hf_path(url)
    if not path_parts:
        return {"found": False, "reason": f"无法解析 HuggingFace URL: {url}"}

    org, repo_name = path_parts
    is_dataset = "/datasets/" in url.lower()
    repo_type = "datasets" if is_dataset else "models"
    api_url = f"https://huggingface.co/api/{repo_type}/{org}/{repo_name}"

    try:
        session = requests.Session()
        r = session.get(api_url, headers=_hf_api_headers(), timeout=20)
        if r.status_code == 404:
            return {"found": False, "reason": f"HuggingFace {repo_type[:-1]} 不存在: {org}/{repo_name}"}
        if r.status_code == 401:
            time.sleep(0.5)
            r = session.get(api_url, headers=_hf_api_headers(), timeout=20)
        if r.status_code >= 400:
            # API 不可用，回退到通用 URL 检查
            fallback = verify_general_url(url, title, author, year)
            if fallback.get("found"):
                fallback["source"] = "URL(HuggingFace/Web)"
                fallback["venue"] = "HuggingFace (page accessible)"
            return fallback
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        # 请求异常时回退到通用 URL 检查
        fallback = verify_general_url(url, title, author, year)
        if fallback.get("found"):
            fallback["source"] = "URL(HuggingFace/Web)"
            fallback["venue"] = "HuggingFace (page accessible)"
        return fallback

    if not data:
        return {"found": False, "reason": "HuggingFace API 返回空数据"}

    model_id = data.get("modelId") or data.get("id") or f"{org}/{repo_name}"
    hf_author = data.get("author") or data.get("_id", "")
    if isinstance(hf_author, dict):
        hf_author = hf_author.get("name") or hf_author.get("user") or ""
    last_modified = data.get("lastModified") or ""
    hf_year = extract_year(last_modified[:4] if last_modified else "")
    tags = data.get("tags") or []
    tag_names = [t if isinstance(t, str) else t.get("label", "") for t in tags]

    # 标题相似度：BibTeX title vs HF modelId
    sim = title_similarity(title, model_id)

    result = {
        "found": True,
        "similarity": sim,
        "matched_title": model_id,
        "author_list": _parse_author_from_org(hf_author),
        "authors": hf_author,
        "year": hf_year or data.get("lastModified", "")[:4],
        "venue": "HuggingFace",
        "type": "dataset" if is_dataset else "model",
        "doi": "",
        "url": url,
        "source": "URL(HuggingFace)",
        "tags": ", ".join(tag_names[:8]) if tag_names else "",
    }
    return result


def _extract_github_path(url: str) -> tuple[str, str] | None:
    """从 GitHub URL 中提取 (owner, repo)。

    支持:
        https://github.com/{owner}/{repo}
        https://github.com/{owner}/{repo}/tree/...
        https://github.com/{owner}/{repo}/blob/...
    """
    m = re.search(r"github\.com/([^/]+)/([^/?#]+)", url)
    if m:
        return m.group(1), m.group(2)
    return None


def verify_github(url: str, title: str, author: str, year: str) -> dict:
    """通过 GitHub API 验证仓库是否存在并比对元数据。"""
    path_parts = _extract_github_path(url)
    if not path_parts:
        return {"found": False, "reason": f"无法解析 GitHub URL: {url}"}

    owner, repo = path_parts
    api_url = f"https://api.github.com/repos/{owner}/{repo}"

    try:
        r = requests.get(api_url, headers={"User-Agent": "RefChecker/1.2"}, timeout=20)
        if r.status_code == 404:
            return {"found": False, "reason": f"GitHub 仓库不存在: {owner}/{repo}"}
        if r.status_code == 403 and "rate limit" in r.text.lower():
            # GitHub API 限流，回退到通用 URL 检查
            return verify_general_url(url, title, author, year)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        # API 不可用时回退到通用 URL 检查
        fallback = verify_general_url(url, title, author, year)
        if fallback.get("found"):
            fallback["source"] = "URL(GitHub/Web)"
            fallback["venue"] = "GitHub (repo page accessible)"
        return fallback

    full_name = data.get("full_name", f"{owner}/{repo}")
    gh_owner = (data.get("owner") or {}).get("login", "") if isinstance(data.get("owner"), dict) else ""
    created = data.get("created_at", "")
    gh_year = extract_year(created)
    description = data.get("description", "") or ""
    stars = data.get("stargazers_count", 0)

    # 标题相似度：BibTeX title vs GitHub full_name / description
    sim_name = title_similarity(title, full_name)
    sim_desc = title_similarity(title, description) if description else 0.0
    sim = max(sim_name, sim_desc)

    result = {
        "found": True,
        "similarity": sim,
        "matched_title": full_name,
        "author_list": _parse_author_from_org(gh_owner) if gh_owner else [],
        "authors": gh_owner,
        "year": gh_year,
        "venue": f"GitHub (stars: {stars})",
        "type": "repository",
        "doi": "",
        "url": url,
        "source": "URL(GitHub)",
    }
    return result


def verify_general_url(url: str, title: str = "", author: str = "",
                       year: str = "") -> dict:
    """通用 URL 可访问性检查（先 requests，失败时用 urllib 兜底）。"""
    headers = {"User-Agent": "RefChecker/1.2"}
    status = None

    # 先尝试 requests
    try:
        r = requests.head(url, headers=headers, timeout=15, allow_redirects=True)
        if r.status_code >= 400:
            r = requests.get(url, headers=headers, timeout=15, allow_redirects=True,
                             stream=True)
            r.close()
        status = r.status_code
    except requests.RequestException:
        status = None

    # requests 失败或返回 4xx/5xx 时用 urllib 兜底
    if status is None or status >= 400:
        try:
            import urllib.request as urllib_request
            req = urllib_request.Request(url, headers=headers)
            req.method = "HEAD"
            resp = urllib_request.urlopen(req, timeout=15)
            status = resp.status
        except Exception:
            pass

    if status is None:
        return {"found": False, "reason": "URL 不可访问"}

    if status < 200 or status >= 400:
        return {"found": False, "reason": f"URL 返回 HTTP {status}"}

    result = {
        "found": True,
        "similarity": 0.0,
        "matched_title": url,
        "author_list": [],
        "authors": "",
        "year": "",
        "venue": "Web",
        "type": "web-resource",
        "doi": "",
        "url": url,
        "source": "URL(Web)",
    }
    return result


def verify_url_resource(url: str, title: str = "", author: str = "",
                        year: str = "", email: str = "") -> dict:
    """URL 资源验证调度器：按平台分发到对应验证函数。"""
    platform = detect_url_platform(url)
    if platform == "huggingface":
        return verify_huggingface(url, title, author, year)
    elif platform == "github":
        return verify_github(url, title, author, year)
    else:
        return verify_general_url(url, title, author, year)


# --------------------------- 主验证流程 ---------------------------

def enrich_result(result: dict, *, bib_author: str, bib_year: str, bib_doi: str) -> dict:
    """补充作者、年份、DOI 核查结果。"""
    author_check = compare_author_lists(bib_author, result.get("author_list", []) or [])
    year_check = compare_year(bib_year, result.get("year", ""))
    doi_check = compare_doi(bib_doi, result.get("doi", ""))

    result.update({
        "author_check": author_check["status"],
        "author_reason": author_check["reason"],
        "bib_author_count": author_check["bib_author_count"],
        "matched_author_count": author_check["matched_author_count"],
        "bib_authors": author_check["bib_authors"],
        "matched_authors": author_check["matched_authors"],
        "missing_authors": author_check["missing_authors"],
        "extra_authors": author_check["extra_authors"],
        "author_order_mismatch": author_check["order_mismatch"],
        "first_author_match": author_check["first_author_match"],
        "year_check": year_check["status"],
        "year_reason": year_check["reason"],
        "bib_year": year_check["bib_year"],
        "matched_year": year_check["matched_year"],
        "doi_check": doi_check["status"],
        "doi_reason": doi_check["reason"],
        "bib_doi": doi_check["bib_doi"],
        "matched_doi": doi_check["matched_doi"],
    })

    review_reasons = []
    if result.get("status") == "not_found" or not result.get("found"):
        review_reasons.append("未找到可靠标题匹配")
    # URL(Web) 来源的 similarity 是 URL vs 标题，0% 是正常的，不标记
    if result.get("similarity", 0) < 1.0:
        source = result.get("source", "")
        if source != "URL(Web)":
            review_reasons.append(f"标题相似度 {result.get('similarity', 0):.0%}")
    # "unknown" = 数据源缺少元数据（非错误），仅 mismatch/partial 需复核
    if result["author_check"] in {"mismatch", "partial"}:
        review_reasons.append(f"作者核查: {result['author_reason']}")
    if result["year_check"] == "mismatch":
        review_reasons.append(result["year_reason"])
    if result["doi_check"] == "mismatch":
        review_reasons.append(result["doi_reason"])

    result["needs_review"] = "Yes" if review_reasons else "No"
    result["review_reasons"] = "；".join(review_reasons)
    return result


def verify_entry(title: str, author: str, year: str, doi: str, threshold: float,
                 email: str, use_openalex: bool, use_dblp: bool,
                 url: str = "", use_url_verify: bool = True) -> dict:
    """先查 DOI，再查 CrossRef 标题，然后用 OpenAlex / DBLP / URL 兜底。"""
    candidates = []

    doi_result = search_crossref_by_doi(doi, title, email) if doi else None
    if doi_result and doi_result.get("matched_title"):
        candidates.append(doi_result)
        # DOI 是精确标识符，即使标题提取有噪声也应接受较低的相似度
        doi_ok = doi_result.get("similarity", 0) >= threshold * 0.6
        if doi_ok or doi_result.get("doi_exact_query"):
            doi_result["found"] = True
            return enrich_result(doi_result, bib_author=author, bib_year=year, bib_doi=doi)

    result = search_crossref(title, author, year, threshold, email)
    if result.get("matched_title"):
        candidates.append(result)
    if result.get("found"):
        return enrich_result(result, bib_author=author, bib_year=year, bib_doi=doi)

    if use_openalex:
        oa = search_openalex(title, author, year, threshold, email)
        if oa.get("matched_title"):
            candidates.append(oa)
        if oa.get("found"):
            return enrich_result(oa, bib_author=author, bib_year=year, bib_doi=doi)

    if use_dblp:
        dblp = search_dblp(title, author, year, threshold)
        if dblp.get("matched_title"):
            candidates.append(dblp)
        if dblp.get("found"):
            return enrich_result(dblp, bib_author=author, bib_year=year, bib_doi=doi)

    if use_url_verify and url:
        web = verify_url_resource(url, title, author, year, email)
        if web.get("matched_title"):
            candidates.append(web)
        if web.get("found"):
            return enrich_result(web, bib_author=author, bib_year=year, bib_doi=doi)

    if candidates:
        best = max(candidates, key=lambda x: x.get("similarity", 0))
    else:
        best = result

    best["found"] = False
    best["reason"] = (
        f"CrossRef"
        f"{' / OpenAlex' if use_openalex else ''}"
        f"{' / DBLP' if use_dblp else ''}"
        f" 均未匹配 (最高相似度 {best.get('similarity', 0):.0%})"
    )
    best["status"] = "not_found"
    return enrich_result(best, bib_author=author, bib_year=year, bib_doi=doi)


def status_icon(status: str) -> str:
    return {
        "exact": "✅",
        "partial": "🟡",
        "mismatch": "❌",
        "unknown": "⚪",
        "missing_in_bib": "🟡",
    }.get(status, "⚪")


def safe_table_text(text: str, max_len: int = 80) -> str:
    text = (text or "").replace("|", "\\|").replace("\n", " ")
    return truncate(text, max_len)


def build_summary(results: list[dict]) -> dict:
    """Build count buckets used by console output, reports, and the desktop UI."""
    return {
        "found": [r for r in results if r["status"] == "found"],
        "missing": [r for r in results if r["status"] == "not_found"],
        "skipped": [r for r in results if r["status"] == "skipped"],
        "review": [r for r in results if r.get("needs_review") == "Yes"],
        "author_mismatch": [r for r in results if r.get("author_check") == "mismatch"],
        "year_mismatch": [r for r in results if r.get("year_check") == "mismatch"],
        "doi_mismatch": [r for r in results if r.get("doi_check") == "mismatch"],
    }


def summary_counts(summary: dict, total: int) -> dict:
    return {
        "total": total,
        "found": len(summary["found"]),
        "not_found": len(summary["missing"]),
        "needs_review": len(summary["review"]),
        "skipped": len(summary["skipped"]),
        "author_mismatch": len(summary["author_mismatch"]),
        "year_mismatch": len(summary["year_mismatch"]),
        "doi_mismatch": len(summary["doi_mismatch"]),
    }


def write_markdown_report(path: str, *, bibfile: str, sources: str, threshold: float,
                          total: int, results: list[dict], summary: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    found = summary["found"]
    missing = summary["missing"]
    skipped = summary["skipped"]
    review = summary["review"]
    author_mismatch = summary["author_mismatch"]
    year_mismatch = summary["year_mismatch"]
    doi_mismatch = summary["doi_mismatch"]

    with open(path, "w", encoding="utf-8") as f:
        f.write("# BibTeX 文献真实性与元数据一致性验证报告\n\n")
        f.write(f"- 文件: `{bibfile}`\n")
        f.write(f"- 数据源: **{sources}**\n")
        f.write(f"- 标题相似度阈值: **{threshold:.0%}**\n")
        f.write(
            f"- 总数: **{total}** | ✅ 找到: **{len(found)}** | ❌ 未找到: **{len(missing)}** "
            f"| ⚠️ 需复核: **{len(review)}** | 跳过: **{len(skipped)}**\n"
        )
        f.write(
            f"- 元数据问题: 作者不一致 **{len(author_mismatch)}** | "
            f"年份不一致 **{len(year_mismatch)}** | DOI 不一致 **{len(doi_mismatch)}**\n\n"
        )
        f.write("> 说明：作者核查表示 BibTeX 作者列表与数据库元数据是否一致。数据库本身可能缺失或有误，因此“作者不一致”表示需要人工复核，不等同于直接判定作者虚构。\n\n")

        if missing:
            f.write("## ❌ 未找到（重点核查）\n\n")
            for r in missing:
                f.write(f"### `{r['key']}`\n")
                f.write(f"- 原标题: {r['title']}\n")
                f.write(f"- 原因: {r.get('reason', '')}\n")
                if r.get("matched_title"):
                    f.write(
                        f"- 最接近 ({r.get('source', '?')}): {r['matched_title']} "
                        f"(标题相似度 {r.get('similarity', 0):.0%})\n"
                    )
                f.write(f"- 作者核查: {r.get('author_reason', '')}\n\n")

        if review:
            f.write("## ⚠️ 需要人工复核的条目\n\n")
            f.write("| Key | 来源 | 标题相似度 | 作者核查 | 年份核查 | DOI 核查 | 复核原因 |\n")
            f.write("|---|---|---:|---|---|---|---|\n")
            for r in review:
                f.write(
                    f"| {safe_table_text(r['key'], 35)} "
                    f"| {safe_table_text(r.get('source', ''), 20)} "
                    f"| {r.get('similarity', 0):.0%} "
                    f"| {safe_table_text(r.get('author_check', '') + ': ' + r.get('author_reason', ''), 70)} "
                    f"| {safe_table_text(r.get('year_check', '') + ': ' + r.get('year_reason', ''), 45)} "
                    f"| {safe_table_text(r.get('doi_check', '') + ': ' + r.get('doi_reason', ''), 45)} "
                    f"| {safe_table_text(r.get('review_reasons', ''), 90)} |\n"
                )

        if found:
            f.write("\n## ✅ 已找到的文献\n\n")
            f.write("| Key | 标题 | 来源 | 标题相似度 | 作者 | 年份 | DOI/URL |\n")
            f.write("|---|---|---|---:|---|---|---|\n")
            for r in found:
                link = r.get("matched_doi") or r.get("doi") or r.get("url", "")
                f.write(
                    f"| {safe_table_text(r['key'], 40)} "
                    f"| {safe_table_text(r['title'], 50)} "
                    f"| {safe_table_text(r.get('source', ''), 20)} "
                    f"| **{r.get('similarity', 0):.0%}** "
                    f"| {status_icon(r.get('author_check'))} {safe_table_text(r.get('author_check', ''), 12)} "
                    f"| {status_icon(r.get('year_check'))} {safe_table_text(r.get('matched_year', ''), 8)} "
                    f"| {safe_table_text(link, 45)} |\n"
                )

        if author_mismatch:
            f.write("\n## ❌ 作者不一致详情\n\n")
            for r in author_mismatch:
                f.write(f"### `{r['key']}`\n")
                f.write(f"- 标题: {r['title']}\n")
                f.write(f"- 问题: {r.get('author_reason', '')}\n")
                f.write(f"- BibTeX 作者: {r.get('bib_authors', '')}\n")
                f.write(f"- 数据库作者: {r.get('matched_authors', '')}\n")
                if r.get("missing_authors"):
                    f.write(f"- BibTeX 可能省略: {r.get('missing_authors')}\n")
                if r.get("extra_authors"):
                    f.write(f"- BibTeX 可能额外/可疑: {r.get('extra_authors')}\n")
                f.write("\n")

        if skipped:
            f.write("\n## ⚠️ 跳过\n\n")
            for r in skipped:
                f.write(f"- `{r['key']}`: {r.get('reason', '')}\n")


def write_csv_report(path: str, results: list[dict]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fieldnames = [
        "key", "status", "needs_review", "review_reasons",
        "bib_title", "matched_title", "similarity", "source", "venue", "year", "type",
        "bib_year", "matched_year", "year_check", "year_reason",
        "bib_doi", "matched_doi", "doi_check", "doi_reason",
        "bib_author_count", "matched_author_count", "author_check", "first_author_match",
        "author_order_mismatch", "bib_authors", "matched_authors", "missing_authors",
        "extra_authors", "author_reason", "authors", "doi", "url", "reason",
    ]
    with open(path, "w", encoding="utf-8-sig", newline="") as cf:
        writer = csv.DictWriter(cf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = dict(r)
            row["bib_title"] = r.get("title", "")
            row["matched_title"] = r.get("matched_title", "")
            row["similarity"] = f"{r.get('similarity', 0):.2%}" if r.get("similarity") is not None else ""
            writer.writerow(row)


def emit_jsonl(event_type: str, **payload) -> None:
    payload["type"] = event_type
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def printable_result(result: dict) -> dict:
    keys = [
        "key", "title", "status", "needs_review", "review_reasons",
        "matched_title", "similarity", "source", "venue", "year", "type",
        "author_check", "author_reason", "year_check", "year_reason",
        "doi_check", "doi_reason", "bib_doi", "matched_doi", "doi", "url", "reason",
    ]
    return {key: result.get(key, "") for key in keys}


# --------------------------- DOCX / APA 参考文献解析 ---------------------------

def _apa_authors_to_bibtex(authors_text: str) -> str:
    """将 APA 格式作者列表转换为 BibTeX 兼容的 ' and ' 分隔格式。

    APA 格式: "Author1, A. B., Author2, C. D., & Author3, E. F."
    BibTeX 格式: "Author1, A. B. and Author2, C. D. and Author3, E. F."

    策略：按 "., " (句号-逗号-空格，作者边界) 分割，然后清理。
    """
    if not authors_text:
        return ""
    t = authors_text.strip().rstrip(',.')
    # 按 "., " 或 ". & " 或 ". and " 分割（APA 作者边界）
    parts = re.split(r'\.\s*[,，]\s*|\.\s*&\s*|\.\s+and\s+', t, flags=re.I)
    result = []
    for part in parts:
        part = part.strip().rstrip(',.')
        if not part:
            continue
        # 去除前导 "& " / "and "
        part = re.sub(r'^(?:&|and)\s+', '', part, flags=re.I).strip()
        # 加上句号（被 split 去掉了）
        if part and not part.endswith('.'):
            part += '.'
        if part:
            result.append(part)
    return " and ".join(result)


def parse_reference_text(text: str) -> dict:
    """解析 APA 格式参考文献，提取 DOI、年份、作者、标题。"""
    original = text.strip()
    if not original:
        return {"text": "", "title": "", "authors": "", "year": "", "doi": ""}

    # 1. 提取 DOI URL（通常位于末尾）
    doi = ""
    doi_match = re.search(r'https?://(dx\.)?doi\.org/(10\.\S+)', original)
    if doi_match:
        doi = doi_match.group(2).rstrip('.;,')
        # 去掉 DOI 部分以便解析剩余文本
        text_body = original[:doi_match.start()].strip().rstrip('.').strip()
    else:
        text_body = original

    if not text_body:
        text_body = original

    # 2. 提取年份: (YYYY)
    year = ""
    year_match = re.search(r'\((\d{4})\)', text_body)
    if year_match:
        year = year_match.group(1)
        authors_raw = text_body[:year_match.start()].strip().rstrip(',. (')
        authors = _apa_authors_to_bibtex(authors_raw)
        # rest = 年份之后的部分
        after_year = text_body[year_match.end():].strip()
        # 去除 "). " / ") " / ". " 前缀
        if after_year.startswith(').'):
            after_year = after_year[2:].strip()
        elif after_year.startswith(') '):
            after_year = after_year[2:].strip()
        if after_year.startswith('.'):
            after_year = after_year[1:].strip()
        after_year = after_year.strip()
    else:
        authors = ""
        after_year = ""

    # 3. 提取标题
    # 标题位于 "). " 之后，期刊信息之前
    # 期刊信息通常以 ", Volume" 或 ", Vol" 或 "http" 开头
    title = after_year
    if after_year:
        # 尝试匹配 ", \d+\(\d+\)" (卷号(期号)) 来定位期刊边界
        journal_pattern = re.search(r',\s*\d+\s*\(\d+\)', after_year)
        if journal_pattern:
            title_candidate = after_year[:journal_pattern.start()].strip().rstrip('.')
            if len(title_candidate) > 5:
                title = title_candidate
        else:
            title = after_year

    return {
        "text": original,
        "title": title or original,
        "authors": authors,
        "year": year,
        "doi": doi,
    }


def extract_references_from_docx(path: str) -> list[dict]:
    """从 Word 文档中提取参考文献段落。

    识别所有 "Bibliography" 样式的段落，
    返回包含原始文本和解析元数据的字典列表。
    """
    try:
        from docx import Document as DocxDocument
    except ImportError:
        sys.exit("请先安装 python-docx: pip install python-docx")

    doc = DocxDocument(path)
    refs = []
    for i, para in enumerate(doc.paragraphs):
        style = (para.style.name if para.style else "").lower()
        text = para.text.strip()
        if not text:
            continue
        # "Bibliography" 样式 或 "参考" / "参考文献" 样式
        is_bib = "bibliography" in style or "reference" in style or "biblio" in style
        if not is_bib:
            # 没有样式信息时，检查是否像参考文献格式
            # APA 格式特征: 包含 "(19xx)" 或 "(20xx)" 且有 DOI
            has_year = bool(re.search(r'\((?:19|20)\d{2}\)', text))
            has_doi = bool(re.search(r'doi\.org/', text))
            if not (has_year and has_doi):
                continue

        parsed = parse_reference_text(text)
        parsed["index"] = i  # 段落序号
        parsed["paragraph"] = i + 1  # 1-based for display
        refs.append(parsed)

    return refs


def verify_docx_file(docx_path: str, *, threshold: float = 0.85, delay: float = 0.2,
                     email: str = "", use_openalex: bool = True, use_dblp: bool = True,
                     use_url_verify: bool = True,
                     output: str | None = None, csv_path: str | None = None,
                     output_dir: str | None = None, jsonl_progress: bool = False,
                     human_output: bool = True) -> dict:
    """从 .docx 文件中提取参考文献并进行验证。"""
    log_stream = sys.stderr if jsonl_progress else sys.stdout

    def log(message: str = "") -> None:
        if human_output:
            print(message, file=log_stream, flush=True)

    def event(event_type: str, **payload) -> None:
        if jsonl_progress:
            emit_jsonl(event_type, **payload)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output = output or os.path.join(output_dir, "report.md")
        csv_path = csv_path or os.path.join(output_dir, "result.csv")

    refs = extract_references_from_docx(docx_path)
    total = len(refs)
    sources = "CrossRef" + (" + OpenAlex" if use_openalex else "") + (" + DBLP" if use_dblp else "")
    if use_url_verify:
        sources += " + URL"
    log(f"📚 从 DOCX 解析到 {total} 条参考文献，开始验证 ({sources}, 标题阈值 {threshold:.0%})\n")
    event("started", total=total, sources=sources, threshold=threshold,
          use_openalex=use_openalex, use_dblp=use_dblp,
          use_url_verify=use_url_verify, bibfile=os.path.abspath(docx_path))

    results = []
    for i, ref in enumerate(refs, 1):
        key = f"ref[{ref.get('paragraph', i)}]"
        title_clean = strip_latex(ref.get("title", "") or ref.get("text", ""))
        author = ref.get("authors", "")
        year = ref.get("year", "")
        doi = ref.get("doi", "")
        ref_url = ref.get("url", "")

        log(f"[{i}/{total}] {key}")
        log(f"    标题: {truncate(title_clean, 90)}")
        event("entry_started", index=i, total=total, key=key, title=title_clean)

        if not title_clean:
            log("    ⚠️  跳过：无法提取标题\n")
            row = {"key": key, "title": "", "status": "skipped",
                   "reason": "无法提取标题", "needs_review": "Yes"}
            results.append(row)
            event("entry_finished", index=i, total=total, result=printable_result(row))
            continue

        res = verify_entry(title_clean, author, year, doi, threshold,
                           email, use_openalex, use_dblp, url=ref_url,
                           use_url_verify=use_url_verify)

        if res.get("found"):
            res["status"] = "found"
            sim = res["similarity"]
            flag = "🟡" if sim < 1.0 or res.get("needs_review") == "Yes" else "✅"
            log(f"    {flag} 找到 [{res['source']}] (标题相似度 {sim:.0%})")
            if sim < 1.0:
                log(f"        Bib 标题: {truncate(title_clean, 90)}")
                log(f"        匹配标题: {truncate(res.get('matched_title', ''), 90)}")
            else:
                log(f"        标题: {truncate(res.get('matched_title', ''), 90)}")
            if res.get("venue"):
                log(f"        来源: {res['venue']} ({res.get('year', '')})  类型: {res.get('type', '')}")
            if res.get("doi"):
                log(f"        DOI: {res['doi']}")
        else:
            res["status"] = "not_found"
            log(f"    ❌ 未找到: {res.get('reason', '')}")
            if res.get("matched_title"):
                log(f"        最接近: {truncate(res['matched_title'], 90)} ({res.get('similarity', 0):.0%})")

        log(f"        作者: {status_icon(res.get('author_check'))} {res.get('author_reason', '')}")
        if res.get("year_check") == "mismatch":
            log(f"        年份: ❌ {res.get('year_reason', '')}")
        if res.get("doi_check") == "mismatch":
            log(f"        DOI : ❌ {res.get('doi_reason', '')}")

        row = {"key": key, "title": title_clean, **res}
        results.append(row)
        event("entry_finished", index=i, total=total, result=printable_result(row))

        log()
        if i < total:
            time.sleep(delay)

    summary = build_summary(results)
    counts = summary_counts(summary, total)

    log("=" * 72)
    log(
        f"总结: ✅ {counts['found']} 找到 | ❌ {counts['not_found']} 未找到 | "
        f"⚠️ {counts['needs_review']} 需复核 | 跳过 {counts['skipped']}"
    )
    log(
        f"元数据问题: 作者不一致 {counts['author_mismatch']} | "
        f"年份不一致 {counts['year_mismatch']} | DOI 不一致 {counts['doi_mismatch']}"
    )
    log("=" * 72)

    if summary["missing"]:
        log("\n⚠️  以下文献未匹配上，建议人工核查：")
        for r in summary["missing"]:
            log(f"   - [{r['key']}] {truncate(r['title'], 80)}")

    if summary["author_mismatch"]:
        log("\n❌ 以下文献作者元数据不一致，建议重点核查：")
        for r in summary["author_mismatch"][:30]:
            log(f"   - [{r['key']}] {r.get('author_reason', '')}")
        if len(summary["author_mismatch"]) > 30:
            log(f"   ... 另有 {len(summary['author_mismatch']) - 30} 条，请查看报告/CSV")

    output_path = os.path.abspath(output) if output else ""
    csv_output_path = os.path.abspath(csv_path) if csv_path else ""
    if output:
        write_markdown_report(output, bibfile=docx_path, sources=sources, threshold=threshold,
                              total=total, results=results, summary=summary)
        log(f"\n📄 报告已保存到: {output}")
    if csv_path:
        write_csv_report(csv_path, results)
        log(f"📊 CSV 表格已保存到: {csv_path}")

    counts.update({
        "bibfile": os.path.abspath(docx_path),
        "sources": sources,
        "output_dir": os.path.abspath(output_dir) if output_dir else "",
        "markdown_path": output_path,
        "csv_path": csv_output_path,
    })
    event("summary", **counts)
    return {"results": results, "summary": counts}


def verify_bib_file(bibfile: str, *, threshold: float = 0.85, delay: float = 0.2,
                    email: str = "", use_openalex: bool = True, use_dblp: bool = True,
                    use_url_verify: bool = True,
                    output: str | None = None, csv_path: str | None = None,
                    output_dir: str | None = None, jsonl_progress: bool = False,
                    human_output: bool = True) -> dict:
    log_stream = sys.stderr if jsonl_progress else sys.stdout

    def log(message: str = "") -> None:
        if human_output:
            print(message, file=log_stream, flush=True)

    def event(event_type: str, **payload) -> None:
        if jsonl_progress:
            emit_jsonl(event_type, **payload)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output = output or os.path.join(output_dir, "report.md")
        csv_path = csv_path or os.path.join(output_dir, "result.csv")

    with open(bibfile, "r", encoding="utf-8") as f:
        if jsonl_progress:
            parser_noise = log_stream
            with contextlib.redirect_stdout(parser_noise), contextlib.redirect_stderr(parser_noise):
                bib_db = bibtexparser.load(f)
        else:
            bib_db = bibtexparser.load(f)

    total = len(bib_db.entries)
    sources = "CrossRef" + (" + OpenAlex" if use_openalex else "") + (" + DBLP" if use_dblp else "")
    if use_url_verify:
        sources += " + URL"
    log(f"📚 解析到 {total} 条文献，开始验证 ({sources}, 标题阈值 {threshold:.0%})\n")
    event("started", total=total, sources=sources, threshold=threshold,
          use_openalex=use_openalex, use_dblp=use_dblp,
          use_url_verify=use_url_verify, bibfile=os.path.abspath(bibfile))

    results = []
    for i, entry in enumerate(bib_db.entries, 1):
        key = entry.get("ID", "<no-key>")
        title = entry.get("title", "").replace("\n", " ").strip()
        title_clean = strip_latex(title)
        author = entry.get("author", "")
        year = entry.get("year", "")
        doi = entry.get("doi", "") or entry.get("DOI", "")
        url = entry.get("url", "") or entry.get("URL", "")
        if not url:
            howpub = entry.get("howpublished", "")
            if howpub:
                m = re.search(r'\\url\{([^}]+)\}', howpub)
                if m:
                    url = m.group(1)
                elif howpub.startswith("http"):
                    url = howpub

        log(f"[{i}/{total}] {key}")
        log(f"    标题: {truncate(title_clean, 90)}")
        event("entry_started", index=i, total=total, key=key, title=title_clean)

        if not title_clean:
            log("    ⚠️  跳过：缺少 title 字段\n")
            row = {"key": key, "title": "", "status": "skipped",
                   "reason": "缺少 title", "needs_review": "Yes"}
            results.append(row)
            event("entry_finished", index=i, total=total, result=printable_result(row))
            continue

        res = verify_entry(title_clean, author, year, doi, threshold,
                           email, use_openalex, use_dblp, url=url,
                           use_url_verify=use_url_verify)

        if res.get("found"):
            res["status"] = "found"
            sim = res["similarity"]
            flag = "🟡" if sim < 1.0 or res.get("needs_review") == "Yes" else "✅"
            log(f"    {flag} 找到 [{res['source']}] (标题相似度 {sim:.0%})")
            if sim < 1.0:
                log(f"        Bib 标题: {truncate(title_clean, 90)}")
                log(f"        匹配标题: {truncate(res.get('matched_title', ''), 90)}")
            else:
                log(f"        标题: {truncate(res.get('matched_title', ''), 90)}")
            if res.get("venue"):
                log(f"        来源: {res['venue']} ({res.get('year', '')})  类型: {res.get('type', '')}")
            if res.get("doi"):
                log(f"        DOI: {res['doi']}")
        else:
            res["status"] = "not_found"
            log(f"    ❌ 未找到: {res.get('reason', '')}")
            if res.get("matched_title"):
                log(f"        最接近: {truncate(res['matched_title'], 90)} ({res.get('similarity', 0):.0%})")

        log(f"        作者: {status_icon(res.get('author_check'))} {res.get('author_reason', '')}")
        if res.get("year_check") == "mismatch":
            log(f"        年份: ❌ {res.get('year_reason', '')}")
        if res.get("doi_check") == "mismatch":
            log(f"        DOI : ❌ {res.get('doi_reason', '')}")

        row = {"key": key, "title": title_clean, **res}
        results.append(row)
        event("entry_finished", index=i, total=total, result=printable_result(row))

        log()
        if i < total:
            time.sleep(delay)

    summary = build_summary(results)
    counts = summary_counts(summary, total)

    log("=" * 72)
    log(
        f"总结: ✅ {counts['found']} 找到 | ❌ {counts['not_found']} 未找到 | "
        f"⚠️ {counts['needs_review']} 需复核 | 跳过 {counts['skipped']}"
    )
    log(
        f"元数据问题: 作者不一致 {counts['author_mismatch']} | "
        f"年份不一致 {counts['year_mismatch']} | DOI 不一致 {counts['doi_mismatch']}"
    )
    log("=" * 72)

    if summary["missing"]:
        log("\n⚠️  以下文献未匹配上，建议人工核查：")
        for r in summary["missing"]:
            log(f"   - [{r['key']}] {truncate(r['title'], 80)}")

    if summary["author_mismatch"]:
        log("\n❌ 以下文献作者元数据不一致，建议重点核查：")
        for r in summary["author_mismatch"][:30]:
            log(f"   - [{r['key']}] {r.get('author_reason', '')}")
        if len(summary["author_mismatch"]) > 30:
            log(f"   ... 另有 {len(summary['author_mismatch']) - 30} 条，请查看报告/CSV")

    output_path = os.path.abspath(output) if output else ""
    csv_output_path = os.path.abspath(csv_path) if csv_path else ""
    if output:
        write_markdown_report(output, bibfile=bibfile, sources=sources, threshold=threshold,
                              total=total, results=results, summary=summary)
        log(f"\n📄 报告已保存到: {output}")
    if csv_path:
        write_csv_report(csv_path, results)
        log(f"📊 CSV 表格已保存到: {csv_path}")

    counts.update({
        "bibfile": os.path.abspath(bibfile),
        "sources": sources,
        "output_dir": os.path.abspath(output_dir) if output_dir else "",
        "markdown_path": output_path,
        "csv_path": csv_output_path,
    })
    event("summary", **counts)
    return {"results": results, "summary": counts}


def main():
    parser = argparse.ArgumentParser(description="基于 CrossRef + OpenAlex + DBLP 验证 BibTeX / DOCX 文献")
    parser.add_argument("file", help=".bib 或 .docx 文件路径")
    parser.add_argument("--threshold", type=float, default=0.85,
                        help="标题相似度阈值 (0-1)，默认 0.85")
    parser.add_argument("--delay", type=float, default=0.2,
                        help="每条文献核查后的间隔秒数，默认 0.2")
    parser.add_argument("--email", default="",
                        help="你的邮箱 (放进 User-Agent / mailto，访问 CrossRef/OpenAlex 更稳)")
    parser.add_argument("--no-openalex", action="store_true",
                        help="不使用 OpenAlex 兜底")
    parser.add_argument("--no-dblp", action="store_true",
                        help="不使用 DBLP 兜底")
    parser.add_argument("--no-url-verify", action="store_true",
                        help="不验证 URL 资源（HuggingFace / GitHub / 通用网页）")
    parser.add_argument("--output", default=None, help="可选: 写入 Markdown 报告路径")
    parser.add_argument("--csv", default=None, help="可选: 写入 CSV 表格路径")
    parser.add_argument("--output-dir", default=None,
                        help="可选: 输出目录；未指定 --output/--csv 时生成 report.md 与 result.csv")
    parser.add_argument("--jsonl-progress", action="store_true",
                        help="逐行输出 JSON 进度事件，便于 Flutter 等 UI 调用")
    args = parser.parse_args()

    try:
        file_path = args.file
        ext = os.path.splitext(file_path)[1].lower()
        common_args = dict(
            threshold=args.threshold,
            delay=args.delay,
            email=args.email,
            use_openalex=not args.no_openalex,
            use_dblp=not args.no_dblp,
            use_url_verify=not args.no_url_verify,
            output=args.output,
            csv_path=args.csv,
            output_dir=args.output_dir,
            jsonl_progress=args.jsonl_progress,
            human_output=True,
        )
        if ext == ".docx":
            verify_docx_file(file_path, **common_args)
        else:
            verify_bib_file(file_path, **common_args)
    except Exception as exc:
        if args.jsonl_progress:
            emit_jsonl("error", message=str(exc), traceback=traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
