"""
Shared scanning and text building for CLI and GUI.

Provides folder walking with filter rules, file info collection,
and output builders (text, markdown, HTML).
"""

import os
import logging
from html import escape
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

from src.utils import human_readable_size

logger = logging.getLogger(__name__)

# Module-level cache for MIME checker (initialized once, not per-call).
_mime_cache: Optional[tuple] = None

# ── Separator for output formats ──
try:
    from src.constants import SEPARATOR_LINE
except ImportError:
    SEPARATOR_LINE = "=" * 60  # fallback

# ── Import shared filter rules ──
try:
    from src.constants import SUPPORTED_TEXT_EXTS, should_filter_dir, should_filter_file
    FALLBACK_EXTS = SUPPORTED_TEXT_EXTS
except ImportError:
    FALLBACK_EXTS = frozenset({
        '.txt', '.md', '.html', '.htm', '.json', '.xml', '.csv',
        '.yaml', '.yml', '.toml', '.ini', '.log', '.cfg', '.conf',
        '.py', '.pyw', '.js', '.jsx', '.ts', '.tsx', '.css', '.scss', '.less',
        '.sh', '.bash', '.zsh', '.fish', '.bat', '.cmd', '.ps1', '.psm1', '.psd1',
        '.rb', '.java', '.c', '.cpp', '.h', '.hpp', '.cc', '.cxx', '.hh', '.hxx',
        '.rs', '.go', '.php', '.swift', '.kt', '.kts', '.scala',
        '.cs', '.fs', '.vb', '.dart', '.lua', '.r', '.R', '.m', '.mm',
        '.hs', '.erl', '.hrl', '.ex', '.exs', '.elm', '.clj', '.cljs',
        '.sql', '.ddl', '.dml', '.pl', '.pm', '.tcl',
        '.markdown', '.rst', '.text', '.tsv',
        '.pdf', '.docx', '.pptx', '.xlsx',
        '.doc', '.ppt', '.xls', '.wps', '.et', '.dps',
        '.csproj', '.fsproj', '.vbproj', '.sln',
        '.xaml', '.axaml',
    })

    def should_filter_dir(dirname: str) -> bool:
        """Fallback: skip dot-prefixed directories."""
        return dirname.startswith('.')

    def should_filter_file(rel_path: str) -> bool:
        """Fallback: skip dot-prefixed files."""
        return os.path.basename(rel_path).startswith('.')


# ── MIME detection ──

def _get_mime_checker() -> Tuple[Optional[Any], tuple, frozenset, frozenset]:
    """Initialize and cache the MIME detection machinery.

    Returns a cached tuple of (magic_checker, text_prefixes, exact_mimes, fallback_exts).
    The checker object is created once at module load and reused for all calls.
    This avoids repeated `import magic` calls that were noted as a performance issue.

    Returns:
        Tuple of (checker_or_None, prefixes_tuple, exact_set, fallback_extensions).
    """
    global _mime_cache
    if _mime_cache is not None:
        return _mime_cache

    # Try to use centralized constants first
    try:
        from src.constants import (
            TEXT_MIME_PREFIXES, EXACT_MIME_SET
        )
        prefixes = tuple(TEXT_MIME_PREFIXES)
        exact = frozenset(EXACT_MIME_SET)
    except ImportError:
        prefixes = ('text/',)
        exact = frozenset({
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/msword', 'application/vnd.ms-powerpoint', 'application/vnd.ms-excel',
        })

    try:
        import magic
        checker = magic.Magic(mime=True)
        _mime_cache = (checker, prefixes, exact, FALLBACK_EXTS)
        return _mime_cache
    except (ImportError, AttributeError, OSError) as e:
        logger.debug("python-magic unavailable (%s), falling back to extension-based detection", e)
        _mime_cache = (None, (), frozenset(), FALLBACK_EXTS)
        return _mime_cache
    except Exception as e:
        # Unexpected error (e.g., ctypes corruption) — still recover gracefully
        logger.debug("Unexpected error loading python-magic: %s", e, exc_info=True)
        _mime_cache = (None, (), frozenset(), FALLBACK_EXTS)
        return _mime_cache


