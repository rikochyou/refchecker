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
import csv
import re
import sys
import time
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
    if result.get("similarity", 0) < 1.0:
        review_reasons.append(f"标题相似度 {result.get('similarity', 0):.0%}")
    if result["author_check"] in {"mismatch", "partial", "unknown"}:
        review_reasons.append(f"作者核查: {result['author_reason']}")
    if result["year_check"] == "mismatch":
        review_reasons.append(result["year_reason"])
    if result["doi_check"] == "mismatch":
        review_reasons.append(result["doi_reason"])

    result["needs_review"] = "Yes" if review_reasons else "No"
    result["review_reasons"] = "；".join(review_reasons)
    return result


def verify_entry(title: str, author: str, year: str, doi: str, threshold: float,
                 email: str, use_openalex: bool, use_dblp: bool) -> dict:
    """先查 DOI，再查 CrossRef 标题，最后用 OpenAlex / DBLP 兜底。"""
    candidates = []

    doi_result = search_crossref_by_doi(doi, title, email) if doi else None
    if doi_result and doi_result.get("matched_title"):
        candidates.append(doi_result)
        if doi_result.get("similarity", 0) >= threshold:
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


def main():
    parser = argparse.ArgumentParser(description="基于 CrossRef + OpenAlex + DBLP 验证 BibTeX 文献")
    parser.add_argument("bibfile", help=".bib 文件路径")
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
    parser.add_argument("--output", default=None, help="可选: 写入 Markdown 报告路径")
    parser.add_argument("--csv", default=None, help="可选: 写入 CSV 表格路径")
    args = parser.parse_args()

    with open(args.bibfile, "r", encoding="utf-8") as f:
        bib_db = bibtexparser.load(f)

    n = len(bib_db.entries)
    use_oa = not args.no_openalex
    use_dblp = not args.no_dblp
    sources = "CrossRef" + (" + OpenAlex" if use_oa else "") + (" + DBLP" if use_dblp else "")
    print(f"📚 解析到 {n} 条文献，开始验证 ({sources}, 标题阈值 {args.threshold:.0%})\n")

    results = []
    for i, entry in enumerate(bib_db.entries, 1):
        key = entry.get("ID", "<no-key>")
        title = entry.get("title", "").replace("\n", " ").strip()
        title_clean = strip_latex(title)
        author = entry.get("author", "")
        year = entry.get("year", "")
        doi = entry.get("doi", "") or entry.get("DOI", "")

        print(f"[{i}/{n}] {key}")
        print(f"    标题: {truncate(title_clean, 90)}")

        if not title_clean:
            print("    ⚠️  跳过：缺少 title 字段\n")
            results.append({"key": key, "title": "", "status": "skipped",
                            "reason": "缺少 title", "needs_review": "Yes"})
            continue

        res = verify_entry(title_clean, author, year, doi, args.threshold,
                           args.email, use_oa, use_dblp)

        if res.get("found"):
            res["status"] = "found"
            sim = res["similarity"]
            flag = "🟡" if sim < 1.0 or res.get("needs_review") == "Yes" else "✅"
            print(f"    {flag} 找到 [{res['source']}] (标题相似度 {sim:.0%})")
            if sim < 1.0:
                print(f"        Bib 标题: {truncate(title_clean, 90)}")
                print(f"        匹配标题: {truncate(res.get('matched_title', ''), 90)}")
            else:
                print(f"        标题: {truncate(res.get('matched_title', ''), 90)}")
            if res.get("venue"):
                print(f"        来源: {res['venue']} ({res.get('year', '')})  类型: {res.get('type', '')}")
            if res.get("doi"):
                print(f"        DOI: {res['doi']}")
        else:
            res["status"] = "not_found"
            print(f"    ❌ 未找到: {res.get('reason', '')}")
            if res.get("matched_title"):
                print(f"        最接近: {truncate(res['matched_title'], 90)} ({res.get('similarity', 0):.0%})")

        print(f"        作者: {status_icon(res.get('author_check'))} {res.get('author_reason', '')}")
        if res.get("year_check") == "mismatch":
            print(f"        年份: ❌ {res.get('year_reason', '')}")
        if res.get("doi_check") == "mismatch":
            print(f"        DOI : ❌ {res.get('doi_reason', '')}")

        results.append({"key": key, "title": title_clean, **res})

        print()
        if i < n:
            time.sleep(args.delay)

    # ---------- 汇总 ----------
    found = [r for r in results if r["status"] == "found"]
    missing = [r for r in results if r["status"] == "not_found"]
    skipped = [r for r in results if r["status"] == "skipped"]
    review = [r for r in results if r.get("needs_review") == "Yes"]
    author_mismatch = [r for r in results if r.get("author_check") == "mismatch"]
    year_mismatch = [r for r in results if r.get("year_check") == "mismatch"]
    doi_mismatch = [r for r in results if r.get("doi_check") == "mismatch"]

    print("=" * 72)
    print(
        f"总结: ✅ {len(found)} 找到 | ❌ {len(missing)} 未找到 | "
        f"⚠️ {len(review)} 需复核 | 跳过 {len(skipped)}"
    )
    print(
        f"元数据问题: 作者不一致 {len(author_mismatch)} | "
        f"年份不一致 {len(year_mismatch)} | DOI 不一致 {len(doi_mismatch)}"
    )
    print("=" * 72)

    if missing:
        print("\n⚠️  以下文献未匹配上，建议人工核查：")
        for r in missing:
            print(f"   - [{r['key']}] {truncate(r['title'], 80)}")

    if author_mismatch:
        print("\n❌ 以下文献作者元数据不一致，建议重点核查：")
        for r in author_mismatch[:30]:
            print(f"   - [{r['key']}] {r.get('author_reason', '')}")
        if len(author_mismatch) > 30:
            print(f"   ... 另有 {len(author_mismatch) - 30} 条，请查看报告/CSV")

    # ---------- Markdown 报告 ----------
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("# BibTeX 文献真实性与元数据一致性验证报告\n\n")
            f.write(f"- 文件: `{args.bibfile}`\n")
            f.write(f"- 数据源: **{sources}**\n")
            f.write(f"- 标题相似度阈值: **{args.threshold:.0%}**\n")
            f.write(
                f"- 总数: **{n}** | ✅ 找到: **{len(found)}** | ❌ 未找到: **{len(missing)}** "
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
        print(f"\n📄 报告已保存到: {args.output}")

    # ---------- CSV 输出 ----------
    if args.csv:
        fieldnames = [
            "key", "status", "needs_review", "review_reasons",
            "bib_title", "matched_title", "similarity", "source", "venue", "year", "type",
            "bib_year", "matched_year", "year_check", "year_reason",
            "bib_doi", "matched_doi", "doi_check", "doi_reason",
            "bib_author_count", "matched_author_count", "author_check", "first_author_match",
            "author_order_mismatch", "bib_authors", "matched_authors", "missing_authors",
            "extra_authors", "author_reason", "authors", "doi", "url", "reason",
        ]
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as cf:
            writer = csv.DictWriter(cf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in results:
                row = dict(r)
                row["bib_title"] = r.get("title", "")
                row["matched_title"] = r.get("matched_title", "")
                row["similarity"] = f"{r.get('similarity', 0):.2%}" if r.get("similarity") is not None else ""
                writer.writerow(row)
        print(f"📊 CSV 表格已保存到: {args.csv}")


if __name__ == "__main__":
    main()
