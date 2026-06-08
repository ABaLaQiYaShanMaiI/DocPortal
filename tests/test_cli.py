"""
Tests for the CLI (generate.py) — TXT export mode and portal mode.
"""

import os
import sys
import subprocess
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, PROJECT_ROOT)

GENERATE_SCRIPT = os.path.join(PROJECT_ROOT, "generate.py")

# ──────────────────────────────────────────────
#  Fixtures
# ──────────────────────────────────────────────

def _create_sample_folder(tmpdir: str) -> str:
    """Create a folder with sample files for testing."""
    folder = os.path.join(tmpdir, "sample_docs")
    os.makedirs(folder, exist_ok=True)

    # Text file
    with open(os.path.join(folder, "hello.txt"), "w", encoding="utf-8") as f:
        f.write("Hello, this is a sample text file for FolderKnowledgeSiteGeneratorForAI testing.\nIt has multiple lines.\n")

    # Markdown file
    with open(os.path.join(folder, "readme.md"), "w", encoding="utf-8") as f:
        f.write("# Sample Document\n\nThis is a Markdown file with some **bold** text.\n")

    # CSV file (supported via fallback extension list)
    with open(os.path.join(folder, "notes.csv"), "w", encoding="utf-8") as f:
        f.write("id,name,value\n1,test,100\n2,demo,200\n")

    return folder


def _create_large_sample_folder(tmpdir: str) -> str:
    """Create a folder with sufficiently large files to test chunking."""
    folder = os.path.join(tmpdir, "large_docs")
    os.makedirs(folder, exist_ok=True)

    # Create ~30K chars each file → 5 files = ~150K chars, fits well in small chunks
    for i in range(5):
        with open(os.path.join(folder, f"doc_{i}.txt"), "w", encoding="utf-8") as f:
            f.write(f"# Document {i}\n\n" + "content line.\n" * 2000)

    return folder


# ──────────────────────────────────────────────
#  Helper: run generate.py as subprocess
# ──────────────────────────────────────────────

