# RefChecker 网页版浏览器扩展

这个方案用于解决：Claude 网页版或其他网页输出的文献链接可能不准确，用户不想切换到 RefChecker 桌面应用再核查。

实现方式：

1. 打开 RefChecker 桌面版，软件会自动启动本机 HTTP 服务。
2. Chrome / Edge 加载本项目的浏览器扩展。
3. 核查普通参考文献时，用户在 Claude 网页版或其他普通网页选中完整参考文献正文。
4. 核查链接跳转是否指错论文时，用户右键复制完整 URL/DOI，并粘贴到扩展弹窗里的“粘贴链接核查”。
5. 扩展把文本或粘贴链接发送到本机 RefChecker，网页右侧显示核查结果、正确 DOI/URL、候选修正版引用和报告路径。
6. 如果粘贴内容包含 DOI，RefChecker 会先做 DOI 精确核验，再继续按用户配置的搜索链查询。
7. 如果桌面端配置了 Brave/Web Evidence 自定义数据源，扩展会把返回的网页结果显示为可点击链接，方便直接打开核对。

## 1. 启动本地服务

推荐方式：直接打开 RefChecker 桌面版。桌面版启动后会自动拉起：

```text
http://127.0.0.1:8765
```

桌面端启动的本地服务会绑定桌面端进程，并通过 parent PID + heartbeat 文件双重监控；关闭 RefChecker 后服务会自动退出。若检测到旧实例，桌面端会先尝试调用本地 `/shutdown` 关闭旧服务，再重新启动一个由当前窗口接管的服务。

手动备用方式：在项目目录运行：

```powershell
python .\refchecker_http_server.py
```

默认同样监听：

```text
http://127.0.0.1:8765
```

测试服务：

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```

如需换端口：

```powershell
python .\refchecker_http_server.py --port 8777
```

本地服务也支持默认核验策略参数；扩展请求里未显式传入时会使用这些默认值：

```powershell
python .\refchecker_http_server.py --search-mode strict --doi-check auto --llm-parse-mode off
```

如果要让插件核查“选中文献/粘贴文献”时启用大模型辅助解析，请先在桌面端高级设置里填写 LLM API Key，或手动设置 `REFCHECKER_LLM_API_KEY` 后启动本地服务。插件只传递 `llm_parse_mode`，不保存 API Key。

## 2. 安装浏览器扩展

Chrome / Edge：

1. 打开扩展管理页：
   - Chrome：`chrome://extensions`
   - Edge：`edge://extensions`
2. 开启“开发者模式”。
3. 点击“加载已解压的扩展”。
4. 选择目录：

```text
C:\Users\lizzi\Desktop\Reference_Check\refcheker\browser_extension\refchecker_claude
```

## 3. 使用

> 注意：短标签/隐藏链接自动识别已移除。链接核查请复制完整 URL/DOI 到插件面板的“粘贴链接核查”；选中文本流程只核查完整参考文献正文。

打开 Claude 网页版或其他需要核查的普通网页，例如：

```text
https://claude.ai
```

### 3.1 核查完整参考文献正文

选中网页中的完整参考文献正文，然后任选一种方式：

- 点击选区附近出现的“RefChecker 核查”浮动按钮。
- 右键选择“用 RefChecker 核查选中文献”。
- 点击浏览器扩展图标，再点“核查选中文本”。

核查结果会显示在网页右侧面板中。

### 3.2 核查网页链接是否指错论文

适用于 AI 网页显示“PNAS”“arXiv”“论文标题”等链接文字，但点进去发现真实目标是另一篇论文的情况：

1. 在网页里右键该链接，选择“复制链接地址”。
2. 点击浏览器右上角 RefChecker 扩展图标。
3. 把完整 URL/DOI 粘贴到“粘贴链接核查”输入框。
4. 如果需要比对网页显示内容，把 AI 网页显示的论文标题、作者或附近上下文粘贴到“页面显示标题/作者（可选）”。
5. 点击“核查粘贴链接”。

不要只选中 `arXiv`、`PNAS` 这类短标签；短标签本身不会再被当作隐藏链接自动解析。

> 扩展支持普通 `http://` / `https://` 页面；浏览器内置页面（如 `chrome://extensions`）、Chrome Web Store、部分 PDF/安全页面通常不允许扩展注入侧边栏。

## 4. 输出内容

侧边栏采用“决策型”展示：

