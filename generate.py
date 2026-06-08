#!/usr/bin/env python3
"""
FolderKnowledgeSiteGeneratorForAI — Folder to Knowledge TXT / Portal / Chunked Generator

Three output modes:
  1. TXT/Markdown export: single-file output (python generate.py <folder> -o <output> [--format md])
  2. Chunked export: split into part_NNN.txt files (python generate.py <folder> --split-chunks -o <dir>)
  3. Portal export: searchable HTML knowledge portal
     - Single-page: --portal-mode single (all content in one index.html)
     - Split-file: --portal-mode split (index.html + docs/*.html subpages) [default]

Usage examples:
    # TXT mode (single file)
    python generate.py <folder_path> -o <output.txt>

    # Markdown mode
    python generate.py <folder_path> -o <output.md> --format md

    # Chunked mode (split into multiple files)
    python generate.py <folder_path> --split-chunks -o <output_dir/>

    # Portal mode (split-file, default)
    python generate.py <folder_path> --portal-mode split -o <output_dir/>

    # Portal mode (single-page, all content in one file)
    python generate.py <folder_path> --portal-mode single -o <output_dir/>

Deprecated flags (still accepted but will be removed in a future version):
    --portal          → use --portal-mode split (default portal mode)
    --single-page     → use --portal-mode single
    --split-files     → use --portal-mode split
"""

import os
import sys
import pathlib
import argparse
import logging
import io

# Fix console encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure the project root is on sys.path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from src.scanner import build_text_from_files, collect_files_info

# Lazy imports
_HAS_PORTAL = None
_HAS_CHUNKER = None


def _check_portal():
    global _HAS_PORTAL
    if _HAS_PORTAL is None:
        try:
            from src.generator.portal import generate_portal, generate_portal_split
            _HAS_PORTAL = True
        except ImportError:
            _HAS_PORTAL = False
    return _HAS_PORTAL


def _check_chunker():
    global _HAS_CHUNKER
    if _HAS_CHUNKER is None:
        try:
            from src.chunker import write_chunks, DEFAULT_CHUNK_SIZE as CHUNKER_DEFAULT
            _HAS_CHUNKER = True
        except ImportError:
            _HAS_CHUNKER = False
    return _HAS_CHUNKER


# Logger setup
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def build_text_content(folder_path: str):
    """Parse all files under folder_path and return full text content.

    Args:
        folder_path: Absolute path to the source folder.

    Returns:
        Tuple of (text, parsed_count, skipped_count, error_count, total_chars).
    """
    file_list, _ = collect_files_info(folder_path)
    text, parsed, skipped, errors, chars = build_text_from_files(
        folder_path, file_list, include_skipped=True,
    )
    return text, parsed, skipped, errors, chars


def _resolve_portal_mode(args) -> str | None:
    """Resolve portal mode from CLI args, with deprecation handling.

    Priority: --portal-mode > --single-page > --portal > default (split).

    Returns:
        'single', 'split', or None if portal mode is not requested.
    """
    # New unified flag takes priority
    if hasattr(args, 'portal_mode') and args.portal_mode:
        return args.portal_mode

    # Deprecated flags — resolve with deprecation notices
    if hasattr(args, 'single_page') and args.single_page:
        print(
            "[DEPRECATED] --single-page is deprecated. Use --portal-mode single instead.",
            file=sys.stderr,
        )
        return 'single'

    if hasattr(args, 'split_files') and args.split_files:
        print(
            "[DEPRECATED] --split-files is deprecated. Use --portal-mode split instead.",
            file=sys.stderr,
        )
        return 'split'

    if hasattr(args, 'portal') and args.portal:
        print(
            "[NOTICE] --portal is deprecated. The default portal mode is now split-file. "
            "Use --portal-mode single for single-page mode.",
            file=sys.stderr,
        )
        return 'split'

    return None


def main():
    parser = argparse.ArgumentParser(
        description="FolderKnowledgeSiteGeneratorForAI - Generate TXT, chunked, or portal output from folders",
    )
    parser.add_argument(
        "folder", help="Folder path to scan",
    )
    parser.add_argument(
        "-o", "--output", required=True,
        help="Output path: file path for TXT/MD mode, directory path for chunked/portal modes",
    )

    # ── Output format ──
    parser.add_argument(
        "--format", "--fmt", type=str, default="txt",
        choices=["txt", "md", "markdown"],
        help="Output format for text export mode: txt or md (default: txt)",
    )

    # ── Portal mode (unified) ──
    parser.add_argument(
        "--portal-mode", type=str, default=None,
        choices=["single", "split"],
        help="Portal mode: 'single' (all content in one page) or 'split' (index + per-file subpages, default)",
    )

    # ── Chunked mode ──
    parser.add_argument(
        "--split-chunks", action="store_true",
        help="Split output into multiple part_NNN.txt files with character limit per chunk",
    )
    parser.add_argument(
        "--force-split", action="store_true",
        help="[Chunked mode] Split oversized files across multiple chunks instead of dedicated chunks",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=500_000,
        help="[Chunked mode] Max characters per chunk (default: 500,000)",
    )
    parser.add_argument(
        "--max-chars", type=int, default=None,
        help="[Chunked mode] Total character limit across all chunks (default: no limit)",
    )

    # ── Portal-specific options ──
    parser.add_argument(
        "--no-skipped", action="store_true",
        help="[Portal mode] Hide skipped file entries in the file tree",
    )
    parser.add_argument(
        "--max-chars-per-file", type=int, default=50_000,
        help="[Portal mode] Max characters per file before truncation (default: 50,000; 0 = no limit)",
    )

    # ── Common options ──
    parser.add_argument(
        "--lang", "--language", type=str, default="en",
        choices=["en", "zh"],
        help="Output language: en=English, zh=Chinese (default: en)",
    )
    parser.add_argument(
        "--log-file", type=str, default=None,
        help="Write detailed debug log to a file",
    )

    # ── Deprecated flags (hidden, accepted for backward compatibility) ──
    parser.add_argument(
        "--portal", action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--single-page", action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--split-files", action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    # ── Configure log file ──
    if args.log_file:
        try:
            file_handler = logging.FileHandler(args.log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            ))
            root_logger = logging.getLogger()
            root_logger.addHandler(file_handler)
            for handler in root_logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setLevel(logging.INFO)
            logger.info("Detailed logging enabled → %s", args.log_file)
        except Exception as e:
            print(f"Warning: Cannot write log to {args.log_file} ({e})", file=sys.stderr)

    if not os.path.isdir(args.folder):
        print("Error: not a valid folder: %s" % args.folder, file=sys.stderr)
        sys.exit(1)

    # ── Resolve mode ──
    portal_mode = _resolve_portal_mode(args)

    # ── Route to appropriate handler ──
    if args.split_chunks:
        _run_chunked_mode(args)
    elif portal_mode:
        _run_portal_mode(args, portal_mode)
    else:
        _run_text_mode(args)


