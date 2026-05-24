#!/usr/bin/env python3
"""RefChecker — AI 幻觉引用与参考文献元数据核验 (向后兼容包装器)。

本文件从 refchecker/ 包重新导出所有公共 API，
保持 `import check_bib_crossref` 的向后兼容性。
"""

# ——— 标准库 re-export（测试直接在 backend 命名空间中使用 requests）———
import requests  # noqa: F401

# ——— 文本工具 ———
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

# ——— 作者解析与比较 ———
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

# ——— 数据源搜索 ———
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

# ——— URL 验证 ———
from refchecker.url_verify import (  # noqa: F401, E402
    detect_url_platform,
    verify_general_url,
    verify_github,
    verify_huggingface,
    verify_url_resource,
)

# ——— 核验引擎 + 评估 + 报告 ———
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

# ——— DOCX / APA 解析 ———
from refchecker.docx_parser import (  # noqa: F401, E402
    _apa_authors_to_bibtex,
    extract_references_from_docx,
    parse_reference_text,
    parse_text_references,
)

# ——— 批量处理 ———
from refchecker.batch import (  # noqa: F401, E402
    verify_bib_file,
    verify_docx_file,
    verify_text,
)

# ——— 源选择 + API Key 测试 ———
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

# ——— 模块引用（测试 monkeypatch 需要）———
from refchecker import verifier, sources, url_verify, batch  # noqa: F401, E402

# ——— CLI ———
from refchecker.cli import main  # noqa: F401, E402


if __name__ == "__main__":
    main()
