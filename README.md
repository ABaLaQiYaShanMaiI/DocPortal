> ⚠️ **重要提示 / Important Note**  
> **此项目为所有 AI 场景设计 —— 无论是粘贴到对话窗口，还是让网页 AI 直接读取**  
> **This project is designed for all AI scenarios — paste into chat windows or let browser AI read natively**  
>
> - **TXT 模式**：纯文本输出，可直接粘贴到任意 AI 对话窗口  
> - **分片模式**：超大型项目自动拆分，避免溢出 LLM 上下文  
> - **Portal 模式**：单页 HTML，浏览器 AI 可直接读取分析  
> 无需插件、文件上传或 API 调用。  
>  
> - **TXT Mode**: Plain text output, ready to paste into any LLM chat  
> - **Chunked Mode**: Automatically split large projects into manageable TXT files  
> - **Portal Mode**: Single-page HTML, directly readable by browser-based AI  
> No plugins, file uploads, or API calls required.

---

# FolderKnowledgeSiteGeneratorForAI 📁 → 🌐

[![PyPI Version](https://img.shields.io/badge/pypi-v2.2.0-blue)](https://pypi.org/project/FolderKnowledgeSiteGeneratorForAI/)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**一键将文件夹转为 AI 可读的知识门户或分片文本，无需服务器与 API。**  
**Turn any folder into AI-readable knowledge portals or chunked text — no server, no API.**

---

## 📋 目录 / Table of Contents

- [环境要求](#️-环境要求--requirements)
- [快速开始](#-快速开始--quick-start)
- [输出模式](#-输出模式--output-modes)
- [Portal 特性](#️-portal-特性--portal-features)
- [分片模式](#-分片模式--chunked-mode)
- [图形界面 (GUI)](#️-图形界面--gui)
- [命令行 (CLI)](#️-命令行--cli)
- [支持格式](#-支持格式--supported-formats)
- [项目架构](#-项目架构--project-architecture)
- [故障排除](#-故障排除--troubleshooting)
- [贡献](#-贡献--contributing)
- [许可证](#-许可证--license)

---

## 🖥️ 环境要求 / Requirements

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | **3.8+** | 推荐 3.10+ |
| tkinter | 系统自带（大多） | Linux 需单独安装 `python3-tk` |
| pip 包 | `python-magic`, `pdfminer.six`, `python-docx`, `python-pptx`, `openpyxl`, `chardet` | `pip install -r requirements.txt` 一键安装 |
| tkinterdnd2 | **可选** | 拖拽文件夹到 GUI。不安装也可通过 Browse / Paste 使用 |

<details>
<summary>📌 各系统 tkinter 安装指南</summary>

| 系统 | 命令 |
|------|------|
| **Windows** | Python 安装程序自带 tkinter，无需额外操作 |
| **Ubuntu / Debian** | `sudo apt-get install python3-tk` |
| **Fedora** | `sudo dnf install python3-tkinter` |
| **macOS** | `brew install python-tk`（如使用 Homebrew Python） |
| **Arch** | `sudo pacman -S tk` |

如果 tkinter 缺失，`start.sh` 会自动检测并提示安装命令，`start.cmd` 会在 Python 安装时自带。

</details>

---

## 🚀 快速开始 / Quick Start

### 方式一：启动脚本（推荐 · 自动配置环境）

| 系统 | 操作 |
|------|------|
| **Windows** | 双击 `start.cmd` |
| **Linux / macOS** | 终端运行 `bash start.sh` |

脚本会 **自动完成全部环境配置**，无需手动操作：

<details>
<summary>🔧 点击展开：启动脚本详细工作流程</summary>

```
首次运行（自动配置环境）
├── 1. 检测 Python 3.8+ 是否已安装
│     ├── Windows: 缺失时自动调用 winget 安装
│     └── Linux/macOS: 显示包管理器安装命令
├── 2. 检测/创建 Python 虚拟环境（.venv）
│     └── 隔离依赖，避免污染系统 Python
├── 3. 安装运行时依赖
│     ├── python-magic, pdfminer.six, python-docx, python-pptx, openpyxl, chardet
│     └── Windows: 自动补充 python-magic-bin
├── 4. 尝试安装 tkinterdnd2（可选的拖拽支持）
│     ├── 先 import 检测 → 已可用则跳过
│     ├── 未安装 → pip install → import 验证
│     └── 失败 → 不阻塞，GUI 仍可用 Browse/Paste 替代
├── 5. 检测 tkinter 是否可用
│     └── Linux: 缺失时显示 sudo apt-get install python3-tk 等命令
├── 6. 生成依赖标记文件（deps_ok.marker）
│     └── 后续启动跳过 pip 检查，直接进入 GUI（秒开）

后续运行（极速启动）
├── 1. 检测 Python ✓
├── 2. 激活虚拟环境 ✓
├── 3. 检测标记文件（deps_ok.marker 存在）→ 跳过 pip 安装
└── 4. 直接启动 GUI ⚡
```
</details>

| 自动完成 | 说明 |
|----------|------|
| ✅ **Python 检测** | 自动查找系统 Python，版本不足时给出安装指引 |
| ✅ **虚拟环境** | 首次自动创建 `.venv`，后续自动激活 |
| ✅ **依赖安装** | 自动 `pip install -r requirements.txt` |
| ✅ **拖拽支持** | 自动尝试安装 `tkinterdnd2`，失败不阻塞 |
| ✅ **编译回退** | Windows 上缺少 C 编译器时自动尝试预编译 wheel |
| ✅ **增量启动** | 首次配置后，后续启动跳过所有 pip 检查，秒开 GUI |
| ✅ **错误诊断** | GUI 崩溃时自动显示可能原因和修复命令 |

### 方式二：手动安装

```bash
# 安装依赖
pip install -r requirements.txt

# 🖥️ 图形界面
python gui.py [文件夹路径]

# ⌨️ 命令行
python generate.py my_folder -o out.txt                         # TXT 导出
python generate.py my_folder --split-chunks -o chunked_out/      # 分片导出
python generate.py my_folder --portal -o portal_out/             # Portal 模式
python generate.py my_folder -o out.md --format md               # Markdown 导出
```

---

## 📊 输出模式 / Output Modes

| 模式 | 命令参数 | 输出 | 适用场景 |
|------|----------|------|----------|
| 🗂️ **TXT** | 默认 | 纯文本（`.txt`） | 粘贴到 ChatGPT、DeepSeek、Claude 等对话窗口 |
| 📝 **Markdown** | `--format md` | Markdown（`.md`） | 带代码块高亮的文档 |
| 📦 **分片** | `--split-chunks` | 多个 `part_NNN.txt` + 索引 | 超大型项目自动拆分，避免溢出 LLM 上下文 |
| 🏛️ **Portal** | `--portal` | 单页/拆分 HTML + 子页面 | 浏览器 AI 直接读取（Edge Copilot / ChatGPT Web） |
| 🏛️ **Portal 单页** | `--portal --single-page` | 单个 HTML 文件 | 所有内容嵌入一个页面（不推荐超大项目） |

---

## 🏛️ Portal 特性 / Portal Features

- **可折叠文件块** — 每个文件默认为折叠状态，点击展开
- **Expand All / Collapse All** — 一键展开/收起所有内容
- **实时搜索** — 按文件名、标签、内容搜索，文件树同步高亮
- **文件树导航** — ASCII 风格，点击跳转
- **关键词云** — 自动提取中英文关键词，点击过滤
- **中英双语** — 右上角切换，偏好自动保存
- **暗黑模式** — 自动跟随系统，统一适配搜索/按钮/badge
- **打印友好** — 打印时自动展开所有内容
- **拆分模式**（默认）— 每个文件独立子页面，主页为文件树+搜索
- **内置 HTTP 服务器** — 生成后一键启动，浏览器 AI 可直接读取

---

## 📦 分片模式 / Chunked Mode

超大项目安全分割为多个 TXT 文件，每个可直接粘贴到 AI 对话。

### 分片策略

| 策略 | 默认 | 说明 |
|------|------|------|
| **文件级完整性** | ✅ 默认 | 不切割单个文件，每个文件完整出现在一个分片中 |
| **强制切分** | `--force-split` | 超大文件（> chunk-size）强制拆分为多个分片 |

### 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--chunk-size` | 500,000 | 每片字符数（设为 0 不限） |
| `--max-chars` | 不限 | 总字符数上限 |
| `--force-split` | false | 强制切分超大文件 |

**输出结构：**
```
output_dir/
├── part_001.txt          # 分片内容（保持文件级完整性，不从中切开）
├── part_002.txt
├── ...
├── <文件夹名>_index.html  # 交互式索引（可折叠，点击查看各分片包含的文件）
└── _manifest.txt          # 纯文本清单
```

---

## 🖥️ 图形界面 / GUI

| 功能 | 说明 |
|------|------|
| 📂 **文件夹选择** | 浏览、粘贴或拖拽，快捷键 `Ctrl+O` |
| 🔄 **模式切换** | Single TXT / Split TXT / Portal，自动调整 UI |
| 🚀 **一键生成** | 进度条实时反馈，快捷键 `Ctrl+G` |
| 🌐 **中英双语** | 即时切换，偏好自动保存（`~/.folderknowledge_settings.json`） |
| 📋 **实时文件列表** | 显示文件、大小、状态，支持名称/内容搜索 |
| ▶️ **HTTP 服务器** | Portal 生成后一键启动本地服务器供 AI 读取 |
| 📂 **拖拽支持** | 支持文件夹拖入 GUI（需 `tkinterdnd2`） |

> ⚠️ **拖拽说明**：若 `tkinterdnd2` 未安装，启动时会显示提示。可使用 **Browse** 按钮或 **Paste**（Ctrl+V 粘贴文件夹路径）代替，功能完全相同。

---

## ⌨️ 命令行 / CLI

### 完整参数

```
usage: python generate.py [-h] -o OUTPUT [--portal] [--single-page]
                          [--no-skipped] [--max-chars-per-file N]
                          [--log-file LOG_FILE] [--format {txt,md}]
                          [--split-chunks] [--force-split]
                          [--chunk-size N] [--max-chars N]
                          [--lang {en,zh}]
                          folder
```

### 参数表

| 参数 | 默认 | 说明 |
|------|------|------|
| `folder` | （必填） | 要扫描的文件夹路径 |
| `-o, --output` | （必填） | TXT/MD 模式：输出文件路径；分片/Portal 模式：输出目录 |
| `--portal` | false | Portal 模式（默认拆分，每个文件独立子页面） |
| `--single-page` | false | Portal 单页模式（所有文件嵌入一个 HTML） |
| `--split-chunks` | false | 分片模式 |
| `--format {txt,md}` | txt | TXT/MD 模式的输出格式 |
| `--chunk-size N` | 500,000 | 分片最大字符数（设为 0 不限制） |
| `--max-chars N` | 不限 | 分片模式总字符上限 |
| `--force-split` | false | 分片模式强制切分超大文件 |
| `--no-skipped` | false | Portal 模式不显示跳过文件标记 |
| `--max-chars-per-file N` | 200,000 | Portal 模式单文件字符上限（设为 0 不限制） |
| `--lang {en,zh}` | en | 输出语言 |
| `--log-file FILE` | 无 | 日志写入指定文件 |

---

## 📦 支持格式 / Supported Formats

| 类别 | 格式 |
|------|------|
| 纯文本/标记 | `.txt`, `.md`, `.html`, `.json`, `.xml`, `.csv`, `.yaml`, `.toml`, `.ini` 等 |
| Office 文档 | `.docx`, `.pptx`, `.xlsx`（需 `python-docx`, `python-pptx`, `openpyxl`） |
| Office 旧格式 | `.doc`, `.ppt`, `.xls`（需 LibreOffice 或 WPS CLI 转换） |
| WPS 格式 | `.wps`, `.et`, `.dps`（需 LibreOffice 或 WPS CLI 转换） |
| PDF | `.pdf`（需 `pdfminer.six`） |
| 代码文件 | `.py`, `.js`, `.ts`, `.java`, `.cs`, `.swift`, `.kt`, `.rs`, `.go` 等 50+ 种 |
| 自动跳过 | `.exe`, `.dll`, `.zip`, `.jpg`, `.png`, `.mp4`, `__pycache__`, `.git`, `node_modules` 等 |

---

## 🏗️ 项目架构 / Project Architecture

```
FolderKnowledgeSiteGeneratorForAI/
├── generate.py              # CLI 入口（argparse 参数解析，三模式分发）
├── gui.py                   # GUI 入口（tkinter 窗口启动）
├── start.cmd                # Windows 一键启动脚本
├── start.sh                 # Linux/macOS 一键启动脚本
├── requirements.txt         # 依赖声明
├── pyproject.toml           # 项目元数据
├── src/
│   ├── __init__.py          # 包入口，公开核心 API
│   ├── constants.py         # 过滤规则、文件类型映射、默认常量
│   ├── utils.py             # 通用工具函数（human_readable_size）
│   ├── scanner.py           # 文件夹遍历、TXT/MD/HTML 输出构建器
│   ├── parser/              # 多格式文件解析模块
│   │   ├── dispatcher.py    # MIME + 扩展名双重调度分发
│   │   ├── text_parser.py   # 文本文件解析（chardet 编码检测）
│   │   ├── pdf_parser.py    # PDF 解析（pdfminer.six）
│   │   └── office_parser.py # Office/WPS 文档解析
│   ├── generator/           # 知识门户生成器
│   │   ├── portal.py        # Portal 生成逻辑（单页/拆分模式）
│   │   └── templates.py     # HTML 模板渲染、子页面构建
│   ├── chunker/             # 分片输出模块
│   │   └── __init__.py      # FileChunk 类、分片策略、索引生成
│   └── ui/                  # 图形界面模块
│       ├── app.py           # GUI 主应用（tkinter）
│       ├── i18n.py          # 中英双语标签定义
│       └── server.py        # HTTP 服务器管理
└── tests/                   # 测试用例
    ├── conftest.py          # pytest 配置
    ├── test_cli.py          # CLI 全模式测试
    ├── test_parser.py       # 解析器单元测试
    └── test_portal.py       # Portal 生成测试
```

### 数据流

```
文件夹路径 → walk_files() [过滤] → collect_files_info() [MIME 检测]
→ parse_file() [Dispatcher 分发]
  ├── text/* → parse_text() [chardet 编码检测]
  ├── PDF    → parse_pdf() [pdfminer.six]
  └── Office → parse_office() [python-docx/pptx/openpyxl + LibreOffice]
→ 输出模式:
  ├── TXT/MD 模式 → build_text_from_files() / build_markdown_from_files()
  ├── 分片模式     → write_chunks() → part_NNN.txt + index.html + _manifest.txt
  └── Portal 模式  → generate_portal_split() → index.html + docs/*.html
```

---

## 🔧 故障排除 / Troubleshooting

<details>
<summary>🐧 Linux/macOS: 启动报错 "No module named 'tkinter'"</summary>

tkinter 未安装。根据系统执行：

```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# macOS (Homebrew Python)
brew install python-tk

# Arch
sudo pacman -S tk
```

安装后重新运行 `bash start.sh`。

</details>

<details>
<summary>🪟 Windows: 双击 start.cmd 后窗口一闪而过</summary>

可能原因：
1. Python 未安装或未添加到 PATH — 安装时勾选 "Add Python to PATH"
2. 在 CMD 中手动运行 `python gui.py` 查看具体错误信息
3. 尝试以管理员身份运行 `start.cmd`

</details>

<details>
<summary>📂 拖拽功能不可用</summary>

这是正常的 — `tkinterdnd2` 是可选依赖，需要 C 编译器安装。**不影响使用**：
- 点击 **Browse** 按钮选择文件夹
- 复制文件夹路径，在路径框中 **Ctrl+V** 粘贴

如需启用拖拽：
```bash
pip install tkinterdnd2
```
若安装失败，可尝试预编译 wheel：
```bash
pip install --only-binary :all: tkinterdnd2
```

</details>

<details>
<summary>🖨️ Office 旧格式 (.doc/.ppt/.xls) 或 WPS 格式无法解析</summary>

这些格式需要外部工具转换为文本：
- **LibreOffice**（免费）：https://www.libreoffice.org/download/
- **WPS Office**（Windows）：安装后自动检测

解析器会自动搜索系统中的 LibreOffice/WPS，找到后自动调用。

</details>

<details>
<summary>🔍 生成的门户 HTML 搜索速度慢</summary>

大型项目建议使用 **拆分模式**（默认），不要使用 `--single-page`。拆分模式下每个文件独立子页面，主页仅显示文件树和搜索索引，加载和搜索更快。

</details>

---

## 🤝 贡献 / Contributing

- **代码风格**：`ruff check src/ tests/`
- **类型检查**：`mypy src/ --install-types --non-interactive --config-file mypy.ini`
- **运行测试**：`pytest tests/ -v`
- **提交规范**：feature branch → PR → main

### ⚠️ 常见 CI 类型检查错误 / Common mypy Type Errors

CI 中 mypy 检查失败通常由以下 3 类问题引起，请务必遵守规范以避免重复提交失败：

**1. Optional 注解缺失（PEP 484 违规）**

变量允许为 `None` 时必须显式标注 `Optional[X]`，禁止隐式 Optional（mypy 默认 `no_implicit_optional=True`）：

```python
# ❌ 错误：变量类型为 set，但默认值为 None
def build_tree(parsed_files: set = None):
    ...

# ✅ 正确：显式使用 Optional
from typing import Optional
def build_tree(parsed_files: Optional[set] = None):
    if parsed_files is None:
        parsed_files = set()
```

**2. 变量缺少类型注解**

mypy 无法推断或推断出错误类型时，需要显式注解：

```python
# ❌ 错误：mypy 无法推断 Counter 类型
counter = Counter()

# ✅ 正确
counter: Counter = Counter()

# ❌ 错误：mypy 无法推断空列表元素类型
lines = []

# ✅ 正确
lines: list[str] = []
```

**3. 类型注解时机问题（导入前使用）**

类型注解在定义时求值，必须确保被引用的类型已定义。对于条件导入的模块（如可选依赖），使用 `TYPE_CHECKING` 条件导入：

```python
# ❌ 错误：magic 在类型注解时尚未导入
_magic: Optional[magic.Magic] = None
try:
    import magic

# ✅ 正确：使用 TYPE_CHECKING + 字符串注解
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from magic import Magic

_magic: Optional['Magic'] = None  # 字符串形式，延迟求值
try:
    import magic
    _magic = magic.Magic(mime=True)
```

**为什么需要字符串形式**：`TYPE_CHECKING` 在运行时为 `False`，运行时 `Magic` 未导入，字符串形式避免了 `NameError`。

> 💡 **提示**：项目根目录的 `mypy.ini` 已配置 `ignore_missing_imports = true` 和模块级忽略规则，可处理 `tkinterdnd2` 等可选依赖的导入问题。

---

## 📄 许可证 / License

[MIT](LICENSE)

---

<p align="center">
  <sub>⭐ <a href="https://github.com/ABaLaQiYaShanMaiI/FolderKnowledgeSiteGeneratorForAI">Star on GitHub</a> if you find this useful!</sub>
  <br>
  <sub>Made with ❤️ by <a href="https://github.com/ABaLaQiYaShanMaiI">ABaLaQiYaShanMaiI</a></sub>
</p>