def _run_text_mode(args):
    """TXT/Markdown mode: single file output."""
    output_fmt = "md" if args.format in ("md", "markdown") else "txt"

    if args.max_chars is not None:
        print(
            "[WARNING] --max-chars has no effect in text export mode.\n"
            "  Use --split-chunks to control output size by splitting into multiple files.\n",
            file=sys.stderr,
        )

    if output_fmt == 'md':
        from src.scanner import build_markdown_from_files
        file_list, _ = collect_files_info(args.folder)
        text, parsed, skipped, errors, chars = build_markdown_from_files(
            args.folder, file_list, include_skipped=True, language=args.lang,
        )
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
    print("OK - Generated: %s" % output_path)
    print("    Format: %s | %d files, %d total chars" % (fmt_name, parsed, chars))
    if skipped:
        print("    %d files skipped" % skipped)
    if errors:
        print("    %d files with errors" % errors)
    print()
    print("Tip: For large folders, consider:")
    print("  --split-chunks : split output into multiple part_NNN.txt files")
    print("  --portal-mode split : generate a searchable split-file knowledge portal")


def _run_chunked_mode(args):
    """Chunked mode: split into part_NNN.txt files."""
    if not _check_chunker():
        print("Error: Chunked output module (src/chunker) not available", file=sys.stderr)
        sys.exit(1)

    from src.chunker import write_chunks

    chunk_size = args.chunk_size
    if chunk_size == 0:
        chunk_size = None

    output_dir = args.output
    print("[FolderKnowledgeSiteGeneratorForAI] Generating chunked knowledge files to: %s" % output_dir)
    print()

    result = write_chunks(
        folder_path=args.folder,
        output_dir=output_dir,
        chunk_size=chunk_size or 500_000,
        max_chars=args.max_chars,
        force_split=args.force_split,
    )

    if result.get("index_file") and result["chunks_count"] > 0:
        print("OK - Chunked files generated!")
        print("    [Output dir] %s" % result['output_dir'])
        print("    [Chunks] %d" % result['chunks_count'])
        print("    [Files] %d" % result['total_files'])
        print("    [Total chars] %s" % f"{result['total_chars']:,}")
        print("    [Index] %s" % result['index_file'])
    else:
        print("Warning: No chunks generated (folder empty or all files unparseable)", file=sys.stderr)
        sys.exit(1)


def _run_portal_mode(args, portal_mode: str):
    """Portal mode: generate searchable HTML knowledge portal."""
    if not _check_portal():
        print("Error: Portal module (src/generator/portal) not available", file=sys.stderr)
        sys.exit(1)

    from src.generator.portal import generate_portal, generate_portal_split

    output_dir = args.output
    max_cpf = args.max_chars_per_file
    if max_cpf == 0:
        max_cpf = None

    if portal_mode == 'single':
        print("[FolderKnowledgeSiteGeneratorForAI] Generating single-page portal to: %s" % output_dir)
        print()
        result = generate_portal(
            folder_path=args.folder,
            output_dir=output_dir,
            include_skipped=not args.no_skipped,
            max_chars_per_file=max_cpf,
            language=args.lang,
        )
    else:
        print("[FolderKnowledgeSiteGeneratorForAI] Generating split-file portal to: %s" % output_dir)
        print()
        result = generate_portal_split(
            folder_path=args.folder,
            output_dir=output_dir,
            include_skipped=not args.no_skipped,
            max_chars_per_file=max_cpf,
            language=args.lang,
        )

    index_file = result.get("index_file")
    if index_file and os.path.exists(index_file):
        mode_label = "single-page" if portal_mode == 'single' else "split-file"
        print("OK - %s portal generated!" % mode_label.capitalize())
        print("    [Output dir] %s" % result['output_dir'])
        print("    [Index] %s" % index_file)
        print("    [Documents] %d" % result['doc_count'])
        print("    [Total chars] %s" % f"{result['total_chars']:,}")
        if result['skipped']:
            print("    [Skipped] %d" % result['skipped'])
        if result['errors']:
            print("    [Errors] %d" % result['errors'])
        print()
        print("Usage:")
        if portal_mode == 'single':
            print("  1. Open index.html in browser")
            print("  2. Use Ctrl+Shift+. to activate Edge Copilot for AI reading")
            print("  3. Search keywords to find specific files")
        else:
            print("  1. Open index.html in browser (file tree + search)")
            print("  2. Click file names to open individual subpages")
            print("  3. Open multiple tabs for AI to read across pages")
    else:
        print("Warning: No documents generated (folder empty or all files unparseable)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()