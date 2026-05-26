"""Batch verification helpers for RefChecker."""
import contextlib
import json
import os
import re
import sys
import time

try:
    import pyparsing as _pyparsing

    if not hasattr(_pyparsing, "DelimitedList") and hasattr(_pyparsing, "delimitedList"):
        _pyparsing.DelimitedList = _pyparsing.delimitedList
except Exception:
    pass

import bibtexparser

from .utils import strip_latex, truncate
from . import verifier as _verifier
from . import citation_consistency as _citation_consistency
from .docx_parser import extract_references_from_docx, parse_text_references
from .version import APP_VERSION

SAFE_MIN_DELAY_SECONDS = 0.5


def _safe_delay(delay: float | int | str | None) -> float:
    try:
        value = float(delay)
    except Exception:
        return SAFE_MIN_DELAY_SECONDS
    if value < SAFE_MIN_DELAY_SECONDS:
        return SAFE_MIN_DELAY_SECONDS
    return value


def _citation_summary_fields(citation_consistency: dict | None) -> dict:
    data = citation_consistency or {}
    return {
        "citation_consistency_available": bool(data.get("available")),
        "missing_reference_citations": len(data.get("missing_references", []) or []),
        "uncited_references": len(data.get("uncited_references", []) or []),
        "duplicate_reference_signatures": len(data.get("duplicate_reference_signatures", []) or []),
    }


def _write_analysis_artifacts(*, output_dir: str | None, citation_consistency: dict | None) -> dict:
    paths = {"citation_consistency_path": ""}
    if not output_dir:
        return paths
    os.makedirs(output_dir, exist_ok=True)
    citation_path = os.path.join(output_dir, "citation_consistency.json")
    with open(citation_path, "w", encoding="utf-8") as f:
        json.dump(citation_consistency or {}, f, ensure_ascii=False, indent=2)
    paths["citation_consistency_path"] = os.path.abspath(citation_path)
    return paths


def _source_label(
    *,
    use_crossref: bool,
    use_openalex: bool,
    use_semantic_scholar: bool,
    use_arxiv: bool,
    use_pubmed: bool,
    use_springer: bool,
    use_ieee: bool,
    use_core: bool,
    springer_api_key: str,
    ieee_api_key: str,
    core_api_key: str,
    custom_rest_profiles: list[dict] | None,
    use_dblp: bool,
    use_url_verify: bool,
) -> str:
    sources: list[str] = []
    if use_crossref:
        sources.append("CrossRef")
    if use_openalex:
        sources.append("OpenAlex")
    if use_semantic_scholar:
        sources.append("Semantic Scholar")
    if use_arxiv:
        sources.append("arXiv")
    if use_pubmed:
        sources.append("PubMed")
    if use_springer and springer_api_key:
        sources.append("Springer Nature")
    if use_ieee and ieee_api_key:
        sources.append("IEEE Xplore")
    if use_core and core_api_key:
        sources.append("CORE")
    for profile in custom_rest_profiles or []:
        if profile.get("enabled", True):
            sources.append(profile.get("name") or "Custom REST")
    if use_dblp:
        sources.append("DBLP")
    if use_url_verify:
        sources.append("URL")
    return " + ".join(sources) if sources else "No data source enabled"


def _log_summary(log, summary: dict, counts: dict) -> None:
    log("=" * 72)
    log(
        f"Summary: {counts['found']} found | {counts['not_found']} not found | "
        f"{counts['needs_review']} need review | {counts['skipped']} skipped"
    )
    log(
        f"Metadata issues: author {counts['author_mismatch']} | "
        f"year {counts['year_mismatch']} | DOI {counts['doi_mismatch']}"
    )
    log("=" * 72)

    if summary["missing"]:
        log("\nItems not matched; please review manually:")
        for r in summary["missing"]:
            log(f"   - [{r['key']}] {truncate(r['title'], 80)}")

    if summary["author_mismatch"]:
        log("\nItems with author metadata mismatch:")
        for r in summary["author_mismatch"][:30]:
            log(f"   - [{r['key']}] {r.get('author_reason', '')}")
        if len(summary["author_mismatch"]) > 30:
            log(f"   ... {len(summary['author_mismatch']) - 30} more; see report/CSV")


