# GitHub 项目描述建议

## 仓库短描述（推荐）

BibTeX 文献批量核验工具：基于 CrossRef / OpenAlex / DBLP 三源交叉验证，支持 DOI 精确查询、标题相似度匹配、作者与年份一致性检查，生成 Markdown / CSV 报告。

## English description

A Python tool for batch-verifying BibTeX references against CrossRef, OpenAlex, and DBLP — checks DOI, title similarity, author consistency, and year accuracy, then generates Markdown/CSV reports for manual review.

## 可选仓库 Topics

```text
bibtex
crossref
openalex
dblp
reference-checker
citation-verification
academic-writing
python
metadata-validation
research-tools
doi
```

## 较详细项目介绍

RefChecker 是一个面向论文写作与参考文献整理场景的 BibTeX 批量核验工具。它会解析 `.bib` 文件中的文献条目，通过 DOI 精确查询、标题相似度匹配、作者列表比对和年份一致性检查四个维度进行交叉验证。数据源覆盖 CrossRef（期刊/会议）、OpenAlex（预印本/广覆盖）和 DBLP（计算机科学），并将核验结果输出为 Markdown 报告和 CSV 表格，帮助用户快速定位可能存在标题错误、作者不一致、年份偏差、DOI 缺失或需要进一步人工确认的引用记录。
