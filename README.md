# RefChecker：AI 幻觉引用与参考文献可信度核验工具

> 当前版本：**v1.1.0+2** ｜ GitHub Release 标签建议：**v1.1.0**

RefChecker 面向论文写作、综述整理、毕业设计和 AI 辅助写作场景，用于筛查疑似 **AI 编造文献、幻觉引用、误引、DOI 错配或元数据异常** 的参考文献。工具支持 **BibTeX / DOCX / TXT / 粘贴文本** 输入，基于 CrossRef、OpenAlex、Semantic Scholar、arXiv、PubMed、DBLP、Springer Nature、IEEE Xplore、CORE、自定义 REST API Profile 与 URL 直连验证，从 **DOI、标题、作者、年份、URL** 等维度交叉核验每条引用，并输出风险等级、置信度、建议操作、Markdown 报告和 CSV 表格。

> 注意：RefChecker 是“辅助筛查工具”，不是最终学术裁决。未匹配不等于文献一定不存在，匹配成功也不等于引用完全正确；最终判断仍需结合 DOI、出版社页面、论文原文和人工学术判断。

## v1.1.0 主要更新

- **重新设计 API 配置面板**：自定义数据源以卡片形式管理，每张卡片都有“启用”开关。
- **自定义 REST API Profile（JSON）**：高级用户可直接配置 endpoint、auth、参数模板和 JSON 字段映射。
- **启用的数据源才进入搜索链**：未启用的自定义 REST 数据源不会显示在“数据源搜索链”，也不会参与检索。
- **卡片级 API 连通性测试**：测试按钮和结果移动到每个 API 卡片内部，便于逐个排查配置。
- **安全请求间隔锁定**：请求间隔最低锁定为 `0.50s`，前端和后端都做兜底，避免误拖到 `0s` 触发限流或封禁。
- **版本号显示**：桌面端标题栏显示当前版本号。

## 功能特点

- **多源交叉验证**：CrossRef + OpenAlex + Semantic Scholar + arXiv + PubMed + DBLP + URL 直连，可按需关闭或排序。
- **API Key 增强源**：支持 Springer Nature / IEEE Xplore / CORE API Key，提高特定数据库覆盖率。
- **自定义 REST 数据源**：通过 JSON Profile 配置第三方 RESTful API，支持 `GET` / `POST`、query/header/bearer 鉴权、参数模板与字段映射。
- **DOI 优先查询**：有 DOI 的条目优先使用 CrossRef DOI 接口精确匹配。
- **标题相似度匹配**：LaTeX 去标记、去重音、标点归一化后计算相似度。
- **作者一致性检查**：识别 `others` / `et al.`，区分首作者不一致、作者遗漏、额外作者、顺序异常等问题。
- **年份与 DOI 一致性检查**：对比输入文献与数据库返回的年份、DOI。
- **URL 资源验证**：对 HuggingFace、GitHub、通用网页等非传统论文引用检查可访问性与元数据。
- **风险分级与置信度**：输出 `high / medium / low / none` 风险等级、`0-100` 置信度和建议操作。
- **桌面端 + 命令行双模式**：普通用户可使用 Windows 便携版 / macOS 桌面包，高级用户可直接调用 CLI。

## 快速开始

### 桌面版（推荐）

