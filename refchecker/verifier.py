"""RefChecker — AI 幻觉引用与参考文献元数据核验."""
import csv
import json
import os
import sys

from .utils import strip_latex, title_similarity, extract_year, clean_doi, truncate, compare_year, compare_doi
from .author import compare_author_lists, author_display_list
from . import sources as _sources
from . import url_verify as _url_verify
from . import custom_rest as _custom_rest
from .config import build_source_order, DEFAULT_SOURCE_ORDER

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


def verify_entry(title: str, author: str, year: str, doi: str, threshold: float,
                 email: str, use_openalex: bool, use_dblp: bool,
                 use_semantic_scholar: bool = True, use_arxiv: bool = True,
                 use_pubmed: bool = True, use_crossref: bool = True,
                 use_springer: bool = False, use_ieee: bool = False,
                 use_core: bool = False, springer_api_key: str = "",
                 ieee_api_key: str = "", core_api_key: str = "", url: str = "",
                 use_url_verify: bool = True,
                 source_order: list[str] | None = None,
                 custom_rest_profiles: list[dict] | None = None) -> dict:
    """根据 DOI、source_order 依次检索数据源，并可选 URL 验证。"""
    candidates: list[dict] = []
    custom_profile_map = _custom_rest.profile_map(custom_rest_profiles)

    # 阶段 1：DOI 精确查询（如果提供了 DOI）
    doi_result = _sources.search_crossref_by_doi(doi, title, email) if use_crossref and doi else None
    if doi_result and doi_result.get("matched_title"):
        candidates.append(doi_result)
        doi_ok = doi_result.get("similarity", 0) >= threshold * 0.6
        if doi_ok or doi_result.get("doi_exact_query"):
            doi_result["found"] = True
            return enrich_result(doi_result, bib_author=author, bib_year=year, bib_doi=doi)

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

    result: dict = {"found": False, "similarity": 0.0, "reason": "未找到匹配"}

    # 阶段 2：按序搜索各数据源
    for source_name in order:
        if not _source_enabled(source_name, **enabled_kwargs):
            continue
        r = _search_source(source_name, title, author, year, threshold, email,
                           springer_api_key=springer_api_key,
                           ieee_api_key=ieee_api_key,
                           core_api_key=core_api_key,
                           custom_rest_profiles=custom_profile_map)
        if r.get("matched_title"):
            candidates.append(r)
        if r.get("found"):
            return enrich_result(r, bib_author=author, bib_year=year, bib_doi=doi)

    # 阶段 3：URL 资源验证（如果提供了 URL）
    if use_url_verify and url:
        web = _url_verify.verify_url_resource(url, title, author, year, email)
        if web.get("matched_title"):
            candidates.append(web)
        if web.get("found"):
            return enrich_result(web, bib_author=author, bib_year=year, bib_doi=doi)

    # 若无精确匹配，从候选中选取最佳结果
    if candidates:
        best = max(candidates, key=lambda x: x.get("similarity", 0))
    else:
        best = result

    best["found"] = False
    source_names = [
        _SOURCE_NAME_LABEL.get(n) or custom_profile_map.get(n, {}).get("name") or n
        for n in order
        if _source_enabled(n, **enabled_kwargs)
    ]
    source_label = " / ".join(source_names) if source_names else "未启用数据源"
    best["reason"] = (
        f"{source_label} 等数据库 "
        f"(最高相似度仅 {best.get('similarity', 0):.0%})"
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

    if result.get("needs_review") == "No":
        score += 3

    return _clamp_score(score)


def assess_risk_level(result: dict) -> str:
    """Classify the entry into a product-friendly review priority."""
    status = result.get("status", "")
    source = result.get("source", "")
    similarity = result.get("similarity", 0) or 0
    author_check = result.get("author_check")
    year_check = result.get("year_check")
    doi_check = result.get("doi_check")

    if status == "skipped":
        return "high"
    if status == "not_found" or not result.get("found", True):
        return "high"
    if doi_check == "mismatch":
        return "high"
    if source != "URL(Web)" and similarity < 0.85:
        return "high"
    if author_check == "mismatch" and _first_author_is_mismatch(result.get("first_author_match")):
        return "high"

    if author_check == "mismatch" or year_check == "mismatch":
        return "medium"
    if source != "URL(Web)" and similarity < 0.90:
        return "medium"

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
        _append_action(actions, "人工检索标题/DOI，排查疑似 AI 幻觉引用；若为模型、代码或硬件资料，请补充可访问 URL。")

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

    if source == "URL(Web)":
        _append_action(actions, "仅验证网页可访问；建议人工确认页面标题、作者和发布日期。")

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
        "doi_mismatch": [r for r in results if r.get("doi_check") == "mismatch"],
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


def write_markdown_report(path: str, *, bibfile: str, sources: str, threshold: float,
                          total: int, results: list[dict], summary: dict) -> None:
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
        f.write("# AI 幻觉引用与参考文献可信度核验报告\n\n")
        f.write(f"- 文件: `{bibfile}`\n")
        f.write(f"- 数据源: **{sources}**\n")
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
        f.write("> 说明：本报告用于辅助识别疑似 AI 幻觉引用、编造文献、误引或元数据异常。未匹配不等于文献一定不存在，匹配成功也不等于引用完全正确；最终判断仍需结合 DOI、出版社页面、论文原文和人工学术判断。\n\n")
        f.write("## 置信度说明\n\n")
        f.write(f"{CONFIDENCE_EXPLANATION}\n\n")
        f.write(f"{CONFIDENCE_SCALE}\n\n")

        if high_risk or medium_risk:
            f.write("## 风险总览（高风险优先核查，中风险建议抽查）\n\n")
            f.write("| 风险 | Key | 置信度 | 来源 | 主要原因 | 建议操作 |\n")
            f.write("|---|---|---:|---|---|---|\n")
            priority_rows = sorted(
                high_risk + medium_risk,
                key=lambda r: (0 if r.get("risk_level") == "high" else 1, r.get("confidence_score", 0)),
            )
            for r in priority_rows[:30]:
                main_reason = r.get("review_reasons") or r.get("reason") or r.get("author_reason") or ""
                f.write(
                    f"| {risk_badge_markdown(r.get('risk_level', 'none'))} "
                    f"| {safe_table_text(r.get('key', ''), 35)} "
                    f"| {r.get('confidence_score', 0)} "
                    f"| {safe_table_text(r.get('source', ''), 20)} "
                    f"| {safe_table_text(main_reason, 80)} "
                    f"| {safe_table_text(r.get('suggested_action', ''), 90)} |\n"
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
                if r.get("matched_title"):
                    f.write(
                        f"- 最接近 ({r.get('source', '?')}): {r['matched_title']} "
                        f"(标题相似度 {r.get('similarity', 0):.0%})\n"
                    )
                f.write(f"- 作者核查: {r.get('author_reason', '')}\n\n")
                f.write(f"- 建议操作: {r.get('suggested_action', '')}\n\n")

        if review:
            f.write("## ⚠️ 需要人工核查的高风险条目\n\n")
            f.write("| 风险 | Key | 置信度 | 来源 | 标题相似度 | 作者核查 | 年份核查 | DOI 核查 | 建议操作 |\n")
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
                    f"| {safe_table_text(r.get('suggested_action', ''), 90)} |\n"
                )

        if found:
            f.write("\n## ✅ 已找到的文献\n\n")
            f.write("| Key | 风险 | 置信度 | 标题 | 来源 | 标题相似度 | 作者 | 年份 | DOI/URL |\n")
            f.write("|---|---|---:|---|---|---:|---|---|---|\n")
            for r in found:
                link = r.get("matched_doi") or r.get("doi") or r.get("url", "")
                f.write(
                    f"| {safe_table_text(r['key'], 40)} "
                    f"| {risk_badge_markdown(r.get('risk_level', 'none'))} "
                    f"| {r.get('confidence_score', 0)} "
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
                f.write(f"- 风险/置信度: {risk_badge_markdown(r.get('risk_level', 'medium'))} / {r.get('confidence_score', 0)}\n")
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
                f.write(f"- `{r['key']}`: {r.get('reason', '')}；建议操作：{r.get('suggested_action', '')}\n")



def write_csv_report(path: str, results: list[dict]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fieldnames = [
        "key", "status", "needs_review", "risk_level", "confidence_score",
        "suggested_action", "review_reasons",
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
        "key", "title", "status", "needs_review", "risk_level",
        "confidence_score", "suggested_action", "review_reasons",
        "matched_title", "similarity", "source", "venue", "year", "type",
        "author_check", "author_reason", "year_check", "year_reason",
        "doi_check", "doi_reason", "bib_doi", "matched_doi", "doi", "url", "reason",
    ]
    return {key: result.get(key, "") for key in keys}

