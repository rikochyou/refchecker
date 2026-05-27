# GitHub 项目描述建议

## 仓库短描述（推荐）

AI 幻觉引用与参考文献可信度核验工具：筛查疑似 AI 编造、幻觉引用、误引或元数据异常的 BibTeX / DOCX / TXT 参考文献，基于 DOI 精确核验、CrossRef / OpenAlex / Semantic Scholar / arXiv / PubMed / Springer Nature / IEEE Xplore / CORE / DBLP / URL 多源交叉验证，支持 Claude Desktop MCP、Chrome/Edge 浏览器扩展、API Key 增强源和自定义 REST API Profile（含 Brave/Web Evidence 辅助网页证据），输出风险等级、置信度、建议操作和 Markdown / CSV 报告。

## English description

A desktop, CLI, MCP, and browser-extension tool for screening potentially AI-hallucinated, fabricated, misquoted, or metadata-inconsistent BibTeX/DOCX/TXT references with DOI exact checks and CrossRef, OpenAlex, Semantic Scholar, arXiv, PubMed, Springer Nature, IEEE Xplore, CORE, DBLP, URL, and custom REST sources — including Brave/Web Evidence as auxiliary clickable web evidence — then generates risk/confidence reports in Markdown/CSV.

## 可选仓库 Topics

```text
bibtex
docx
crossref
openalex
semantic-scholar
arxiv
pubmed
springer
ieee-xplore
core
dblp
reference-risk
ai-hallucination
fabricated-references
reference-checker
citation-verification
academic-writing
python
flutter
metadata-validation
research-tools
doi
brave-search
custom-rest-api
mcp
chrome-extension
edge-extension
```

## 较详细项目介绍

RefChecker 是一个面向论文写作、综述整理和 AI 辅助写作场景的参考文献可信度核验工具。它可以解析 `.bib`、`.docx`、`.txt` 或粘贴文本参考文献，通过 DOI 精确查询、标题相似度匹配、作者列表比对、年份一致性检查和 URL 可访问性验证进行交叉核验。数据源覆盖 CrossRef（期刊/会议）、OpenAlex（预印本/广覆盖）、Semantic Scholar（跨学科/引用图谱）、arXiv（预印本）、PubMed（生物医学）、Springer Nature、IEEE Xplore、CORE、DBLP（计算机科学）以及 HuggingFace / GitHub / 通用网页；高级用户可通过来源白名单、API Key 和自定义 REST API Profile 接入指定数据库、机构内部检索服务或 Brave Search/Research 这类网页证据源。桌面应用之外，RefChecker 也提供 Claude Desktop MCP 和 Chrome/Edge 浏览器扩展，方便在 Claude 网页版或普通网页中核查选中文献和粘贴链接。核验结果输出为带风险等级、置信度和建议操作的 Markdown 报告与 CSV 表格，帮助用户优先排查疑似 AI 编造文献、幻觉引用、严重错引、DOI 不一致、首作者不一致、年份偏差或元数据缺失的引用记录。
