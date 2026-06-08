"""
FolderKnowledgeSiteGeneratorForAI — Chunked Text Output Module

Instead of generating a single monolithic TXT file (which can overflow LLM context),
splits the output into multiple files, each capped at a configurable character limit.

Key design decisions:
- Uses **character count** as the splitting unit (not bytes), stable across encodings.
- **File-level integrity** (default): never splits a file mid-document.
  When accumulated chars exceed chunk_size, the *next* file goes to a new chunk.
- **Oversized files** (default): A single file larger than chunk_size gets its own dedicated chunk,
  with a warning printed to the user.
- **Force-split mode** (--force-split): Splits oversized files across multiple chunks at chunk_size
  boundaries, so no single chunk exceeds the size limit.
- Output files named `part_001.txt`, `part_002.txt`, ... (sorted sequentially)
- Index HTML named `<folder>_index.html` (manifest that lists files per chunk)
"""

import os
import logging
from html import escape
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any, TypedDict

logger = logging.getLogger(__name__)

# ── Try to import SEPARATOR_LINE ──
try:
    from src.constants import SEPARATOR_LINE
except ImportError:
    SEPARATOR_LINE = "=" * 60  # fallback


class FileEntry(TypedDict):
    """Type for a single file entry in chunking operations."""

    rel_path: str
    text: str
    size_hr: str
    size: int


# ── Default chunk size: 500,000 characters ──
# 500K chars ≈ ~100K tokens for most LLMs (roughly 5 chars/token for code).
# This value was chosen as a practical balance:
# - Large enough to provide meaningful context per chunk (~2-3 average source files)
# - Small enough to fit within GPT-4/Claude 128K context windows with room for
#   the user's message, instructions, and the model's response
# Note: This is the chunker module's own default, distinct from the constants.py
# DEFAULT_CHUNK_SIZE (50K) which is used for portal-mode per-file page generation.
DEFAULT_CHUNK_SIZE = 500_000


class FileChunk:
    """Represents one chunk containing a list of complete file entries."""

    def __init__(self, chunk_index: int, chunk_size: int):
        self.index = chunk_index  # 0-based
        self.chunk_size = chunk_size  # max chars for this chunk
        self.files: List[FileEntry] = []
        self.accumulated_chars: int = 0

    @property
    def is_full(self) -> bool:
        """Return True if adding another file would exceed chunk_size."""
        return self.accumulated_chars >= self.chunk_size

    def can_add(self, text_len: int) -> bool:
        """Check whether adding a file of `text_len` chars fits within chunk_size."""
        return self.accumulated_chars + text_len <= self.chunk_size

    def add_file(self, rel_path: str, text: str, size_hr: str):
        """Add a file entry to this chunk."""
        self.files.append(
            {
                "rel_path": rel_path,
                "text": text,
                "size": len(text),
                "size_hr": size_hr,
            }
        )
        self.accumulated_chars += len(text)

    def get_header(self, folder_name: str) -> str:
        """Generate a header for this chunk's TXT output."""
        sep = SEPARATOR_LINE
        lines = [
            sep,
            f"Folder Knowledge Export — Chunk {self.index + 1}",
            f"Source: {folder_name}",
            f"Files in this chunk: {len(self.files)}",
            f"Characters: {self.accumulated_chars:,}",
            f"Chunk size limit: {self.chunk_size:,} chars",
            sep,
            "",
        ]
        return "\n".join(lines)

    def to_text(self, folder_name: str, include_header: bool = True) -> str:
        """Render this chunk as a plain-text string."""
        parts = []
        if include_header:
            parts.append(self.get_header(folder_name))
        sep = SEPARATOR_LINE
        for f in self.files:
            block = (
                f"{sep}\nFile: {f['rel_path']}\nSize: {f['size_hr']}\nCharacters: {f['size']:,}\n{sep}\n{f['text']}\n\n"
            )
            parts.append(block)
        return "".join(parts)


def _parse_single_file(full_path: str, rel_path: str) -> Optional[str]:
    """Parse a single file and return its text, or None on failure."""
    from src.parser.dispatcher import parse_file as _parse_file

    try:
        result = _parse_file(full_path)
        if result is None:
            return None
        text = (result.get("text") or "").strip()
        if not text:
            return None
        return text
    except Exception as e:
        logger.debug("Failed to parse %s: %s", rel_path, e)
        return None


