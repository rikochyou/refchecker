"""RefChecker — AI 幻觉引用与参考文献元数据核验."""
import contextlib
import os
import re
import sys
import time

import bibtexparser

from .utils import strip_latex, truncate
from . import verifier as _verifier
from .docx_parser import extract_references_from_docx, parse_text_references

SAFE_MIN_DELAY_SECONDS = 0.5


def _safe_delay(delay: float | int | str | None) -> float:
    try:
        value = float(delay)
    except Exception:
        return SAFE_MIN_DELAY_SECONDS
    if value < SAFE_MIN_DELAY_SECONDS:
        return SAFE_MIN_DELAY_SECONDS
    return value


def verify_text(text: str, *, threshold: float = 0.85, delay: float = SAFE_MIN_DELAY_SECONDS,
                email: str = "", use_openalex: bool = True, use_dblp: bool = True,
                use_semantic_scholar: bool = True, use_arxiv: bool = True,
                use_pubmed: bool = True,
                use_crossref: bool = True, use_springer: bool = False,
                use_ieee: bool = False, use_core: bool = False,
                springer_api_key: str = "", ieee_api_key: str = "",
                core_api_key: str = "",
                use_url_verify: bool = True,
                source_order: list[str] | None = None,
                custom_rest_profiles: list[dict] | None = None,
                output: str | None = None, csv_path: str | None = None,
                output_dir: str | None = None, jsonl_progress: bool = False,
                human_output: bool = True) -> dict:
    """解析粘贴的参考文献文本并进行验证。"""
    delay = _safe_delay(delay)
    log_stream = sys.stderr if jsonl_progress else sys.stdout

    def log(message: str = "") -> None:
        if human_output:
            print(message, file=log_stream, flush=True)

    def event(event_type: str, **payload) -> None:
        if jsonl_progress:
            _verifier.emit_jsonl(event_type, **payload)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output = output or os.path.join(output_dir, "report.md")
        csv_path = csv_path or os.path.join(output_dir, "result.csv")

    refs = parse_text_references(text)
    total = len(refs)
    sources = "CrossRef" if use_crossref else ""
    sources += (" + OpenAlex" if use_openalex else "")
    sources += (" + Semantic Scholar" if use_semantic_scholar else "")
    sources += (" + arXiv" if use_arxiv else "")
    sources += (" + PubMed" if use_pubmed else "")
    sources += (" + Springer Nature" if use_springer and springer_api_key else "")
    sources += (" + IEEE Xplore" if use_ieee and ieee_api_key else "")
    sources += (" + CORE" if use_core and core_api_key else "")
    for profile in custom_rest_profiles or []:
        if profile.get("enabled", True):
            sources += " + " + (profile.get("name") or "Custom REST")
    sources += (" + DBLP" if use_dblp else "")
    if use_url_verify:
        sources += " + URL"
    sources = sources.strip(" +") or "未启用数据库源"
    log(f"📚 从文本解析到 {total} 条参考文献，开始验证 ({sources}, 标题阈值 {threshold:.0%})\n")
    event("started", total=total, sources=sources, threshold=threshold,
          use_openalex=use_openalex, use_dblp=use_dblp,
          use_semantic_scholar=use_semantic_scholar, use_arxiv=use_arxiv,
          use_pubmed=use_pubmed, use_crossref=use_crossref,
          use_springer=use_springer and bool(springer_api_key),
          use_ieee=use_ieee and bool(ieee_api_key),
          use_core=use_core and bool(core_api_key),
          use_url_verify=use_url_verify, bibfile="粘贴文本")

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
            _verifier.apply_product_assessment(row)
            results.append(row)
            event("entry_finished", index=i, total=total, result=_verifier.printable_result(row))
            continue

        res = _verifier.verify_entry(title_clean, author, year, doi, threshold,
                           email, use_openalex, use_dblp,
                           use_semantic_scholar=use_semantic_scholar,
                           use_arxiv=use_arxiv, use_pubmed=use_pubmed,
                           use_crossref=use_crossref, use_springer=use_springer,
                           use_ieee=use_ieee, use_core=use_core,
                           springer_api_key=springer_api_key,
                           ieee_api_key=ieee_api_key, core_api_key=core_api_key,
                           url=ref_url,
                           use_url_verify=use_url_verify,
                           source_order=source_order,
                           custom_rest_profiles=custom_rest_profiles)
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

        log(f"        作者: {_verifier.status_icon(res.get('author_check'))} {res.get('author_reason', '')}")
        if res.get("year_check") == "mismatch":
            log(f"        年份: ❌ {res.get('year_reason', '')}")
        if res.get("doi_check") == "mismatch":
            log(f"        DOI : ❌ {res.get('doi_reason', '')}")

        row = {"key": key, "title": title_clean, **res}
        _verifier.apply_product_assessment(row)
        results.append(row)
        event("entry_finished", index=i, total=total, result=_verifier.printable_result(row))

        log()
        if i < total:
            time.sleep(delay)

    summary = _verifier.build_summary(results)
    counts = _verifier.summary_counts(summary, total)

    log("=" * 72)
    log(
        f"总结: ✅ {counts['found']} 找到 | ❌ {counts['not_found']} 未找到 | "
        f"⚠️ {counts['needs_review']} 需人工核查 | 跳过 {counts['skipped']}"
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
        _verifier.write_markdown_report(output, bibfile="粘贴文本", sources=sources, threshold=threshold,
                              total=total, results=results, summary=summary)
        log(f"\n📄 报告已保存到: {output}")
    if csv_path:
        _verifier.write_csv_report(csv_path, results)
        log(f"📊 CSV 表格已保存到: {csv_path}")

    counts.update({
        "bibfile": "粘贴文本",
        "sources": sources,
        "output_dir": os.path.abspath(output_dir) if output_dir else "",
        "markdown_path": output_path,
        "csv_path": csv_output_path,
    })
    event("summary", **counts)
    return {"results": results, "summary": counts}


def verify_docx_file(docx_path: str, *, threshold: float = 0.85, delay: float = SAFE_MIN_DELAY_SECONDS,
                     email: str = "", use_openalex: bool = True, use_dblp: bool = True,
                     use_semantic_scholar: bool = True, use_arxiv: bool = True,
                     use_pubmed: bool = True,
                     use_crossref: bool = True, use_springer: bool = False,
                     use_ieee: bool = False, use_core: bool = False,
                     springer_api_key: str = "", ieee_api_key: str = "",
                     core_api_key: str = "",
                     use_url_verify: bool = True,
                     source_order: list[str] | None = None,
                     custom_rest_profiles: list[dict] | None = None,
                     output: str | None = None, csv_path: str | None = None,
                     output_dir: str | None = None, jsonl_progress: bool = False,
                     human_output: bool = True) -> dict:
    """从 .docx 文件中提取参考文献并进行验证。"""
    delay = _safe_delay(delay)
    log_stream = sys.stderr if jsonl_progress else sys.stdout

    def log(message: str = "") -> None:
        if human_output:
            print(message, file=log_stream, flush=True)

    def event(event_type: str, **payload) -> None:
        if jsonl_progress:
            _verifier.emit_jsonl(event_type, **payload)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output = output or os.path.join(output_dir, "report.md")
        csv_path = csv_path or os.path.join(output_dir, "result.csv")

    refs = extract_references_from_docx(docx_path)
    total = len(refs)
    sources = "CrossRef" if use_crossref else ""
    sources += (" + OpenAlex" if use_openalex else "")
    sources += (" + Semantic Scholar" if use_semantic_scholar else "")
    sources += (" + arXiv" if use_arxiv else "")
    sources += (" + PubMed" if use_pubmed else "")
    sources += (" + Springer Nature" if use_springer and springer_api_key else "")
    sources += (" + IEEE Xplore" if use_ieee and ieee_api_key else "")
    sources += (" + CORE" if use_core and core_api_key else "")
    for profile in custom_rest_profiles or []:
        if profile.get("enabled", True):
            sources += " + " + (profile.get("name") or "Custom REST")
    sources += (" + DBLP" if use_dblp else "")
    if use_url_verify:
        sources += " + URL"
    sources = sources.strip(" +") or "未启用数据库源"
    log(f"📚 从 DOCX 解析到 {total} 条参考文献，开始验证 ({sources}, 标题阈值 {threshold:.0%})\n")
    event("started", total=total, sources=sources, threshold=threshold,
          use_openalex=use_openalex, use_dblp=use_dblp,
          use_semantic_scholar=use_semantic_scholar, use_arxiv=use_arxiv,
          use_pubmed=use_pubmed, use_crossref=use_crossref,
          use_springer=use_springer and bool(springer_api_key),
          use_ieee=use_ieee and bool(ieee_api_key),
          use_core=use_core and bool(core_api_key),
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
            _verifier.apply_product_assessment(row)
            results.append(row)
            event("entry_finished", index=i, total=total, result=_verifier.printable_result(row))
            continue

        res = _verifier.verify_entry(title_clean, author, year, doi, threshold,
                           email, use_openalex, use_dblp,
                           use_semantic_scholar=use_semantic_scholar,
                           use_arxiv=use_arxiv, use_pubmed=use_pubmed,
                           use_crossref=use_crossref, use_springer=use_springer,
                           use_ieee=use_ieee, use_core=use_core,
                           springer_api_key=springer_api_key,
                           ieee_api_key=ieee_api_key, core_api_key=core_api_key,
                           url=ref_url,
                           use_url_verify=use_url_verify,
                           source_order=source_order,
                           custom_rest_profiles=custom_rest_profiles)
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

        log(f"        作者: {_verifier.status_icon(res.get('author_check'))} {res.get('author_reason', '')}")
        if res.get("year_check") == "mismatch":
            log(f"        年份: ❌ {res.get('year_reason', '')}")
        if res.get("doi_check") == "mismatch":
            log(f"        DOI : ❌ {res.get('doi_reason', '')}")

        row = {"key": key, "title": title_clean, **res}
        _verifier.apply_product_assessment(row)
        results.append(row)
        event("entry_finished", index=i, total=total, result=_verifier.printable_result(row))

        log()
        if i < total:
            time.sleep(delay)

    summary = _verifier.build_summary(results)
    counts = _verifier.summary_counts(summary, total)

    log("=" * 72)
    log(
        f"总结: ✅ {counts['found']} 找到 | ❌ {counts['not_found']} 未找到 | "
        f"⚠️ {counts['needs_review']} 需人工核查 | 跳过 {counts['skipped']}"
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
        _verifier.write_markdown_report(output, bibfile=docx_path, sources=sources, threshold=threshold,
                              total=total, results=results, summary=summary)
        log(f"\n📄 报告已保存到: {output}")
    if csv_path:
        _verifier.write_csv_report(csv_path, results)
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


def verify_bib_file(bibfile: str, *, threshold: float = 0.85, delay: float = SAFE_MIN_DELAY_SECONDS,
                    email: str = "", use_openalex: bool = True, use_dblp: bool = True,
                    use_semantic_scholar: bool = True, use_arxiv: bool = True,
                    use_pubmed: bool = True,
                    use_crossref: bool = True, use_springer: bool = False,
                    use_ieee: bool = False, use_core: bool = False,
                    springer_api_key: str = "", ieee_api_key: str = "",
                    core_api_key: str = "",
                    use_url_verify: bool = True,
                    source_order: list[str] | None = None,
                    custom_rest_profiles: list[dict] | None = None,
                    output: str | None = None, csv_path: str | None = None,
                    output_dir: str | None = None, jsonl_progress: bool = False,
                    human_output: bool = True) -> dict:
    delay = _safe_delay(delay)
    log_stream = sys.stderr if jsonl_progress else sys.stdout

    def log(message: str = "") -> None:
        if human_output:
            print(message, file=log_stream, flush=True)

    def event(event_type: str, **payload) -> None:
        if jsonl_progress:
            _verifier.emit_jsonl(event_type, **payload)

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
    sources = "CrossRef" if use_crossref else ""
    sources += (" + OpenAlex" if use_openalex else "")
    sources += (" + Semantic Scholar" if use_semantic_scholar else "")
    sources += (" + arXiv" if use_arxiv else "")
    sources += (" + PubMed" if use_pubmed else "")
    sources += (" + Springer Nature" if use_springer and springer_api_key else "")
    sources += (" + IEEE Xplore" if use_ieee and ieee_api_key else "")
    sources += (" + CORE" if use_core and core_api_key else "")
    for profile in custom_rest_profiles or []:
        if profile.get("enabled", True):
            sources += " + " + (profile.get("name") or "Custom REST")
    sources += (" + DBLP" if use_dblp else "")
    if use_url_verify:
        sources += " + URL"
    sources = sources.strip(" +") or "未启用数据库源"
    log(f"📚 解析到 {total} 条文献，开始验证 ({sources}, 标题阈值 {threshold:.0%})\n")
    event("started", total=total, sources=sources, threshold=threshold,
          use_openalex=use_openalex, use_dblp=use_dblp,
          use_semantic_scholar=use_semantic_scholar, use_arxiv=use_arxiv,
          use_pubmed=use_pubmed, use_crossref=use_crossref,
          use_springer=use_springer and bool(springer_api_key),
          use_ieee=use_ieee and bool(ieee_api_key),
          use_core=use_core and bool(core_api_key),
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
            _verifier.apply_product_assessment(row)
            results.append(row)
            event("entry_finished", index=i, total=total, result=_verifier.printable_result(row))
            continue

        res = _verifier.verify_entry(title_clean, author, year, doi, threshold,
                           email, use_openalex, use_dblp,
                           use_semantic_scholar=use_semantic_scholar,
                           use_arxiv=use_arxiv, use_pubmed=use_pubmed,
                           use_crossref=use_crossref, use_springer=use_springer,
                           use_ieee=use_ieee, use_core=use_core,
                           springer_api_key=springer_api_key,
                           ieee_api_key=ieee_api_key, core_api_key=core_api_key,
                           url=url,
                           use_url_verify=use_url_verify,
                           source_order=source_order,
                           custom_rest_profiles=custom_rest_profiles)

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

        log(f"        作者: {_verifier.status_icon(res.get('author_check'))} {res.get('author_reason', '')}")
        if res.get("year_check") == "mismatch":
            log(f"        年份: ❌ {res.get('year_reason', '')}")
        if res.get("doi_check") == "mismatch":
            log(f"        DOI : ❌ {res.get('doi_reason', '')}")

        row = {"key": key, "title": title_clean, **res}
        _verifier.apply_product_assessment(row)
        results.append(row)
        event("entry_finished", index=i, total=total, result=_verifier.printable_result(row))

        log()
        if i < total:
            time.sleep(delay)

    summary = _verifier.build_summary(results)
    counts = _verifier.summary_counts(summary, total)

    log("=" * 72)
    log(
        f"总结: ✅ {counts['found']} 找到 | ❌ {counts['not_found']} 未找到 | "
        f"⚠️ {counts['needs_review']} 需人工核查 | 跳过 {counts['skipped']}"
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
        _verifier.write_markdown_report(output, bibfile=bibfile, sources=sources, threshold=threshold,
                              total=total, results=results, summary=summary)
        log(f"\n📄 报告已保存到: {output}")
    if csv_path:
        _verifier.write_csv_report(csv_path, results)
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
