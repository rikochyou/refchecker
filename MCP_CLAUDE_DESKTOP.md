# RefChecker MCP for Claude Desktop

这个方案把 RefChecker 后端注册成 Claude Desktop 的本地 MCP 工具。用户可以留在 Claude Desktop 里直接让 Claude 调用 RefChecker，不需要在 Claude Desktop 和 RefChecker 桌面应用之间来回切换。

## 1. 安装 Python 依赖

在本项目目录执行：

```powershell
pip install -r requirements.txt
```

## 2. 配置 Claude Desktop

打开 Claude Desktop 配置文件：

```text
%APPDATA%\Claude\claude_desktop_config.json
```

加入下面的 MCP server 配置：

```json
{
  "mcpServers": {
    "refchecker": {
      "command": "python",
      "args": [
        "C:\\Users\\lizzi\\Desktop\\Reference_Check\\refcheker\\refchecker_mcp_server.py"
      ]
    }
  }
}
```

如果 `python` 不在 Claude Desktop 的 PATH 里，把 `command` 改成 Python 的完整路径，例如：

```json
{
  "mcpServers": {
    "refchecker": {
      "command": "C:\\Users\\lizzi\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
      "args": [
        "C:\\Users\\lizzi\\Desktop\\Reference_Check\\refcheker\\refchecker_mcp_server.py"
      ]
    }
  }
}
```

保存后重启 Claude Desktop。

## 3. 可用工具

Claude Desktop 会看到 3 个 RefChecker 工具：

- `check_reference_file`：核验本地 `.bib / .docx / .txt` 文件。
- `check_reference_text`：核验直接粘贴的参考文献文本。
- `test_reference_api_keys`：测试 Springer Nature / IEEE Xplore / CORE / 自定义 REST API Key。

## 4. 使用示例

在 Claude Desktop 里可以直接说：

```text
用 RefChecker 检查 C:\Users\lizzi\Desktop\Reference_Check\refcheker\References.docx
```

或：

```text
用 RefChecker 检查下面这几条参考文献，并把报告保存到 C:\tmp\refchecker_out
...
```

工具会返回摘要，并在输出目录写入：

- `report.md`
- `result.csv`
- `citation_consistency.json`（适用于 DOCX / 含正文的 TXT）

## 5. 可选参数

Claude 可以传给工具的常用参数：

- `threshold`：标题相似度阈值，默认 `0.85`。
- `email`：用于 CrossRef/OpenAlex/NCBI 的 User-Agent/mailto。
- `sources`：数据源优先级，例如 `crossref,openalex,semantic-scholar,pubmed`。
- `disabled_sources`：禁用某些源，例如 `["url"]`。
- `springer_api_key` / `ieee_api_key` / `core_api_key`：也可用环境变量配置。
- `custom_rest_profiles`：自定义 REST API Profile JSON 文件路径。

## 6. 本地自测

可以用一行 JSON-RPC 测试 server 是否能列出工具：

```powershell
'{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python .\refchecker_mcp_server.py
```

正常会返回包含 `check_reference_file`、`check_reference_text`、`test_reference_api_keys` 的 JSON。
