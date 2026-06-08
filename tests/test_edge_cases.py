"""
Boundary and edge-case tests for FolderKnowledgeSiteGeneratorForAI.

Covers BOM detection, symlink handling, concurrent parsing safety,
malformed Office file resilience, and large-file chunking behavior.
"""

import os
import io
import tempfile
import struct
import zipfile
import threading
import pytest

# ── Imports under test ──
from src.parser.dispatcher import parse_file
from src.scanner import walk_files, collect_files_info
from src.chunker import DEFAULT_CHUNK_SIZE


# ═══════════════════════════════════════════════════════════════════
# Unicode BOM detection
# ═══════════════════════════════════════════════════════════════════

class TestUnicodeBOMDetection:
    """Verify UTF-8 BOM files are correctly parsed without corruption."""

    @staticmethod
    def _make_bom_file(suffix: str, content: str) -> str:
        """Write a file with UTF-8 BOM prefix and return its path."""
        fd, path = tempfile.mkstemp(suffix=suffix, prefix="test_bom_")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(b"\xef\xbb\xbf")  # UTF-8 BOM
            f.write(content.encode("utf-8"))
        return path

    def test_utf8_bom_text_file(self):
        path = self._make_bom_file(".txt", "Hello BOM world\n")
        try:
            result = parse_file(path)
            assert result is not None
            assert result["extract_type"] == "text"
            # BOM should be stripped, leaving the original content
            assert "Hello BOM world" in result["text"]
        finally:
            os.unlink(path)

    def test_utf8_bom_python_file(self):
        path = self._make_bom_file(".py", 'print("hello BOM")\n')
        try:
            result = parse_file(path)
            assert result is not None
            assert 'print("hello BOM")' in result["text"]
        finally:
            os.unlink(path)

    def test_utf8_bom_json_file(self):
        path = self._make_bom_file(".json", '{"key": "value"}\n')
        try:
            result = parse_file(path)
            assert result is not None
            assert '"key"' in result["text"]
        finally:
            os.unlink(path)

    def test_non_bom_file_still_works(self):
        """Ensure files without BOM are also parsed correctly (no regression)."""
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="test_nobom_")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write("No BOM here\n")
        try:
            result = parse_file(path)
            assert result is not None
            assert "No BOM here" in result["text"]
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════
# Malformed Office files
# ═══════════════════════════════════════════════════════════════════