def is_file_supported(full_path: str, ext: str) -> bool:
    """Check if a file is supported via MIME type, falling back to extension.

    Strategy:
    1. If python-magic is available, detect MIME type from file content.
       - Returns True for text/* MIME types and known exact matches (PDF, Office).
    2. If python-magic is unavailable or fails, fall back to extension matching
       against the supported text extensions list.

    Args:
        full_path: Absolute path to the file.
        ext: Lowercase file extension (including dot, e.g., '.py').

    Returns:
        True if the file should be parsed, False otherwise.
    """
    checker, prefixes, exact, fallback_exts = _get_mime_checker()
    if checker is not None:
        try:
            mime = checker.from_file(full_path)
            if mime.startswith(prefixes) or mime in exact:
                return True
        except (OSError, IOError) as e:
            # File may have been deleted between scan and check, or permissions issue
            logger.debug("MIME detection I/O error for %s: %s", full_path, e)
        except Exception as e:
            # python-magic may raise MagicException on some edge cases
            logger.debug("MIME detection failed for %s: %s", full_path, e)
    return ext in fallback_exts


# ── Shared folder walker ──

def walk_files(root_dir: str):
    """Yield (full_path, rel_path) for all non-filtered files under root_dir.

    Used by both CLI (generate.py) and GUI (collect_files_info).
    Filters directories and files according to the rules defined in
    constants.py (should_filter_dir, should_filter_file).

    Args:
        root_dir: Root directory path to walk.

    Yields:
        Tuple of (full_path: str, rel_path: str) for each accepted file.
    """
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if not should_filter_dir(d)]
        for fname in filenames:
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, root_dir)
            if should_filter_file(rel_path):
                continue
            if os.path.isfile(full_path):
                yield full_path, rel_path


# ── File info collection (GUI) ──

def collect_files_info(root_dir: str) -> Tuple[List[Dict[str, Any]], int]:
    """Scan folder, return file list with metadata and total size.

    Collects file path, relative path, size (bytes and human-readable),
    extension, and whether the file is supported for parsing.

    Args:
        root_dir: Root directory path to scan.

    Returns:
        Tuple of (file_list, total_size):
        - file_list: List of dicts with keys {path, rel_path, size, size_hr, ext, supported}
        - total_size: Total bytes of all collected files
    """
    file_list: List[Dict[str, Any]] = []
    total_size = 0
    try:
        for full_path, rel_path in walk_files(root_dir):
            try:
                file_size = os.path.getsize(full_path)
            except OSError as e:
                logger.warning("Cannot get size for %s: %s", full_path, e)
                continue
            ext = os.path.splitext(rel_path)[1].lower()
            supported = is_file_supported(full_path, ext)
            file_list.append({
                'path': full_path, 'rel_path': rel_path,
                'size': file_size, 'size_hr': human_readable_size(file_size),
                'ext': ext, 'supported': supported,
            })
            total_size += file_size
    except OSError as e:
        logger.error("Error scanning folder %s: %s", root_dir, e, exc_info=True)
    except Exception as e:
        logger.error("Unexpected error scanning folder %s: %s", root_dir, e, exc_info=True)
    return file_list, total_size


# ── Label helpers ──

def _txt_labels(language: str) -> Dict[str, str]:
    """Return label dict for text/markdown builders.

    Args:
        language: ISO 639-1 language code ('zh' for Chinese, otherwise English).

    Returns:
        Dict mapping label keys to localized strings.
    """
    if language == 'zh':
        return {
            'size': '文件大小', 'chars': '字符数', 'unsupported': '不支持的格式',
            'source': '文件夹名', 'files': '解析文件数', 'total_chars': '总字符数',
        }
    return {
        'size': 'File size', 'chars': 'Characters', 'unsupported': 'Unsupported format',
        'source': 'Source folder', 'files': 'Files parsed', 'total_chars': 'Total characters',
    }


# ── Text output builder ──

