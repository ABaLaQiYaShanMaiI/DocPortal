"""
FolderKnowledgeSiteGeneratorForAI — HTML Templates
Loads and renders HTML templates from the templates/ directory.
Generates single-page knowledge portal with collapsible file contents.
"""

import os
import string
import base64
from html import escape
from src.utils import human_readable_size

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
_TEMPLATE_CACHE: dict[str, str] = {}


def _load_template(name: str) -> str:
    if name not in _TEMPLATE_CACHE:
        path = os.path.join(_TEMPLATES_DIR, name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Template not found: {path}")
        with open(path, encoding="utf-8") as f:
            _TEMPLATE_CACHE[name] = f.read()
    return _TEMPLATE_CACHE[name]


# Import shared type mappings from constants module
try:
    from src.constants import FILE_TYPE_MAP, FILE_TYPE_ICONS
except ImportError:
    # Fallback mappings if constants module unavailable
    FILE_TYPE_MAP = {
        '.txt': 'TXT', '.md': 'Markdown', '.py': 'Python', '.js': 'JavaScript',
        '.ts': 'TypeScript', '.html': 'HTML', '.css': 'CSS', '.json': 'JSON',
        '.xml': 'XML', '.yaml': 'YAML', '.yml': 'YAML', '.csv': 'CSV',
        '.ini': 'Config', '.cfg': 'Config', '.conf': 'Config',
        '.cs': 'C#', '.java': 'Java', '.cpp': 'C++', '.h': 'C Header',
        '.go': 'Go', '.rs': 'Rust', '.swift': 'Swift', '.kt': 'Kotlin',
        '.rb': 'Ruby', '.php': 'PHP', '.sh': 'Shell Script', '.bat': 'Batch',
        '.ps1': 'PowerShell', '.sql': 'SQL', '.r': 'R',
    }
    FILE_TYPE_ICONS = {
        'Python': '🐍', 'JavaScript': '🟨', 'TypeScript': '🔵',
        'HTML': '🌐', 'CSS': '🎨', 'Markdown': '📝', 'TXT': '📄',
        'C#': '🔷', 'Java': '☕', 'Go': '🔷', 'Rust': '🦀',
        'Swift': '🍎', 'Kotlin': '🅺',
    }


def _get_file_type(filename: str) -> str:
    """Determine file type from extension using shared constants."""
    ext = os.path.splitext(filename)[1].lower()
    return FILE_TYPE_MAP.get(ext, ext.upper().lstrip('.').replace('.', '') if ext else 'Unknown')


def _get_file_type_icon(file_type: str) -> str:
    """Return an emoji icon for the given file type using shared constants."""
    return FILE_TYPE_ICONS.get(file_type, '📄')


def build_file_content_blocks(docs_texts: list) -> str:
    """
    Build HTML file blocks for all file contents — always expanded.

    Each block has:
      - doc-header: icon, filename, size, tags, copy button (no toggle)
      - doc-content: code preview (always visible, with minimal font for AI density)

    Args:
        docs_texts: list of dicts with keys:
            - title: display title / relative path
            - text: full file text content
            - size: char count
            - file_type: file type string
            - size_hr: human-readable size (optional)
            - tags: list of keyword strings (optional)

    Returns:
        HTML string with always-expanded file blocks
    """
    parts = []
    for i, doc in enumerate(docs_texts):
        title = doc.get("title", f"file_{i}")
        text = doc.get("text", "")
        size = doc.get("size", 0)
        file_type = doc.get("file_type", _get_file_type(title))
        size_hr = doc.get("size_hr", "")
        tags = doc.get("tags", []) or []

        escaped_title = escape(title)
        escaped_text = escape(text)
        size_str = f"{size:,}" if size else "0"
        size_hr_escaped = escape(size_hr)
        # Base64 encode the filename to avoid CSS selector escaping issues
        # with special characters like &, ", ', etc.
        safe_filename_b64 = base64.b64encode(title.replace('\\', '/').encode('utf-8')).decode('ascii')

        # Build pre-computed search index (lowercase title + tags for fast JS filtering)
        search_index = (title.lower() + ' ' + ' '.join(t.lower() for t in tags)).strip()
        safe_search_index = escape(search_index)

        # Build tags string
        tags_html = ""
        for tag in tags[:5]:
            safe_tag = escape(tag)
            tags_html += f'<span class="file-tag">{safe_tag}</span>'

        # File type icon
        type_icon = _get_file_type_icon(file_type)

        # Build the file block with header + always-visible content + copy button
        # Content area always visible (no display:none), toggles are removed
        block = (
            f'<div class="doc-block" data-filename-b64="{safe_filename_b64}" data-index="{safe_search_index}">\n'
            f'  <div class="doc-header">\n'
            f'    <span class="file-icon">{type_icon}</span>\n'
            f'    <span class="file-name">{escaped_title}</span>\n'
            f'    <span class="file-size">{size_hr_escaped}</span>\n'
            f'    <span class="file-chars">{size_str} chars</span>\n'
            f'    <span class="file-tags">{tags_html}</span>\n'
    f'    <button class="copy-file-btn" data-file-index="{i}" onclick="copyFileContent(this)" title="Copy this file">📋 Copy</button>\n'
            f'  </div>\n'
            f'  <div class="doc-content">\n'
            f'    <pre id="file-content-{i}"><code>{escaped_text}</code></pre>\n'
            f'  </div>\n'
            f'</div>'
        )
        parts.append(block)

    return "\n".join(parts)


def build_ai_raw_text_block(
    docs_texts: list,
    folder_name: str,
    total_chars: int,
    generated_at: str,
) -> str:
    """
    Build a hidden AI-readable plain-text block containing all file contents.

    This produces a pure-text representation of all files, separated by
    ASCII dividers, wrapped in a <pre> tag. It is placed in the HTML with
    'position: absolute; left: -9999px' so that:
      - Human users never see it
      - Screen readers skip it (via aria-hidden="true")
      - AI text extractors (Edge Copilot, ChatGPT, etc.) can read the full
        content because they check 'display' property, not visual position

    Args:
        docs_texts: list of dicts with keys:
            - title: display title / relative path
            - text: full file text content
            - size: char count
            - size_hr: human-readable size (optional)
        folder_name: Source folder name
        total_chars: Total character count across all files
        generated_at: Timestamp string

    Returns:
        HTML string: a <pre> block containing all file texts in plain text
        format, already HTML-escaped and ready for template insertion.
    """
    lines = []

    # ── Header / metadata block ──
    lines.append("=" * 80)
    lines.append("  KNOWLEDGE PORTAL — AI-READABLE TEXT EXTRACT")
    lines.append("=" * 80)
    lines.append(f"  Source folder : {folder_name}")
    lines.append(f"  Total files   : {len(docs_texts)}")
    lines.append(f"  Total chars   : {total_chars:,}")
    lines.append(f"  Generated at  : {generated_at}")
    lines.append("=" * 80)
    lines.append("")

    # ── Each file ──
    for i, doc in enumerate(docs_texts):
        title = doc.get("title", f"file_{i}")
        text = doc.get("text", "")
        size = doc.get("size", 0)
        size_hr = doc.get("size_hr", "")

        # File header separator
        lines.append("-" * 80)
        lines.append(f"  FILE: {title}")
        lines.append(f"  Size: {size_hr}  |  {size:,} characters")
        lines.append("-" * 80)
        lines.append("")

        # The actual file content — keep as-is (will be HTML-escaped once as a whole)
        lines.append(text)

        # Trailing newline before next file
        lines.append("")

    # Footer
    lines.append("=" * 80)
    lines.append("  END OF AI-READABLE TEXT EXTRACT")
    lines.append("=" * 80)

    raw_text = "\n".join(lines)

    # HTML-escape the entire block and wrap in <pre> tags for formatting preservation
    escaped_raw_text = escape(raw_text)

    return f"<pre>{escaped_raw_text}</pre>"


def _format_total_size(docs_meta: list) -> str:
    total = sum(d.get("size", 0) for d in docs_meta)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if total < 1024:
            return f"{total:.1f} {unit}"
        total /= 1024
    return f"{total:.1f} TB"


def _path_to_subpage_filename(rel_path: str) -> str:
    """Convert a file's relative path into a safe HTML filename for the subpage.

    Examples:
        src/parser/text_parser.py → src_parser_text_parser.html
        README.md → README.html
    """
    safe = rel_path.replace('\\', '/').replace('/', '_')
    # Replace other potentially problematic characters
    safe = safe.replace(' ', '_').replace('#', '_').replace('?', '_')
    safe = safe.replace('%', '_').replace('&', '_').replace('=', '_')
    return safe + '.html'


def build_subpage_html(
    doc: dict,
    folder_name: str,
    language: str = "en",
) -> str:
    """Generate a standalone HTML subpage for a single file.

    Args:
        doc: Dict with keys: title, text, size, size_hr, file_type, tags
        folder_name: Project/source folder name
        language: Language code ('en' or 'zh')

    Returns:
        Complete HTML string for the subpage
    """
    template = _load_template("subpage.html")

    title = doc.get("title", "unknown")
    text = doc.get("text", "")
    size = doc.get("size", 0)
    size_hr = doc.get("size_hr", "")
    tags = doc.get("tags", []) or []

    escaped_title = escape(title)
    escaped_text = escape(text)
    escaped_folder = escape(folder_name)

    # Build i18n text
    if language == "zh":
        back_text = "返回索引"
        copy_text = "复制代码"
        copied_text = "✅ 已复制！"
        size_text = "大小"
        chars_text = "字符"
        generated_by_text = "由"
    else:
        back_text = "Back to Index"
        copy_text = "Copy Code"
        copied_text = "✅ Copied!"
        size_text = "Size"
        chars_text = "Chars"
        generated_by_text = "Generated by"

    # Build tags HTML for meta line
    meta_tags_html = ""
    for tag in tags[:5]:
        safe_tag = escape(tag)
        meta_tags_html += f'<span class="file-tag" style="background:#e8f0fe;color:#1a73e8;border-radius:6px;padding:1px 6px;font-size:0.85em;">{safe_tag}</span>'
    if meta_tags_html:
        meta_tags_html = f'<span>🏷️ {meta_tags_html}</span>'

    tpl = string.Template(template)
    result = tpl.safe_substitute({
        "escaped_title": escaped_title,
        "escaped_folder": escaped_folder,
        "escaped_text": escaped_text,
        "file_size_hr": escape(size_hr),
        "char_count": f"{size:,}",
        "meta_tags_html": meta_tags_html,
        "back_text": back_text,
        "copy_text": copy_text,
        "copied_text": copied_text,
        "size_text": size_text,
        "chars_text": chars_text,
        "generated_by_text": generated_by_text,
    })
    # Guard against accidental bare $$ in output (from user content that contained $)
    # string.Template uses $$ for literal $, so if user content had $ it's already escaped.
    return result


def build_file_tree_split_html(folder_path: str, parsed_docs: list, include_skipped: bool = True) -> str:
    """Build a collapsible file tree where each file links to its subpage.

    Features:
    - Folders are clickable to collapse/expand their children
    - Toggle icons (▶/▼) show current state
    - "Expand All / Collapse All" buttons at the top
    - Each file links to its subpage in docs/ directory

    Args:
        folder_path: Root folder to scan
        parsed_docs: List of parsed doc dicts with 'title' (rel_path) key
        include_skipped: If True, show scanner-filtered files (e.g. .bin) in tree as skipped.

    Returns:
        HTML string for the collapsible file tree
    """
    from src.constants import FILTER_DIRS as _FILTER_DIRS
    from src.constants import should_filter_file as _should_filter_file

    parsed_paths = {d.get("title", "") for d in parsed_docs}

    def walk(dirpath, prefix=""):
        """Recursively build tree items. Returns list of HTML lines."""
        items = []
        try:
            names = sorted(os.listdir(dirpath), key=str.lower)
        except PermissionError:
            return []

        root_for_rel = folder_path
        for name in names:
            full_path = os.path.join(dirpath, name)
            rel_path = os.path.relpath(full_path, root_for_rel)

            if os.path.isdir(full_path):
                if name in _FILTER_DIRS or name.startswith('.'):
                    continue
                items.append(('dir', name, full_path, rel_path))
            else:
                if _should_filter_file(rel_path):
                    if not include_skipped:
                        continue
                    # include_skipped=True: show filtered files as non-parsed
                items.append(('file', name, full_path, rel_path))

        dirs = [(n, f, r) for t, n, f, r in items if t == 'dir']
        files = [(n, f, r) for t, n, f, r in items if t == 'file']
        all_items = dirs + files

        result = []
        for idx, (name, full_path, rel_path) in enumerate(all_items):
            is_last = (idx == len(all_items) - 1)
            connector = '└──' if is_last else '├──'
            child_prefix = prefix + ('    ' if is_last else '│   ')

            if os.path.isdir(full_path):
                # Build children recursively
                children = walk(full_path, child_prefix)
                children_html = (
                    f'<ul class="folder-children">\n'
                    f'  {chr(10).join(children)}'
                    f'</ul>'
                ) if children else ''

                result.append(
                    f'<li class="tree-folder" onclick="toggleFolder(this)">'
                    f'<span class="tree-prefix">{prefix}{connector}</span>'
                    f'<span class="folder-toggle-icon">▼</span>'
                    f'<span class="tree-folder-name">📁 {name}</span>'
                    f'{children_html}'
                    f'</li>'
                )
            else:
                size = os.path.getsize(full_path)
                size_hr = human_readable_size(size)
                is_parsed = rel_path in parsed_paths

                subpage_name = _path_to_subpage_filename(rel_path)

                if is_parsed:
                    link_html = f'<a href="docs/{subpage_name}" target="_blank" onclick="event.stopPropagation()">📄 {name}</a>'
                else:
                    link_html = f'<span class="unparsed">⏭️ {name}</span>'

                css_class = 'tree-file'
                if not is_parsed:
                    css_class += ' skipped'

                result.append(
                    f'<li class="{css_class}">'
                    f'<span class="tree-prefix">{prefix}{connector}</span>'
                    f'{link_html}'
                    f'<span class="tree-size"> {size_hr}</span>'
                    f'</li>'
                )

        return result

    lines = walk(folder_path)
    return '\n'.join(lines)


def build_search_index_json(docs_texts: list) -> str:
    """Build a lightweight JSON array for client-side search indexing.

    Each entry contains: path, name, tags, preview (first 300 chars).
    The 'text' field is intentionally omitted — the index is embedded in the
    HTML page and would bloat memory with full file contents. For large
    document sets, consider loading the index dynamically from an external
    JSON file instead.

    Args:
        docs_texts: List of doc dicts with keys: title, text, tags

    Returns:
        JSON string for embedding in <script> tag
    """
    import json

    index_data = []
    for doc in docs_texts:
        title = doc.get("title", "")
        text = doc.get("text", "")
        tags = doc.get("tags", []) or []

        # Get just the filename from the path
        name = os.path.basename(title.replace('\\', '/'))

        # Preview: first 2000 chars for better search context and content matching.
        # Also include first 200 chars of raw text as hidden searchable text.
        preview = text[:2000].replace('\n', ' ').strip()

        index_data.append({
            "path": title,
            "name": name,
            "tags": tags[:8],
            "preview": preview,
            # Note: full 'text' field omitted to keep index lightweight,
            # but increased preview provides significantly better search quality.
        })
    return json.dumps(index_data, ensure_ascii=False)


def wrap_skipped_html(
    title: str,
    folder_name: str,
    file_size_hr: str,
    filepath: str,
) -> str:
    """Generate an HTML page for a file that was skipped (unsupported format).

    Args:
        title: Display title / relative path of the skipped file.
        folder_name: Source folder name.
        file_size_hr: Human-readable file size.
        filepath: Full path to the skipped file.

    Returns:
        Complete HTML string for the skipped-file notice page.
    """
    from html import escape

    escaped_title = escape(title)
    escaped_folder = escape(folder_name)
    escaped_filepath = escape(filepath)
    escaped_size = escape(file_size_hr)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escaped_title} — {escaped_folder} (Skipped)</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 900px; margin: 0 auto; padding: 24px 20px;
    background: #f8f9fa; color: #333; line-height: 1.7;
  }}
  .skip-notice {{
    background: #fff3cd; border: 1px solid #ffeeba; border-radius: 8px;
    padding: 24px; text-align: center; margin-bottom: 20px;
  }}
  .skip-notice .icon {{ font-size: 3em; margin-bottom: 12px; }}
  .skip-notice h2 {{ color: #856404; margin-bottom: 8px; }}
  .skip-notice p {{ color: #6c757d; font-size: 0.95em; line-height: 1.6; }}
  .skip-notice .details {{
    margin-top: 12px; font-size: 0.85em; color: #888;
    background: #f8f9fa; border-radius: 6px; padding: 10px 14px;
    text-align: left;
  }}
  .footer {{
    text-align: center; color: #999; font-size: 0.82em;
    margin-top: 24px; padding-top: 16px; border-top: 1px solid #e0e0e0;
  }}
  a {{ color: #1a73e8; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #1a1a2e; color: #e0e0e0; }}
    .skip-notice {{ background: #2a2a1e; border-color: #5a5a3e; }}
    .skip-notice h2 {{ color: #ffc107; }}
    .skip-notice p {{ color: #aaa; }}
    .skip-notice .details {{ background: #1a1a2e; color: #888; }}
    .footer {{ border-top-color: #333; color: #666; }}
  }}
</style>
</head>
<body>
<a href="index.html">⬅ Back to Index</a>

<div class="skip-notice">
  <div class="icon">⏭️</div>
  <h2>Unsupported File Type</h2>
  <p>
    This file format is not supported by FolderKnowledgeSiteGeneratorForAI and has been skipped.<br>
    To parse it, convert to a supported format (.txt, .md, .pdf, .docx, .pptx, .xlsx, etc.).
  </p>
  <div class="details">
    <strong>Path:</strong> {escaped_filepath}<br>
    <strong>Size:</strong> {escaped_size}
  </div>
</div>

<div class="footer">
  <p>Generated by FolderKnowledgeSiteGeneratorForAI | {escaped_folder}</p>
</div>
</body>
</html>"""


def wrap_index_html(
    docs_meta: list,
    folder_name: str,
    folder_path: str,
    total_chars: int,
    generated_at: str,
    file_tree_html: str = "",
    file_contents_html: str = "",
    language: str = "en",
) -> str:
    """Wrap index page with all portal content.

    Note: The 'ai_raw_text_html' parameter has been removed because all
    file content is now always expanded in the DOM. The sr-only block
    is no longer needed.
    """
    escaped_folder = escape(folder_name)
    escaped_path = escape(folder_path)

    # No longer build cards_html — all info is in the file blocks now

    # Keyword cloud from parsed docs only
    all_tags = set()
    for doc in docs_meta:
        for tag in doc.get("tags", []):
            if tag and tag != "Skipped":
                all_tags.add(tag)
    all_tags_sorted = sorted(all_tags)[:40]
    tags_cloud_html = ""
    for tag in all_tags_sorted:
        safe_tag = escape(tag)
        tags_cloud_html += f'<span class="cloud-tag" data-tag="{safe_tag}">{safe_tag}</span> '

    doc_count = sum(1 for d in docs_meta if not d.get("skipped"))
    skipped_count = sum(1 for d in docs_meta if d.get("skipped"))
    total_size_hr = _format_total_size(docs_meta)

    # --- Build AI-friendly meta description for index page ---
    index_meta_desc = (
        f'Knowledge portal for folder "{folder_name}" with {doc_count} documents, '
        f'{total_chars:,} total characters, generated at {generated_at}'
    )
    escaped_index_meta_desc = escape(index_meta_desc)

    # --- Build AI-friendly keywords for index page (top 20 from all docs) ---
    all_index_keywords = set()
    for doc in docs_meta:
        for tag in doc.get("tags", []):
            if tag and tag != "Skipped":
                all_index_keywords.add(tag)
    index_keywords_list = sorted(all_index_keywords)[:20]
    escaped_index_keywords = escape(", ".join(index_keywords_list))

    template = _load_template("index_page.html")
    tpl = string.Template(template)
    result = tpl.safe_substitute({
        "escaped_folder": escaped_folder,
        "language": language,
        "escaped_subtitle": "Knowledge Portal",
        "escaped_path": escaped_path,
        "doc_count": str(doc_count),
        "skipped_count": str(skipped_count),
        "total_chars": f"{total_chars:,}",
        "total_size_hr": total_size_hr,
        "generated_at_escaped": escape(generated_at),
        "tags_cloud_html": tags_cloud_html,
        "cards_html": "",
        "file_tree_html": file_tree_html,
        "file_contents_html": file_contents_html,
        "meta_description_escaped": escaped_index_meta_desc,
        "meta_keywords_escaped": escaped_index_keywords,
    })
    return result