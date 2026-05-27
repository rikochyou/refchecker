"""RefChecker — 疑似虚构引用与参考文献元数据核验."""
import csv
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from .utils import strip_latex, title_similarity, extract_year, clean_doi, truncate, compare_year, compare_doi
from .author import compare_author_lists, author_display_list, parse_author_name
from . import sources as _sources
from . import url_verify as _url_verify
from . import custom_rest as _custom_rest
from .config import build_source_order, DEFAULT_SOURCE_ORDER
from .version import APP_VERSION

# --------------------------- 主验证流程 ---------------------------

def _search_source(source_name: str, title: str, author: str, year: str,
                   threshold: float, email: str,
                   springer_api_key: str = "", ieee_api_key: str = "",
                   core_api_key: str = "",
                   custom_rest_profiles: dict[str, dict] | None = None) -> dict:
    """调用指定数据源检索文献。"""
    if source_name == "crossref":
        return _sources.search_crossref(title, author, year, threshold, email)
    if source_name == "openalex":
        return _sources.search_openalex(title, author, year, threshold, email)
    if source_name == "semantic-scholar":
        return _sources.search_semantic_scholar(title, author, year, threshold, email)
    if source_name == "arxiv":
        return _sources.search_arxiv(title, author, year, threshold)
    if source_name == "pubmed":
        return _sources.search_pubmed(title, author, year, threshold, email)
    if source_name == "springer":
        return _sources.search_springer(title, author, year, threshold, springer_api_key)
    if source_name == "ieee":
        return _sources.search_ieee(title, author, year, threshold, ieee_api_key)
    if source_name == "core":
        return _sources.search_core(title, author, year, threshold, core_api_key)
    if source_name == "dblp":
        return _sources.search_dblp(title, author, year, threshold)
    if custom_rest_profiles and source_name in custom_rest_profiles:
        return _custom_rest.search_custom_rest(
            custom_rest_profiles[source_name], title, author, year, threshold, email
        )
    return {"found": False, "reason": f"未知数据源: {source_name}"}


_SOURCE_NAME_LABEL = {
    "crossref": "CrossRef", "openalex": "OpenAlex",
    "semantic-scholar": "Semantic Scholar", "arxiv": "arXiv",
    "pubmed": "PubMed", "springer": "Springer Nature",
    "ieee": "IEEE Xplore", "core": "CORE", "dblp": "DBLP",
}


def _source_enabled(source_name: str, *,
                    use_openalex: bool, use_dblp: bool,
                    use_semantic_scholar: bool, use_arxiv: bool,
                    use_pubmed: bool, use_crossref: bool,
                    use_springer: bool, use_ieee: bool, use_core: bool,
                    springer_api_key: str, ieee_api_key: str,
                    core_api_key: str,
                    custom_rest_profiles: dict[str, dict] | None = None) -> bool:
    if source_name == "crossref":
        return use_crossref
    if source_name == "openalex":
        return use_openalex
    if source_name == "semantic-scholar":
        return use_semantic_scholar
    if source_name == "arxiv":
        return use_arxiv
    if source_name == "pubmed":
        return use_pubmed
    if source_name == "springer":
        return use_springer and bool(springer_api_key)
    if source_name == "ieee":
        return use_ieee and bool(ieee_api_key)
    if source_name == "core":
        return use_core and bool(core_api_key)
    if source_name == "dblp":
        return use_dblp
    if custom_rest_profiles and source_name in custom_rest_profiles:
        return True
    return False


_SOURCE_RELIABILITY = {
    "CrossRef(DOI)": 0.98,
    "CrossRef": 0.95,
    "PubMed": 0.94,
    "Springer Nature": 0.93,
    "IEEE Xplore": 0.93,
    "OpenAlex": 0.90,
    "Semantic Scholar": 0.86,
    "DBLP": 0.86,
    "arXiv": 0.82,
    "CORE": 0.78,
    "URL(Web)": 0.55,
}


def _source_label(source_name: str, custom_rest_profiles: dict[str, dict] | None = None) -> str:
    """Return a user-facing source label for built-in or custom sources."""
    if custom_rest_profiles and source_name in custom_rest_profiles:
        return custom_rest_profiles[source_name].get("name") or source_name
    return _SOURCE_NAME_LABEL.get(source_name, source_name)


def _has_candidate_payload(result: dict | None) -> bool:
    if not result:
        return False
    return bool(
        result.get("matched_title")
        or result.get("found")
        or result.get("doi_exact_query")
        or result.get("doi")
        or result.get("url")
    )


def _is_web_evidence_result(result: dict | None) -> bool:
    if not result:
        return False
    if str(result.get("web_evidence") or "").strip().lower() in {"yes", "true", "1", "web"}:
        return True
    if str(result.get("evidence_kind") or "").strip().lower() in {"web", "web_evidence", "web_search"}:
        return True
    source = str(result.get("source") or "")
    return "Web Evidence" in source or source.lower().startswith("brave ")


def _candidate_reliability(result: dict) -> float:
    source = result.get("source", "")
    if _is_web_evidence_result(result):
        return 0.58
    if source in _SOURCE_RELIABILITY:
        return _SOURCE_RELIABILITY[source]
    if source.startswith("URL("):
        return 0.60
    return 0.74


def _arbitration_score(result: dict, *, threshold: float) -> float:
    """Score one enriched candidate for cross-source arbitration.

    Title similarity and DOI/metadata agreement dominate the score. Source order is
    intentionally not baked in here; it is used only as a tie-breaker when evidence
    quality is close.
    """
    similarity = result.get("similarity", 0) or 0
    score = similarity * 100.0

    if result.get("doi_exact_query"):
        score += 28

    doi_check = result.get("doi_check")
    if doi_check == "exact":
        score += 22
    elif doi_check == "missing_in_bib" and result.get("matched_doi"):
        score += 8
    elif doi_check == "mismatch":
        score -= 65

    author_check = result.get("author_check")
    if author_check == "exact":
        score += 10
    elif author_check == "partial":
        score += 4
    elif author_check == "mismatch":
        score -= 22
        if _first_author_is_mismatch(result.get("first_author_match")):
            score -= 18

    year_check = result.get("year_check")
    if year_check == "exact":
        score += 7
    elif year_check == "mismatch":
        score -= 18

    # A small nudge for a source that already passed its own title threshold.
    if result.get("found") and similarity >= threshold:
        score += 4

    return score


def _compact_candidate(result: dict) -> dict:
    return {
        "source": result.get("source", ""),
        "matched_title": result.get("matched_title", ""),
        "similarity": round(float(result.get("similarity", 0) or 0), 4),
        "doi": result.get("matched_doi") or result.get("doi", ""),
        "year": result.get("matched_year") or result.get("year", ""),
        "author_check": result.get("author_check", ""),
        "year_check": result.get("year_check", ""),
        "doi_check": result.get("doi_check", ""),
        "score": round(float(result.get("arbitration_score", 0) or 0), 2),
        "reason": result.get("reason", ""),
    }


def _format_candidate_line(result: dict) -> str:
    sim = result.get("similarity", 0) or 0
    bits = [
        f"{result.get('source', 'Unknown')} {sim:.0%}",
    ]
    if result.get("doi_check"):
        bits.append(f"DOI:{result.get('doi_check')}")
    if result.get("author_check"):
        bits.append(f"作者:{result.get('author_check')}")
    if result.get("year_check"):
        bits.append(f"年份:{result.get('year_check')}")
    if result.get("arbitration_score") is not None:
        bits.append(f"评分:{result.get('arbitration_score'):.1f}")
    return " / ".join(bits)


def _format_source_trace(trace: list[dict]) -> str:
    rows = []
    for item in sorted(trace, key=lambda row: row.get("order", 999)):
        label = item.get("source", "")
        status = item.get("status", "")
        sim = item.get("similarity")
        reason = item.get("reason", "")
        if sim is not None:
            rows.append(f"{label}: {status} ({sim:.0%})")
        elif reason:
            rows.append(f"{label}: {status} - {reason}")
        else:
            rows.append(f"{label}: {status}")
    return "；".join(rows)


def _candidate_conflict(best: dict, alternatives: list[dict], *, threshold: float) -> str:
    """Detect strong contradictory evidence from other high-quality candidates."""
    best_doi = clean_doi(best.get("matched_doi") or best.get("doi", ""))
    best_year = extract_year(best.get("matched_year") or best.get("year", ""))
    conflicts = []
    for alt in alternatives:
        alt_similarity = alt.get("similarity", 0) or 0
        if alt_similarity < max(0.90, threshold):
            continue
        # Ignore much weaker alternatives; they are useful trace data, not a conflict.
        if (best.get("arbitration_score", 0) or 0) - (alt.get("arbitration_score", 0) or 0) > 18:
            continue
        alt_doi = clean_doi(alt.get("matched_doi") or alt.get("doi", ""))
        alt_year = extract_year(alt.get("matched_year") or alt.get("year", ""))
        if best_doi and alt_doi and best_doi != alt_doi:
            conflicts.append(f"{alt.get('source')} DOI={alt_doi}")
        elif best_year and alt_year and best_year != alt_year:
            conflicts.append(f"{alt.get('source')} 年份={alt_year}")
    if not conflicts:
        return ""
    return "多个高相似度候选存在元数据冲突：" + "；".join(conflicts[:3])


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
    # URL(Web) 来源的 similarity 是 URL vs 标题，0% 是正常的，不标记。
    # “需人工核查”只保留高风险信号：标题低于 85% 才进入强制核查；
    # 85%-90% 放入中风险/建议抽查，避免小样本里大面积提示人工核查。
    if result.get("similarity", 0) < 0.85:
        source = result.get("source", "")
        if source != "URL(Web)":
            review_reasons.append(f"标题相似度 {result.get('similarity', 0):.0%}")
    # needs_review 只保留“必须人工核查”的高风险信号。
    # 作者列表轻微差异、et al./others 省略、年份差异等会进入风险/建议，但不再直接计入人工复核。
    if result["author_check"] == "mismatch" and _first_author_is_mismatch(
        result.get("first_author_match")
    ):
        review_reasons.append(f"首作者不一致: {result['author_reason']}")
    if result["doi_check"] == "mismatch":
        review_reasons.append(result["doi_reason"])

    result["needs_review"] = "Yes" if review_reasons else "No"
    result["review_reasons"] = "；".join(review_reasons)
    return result



SEARCH_MODE_STRICT = "strict"
SEARCH_MODE_PARALLEL = "parallel"
DOI_CHECK_AUTO = "auto"
DOI_CHECK_OFF = "off"
DOI_STATUS_MATCHED = "matched"
DOI_STATUS_MISMATCH = "mismatch"
DOI_STATUS_UNRESOLVED = "unresolved"
DOI_STATUS_NO_METADATA = "no_metadata"
DOI_STATUS_NOT_PROVIDED = "not_provided"