def _verify_reference_rows(
    refs: list[dict],
    *,
    threshold: float,
    delay: float,
    email: str,
    use_openalex: bool,
    use_dblp: bool,
    use_semantic_scholar: bool,
    use_arxiv: bool,
    use_pubmed: bool,
    use_crossref: bool,
    use_springer: bool,
    use_ieee: bool,
    use_core: bool,
    springer_api_key: str,
    ieee_api_key: str,
    core_api_key: str,
    use_url_verify: bool,
    source_order: list[str] | None,
    custom_rest_profiles: list[dict] | None,
    log,
    event,
) -> list[dict]:
    total = len(refs)
    results: list[dict] = []
    for i, ref in enumerate(refs, 1):
        key = str(ref.get("key") or f"ref[{ref.get('paragraph', i)}]")
        title_clean = strip_latex(ref.get("title", "") or ref.get("text", ""))
        author = ref.get("authors", "")
        year = ref.get("year", "")
        doi = ref.get("doi", "")
        ref_url = ref.get("url", "")

        log(f"[{i}/{total}] {key}")
        log(f"    Title: {truncate(title_clean, 90)}")
        event("entry_started", index=i, total=total, key=key, title=title_clean)

        if not title_clean:
            log("    Skipped: title could not be extracted\n")
            row = {"key": key, "title": "", "status": "skipped", "reason": "missing title", "needs_review": "Yes"}
            _verifier.apply_product_assessment(row)
            results.append(row)
            event("entry_finished", index=i, total=total, result=_verifier.printable_result(row))
            continue

        res = _verifier.verify_entry(
            title_clean,
            author,
            year,
            doi,
            threshold,
            email,
            use_openalex,
            use_dblp,
            use_semantic_scholar=use_semantic_scholar,
            use_arxiv=use_arxiv,
            use_pubmed=use_pubmed,
            use_crossref=use_crossref,
            use_springer=use_springer,
            use_ieee=use_ieee,
            use_core=use_core,
            springer_api_key=springer_api_key,
            ieee_api_key=ieee_api_key,
            core_api_key=core_api_key,
            url=ref_url,
            use_url_verify=use_url_verify,
            source_order=source_order,
            custom_rest_profiles=custom_rest_profiles,
        )
        if res.get("found"):
            res["status"] = "found"
            sim = res.get("similarity", 0) or 0
            flag = "WARN" if sim < 1.0 or res.get("needs_review") == "Yes" else "OK"
            log(f"    {flag} found [{res.get('source', '')}] (title similarity {sim:.0%})")
            if sim < 1.0:
                log(f"        Input title: {truncate(title_clean, 90)}")
                log(f"        Matched title: {truncate(res.get('matched_title', ''), 90)}")
            else:
                log(f"        Title: {truncate(res.get('matched_title', ''), 90)}")
            if res.get("venue"):
                log(f"        Venue: {res['venue']} ({res.get('year', '')})  Type: {res.get('type', '')}")
            if res.get("doi"):
                log(f"        DOI: {res['doi']}")
        else:
            res["status"] = "not_found"
            log(f"    Not found: {res.get('reason', '')}")
            if res.get("matched_title"):
                log(f"        Closest: {truncate(res['matched_title'], 90)} ({res.get('similarity', 0):.0%})")

        log(f"        Author: {_verifier.status_icon(res.get('author_check'))} {res.get('author_reason', '')}")
        if res.get("year_check") == "mismatch":
            log(f"        Year: {_verifier.status_icon('mismatch')} {res.get('year_reason', '')}")
        if res.get("doi_check") == "mismatch":
            log(f"        DOI : {_verifier.status_icon('mismatch')} {res.get('doi_reason', '')}")

        row = {"key": key, "title": title_clean, **res}
        _verifier.apply_product_assessment(row)
        results.append(row)
        event("entry_finished", index=i, total=total, result=_verifier.printable_result(row))

        log()
        if i < total:
            time.sleep(delay)
    return results


