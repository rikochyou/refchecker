# Brave Search/Research API 自定义数据源指南

本文说明如何在 RefChecker v1.2.0 中通过 **自定义 REST API Profile** 使用 Brave Search/Research API。

## 1. 先理解 Brave 返回的是什么

Brave Search/Research API 返回的是网页搜索结果，通常包含：

- 网页标题
- URL
- 摘要/description
- 站点或 profile 信息

它一般不返回 CrossRef/OpenAlex 那样完整、可直接比对的文献元数据，例如作者列表、出版年份、DOI、期刊/会议。因此 RefChecker 会把 Brave 结果标记为：

```text
Web Evidence / 辅助网页证据
```

这意味着：

- Brave 可以帮助你找到疑似相关网页、论文页面、机构页面或预印本页面。
- Brave 结果会在桌面端、Markdown 报告、CSV 和浏览器扩展里显示为可打开链接。
- Brave 结果本身不等于“文献已核验通过”，也不会被用来自动补造规范引用。
- 最终仍建议结合 DOI、CrossRef、OpenAlex、Semantic Scholar、PubMed、DBLP 等结构化数据源确认。

## 2. 推荐配置

示例文件位于：

```text
examples\brave_search_custom_rest_profile.example.json
```

核心字段如下：

```json
{
  "id": "brave-search",
  "name": "Brave Web Evidence",
  "enabled": true,
  "evidenceType": "web",
  "endpoint": "https://api.search.brave.com/res/v1/web/search",
  "method": "GET",
  "authType": "header",
  "apiKeyHeader": "X-Subscription-Token",
  "apiKey": "",
  "queryParams": {
    "q": "\"{title}\" DOI scholarly article",
    "count": "10",
    "result_filter": "web",
    "search_lang": "en",
    "country": "US",
    "safesearch": "moderate",
    "text_decorations": "false"
  },
  "resultsPath": "web.results",
  "titlePath": "title",
  "urlPath": "url",
  "venuePath": "profile.name",
  "typePath": "type",
  "snippetPath": "description"
}
```

请保持仓库示例里的 `apiKey` 为空。真实 Key 只填在你本机的桌面端设置或不提交的本地 profile 文件中。

## 3. 桌面端使用步骤

1. 打开 RefChecker 桌面版。
2. 进入数据源/API Key 设置。
3. 添加或编辑 **Custom REST API** 数据源。
4. 把 `examples\brave_search_custom_rest_profile.example.json` 中的配置复制进去。
5. 填入自己的 Brave API Key。
6. 使用 API Key 输入框右侧的小眼睛按钮临时显示/隐藏 Key，确认没有粘贴错。
7. 点击测试连接。
8. 在搜索链中启用该自定义源。

推荐排序：

```text
CrossRef / OpenAlex / Semantic Scholar / PubMed / DBLP 等结构化源在前，
Brave Web Evidence 放在后面作为辅助证据。
```

## 4. 命令行使用

把示例复制为自己的本地文件，例如：

```text
C:\tmp\refchecker_custom_rest_profiles.json
```

然后运行：

```powershell
python check_bib_crossref.py refs.bib `
  --custom-rest-profiles C:\tmp\refchecker_custom_rest_profiles.json `
  --sources crossref,openalex,semantic-scholar,custom:brave-search `
  --output-dir results
```

注意：如果本地 profile 文件含真实 Key，不要提交到 Git。项目 `.gitignore` 已建议忽略 `custom_rest_profiles*.json`、`.env` 和本地 settings 文件。

## 5. 浏览器扩展如何展示

浏览器扩展会沿用桌面端/本地 HTTP 服务配置的自定义数据源。Brave 返回的网页结果会显示为：

- 辅助证据区块
- 可点击标题或 URL
- 摘要 snippet
- “Web Evidence” 提示

点击链接会直接打开对应网页。请把它当作“打开网页人工核对”的入口，而不是数据库元数据匹配结论。

## 6. 常见 HTTP 状态

| 状态 | 常见含义 | 建议 |
| --- | --- | --- |
| `200` | 请求成功 | 若记录数为 0，检查 `resultsPath` 和查询模板 |
| `401/403` | Key、Header 或权限错误 | 检查 `apiKeyHeader` 是否为 `X-Subscription-Token`，确认 Key 有权限 |
| `402` | 订阅、额度、计费或账号权限不足 | 到 Brave 控制台检查套餐、余额、额度和 API 权限 |
| `429` | 请求过多/触发限流 | 降低并发或等待额度恢复 |
| 其它 4xx/5xx | 参数或服务端错误 | 检查 endpoint、queryParams、账号权限和 Brave 返回信息 |

## 7. 安全提醒

- 不要把真实 API Key 写入 `examples/`。
- 不要把含 Key 的 `custom_rest_profiles.json`、`.env` 或 settings 文件提交到 Git。
- 发布包不会复制本机 settings、API Key、`.env`、运行日志或生成报告。
- 如果准备发布，请同时扫描目录包和 ZIP 包，确认不存在 `sk-...`、`Bearer ...`、`X-Subscription-Token: <真实值>` 等敏感内容。