def normalize_search_mode(value: str | None) -> str:
    value = (value or SEARCH_MODE_STRICT).strip().lower()
    if value not in {SEARCH_MODE_STRICT, SEARCH_MODE_PARALLEL}:
        return SEARCH_MODE_STRICT
    return value


def normalize_doi_check(value: str | None) -> str:
    value = (value or DOI_CHECK_AUTO).strip().lower()
    if value not in {DOI_CHECK_AUTO, DOI_CHECK_OFF}:
        return DOI_CHECK_AUTO
    return value


def _doi_status_label(status: str) -> str:
    return {
        DOI_STATUS_MATCHED: "matched",
        DOI_STATUS_MISMATCH: "mismatch",
        DOI_STATUS_UNRESOLVED: "unresolved",
        DOI_STATUS_NO_METADATA: "no metadata",
        DOI_STATUS_NOT_PROVIDED: "not provided",
    }.get(status or DOI_STATUS_NOT_PROVIDED, "not provided")


def _is_meaningful_input_title(title: str, doi: str = "") -> bool:
    clean_title = (title or "").strip()
    if len(clean_title) < 12:
        return False
    if clean_title.lower().startswith(("http://", "https://", "doi:", "doi.org/")):
        return False
    looks_like_doi = bool(re.fullmatch(r"10\.\d{4,9}/\S+", clean_title, flags=re.I))
    cleaned = clean_doi(clean_title) if looks_like_doi else ""
    if looks_like_doi and cleaned and (not doi or cleaned == clean_doi(doi)):
        # DOI-only / URL-only pasted input should not be treated as a title mismatch.
        return False
    return bool(re.search(r"[A-Za-z\u4e00-\u9fff]", clean_title))


def run_doi_exact_check(
    *,
    title: str,
    author: str,
    year: str,
    doi: str,
    threshold: float,
    email: str,
    doi_check: str = DOI_CHECK_AUTO,
) -> dict:
    """Independent DOI exact-check stage.

    This stage is intentionally separate from the user-configured search chain.
    It currently uses CrossRef DOI metadata as the metadata resolver, but exposes
    the result as "DOI exact check" rather than as a CrossRef source hit.
    """
    strategy = normalize_doi_check(doi_check)
    cleaned = clean_doi(doi)
    base = {
        "doi_check_status": DOI_STATUS_NOT_PROVIDED,
        "doi_check_strategy": strategy,
        "doi_normalized": cleaned,
        "doi_resolved_url": "",
        "doi_target_title": "",
        "doi_target_authors": "",
        "doi_target_year": "",
        "doi_target_doi": "",
        "doi_title_similarity": "",
        "doi_check_message": "No DOI provided; DOI exact check skipped.",
        "doi_metadata_source": "DOI exact check",
        "doi_metadata": None,
    }
    if strategy == DOI_CHECK_OFF:
        base["doi_check_message"] = "DOI exact check is disabled."
        return base
    if not cleaned:
        return base

    base["doi_check_message"] = "Checking DOI metadata."
    try:
        metadata = _sources.search_crossref_by_doi(cleaned, title, email)
    except Exception as exc:  # Defensive: source helpers should already catch.
        metadata = {"found": False, "reason": f"DOI metadata lookup failed: {type(exc).__name__}: {exc}"}

    if not _has_candidate_payload(metadata) or not metadata.get("matched_title"):
        reason = metadata.get("reason", "DOI metadata lookup returned no result") if isinstance(metadata, dict) else "DOI metadata lookup returned no result"
        lower_reason = str(reason).lower()
        status = DOI_STATUS_UNRESOLVED if any(
            token in lower_reason
            for token in ["failed", "failure", "timeout", "timed out", "connection", "network", "http", "request"]
        ) else DOI_STATUS_NO_METADATA
        base.update({
            "doi_check_status": status,
            "doi_resolved_url": f"https://doi.org/{cleaned}",
            "doi_target_doi": cleaned,
            "doi_check_message": f"DOI exact check {_doi_status_label(status)}: {reason}",
        })
        return base

    metadata = dict(metadata)
    target_title = metadata.get("matched_title", "")
    target_year = str(metadata.get("year", "") or "")
    target_doi = clean_doi(metadata.get("doi", "")) or cleaned
    target_authors = metadata.get("authors", "")
    resolved_url = metadata.get("url", "") or (f"https://doi.org/{target_doi}" if target_doi else f"https://doi.org/{cleaned}")

    mismatches: list[str] = []
    sim = ""
    if _is_meaningful_input_title(title, cleaned) and target_title:
        sim_value = title_similarity(title, target_title)
        sim = f"{sim_value:.4f}"
        if sim_value < threshold:
            mismatches.append(f"title mismatch (similarity {sim_value:.0%})")

    if author and metadata.get("author_list"):
        author_cmp = compare_author_lists(author, metadata.get("author_list") or [])
        if author_cmp.get("status") == "mismatch":
            mismatches.append(f"author mismatch: {author_cmp.get('reason', '')}")

    if year:
        year_cmp = compare_year(year, target_year)
        if year_cmp.get("status") == "mismatch":
            mismatches.append(f"year mismatch: {year_cmp.get('reason', '')}")

    status = DOI_STATUS_MISMATCH if mismatches else DOI_STATUS_MATCHED
    base.update({
        "doi_check_status": status,
        "doi_resolved_url": resolved_url,
        "doi_target_title": target_title,
        "doi_target_authors": target_authors,
        "doi_target_year": target_year,
        "doi_target_doi": target_doi,
        "doi_title_similarity": sim,
        "doi_check_message": (
            f"DOI exact check mismatch: {'; '.join(mismatches)}."
            if mismatches else "DOI exact check passed: DOI metadata has no explicit title/author/year conflict."
        ),
        "doi_metadata": metadata,
    })
    return base


def _source_order_text(enabled_sources: list[str], custom_rest_profiles: dict[str, dict] | None = None) -> str:
    if not enabled_sources:
        return "No database source enabled"
    return " -> ".join(_source_label(name, custom_rest_profiles) for name in enabled_sources)


def _format_actual_query_trace(doi_info: dict | None, source_trace: list[dict]) -> str:
    parts: list[str] = []
    if doi_info and doi_info.get("doi_check_status") != DOI_STATUS_NOT_PROVIDED:
        parts.append(
            "DOI exact check: "
            + _doi_status_label(str(doi_info.get("doi_check_status") or ""))
            + (f" - {doi_info.get('doi_target_title')}" if doi_info.get("doi_target_title") else "")
        )
    source_text = _format_source_trace(source_trace)
    if source_text:
        parts.append(source_text)
    return "; ".join(parts)


def _attach_flow_fields(
    result: dict,
    *,
    search_mode: str,
    doi_info: dict | None,
    enabled_sources: list[str],
    custom_profile_map: dict[str, dict] | None,
    source_trace: list[dict],
) -> dict:
    source_order = _source_order_text(enabled_sources, custom_profile_map)
    actual_trace = _format_actual_query_trace(doi_info, source_trace)
    result["search_mode"] = search_mode
    result["source_order"] = source_order
    result["source_order_keys"] = ",".join(enabled_sources)
    result["query_trace"] = actual_trace
    result["actual_query_trace"] = actual_trace
    result["adopted_source"] = result.get("source", "")
    # Keep the legacy field useful for the desktop detail dialog.
    result["source_trace"] = actual_trace or result.get("source_trace", "")

    info = doi_info or {}
    for key in [
        "doi_check_status",
        "doi_check_strategy",
        "doi_normalized",
        "doi_resolved_url",
        "doi_target_title",
        "doi_target_authors",
        "doi_target_year",
        "doi_target_doi",
        "doi_title_similarity",
        "doi_check_message",
        "doi_metadata_source",
    ]:
        result[key] = info.get(key, "")
    return result


def _is_high_confidence_candidate(candidate: dict, *, threshold: float) -> bool:
    if not candidate.get("found"):
        return False
    if _is_web_evidence_result(candidate):
        return False
    if candidate.get("source") == "URL(Web)":
        return False
    if (candidate.get("similarity", 0) or 0) < threshold:
        return False
    if candidate.get("doi_check") == "mismatch":
        return False
    if candidate.get("author_check") == "mismatch":
        return False
    if candidate.get("year_check") == "mismatch":
        return False
    return True


def _candidate_sort_key(item: dict) -> tuple[float, int, float]:
    return (
        float(item.get("arbitration_score", 0) or 0),
        -int(item.get("_source_order", 999)),
        _candidate_reliability(item),
    )


def _candidate_from_doi_info(doi_info: dict | None, *, title: str, author: str, year: str, threshold: float) -> dict | None:
    if not doi_info or doi_info.get("doi_check_status") not in {DOI_STATUS_MATCHED, DOI_STATUS_MISMATCH}:
        return None
    metadata = doi_info.get("doi_metadata")
    if not isinstance(metadata, dict):
        return None
    candidate = dict(metadata)
    candidate["source"] = "DOI exact check"
    candidate["_source_key"] = "doi-exact"
    candidate["_source_order"] = 998
    if doi_info.get("doi_check_status") == DOI_STATUS_MATCHED:
        candidate["found"] = True
        candidate["status"] = "found"
        candidate.setdefault("reason", doi_info.get("doi_check_message", ""))
        if not _is_meaningful_input_title(title, doi_info.get("doi_normalized", "")):
            candidate["similarity"] = 1.0
    else:
        candidate["found"] = False
        candidate["status"] = "not_found"
        candidate["reason"] = doi_info.get("doi_check_message", "Input DOI points to metadata that does not match this reference.")
    enriched = enrich_result(candidate, bib_author=author, bib_year=year, bib_doi=doi_info.get("doi_normalized", ""))
    enriched["arbitration_score"] = _arbitration_score(enriched, threshold=threshold)
    if doi_info.get("doi_check_status") == DOI_STATUS_MATCHED:
        enriched["arbitration_score"] += 18
    else:
        enriched["arbitration_score"] -= 80
    return enriched


def _no_source_result(source_label: str, *, author: str, year: str, doi: str) -> dict:
    result: dict = {"found": False, "similarity": 0.0, "reason": "No enabled source returned a reliable match", "source": source_label}
    return enrich_result(result, bib_author=author, bib_year=year, bib_doi=doi)


