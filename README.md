# RefChecker：参考文献核验工具

> 当前测试版：**v1.2.0-beta.1**；上一稳定版：**v1.1.0**

RefChecker 用于核验 BibTeX、Word DOCX、TXT 或粘贴文本中的参考文献，重点检查标题、作者、年份、DOI、URL 可访问性、正文引用一致性，以及多数据源匹配结果。输出为 Markdown 报告、CSV 表格和必要的 JSON 分析文件。

> 说明：RefChecker 提供自动化核验线索，不替代最终人工学术判断。未匹配不代表文献一定不存在，匹配成功也不代表引用完全正确。

## 功能

- 多数据源检索：CrossRef、OpenAlex、Semantic Scholar、arXiv、PubMed、DBLP。
- API Key 增强源：Springer Nature、IEEE Xplore、CORE。
- 自定义 REST API Profile：支持 GET/POST、query/header/bearer 等配置。
- DOI 精确核验：优先使用 DOI 精确查询和 DOI 一致性检查。
- URL 核验：支持 GitHub、HuggingFace 和通用网页可访问性检查。
- DOCX / TXT 正文引用一致性检查。
- 风险分级、置信度、修复建议和规范引用候选输出。
- 桌面应用、命令行、Claude Desktop MCP、Claude 网页版/普通网页浏览器扩展四种使用方式。

## 安装依赖

需要 Python 3.8+：

```bash
pip install -r requirements.txt
```

## 命令行使用

核验 BibTeX：

```bash
python check_bib_crossref.py refs.bib --output-dir results/
```

核验 Word 文档：

```bash
python check_bib_crossref.py References.docx --output-dir results/
```

核验 TXT：

```bash
python check_bib_crossref.py references.txt --output-dir results/
```

核验粘贴文本：

```bash
python check_bib_crossref.py --text "Smith, J. (2020). A Test Paper. Journal." --output-dir results/
```

常用参数：

- `--threshold 0.85`：标题相似度阈值。
- `--sources crossref,openalex,semantic-scholar`：设置数据源优先级。
- `--no-url-verify`：关闭 URL 核验。
- `--springer-api-key` / `--ieee-api-key` / `--core-api-key`：配置增强源。
- `--custom-rest-profiles profiles.json`：加载自定义 REST API Profile。

## 输出文件

指定 `--output-dir` 后默认生成：

- `report.md`：Markdown 报告。
- `result.csv`：表格结果。
- `citation_consistency.json`：正文引用一致性结果（适用于 DOCX / 含正文的 TXT）。

## Claude Desktop MCP

如果用户希望留在 Claude Desktop 里直接核验参考文献，不想来回切换应用，可以使用本项目的本地 MCP server：

```powershell
python .\refchecker_mcp_server.py
```

Claude Desktop 配置和使用方法见：`MCP_CLAUDE_DESKTOP.md`。

## Claude 网页版浏览器扩展

如果用户在 Claude 网页版或其他网页里看到可疑参考文献链接，可以打开 RefChecker 桌面版自动启动本地 HTTP 服务，并加载浏览器扩展。手动备用启动方式：

```powershell
python .\refchecker_http_server.py
```

扩展目录：

```text
browser_extension\refchecker_claude
```

推荐使用方式：

- 核查普通参考文献：选中完整参考文献正文，再点网页浮动按钮、右键菜单或扩展面板里的“核查选中文本”。
- 核查 AI 网页给出的跳转链接是否指错论文：右键复制完整 URL/DOI，粘贴到扩展面板的“粘贴链接核查”再运行。
- 短标签/隐藏链接自动识别已移除；不要只选中 `arXiv`、`PNAS` 这类短标签进行链接核查。

安装和使用说明见：`BROWSER_EXTENSION_CLAUDE_WEB.md`。

本测试版发布说明见：`RELEASE_NOTES_v1.2.0-beta.1.md`。

## 桌面版打包

Windows 打包脚本：

```powershell
.\tool\package_windows.ps1
```

该脚本会构建 Python 后端、Flutter Windows 应用，并生成便携版 zip。

## macOS Gatekeeper note

If macOS reports that the app is damaged or from an unidentified developer, clear the quarantine attribute and open it again:

```bash
xattr -cr /Applications/refchecker_desktop.app
```
