                                                                                                                                                                                                                                                                                                                                                                                        #!/usr/bin/env python3
"""
FolderKnowledgeSiteGeneratorForAI — Folder to Knowledge TXT / Portal / Chunked Generator

Usage:
    # TXT 模式：生成单个完整 TXT 文件（无字符截断）
    python generate.py <folder_path> -o <output.txt>

    # 分片模式：按固定大小自动拆分为多个文件，避免溢出 LLM 上下文
    python generate.py <folder_path> --split-chunks -o <output_dir/> [--chunk-size 500000]

    # 门户模式：默认生成拆分式知识门户（每个文件独立子页面，主页显示文件树+搜索）
    python generate.py <folder_path> --portal -o <output_dir/>

    # 门户模式（单页，不推荐）：将所有内容嵌入一个 HTML
    python generate.py <folder_path> --portal --single-page -o <output_dir/>

Scans all files in a folder, parses documents (PDF, DOCX, PPTX, XLSX, TXT, etc.),
and generates:
  - TXT 模式：一个纯文本文件（完整内容，无截断）
  - 分片模式：多个 part_NNN.txt 文件，每个 ≤ chunk-size 字符，并附带索引 HTML
  - 门户模式（默认）：拆分式知识门户，每个文件独立 HTML 子页面，主页为文件树+搜索
  - 门户模式（--single-page）：所有文件内容嵌入一个页面（不推荐）
"""

import os
import sys
import pathlib
import argparse
import logging
import io

# Fix console encoding for Windows (防止中文乱码)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure the project root is on sys.path so the src package is always findable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from src.scanner import build_text_from_files, collect_files_info

# Try to import portal generator
try:
    from src.generator.portal import generate_portal
    from src.generator.portal import generate_portal_split
    HAS_PORTAL = True
except ImportError:
    HAS_PORTAL = False

# Try to import chunker (this also provides its own DEFAULT_CHUNK_SIZE for chunked mode)
try:
    from src.chunker import write_chunks, DEFAULT_CHUNK_SIZE as CHUNKER_DEFAULT_CHUNK_SIZE
    HAS_CHUNKER = True
except ImportError:
    HAS_CHUNKER = False
    CHUNKER_DEFAULT_CHUNK_SIZE = 500_000
    def write_chunks(*args, **kwargs):
        raise ImportError("src.chunker module not available")

# Logger setup — will be reconfigured when --log-file is parsed
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def build_text_content(folder_path: str):
    """Parse all files under folder_path and return full text content (no truncation).
    
    Args:
        folder_path: Absolute path to the source folder.
    
    Returns:
        Tuple of (text, parsed_count, skipped_count, error_count, total_chars).
    """
    file_list, _ = collect_files_info(folder_path)
    text, parsed, skipped, errors, chars = build_text_from_files(
        folder_path, file_list, include_skipped=True
    )
    return text, parsed, skipped, errors, chars


