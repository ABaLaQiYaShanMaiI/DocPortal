"""FolderKnowledgeSiteGeneratorForAI Portal Generator — Smart knowledge portal generator.

Exports:
    generate_portal(folder_path, output_dir, ...)  — Single-file portal (all content in one page)
    generate_portal_split(folder_path, output_dir, ...)  — Split portal (index + per-file subpages)
"""

from src.generator.portal import generate_portal, generate_portal_split

__all__ = ["generate_portal", "generate_portal_split"]