- 顶部结论卡：正常 / 需确认 / 高风险、核心问题、建议动作。
- 关键对比卡：输入标题 vs DOI 指向标题 / 数据源匹配标题。
- 流程标签：DOI 核验、解析方式、搜索模式、搜索链、实际查询路径、最终采用来源。
- 可操作按钮：打开 DOI、打开候选 DOI/URL、复制候选修正版。
- Brave/Web Evidence：展示前几条网页搜索结果，标题/URL 可直接点击打开；这些结果只作为辅助网页证据。
- 证据详情默认折叠：作者/年份/DOI 对比、完整查询路径、报告和 CSV 路径。

本地服务会默认把报告写入：

```text
refchecker_web_output\YYYYMMDD_HHMMSS\
```

也可以在扩展弹窗里设置输出目录。

### 4.1 Brave/Web Evidence 展示

Brave Search/Research API 通常只返回网页标题、URL 和摘要，不返回作者、年份、DOI 等结构化文献元数据。因此扩展不会把 Brave 结果当成“已匹配文献”，而是显示为辅助证据：

- 标题或 URL 可点击，点击后在浏览器中打开对应页面。
- 摘要只用于快速判断网页是否相关。
- 仍需结合 DOI 核验、CrossRef/OpenAlex/Semantic Scholar 等结构化数据源做最终判断。

如果想启用 Brave，请先在 RefChecker 桌面端的数据源设置里添加自定义 REST Profile。配置方法见 `CUSTOM_REST_BRAVE_SEARCH.md`。

## 5. 本地 HTTP API

健康检查：

```http
GET /health
```

核查选中文本：

```http
POST /check-text
Content-Type: application/json

{
  "text": "Smith, J. (2020). A Test Paper. Journal. https://doi.org/10.xxxx/demo",
  "threshold": 0.85,
  "sources": "openalex,semantic-scholar,crossref",
  "search_mode": "strict",
  "doi_check": "auto",
  "llm_parse_mode": "auto",
  "output_dir": "C:\\tmp\\refchecker_out"
}
```

核查粘贴的完整链接：

```http
POST /check-text
Content-Type: application/json

{
  "text": "https://doi.org/10.xxxx/demo",
  "threshold": 0.85,
  "search_mode": "strict",
  "doi_check": "auto",
  "links_only": true,
  "links": [
    {
      "text": "网页显示的论文标题或链接标签",
      "href": "https://doi.org/10.xxxx/demo",
      "surroundingText": "可选：网页附近上下文"
    }
  ]
}
```

返回 JSON 中包含：

- `summary`
- `priority_items`
- `items`
- `corrected_references`
- `paths`
- `link_checks`（仅粘贴完整 URL/DOI 核查时返回）

## 6. 注意事项

- 扩展默认只访问本机 `127.0.0.1` 的 RefChecker 服务；如果你在本地服务/桌面端启用了 LLM 辅助解析，待解析的引用文本会由本地服务发送到你配置的 LLM API。
- RefChecker 仍会访问 CrossRef、OpenAlex、PubMed 等外部数据库进行核验。
- 链接核查请复制完整 URL/DOI 到插件面板粘贴，不要只选中 arXiv / PNAS 这类短标签。
- 自动校正结果是候选建议，最终仍需人工打开 DOI/出版社页面确认。

## 7. 常见问题

### 点击核查后一直没有结果

1. 确认 RefChecker 桌面版已经打开；桌面版会自动启动本地 HTTP 服务。
2. 在扩展面板点击“测试连接”，应返回 RefChecker 版本号。
3. 如果刚更新过扩展，请到 `chrome://extensions` 或 `edge://extensions` 点击 RefChecker 的“重新加载”，再刷新目标网页。
4. 选中文本核查请选中完整参考文献；链接核查请粘贴完整 URL/DOI。

### 绿色浮动按钮不想在所有网页出现

打开扩展面板，关闭“选中文本后显示绿色浮动按钮”。关闭后仍可使用右键菜单或扩展面板按钮核查选中文本。

### 结果面板里 CrossRef 看起来先出现怎么办

DOI 精确核验是前置强校验，不属于搜索链；它可能使用 DOI 元数据解析，但会在结果中显示为“DOI 核验”。真正的数据库搜索链会按“搜索模式”和“数据源优先级”执行，并在面板里显示“搜索链”“实际查询路径”和“最终采用”。

### Brave 测试返回 402 怎么办

HTTP `402` 一般表示 Brave API 订阅、额度、计费或账号权限不满足当前请求，不是浏览器扩展展示问题。先检查 Brave 控制台中的套餐/额度，再确认 Profile 里使用的是：

- `authType`: `header`
- `apiKeyHeader`: `X-Subscription-Token`
- `endpoint`: `https://api.search.brave.com/res/v1/web/search`

不要把真实 API Key 写进仓库示例文件或提交到 Git。