def build_text_from_files(
    folder_path: str,
    file_list: List[Dict[str, Any]],
    include_skipped: bool = False,
) -> Tuple[str, int, int, int, int]:
    """Generate plain text output with file separators. No truncation.

    Iterates through file_list, parses each supported file, and concatenates
    their content with separator headers.

    Args:
        folder_path: Absolute path to the source folder.
        file_list: List of file info dicts from collect_files_info().
        include_skipped: If True, include [SKIPPED] entries in output.

    Returns:
        Tuple of (text, parsed_count, skipped_count, error_count, total_chars).
    """
    from src.parser.dispatcher import parse_file

    parts = []
    total_chars = 0
    parsed_count = 0
    skipped_count = 0
    error_count = 0
    sep = SEPARATOR_LINE

    for finfo in file_list:
        if not finfo['supported']:
            skipped_count += 1
            if include_skipped:
                parts.append(f"{sep}\n[SKIPPED] {finfo['rel_path']} (Size: {finfo['size_hr']})\n{sep}\n")
            continue
        try:
            result = parse_file(finfo['path'])
            if result is None:
                skipped_count += 1
                continue
            text = (result.get("text") or "").strip()
        except (OSError, IOError) as e:
            logger.debug("I/O error parsing %s: %s", finfo['rel_path'], e)
            error_count += 1
            continue
        except Exception as e:
            logger.debug("Unexpected error parsing %s: %s", finfo['rel_path'], e)
            error_count += 1
            continue

        if not text:
            skipped_count += 1
            continue

        parts.append(
            f"{sep}\nFile: {finfo['rel_path']}\nSize: {finfo['size_hr']}\n"
            f"Characters: {len(text):,}\nType: {os.path.splitext(finfo['rel_path'])[1] or 'plain'}\n{sep}\n"
            f"{text}\n\n"
        )
        total_chars += len(text)
        parsed_count += 1

    header = (
        f"Folder Knowledge Export\nSource: {os.path.abspath(folder_path)}\n"
        f"Parsed files: {parsed_count}\nSkipped files: {skipped_count}\n"
        f"Errors: {error_count}\nTotal characters: {total_chars:,}\n{sep}\n\n"
    )
    return header + ''.join(parts), parsed_count, skipped_count, error_count, total_chars


# ── Markdown output builder ──

def build_markdown_from_files(
    folder_path: str,
    file_list: List[Dict[str, Any]],
    include_skipped: bool = False,
    language: str = "en",
    verbose: bool = True,
) -> Tuple[str, int, int, int, int]:
    """Generate Markdown output with syntax-highlighted code blocks per file.

    Each file is rendered as a Markdown section with metadata (size, chars)
    and its content wrapped in a fenced code block with an appropriate language tag.

    Args:
        folder_path: Absolute path to the source folder.
        file_list: List of file info dicts from collect_files_info().
        include_skipped: If True, include skipped-file annotations in output.
        language: ISO 639-1 language code for labels ('zh' or 'en').
        verbose: If True, print skip/error summaries to stdout.

    Returns:
        Tuple of (markdown_text, parsed_count, skipped_count, error_count, total_chars).
    """
    from src.parser.dispatcher import parse_file

    labels = _txt_labels(language)
    sections = []
    total_chars = 0
    parsed_count = 0
    skipped_count = 0
    error_count = 0
    skip_reasons: Dict[str, int] = {}

    for finfo in file_list:
        if not finfo['supported']:
            skipped_count += 1
            skip_reasons['unsupported format'] = skip_reasons.get('unsupported format', 0) + 1
            if include_skipped:
                sections.append(
                    f"---\n\n## ⏭️ {finfo['rel_path']}\n\n"
                    f"**{labels['unsupported']}** | **{labels['size']}**: {finfo['size_hr']}\n\n"
                    f"> *This file format is not supported.*\n"
                )
            continue
        try:
            result = parse_file(finfo['path'])
            if result is None:
                skipped_count += 1
                skip_reasons['parser returned no content'] = skip_reasons.get('parser returned no content', 0) + 1
                continue
            text = (result.get("text") or "").strip()
        except (OSError, IOError) as e:
            logger.debug("I/O error parsing %s: %s", finfo['rel_path'], e)
            error_count += 1
            continue
        except Exception as e:
            logger.debug("Unexpected error parsing %s: %s", finfo['rel_path'], e)
            error_count += 1
            continue

        if not text:
            skipped_count += 1
            skip_reasons['empty content after parsing'] = skip_reasons.get('empty content after parsing', 0) + 1
            continue

        lang_tag = _md_lang_tag(os.path.splitext(finfo['rel_path'])[1].lower())
        rel_path_clean = finfo['rel_path'].replace('\\', '/')
        section = (
            f"---\n\n## 📄 {rel_path_clean}\n\n"
            f"**{labels['size']}**: {finfo['size_hr']}  \n**{labels['chars']}**: {len(text):,}\n\n"
            f"```{lang_tag}\n{text}\n```\n"
        )
        sections.append(section)
        total_chars += len(text)
        parsed_count += 1

    if verbose and skip_reasons:
        print(f"[Skip Summary] {skipped_count} files skipped:")
        for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            print(f"  - {count} file(s): {reason}")
    if verbose and error_count:
        print(f"[Error Summary] {error_count} file(s) failed to parse")

    folder_name = os.path.basename(os.path.abspath(folder_path))
    header = (
        f"# {labels['source']}：{folder_name}\n\n"
        f"**{labels['files']}**：{parsed_count}，**{labels['total_chars']}**：{total_chars:,}\n\n---\n\n"
    )
    return header + ''.join(sections), parsed_count, skipped_count, error_count, total_chars