def _collect_files(folder_path: str, max_chars: Optional[int] = None) -> Tuple[List[FileEntry], int]:
    """Walk folder_path, collect file info, and parse text.

    Args:
        folder_path: Root folder to scan.
        max_chars: Optional global character limit across all files.

    Returns:
        Tuple of (entries list, total_size int):
        entries: list of dicts with keys {rel_path, text, size_hr}, ordered by file path.
    """
    from src.utils import human_readable_size
    from src.scanner import walk_files

    # Collect ALL entries first (without applying max_chars limit)
    # so that sorting happens before truncation.
    raw_entries: List[FileEntry] = []
    total_size = 0

    for full_path, rel_path in walk_files(folder_path):
        text = _parse_single_file(full_path, rel_path)
        if text is None:
            continue
        file_size = os.path.getsize(full_path)
        size_hr = human_readable_size(file_size)
        raw_entries.append(
            {
                "rel_path": rel_path,
                "text": text,
                "size_hr": size_hr,
                "size": len(text),
            }
        )
        total_size += len(text)

    # Sort by relative path BEFORE applying max_chars limit
    raw_entries.sort(key=lambda e: e["rel_path"].lower())

    # Now apply max_chars global limit on sorted entries
    entries: List[FileEntry] = []
    accumulated = 0
    limit_reached = False

    for entry in raw_entries:
        if limit_reached:
            break
        text = entry["text"]
        if max_chars is not None and accumulated + len(text) > max_chars:
            allowed = max_chars - accumulated
            if allowed <= 0:
                break
            # Find nearest newline boundary for cleaner truncation
            truncated = text[:allowed]
            last_newline = truncated.rfind("\n")
            if last_newline > allowed * 0.5:
                truncated = truncated[:last_newline]
            text = truncated
            limit_reached = True

        entries.append(
            {
                "rel_path": entry["rel_path"],
                "text": text,
                "size_hr": entry["size_hr"],
                "size": len(text),
            }
        )
        accumulated += len(text)

    return entries, accumulated


def chunk_files(
    entries: List[FileEntry],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    force_split: bool = False,
) -> List[FileChunk]:
    """Split a sorted list of file entries into chunks for LLM context fitting.

    Design notes:
    - Uses **character count** as the splitting unit (not bytes), stable across encodings.
      Character count is more meaningful for LLMs since models tokenize by characters.
    - **File-level integrity** (default): never splits a file mid-document.
      When accumulated chars exceed chunk_size, the *next* file goes to a new chunk.
    - **Oversized files** (default): A single file larger than chunk_size gets its
      own dedicated chunk, with a warning printed to the user.
    - **Force-split mode** (--force-split): Splits oversized files across multiple
      chunks at chunk_size boundaries, so no single chunk exceeds the size limit.

    Why not just split at chunk_size without file-level integrity?
      - Splitting mid-file would produce fragments that are hard for LLMs to interpret.
      - The index HTML shows which files are in which chunk, and users expect
        complete files, not partial fragments.
      - Force-split is provided as an escape hatch for truly massive files (e.g.,
        10MB+ data exports) that would otherwise create unusable chunks.

    Args:
        entries: List of dicts with keys {rel_path, text, size_hr}, sorted.
        chunk_size: Maximum characters per chunk.
        force_split: If True, split oversized files across multiple chunks
                     instead of placing them in a single dedicated chunk.

    Returns:
        List of FileChunk objects.
    """
    chunks: List[FileChunk] = []
    current_chunk = FileChunk(0, chunk_size)
    oversized_files: List[str] = []

    for entry in entries:
        text_len = len(entry["text"])

        # Case 1: Single file exceeds chunk_size
        if text_len > chunk_size:
            oversized_files.append(entry["rel_path"])

            if force_split:
                # ── Force-split mode: split file across multiple chunks ──
                text = entry["text"]
                total_parts = (text_len + chunk_size - 1) // chunk_size  # ceil division

                for part_idx in range(total_parts):
                    start = part_idx * chunk_size
                    end = min(start + chunk_size, text_len)
                    segment = text[start:end]

                    # Create a modified entry for this segment
                    part_entry = {
                        "rel_path": f"{entry['rel_path']} [part {part_idx + 1}/{total_parts}]",
                        "text": segment,
                        "size_hr": entry["size_hr"],
                    }

                    # Try to add to current chunk if it fits
                    if current_chunk.can_add(len(segment)):
                        current_chunk.add_file(part_entry["rel_path"], part_entry["text"], part_entry["size_hr"])
                    else:
                        # Finalize current chunk and start new one
                        if current_chunk.files:
                            chunks.append(current_chunk)
                        current_chunk = FileChunk(len(chunks), chunk_size)
                        current_chunk.add_file(part_entry["rel_path"], part_entry["text"], part_entry["size_hr"])
            else:
                # ── Default: dedicated chunk for oversized file ──
                # If current chunk has content, finalize it first
                if current_chunk.files:
                    chunks.append(current_chunk)
                # Create a dedicated chunk for this single huge file
                dedicated = FileChunk(len(chunks), chunk_size)
                dedicated.add_file(entry["rel_path"], entry["text"], entry["size_hr"])
                chunks.append(dedicated)
                # Start a new empty chunk
                current_chunk = FileChunk(len(chunks), chunk_size)

            continue

        # Case 2: File fits in current chunk
        if current_chunk.can_add(text_len):
            current_chunk.add_file(entry["rel_path"], entry["text"], entry["size_hr"])
        else:
            # Finalize current chunk and start a new one
            chunks.append(current_chunk)
            current_chunk = FileChunk(len(chunks), chunk_size)
            current_chunk.add_file(entry["rel_path"], entry["text"], entry["size_hr"])

    # Don't forget the last chunk if it has content
    if current_chunk.files:
        chunks.append(current_chunk)

    # Log warnings for oversized files
    if oversized_files:
        if force_split:
            logger.warning(
                "🔪 %d file(s) exceed chunk size (%s chars) — auto-split across multiple chunks:",
                len(oversized_files),
                f"{chunk_size:,}",
            )
        else:
            logger.warning("⚠️  %d file(s) exceed chunk size (%s chars):", len(oversized_files), f"{chunk_size:,}")
        for f in oversized_files:
            logger.warning("     - %s", f)
        if not force_split:
            logger.warning(
                "     These files are placed in their own dedicated chunk(s). "
                "Use --force-split to split them across multiple chunks."
            )

    # Re-index chunks after potential insertions
    for i, chunk in enumerate(chunks):
        chunk.index = i

    return chunks


