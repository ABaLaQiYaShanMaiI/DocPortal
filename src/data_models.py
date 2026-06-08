"""
FolderKnowledgeSiteGeneratorForAI — Unified Data Models

Centralized TypedDict definitions for all data structures that flow
between modules (scanner -> parser -> generator -> templates).

These replace ad-hoc dict[str, Any] usage throughout the codebase.
"""

from __future__ import annotations

from typing import TypedDict, List, Optional


class ParseResult(TypedDict):
    """Output from any parser (text, PDF, Office).

    Design notes:
    - Uses TypedDict for structural type checking without runtime overhead.
    - 'extract_type' is always 'text' for this project (we extract text from all formats).
    - 'metadata' carries format-specific info (mime, encoding, format).
    """

    extract_type: str
    text: str
    metadata: dict


class FileEntry(TypedDict):
    """A single file's parsed result, used by chunker and build layers.

    Used in: chunker door_init__, portal door_init__, scanner output builders.
    """

    rel_path: str
    text: str
    size: int
    size_hr: str


class PortalDocMeta(TypedDict):
    """Metadata entry for one file in a portal's index/card view.

    This is the "metadata view" — search index, card display, file tree labels.
    Does NOT contain full text content.
    """

    title: str
    file: str
    size: int
    size_hr: str
    preview: str
    tags: List[str]
    skipped: bool
    mtime: str


class PortalDocText(TypedDict):
    """Full text entry for one file in a portal's content blocks.

    This is the "content view" — rendered in file content blocks, subpages, etc.
    """

    title: str
    text: str
    size: int
    file_type: str
    size_hr: str
    tags: List[str]


class PortalBuildResult(TypedDict):
    """Aggregate result from the portal document collection phase.

    This is the shared output of `collect_portal_documents()`, consumed by both
    generate_portal() and generate_portal_split() for their rendering phases.
    """

    docs_meta: List[PortalDocMeta]
    docs_texts: List[PortalDocText]
    parsed_count: int
    skipped_count: int
    error_count: int
    total_chars: int
    folder_name: str
    all_files: List


class ScannedFile(TypedDict):
    """Unified scan result for a single file — produced once, consumed everywhere.

    Replaces the scattered ad-hoc dicts that were built by walk_files,
    collect_files_info, and inline file processing loops.
    """

    rel_path: str
    full_path: str
    size: int
    size_hr: str
    status: str  # FileScanStatus value
    reason: str  # Human-readable reason (empty if PARSED)
    text: str  # Empty if not parsed


class ChunkerResult(TypedDict):
    """Output from the write_chunks() function."""

    chunks_count: int
    total_chars: int
    total_files: int
    output_dir: str
    index_file: Optional[str]


class PortalResult(TypedDict):
    """Output from generate_portal() or generate_portal_split()."""

    doc_count: int
    total_chars: int
    skipped: int
    errors: int
    output_dir: str
    index_file: Optional[str]
    folder_name: str