def _finalize_verified_result(
    *,
    selected: dict | None,
    candidates: list[dict],
    alternatives: list[dict],
    source_trace: list[dict],
    enabled_sources: list[str],
    custom_profile_map: dict[str, dict],
    threshold: float,
    title: str,
    author: str,
    year: str,
    doi: str,
    search_mode: str,
    doi_info: dict | None,
    use_url_verify: bool,
    url: str,
    db_best_is_found: bool,
    stopped_early: bool = False,
) -> dict:
    source_label = _source_order_text(enabled_sources, custom_profile_map)
    if selected is None:
        selected = _no_source_result(source_label, author=author, year=year, doi=doi)

    best = dict(selected)
    if best.get("source") == "DOI exact check" and (doi_info or {}).get("doi_check_status") == DOI_STATUS_MISMATCH:
        found = False
    else:
        found = bool(
            best.get("doi_exact_query")
            or (best.get("source", "").startswith("URL(") and best.get("found"))
            or best.get("similarity", 0) >= threshold
            or (best.get("source") == "DOI exact check" and best.get("found"))
        )
    best["found"] = found
    best["status"] = "found" if found else "not_found"

    best["candidate_count"] = len(candidates)
    best["alternative_candidates"] = "; ".join(
        _format_candidate_line(item) for item in alternatives[:5]
    )
    if search_mode == SEARCH_MODE_STRICT:
        if stopped_early:
            reason = "Strict mode: queried sources one by one and stopped after a high-confidence hit."
        else:
            reason = "Strict mode: queried sources one by one; no earlier source met the high-confidence stop rule."
    else:
        reason = "Parallel mode: queried multiple sources concurrently; order is used only as a tie-breaker."
    best["arbitration_reason"] = (
        f"{reason} Search chain: {source_label}; "
        f"{len(candidates)} search-chain candidate(s). Adopted {best.get('source', 'Unknown')}: "
        f"{_format_candidate_line(best)}."
    )
    if search_mode == SEARCH_MODE_PARALLEL:
        best["arbitration_reason"] += " Parallel arbitration is not strict ordered querying."
    if use_url_verify and url and not db_best_is_found:
        best["arbitration_reason"] += " URL verification was added because database sources did not produce a reliable hit."

    if not found:
        best["reason"] = best.get("reason") or (
            f"{source_label} did not return a reliable match above threshold "
            f"(best title similarity {best.get('similarity', 0):.0%})"
        )
    elif not best.get("reason"):
        best["reason"] = best["arbitration_reason"]

    conflict = _candidate_conflict(best, alternatives, threshold=threshold)
    best["candidate_conflict"] = "Yes" if conflict else "No"
    if conflict:
        existing = best.get("review_reasons", "")
        best["needs_review"] = "Yes"
        best["review_reasons"] = "; ".join([v for v in [existing, conflict] if v])

    return _attach_flow_fields(
        best,
        search_mode=search_mode,
        doi_info=doi_info,
        enabled_sources=enabled_sources,
        custom_profile_map=custom_profile_map,
        source_trace=source_trace,
    )


def verify_entry(title: str, author: str, year: str, doi: str, threshold: float,
                 email: str, use_openalex: bool, use_dblp: bool,
                 use_semantic_scholar: bool = True, use_arxiv: bool = True,
                 use_pubmed: bool = True, use_crossref: bool = True,
                 use_springer: bool = False, use_ieee: bool = False,
                 use_core: bool = False, springer_api_key: str = "",
                 ieee_api_key: str = "", core_api_key: str = "", url: str = "",
                 use_url_verify: bool = True,
                 source_order: list[str] | None = None,
                 custom_rest_profiles: list[dict] | None = None,
                 search_mode: str = SEARCH_MODE_STRICT,
                 doi_check: str = DOI_CHECK_AUTO) -> dict:
    """Verify one entry with DOI pre-check plus strict/parallel search-chain modes."""
    search_mode = normalize_search_mode(search_mode)
    doi_check = normalize_doi_check(doi_check)
    custom_profile_map = _custom_rest.profile_map(custom_rest_profiles)
    order = build_source_order(source_order, list(custom_profile_map.keys()))
    enabled_kwargs = dict(
        use_openalex=use_openalex, use_dblp=use_dblp,
        use_semantic_scholar=use_semantic_scholar, use_arxiv=use_arxiv,
        use_pubmed=use_pubmed, use_crossref=use_crossref,
        use_springer=use_springer, use_ieee=use_ieee, use_core=use_core,
        springer_api_key=springer_api_key, ieee_api_key=ieee_api_key,
        core_api_key=core_api_key,
        custom_rest_profiles=custom_profile_map,
    )
    enabled_sources = [
        source_name for source_name in order
        if _source_enabled(source_name, **enabled_kwargs)
    ]
    query_sources = enabled_sources if _is_meaningful_input_title(title, doi) else []
    order_index = {source_name: index for index, source_name in enumerate(order)}

    doi_info = run_doi_exact_check(
        title=title,
        author=author,
        year=year,
        doi=doi,
        threshold=threshold,
        email=email,
        doi_check=doi_check,
    )

    def run_source(source_name: str) -> list[dict]:
        """Run one search-chain source. DOI exact lookup is not done here."""
        r = _search_source(
            source_name, title, author, year, threshold, email,
            springer_api_key=springer_api_key,
            ieee_api_key=ieee_api_key,
            core_api_key=core_api_key,
            custom_rest_profiles=custom_profile_map,
        )
        return [dict(r)] if _has_candidate_payload(r) else []

    def enrich_rows(source_name: str, rows: list[dict]) -> list[dict]:
        enriched_rows: list[dict] = []
        label = _source_label(source_name, custom_profile_map)
        for raw in rows:
            candidate = dict(raw)
            candidate.setdefault("source", label)
            candidate["_source_key"] = source_name
            candidate["_source_order"] = order_index.get(source_name, 999)
            enriched = enrich_result(candidate, bib_author=author, bib_year=year, bib_doi=doi)
            enriched["arbitration_score"] = _arbitration_score(enriched, threshold=threshold)
            enriched_rows.append(enriched)
        return enriched_rows

    if search_mode == SEARCH_MODE_PARALLEL:
        return _verify_entry_parallel_mode(
            title=title,
            author=author,
            year=year,
            doi=doi,
            threshold=threshold,
            email=email,
            url=url,
            use_url_verify=use_url_verify,
            enabled_sources=query_sources,
            order_index=order_index,
            custom_profile_map=custom_profile_map,
            run_source=run_source,
            enrich_rows=enrich_rows,
            doi_info=doi_info,
        )

    return _verify_entry_strict_mode(
        title=title,
        author=author,
        year=year,
        doi=doi,
        threshold=threshold,
        email=email,
        url=url,
        use_url_verify=use_url_verify,
        enabled_sources=query_sources,
        order_index=order_index,
        custom_profile_map=custom_profile_map,
        run_source=run_source,
        enrich_rows=enrich_rows,
        doi_info=doi_info,
    )


def _verify_entry_parallel_mode(
    *,
    title: str,
    author: str,
    year: str,
    doi: str,
    threshold: float,
    email: str,
    url: str,
    use_url_verify: bool,
    enabled_sources: list[str],
    order_index: dict[str, int],
    custom_profile_map: dict[str, dict],
    run_source,
    enrich_rows,
    doi_info: dict,
) -> dict:
    candidates: list[dict] = []
    source_trace: list[dict] = []

    if enabled_sources:
        max_workers = min(4, len(enabled_sources))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(run_source, source_name): source_name for source_name in enabled_sources}
            for future in as_completed(futures):
                source_name = futures[future]
                label = _source_label(source_name, custom_profile_map)
                try:
                    rows = future.result()
                except Exception as exc:
                    source_trace.append({
                        "source": label,
                        "status": "error",
                        "order": order_index.get(source_name, 999),
                        "reason": f"{type(exc).__name__}: {exc}",
                    })
                    continue
                if not rows:
                    source_trace.append({
                        "source": label,
                        "status": "no_candidate",
                        "order": order_index.get(source_name, 999),
                    })
                    continue
                best_for_source = max(rows, key=lambda item: item.get("similarity", 0) or 0)
                source_trace.append({
                    "source": best_for_source.get("source") or label,
                    "status": "found" if best_for_source.get("found") else "candidate",
                    "order": order_index.get(source_name, 999),
                    "similarity": best_for_source.get("similarity", 0) or 0,
                    "reason": best_for_source.get("reason", ""),
                })
                candidates.extend(enrich_rows(source_name, rows))

    db_best = max(candidates, key=_candidate_sort_key) if candidates else None
    db_best_is_found = bool(db_best and (db_best.get("similarity", 0) >= threshold))

    if use_url_verify and url and not db_best_is_found:
        web = _url_verify.verify_url_resource(url, title, author, year, email)
        if _has_candidate_payload(web):
            web = dict(web)
            web.setdefault("source", "URL(Web)")
            web["_source_key"] = "url"
            web["_source_order"] = len(enabled_sources) + 1
            enriched = enrich_result(web, bib_author=author, bib_year=year, bib_doi=doi)
            enriched["arbitration_score"] = _arbitration_score(enriched, threshold=threshold)
            candidates.append(enriched)
            source_trace.append({
                "source": enriched.get("source", "URL(Web)"),
                "status": "found" if enriched.get("found") else "candidate",
                "order": len(enabled_sources) + 1,
                "similarity": enriched.get("similarity", 0) or 0,
                "reason": enriched.get("reason", ""),
            })

    doi_candidate = _candidate_from_doi_info(doi_info, title=title, author=author, year=year, threshold=threshold)
    all_candidates = list(candidates)
    if doi_candidate and doi_info.get("doi_check_status") == DOI_STATUS_MATCHED:
        all_candidates.append(doi_candidate)

    if all_candidates:
        sorted_candidates = sorted(all_candidates, key=_candidate_sort_key, reverse=True)
        best = dict(sorted_candidates[0])
        alternatives = [dict(item) for item in sorted_candidates[1:]]
    elif doi_candidate:
        best = dict(doi_candidate)
        alternatives = []
    else:
        best = None
        alternatives = []

    return _finalize_verified_result(
        selected=best,
        candidates=candidates,
        alternatives=alternatives,
        source_trace=source_trace,
        enabled_sources=enabled_sources,
        custom_profile_map=custom_profile_map,
        threshold=threshold,
        title=title,
        author=author,
        year=year,
        doi=doi,
        search_mode=SEARCH_MODE_PARALLEL,
        doi_info=doi_info,
        use_url_verify=use_url_verify,
        url=url,
        db_best_is_found=db_best_is_found,
    )


