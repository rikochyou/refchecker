# RefChecker 网页版浏览器扩展

这个方案用于解决：Claude 网页版或其他网页输出的文献链接可能不准确，用户不想切换到 RefChecker 桌面应用再核查。

实现方式：

1. 打开 RefChecker 桌面版，软件会自动启动本机 HTTP 服务。
2. Chrome / Edge 加载本项目的浏览器扩展。
3. 核查普通参考文献时，用户在 Claude 网页版或其他普通网页选中完整参考文献正文。
4. 核查链接跳转是否指错论文时，用户右键复制完整 URL/DOI，并粘贴到扩展弹窗里的“粘贴链接核查”。
5. 扩展把文本或粘贴链接发送到本机 RefChecker，网页右侧显示核查结果、正确 DOI/URL、候选修正版引用和报告路径。

## 1. 启动本地服务

推荐方式：直接打开 RefChecker 桌面版。桌面版启动后会自动拉起：

```text
http://127.0.0.1:8765
```

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

侧边栏会显示：

- 总数、找到、未找到、需核查数量。
- 重点问题和风险等级。
- 正确 DOI/URL 候选。
- DOI/作者/年份问题说明。
- 候选修正版 APA 引用。
- `report.md` 和 `result.csv` 的本地路径。

本地服务会默认把报告写入：

```text
refchecker_web_output\YYYYMMDD_HHMMSS\
```

也可以在扩展弹窗里设置输出目录。

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
  "sources": "crossref,openalex,semantic-scholar",
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

- 扩展不会把内容发到第三方服务；它只访问本机 `127.0.0.1` 的 RefChecker 服务。
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