def _md_lang_tag(ext: str) -> str:
    """Map file extension to a Markdown fenced-code-block language tag.

    The mapping is based on common conventions for syntax highlighting
    in Markdown renderers (GitHub, VS Code, etc.). Unknown extensions
    return an empty string (no language tag).

    Args:
        ext: Lowercase file extension including dot (e.g., '.py').

    Returns:
        Language tag string for the Markdown code fence, or '' if unknown.
    """
    return {
        '.py': 'python', '.pyw': 'python', '.js': 'javascript', '.jsx': 'jsx',
        '.ts': 'typescript', '.tsx': 'tsx', '.html': 'html', '.css': 'css',
        '.scss': 'scss', '.less': 'less', '.json': 'json', '.xml': 'xml',
        '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml', '.md': 'markdown',
        '.rst': 'rst', '.sh': 'bash', '.bash': 'bash', '.zsh': 'bash',
        '.fish': 'fish', '.bat': 'batch', '.cmd': 'batch', '.ps1': 'powershell',
        '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.hpp': 'cpp', '.cs': 'csharp',
        '.java': 'java', '.go': 'go', '.rs': 'rust', '.rb': 'ruby',
        '.php': 'php', '.swift': 'swift', '.kt': 'kotlin', '.kts': 'kotlin',
        '.sql': 'sql', '.lua': 'lua', '.r': 'r', '.R': 'r', '.dart': 'dart',
        '.scala': 'scala', '.pl': 'perl', '.pm': 'perl', '.tex': 'latex',
        '.cfg': 'ini', '.ini': 'ini', '.conf': 'ini',
    }.get(ext, '')


# ── HTML output builder (legacy single-page) ──

