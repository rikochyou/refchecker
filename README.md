# RefChecker：文献真实性与元数据一致性核验工具

> 基于 CrossRef、OpenAlex、DBLP 与 URL 直连验证的参考文献核验工具，支持 **BibTeX** 和 **DOCX** 两种输入，从 **DOI、标题、作者、年份、URL** 五个维度交叉验证每条引用，批量生成 Markdown / CSV 报告。

RefChecker 适合在论文写作、毕业设计、综述整理或参考文献清洗阶段使用：

- **BibTeX 模式**：读取 `.bib` 文件，解析文献条目，通过 DOI 精确查询 → CrossRef 标题检索 → OpenAlex / DBLP 兜底 → URL 直连验证；
- **DOCX 模式**：自动识别 APA 格式的参考文献段落，提取 DOI / 标题 / 作者 / 年份后进行相同的多源核验；
- 提供 **Flutter 桌面界面**，也支持 **命令行** 直接调用；
- 提供 **免安装 Windows 便携版**，下载即用。

> 注意：本项目是"辅助核验"工具，不能单独作为判断文献真实性的唯一依据。未匹配不一定代表文献不存在，匹配成功也建议结合 DOI、作者、年份和期刊/会议进一步确认。

## 功能特点

- **多源交叉验证**：CrossRef + OpenAlex + DBLP + URL 直连，可按需关闭
- **DOI 优先查询**：有 DOI 的条目直接用 CrossRef DOI 接口精确匹配
- **URL 资源验证**：对 HuggingFace 模型、GitHub 仓库、NVIDIA/Intel 产品页等非学术引用，验证 URL 可访问性并通过 API 比对元数据
- **DOCX 参考文献解析**：自动识别 Word 文档中的 APA 格式参考文献，提取相应字段后核验
- **标题相似度匹配**：LaTeX 去标记、去重音、标点归一化后使用 `SequenceMatcher` 计算相似度
- **作者一致性检查**：
  - 支持 `Last, First` 与 `First Last` 两种 BibTeX 作者格式
  - 处理姓氏粒子（van, de, von, della …）与后缀（Jr, Sr, II …）
  - 识别 `others` / `et al.` 省略标记
  - 区分"顺序异常"、"遗漏作者"、"多余作者"、"首作者不一致"等场景
- **年份与 DOI 一致性检查**：对比 BibTeX / DOCX 中的年份、DOI 与数据库返回值
- **灵活的命令行参数**：可配置相似度阈值、请求间隔、邮箱 User-Agent、是否启用各验证源
- **多种输出形式**：
  - 命令行实时进度与汇总
  - JSONL 进度事件（供桌面 UI 消费）
  - Markdown 报告（含需复核条目、元数据不一致清单、完整结果表）
  - CSV 表格（30+ 字段，便于用 Excel / pandas 进一步分析）

## 快速开始

### 免安装版（推荐）

