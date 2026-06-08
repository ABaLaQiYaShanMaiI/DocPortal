"""
FolderKnowledgeSiteGeneratorForAI — Shared Utility Functions
"""


def human_readable_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format.

    Supports units from B through PB.
    Does not modify the original value.
    """
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(abs(size_bytes))
    unit_index = 0
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    unit = units[unit_index]
    if unit_index == 0:
        return f"{size:.0f} B" if size == int(size) else f"{size:.1f} B"
    return f"{size:.1f} {unit}"
