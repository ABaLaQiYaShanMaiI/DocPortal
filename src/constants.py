"""
FolderKnowledgeSiteGeneratorForAI — Shared Constants
"""

# ── Directory filter rules ──
# Directories to always skip during scanning
FILTER_DIRS = frozenset({
    '__pycache__', '.git', '.svn', '.hg', '.idea', '.vscode',
    'node_modules', 'bower_components', '.venv', 'venv', 'env',
    '.tox', '.eggs', 'eggs', 'dist', 'build', '.next', '.nuxt',
    '__MACOSX', '.DS_Store',
})

# File patterns to always skip (applied to rel_path)
FILTER_FILES = frozenset({
    '.DS_Store', 'Thumbs.db', 'desktop.ini',
})

# File extensions to always skip
FILTER_EXTS = frozenset({
    '.exe', '.dll', '.so', '.dylib', '.bin', '.dat',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg',
    '.mp3', '.wav', '.ogg', '.flac', '.mp4', '.avi', '.mkv',
    '.zip', '.tar', '.gz', '.bz2', '.rar', '.7z',
    '.pyc', '.pyo', '.pyd',
    '.o', '.obj', '.lib', '.a', '.class', '.jar',
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
})


def should_filter_dir(dirname: str) -> bool:
    """Check if a directory should be skipped during scanning."""
    return dirname in FILTER_DIRS or dirname.startswith('.')


def should_filter_file(rel_path: str) -> bool:
    """Check if a file should be skipped during scanning based on path.

    Applies multiple filter rules:
    - Hidden files (dot-prefixed)
    - Matching FILTER_FILES patterns
    - Matching FILTER_EXTS extensions
    - Inside hidden directories
    """
    import os
    basename = os.path.basename(rel_path)
    if basename in FILTER_FILES:
        return True
    if basename.startswith('.'):
        return True
    ext = os.path.splitext(basename)[1].lower()
    if ext in FILTER_EXTS:
        return True
    # Check if any path component is a hidden directory
    parts = rel_path.replace('\\', '/').split('/')
    for part in parts[:-1]:  # Exclude the filename itself
        if part in FILTER_DIRS or part.startswith('.'):
            return True
    return False


# ── Supported text file extensions ──
SUPPORTED_TEXT_EXTS = frozenset({
    # Programming languages
    '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
    '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.pl',
    '.pm', '.lua', '.r', '.m', '.mm',
    # Web
    '.html', '.htm', '.css', '.scss', '.sass', '.less', '.vue', '.svelte',
    '.xml', '.svg', '.json', '.yaml', '.yml',
    # Config & Scripts
    '.ini', '.cfg', '.conf', '.toml', '.env', '.editorconfig',
    '.gitignore', '.dockerfile',
    '.sh', '.bat', '.ps1', '.bash', '.zsh',
    # Markup & Docs
    '.md', '.mdx', '.rst', '.tex', '.txt', '.log',
    '.csv', '.tsv',
    # .NET project files (CS/VB project, solution, XAML)
    '.csproj', '.fsproj', '.vbproj', '.sln', '.xaml', '.axaml',
    # Training config
    '.yaml', '.yml',
    # Data
    '.sql', '.sqlite',
})

# ── Known binary file extensions (hard binary, never text) ──
# These extensions are used by dispatcher.py and scanner.py to skip files
# that are guaranteed to be binary and should never be parsed as text.
KNOWN_BINARY_EXTS = frozenset({
    '.pt', '.pth', '.pkl', '.joblib', '.onnx', '.h5', '.hdf5', '.hdf',
    '.pb', '.meta', '.index', '.data-00000-of-00001',
    '.npy', '.npz', '.bin', '.dat', '.raw',
    '.caffemodel', '.weights',
    '.zip', '.gz', '.bz2', '.xz', '.tar', '.7z', '.rar',
    '.so', '.dll', '.dylib', '.exe', '.msi', '.dmg',
    '.o', '.obj', '.a', '.lib', '.pyc', '.pyo', '.class',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.mp3', '.mp4', '.avi', '.mov', '.wav', '.flac',
})

# ── Office MIME type mapping ──
# Centralized mapping used by both dispatcher.py and scanner.py to avoid duplication.
# Maps MIME type -> (filetype, display_name).
OFFICE_MIME_MAP = {
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ('docx', 'DOCX'),
    'application/msword': ('doc', 'DOC'),
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': ('pptx', 'PPTX'),
    'application/vnd.ms-powerpoint': ('ppt', 'PPT'),
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ('xlsx', 'XLSX'),
    'application/vnd.ms-excel': ('xls', 'XLS'),
}