def _verify_entry_strict_mode(
    *,
    title: str,
    author: str,
    year: str,
    doi: str,
    threshold: float,
    email: str,
    url: str,
    use_url_verify: bool,
    enabled_sources: list[str],
    order_index: dict[str, int],
    custom_profile_map: dict[str, dict],
    run_source,
    enrich_rows,
    doi_info: dict,
) -> dict:
    candidates: list[dict] = []
    source_trace: list[dict] = []
    selected: dict | None = None
    stopped_early = False

    for source_name in enabled_sources:
        label = _source_label(source_name, custom_profile_map)
        try:
            rows = run_source(source_name)
        except Exception as exc:
            source_trace.append({
                "source": label,
                "status": "error",
                "order": order_index.get(source_name, 999),
                "reason": f"{type(exc).__name__}: {exc}",
            })
            continue
        if not rows:
            source_trace.append({
                "source": label,
                "status": "no_candidate",
                "order": order_index.get(source_name, 999),
            })
            continue

        enriched_rows = enrich_rows(source_name, rows)
        candidates.extend(enriched_rows)
        best_for_source = max(enriched_rows, key=_candidate_sort_key)
        source_trace.append({
            "source": best_for_source.get("source") or label,
            "status": "found" if best_for_source.get("found") else "candidate",
            "order": order_index.get(source_name, 999),
            "similarity": best_for_source.get("similarity", 0) or 0,
            "reason": best_for_source.get("reason", ""),
        })
        if (
            doi_info.get("doi_check_status") != DOI_STATUS_MISMATCH
            and _is_high_confidence_candidate(best_for_source, threshold=threshold)
        ):
            selected = best_for_source
            stopped_early = True
            break

    db_best = max(candidates, key=_candidate_sort_key) if candidates else None
    db_best_is_found = bool(db_best and (db_best.get("similarity", 0) >= threshold))

    if selected is None and use_url_verify and url and not db_best_is_found:
        web = _url_verify.verify_url_resource(url, title, author, year, email)
        if _has_candidate_payload(web):
            web = dict(web)
            web.setdefault("source", "URL(Web)")
            web["_source_key"] = "url"
            web["_source_order"] = len(enabled_sources) + 1
            enriched = enrich_result(web, bib_author=author, bib_year=year, bib_doi=doi)
            enriched["arbitration_score"] = _arbitration_score(enriched, threshold=threshold)
            candidates.append(enriched)
            source_trace.append({
                "source": enriched.get("source", "URL(Web)"),
                "status": "found" if enriched.get("found") else "candidate",
                "order": len(enabled_sources) + 1,
                "similarity": enriched.get("similarity", 0) or 0,
                "reason": enriched.get("reason", ""),
            })
            if (
                doi_info.get("doi_check_status") != DOI_STATUS_MISMATCH
                and _is_high_confidence_candidate(enriched, threshold=threshold)
            ):
                selected = enriched

    doi_candidate = _candidate_from_doi_info(doi_info, title=title, author=author, year=year, threshold=threshold)
    all_candidates = list(candidates)
    if doi_candidate and doi_info.get("doi_check_status") == DOI_STATUS_MATCHED:
        all_candidates.append(doi_candidate)

    if selected is None:
        if all_candidates:
            selected = max(all_candidates, key=_candidate_sort_key)
        elif doi_candidate:
            selected = doi_candidate

    alternatives = []
    if selected is not None:
        alternatives = sorted(
            [dict(item) for item in all_candidates if item is not selected and item.get("source") != selected.get("source")],
            key=_candidate_sort_key,
            reverse=True,
        )

    return _finalize_verified_result(
        selected=selected,
        candidates=candidates,
        alternatives=alternatives,
        source_trace=source_trace,
        enabled_sources=enabled_sources,
        custom_profile_map=custom_profile_map,
        threshold=threshold,
        title=title,
        author=author,
        year=year,
        doi=doi,
        search_mode=SEARCH_MODE_STRICT,
        doi_info=doi_info,
        use_url_verify=use_url_verify,
        url=url,
        db_best_is_found=db_best_is_found,
        stopped_early=stopped_early,
    )

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


def _clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def risk_label(level: str) -> str:
    return {
        "high": "高风险",
        "medium": "中风险",
        "low": "低风险",
        "none": "无明显风险",
    }.get(level or "none", "无明显风险")


def risk_color(level: str) -> str:
    return {
        "high": "#b42318",
        "medium": "#b54708",
        "low": "#a15c07",
        "none": "#276b37",
    }.get(level or "none", "#276b37")


def risk_badge_markdown(level: str) -> str:
    label = risk_label(level)
    color = risk_color(level)
    return f'<span style="color:{color};font-weight:700">{label}</span>'


CONFIDENCE_EXPLANATION = (
    "置信度是 RefChecker 对“当前匹配结果有多可靠”的 0-100 综合评分，"
    "不是文献真实存在的概率。它会综合 DOI 是否一致、标题相似度、作者一致性、年份一致性、"
    "来源类型以及是否仅为网页可访问等信号；分数越高，表示当前匹配越可信。"
)

CONFIDENCE_SCALE = (
    "建议解读：90-100 通常可信；70-89 建议按需抽查；40-69 建议重点抽查；"
    "低于 40 或高风险条目应优先人工检索 DOI、出版社页面或论文原文。"
)


def _as_text(value) -> str:
    return str(value or "").strip()


def _evidence_source_label(result: dict) -> str:
    return _as_text(result.get("source")) or "启用的数据源"


def build_evidence_basis(result: dict) -> str:
    """Summarize the database/source evidence used by repair suggestions."""
    source = _evidence_source_label(result)
    evidence: list[str] = []
    if _is_web_evidence_result(result):
        evidence.append(
            f"{source} 仅提供网页搜索证据，不提供 CrossRef/OpenAlex 类型的结构化文献元数据"
        )
        if result.get("web_evidence_note"):
            evidence.append(_as_text(result.get("web_evidence_note")))
        if result.get("web_evidence_links"):
            evidence.append(f"可点击网页候选：{result.get('web_evidence_links')}")
    if result.get("status") == "not_found" or not result.get("found", True):
        evidence.append(
            f"{source} 未返回达到阈值的可靠匹配"
            + (f"（最接近标题相似度 {result.get('similarity', 0):.0%}）" if result.get("similarity") else "")
        )
    if result.get("matched_title"):
        evidence.append(f"{source} 匹配标题：{truncate(result.get('matched_title', ''), 120)}")
    if result.get("matched_doi"):
        evidence.append(f"{source} 返回 DOI：{result.get('matched_doi')}")
    elif result.get("doi"):
        evidence.append(f"{source} 返回 DOI：{result.get('doi')}")
    if result.get("matched_year"):
        evidence.append(f"{source} 返回年份：{result.get('matched_year')}")
    elif result.get("year"):
        evidence.append(f"{source} 返回年份：{result.get('year')}")
    if result.get("matched_authors"):
        evidence.append(f"{source} 返回作者：{truncate(result.get('matched_authors', ''), 120)}")
    elif result.get("authors"):
        evidence.append(f"{source} 返回作者：{truncate(result.get('authors', ''), 120)}")
    if result.get("bib_doi"):
        evidence.append(f"输入记录 DOI：{result.get('bib_doi')}")
    if result.get("bib_year"):
        evidence.append(f"输入记录年份：{result.get('bib_year')}")
    if result.get("author_reason"):
        evidence.append(f"作者核验：{result.get('author_reason')}")
    if result.get("year_reason"):
        evidence.append(f"年份核验：{result.get('year_reason')}")
    if result.get("doi_reason"):
        evidence.append(f"DOI 核验：{result.get('doi_reason')}")
    if result.get("doi_check_status") and result.get("doi_check_status") != DOI_STATUS_NOT_PROVIDED:
        evidence.append(f"DOI 精确核验：{result.get('doi_check_status')}；{result.get('doi_check_message', '')}")
        if result.get("doi_target_title"):
            evidence.append(f"DOI 指向标题：{truncate(result.get('doi_target_title', ''), 120)}")
        if result.get("doi_resolved_url"):
            evidence.append(f"DOI 解析地址：{result.get('doi_resolved_url')}")
    if result.get("actual_query_trace"):
        evidence.append(f"实际查询路径：{result.get('actual_query_trace')}")
    if result.get("arbitration_reason"):
        evidence.append(f"多来源仲裁：{result.get('arbitration_reason')}")
    if not evidence and result.get("reason"):
        evidence.append(_as_text(result.get("reason")))
    return "；".join(dict.fromkeys(evidence))


def risk_explanation(result: dict) -> str:
    """Generate a deterministic, evidence-based risk explanation."""
    level = risk_label(result.get("risk_level", "none"))
    source = _evidence_source_label(result)
    reasons: list[str] = []
    status = result.get("status", "")
    similarity = result.get("similarity", 0) or 0

    if status == "skipped":
        reasons.append("输入条目缺少可解析标题，无法进入数据库核验流程")
    elif status == "not_found" or not result.get("found", True):
        reasons.append(f"在 {source} 中未找到达到阈值的可靠标题匹配")
        if result.get("matched_title"):
            reasons.append(f"最接近结果标题相似度为 {similarity:.0%}")
    else:
        if _is_web_evidence_result(result):
            reasons.append(
                f"{source} 发现了网页搜索候选，但该来源不返回结构化作者、年份、DOI 等文献元数据"
            )
            reasons.append("该结果只能作为可打开核对的网页证据，不能单独证明参考文献真实或元数据正确")
        else:
            reasons.append(f"数据库核验来源为 {source}")
        if source != "URL(Web)" and similarity:
            reasons.append(f"标题相似度 {similarity:.0%}")

    if result.get("doi_check") == "mismatch":
        reasons.append(
            f"输入 DOI（{result.get('bib_doi') or '空'}）与数据源 DOI（{result.get('matched_doi') or '空'}）不一致"
        )
    elif result.get("doi_check") == "missing_in_bib" and result.get("matched_doi"):
        reasons.append(f"输入记录缺少 DOI，数据源提供候选 DOI {result.get('matched_doi')}")

    doi_exact_status = result.get("doi_check_status")
    if doi_exact_status == DOI_STATUS_MATCHED:
        reasons.append("DOI 精确核验通过，DOI 元数据与输入记录未发现明确冲突")
    elif doi_exact_status == DOI_STATUS_MISMATCH:
        target = result.get("doi_target_title") or "另一条 DOI 元数据"
        reasons.append(f"DOI 精确核验不匹配：输入 DOI 指向《{truncate(target, 100)}》")
    elif doi_exact_status in {DOI_STATUS_UNRESOLVED, DOI_STATUS_NO_METADATA}:
        reasons.append(f"DOI 精确核验未通过：{result.get('doi_check_message', doi_exact_status)}")

    if result.get("author_check") == "mismatch":
        reasons.append("作者列表与数据源不一致")
        if _first_author_is_mismatch(result.get("first_author_match")):
            reasons.append("首作者不一致")
    elif result.get("author_check") == "partial":
        reasons.append("作者字段使用 et al./others 或缩写，需抽查完整作者列表")

    if result.get("year_check") == "mismatch":
        reasons.append(
            f"输入年份 {result.get('bib_year') or '空'} 与数据源年份 {result.get('matched_year') or '空'} 不一致"
        )

    if result.get("source") == "URL(Web)":
        reasons.append("仅完成网页可访问性核验，页面作者、发布日期和版本仍需人工确认")
    if result.get("actual_query_trace"):
        reasons.append(f"实际查询路径：{result.get('actual_query_trace')}")
    if result.get("candidate_conflict") == "Yes":
        reasons.append(result.get("review_reasons") or "多个高相似度候选存在元数据冲突")
    if result.get("arbitration_reason"):
        reasons.append(result.get("arbitration_reason"))

    if not reasons:
        reasons.append("未发现明显标题、作者、年份或 DOI 冲突")
    return f"{level}：{'；'.join(dict.fromkeys(reasons))}。该解释基于数据库核验结果，不是最终学术裁决。"


