# RefChecker：参考文献核验工具

> 当前稳定版：**v1.2.0**；上一稳定版：**v1.1.0**

RefChecker 用于核验 BibTeX、Word DOCX、TXT 或粘贴文本中的参考文献，重点检查标题、作者、年份、DOI、URL 可访问性、正文引用一致性，以及多数据源匹配结果。输出为 Markdown 报告、CSV 表格和必要的 JSON 分析文件。

> 说明：RefChecker 提供自动化核验线索，不替代最终人工学术判断。未匹配不代表文献一定不存在，匹配成功也不代表引用完全正确。

## 功能

- 多数据源检索：CrossRef、OpenAlex、Semantic Scholar、arXiv、PubMed、DBLP。
- API Key 增强源：Springer Nature、IEEE Xplore、CORE。
- 自定义 REST API Profile：支持 GET/POST、query/header/bearer 等配置；既可接入返回结构化元数据的数据库，也可接入 Brave Search/Research 这类只返回网页结果的辅助证据源。
- DOI 前置精确核验：有 DOI 时先核验 DOI 是否可解析、是否指向同一篇论文；该步骤独立于搜索链。
- URL 核验：支持 GitHub、HuggingFace 和通用网页可访问性检查。
- DOCX / TXT 正文引用一致性检查。
- 风险分级、置信度、修复建议和规范引用候选输出。
- 桌面端数据源 API Key 输入框支持“小眼睛”显示/隐藏，便于检查 Key 是否粘贴正确。
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
- `--sources openalex,semantic-scholar,crossref`：设置搜索链和查询顺序。
- `--search-mode strict|parallel`：搜索模式；默认 `strict` 会按搜索链逐个查询并在高可信命中后停止，`parallel` 为快速并发仲裁，排序只作为接近时的 tie-breaker。
- `--doi-check auto|off`：DOI 精确核验；默认 `auto` 表示有 DOI 时先做独立 DOI 核验，`off` 表示关闭。
- `--no-url-verify`：关闭 URL 核验。
- `--springer-api-key` / `--ieee-api-key` / `--core-api-key`：配置增强源。
- `--custom-rest-profiles profiles.json`：加载自定义 REST API Profile。Brave 示例见 `CUSTOM_REST_BRAVE_SEARCH.md` 和 `examples/brave_search_custom_rest_profile.example.json`。

### LLM 辅助解析（可选）

当选中文献或粘贴文本格式很乱、规则解析抓不到标题/作者/年份时，可以启用大模型辅助解析：

```bash
python check_bib_crossref.py references.txt --llm-parse-mode auto --llm-model gpt-4o-mini --llm-base-url https://api.openai.com/v1
```

配置方式：

- `--llm-parse-mode off|auto|always`：默认 `off`；`auto` 为 LLM 优先：先用大模型解析，缺字段时回退本地规则；`always` 每条都调用。
- `REFCHECKER_LLM_API_KEY` 或 `--llm-api-key`：LLM API Key（桌面端会通过本机环境传给后端）。
- LLM 只提取原文明确出现的 `title/authors/year/doi/url` 字段，不参与文献真假判断，也不补造缺失信息。

## 自定义数据源与 Brave Search/Research API

RefChecker 的 Custom REST Profile 可以接入两类外部数据源：

1. **结构化文献元数据源**：返回标题、作者、年份、DOI、期刊/会议等字段，可参与常规元数据匹配。
2. **网页搜索证据源**：例如 Brave Search/Research API，通常只返回网页标题、链接和摘要，不返回完整文献元数据。

对 Brave 这类网页结果源，RefChecker v1.2.0 会把它展示为 **Web Evidence / 辅助网页证据**：

- 不把网页搜索结果伪装成 CrossRef/OpenAlex 那样的文献元数据。
- 不用 Brave 结果自动补造规范引用。
- 在桌面端、报告和浏览器扩展里展示可打开的结果链接，方便用户直接点开网页人工确认。

示例配置文件：

```text
examples\brave_search_custom_rest_profile.example.json
```

使用时把示例复制到自己的本地配置文件或桌面端自定义数据源编辑器里，再填入自己的 API Key。不要把真实 Key 写回 `examples/`，也不要提交含 Key 的 `custom_rest_profiles.json`。

Brave 常见配置要点：

- `endpoint`: `https://api.search.brave.com/res/v1/web/search`
- `authType`: `header`
- `apiKeyHeader`: `X-Subscription-Token`
- `resultsPath`: `web.results`
- `evidenceType`: `web`

如果测试返回 HTTP `402`，通常表示 Brave API 订阅、额度、计费或账号权限不满足当前请求；若返回 `401/403`，优先检查 Key、Header 名称和权限。详细说明见 `CUSTOM_REST_BRAVE_SEARCH.md`。

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
- 浏览器扩展和桌面端使用同一套流程：先做 DOI 精确核验，再按严格顺序/快速并发搜索链查询，结果中展示 DOI 状态、实际查询路径和最终采用来源。
- 浏览器扩展会把 Brave/Web Evidence 结果展示为可点击链接，点击后直接打开对应网页；这些结果只作为辅助证据，不替代 DOI/数据库核验。

安装和使用说明见：`BROWSER_EXTENSION_CLAUDE_WEB.md`。

正式版发布说明见：`RELEASE_NOTES_v1.2.0.md`。

## 桌面版打包

Windows 打包脚本：

```powershell
.\tool\package_windows.ps1
```

该脚本会构建 Python 后端、Flutter Windows 应用，并生成便携版 zip。

桌面端启动时会检查 GitHub Releases；如果发现高于当前版本的发布包，会在顶部显示更新提示和下载入口。当前为通知式更新，用户仍需手动下载并替换便携版目录。

## 安全与隐私

- 便携版发布包不会复制本机 `settings.json`、`.env`、`custom_rest_profiles.json`、API Key、运行日志或生成报告。
- 打包脚本会在创建 ZIP 前执行 secret guard；发布前仍建议额外扫描 `dist_portable\RefChecker_portable_v版本号` 和对应 ZIP。
- 示例配置中的 `apiKey` 必须保持空字符串；真实 Key 只放在本机桌面端设置、环境变量或不提交的本地 profile 文件里。

## macOS Gatekeeper note

If macOS reports that the app is damaged or from an unidentified developer, clear the quarantine attribute and open it again:

```bash
xattr -cr /Applications/refchecker_desktop.app
```