def generate_index_html(
    folder_name: str,
    chunk_size: int,
    chunks: List[FileChunk],
    output_dir: str,
) -> str:
    """Generate an index HTML file listing all chunks and their contents.

    Args:
        folder_name: Source folder display name.
        chunk_size: Character limit per chunk.
        chunks: List of FileChunk objects.
        output_dir: Absolute path to output directory.

    Returns:
        HTML string.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_chars = sum(c.accumulated_chars for c in chunks)
    total_files = sum(len(c.files) for c in chunks)

    # Build chunk table rows
    chunk_rows: List[str] = []
    for chunk in chunks:
        file_list_items: List[str] = []
        for f in chunk.files:
            file_list_items.append(
                f'            <li class="file-entry">{escape(f["rel_path"])} '
                f'<span class="file-size">({f["size_hr"]}, {f["size"]:,} chars)</span></li>'
            )
        file_list_html = (
            "\n".join(file_list_items) if file_list_items else '            <li class="empty">(empty chunk)</li>'
        )

        chunk_rows.append(f"""
        <div class="chunk-card">
            <div class="chunk-header" onclick="toggleChunk(this)">
                <span class="chunk-number">Chunk {chunk.index + 1:03d}</span>
                <span class="chunk-stats">{len(chunk.files)} files · {chunk.accumulated_chars:,} chars</span>
                <span class="toggle-icon">▶</span>
            </div>
            <div class="chunk-body" style="display:none;">
                <p class="chunk-file-label">Files in this chunk:</p>
                <ul class="chunk-file-list">
{file_list_html}
                </ul>
                <p class="chunk-filename">
                    📄 <a href="part_{chunk.index + 1:03d}.txt" style="color:#1a73e8;text-decoration:none;" target="_blank"><code>part_{chunk.index + 1:03d}.txt</code></a> <span style="font-size:0.8em;color:#888;">(click to open)</span>
                </p>
            </div>
        </div>""")

    chunk_rows_html = "\n".join(chunk_rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Knowledge Export Index — {escape(folder_name)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 960px; margin: 0 auto; padding: 20px;
    background: #f8f9fa; color: #333;
  }}
  h1 {{ font-size: 1.5em; color: #1a73e8; margin-bottom: 4px; }}
  .subtitle {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
  .stats-bar {{
    background: #fff; border-radius: 10px; padding: 16px 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 20px;
    font-size: 0.95em; line-height: 1.8;
  }}
  .stats-bar .stat {{ display: inline-block; margin-right: 24px; }}
  .stats-bar .stat-label {{ color: #888; }}
  .stats-bar .stat-value {{ font-weight: 600; color: #1a73e8; }}

  h2 {{ font-size: 1.15em; color: #333; margin-bottom: 12px; }}

  .chunk-card {{
    background: #fff; border: 1px solid #e0e0e0; border-radius: 8px;
    margin-bottom: 8px; overflow: hidden;
  }}
  .chunk-header {{
    display: flex; align-items: center; gap: 12px;
    padding: 12px 16px; cursor: pointer;
    transition: background 0.15s; user-select: none;
  }}
  .chunk-header:hover {{ background: #f0f4ff; }}
  .chunk-number {{
    font-weight: 600; color: #1a73e8; font-size: 0.95em;
  }}
  .chunk-stats {{ color: #888; font-size: 0.85em; flex: 1; }}
  .toggle-icon {{ color: #888; font-size: 0.8em; transition: transform 0.2s; }}
  .chunk-header.expanded .toggle-icon {{ transform: rotate(90deg); }}
  .chunk-body {{
    padding: 0 16px 12px 16px; border-top: 1px solid #eee;
  }}
  .chunk-file-label {{ font-size: 0.85em; color: #666; margin-bottom: 6px; }}
  .chunk-file-list {{
    list-style: none; padding: 0; margin-bottom: 8px;
    max-height: 300px; overflow-y: auto;
  }}
  .file-entry {{
    font-size: 0.88em; padding: 3px 0; color: #444;
    border-bottom: 1px solid #f0f0f0;
  }}
  .file-entry:last-child {{ border-bottom: none; }}
  .file-size {{ color: #999; font-size: 0.85em; }}
  .chunk-filename {{ font-size: 0.85em; color: #666; }}
  .chunk-filename code {{
    background: #f0f0f0; padding: 2px 6px; border-radius: 4px;
    font-size: 0.95em;
  }}
  .empty {{ color: #ccc; font-style: italic; }}

  .usage-box {{
    background: #e8f5e9; border: 1px solid #c8e6c9; border-radius: 8px;
    padding: 14px 18px; margin-top: 20px; font-size: 0.9em; line-height: 1.7;
  }}
  .usage-box strong {{ color: #2e7d32; }}

  .footer {{
    text-align: center; color: #aaa; font-size: 0.82em;
    padding: 24px 0 12px 0;
  }}
</style>
</head>
<body>
<h1>📁 {escape(folder_name)}</h1>
<p class="subtitle">Folder Knowledge Export — Chunked Output Index</p>

<div class="stats-bar">
  <div class="stat">
    <span class="stat-label">Total chunks: </span>
    <span class="stat-value">{len(chunks)}</span>
  </div>
  <div class="stat">
    <span class="stat-label">Files: </span>
    <span class="stat-value">{total_files}</span>
  </div>
  <div class="stat">
    <span class="stat-label">Total chars: </span>
    <span class="stat-value">{total_chars:,}</span>
  </div>
  <div class="stat">
    <span class="stat-label">Chunk size: </span>
    <span class="stat-value">{chunk_size:,}</span>
  </div>
  <div class="stat">
    <span class="stat-label">Generated: </span>
    <span class="stat-value">{now}</span>
  </div>
</div>

<h2>📄 Chunks</h2>
<p style="font-size: 0.88em; color: #666; margin-bottom: 12px;">
  Click on a chunk to see which files it contains. Submit each <code>part_*.txt</code> file to your AI in order.
</p>

{chunk_rows_html}

<div class="usage-box">
<strong>📋 Usage Instructions:</strong><br>
1. Open each <code>part_*.txt</code> file and copy its contents.<br>
2. Submit them to your AI <strong>in order</strong> (Chunk 1 → Chunk 2 → ...).<br>
3. Each chunk contains approximately {chunk_size:,} characters of content.<br>
4. Files are never split mid-document — each chunk ends at a file boundary.<br>
5. If any file exceeds the chunk size, it gets its own dedicated chunk (flagged above).
</div>

<div class="footer">
  Generated by FolderKnowledgeSiteGeneratorForAI | {now}
</div>

<script>
function toggleChunk(header) {{
    header.classList.toggle('expanded');
    var body = header.nextElementSibling;
    if (body.style.display === 'none') {{
        body.style.display = 'block';
        header.querySelector('.toggle-icon').textContent = '▼';
    }} else {{
        body.style.display = 'none';
        header.querySelector('.toggle-icon').textContent = '▶';
    }}
}}
</script>
</body>
</html>"""
    return html