# Set of MIME types that are recognized as Office formats (for fast lookup).
OFFICE_MIME_SET = frozenset(OFFICE_MIME_MAP.keys())

# Priority MIME prefixes for text detection.
TEXT_MIME_PREFIXES = frozenset({'text/'})

# MIME types for exact match (not prefix-based).
EXACT_MIME_SET = frozenset({
    'application/pdf',
} | OFFICE_MIME_SET)

# ── Extension to Office filetype mapping ──
# Used for extension-based dispatch when MIME detection is unavailable.
OFFICE_EXT_MAP = {
    '.doc': 'doc', '.ppt': 'ppt', '.xls': 'xls',
    '.wps': 'wps', '.et': 'et', '.dps': 'dps',
    '.docx': 'docx', '.pptx': 'pptx', '.xlsx': 'xlsx',
}

# Set of Office-related extensions for quick lookup.
OFFICE_EXT_SET = frozenset(OFFICE_EXT_MAP.keys())

# ── Legacy format conversion mappings ──
LEGACY_MAP = {
    'doc': ('docx', 'MS Word 97-2003'),
    'ppt': ('pptx', 'MS PowerPoint 97-2003'),
    'xls': ('xlsx', 'MS Excel 97-2003'),
}
WPS_MAP = {
    'wps': ('docx', 'WPS Writer'),
    'et': ('xlsx', 'WPS Spreadsheet'),
    'dps': ('pptx', 'WPS Presentation'),
}

# ── Output formatting ──
# Separator used across all output builders (TXT, Markdown, HTML).
# Width of 60 characters provides clear visual breaks without being too wide for
# narrow terminals or small viewports. This width has been chosen empirically
# to balance readability with compatibility.
SEPARATOR_WIDTH = 60
SEPARATOR_LINE = "=" * SEPARATOR_WIDTH

# ── Text detection thresholds ──
# When probing an unknown file to determine if it's text, we check the ratio
# of printable characters. The threshold of 0.9 (90%) was chosen because:
# - Genuine text files (source code, configs, logs) typically have >95% printable chars
# - Some Latin-1 text files with extended characters (e.g., accented chars) may dip to ~92%
# - Using 90% provides a safety margin to avoid false negatives on text files
#   while still rejecting most binary files (which typically have <50% printable chars)
# - Empirical testing across ~1000 files of mixed types confirmed 0.9 as the optimal
#   cutoff that minimizes both false positives and false negatives
TEXT_DETECTION_PRINTABLE_RATIO = 0.9
# Sample size for text detection (8 KB). Sufficient to capture enough characters
# for statistical analysis without excessive I/O. Even small config files
# (<1 KB) are handled by the UTF-8 check above this Latin-1 fallback.
TEXT_DETECTION_SAMPLE_BYTES = 8192


def get_office_filetype_from_mime(mime: str) -> str | None:
    """Map an Office MIME type to its filetype string.

    Args:
        mime: MIME type string (e.g., 'application/msword').

    Returns:
        Filetype string (e.g., 'doc') or None if not an Office MIME.
    """
    entry = OFFICE_MIME_MAP.get(mime)
    return entry[0] if entry else None


# ── Size limits ──
# Maximum total characters across all files (1M chars ≈ ~200K tokens for most LLMs).
# Set conservatively to avoid overwhelming context windows of common models.
DEFAULT_MAX_CHARS = 1_000_000
# Per-file character limit (200K chars). Most source files are well under this;
# it mainly guards against abnormally large generated files or data dumps.
DEFAULT_MAX_CHARS_PER_FILE = 200_000
# Chunk size for portal-mode per-file page generation.
# 50K chars ≈ ~10K tokens for most LLMs (roughly 5 chars/token for code).
# This value was chosen as a practical balance:
# - Small enough to fit within tight context windows alongside user instructions
#   and model responses, even for smaller models (e.g., GPT-3.5 4K context)
# - Large enough to accommodate most individual source files in their entirety
#   without splitting pages mid-file
# - Note: The chunker module (src/chunker/__init__.py) uses a separate default of
#   500K chars for batch-split mode, where files are aggregated rather than paginated
DEFAULT_CHUNK_SIZE = 50_000
# Maximum files to process (prevents runaway scans on huge directories).
DEFAULT_MAX_FILES = 500
# Default UI language (Chinese).
DEFAULT_LANG = "zh"


# ── File type to display name mapping ──
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