def fix_suggestion(result: dict) -> tuple[str, str]:
    """Return (suggestion, evidence basis) for repair workflows."""
    source = _evidence_source_label(result)
    basis = build_evidence_basis(result)
    suggestions: list[str] = []
    status = result.get("status", "")
    similarity = result.get("similarity", 0) or 0

    if status == "skipped":
        suggestions.append("先补全文献标题、作者、年份或 DOI，再重新核验。")
    elif status == "not_found" or not result.get("found", True):
        suggestions.append("不要补造该文献；请用标题、作者和 DOI 到出版社页面、CrossRef、OpenAlex 或学科数据库人工检索。")
        if result.get("matched_title"):
            suggestions.append("若最接近结果来自可信来源，可人工比对标题、作者、年份和 DOI 后再决定是否替换。")

    if _is_web_evidence_result(result):
        suggestions.append(
            f"{source} 仅返回网页搜索结果；请打开候选链接，优先确认出版社/DOI/论文原文页面中的标题、作者、年份和 DOI。"
        )

    if result.get("doi_check") == "mismatch":
        suggestions.append(
            f"优先核对 DOI：把输入 DOI {result.get('bib_doi') or '空'} 与 {source} 返回 DOI {result.get('matched_doi') or '空'} 逐项比对。"
        )
    elif result.get("doi_check") == "missing_in_bib" and result.get("matched_doi"):
        suggestions.append(f"可将 {source} 返回的 DOI {result.get('matched_doi')} 作为候选补充，但应先打开 DOI/出版社页面确认。")

    doi_exact_status = result.get("doi_check_status")
    if doi_exact_status == DOI_STATUS_MISMATCH:
        suggestions.append("输入 DOI 可能指向另一篇论文；请优先打开 DOI 页面核对标题、作者和年份，不要直接沿用该 DOI。")
    elif doi_exact_status in {DOI_STATUS_UNRESOLVED, DOI_STATUS_NO_METADATA}:
        suggestions.append("DOI 暂时无法精确核验；请手动打开 doi.org 或出版社页面确认 DOI 是否有效。")

    if result.get("year_check") == "mismatch":
        suggestions.append(
            f"核对发表年份：当前记录为 {result.get('bib_year') or '空'}，{source} 返回为 {result.get('matched_year') or '空'}。"
        )

    if result.get("author_check") == "mismatch":
        if _first_author_is_mismatch(result.get("first_author_match")):
            suggestions.append("优先核对首作者，避免将相近标题的另一篇文献误当作目标文献。")
        else:
            suggestions.append("核对作者列表、顺序、缩写和 et al./others 省略写法。")
    elif result.get("author_check") == "partial":
        suggestions.append("抽查完整作者列表，确认 et al./others 省略没有掩盖作者缺失或顺序错误。")

    if source != "URL(Web)" and 0 < similarity < 0.90:
        suggestions.append("标题相似度偏低，建议人工确认副标题、版本、会议/期刊记录是否一致。")
    elif source == "URL(Web)":
        suggestions.append("仅网页可访问不等于引用正确；请人工确认页面标题、作者、日期和版本。")
    if result.get("candidate_conflict") == "Yes":
        suggestions.append("多来源候选存在冲突，请以 DOI 页面、出版社页面或论文原文为准进行人工裁决。")

    if not suggestions:
        suggestions.append("无需立即修复；如用于投稿或学位论文，建议对关键引用抽查 DOI 页面和论文原文。")
    if not basis:
        basis = "依据：当前条目的数据库核验字段；缺失字段不会由程序补造。"
    return " ".join(dict.fromkeys(suggestions)), basis


def _authors_from_result(result: dict) -> list[dict]:
    raw_list = result.get("author_list")
    if isinstance(raw_list, list) and raw_list:
        authors = []
        for item in raw_list:
            if isinstance(item, dict):
                if item.get("family") or item.get("given"):
                    authors.append(item)
                elif item.get("display") or item.get("raw"):
                    authors.append(parse_author_name(item.get("display") or item.get("raw")))
        if authors:
            return authors

    for field in ("matched_authors", "authors", "bib_authors"):
        text = _as_text(result.get(field))
        if not text:
            continue
        parts = [p.strip() for p in re.split(r";|\band\b", text) if p.strip()]
        authors = [parse_author_name(part) for part in parts[:20]]
        authors = [a for a in authors if a.get("family") or a.get("display")]
        if authors:
            return authors
    return []