def write_chunks(
    folder_path: str,
    output_dir: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_chars: Optional[int] = None,
    force_split: bool = False,
) -> Dict[str, Any]:
    """Main entry point: scan, chunk, and write output files.

    Args:
        folder_path: Source folder to scan.
        output_dir: Output directory (will be created if not exists).
        chunk_size: Maximum characters per chunk.
        max_chars: Optional global character limit across all chunks.
        force_split: If True, split oversized files across multiple chunks.

    Returns:
        Dict with the following keys:
            - chunks_count (int): Number of chunk files generated (0 if no parseable files).
            - total_chars (int): Total characters across all chunks.
            - total_files (int): Total number of files parsed.
            - output_dir (str): Absolute path to the output directory.
            - index_file (str | None): Path to the generated index HTML file, or None if no chunks.
    """
    folder_name = os.path.basename(os.path.abspath(folder_path))
    os.makedirs(output_dir, exist_ok=True)

    # 1. Collect and parse all files
    logger.info("  [Scan] Parsing files...")
    entries, total_size = _collect_files(folder_path, max_chars=max_chars)

    if not entries:
        logger.warning("  ⚠️  No parseable files found.")
        return {
            "chunks_count": 0,
            "total_chars": 0,
            "total_files": 0,
            "output_dir": output_dir,
            "index_file": None,
        }

    logger.info("  [Scan] %d files parsed, %s total chars.", len(entries), f"{total_size:,}")

    # 2. Chunk the files
    mode_hint = "force-split" if force_split else "file-level integrity"
    logger.info("  [Chunk] Splitting into chunks of max %s chars each (%s)...", f"{chunk_size:,}", mode_hint)
    chunks = chunk_files(entries, chunk_size=chunk_size, force_split=force_split)
    logger.info("  [Chunk] Created %d chunk(s).", len(chunks))

    # 3. Write TXT files
    for chunk in chunks:
        part_name = f"part_{chunk.index + 1:03d}.txt"
        part_path = os.path.join(output_dir, part_name)
        text_content = chunk.to_text(folder_name)
        with open(part_path, "w", encoding="utf-8") as f:
            f.write(text_content)
        logger.info("Wrote %s (%d chars, %d files)", part_name, chunk.accumulated_chars, len(chunk.files))

    # 4. Write index HTML
    index_html = generate_index_html(
        folder_name=folder_name,
        chunk_size=chunk_size,
        chunks=chunks,
        output_dir=os.path.abspath(output_dir),
    )
    index_path = os.path.join(output_dir, f"{folder_name}_index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)

    # 5. Write a simple manifest text file
    manifest_path = os.path.join(output_dir, "_manifest.txt")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(f"Folder: {folder_name}\n")
        f.write(f"Total chunks: {len(chunks)}\n")
        f.write(f"Total files: {len(entries)}\n")
        f.write(f"Total chars: {total_size:,}\n")
        f.write(f"Chunk size: {chunk_size:,} chars\n")
        f.write(f"Force split: {force_split}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(SEPARATOR_LINE + "\n\n")
        for chunk in chunks:
            f.write(f"Chunk {chunk.index + 1:03d} (part_{chunk.index + 1:03d}.txt):\n")
            f.write(f"  Files: {len(chunk.files)}, Chars: {chunk.accumulated_chars:,}\n")
            for fe in chunk.files:
                f.write(f"    - {fe['rel_path']} ({fe['size_hr']}, {fe['size']:,} chars)\n")
            f.write("\n")

    logger.info("  ✅  Generated %d chunk file(s) in:", len(chunks))
    logger.info("      %s", os.path.abspath(output_dir))
    logger.info("")
    logger.info("      📄 Index:  %s", index_path)
    logger.info("      📄 Manifest: %s", manifest_path)
    logger.info("")
    for chunk in chunks:
        logger.info(
            "         %3d. part_%03d.txt  (%s chars, %d files)",
            chunk.index + 1,
            chunk.index + 1,
            f"{chunk.accumulated_chars:,}",
            len(chunk.files),
        )
    logger.info("")
    logger.info("  📋  Usage: Submit each part_*.txt to your AI in order.")

    return {
        "chunks_count": len(chunks),
        "total_chars": total_size,
        "total_files": len(entries),
        "output_dir": output_dir,
        "index_file": index_path,
    }
