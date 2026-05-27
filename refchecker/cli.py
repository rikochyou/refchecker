"""RefChecker — 疑似虚构引用与参考文献元数据核验."""
import argparse
import os
import sys
import traceback

from .config import parse_source_selection, build_source_order, source_selected, test_api_keys
from .batch import verify_bib_file, verify_docx_file, verify_text
from .verifier import emit_jsonl
from .custom_rest import load_profiles_file
from .version import APP_VERSION

def main():
    # 确保 stdout/stderr 使用 UTF-8，避免 Windows GBK 控制台因 emoji 崩溃
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass

    parser = argparse.ArgumentParser(description="筛查疑似虚构引用并核验 BibTeX / DOCX 参考文献可信度")
    parser.add_argument("--version", action="version", version=f"RefChecker {APP_VERSION}")
    parser.add_argument("file", nargs="?",
                        help=".bib 或 .docx 文件路径；使用 --test-api-keys 时可省略")
    parser.add_argument("--app-version", default=APP_VERSION,
                        help="写入报告/JSONL 摘要的应用版本号，默认使用后端内置版本")
    parser.add_argument("--threshold", type=float, default=0.85,
                        help="标题相似度阈值 (0-1)，默认 0.85")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="每条文献核查后的间隔秒数；安全最小值锁定为 0.5，低于该值会自动提升")
    parser.add_argument("--email", default="",
                        help="你的邮箱 (放进 User-Agent / mailto，访问 CrossRef/OpenAlex/NCBI 更稳)")
    parser.add_argument("--sources", default="",
                        help="可选: 指定搜索链数据源及顺序，逗号分隔；严格顺序模式会按此顺序逐个查询。"
                             "如 crossref,openalex,semantic-scholar,arxiv,pubmed,dblp,url,springer,ieee,core")
    parser.add_argument("--search-mode", choices=["strict", "parallel"], default="strict",
                        help="搜索模式：strict=严格顺序（默认），parallel=快速并发仲裁")
    parser.add_argument("--doi-check", choices=["auto", "off"], default="auto",
                        help="DOI 精确核验：auto=有 DOI 时先核验（默认），off=关闭")
    parser.add_argument("--llm-parse-mode", choices=["off", "auto", "always"],
                        default=os.getenv("REFCHECKER_LLM_PARSE_MODE", "off"),
                        help="LLM field extraction: off=rules only (default); auto/always=LLM-first with rule fallback when the LLM cannot parse a field/row. The LLM only extracts fields and does not judge authenticity.")
    parser.add_argument("--llm-provider", default=os.getenv("REFCHECKER_LLM_PROVIDER", "openai-compatible"),
                        help="LLM 提供商；当前支持 openai-compatible。")
    parser.add_argument("--llm-model", default=os.getenv("REFCHECKER_LLM_MODEL", "gpt-4o-mini"),
                        help="LLM 模型名；也可用环境变量 REFCHECKER_LLM_MODEL。")
    parser.add_argument("--llm-base-url", default=os.getenv("REFCHECKER_LLM_BASE_URL", "https://api.openai.com/v1"),
                        help="OpenAI-compatible API base URL；也可用 REFCHECKER_LLM_BASE_URL。")
    parser.add_argument("--llm-api-key", default=os.getenv("REFCHECKER_LLM_API_KEY", ""),
                        help="LLM API Key；也可用环境变量 REFCHECKER_LLM_API_KEY。")
    parser.add_argument("--no-crossref", action="store_true",
                        help="不使用 CrossRef 作为搜索链数据源；DOI 精确核验仍按 --doi-check 策略独立执行")
    parser.add_argument("--no-openalex", action="store_true",
                        help="不使用 OpenAlex 兜底")
    parser.add_argument("--no-semantic-scholar", action="store_true",
                        help="不使用 Semantic Scholar 兜底")
    parser.add_argument("--no-arxiv", action="store_true",
                        help="不使用 arXiv 兜底")
    parser.add_argument("--no-pubmed", action="store_true",
                        help="不使用 PubMed 兜底")
    parser.add_argument("--no-springer", action="store_true",
                        help="不使用 Springer Nature API Key 增强源")
    parser.add_argument("--no-ieee", action="store_true",
                        help="不使用 IEEE Xplore API Key 增强源")
    parser.add_argument("--no-core", action="store_true",
                        help="不使用 CORE API Key 增强源")
    parser.add_argument("--springer-api-key", default=os.getenv("REFCHECKER_SPRINGER_API_KEY", ""),
                        help="Springer Nature Metadata API Key，也可用环境变量 REFCHECKER_SPRINGER_API_KEY")
    parser.add_argument("--ieee-api-key", default=os.getenv("REFCHECKER_IEEE_API_KEY", ""),
                        help="IEEE Xplore API Key，也可用环境变量 REFCHECKER_IEEE_API_KEY")
    parser.add_argument("--core-api-key", default=os.getenv("REFCHECKER_CORE_API_KEY", ""),
                        help="CORE API Key，也可用环境变量 REFCHECKER_CORE_API_KEY")
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
    parser.add_argument("--text", default="",
                        help="直接核验粘贴的参考文献文本（APA 格式，多条用空行分隔）")
    parser.add_argument("--test-api-keys", action="store_true",
                        help="仅测试 Springer / IEEE / CORE API Key 连通性，不核验文献文件")
    parser.add_argument("--custom-rest-profiles", default="",
                        help="高级用法：自定义 REST API Profile JSON 文件路径")
    args = parser.parse_args()

    try:
        file_path = args.file
        selected_sources = parse_source_selection(args.sources)
        custom_rest_profiles = load_profiles_file(args.custom_rest_profiles)
        custom_source_keys = [p["sourceKey"] for p in custom_rest_profiles]
        if selected_sources is not None:
            custom_rest_profiles = [
                p for p in custom_rest_profiles if p["sourceKey"] in selected_sources
            ]
            custom_source_keys = [p["sourceKey"] for p in custom_rest_profiles]
        springer_key = args.springer_api_key.strip()
        ieee_key = args.ieee_api_key.strip()
        core_key = args.core_api_key.strip()
        if args.test_api_keys:
            test_api_keys(
                selected_sources=selected_sources,
                springer_api_key=springer_key,
                ieee_api_key=ieee_key,
                core_api_key=core_key,
                use_springer=not args.no_springer,
                use_ieee=not args.no_ieee,
                use_core=not args.no_core,
                custom_rest_profiles=custom_rest_profiles,
                jsonl_progress=args.jsonl_progress,
                human_output=True,
            )
            return
        if args.text:
            verify_text(args.text, threshold=args.threshold, delay=args.delay,
                        email=args.email,
                        use_crossref=source_selected(selected_sources, "crossref", True) and not args.no_crossref,
                        use_openalex=source_selected(selected_sources, "openalex", True) and not args.no_openalex,
                        use_dblp=source_selected(selected_sources, "dblp", True) and not args.no_dblp,
                        use_semantic_scholar=source_selected(selected_sources, "semantic-scholar", True) and not args.no_semantic_scholar,
                        use_arxiv=source_selected(selected_sources, "arxiv", True) and not args.no_arxiv,
                        use_pubmed=source_selected(selected_sources, "pubmed", True) and not args.no_pubmed,
                        use_springer=source_selected(selected_sources, "springer", bool(springer_key)) and not args.no_springer,
                        use_ieee=source_selected(selected_sources, "ieee", bool(ieee_key)) and not args.no_ieee,
                        use_core=source_selected(selected_sources, "core", bool(core_key)) and not args.no_core,
                        springer_api_key=springer_key,
                        ieee_api_key=ieee_key,
                        core_api_key=core_key,
                        use_url_verify=source_selected(selected_sources, "url", True) and not args.no_url_verify,
                         source_order=build_source_order(selected_sources, custom_source_keys),
                         custom_rest_profiles=custom_rest_profiles,
                         search_mode=args.search_mode,
                         doi_check=args.doi_check,
                         llm_parse_mode=args.llm_parse_mode,
                         llm_provider=args.llm_provider,
                         llm_model=args.llm_model,
                         llm_base_url=args.llm_base_url,
                         llm_api_key=args.llm_api_key,
                         app_version=args.app_version,
                        output=args.output,
                        csv_path=args.csv,
                        output_dir=args.output_dir,
                        jsonl_progress=args.jsonl_progress,
                        human_output=True)
            return
        if not file_path:
            parser.error("请提供 .bib / .docx / .txt 文件路径，或用 --text 粘贴参考文献文本")
        ext = os.path.splitext(file_path)[1].lower()
        common_args = dict(
            threshold=args.threshold,
            delay=args.delay,
            email=args.email,
            use_crossref=source_selected(selected_sources, "crossref", True) and not args.no_crossref,
            use_openalex=source_selected(selected_sources, "openalex", True) and not args.no_openalex,
            use_dblp=source_selected(selected_sources, "dblp", True) and not args.no_dblp,
            use_semantic_scholar=source_selected(selected_sources, "semantic-scholar", True) and not args.no_semantic_scholar,
            use_arxiv=source_selected(selected_sources, "arxiv", True) and not args.no_arxiv,
            use_pubmed=source_selected(selected_sources, "pubmed", True) and not args.no_pubmed,
            use_springer=source_selected(selected_sources, "springer", bool(springer_key)) and not args.no_springer,
            use_ieee=source_selected(selected_sources, "ieee", bool(ieee_key)) and not args.no_ieee,
            use_core=source_selected(selected_sources, "core", bool(core_key)) and not args.no_core,
            springer_api_key=springer_key,
            ieee_api_key=ieee_key,
            core_api_key=core_key,
            use_url_verify=source_selected(selected_sources, "url", True) and not args.no_url_verify,
            source_order=build_source_order(selected_sources, custom_source_keys),
            custom_rest_profiles=custom_rest_profiles,
            search_mode=args.search_mode,
            doi_check=args.doi_check,
            llm_parse_mode=args.llm_parse_mode,
            llm_provider=args.llm_provider,
            llm_model=args.llm_model,
            llm_base_url=args.llm_base_url,
            llm_api_key=args.llm_api_key,
            app_version=args.app_version,
            output=args.output,
            csv_path=args.csv,
            output_dir=args.output_dir,
            jsonl_progress=args.jsonl_progress,
            human_output=True,
        )
        if ext == ".docx":
            verify_docx_file(file_path, **common_args)
        elif ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                verify_text(f.read(), **common_args)
        else:
            verify_bib_file(file_path, **common_args)
    except Exception as exc:
        if args.jsonl_progress:
            emit_jsonl("error", message=str(exc), traceback=traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