def _finalize_run(
    *,
    results: list[dict],
    total: int,
    citation_consistency: dict | None,
    output: str | None,
    csv_path: str | None,
    output_dir: str | None,
    bibfile_label: str,
    sources: str,
    threshold: float,
    app_version: str,
    log,
    event,
) -> dict:
    summary = _verifier.build_summary(results)
    counts = _verifier.summary_counts(summary, total)
    counts.update(_citation_summary_fields(citation_consistency))
    counts["report_summary"] = _verifier.build_report_summary(results, counts, citation_consistency)

    _log_summary(log, summary, counts)

    output_path = os.path.abspath(output) if output else ""
    csv_output_path = os.path.abspath(csv_path) if csv_path else ""
    if output:
        _verifier.write_markdown_report(
            output,
            bibfile=bibfile_label,
            sources=sources,
            threshold=threshold,
            total=total,
            results=results,
            summary=summary,
            citation_consistency=citation_consistency,
            app_version=app_version,
        )
        log(f"\nReport saved to: {output}")
    if csv_path:
        _verifier.write_csv_report(csv_path, results)
        log(f"CSV saved to: {csv_path}")

    artifact_paths = _write_analysis_artifacts(
        output_dir=output_dir,
        citation_consistency=citation_consistency,
    )
    counts.update({
        "bibfile": bibfile_label,
        "sources": sources,
        "output_dir": os.path.abspath(output_dir) if output_dir else "",
        "markdown_path": output_path,
        "csv_path": csv_output_path,
        "app_version": app_version,
        **artifact_paths,
    })
    event("summary", **counts)
    return {"results": results, "summary": counts}


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
                app_version: str = APP_VERSION,
                output: str | None = None, csv_path: str | None = None,
                output_dir: str | None = None, jsonl_progress: bool = False,
                human_output: bool = True) -> dict:
    """Verify pasted reference text."""
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

    text_split = _citation_consistency.split_text_body_and_references(text)
    refs = text_split["references"] if text_split.get("has_reference_section") else parse_text_references(text)
    total = len(refs)
    sources = _source_label(
        use_crossref=use_crossref,
        use_openalex=use_openalex,
        use_semantic_scholar=use_semantic_scholar,
        use_arxiv=use_arxiv,
        use_pubmed=use_pubmed,
        use_springer=use_springer,
        use_ieee=use_ieee,
        use_core=use_core,
        springer_api_key=springer_api_key,
        ieee_api_key=ieee_api_key,
        core_api_key=core_api_key,
        custom_rest_profiles=custom_rest_profiles,
        use_dblp=use_dblp,
        use_url_verify=use_url_verify,
    )
    log(f"Parsed {total} references from text; starting verification ({sources}, title threshold {threshold:.0%})\n")
    event("started", total=total, sources=sources, threshold=threshold,
          use_openalex=use_openalex, use_dblp=use_dblp,
          use_semantic_scholar=use_semantic_scholar, use_arxiv=use_arxiv,
          use_pubmed=use_pubmed, use_crossref=use_crossref,
          use_springer=use_springer and bool(springer_api_key),
          use_ieee=use_ieee and bool(ieee_api_key),
          use_core=use_core and bool(core_api_key),
          use_url_verify=use_url_verify, bibfile="pasted text")

    results = _verify_reference_rows(
        refs,
        threshold=threshold,
        delay=delay,
        email=email,
        use_openalex=use_openalex,
        use_dblp=use_dblp,
        use_semantic_scholar=use_semantic_scholar,
        use_arxiv=use_arxiv,
        use_pubmed=use_pubmed,
        use_crossref=use_crossref,
        use_springer=use_springer,
        use_ieee=use_ieee,
        use_core=use_core,
        springer_api_key=springer_api_key,
        ieee_api_key=ieee_api_key,
        core_api_key=core_api_key,
        use_url_verify=use_url_verify,
        source_order=source_order,
        custom_rest_profiles=custom_rest_profiles,
        log=log,
        event=event,
    )
    citation_consistency = _citation_consistency.check_text_citation_consistency(
        text,
        references=refs,
        parsed_split=text_split,
    )
    return _finalize_run(
        results=results,
        total=total,
        citation_consistency=citation_consistency,
        output=output,
        csv_path=csv_path,
        output_dir=output_dir,
        bibfile_label="pasted text",
        sources=sources,
        threshold=threshold,
        app_version=app_version,
        log=log,
        event=event,
    )


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
                     app_version: str = APP_VERSION,
                     output: str | None = None, csv_path: str | None = None,
                     output_dir: str | None = None, jsonl_progress: bool = False,
                     human_output: bool = True) -> dict:
    """Extract references from a .docx file and verify them."""
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
    sources = _source_label(
        use_crossref=use_crossref,
        use_openalex=use_openalex,
        use_semantic_scholar=use_semantic_scholar,
        use_arxiv=use_arxiv,
        use_pubmed=use_pubmed,
        use_springer=use_springer,
        use_ieee=use_ieee,
        use_core=use_core,
        springer_api_key=springer_api_key,
        ieee_api_key=ieee_api_key,
        core_api_key=core_api_key,
        custom_rest_profiles=custom_rest_profiles,
        use_dblp=use_dblp,
        use_url_verify=use_url_verify,
    )
    log(f"Parsed {total} references from DOCX; starting verification ({sources}, title threshold {threshold:.0%})\n")
    event("started", total=total, sources=sources, threshold=threshold,
          use_openalex=use_openalex, use_dblp=use_dblp,
          use_semantic_scholar=use_semantic_scholar, use_arxiv=use_arxiv,
          use_pubmed=use_pubmed, use_crossref=use_crossref,
          use_springer=use_springer and bool(springer_api_key),
          use_ieee=use_ieee and bool(ieee_api_key),
          use_core=use_core and bool(core_api_key),
          use_url_verify=use_url_verify, bibfile=os.path.abspath(docx_path))

    results = _verify_reference_rows(
        refs,
        threshold=threshold,
        delay=delay,
        email=email,
        use_openalex=use_openalex,
        use_dblp=use_dblp,
        use_semantic_scholar=use_semantic_scholar,
        use_arxiv=use_arxiv,
        use_pubmed=use_pubmed,
        use_crossref=use_crossref,
        use_springer=use_springer,
        use_ieee=use_ieee,
        use_core=use_core,
        springer_api_key=springer_api_key,
        ieee_api_key=ieee_api_key,
        core_api_key=core_api_key,
        use_url_verify=use_url_verify,
        source_order=source_order,
        custom_rest_profiles=custom_rest_profiles,
        log=log,
        event=event,
    )
    citation_consistency = _citation_consistency.check_docx_citation_consistency(
        docx_path,
        references=refs,
    )
    return _finalize_run(
        results=results,
        total=total,
        citation_consistency=citation_consistency,
        output=output,
        csv_path=csv_path,
        output_dir=output_dir,
        bibfile_label=os.path.abspath(docx_path),
        sources=sources,
        threshold=threshold,
        app_version=app_version,
        log=log,
        event=event,
    )


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
                    app_version: str = APP_VERSION,
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

    refs: list[dict] = []
    for i, entry in enumerate(bib_db.entries, 1):
        title = entry.get("title", "").replace("\n", " ").strip()
        url = entry.get("url", "") or entry.get("URL", "")
        if not url:
            howpub = entry.get("howpublished", "")
            if howpub:
                match = re.search(r"\\url\{([^}]+)\}", howpub)
                if match:
                    url = match.group(1)
                elif howpub.startswith("http"):
                    url = howpub
        refs.append({
            "key": entry.get("ID", "<no-key>"),
            "paragraph": entry.get("ID", f"ref-{i}"),
            "title": title,
            "authors": entry.get("author", ""),
            "year": entry.get("year", ""),
            "doi": entry.get("doi", "") or entry.get("DOI", ""),
            "url": url,
        })

    total = len(refs)
    sources = _source_label(
        use_crossref=use_crossref,
        use_openalex=use_openalex,
        use_semantic_scholar=use_semantic_scholar,
        use_arxiv=use_arxiv,
        use_pubmed=use_pubmed,
        use_springer=use_springer,
        use_ieee=use_ieee,
        use_core=use_core,
        springer_api_key=springer_api_key,
        ieee_api_key=ieee_api_key,
        core_api_key=core_api_key,
        custom_rest_profiles=custom_rest_profiles,
        use_dblp=use_dblp,
        use_url_verify=use_url_verify,
    )
    log(f"Parsed {total} BibTeX entries; starting verification ({sources}, title threshold {threshold:.0%})\n")
    event("started", total=total, sources=sources, threshold=threshold,
          use_openalex=use_openalex, use_dblp=use_dblp,
          use_semantic_scholar=use_semantic_scholar, use_arxiv=use_arxiv,
          use_pubmed=use_pubmed, use_crossref=use_crossref,
          use_springer=use_springer and bool(springer_api_key),
          use_ieee=use_ieee and bool(ieee_api_key),
          use_core=use_core and bool(core_api_key),
          use_url_verify=use_url_verify, bibfile=os.path.abspath(bibfile))

    results = _verify_reference_rows(
        refs,
        threshold=threshold,
        delay=delay,
        email=email,
        use_openalex=use_openalex,
        use_dblp=use_dblp,
        use_semantic_scholar=use_semantic_scholar,
        use_arxiv=use_arxiv,
        use_pubmed=use_pubmed,
        use_crossref=use_crossref,
        use_springer=use_springer,
        use_ieee=use_ieee,
        use_core=use_core,
        springer_api_key=springer_api_key,
        ieee_api_key=ieee_api_key,
        core_api_key=core_api_key,
        use_url_verify=use_url_verify,
        source_order=source_order,
        custom_rest_profiles=custom_rest_profiles,
        log=log,
        event=event,
    )
    citation_consistency = _citation_consistency.not_available(
        "BibTeX files do not include body text, so citation consistency was not checked."
    )
    return _finalize_run(
        results=results,
        total=total,
        citation_consistency=citation_consistency,
        output=output,
        csv_path=csv_path,
        output_dir=output_dir,
        bibfile_label=os.path.abspath(bibfile),
        sources=sources,
        threshold=threshold,
        app_version=app_version,
        log=log,
        event=event,
    )
