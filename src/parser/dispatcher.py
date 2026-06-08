"""
File parsing dispatcher.

Routes files to the appropriate parser (text, PDF, Office) based on
MIME type detection, with extension-based fallback.
"""

import os
import logging
from typing import Optional, Dict, Any

from .text_parser import parse_text
from .pdf_parser import parse_pdf
from .office_parser import parse_office

logger = logging.getLogger(__name__)

# ── python-magic initialization ──
# We catch specific exceptions because magic can raise:
#   - ImportError: not installed
#   - AttributeError: version mismatch (e.g., python-magic d0.4.24 lacks Magic)
#   - OSError/FileNotFoundError: shared library (libmagic) not found on system
#   - Various low-level errors: ctypes.CDLL error on Windows (bundled magic1.dll missing/corrupt)
try:
    import magic
    _magic = magic.Magic(mime=True)  # type: ignore[assignment]
    _magic_available = True
except (ImportError, AttributeError, OSError):
    magic = None  # type: ignore[assignment]
    _magic = None
    _magic_available = False
    logger.debug(
        "python-magic not available (or failed to load). "
        "Falling back to extension-based dispatch."
    )
except Exception:
    # Truly unexpected errors (e.g., ctypes corruption)
    magic = None  # type: ignore[assignment]
    _magic = None
    _magic_available = False
    logger.debug(
        "python-magic unavailable due to unexpected error. "
        "Falling back to extension-based dispatch.",
        exc_info=True,
    )

# ── Import centralized constants (with graceful fallback) ──
try:
    from src.constants import (
        SUPPORTED_TEXT_EXTS,
        KNOWN_BINARY_EXTS,
        OFFICE_MIME_SET,
        OFFICE_EXT_MAP,
        OFFICE_EXT_SET,
        TEXT_MIME_PREFIXES,
        TEXT_DETECTION_PRINTABLE_RATIO,
        TEXT_DETECTION_SAMPLE_BYTES,
    )
    _FALLBACK_TEXT_EXTS: frozenset = SUPPORTED_TEXT_EXTS
    _KNOWN_BINARY_EXTS: frozenset = KNOWN_BINARY_EXTS
    _OFFICE_MIME_SET: frozenset = OFFICE_MIME_SET
    _OFFICE_EXT_MAP: dict = OFFICE_EXT_MAP
    _OFFICE_EXT_SET: frozenset = OFFICE_EXT_SET
    _TEXT_MIME_PREFIXES: frozenset = TEXT_MIME_PREFIXES
    _PRINTABLE_RATIO_THRESHOLD: float = TEXT_DETECTION_PRINTABLE_RATIO
    _SAMPLE_BYTES: int = TEXT_DETECTION_SAMPLE_BYTES