def _run_generate(args: list) -> tuple:
    """Run generate.py with given args and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, GENERATE_SCRIPT] + args
    # Use utf-8 encoding explicitly to handle Chinese output on Windows
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return result.returncode, result.stdout, result.stderr


# ──────────────────────────────────────────────
#  Tests — TXT Export Mode (default, no --portal)
# ──────────────────────────────────────────────

class TestTextExportMode:
    """Test the traditional TXT export mode (default, no --portal)."""

    def test_basic_text_export(self, tmp_path):
        """Generate a TXT file from sample docs."""
        folder = _create_sample_folder(str(tmp_path))
        output = os.path.join(str(tmp_path), "output.txt")

        rc, stdout, stderr = _run_generate([folder, "-o", output])

        assert rc == 0, f"Expected exit code 0, got {rc}. stderr: {stderr}"
        assert os.path.exists(output), f"Output file not found: {output}"
        assert os.path.getsize(output) > 0, "Output file is empty"
        assert "OK" in stdout, f"Unexpected stdout: {stdout}"

        # Verify plain text structure (TXT mode)
        with open(output, encoding="utf-8") as f:
            content = f.read()
        # TXT mode uses file: headers
        assert "hello.txt" in content

    def test_extension_appended(self, tmp_path):
        """Verify .txt extension is appended when missing."""
        folder = _create_sample_folder(str(tmp_path))
        output = os.path.join(str(tmp_path), "output")  # No extension

        rc, stdout, stderr = _run_generate([folder, "-o", output])
        assert rc == 0
        # TXT mode appends .txt
        expected = output + ".txt"
        assert os.path.exists(expected), f"Expected {expected} to exist"

    def test_max_chars_warning_in_txt_mode(self, tmp_path):
        """Verify --max-chars in TXT mode prints a warning (no longer truncates)."""
        folder = _create_sample_folder(str(tmp_path))
        output = os.path.join(str(tmp_path), "output.txt")

        rc, stdout, stderr = _run_generate([folder, "-o", output, "--max-chars", "20"])

        assert rc == 0, f"Expected exit code 0, got {rc}. stderr: {stderr}"
        assert os.path.exists(output)

        with open(output, encoding="utf-8") as f:
            content = f.read()
        # Must NOT be truncated (old behavior would have ~20 chars)
        assert len(content) > 100, f"Expected full content (>100 chars), got {len(content)}"
        # Must print a warning
        assert "no effect" in stdout.lower(), f"Expected warning about no effect in: {stdout}"

    def test_missing_folder(self, tmp_path):
        """Verify error on non-existent folder."""
        output = os.path.join(str(tmp_path), "output.txt")
        rc, stdout, stderr = _run_generate(["/nonexistent/path", "-o", output])
        assert rc != 0, "Expected non-zero exit for invalid folder"

    def test_no_output_flag(self, tmp_path):
        """Verify error when -o is missing."""
        folder = _create_sample_folder(str(tmp_path))
        rc, stdout, stderr = _run_generate([folder])
        assert rc != 0, "Expected non-zero exit when -o is missing"
        # Should print usage/error
        assert "usage" in stdout.lower() or "error" in stderr.lower()


# ──────────────────────────────────────────────
#  Tests — Chunked Mode (--split-chunks)
# ──────────────────────────────────────────────

class TestChunkedMode:
    """Test the chunked (--split-chunks) output mode."""

    def test_basic_split_chunks(self, tmp_path):
        """Generate chunked output from sample docs."""
        folder = _create_sample_folder(str(tmp_path))
        output_dir = os.path.join(str(tmp_path), "chunked_out")

        rc, stdout, stderr = _run_generate([
            folder, "--split-chunks", "-o", output_dir,
        ])

        assert rc == 0, f"Expected exit code 0, got {rc}. stderr: {stderr}"
        assert os.path.isdir(output_dir), f"Output dir not created: {output_dir}"
        # Should have part files and index
        files = [f for f in os.listdir(output_dir) if f.startswith("part_") and f.endswith(".txt")]
        assert len(files) > 0, f"No part files found in {output_dir}: {os.listdir(output_dir)}"
        assert any(f.startswith("sample_docs_index") for f in os.listdir(output_dir)), \
            f"Index HTML not found in {output_dir}: {os.listdir(output_dir)}"
        assert "分片" in stdout or "chunk" in stdout.lower(), f"Unexpected stdout: {stdout}"

    def test_split_chunks_with_max_chars_limit(self, tmp_path):
        """Verify --max-chars in chunked mode truncates across all chunks."""
        folder = _create_large_sample_folder(str(tmp_path))
        output_dir = os.path.join(str(tmp_path), "chunked_limited")

        # Use very small max to test global limit with large chunk size
        rc, stdout, stderr = _run_generate([
            folder, "--split-chunks", "-o", output_dir,
            "--chunk-size", "500000", "--max-chars", "100",
        ])

        assert rc == 0, f"Expected exit code 0, got {rc}. stderr: {stderr}"
        # Total content across all chunks should be ≤ ~100 chars
        total_chars = 0
        for fname in os.listdir(output_dir):
            if fname.startswith("part_") and fname.endswith(".txt"):
                fpath = os.path.join(output_dir, fname)
                with open(fpath, encoding="utf-8") as f:
                    total_chars += len(f.read())
        # Allow some overhead for separators/headers, but should be small
        assert total_chars < 700, f"Expected total < 700 chars with --max-chars=100, got {total_chars}"

    def test_split_chunks_custom_chunk_size(self, tmp_path):
        """Verify --chunk-size controls per-file limit."""
        folder = _create_large_sample_folder(str(tmp_path))
        output_dir = os.path.join(str(tmp_path), "chunked_custom")

        rc, stdout, stderr = _run_generate([
            folder, "--split-chunks", "-o", output_dir,
            "--chunk-size", "20000",
        ])

        assert rc == 0, f"Expected exit code 0, got {rc}. stderr: {stderr}"
        files = sorted([f for f in os.listdir(output_dir) if f.startswith("part_") and f.endswith(".txt")])
        # Each file contains whole files (not truncated mid-file), so there should be multiple chunks
        assert len(files) >= 2, f"Expected >=2 chunks with small chunk size, got {len(files)}"

    def test_split_chunks_output_dir(self, tmp_path):
        """Verify -o is used directly as output directory (no extra nesting)."""
        folder = _create_sample_folder(str(tmp_path))
        output_dir = os.path.join(str(tmp_path), "my_export")

        # First generate
        rc, stdout, stderr = _run_generate([
            folder, "--split-chunks", "-o", output_dir,
        ])
        assert rc == 0

        # Files should be directly in output_dir, not nested
        assert os.path.isdir(output_dir)
        direct_files = os.listdir(output_dir)
        assert any(f.startswith("part_") for f in direct_files), \
            f"part files should be directly in {output_dir}, got: {direct_files}"
        # There should be no subdirectory with the same name
        assert not any(os.path.isdir(os.path.join(output_dir, name)) for name in direct_files), \
            f"Should not have subdirectories in {output_dir}, got: {direct_files}"


# ──────────────────────────────────────────────
#  Tests — Portal Mode
# ──────────────────────────────────────────────

class TestPortalMode:
    """Test the portal (single-page) generation mode."""

    def test_basic_portal_generation(self, tmp_path):
        """Generate a portal from sample docs."""
        folder = _create_sample_folder(str(tmp_path))
        output_dir = os.path.join(str(tmp_path), "portal_output")

        rc, stdout, stderr = _run_generate([
            folder, "--portal", "-o", output_dir,
        ])

        assert rc == 0, f"Expected exit code 0, got {rc}. stderr: {stderr}"
        assert os.path.isdir(output_dir), f"Output dir not created: {output_dir}"
        assert os.path.exists(os.path.join(output_dir, "index.html")), "index.html not found"
        assert "知识门户" in stdout or "Portal" in stdout or "门户" in stdout

        # Verify index.html structure
        index_path = os.path.join(output_dir, "index.html")
        with open(index_path, encoding="utf-8") as f:
            content = f.read()
        assert "FolderKnowledgeSiteGeneratorForAI" in content or "folder-knowledge" in content
        assert "sample_docs" in content

    def test_portal_page_creation(self, tmp_path):
        """Verify that portal is single-page: no docs/ dir, all content in index.html."""
        folder = _create_sample_folder(str(tmp_path))
        output_dir = os.path.join(str(tmp_path), "portal_pages")

        rc, stdout, stderr = _run_generate([
            folder, "--portal", "-o", output_dir,
        ])
        assert rc == 0

        # Portal is single-page — no docs/ subdirectory
        docs_dir = os.path.join(output_dir, "docs")
        assert not os.path.isdir(docs_dir), "docs/ subdirectory should NOT exist (single-page portal)"

        # All content is in index.html
        index_path = os.path.join(output_dir, "index.html")
        assert os.path.isfile(index_path), "index.html should exist"
        with open(index_path, encoding="utf-8") as f:
            content = f.read()
        # Verify file contents are embedded directly in index.html
        assert "hello.txt" in content, "hello.txt content should be in index.html"
        assert "readme.md" in content, "readme.md content should be in index.html"

    def test_portal_skipped_flag(self, tmp_path):
        """Verify --no-skipped works (all supported files so no effect)."""
        folder = _create_sample_folder(str(tmp_path))
        output_dir = os.path.join(str(tmp_path), "portal_no_skipped")

        rc, stdout, stderr = _run_generate([
            folder, "--portal", "-o", output_dir,
            "--no-skipped"
        ])
        assert rc == 0

    def test_portal_missing_folder(self, tmp_path):
        """Verify error on non-existent folder in portal mode."""
        output_dir = os.path.join(str(tmp_path), "portal_empty")
        rc, stdout, stderr = _run_generate([
            "/nonexistent/path", "--portal", "-o", output_dir
        ])
        assert rc != 0, "Expected non-zero exit for invalid folder in portal mode"


# ──────────────────────────────────────────────
#  Tests — CLI Argument Validation
# ──────────────────────────────────────────────

class TestCLIArgs:
    """Test CLI argument parsing and validation."""

    def test_help_output(self):
        """Verify --help prints usage information."""
        rc, stdout, stderr = _run_generate(["--help"])
        assert rc == 0
        assert "FolderKnowledgeSiteGeneratorForAI" in stdout or "folderknowledge" in stdout.lower()
        assert "--portal" in stdout

    def test_version_or_name(self):
        """Verify basic CLI identification."""
        rc, stdout, stderr = _run_generate(["--help"])
        assert rc == 0
        # Should mention both modes
        assert "TXT" in stdout or "HTML" in stdout
        assert "portal" in stdout.lower()
        assert "split-chunks" in stdout.lower()
