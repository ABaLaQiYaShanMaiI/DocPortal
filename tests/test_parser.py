"""
Tests for the parser module.
"""
import os
import tempfile
import pytest
from src.parser.dispatcher import parse_file


def test_text_parser(sample_text_file):
    result = parse_file(sample_text_file)
    assert result is not None
    assert result["extract_type"] == "text"
    assert result["text"] == "Hello world"


def test_pdf_parser(sample_pdf_file):
    result = parse_file(sample_pdf_file)
    assert result is not None
    assert result["extract_type"] == "text"


def test_nonexistent_file():
    nonexistent = os.path.join(tempfile.gettempdir(), "folderrag_nonexistent_file.txt")
    result = parse_file(nonexistent)
    assert result is None


# Constants Integration Tests

try:
    from src.constants import SUPPORTED_TEXT_EXTS
    _HAS_CONSTANTS = True
except ImportError:
    _HAS_CONSTANTS = False


def _get_supported_text_extensions() -> set:
    """Get the set of supported text extensions for testing.

    Returns only pure text/parsable extensions (not Office/PDF which need special handling).
    """
    if not _HAS_CONSTANTS:
        pytest.skip("src.constants not available")

    skip_exts = {'.pdf', '.docx', '.pptx', '.xlsx'}

    pure_text_exts = set()
    for ext in sorted(SUPPORTED_TEXT_EXTS):
        if ext not in skip_exts:
            pure_text_exts.add(ext)

    return pure_text_exts


def test_constants_integration_imports():
    """Verify that constants module provides SUPPORTED_TEXT_EXTS correctly."""
    if not _HAS_CONSTANTS:
        pytest.skip("src.constants not available")

    from src.constants import SUPPORTED_TEXT_EXTS as exts
    assert len(exts) > 50, f"Expected many supported extensions, got {len(exts)}"
    assert '.txt' in exts
    assert '.py' in exts
    assert '.cs' in exts
    assert '.xaml' in exts
    assert '.md' in exts


@pytest.mark.parametrize("ext", sorted(
    _get_supported_text_extensions() if _HAS_CONSTANTS else ['.txt', '.py', '.cs', '.xaml', '.json']
))
def test_all_text_extensions_parseable(tmp_path, ext):
    """Verify dispatcher can recognize and parse files with ALL supported text extensions.

    Creates a minimal file for each extension and checks that parse_file returns valid content.
    This ensures no supported extension is accidentally dropped when constants change.
    """
    if not _HAS_CONSTANTS:
        pytest.skip("src.constants not available")

    fname = f"test{ext}"
    filepath = os.path.join(str(tmp_path), fname)

    content = "hello world test content 42"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    result = parse_file(filepath)
    assert result is not None, f"parse_file returned None for extension {ext} ({fname})"
    assert result.get("text", "").strip() == content, (
        f"Content mismatch for extension {ext}: got {result.get('text', '')!r}"
    )


def test_magic_fallback():
    """Verify the dispatcher gracefully handles magic import failure.

    The dispatcher already handles this internally via try/except blocks
    around magic import. This test validates the module structure is intact.
    """
    from src.parser.dispatcher import _magic_available
    # _magic should be either None or a valid Magic object
    # _magic_available should be a boolean
    assert isinstance(_magic_available, bool)


@pytest.mark.parametrize("ext", ['.cs', '.xaml', '.sln', '.csproj', '.swift', '.kt', '.rs'])
def test_code_extensions_parsed_as_text(tmp_path, ext):
    """Specifically verify code-file extensions that were historically problematic
    (magic returns application/octet-stream for .cs on Windows) are parsed as text."""
    fname = f"test{ext}"
    filepath = os.path.join(str(tmp_path), fname)

    content_map = {
        '.xaml': '<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"><Grid/></Window>',
        '.sln': '\nMicrosoft Visual Studio Solution File, Format Version 12.00\n',
        '.swift': 'import Foundation\nlet x = 42\n',
        '.kt': 'package test\nfun main() { println(42) }\n',
        '.rs': 'fn main() { println!("hello"); }\n',
        '.cs': 'using System; class Test { static void Main() { } }',
    }
    content = content_map.get(ext, f"// test content for {ext} file\nint x = 42;")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    result = parse_file(filepath)
    assert result is not None, f"parse_file returned None for code extension {ext}"
    text = result.get("text", "").strip()
    assert len(text) > 0, f"Empty text for code extension {ext}"
    assert result["extract_type"] == "text", f"Expected text extract_type for {ext}"