#!/usr/bin/env python3
"""Backward-compatible wrapper for the RefChecker backend package."""

# Standard-library / third-party symbols kept for compatibility with tests and older imports.
import requests  # noqa: F401

from refchecker.utils import (  # noqa: F401, E402
    NAME_PARTICLES,
    NAME_SUFFIXES,
    clean_doi,
    compare_doi,
    compare_year,
    extract_year,
    normalize_ascii,
    normalize_title,
    strip_latex,
    title_similarity,
    truncate,
)
from refchecker.author import (  # noqa: F401, E402
    author_display_list,
    author_matches,
    candidate_score,
    compare_author_lists,
    family_matches,
    first_author_lastname,
    initials_compatible,
    match_indices,
    parse_author_name,
    split_bibtex_author_field,
)
from refchecker.sources import (  # noqa: F401, E402
    arxiv_author_list,
    build_arxiv_result,
    build_core_result,
    build_crossref_result,
    build_dblp_result,
    build_ieee_result,
    build_openalex_result,
    build_pubmed_result,
    build_semantic_scholar_result,
    build_springer_result,
    core_author_list,
    crossref_author_list,
    dblp_author_list,
    ieee_author_list,
    openalex_author_list,
    pubmed_author_list,
    search_arxiv,
    search_core,
    search_crossref,
    search_crossref_by_doi,
    search_dblp,
    search_ieee,
    search_openalex,
    search_pubmed,
    search_semantic_scholar,
    search_springer,
    semantic_scholar_author_list,
    springer_author_list,
)
from refchecker.url_verify import (  # noqa: F401, E402
    detect_url_platform,
    verify_general_url,
    verify_github,
    verify_huggingface,
    verify_url_resource,
)
from refchecker.verifier import (  # noqa: F401, E402
    CONFIDENCE_EXPLANATION,
    CONFIDENCE_SCALE,
    apply_product_assessment,
    assess_risk_level,
    build_summary,
    confidence_score,
    emit_jsonl,
    enrich_result,
    printable_result,
    risk_badge_markdown,
    risk_color,
    risk_label,
    safe_table_text,
    status_icon,
    suggested_action,
    summary_counts,
    verify_entry,
    write_csv_report,
    write_markdown_report,
)
from refchecker.docx_parser import (  # noqa: F401, E402
    _apa_authors_to_bibtex,
    extract_references_from_docx,
    parse_reference_text,
    parse_text_references,
)
from refchecker.batch import (  # noqa: F401, E402
    verify_bib_file,
    verify_docx_file,
    verify_text,
)
from refchecker.config import (  # noqa: F401, E402
    API_KEY_TEST_QUERY,
    API_KEY_TEST_TIMEOUT,
    DEFAULT_SOURCE_ORDER,
    SOURCE_ALIASES,
    build_source_order,
    parse_source_selection,
    source_selected,
    test_api_keys,
    test_core_api_key,
    test_ieee_api_key,
    test_springer_api_key,
)
from refchecker.citation_consistency import (  # noqa: F401, E402
    check_citation_consistency,
    check_docx_citation_consistency,
    check_text_citation_consistency,
    extract_body_citations,
    split_docx_body_and_references,
    split_text_body_and_references,
)
from refchecker.version import APP_VERSION  # noqa: F401, E402

from refchecker import verifier, sources, url_verify, batch, citation_consistency  # noqa: F401, E402
from refchecker.cli import main  # noqa: F401, E402

if __name__ == "__main__":
    main()
