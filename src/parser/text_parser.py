"""
Text file parser with multi-encoding detection and fallback.

Supports UTF-8, GBK, Latin-1, and chardet-based auto-detection for
text files with unknown or non-standard encoding.
"""

import os
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ── Encoding detection constants ──
# Sample size for chardet encoding detection.
# 64 KB is the chardet recommended minimum for reliable detection;
# it provides enough context for statistical analysis of byte patterns.
_DEFAULT_DETECT_SAMPLE = 65536  # 64 KB
# Minimum sample size for chardet. Files smaller than this may not be
# reliably detectable by chardet (not enough statistical signal).
# For files below this size, we skip chardet and go directly to
# ordered fallback encoding attempts.
_MIN_DETECT_SAMPLE = 8192  # 8 KB
# Confidence threshold for chardet results. Values below 0.5 indicate
# the detection is likely unreliable. We use 0.5 as a conservative
# cutoff to avoid acting on low-confidence guesses.
_CHARDET_CONFIDENCE_THRESHOLD = 0.5

# Try to use chardet for more accurate encoding detection
try:
    import chardet

    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False
    chardet = None  # type: ignore[assignment]


def _detect_encoding(filepath: str) -> Optional[str]:
    """Detect file encoding using chardet with adaptive sampling.

    For files >= 8KB, reads the first 64KB for chardet analysis.
    For files < 8KB, skips chardet (insufficient sample) and returns None
    to fall through to ordered encoding attempts.

    This adaptive approach avoids unnecessary chardet overhead on small
    files where the detection would be unreliable anyway.

    Args:
        filepath: Absolute path to the file.

    Returns:
        Detected encoding name (e.g., 'utf-8', 'gbk'), or None if
        detection is inconclusive or chardet is unavailable.
    """
    if not HAS_CHARDET:
        return None

    try:
        # Get file size to determine optimal sample size.
        file_size = os.path.getsize(filepath)
    except OSError:
        file_size = 0

    # For files smaller than the minimum sample, chardet is unlikely
    # to produce reliable results. Skip to ordered fallback.
    if 0 < file_size < _MIN_DETECT_SAMPLE:
        logger.debug("File %s too small (%d bytes) for chardet, using ordered fallback", filepath, file_size)
        return None

    # Read a sample for chardet analysis.
    # Use min(file_size, _DEFAULT_DETECT_SAMPLE) to avoid reading whole file
    # when it's smaller than 64KB but still large enough for detection.
    read_size = min(file_size, _DEFAULT_DETECT_SAMPLE) if file_size > 0 else _DEFAULT_DETECT_SAMPLE
    try:
        with open(filepath, "rb") as f:
            raw_data = f.read(read_size)
    except (OSError, IOError) as e:
        logger.debug("Cannot read %s for encoding detection: %s", filepath, e)
        return None

    try:
        result = chardet.detect(raw_data)  # type: ignore[union-attr]
        detected = result.get("encoding")
        confidence = result.get("confidence", 0)
        if detected and confidence > _CHARDET_CONFIDENCE_THRESHOLD:
            logger.debug("chardet detected encoding: %s (confidence: %.2f)", detected, confidence)
            return detected
        logger.debug("chardet low confidence (%.2f) for %s, falling back", confidence, detected)
    except Exception as e:
        logger.debug("chardet detection failed: %s", e)

    return None


def _try_encodings(filepath: str, encodings: List[str]) -> str:
    """Try reading file with given encodings in order.

    Iterates through the encoding list, attempting to decode the file
    with each encoding. Returns the decoded text on first success.

    Args:
        filepath: Absolute path to the file.
        encodings: List of encoding names to try (in priority order).

    Returns:
        Decoded file content as a string.

    Raises:
        UnicodeDecodeError: If all encoding attempts fail with decoding errors.
        RuntimeError: If the encoding list is empty (no encodings to try).
    """
    last_error: Optional[Exception] = None
    for enc in encodings:
        try:
            with open(filepath, encoding=enc) as f:
                text = f.read()
            logger.debug("Successfully decoded %s with encoding %s", filepath, enc)
            return text
        except UnicodeDecodeError as e:
            last_error = e
            continue
        except (OSError, IOError) as e:
            last_error = e
            continue
    # Raise appropriate error based on what failed
    if last_error is None:
        raise RuntimeError("No encodings provided to try")
    raise last_error


def parse_text(filepath: str, mime: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Parse a text file with multi-encoding detection and fallback.

    Detection strategy (in order):
    1. If chardet is available and file is large enough (>8KB):
       - Run chardet on first 64KB.
       - If confidence > 0.5, use the detected encoding.
       - If that fails, continue to step 2.
    2. Try ordered fallback encodings: UTF-8 → GBK → Latin-1.
       UTF-8 is first because it's the most common encoding for modern
       source code and documentation. GBK is second to handle Chinese
       Windows environments (simplified Chinese). Latin-1 is last because
       it can decode any byte sequence (never raises UnicodeDecodeError),
       making it a reliable last resort.
    3. If all ordered encodings fail, fall back to UTF-8 with
       errors='replace' to salvage whatever content is recoverable.

    Args:
        filepath: Absolute path to the text file.
        mime: Optional MIME type string for metadata.

    Returns:
        Dict with keys {extract_type, text, metadata}, or None if
        the file cannot be read at all.
    """
    # Step 1: Try chardet-based detection if available
    detected_enc = _detect_encoding(filepath)
    if detected_enc:
        try:
            with open(filepath, encoding=detected_enc) as f:
                text = f.read()
            return {
                "extract_type": "text",
                "text": text,
                "metadata": {"mime": mime or "text/plain", "encoding": detected_enc},
            }
        except (UnicodeDecodeError, OSError, IOError) as e:
            logger.debug("chardet encoding %s failed: %s, trying fallbacks", detected_enc, e)

    # Step 2: Try common encodings in priority order
    # UTF-8: Most common modern encoding (covers >95% of source/text files)
    # GBK: Chinese Windows default encoding (simplified Chinese)
    # Latin-1: Universal fallback that decodes any byte sequence
    common_encodings: List[str] = ["utf-8", "gbk", "latin-1"]
    try:
        text = _try_encodings(filepath, common_encodings)
        return {
            "extract_type": "text",
            "text": text,
            "metadata": {"mime": mime or "text/plain"},
        }
    except (UnicodeDecodeError, RuntimeError):
        pass

    # Step 3: All encodings failed — fallback with error replacement.
    # This salvages whatever readable content exists by replacing
    # undecodable bytes with the Unicode replacement character ().
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            text = f.read()
        logger.warning("Fallback reading %s with utf-8 replace mode", filepath)
        return {
            "extract_type": "text",
            "text": text,
            "metadata": {"mime": mime or "text/plain"},
        }
    except (OSError, IOError) as e:
        logger.warning("Cannot read %s even with replace mode: %s", filepath, e)
        return None
    except Exception as e:
        logger.exception("Failed to parse text file %s: %s", filepath, e)
        return None