def build_html_from_files(
    folder_path: str,
    file_list: List[Dict[str, Any]],
    output_path: str,
    include_skipped: bool = True,
    language: str = "en",
    verbose: bool = True,
) -> Tuple[str, int, int, int, int]:
    """Generate single-page HTML with all file contents (legacy, not recommended).

    Note: This is a legacy function. For new development, prefer the portal
    generator (src/generator/portal.py) which produces split-page output.

    Args:
        folder_path: Absolute path to the source folder.
        file_list: List of file info dicts from collect_files_info().
        output_path: Not used in output generation (legacy parameter).
        include_skipped: If True, render skipped-file entries.
        language: ISO 639-1 language code ('zh' for Chinese).
        verbose: If True, print skip/error summaries to stdout.

    Returns:
        Tuple of (html_text, parsed_count, skipped_count, error_count, total_chars).
    """
    from src.parser.dispatcher import parse_file

    articles = []
    total_chars = 0
    parsed_count = 0
    skipped_count = 0
    error_count = 0
    skip_reasons: Dict[str, int] = {}

    for finfo in file_list:
        if not finfo['supported']:
            if include_skipped:
                articles.append(
                    f"  <article class=\"skipped\">\n"
                    f"    <h2>⏭️ {escape(finfo['rel_path'])}</h2>\n"
                    f"    <p class=\"meta\">Unsupported | Size: {escape(finfo['size_hr'])}</p>\n"
                    f"  </article>"
                )
            skipped_count += 1
            skip_reasons['unsupported format'] = skip_reasons.get('unsupported format', 0) + 1
            continue
        try:
            result = parse_file(finfo['path'])
            if result is None:
                skipped_count += 1
                skip_reasons['parser returned no content'] = skip_reasons.get('parser returned no content', 0) + 1
                continue
            text = (result.get("text") or "").strip()
        except (OSError, IOError) as e:
            logger.debug("I/O error parsing %s: %s", finfo['rel_path'], e)
            error_count += 1
            continue
        except Exception as e:
            logger.debug("Unexpected error parsing %s: %s", finfo['rel_path'], e)
            error_count += 1
            continue

        if not text:
            skipped_count += 1
            skip_reasons['empty content after parsing'] = skip_reasons.get('empty content after parsing', 0) + 1
            continue

        articles.append(
            f"  <article>\n"
            f"    <h2>📄 {escape(finfo['rel_path'])}</h2>\n"
            f"    <p class=\"meta\">Size: {escape(finfo['size_hr'])} | Content: {len(text)} chars</p>\n"
            f"    <p>{escape(text)}</p>\n"
            f"  </article>"
        )
        total_chars += len(text)
        parsed_count += 1

    if verbose and skip_reasons:
        print(f"[Skip Summary] {skipped_count} files skipped:")
        for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            print(f"  - {count} file(s): {reason}")
    if verbose and error_count:
        print(f"[Error Summary] {error_count} file(s) failed to parse")

    folder_name = escape(os.path.basename(os.path.abspath(folder_path)))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html_lang = "zh-CN" if language == "zh" else "en"

    html = (
        f"<!DOCTYPE html>\n<html lang=\"{html_lang}\">\n<head>\n"
        f"<meta charset=\"UTF-8\">\n"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        f"<title>Knowledge Export - {folder_name}</title>\n"
        f"<style>\n"
        f"  * {{ margin: 0; padding: 0; box-sizing: border-box; }}\n"
        f"  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; "
        f"max-width: 960px; margin: 0 auto; padding: 20px; background: #f8f9fa; color: #333; }}\n"
        f"  .header {{ background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 20px; "
        f"box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}\n"
        f"  .header h1 {{ font-size: 1.5em; color: #1a73e8; margin-bottom: 8px; }}\n"
        f"  .header .meta {{ color: #666; font-size: 0.9em; line-height: 1.8; }}\n"
        f"  article {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; "
        f"padding: 16px; margin-bottom: 12px; transition: box-shadow 0.2s; }}\n"
        f"  article:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,0.1); }}\n"
        f"  article.skipped {{ opacity: 0.6; background: #f5f5f5; }}\n"
        f"  h2 {{ font-size: 1em; color: #1a73e8; margin-bottom: 6px; word-break: break-all; }}\n"
        f"  .meta {{ color: #888; font-size: 0.82em; margin-bottom: 8px; }}\n"
        f"  p {{ white-space: pre-wrap; word-break: break-word; font-size: 0.93em; line-height: 1.7; }}\n"
        f"  .footer {{ text-align: center; color: #999; font-size: 0.85em; padding: 20px; }}\n"
        f"</style>\n</head>\n<body>\n"
        f"  <div class=\"header\">\n"
        f"    <h1>📁 {folder_name}</h1>\n"
        f"    <div class=\"meta\">\n"
        f"      <span>📄 Files: {parsed_count}</span>\n"
        f"      <span>📝 Total chars: {total_chars:,}</span>\n"
        f"      <span>🕐 Exported: {now}</span>\n"
        f"      <span>📂 Source: {escape(os.path.abspath(folder_path))}</span>\n"
        f"    </div>\n  </div>\n"
        f"{''.join(articles)}\n"
        f"  <div class=\"footer\">\n"
        f"    <p>Generated by FolderKnowledgeSiteGeneratorForAI | Total {parsed_count} files, {total_chars:,} chars | {now}</p>\n"
        f"  </div>\n</body>\n</html>"
    )
    return html, parsed_count, skipped_count, error_count, total_chars