class TestMalformedOfficeFiles:
    """Verify corrupted DOCX / XLSX files do not crash the parser."""

    @staticmethod
    def _make_corrupt_zip(suffix: str) -> str:
        """Create a file with a .docx/.xlsx extension but invalid ZIP content."""
        fd, path = tempfile.mkstemp(suffix=suffix, prefix="corrupt_")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(b"NOT_A_ZIP_FILE\x00\x01\x02\x03" * 10)
        return path

    def test_corrupt_docx_returns_none(self):
        path = self._make_corrupt_zip(".docx")
        try:
            result = parse_file(path)
            # Should either return None or a graceful error response, never raise
            assert result is None or isinstance(result, dict)
        finally:
            os.unlink(path)

    def test_corrupt_xlsx_returns_none(self):
        path = self._make_corrupt_zip(".xlsx")
        try:
            result = parse_file(path)
            assert result is None or isinstance(result, dict)
        finally:
            os.unlink(path)

    def test_empty_docx_returns_none(self):
        """A truly empty file with .docx extension should not crash."""
        fd, path = tempfile.mkstemp(suffix=".docx", prefix="empty_")
        os.close(fd)
        # file is 0 bytes
        try:
            result = parse_file(path)
            assert result is None or isinstance(result, dict)
        finally:
            os.unlink(path)

    def test_truncated_zip_docx(self):
        """ZIP header present but truncated body should not crash."""
        fd, path = tempfile.mkstemp(suffix=".docx", prefix="trunc_")
        os.close(fd)
        # Write only a partial ZIP local file header
        with open(path, "wb") as f:
            f.write(b"PK\x03\x04" + b"\x00" * 26)
        try:
            result = parse_file(path)
            assert result is None or isinstance(result, dict)
        finally:
            os.unlink(path)

    def test_valid_empty_docx(self):
        """A minimal but valid DOCX (ZIP with bare structure) parses without crash."""
        fd, path = tempfile.mkstemp(suffix=".docx", prefix="valid_empty_")
        os.close(fd)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Minimum required parts for python-docx
            zf.writestr("[Content_Types].xml",
                '<?xml version="1.0"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                '</Types>')
            zf.writestr("_rels/.rels",
                '<?xml version="1.0"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                '</Relationships>')
            zf.writestr("word/document.xml",
                '<?xml version="1.0"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>Minimal docx</w:t></w:r></w:p></w:body>'
                '</w:document>')
        try:
            result = parse_file(path)
            assert result is not None
            assert isinstance(result, dict)
            assert "Minimal docx" in result.get("text", "")
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════
# Concurrent parsing (thread-safety)
# ═══════════════════════════════════════════════════════════════════

class TestConcurrentParsing:
    """Verify thread-safety of text file parsing under concurrent access."""

    def test_concurrent_text_parsing(self):
        """Multiple threads parsing different text files should not interfere."""
        # Create several temporary text files
        paths = []
        try:
            for i in range(10):
                fd, path = tempfile.mkstemp(suffix=".txt", prefix=f"conc_{i}_")
                os.close(fd)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"Content of file {i}\nLine 2\n")
                paths.append(path)

            results = []
            lock = threading.Lock()
            errors = []

            def worker(filepath: str, expected_prefix: str):
                try:
                    result = parse_file(filepath)
                    with lock:
                        results.append(result)
                except Exception as e:
                    with lock:
                        errors.append((filepath, str(e)))

            threads = []
            for idx, p in enumerate(paths):
                t = threading.Thread(target=worker, args=(p, f"Content of file {idx}"))
                threads.append(t)

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"Concurrent parsing errors: {errors}"
            assert len(results) == len(paths)
            for r in results:
                assert r is not None
                assert r["extract_type"] == "text"
        finally:
            for p in paths:
                if os.path.exists(p):
                    os.unlink(p)

    def test_concurrent_same_file_parsing(self):
        """Multiple threads parsing the same file should be safe."""
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="shared_")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write("Shared file content\n" * 100)

        try:
            errors = []
            lock = threading.Lock()

            def worker():
                try:
                    parse_file(path)
                except Exception as e:
                    with lock:
                        errors.append(str(e))

            threads = [threading.Thread(target=worker) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"Shared file parsing errors: {errors}"
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════
# Large file chunking
# ═══════════════════════════════════════════════════════════════════

class TestHugeFileChunking:
    """Verify large files are handled correctly in chunked mode."""

    def test_large_text_file_does_not_crash(self):
        """A moderately large text file (~5MB) should parse without errors."""
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="large_")
        os.close(fd)
        # Write ~5 MB of text
        line = "A" * 79 + "\n"
        with open(path, "w", encoding="utf-8") as f:
            for _ in range(65_000):  # ~5.2 MB
                f.write(line)

        try:
            result = parse_file(path)
            assert result is not None
            assert result["extract_type"] == "text"
            assert len(result["text"]) > 1_000_000
        finally:
            os.unlink(path)

    def test_chunk_size_exceeds_single_file(self):
        """When a single file is larger than chunk_size, chunker handles it gracefully."""
        from src.chunker import FileChunk

        chunk = FileChunk(chunk_index=0, chunk_size=10_000)
        # Simulate adding a file larger than the chunk
        large_content = "X" * 25_000
        chunk.files.append({
            "rel_path": "big_file.txt",
            "text": large_content,
            "size": len(large_content),
            "size_hr": "25 KB"
        })

        # The chunk should not crash when serialized
        assert chunk.files[0]["size"] == 25_000

    def test_empty_file_in_chunk(self):
        """Empty files should be handled gracefully in chunking."""
        from src.chunker import FileChunk

        chunk = FileChunk(chunk_index=0, chunk_size=10_000)
        chunk.files.append({
            "rel_path": "empty.txt",
            "text": "",
            "size": 0,
            "size_hr": "0 B"
        })

        assert len(chunk.files) == 1
        assert chunk.files[0]["text"] == ""


# ═══════════════════════════════════════════════════════════════════
# Symlink handling
# ═══════════════════════════════════════════════════════════════════

class TestSymlinkHandling:
    """Verify symbolic links are handled gracefully (skipped, not followed)."""

    def test_symlink_does_not_crash_scanner(self, tmp_path):
        """Scanner should not crash or hang when encountering a symlink."""
        # Create a real file and a symlink pointing to it
        real_file = tmp_path / "real.txt"
        real_file.write_text("real content", encoding="utf-8")

        symlink = tmp_path / "link.txt"
        try:
            os.symlink(str(real_file), str(symlink))
        except OSError:
            pytest.skip("Symlink creation not supported on this platform (requires admin/privilege)")

        # walk_files should not raise; symlink may be skipped or followed
        try:
            results = list(walk_files(str(tmp_path)))
            # At minimum, the scanner must not crash
            assert isinstance(results, list)
        except Exception as e:
            pytest.fail(f"walk_files raised on symlink: {e}")

    def test_symlink_parse_handles_gracefully(self, tmp_path):
        """parse_file on a symlink target should work; on a dangling symlink should not crash."""
        real_file = tmp_path / "sym_target.txt"
        real_file.write_text("target content", encoding="utf-8")

        link = tmp_path / "good_link.txt"
        dangling = tmp_path / "dangling_link.txt"
        try:
            os.symlink(str(real_file), str(link))
            os.symlink(str(tmp_path / "nonexistent.txt"), str(dangling))
        except OSError:
            pytest.skip("Symlink creation not supported on this platform")

        # Good symlink → should parse the target file
        result = parse_file(str(link))
        assert result is not None
        assert "target content" in result["text"]

        # Dangling symlink → should return None, not crash
        result_dangling = parse_file(str(dangling))
        assert result_dangling is None or isinstance(result_dangling, dict)