def main():
    parser = argparse.ArgumentParser(
        description="FolderKnowledgeSiteGeneratorForAI - 将文件夹中的文档解析为 TXT / 分片 / 门户"
    )
    parser.add_argument("folder", help="要扫描的文件夹路径")
    parser.add_argument("-o", "--output", required=True,
                        help="输出路径：TXT模式为文件路径，分片/门户模式为目录路径")
    parser.add_argument(
        "--portal",
        action="store_true",
        help="[门户模式] 生成可搜索的知识门户（默认拆分模式：每个文件独立子页面）",
    )
    parser.add_argument(
        "--single-page",
        action="store_true",
        help="[门户模式] 单页模式：所有文件内容嵌入一个页面（不推荐，内容过多时可能卡顿）",
    )
    parser.add_argument(
        "--split-files",
        action="store_true",
        help="[已废弃] 请直接使用 --portal，拆分模式已是默认行为",
    )
    parser.add_argument(
        "--no-skipped",
        action="store_true",
        help="[门户模式] 不在首页中显示不支持的文档标记",
    )
    parser.add_argument(
        "--max-chars-per-file",
        type=int,
        default=50000,
        help="[门户模式] 单文件最大字符数（默认 50,000，设为 0 不限）",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="将详细日志写入指定文件（默认仅输出到控制台）",
    )
    # ── 输出格式 ──
    parser.add_argument(
        "--format", "--fmt",
        type=str,
        default="txt",
        choices=["txt", "md", "markdown"],
        help="Output format: txt (default) or md/markdown (default: txt)",
    )
    # ── 分片模式（Chunked Output）──
    parser.add_argument(
        "--split-chunks",
        action="store_true",
        help="[分片模式] 按固定大小将内容拆分到多个文件，避免单文件过大溢出 LLM 上下文",
    )
    parser.add_argument(
        "--force-split",
        action="store_true",
        help="[分片模式] 强制切分超大文件（单文件超过 chunk-size 时自动分割到多个分片，而不是整文件独占一个分片）",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=CHUNKER_DEFAULT_CHUNK_SIZE,
        help=f"[分片模式] 每个分片的最大字符数（默认 {CHUNKER_DEFAULT_CHUNK_SIZE:,}，设为 0 不限）",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=None,
        help="[分片模式] 所有分片的总字符数上限（默认不限，超出则截断最后一文件）",
    )
    parser.add_argument(
        "--lang", "--language",
        type=str,
        default="en",
        choices=["en", "zh"],
        help="输出语言：en=英语, zh=中文（默认 en）",
    )
    args = parser.parse_args()

    # ── Configure logging with optional file handler ──
    if args.log_file:
        log_path = args.log_file
        try:
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            file_handler.setFormatter(file_formatter)
            # Add file handler to root logger
            root_logger = logging.getLogger()
            root_logger.addHandler(file_handler)
            # Also set console to INFO level (file gets DEBUG level)
            for handler in root_logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setLevel(logging.INFO)
            logger.info("Detailed logging enabled → %s", log_path)
        except Exception as e:
            print(f"Warning: Cannot write log to {log_path} ({e}), logging to console only", file=sys.stderr)

    if not os.path.isdir(args.folder):
        print("错误：路径不是有效的文件夹：%s" % args.folder, file=sys.stderr)
        sys.exit(1)

    # Determine output format
    output_fmt = args.format
    if output_fmt in ("md", "markdown"):
        output_fmt = "md"
    else:
        output_fmt = "txt"

    if args.split_chunks:
        # ── 分片模式（Chunked Output）──
        if not HAS_CHUNKER:
            print("错误：分片模块不可用（src/chunker/__init__.py 未找到）", file=sys.stderr)
            sys.exit(1)

        folder_path = args.folder
        # In chunked mode, -o is used directly as the output directory (no extra nesting).
        output_dir = args.output

        chunk_size = args.chunk_size
        if chunk_size == 0:
            chunk_size = None  # no per-chunk limit

        print("[FolderKnowledgeSiteGeneratorForAI] 正在生成分片知识文件到: %s" % output_dir)
        print()

        result = write_chunks(
            folder_path=folder_path,
            output_dir=output_dir,
            chunk_size=chunk_size or CHUNKER_DEFAULT_CHUNK_SIZE,
            max_chars=args.max_chars,
            force_split=args.force_split,
        )

        if result.get("index_file") and result["chunks_count"] > 0:
            print("✅ 分片知识文件生成成功！")
            print(f"   [输出目录] {result['output_dir']}")
            print(f"   [分片数量] {result['chunks_count']}")
            print(f"   [文件总数] {result['total_files']}")
            print(f"   [总字符数] {result['total_chars']:,}")
            print(f"   [索引文件] {result['index_file']}")
        else:
            print("警告：未生成任何分片（文件夹为空或所有文件都无法解析）", file=sys.stderr)
            sys.exit(1)

    elif args.portal:
        # -- 门户模式 --
        if not HAS_PORTAL:
            print("错误：门户模块不可用（src/generator/portal.py 未找到）", file=sys.stderr)
            sys.exit(1)

        output_dir = args.output
        print("[FolderKnowledgeSiteGeneratorForAI] 正在生成知识门户到: %s" % output_dir)
        print()

        max_cpf = args.max_chars_per_file
        if max_cpf == 0:
            max_cpf = None
        
        if args.single_page:
            result = generate_portal(
                folder_path=args.folder,
                output_dir=output_dir,
                include_skipped=not args.no_skipped,
                max_chars_per_file=max_cpf,
                language=args.lang,
            )
        else:
            result = generate_portal_split(
                folder_path=args.folder,
                output_dir=output_dir,
                include_skipped=not args.no_skipped,
                max_chars_per_file=max_cpf,
                language=args.lang,
            )

        index_file = result.get("index_file")
        if index_file and os.path.exists(index_file):
            print("OK - 知识门户生成成功！")
            print("   [输出目录] %s" % result['output_dir'])
            print("   [首页入口] %s" % index_file)
            print("   [文档数量] %d" % result['doc_count'])
            print("   [总字符数] %s" % f"{result['total_chars']:,}")
            if result['skipped']:
                print("   [跳过文件] %d" % result['skipped'])
            if result['errors']:
                print("   [错误文件] %d" % result['errors'])
            print()
            print("[使用提示]")
            if args.single_page:
                print("   1. 双击 index.html 在浏览器中打开")
                print("   2. 搜索关键词找到目标文档")
                print("   3. 点击文档标题在新标签页打开")
                print("   4. 按 Ctrl+Shift+. 唤醒 Edge Copilot 提问")
            else:
                print("   1. 双击 index.html 在浏览器中打开（拆分模式）")
                print("   2. 主页面显示文件树和搜索框，可搜索文件名和关键词")
                print("   3. 点击文件名在新标签页打开对应子页面")
                print("   4. 可一次性按 Ctrl+点击 打开多个标签页")
                print("   5. 唤醒 Edge Copilot 自动读取所有打开标签页的内容")
        else:
            print("警告：未生成任何文档（文件夹为空或所有文件都无法解析）", file=sys.stderr)
            sys.exit(1)
    else:
        # -- 传统 TXT/MD 模式（完整内容，无截断）--
        if args.max_chars is not None:
            print("⚠️  warning: --max-chars has no effect in single TXT mode (no truncation).\n"
                  "   Use --split-chunks to control output size by splitting into multiple files.\n")
        
        if output_fmt == 'md':
            from src.scanner import build_markdown_from_files
            file_list, _ = collect_files_info(args.folder)
            text, parsed, skipped, errors, chars = build_markdown_from_files(
                args.folder, file_list,
                include_skipped=True, language=args.lang)
            output_path = args.output
            if not output_path.lower().endswith('.md'):
                output_path += '.md'
        else:
            text, parsed, skipped, errors, chars = build_text_content(args.folder)
            output_path = args.output
            if not output_path.lower().endswith('.txt'):
                output_path += '.txt'

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        
        fmt_name = "Markdown" if output_fmt == 'md' else "TXT"
        print("OK - 已生成完整知识文件: %s" % output_path)
        print("    Format: %s | 共包含 %d 个文件内容, %d 总字符" % (fmt_name, parsed, chars))
        if skipped:
            print("    %d 个文件被跳过" % skipped)
        if errors:
            print("    %d 个文件解析出错" % errors)
        print()
        print("提示：为避免单个文件过大溢出 LLM 上下文，建议使用：")
        print("  --split-chunks : 按固定大小将内容自动拆分到多个文件")
        print("  --portal       : 生成可搜索的知识门户（推荐）")


if __name__ == "__main__":
    main()