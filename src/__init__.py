"""
FolderKnowledgeSiteGeneratorForAI
Lightweight offline document portal: convert folders into AI-readable knowledge portals.

Main entry points:
    - generate_portal(folder_path, output_dir, ...)
    - generate_portal_split(folder_path, output_dir, ...)
    - collect_files_info(root_dir)
    - write_chunks(folder_path, output_dir, ...)
    - parse_file(full_path)
"""

# Core API: Portal generation
from src.generator.portal import generate_portal, generate_portal_split

# Core API: Scanning & file info
from src.scanner import collect_files_info, is_file_supported

# Core API: Chunked output
try:
    from src.chunker import write_chunks, DEFAULT_CHUNK_SIZE
except ImportError:
    pass

# Core API: File parsing
from src.parser.dispatcher import parse_file

# Utilities
from src.utils import human_readable_size

__all__ = [
    'generate_portal',
    'generate_portal_split',
    'collect_files_info',
    'is_file_supported',
    'write_chunks',
    'DEFAULT_CHUNK_SIZE',
    'parse_file',
    'human_readable_size',
]