从 [Releases](https://github.com/rikochyou/refchecker/releases) 下载：

- **Windows**：`RefChecker_portable.zip`，解压后双击 `refchecker_desktop.exe`
- **macOS**：`RefChecker-macOS.dmg` 或压缩包版本，拖入 Applications 后运行

> macOS 首次运行时，如果系统提示来自未验证开发者，可右键点击 app → “打开”。

Windows 便携包入口：

```text
refchecker_desktop.exe
```

便携版已内置 Python 后端，不需要用户单独安装 Python 依赖。

### 命令行版

环境要求：Python 3.8+

```bash
pip install -r requirements.txt
```

核验 BibTeX 文件：

```bash
python check_bib_crossref.py refs.bib --output-dir results/
```

核验 Word 文档中的参考文献：

```bash
python check_bib_crossref.py References.docx --output-dir results/
```

核验 TXT 文本文件：

```bash
python check_bib_crossref.py references.txt --output-dir results/
```

直接传入粘贴文本：

```bash
python check_bib_crossref.py --text "Smith, J. (2020). A Test Paper. Journal." --output-dir results/
```

## 桌面端使用说明

1. 选择输入方式：`.bib / .docx / .txt` 文件，或直接粘贴参考文献文本。
2. 选择结果保存位置。
3. 在高级设置中按需调整标题相似度阈值、请求间隔、邮箱、数据源搜索链和 API 配置。
4. 点击“开始校验”。
5. 查看 UI 结果面板，或打开生成的 `report.md` / `result.csv`。

输出目录会自动创建类似：

```text
refchecker_YYYYMMDD_HHMMSS/
├── report.md
├── result.csv
└── run.log
```

## 数据源搜索链

默认开放来源包括：

```text
crossref, openalex, semantic-scholar, arxiv, pubmed, dblp, url
```

可选 API Key 增强源包括：

```text
springer, ieee, core
```

桌面端“数据源搜索链”支持拖拽排序。只有满足以下条件的数据源才会显示并参与检索：

- 内置开放源：在搜索链中启用；
- Springer / IEEE / CORE：对应 API Key 卡片启用；
- 自定义 REST API：卡片启用，且 JSON Profile 或旧字段中配置了 endpoint。

命令行中可通过 `--sources` 指定启用来源和优先级：

```bash
python check_bib_crossref.py refs.bib --sources crossref,pubmed,dblp --output-dir results/
```

## API Key 增强源

| 来源 | 参数 | 环境变量 |
|---|---|---|
| Springer Nature | `--springer-api-key` | `REFCHECKER_SPRINGER_API_KEY` |
| IEEE Xplore | `--ieee-api-key` | `REFCHECKER_IEEE_API_KEY` |
| CORE | `--core-api-key` | `REFCHECKER_CORE_API_KEY` |

示例：

```bash
python check_bib_crossref.py refs.bib \
  --sources crossref,springer,ieee,core \
  --springer-api-key YOUR_SPRINGER_KEY \
  --ieee-api-key YOUR_IEEE_KEY \
  --core-api-key YOUR_CORE_KEY
```

也可以使用环境变量，避免命令行明文输入：

```powershell
$env:REFCHECKER_SPRINGER_API_KEY="..."
$env:REFCHECKER_IEEE_API_KEY="..."
$env:REFCHECKER_CORE_API_KEY="..."
python check_bib_crossref.py refs.bib --sources crossref,springer,ieee,core
```

连通性测试：

```bash
python check_bib_crossref.py --test-api-keys --sources springer,ieee,core
```

桌面端中，连通性测试位于每个 API 卡片内部；测试只使用通用关键词，不上传你的文献内容，日志中也不会输出 Key 明文。

## 自定义 REST API Profile（高级）

v1.1.0 起，桌面端支持直接编辑 JSON Profile。适合高级用户接入机构数据库、内部检索服务或其他第三方 RESTful API。

### JSON Profile 示例

```json
{
  "name": "My Literature API",
  "endpoint": "https://api.example.com/search",
  "method": "GET",
  "authType": "bearer",
  "queryParams": {
    "q": "{title}",
    "year": "{year}"
  },
  "headers": {
    "Accept": "application/json"
  },
  "resultsPath": "results",
  "titlePath": "title",
  "authorsPath": "authors",
  "yearPath": "year",
  "doiPath": "doi",
  "urlPath": "url",
  "venuePath": "venue",
  "typePath": "type"
}
```

### 支持字段

| 字段 | 说明 |
|---|---|
| `name` | 数据源显示名称 |
| `endpoint` | REST API URL，必填 |
| `method` | `GET` 或 `POST`，默认 `GET` |
| `authType` | `none` / `query` / `header` / `bearer` |
| `apiKey` | 可写在 JSON 中；桌面端也可使用卡片上方 API Key 字段注入 |
| `apiKeyParam` | `authType=query` 时的 query 参数名，默认 `api_key` |
| `apiKeyHeader` | `authType=header/bearer` 时的 header 名，默认 `Authorization` |
| `queryParams` | 查询参数模板；`GET` 作为 query 参数，`POST` 作为 JSON body |
| `headers` | 额外请求头 |
| `resultsPath` | 返回 JSON 中结果列表路径，如 `results` / `data.items` |
| `titlePath` | 结果项中的标题字段路径 |
| `authorsPath` | 结果项中的作者字段路径 |
| `yearPath` | 结果项中的年份字段路径 |
| `doiPath` | 结果项中的 DOI 字段路径 |
| `urlPath` | 结果项中的 URL 字段路径 |
| `venuePath` | 结果项中的期刊/会议/出版源字段路径 |
| `typePath` | 结果项中的类型字段路径 |

`queryParams` 和 `headers` 中支持模板变量：

```text
{title}, {author}, {year}, {email}
```

### 命令行接入自定义 REST Profile

将 Profile 保存为 JSON 文件，例如 `custom_rest_profiles.json`：

```json
[
  {
    "id": "my-api",
    "name": "My Literature API",
    "endpoint": "https://api.example.com/search",
    "method": "GET",
    "queryParams": {"q": "{title}"},
    "resultsPath": "results",
    "titlePath": "title",
    "authorsPath": "authors",
    "yearPath": "year",
    "doiPath": "doi"
  }
]
```

运行：

```bash
python check_bib_crossref.py refs.bib \
  --sources crossref,custom:my-api \
  --custom-rest-profiles custom_rest_profiles.json \
  --output-dir results/
```

测试自定义 REST Profile 连通性：

```bash
python check_bib_crossref.py \
  --test-api-keys \
  --sources custom:my-api \
  --custom-rest-profiles custom_rest_profiles.json
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `file` | 待核验的 `.bib` / `.docx` / `.txt` 文件路径；`--text` 或 `--test-api-keys` 时可省略 | 必填 |
| `--text` | 直接核验粘贴的参考文献文本 | 空 |
| `--threshold` | 标题相似度阈值，范围 `0-1` | `0.85` |
| `--delay` | 每条文献核查后的间隔秒数；安全最小值锁定为 `0.50`，低于该值会自动提升 | `0.5` |
| `--email` | 邮箱，用于 CrossRef / OpenAlex / NCBI User-Agent 或 mailto | 空 |
| `--sources` | 指定启用的数据源，逗号分隔；支持 `custom:<id>` | 空，使用默认来源 |
| `--custom-rest-profiles` | 自定义 REST API Profile JSON 文件路径 | 空 |
| `--springer-api-key` | Springer Nature Metadata API Key | 环境变量或空 |
| `--ieee-api-key` | IEEE Xplore API Key | 环境变量或空 |
| `--core-api-key` | CORE API Key | 环境变量或空 |
| `--test-api-keys` | 仅测试 API / REST Profile 连通性，不核验文献文件 | 关闭 |
| `--no-openalex` | 不使用 OpenAlex 兜底 | 关闭 |
| `--no-semantic-scholar` | 不使用 Semantic Scholar 兜底 | 关闭 |
| `--no-arxiv` | 不使用 arXiv 兜底 | 关闭 |
| `--no-pubmed` | 不使用 PubMed 兜底 | 关闭 |
| `--no-dblp` | 不使用 DBLP 兜底 | 关闭 |
| `--no-url-verify` | 不验证 URL 资源 | 关闭 |
| `--no-springer` | 不使用 Springer Nature API Key 增强源 | 关闭 |
| `--no-ieee` | 不使用 IEEE Xplore API Key 增强源 | 关闭 |
| `--no-core` | 不使用 CORE API Key 增强源 | 关闭 |
| `--output` | Markdown 报告输出路径 | 不输出 |
| `--csv` | CSV 表格输出路径 | 不输出 |
| `--output-dir` | 输出目录，自动生成 `report.md` + `result.csv` | 不输出 |
| `--jsonl-progress` | 输出 JSONL 进度事件，供桌面 UI 调用 | 关闭 |

## 核查维度

| 维度 | 说明 |
|---|---|
| **DOI** | 若有 DOI，优先用 CrossRef DOI 接口精确查询；同时比对匹配结果 DOI 是否一致 |
| **标题** | 去除 LaTeX 标记、重音、标点后计算相似度 |
| **作者** | 对比作者姓氏、名缩写、顺序、数量；识别 `others` / `et al.` |
| **年份** | 从输入文献和数据库年份中抽取 4 位年份进行比对 |
| **URL** | 对非学术引用验证 URL 可访问性；HuggingFace / GitHub 可进一步比对元数据 |

## 输出说明

| 字段 | 说明 |
|---|---|
| `status` | `found` / `not_found` / `skipped` |
| `needs_review` | 是否建议必须人工核查 |
| `risk_level` | `high` / `medium` / `low` / `none` |
| `confidence_score` | 0-100 的匹配置信度 |
| `suggested_action` | 下一步建议操作 |

建议优先处理：

1. `risk_level=high`
2. DOI 不一致
3. 首作者不一致
4. 未找到可靠来源
5. 标题相似度明显偏低

## 使用建议

1. 首次运行建议使用默认阈值 `0.85`。
2. 如果误匹配较多，可以提高阈值，例如 `--threshold 0.90`。
3. 大批量核验时建议设置更长请求间隔，例如 `--delay 1`；程序会强制保证最低 `0.50s`。
4. 填写 `--email` 可提高 CrossRef / OpenAlex / NCBI 的访问稳定性。
5. 优先关注 CSV 中 `risk_level=high`，再处理 `risk_level=medium` 且作者或年份存在差异的条目。

## 项目结构

```text
.
├── check_bib_crossref.py          # CLI 入口
├── refchecker/                    # Python 后端模块
├── lib/                           # Flutter 桌面 UI
├── assets/                        # 字体等资源
├── requirements.txt               # Python 依赖
├── pubspec.yaml                   # Flutter 依赖和版本号
├── tests/                         # Python 后端测试
├── test/                          # Flutter 测试
├── tool/                          # 构建脚本
├── windows/                       # Windows 桌面 runner
└── macos/                         # macOS 桌面 runner
```

## 开发与构建

Python 后端：

```bash
pip install -r requirements.txt
python -m py_compile check_bib_crossref.py refchecker/*.py
```

Flutter 桌面端：

```bash
flutter analyze
flutter test
flutter build windows --release --dart-define APP_VERSION=1.1.0+2
```

Windows 便携包布局：

```text
refchecker_desktop.exe
flutter_windows.dll
data/
backend/
  refchecker_backend.exe
```

## 发布 v1.1.0

推荐 GitHub Release 信息：

- Tag：`v1.1.0`
- Title：`RefChecker v1.1.0`
- Asset：`RefChecker_portable.zip`
- App 内版本：`v1.1.0+2`

发布说明可直接使用：

```text
RELEASE_NOTES_v1.1.0.md
```

## 局限性

- 作者核查是“元数据一致性检查”，不能 100% 证明作者真伪。
- 第三方数据库元数据可能存在缺失、延迟或不一致。
- 非英文标题、特殊 LaTeX 命令、非标准参考文献格式可能影响解析。
- URL 验证依赖第三方 API 可用性，可能受限流影响。
- 自定义 REST API Profile 的字段映射依赖目标 API 返回结构，配置错误会导致结果不可解析。
- 本工具无法替代人工学术判断。

## License

MIT