从 [Releases](https://github.com/rikochyou/refchecker/releases) 下载 `refchecker_portable.zip`，解压后双击 `refchecker_desktop.exe`。

### 命令行版

环境要求：Python 3.8+

```bash
pip install bibtexparser requests python-docx
```

核验 BibTeX 文件：

```bash
python check_bib_crossref.py ref.bib --output-dir results/
```

核验 Word 文档中的参考文献：

```bash
python check_bib_crossref.py References.docx --output-dir results/
```

## 项目结构

```text
.
├── check_bib_crossref.py          # 主程序（CLI 后端）
├── lib/main.dart                  # Flutter 桌面 UI
├── requirements.txt               # Python 依赖
├── pubspec.yaml                   # Flutter 依赖
├── ref.bib                        # 示例 BibTeX 文件
├── reference_filtered.bib         # 包含 URL/硬件引用的示例
├── tests/                         # Python 后端测试
├── test/                          # Flutter 测试
├── tool/                          # 构建脚本
├── windows/                       # Windows 桌面 runner
└── macos/                         # macOS 桌面 runner
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `file` | 待核验的 `.bib` 或 `.docx` 文件路径 | 必填 |
| `--threshold` | 标题相似度阈值，范围 `0-1` | `0.85` |
| `--delay` | 每条文献核查后的间隔秒数 | `0.2` |
| `--email` | 邮箱，用于 CrossRef User-Agent | 空 |
| `--no-openalex` | 不使用 OpenAlex 兜底 | 关闭 |
| `--no-dblp` | 不使用 DBLP 兜底 | 关闭 |
| `--no-url-verify` | 不验证 URL 资源 | 关闭 |
| `--output` | Markdown 报告输出路径 | 不输出 |
| `--csv` | CSV 表格输出路径 | 不输出 |
| `--output-dir` | 输出目录（自动生成 report.md + result.csv） | 不输出 |
| `--jsonl-progress` | 输出 JSONL 进度事件（供 UI 调用） | 关闭 |

## 核查维度

| 维度 | 说明 |
|---|---|
| **DOI** | 若有 DOI，优先用 CrossRef DOI 接口精确查询；同时比对匹配结果 DOI 是否一致 |
| **标题** | 去除 LaTeX 标记 / 重音 / 标点后计算相似度 |
| **作者** | 对比作者姓氏、名缩写、顺序、数量；识别 `others` / `et al.` |
| **年份** | 从 BibTeX / DOCX 与数据库年份中抽取 4 位年份进行比对 |
| **URL** | 对非学术引用验证 URL 可访问性；HuggingFace / GitHub 可进一步比对元数据 |

## URL 资源验证

对于计算机类论文中常见的模型、仓库、硬件引用：

| 来源 | 验证方式 |
|---|---|
| **HuggingFace** | API 查询模型/数据集，比对 modelId ↔ 标题、author ↔ 作者、lastModified ↔ 年份 |
| **GitHub** | API 查询仓库，比对 full_name ↔ 标题、owner ↔ 作者、created_at ↔ 年份 |
| **通用网页** | HTTP HEAD/GET 检查可访问性 |

示例 BibTeX 条目：

```bibtex
@misc{llama318B,
  author       = {{Meta}},
  title        = {meta-llama/Llama-3-1-8B-Instruct},
  year         = {2024},
  url          = {https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct}
}
```

## 输出说明

### 状态分类

| 状态 | 含义 |
|---|---|
| `found` | 在某个数据源中找到达到阈值的匹配结果 |
| `not_found` | 所有数据源均未找到达到阈值的结果 |
| `skipped` | 缺少必要字段，被跳过 |

### needs_review 标记

条目在以下情况会被标记为"需复核"：

- `not_found`：未找到匹配
- 标题相似度 < 100%（URL(Web) 来源除外）
- 作者核查结果为 `mismatch` 或 `partial`
- 年份核查结果为 `mismatch`
- DOI 核查结果为 `mismatch`

> "元数据缺失"（unknown）不计入需复核，因为对 URL 资源来说这属于正常情况。

## 使用建议

1. 首次运行建议使用默认阈值 `0.85`
2. 如果误匹配较多，可以提高阈值，例如 `--threshold 0.90`
3. 大批量核验时建议设置更长请求间隔，例如 `--delay 1`
4. 填写 `--email` 可提高 CrossRef / OpenAlex 的访问稳定性
5. 优先关注 CSV 中 `needs_review=Yes` 且 `author_check=mismatch` 或 `year_check=mismatch` 的条目

## 局限性

- 作者核查是"元数据一致性检查"，不能 100% 证明作者真伪
- CrossRef / OpenAlex / DBLP 的元数据可能存在缺失、延迟或不一致
- 对非英文标题、特殊 LaTeX 命令的支持可能有限
- URL 验证（HuggingFace / GitHub）依赖第三方 API 可用性，可能受限流影响
- 本工具无法替代人工学术判断

## 构建

### Python 后端（PyInstaller）

```bash
pip install pyinstaller
pyinstaller --onefile --name refchecker_backend check_bib_crossref.py
```

### Flutter 桌面 UI

```bash
flutter build windows
```

## License

MIT