def _apa_author(author: dict) -> str:
    family = _as_text(author.get("family")) or _as_text(author.get("display"))
    given = _as_text(author.get("given"))
    initials = "".join(f"{token[0].upper()}." for token in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", given))
    return f"{family}, {initials}".strip().rstrip(",")


def _apa_author_list(authors: list[dict]) -> str:
    if not authors:
        return ""
    formatted = [_apa_author(a) for a in authors if _apa_author(a)]
    if len(formatted) <= 1:
        return formatted[0] if formatted else ""
    if len(formatted) == 2:
        return f"{formatted[0]}, & {formatted[1]}"
    return f"{', '.join(formatted[:-1])}, & {formatted[-1]}"


def _bibtex_author(author: dict) -> str:
    family = _as_text(author.get("family")) or _as_text(author.get("display"))
    given = _as_text(author.get("given"))
    return f"{family}, {given}".strip().rstrip(",")


def _citation_key(result: dict, authors: list[dict], year: str) -> str:
    base_author = authors[0].get("family") if authors else result.get("key", "ref")
    raw = f"{base_author}{year or result.get('key', '')}"
    key = re.sub(r"[^A-Za-z0-9_:-]+", "", raw)
    return key or re.sub(r"[^A-Za-z0-9_:-]+", "", _as_text(result.get("key"))) or "ref"


def _bibtex_entry_type(result: dict) -> str:
    typ = _as_text(result.get("type")).lower()
    venue = _as_text(result.get("venue")).lower()
    if "proceed" in typ or "conference" in typ or "conference" in venue:
        return "inproceedings"
    if "book" in typ:
        return "book"
    if "web" in typ or result.get("source") == "URL(Web)":
        return "misc"
    return "article"


def standard_citations(result: dict) -> dict:
    """Build deterministic citation formats from matched metadata only."""
    if result.get("status") == "skipped" or result.get("status") == "not_found" or not result.get("found", True):
        return {
            "available": False,
            "basis": "未找到可靠数据库匹配，RefChecker 不会生成或补造规范引用。",
            "apa": "",
            "bibtex": "",
            "gbt7714": "",
        }
    if _is_web_evidence_result(result):
        return {
            "available": False,
            "basis": "仅有网页搜索证据，缺少结构化文献元数据；RefChecker 不会据此生成或补造规范引用。",
            "apa": "",
            "bibtex": "",
            "gbt7714": "",
        }

    source = _evidence_source_label(result)
    title = _as_text(result.get("matched_title")) or _as_text(result.get("title"))
    year = _as_text(result.get("matched_year")) or _as_text(result.get("year")) or _as_text(result.get("bib_year"))
    doi = _as_text(result.get("matched_doi")) or _as_text(result.get("doi"))
    url = _as_text(result.get("url"))
    venue = _as_text(result.get("venue"))
    authors = _authors_from_result(result)
    author_apa = _apa_author_list(authors)
    author_bibtex = " and ".join(_bibtex_author(a) for a in authors if _bibtex_author(a))
    key = _citation_key(result, authors, year)

    doi_url = f"https://doi.org/{doi}" if doi else url
    apa_parts = []
    if author_apa:
        apa_parts.append(author_apa)
    if year:
        apa_parts.append(f"({year}).")
    if title:
        apa_parts.append(f"{title}.")
    if venue:
        apa_parts.append(f"{venue}.")
    if doi_url:
        apa_parts.append(doi_url)
    apa = " ".join(apa_parts).strip()

    entry_type = _bibtex_entry_type(result)
    fields = []
    if title:
        fields.append(("title", title))
    if author_bibtex:
        fields.append(("author", author_bibtex))
    if year:
        fields.append(("year", year))
    if venue:
        fields.append(("journal" if entry_type == "article" else "booktitle", venue))
    if doi:
        fields.append(("doi", doi))
    if url:
        fields.append(("url", url))
    bibtex_lines = [f"@{entry_type}{{{key},"]
    for index, (name, value) in enumerate(fields):
        comma = "," if index < len(fields) - 1 else ""
        bibtex_lines.append(f"  {name} = {{{value}}}{comma}")
    bibtex_lines.append("}")
    bibtex = "\n".join(bibtex_lines)

    gbt_authors = ", ".join(
        " ".join(part for part in [_as_text(a.get("family")).upper(), _as_text(a.get("given"))] if part)
        for a in authors
    )
    gbt_parts = []
    if gbt_authors:
        gbt_parts.append(gbt_authors + ".")
    if title:
        gbt_parts.append(f"{title}.")
    if venue or year:
        gbt_parts.append(", ".join(part for part in [venue, year] if part) + ".")
    if doi:
        gbt_parts.append(f"DOI: {doi}.")
    elif url:
        gbt_parts.append(url)
    gbt7714 = " ".join(gbt_parts).strip()

    basis = (
        f"仅使用 {source} 返回的标题、作者、年份、来源、DOI/URL 等字段生成；"
        "缺失字段保持缺失，不由程序补造。"
    )
    return {
        "available": bool(title or doi or url),
        "basis": basis,
        "apa": apa,
        "bibtex": bibtex,
        "gbt7714": gbt7714,
    }


def _first_author_is_mismatch(value) -> bool:
    if isinstance(value, bool):
        return not value
    return str(value).lower() in {"no", "false", "0"}


def _append_action(actions: list[str], action: str) -> None:
    if action and action not in actions:
        actions.append(action)


def confidence_score(result: dict) -> int:
    """Estimate how reliable the selected match is for product-facing triage."""
    status = result.get("status", "")
    source = result.get("source", "")
    similarity = result.get("similarity", 0) or 0

    if status == "skipped":
        return 0
    if status == "not_found" or not result.get("found", True):
        return _clamp_score(8 + similarity * 40)

    if source == "URL(Web)":
        score = 52
    elif source.startswith("URL("):
        score = 62
    elif result.get("doi_check") == "exact" or (
        source == "CrossRef(DOI)" and result.get("doi_check") != "mismatch"
    ):
        score = 78
    else:
        score = 58

    score += similarity * 22
    if similarity >= 0.98:
        score += 6
    elif similarity < 0.85 and source != "URL(Web)":
        score -= 18

    author_check = result.get("author_check")
    if author_check == "exact":
        score += 6
    elif author_check == "partial":
        score -= 4
    elif author_check == "mismatch":
        score -= 16
        if _first_author_is_mismatch(result.get("first_author_match")):
            score -= 8
    elif author_check == "unknown":
        score -= 2

    year_check = result.get("year_check")
    if year_check == "exact":
        score += 5
    elif year_check == "mismatch":
        score -= 12
    elif year_check == "unknown":
        score -= 2

    doi_check = result.get("doi_check")
    if doi_check == "exact":
        score += 6
    elif doi_check == "mismatch":
        score -= 34
    elif doi_check == "missing_in_bib":
        score -= 3

    doi_exact_status = result.get("doi_check_status")
    if doi_exact_status == DOI_STATUS_MATCHED:
        score += 5
    elif doi_exact_status == DOI_STATUS_MISMATCH:
        score -= 42
    elif doi_exact_status in {DOI_STATUS_UNRESOLVED, DOI_STATUS_NO_METADATA}:
        score -= 8

    if result.get("candidate_conflict") == "Yes":
        score -= 18

    if result.get("needs_review") == "No":
        score += 3

    if _is_web_evidence_result(result):
        # Web search results are useful pages to open, but not metadata verification.
        score = min(score, 64)

    return _clamp_score(score)


def assess_risk_level(result: dict) -> str:
    """Classify the entry into a product-friendly review priority."""
    status = result.get("status", "")
    source = result.get("source", "")
    similarity = result.get("similarity", 0) or 0
    author_check = result.get("author_check")
    year_check = result.get("year_check")
    doi_check = result.get("doi_check")
    doi_exact_status = result.get("doi_check_status")

    if status == "skipped":
        return "high"
    if status == "not_found" or not result.get("found", True):
        return "high"
    if doi_exact_status == DOI_STATUS_MISMATCH:
        return "high"
    if doi_check == "mismatch":
        return "high"
    if result.get("candidate_conflict") == "Yes":
        return "high"
    if source != "URL(Web)" and similarity < 0.85:
        return "high"
    if author_check == "mismatch" and _first_author_is_mismatch(result.get("first_author_match")):
        return "high"

    if author_check == "mismatch" or year_check == "mismatch":
        return "medium"
    if doi_exact_status in {DOI_STATUS_UNRESOLVED, DOI_STATUS_NO_METADATA}:
        return "medium"
    if source != "URL(Web)" and similarity < 0.90:
        return "medium"

    if _is_web_evidence_result(result):
        if not result.get("matched_doi") and result.get("author_check") != "exact" and result.get("year_check") != "exact":
            return "medium"
        return "low"

    if author_check == "partial":
        return "low"
    if source != "URL(Web)" and similarity < 0.98:
        return "low"
    if doi_check == "missing_in_bib":
        return "low"
    if source == "URL(Web)":
        return "low"

    return "none"


def suggested_action(result: dict) -> str:
    """Generate concise next-step guidance for the report, CSV, and desktop UI."""
    actions: list[str] = []
    status = result.get("status", "")
    source = result.get("source", "")
    similarity = result.get("similarity", 0) or 0

    if status == "skipped":
        _append_action(actions, "补全文献标题后重新核验。")
    if status == "not_found" or not result.get("found", True):
        _append_action(actions, "人工检索标题/DOI，排查疑似虚构引用；若为模型、代码或硬件资料，请补充可访问 URL。")

    if source != "URL(Web)" and 0 < similarity < 0.90:
        _append_action(actions, "核对标题、大小写、副标题和 LaTeX 标记，避免匹配到相近但不同的文献。")
    elif source != "URL(Web)" and 0.90 <= similarity < 0.98:
        _append_action(actions, "标题存在轻微差异，建议确认是否为同一版本或同一出版记录。")

    if result.get("author_check") == "mismatch":
        if _first_author_is_mismatch(result.get("first_author_match")):
            _append_action(actions, "优先核对首作者，确认是否匹配到了错误文献。")
        else:
            _append_action(actions, "核对作者列表、顺序和省略写法。")
    elif result.get("author_check") == "partial":
        _append_action(actions, "作者使用 others/et al. 或缩写，建议抽查完整作者列表。")

    if result.get("year_check") == "mismatch":
        _append_action(
            actions,
            f"核对年份：当前 {result.get('bib_year', '') or '空'}，数据源 {result.get('matched_year', '') or '空'}。",
        )

    if result.get("doi_check") == "mismatch":
        _append_action(actions, "优先核对 DOI，避免引用到错误文献。")
    elif result.get("doi_check") == "missing_in_bib" and result.get("matched_doi"):
        _append_action(actions, f"建议补充 DOI：{result.get('matched_doi')}")

    doi_exact_status = result.get("doi_check_status")
    if doi_exact_status == DOI_STATUS_MISMATCH:
        _append_action(actions, "DOI 精确核验显示该 DOI 指向另一篇论文，请先替换或删除错误 DOI。")
    elif doi_exact_status in {DOI_STATUS_UNRESOLVED, DOI_STATUS_NO_METADATA}:
        _append_action(actions, "DOI 无法解析或缺少元数据，请人工打开 DOI/出版社页面确认。")

    if result.get("candidate_conflict") == "Yes":
        _append_action(actions, "多来源候选存在冲突，请打开 DOI/出版社页面或论文原文人工裁决。")

    if source == "URL(Web)":
        _append_action(actions, "仅验证网页可访问；建议人工确认页面标题、作者和发布日期。")

    if _is_web_evidence_result(result):
        _append_action(actions, "仅发现网页搜索证据；请点击候选页面人工核对，不能直接视为元数据验证通过。")

    return " ".join(actions) if actions else "无需处理。"


def apply_product_assessment(result: dict) -> dict:
    """Attach P0 product fields: risk_level, confidence_score, suggested_action."""
    level = assess_risk_level(result)
    result["risk_level"] = level
    result["suggested_action"] = suggested_action(result)

    if level == "high" and result.get("needs_review") != "Yes":
        result["needs_review"] = "Yes"
        reason = f"{risk_label(level)}：{result['suggested_action']}"
        existing = result.get("review_reasons", "")
        result["review_reasons"] = "；".join([v for v in [existing, reason] if v])
    elif level != "high":
        result["needs_review"] = "No"
        result["review_reasons"] = ""

    result["confidence_score"] = confidence_score(result)
    result["risk_explanation"] = risk_explanation(result)
    fix_text, fix_basis = fix_suggestion(result)
    result["fix_suggestion"] = fix_text
    result["fix_suggestion_basis"] = fix_basis
    citations = standard_citations(result)
    result["standard_citation_available"] = "Yes" if citations.get("available") else "No"
    result["standard_citation_basis"] = citations.get("basis", "")
    result["standard_citation_apa"] = citations.get("apa", "")
    result["standard_citation_bibtex"] = citations.get("bibtex", "")
    result["standard_citation_gbt7714"] = citations.get("gbt7714", "")
    result["standard_citation_json"] = json.dumps(citations, ensure_ascii=False)
    return result


def build_summary(results: list[dict]) -> dict:
    """Build count buckets used by console output, reports, and the desktop UI."""
    return {
        "found": [r for r in results if r["status"] == "found"],
        "missing": [r for r in results if r["status"] == "not_found"],
        "skipped": [r for r in results if r["status"] == "skipped"],
        "review": [r for r in results if r.get("needs_review") == "Yes"],
        "high_risk": [r for r in results if r.get("risk_level") == "high"],
        "medium_risk": [r for r in results if r.get("risk_level") == "medium"],
        "low_risk": [r for r in results if r.get("risk_level") == "low"],
        "author_mismatch": [r for r in results if r.get("author_check") == "mismatch"],
        "year_mismatch": [r for r in results if r.get("year_check") == "mismatch"],
        "doi_mismatch": [
            r for r in results
            if r.get("doi_check") == "mismatch" or r.get("doi_check_status") == DOI_STATUS_MISMATCH
        ],
    }


def summary_counts(summary: dict, total: int) -> dict:
    return {
        "total": total,
        "found": len(summary["found"]),
        "not_found": len(summary["missing"]),
        "needs_review": len(summary["review"]),
        "skipped": len(summary["skipped"]),
        "high_risk": len(summary["high_risk"]),
        "medium_risk": len(summary["medium_risk"]),
        "low_risk": len(summary["low_risk"]),
        "author_mismatch": len(summary["author_mismatch"]),
        "year_mismatch": len(summary["year_mismatch"]),
        "doi_mismatch": len(summary["doi_mismatch"]),
    }


def database_summary_text(counts: dict) -> str:
    total = counts.get("total", 0)
    if total <= 0:
        return "未解析到可核验的参考文献。"
    parts = [
        f"本次共核验 {total} 条参考文献",
        f"数据库匹配成功 {counts.get('found', 0)} 条",
        f"未找到可靠匹配 {counts.get('not_found', 0)} 条",
        f"高风险 {counts.get('high_risk', 0)} 条",
        f"中风险 {counts.get('medium_risk', 0)} 条",
    ]
    issues = []
    if counts.get("author_mismatch", 0):
        issues.append(f"作者不一致 {counts.get('author_mismatch', 0)} 条")
    if counts.get("year_mismatch", 0):
        issues.append(f"年份不一致 {counts.get('year_mismatch', 0)} 条")
    if counts.get("doi_mismatch", 0):
        issues.append(f"DOI 不一致 {counts.get('doi_mismatch', 0)} 条")
    if issues:
        parts.append("元数据问题：" + "、".join(issues))
    return "；".join(parts) + "。"


def build_report_summary(
    results: list[dict],
    counts: dict,
    citation_consistency: dict | None = None,
) -> str:
    """Create a concise, deterministic executive summary for reports/UI."""
    total = counts.get("total", 0)
    if total <= 0:
        return "本次未解析到可核验的参考文献。"

    issue_counts = [
        ("未找到可靠匹配", counts.get("not_found", 0)),
        ("DOI 不一致", counts.get("doi_mismatch", 0)),
        ("作者不一致", counts.get("author_mismatch", 0)),
        ("年份不一致", counts.get("year_mismatch", 0)),
        ("正文引用缺少参考文献", len((citation_consistency or {}).get("missing_references", []) or [])),
        ("参考文献可能未被正文引用", len((citation_consistency or {}).get("uncited_references", []) or [])),
    ]
    main_issues = [f"{name} {count} 条" for name, count in issue_counts if count]
    priority = sorted(
        [r for r in results if r.get("risk_level") in {"high", "medium"}],
        key=lambda r: (
            0 if r.get("risk_level") == "high" else 1,
            r.get("confidence_score", 0),
        ),
    )
    priority_labels = [
        safe_table_text(r.get("key") or r.get("title") or "", 40)
        for r in priority[:5]
        if (r.get("key") or r.get("title"))
    ]

    lines = [
        f"本次共检查 {total} 条参考文献：数据库匹配成功 {counts.get('found', 0)} 条，"
        f"未找到可靠匹配 {counts.get('not_found', 0)} 条；"
        f"高风险 {counts.get('high_risk', 0)} 条，中风险 {counts.get('medium_risk', 0)} 条。",
    ]
    if main_issues:
        lines.append("主要问题集中在：" + "、".join(main_issues[:4]) + "。")
    else:
        lines.append("未发现明显 DOI、作者、年份或正文引用一致性问题。")
    if priority_labels:
        lines.append("建议优先处理：" + "、".join(priority_labels) + "。")
    else:
        lines.append("当前没有中高风险条目需要优先处理。")
    lines.append("以上摘要基于数据库核验与本地规则生成，不是最终学术裁决。")
    return "\n".join(lines)


def _write_citation_consistency_section(f, citation_consistency: dict | None) -> None:
    f.write("## 正文引用一致性检查\n\n")
    if not citation_consistency or not citation_consistency.get("available"):
        reason = (citation_consistency or {}).get(
            "reason",
            "当前输入类型不包含正文，未运行正文引用一致性检查。",
        )
        f.write(f"{reason}\n\n")
        return

    f.write(f"- 方法: {citation_consistency.get('method', '')}\n")
    f.write(
        f"- 正文引用签名: **{citation_consistency.get('body_signature_count', 0)}** "
        f"（出现次数 {citation_consistency.get('body_citation_count', 0)}）\n"
    )
    f.write(f"- 参考文献签名: **{citation_consistency.get('reference_signature_count', 0)}**\n")
    f.write(
        f"- 正文有但参考文献缺失: **{len(citation_consistency.get('missing_references', []))}** | "
        f"参考文献有但正文未引用: **{len(citation_consistency.get('uncited_references', []))}** | "
        f"同作者同年份重复签名: **{len(citation_consistency.get('duplicate_reference_signatures', []))}**\n\n"
    )
    f.write(f"> {citation_consistency.get('disclaimer', '')}\n\n")

    missing = citation_consistency.get("missing_references", [])
    if missing:
        f.write("### 正文引用缺少对应参考文献\n\n")
        f.write("| 正文引用 | 出现次数 | 段落 | 上下文 |\n")
        f.write("|---|---:|---:|---|\n")
        for item in missing[:30]:
            f.write(
                f"| {safe_table_text(item.get('citation', ''), 40)} "
                f"| {item.get('count', 0)} "
                f"| {item.get('paragraph') or ''} "
                f"| {safe_table_text(item.get('context', ''), 120)} |\n"
            )
        f.write("\n")

    uncited = citation_consistency.get("uncited_references", [])
    if uncited:
        f.write("### 参考文献列表中可能未被正文引用\n\n")
        f.write("| 参考文献签名 | Key/段落 | 标题 |\n")
        f.write("|---|---|---|\n")
        for item in uncited[:50]:
            key = item.get("key") or f"段落 {item.get('paragraph', '')}"
            f.write(
                f"| {safe_table_text(item.get('citation', ''), 40)} "
                f"| {safe_table_text(key, 35)} "
                f"| {safe_table_text(item.get('title', ''), 100)} |\n"
            )
        f.write("\n")

    duplicates = citation_consistency.get("duplicate_reference_signatures", [])
    if duplicates:
        f.write("### 同作者同年份重复签名（建议检查 2020a/2020b 或重复条目）\n\n")
        for item in duplicates[:20]:
            f.write(f"- **{safe_table_text(item.get('citation', ''), 60)}**：{item.get('count', 0)} 条\n")
        f.write("\n")

    if citation_consistency.get("unparsed_body_citations") or citation_consistency.get("unparsed_references"):
        f.write("### 未解析项提示\n\n")
        if citation_consistency.get("unparsed_body_citations"):
            f.write(
                "- 未解析正文引用: "
                + "；".join(safe_table_text(v, 40) for v in citation_consistency.get("unparsed_body_citations", [])[:20])
                + "\n"
            )
        if citation_consistency.get("unparsed_references"):
            f.write(f"- 未解析参考文献条目: {len(citation_consistency.get('unparsed_references', []))} 条\n")
        f.write("\n")


def _write_standard_citations_section(f, results: list[dict]) -> None:
    citation_rows = [r for r in results if r.get("standard_citation_available") == "Yes"]
    if not citation_rows:
        return
    f.write("## 一键生成规范引用（基于数据库匹配）\n\n")
    f.write(
        "> 以下引用格式由程序根据数据库匹配结果生成；不会由程序补造缺失字段。"
        "用于正式提交前，请打开 DOI/出版社页面或论文原文确认。\n\n"
    )
    for r in citation_rows[:30]:
        f.write(f"### `{safe_table_text(r.get('key', ''), 80)}`\n\n")
        f.write(f"- 依据来源: {r.get('standard_citation_basis', '')}\n\n")
        if r.get("standard_citation_apa"):
            f.write("**APA 候选格式**\n\n")
            f.write("```text\n")
            f.write(r.get("standard_citation_apa", "").strip() + "\n")
            f.write("```\n\n")
        if r.get("standard_citation_bibtex"):
            f.write("**BibTeX 候选格式**\n\n")
            f.write("```bibtex\n")
            f.write(r.get("standard_citation_bibtex", "").strip() + "\n")
            f.write("```\n\n")
        if r.get("standard_citation_gbt7714"):
            f.write("**GB/T 7714 候选格式**\n\n")
            f.write("```text\n")
            f.write(r.get("standard_citation_gbt7714", "").strip() + "\n")
            f.write("```\n\n")
    if len(citation_rows) > 30:
        f.write(f"> 另有 {len(citation_rows) - 30} 条已找到文献的规范引用候选，请查看 CSV 完整字段。\n\n")


def _web_evidence_rows(result: dict) -> list[dict]:
    raw = result.get("web_evidence_results")
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except Exception:
            raw = []
    if not isinstance(raw, list):
        return []
    rows: list[dict] = []
    for item in raw:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _markdown_link(label: str, url: str, max_len: int = 80) -> str:
    clean_url = _as_text(url)
    clean_label = safe_table_text(label or clean_url or "open", max_len)
    if not clean_url:
        return clean_label
    # Avoid breaking Markdown table links when URLs contain parentheses.
    safe_url = clean_url.replace(")", "%29").replace("(", "%28")
    return f"[{clean_label}]({safe_url})"


def _doi_url_markdown(result: dict) -> str:
    doi = clean_doi(result.get("matched_doi") or result.get("doi", ""))
    url = _as_text(result.get("url"))
    if doi:
        return _markdown_link(doi, f"https://doi.org/{doi}", 45)
    if url:
        return _markdown_link(url, url, 45)
    return ""


def _write_web_evidence_section(f, results: list[dict]) -> None:
    rows = [
        r for r in results
        if _is_web_evidence_result(r) or _web_evidence_rows(r) or _as_text(r.get("web_evidence_links"))
    ]
    if not rows:
        return
    f.write("## 网页搜索证据（仅辅助，不等同于元数据验证）\n\n")
    f.write(
        "> 以下结果来自 Brave 等网页搜索型自定义源。它们可作为可点击的网页证据，"
        "但不提供结构化作者、年份、DOI 或出版元数据；请打开链接人工确认。\n\n"
    )
    for r in rows:
        f.write(f"### `{safe_table_text(r.get('key', ''), 80)}`\n\n")
        note = r.get("web_evidence_note") or "Web search evidence only; verify metadata manually."
        f.write(f"- 说明: {note}\n")
        if r.get("matched_title"):
            f.write(
                f"- 最接近网页标题: {safe_table_text(r.get('matched_title', ''), 120)} "
                f"（标题相似度 {r.get('similarity', 0):.0%}）\n"
            )
        evidence = _web_evidence_rows(r)
        if evidence:
            f.write("\n| 排名 | 网页标题 | 来源 | 相似度 | 链接 |\n")
            f.write("|---:|---|---|---:|---|\n")
            for item in evidence[:5]:
                sim = item.get("similarity")
                try:
                    sim_text = f"{float(sim):.0%}"
                except Exception:
                    sim_text = ""
                f.write(
                    f"| {item.get('rank', '')} "
                    f"| {safe_table_text(item.get('title', ''), 70)} "
                    f"| {safe_table_text(item.get('source', ''), 35)} "
                    f"| {sim_text} "
                    f"| {_markdown_link('打开页面', item.get('url', ''), 20)} |\n"
                )
            f.write("\n")
        elif r.get("web_evidence_links"):
            f.write("\n```text\n")
            f.write(_as_text(r.get("web_evidence_links")).strip() + "\n")
            f.write("```\n\n")


def write_markdown_report(path: str, *, bibfile: str, sources: str, threshold: float,
                          total: int, results: list[dict], summary: dict,
                          citation_consistency: dict | None = None,
                          app_version: str = APP_VERSION) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    found = summary["found"]
    missing = summary["missing"]
    skipped = summary["skipped"]
    review = summary["review"]
    high_risk = summary["high_risk"]
    medium_risk = summary["medium_risk"]
    low_risk = summary["low_risk"]
    author_mismatch = summary["author_mismatch"]
    year_mismatch = summary["year_mismatch"]
    doi_mismatch = summary["doi_mismatch"]

    with open(path, "w", encoding="utf-8") as f:
        f.write("# 疑似虚构引用与参考文献可信度核验报告\n\n")
        if app_version:
            f.write(f"- RefChecker 版本: **v{app_version}**\n")
        f.write(f"- 文件: `{bibfile}`\n")
        f.write(f"- 数据源: **{sources}**\n")
        if summary.get("search_mode"):
            mode_label = "严格顺序" if summary.get("search_mode") == SEARCH_MODE_STRICT else "快速并发"
            f.write(f"- 搜索模式: **{mode_label}**\n")
        if summary.get("source_order"):
            f.write(f"- 搜索链: **{summary.get('source_order')}**\n")
        if summary.get("llm_parse_mode"):
            f.write(f"- 解析方式: **{summary.get('parser_summary') or 'rules'}**（LLM 模式: {summary.get('llm_parse_mode')}）\n")
        f.write(f"- 标题相似度阈值: **{threshold:.0%}**\n")
        f.write(
            f"- 总数: **{total}** | ✅ 找到: **{len(found)}** | ❌ 未找到: **{len(missing)}** "
            f"| ⚠️ 需人工核查: **{len(review)}** | 跳过: **{len(skipped)}**\n"
        )
        f.write(
            f"- 元数据问题: 作者不一致 **{len(author_mismatch)}** | "
            f"年份不一致 **{len(year_mismatch)}** | DOI 不一致 **{len(doi_mismatch)}**\n\n"
        )
        f.write(
            f"- 风险分级: 🔴 高风险 **{len(high_risk)}** | "
            f"🟠 中风险 **{len(medium_risk)}** | 🟡 低风险 **{len(low_risk)}**\n\n"
        )
        f.write("> 说明：本报告用于辅助识别疑似虚构引用、编造文献、误引或元数据异常。未匹配不等于文献一定不存在，匹配成功也不等于引用完全正确；最终判断仍需结合 DOI、出版社页面、论文原文和人工学术判断。\n\n")
        f.write("## 置信度说明\n\n")
        f.write(f"{CONFIDENCE_EXPLANATION}\n\n")
        f.write(f"{CONFIDENCE_SCALE}\n\n")
        f.write("## 报告摘要\n\n")
        f.write(build_report_summary(results, summary_counts(summary, total), citation_consistency) + "\n\n")
        f.write("## 数据库核验摘要\n\n")
        f.write(database_summary_text(summary_counts(summary, total)) + "\n\n")
        f.write(
            "> Verification results come from enabled data sources, URL checks, "
            "and local rules. Repair suggestions must be based on traceable evidence.\n\n"
        )
        f.write("## 隐私与边界说明\n\n")
        f.write("- 修复建议必须依据数据库返回结果、URL 验证结果或正文一致性检查；证据不足时应人工核查。\n")
        f.write("\n")
        _write_web_evidence_section(f, results)
        _write_citation_consistency_section(f, citation_consistency)

        if high_risk or medium_risk:
            f.write("## 风险总览（高风险优先核查，中风险建议抽查）\n\n")
            f.write("| 风险 | Key | 置信度 | 来源 | 风险解释 | 修复建议与依据 |\n")
            f.write("|---|---|---:|---|---|---|\n")
            priority_rows = sorted(
                high_risk + medium_risk,
                key=lambda r: (0 if r.get("risk_level") == "high" else 1, r.get("confidence_score", 0)),
            )
            for r in priority_rows[:30]:
                explanation = r.get("risk_explanation") or r.get("review_reasons") or ""
                fix = r.get("fix_suggestion") or r.get("suggested_action") or ""
                basis = r.get("fix_suggestion_basis", "")
                f.write(
                    f"| {risk_badge_markdown(r.get('risk_level', 'none'))} "
                    f"| {safe_table_text(r.get('key', ''), 35)} "
                    f"| {r.get('confidence_score', 0)} "
                    f"| {safe_table_text(r.get('source', ''), 20)} "
                    f"| {safe_table_text(explanation, 110)} "
                    f"| {safe_table_text(fix + ' 依据：' + basis, 140)} |\n"
                )
            if len(priority_rows) > 30:
                f.write(f"\n> 另有 {len(priority_rows) - 30} 条中高风险记录，请查看 CSV 完整结果。\n")
            f.write("\n")

        if missing:
            f.write("## ❌ 未找到（重点核查）\n\n")
            for r in missing:
                f.write(f"### `{r['key']}`\n")
                f.write(f"- 风险/置信度: {risk_badge_markdown(r.get('risk_level', 'high'))} / {r.get('confidence_score', 0)}\n")
                f.write(f"- 原标题: {r['title']}\n")
                f.write(f"- 原因: {r.get('reason', '')}\n")
                f.write(f"- 风险解释: {r.get('risk_explanation', '')}\n")
                if r.get("matched_title"):
                    f.write(
                        f"- 最接近 ({r.get('source', '?')}): {r['matched_title']} "
                        f"(标题相似度 {r.get('similarity', 0):.0%})\n"
                    )
                f.write(f"- 作者核查: {r.get('author_reason', '')}\n\n")
                if r.get("doi_check_status") and r.get("doi_check_status") != DOI_STATUS_NOT_PROVIDED:
                    f.write(f"- DOI 精确核验: {r.get('doi_check_status')}；{r.get('doi_check_message', '')}\n")
                    if r.get("doi_target_title"):
                        f.write(f"- DOI 指向标题: {r.get('doi_target_title')}\n")
                if r.get("actual_query_trace"):
                    f.write(f"- 实际查询路径: {r.get('actual_query_trace')}\n")
                f.write(f"- 修复建议: {r.get('fix_suggestion') or r.get('suggested_action', '')}\n")
                f.write(f"- 依据来源: {r.get('fix_suggestion_basis', '')}\n\n")

        if review:
            f.write("## ⚠️ 需要人工核查的高风险条目\n\n")
            f.write("| 风险 | Key | 置信度 | 来源 | 标题相似度 | 作者核查 | 年份核查 | DOI 核查 | 修复建议 |\n")
            f.write("|---|---|---:|---|---:|---|---|---|---|\n")
            for r in review:
                f.write(
                    f"| {risk_badge_markdown(r.get('risk_level', 'none'))} "
                    f"| {safe_table_text(r['key'], 35)} "
                    f"| {r.get('confidence_score', 0)} "
                    f"| {safe_table_text(r.get('source', ''), 20)} "
                    f"| {r.get('similarity', 0):.0%} "
                    f"| {safe_table_text(r.get('author_check', '') + ': ' + r.get('author_reason', ''), 70)} "
                    f"| {safe_table_text(r.get('year_check', '') + ': ' + r.get('year_reason', ''), 45)} "
                    f"| {safe_table_text(r.get('doi_check', '') + ': ' + r.get('doi_reason', ''), 45)} "
                    f"| {safe_table_text((r.get('fix_suggestion') or r.get('suggested_action', '')) + ' 依据：' + r.get('fix_suggestion_basis', ''), 130)} |\n"
                )

        if found:
            f.write("\n## ✅ 已找到的文献\n\n")
            f.write("| Key | 风险 | 置信度 | 标题 | DOI 精确核验 | 最终采用 | 标题相似度 | 作者 | 年份 | DOI/URL |\n")
            f.write("|---|---|---:|---|---|---|---:|---|---|---|\n")
            for r in found:
                link = _doi_url_markdown(r)
                f.write(
                    f"| {safe_table_text(r['key'], 40)} "
                    f"| {risk_badge_markdown(r.get('risk_level', 'none'))} "
                    f"| {r.get('confidence_score', 0)} "
                    f"| {safe_table_text(r['title'], 50)} "
                    f"| {safe_table_text(r.get('doi_check_status', ''), 18)} "
                    f"| {safe_table_text(r.get('adopted_source') or r.get('source', ''), 20)} "
                    f"| **{r.get('similarity', 0):.0%}** "
                    f"| {status_icon(r.get('author_check'))} {safe_table_text(r.get('author_check', ''), 12)} "
                    f"| {status_icon(r.get('year_check'))} {safe_table_text(r.get('matched_year', ''), 8)} "
                    f"| {link or safe_table_text('', 45)} |\n"
                )

        if author_mismatch:
            f.write("\n## ❌ 作者不一致详情\n\n")
            for r in author_mismatch:
                f.write(f"### `{r['key']}`\n")
                f.write(f"- 标题: {r['title']}\n")
                f.write(f"- 风险/置信度: {risk_badge_markdown(r.get('risk_level', 'medium'))} / {r.get('confidence_score', 0)}\n")
                f.write(f"- 问题: {r.get('author_reason', '')}\n")
                f.write(f"- BibTeX 作者: {r.get('bib_authors', '')}\n")
                f.write(f"- 数据库作者: {r.get('matched_authors', '')}\n")
                if r.get("missing_authors"):
                    f.write(f"- BibTeX 可能省略: {r.get('missing_authors')}\n")
                if r.get("extra_authors"):
                    f.write(f"- BibTeX 可能额外/可疑: {r.get('extra_authors')}\n")
                f.write(f"- 修复建议: {r.get('fix_suggestion', '')}\n")
                f.write(f"- 依据来源: {r.get('fix_suggestion_basis', '')}\n")
                f.write("\n")

        if skipped:
            f.write("\n## ⚠️ 跳过\n\n")
            for r in skipped:
                f.write(f"- `{r['key']}`: {r.get('reason', '')}；建议操作：{r.get('suggested_action', '')}\n")

        _write_standard_citations_section(f, results)



def write_csv_report(path: str, results: list[dict]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fieldnames = [
        "key", "status", "needs_review", "risk_level", "confidence_score",
        "suggested_action", "review_reasons",
        "risk_explanation", "fix_suggestion", "fix_suggestion_basis",
        "parser", "parser_note", "parser_confidence", "parser_warning", "llm_parse_mode",
        "search_mode", "source_order", "actual_query_trace", "query_trace",
        "adopted_source",
        "doi_check_status", "doi_check_message", "doi_resolved_url",
        "doi_target_title", "doi_target_authors", "doi_target_year", "doi_target_doi",
        "candidate_count", "arbitration_reason", "source_trace",
        "alternative_candidates", "candidate_conflict",
        "standard_citation_available", "standard_citation_basis",
        "standard_citation_apa", "standard_citation_bibtex",
        "standard_citation_gbt7714", "standard_citation_json",
        "web_evidence", "evidence_kind", "web_evidence_note",
        "web_evidence_links", "web_evidence_results", "snippet",
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
            if isinstance(row.get("web_evidence_results"), (list, dict)):
                row["web_evidence_results"] = json.dumps(row.get("web_evidence_results"), ensure_ascii=False)
            writer.writerow(row)


def emit_jsonl(event_type: str, **payload) -> None:
    payload["type"] = event_type
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def printable_result(result: dict) -> dict:
    keys = [
        "key", "title", "status", "needs_review", "risk_level",
        "confidence_score", "suggested_action", "review_reasons",
        "risk_explanation", "fix_suggestion", "fix_suggestion_basis",
        "parser", "parser_note", "parser_confidence", "parser_warning", "llm_parse_mode",
        "candidate_count", "arbitration_reason", "source_trace",
        "search_mode", "source_order", "actual_query_trace", "query_trace",
        "adopted_source", "doi_check_status", "doi_check_message",
        "doi_resolved_url", "doi_target_title", "doi_target_year", "doi_target_doi",
        "alternative_candidates", "candidate_conflict",
        "standard_citation_available", "standard_citation_basis",
        "standard_citation_apa", "standard_citation_bibtex",
        "standard_citation_gbt7714",
        "web_evidence", "evidence_kind", "web_evidence_note",
        "web_evidence_links", "web_evidence_results", "snippet",
        "matched_title", "similarity", "source", "venue", "year", "type",
        "author_check", "author_reason", "year_check", "year_reason",
        "doi_check", "doi_reason", "bib_doi", "matched_doi", "doi", "url",
        "bib_url", "bib_year", "matched_year",
        "bib_author_count", "matched_author_count", "author_order_mismatch",
        "bib_authors", "matched_authors", "missing_authors", "extra_authors",
        "authors", "reason",
    ]
    printable = {}
    for key in keys:
        value = result.get(key, "")
        if key == "web_evidence_results" and isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)
        printable[key] = value
    return printable