except ImportError:
    # Standalone fallback
    _FALLBACK_TEXT_EXTS = frozenset({
        '.txt', '.md', '.py', '.js', '.ts', '.html', '.css', '.json',
        '.xml', '.csv', '.yaml', '.yml', '.log', '.ini', '.cfg', '.conf',
        '.cs', '.java', '.cpp', '.h',
    })
    _KNOWN_BINARY_EXTS = frozenset({
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
    _OFFICE_MIME_SET = frozenset({
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
    })
    _OFFICE_EXT_MAP = {
        '.doc': 'doc', '.ppt': 'ppt', '.xls': 'xls',
        '.wps': 'wps', '.et': 'et', '.dps': 'dps',
        '.docx': 'docx', '.pptx': 'pptx', '.xlsx': 'xlsx',
    }
    _OFFICE_EXT_SET = frozenset(_OFFICE_EXT_MAP.keys())
    _TEXT_MIME_PREFIXES = frozenset({'text/'})
    _PRINTABLE_RATIO_THRESHOLD = 0.9
    _SAMPLE_BYTES = 8192


# ── MIME to filetype mapping ──
# Maps Office MIME types to their corresponding filetype strings for parse_office().
_MIME_TO_FILETYPE: Dict[str, str] = {
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/msword': 'doc',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
    'application/vnd.ms-powerpoint': 'ppt',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'application/vnd.ms-excel': 'xls',
}

# Configuration for Office parser behavior
# These defaults can be overridden via environment variables or direct import.
OFFICE_INCLUDE_TABLES = os.environ.get('OFFICE_INCLUDE_TABLES', '0') == '1'
OFFICE_INCLUDE_HEADERS_FOOTERS = os.environ.get('OFFICE_INCLUDE_HEADERS_FOOTERS', '0') == '1'
OFFICE_INCLUDE_FOOTNOTES = os.environ.get('OFFICE_INCLUDE_FOOTNOTES', '0') == '1'
OFFICE_ANNOTATE_STYLES = os.environ.get('OFFICE_ANNOTATE_STYLES', '1') == '1'
OFFICE_EXTRACT_PPT_NOTES = os.environ.get('OFFICE_EXTRACT_PPT_NOTES', '0') == '1'
OFFICE_MAX_ROWS_XLSX = int(os.environ.get('OFFICE_MAX_ROWS_XLSX', '10000'))


def _should_try_text_fallback(filepath: str) -> bool:
    """Determine if a file should be attempted as text when MIME type is unknown.

    Strategy (in priority order):
    1. **Known binary extensions** (.exe, .jpg, .pkl, etc.) → **False**
       These are guaranteed binary formats; no point trying text parse.
    2. **Known text extensions** (.py, .txt, .cs, etc.) → **True**
       These are always text; we can parse them directly.
    3. **Unknown extensions** → Read a sample and analyze:
       a. Attempt UTF-8 decode. If successful → **True** (most modern text is UTF-8).
       b. Fall back to Latin-1 (all byte values are valid). Count printable characters.
          If >90% of bytes are printable (including \n, \r, \t) → **True**.
          The 90% threshold was chosen because:
          - Genuine text files typically have >95% printable characters.
          - Latin-1 text with extended chars (accented) may dip to ~92%.
          - Binary files typically have <50% printable characters.
          - 90% provides a safety margin that minimizes false positives
            (binary files misidentified as text) while avoiding false negatives
            (text files that go unparsed).

    Args:
        filepath: Absolute path to the file.

    Returns:
        True if the file should be attempted as text, False otherwise.
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext in _KNOWN_BINARY_EXTS:
        return False
    if ext in _FALLBACK_TEXT_EXTS:
        return True
    # For unknown extensions, read a small sample to determine if it's text.
    try:
        with open(filepath, 'rb') as f:
            sample = f.read(_SAMPLE_BYTES)
        # First try UTF-8 — most modern text files will succeed here.
        try:
            sample.decode('utf-8')
            return True
        except UnicodeDecodeError:
            # UTF-8 failed. Try Latin-1 which decodes any byte sequence.
            # Then count printable characters to distinguish text from binary.
            decoded = sample.decode('latin-1')
            # Count characters that are printable (letters, digits, punctuation)
            # plus common whitespace controls (newline, carriage return, tab).
            printable = sum(1 for c in decoded if c.isprintable() or c in '\n\r\t')
            if len(sample) > 0 and printable / len(sample) > _PRINTABLE_RATIO_THRESHOLD:
                return True
    except (OSError, IOError) as e:
        logger.debug("Cannot read sample from %s: %s", filepath, e)
    except Exception as e:
        logger.debug("Unexpected error reading sample from %s: %s", filepath, e)
    return False


def _get_office_filetype_from_mime(mime: str) -> Optional[str]:
    """Map an Office MIME type to filetype string for parse_office().

    Args:
        mime: MIME type string (e.g., 'application/msword').

    Returns:
        Filetype string (e.g., 'doc') or None if not an Office MIME.
    """
    return _MIME_TO_FILETYPE.get(mime)


def parse_file(filepath: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
    """Dispatch a file to the appropriate parser based on MIME type.

    Detection strategy:
    1. Check extension against known binary list → skip immediately.
    2. Try MIME detection via python-magic (if available).
    3. Route based on MIME type:
       - text/* → parse_text()
       - application/pdf → parse_pdf()
       - Office MIME types → parse_office() with appropriate filetype
    4. If MIME detection unavailable or returned unknown type:
       - Check extension-based Office mapping
       - Try text fallback heuristic for code/text extensions
    5. Return None if no parser could handle the file.

    Args:
        filepath: Absolute path to the file to parse.
        **kwargs: Additional arguments passed to parse_office() when applicable.
            - include_tables: bool (default from OFFICE_INCLUDE_TABLES env var)
            - include_headers_footers: bool
            - include_footnotes: bool
            - annotate_styles: bool
            - extract_ppt_notes: bool
            - max_rows_xlsx: int

    Returns:
        Dict with keys {extract_type, text, metadata}, or None if file
        cannot be parsed.
    """
    if not os.path.isfile(filepath):
        return None

    ext = os.path.splitext(filepath)[1].lower()

    # Skip known binary files early
    if ext in _KNOWN_BINARY_EXTS:
        logger.debug("Skipping known binary file: %s", filepath)
        return None

    # Try MIME-based dispatch (gracefully handle missing or broken python-magic).
    mime: Optional[str] = None
    if _magic is not None:
        try:
            mime = _magic.from_file(filepath)
        except (OSError, IOError) as e:
            mime = None
            logger.debug("magic.from_file() I/O error for %s: %s, falling back to extension", filepath, e)
        except Exception as e:
            mime = None
            logger.debug("magic.from_file() failed for %s: %s, falling back to extension", filepath, e)

    # Collect office parser arguments from kwargs + env defaults
    office_kwargs: Dict[str, Any] = {
        'include_tables': kwargs.get('include_tables', OFFICE_INCLUDE_TABLES),
        'include_headers_footers': kwargs.get('include_headers_footers', OFFICE_INCLUDE_HEADERS_FOOTERS),
        'include_footnotes': kwargs.get('include_footnotes', OFFICE_INCLUDE_FOOTNOTES),
        'annotate_styles': kwargs.get('annotate_styles', OFFICE_ANNOTATE_STYLES),
        'extract_ppt_notes': kwargs.get('extract_ppt_notes', OFFICE_EXTRACT_PPT_NOTES),
        'max_rows_xlsx': kwargs.get('max_rows_xlsx', OFFICE_MAX_ROWS_XLSX),
    }

    # MIME-based dispatch
    if mime:
        if mime.startswith(tuple(_TEXT_MIME_PREFIXES)):
            return parse_text(filepath, mime)
        elif mime == "application/pdf":
            return parse_pdf(filepath)
        elif mime in _OFFICE_MIME_SET:
            filetype = _get_office_filetype_from_mime(mime)
            if filetype:
                return parse_office(filepath, filetype, **office_kwargs)

    # Extension-based dispatch for formats python-magic may not identify.
    # This handles legacy formats (.doc, .ppt, .xls) when magic is unavailable,
    # WPS-specific formats (.wps, .et, .dps),
    # and modern Office formats (.docx, .pptx, .xlsx) as a fallback
    # when python-magic is not available or returns non-standard MIME types.
    if ext in _OFFICE_EXT_SET:
        ft = _OFFICE_EXT_MAP.get(ext, ext.lstrip('.'))
        logger.debug("Extension-based Office/WPS dispatch for %s (type=%s)", filepath, ft)
        return parse_office(filepath, ft, **office_kwargs)

    # Extension-based fallback: try to parse as text for known code/text extensions.
    # This handles .cs, .swift, .kt, csproj, sln, xaml, and other code files
    # where magic might return unexpected MIME types (e.g., application/octet-stream)
    # or simply crash (MagicException for .cs on some Windows setups).
    if _should_try_text_fallback(filepath):
        logger.debug("Trying text fallback for %s (mime=%s, ext=%s)", filepath, mime, ext)
        try:
            result = parse_text(filepath, mime)
            if result and result.get("text", "").strip():
                return result
        except (OSError, IOError) as e:
            logger.debug("Text fallback I/O error for %s: %s", filepath, e)
        except UnicodeDecodeError as e:
            logger.debug("Text fallback encoding error for %s: %s", filepath, e)
        except Exception as e:
            logger.debug("Text fallback unexpected error for %s: %s", filepath, e)

    return None