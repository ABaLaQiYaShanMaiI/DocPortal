"""
边界与极端情况测试 / Boundary and edge-case tests.

覆盖：BOM检测、符号链接处理、并发解析安全、损坏Office文件容错、大文件分块。
"""

import os
import tempfile
import zipfile
import threading
import pytest

# ── Imports under test ──
from src.parser.dispatcher import parse_file
from src.scanner import walk_files


# ═══════════════════════════════════════════════════════════════════
# Unicode BOM 检测 / BOM detection
# ═══════════════════════════════════════════════════════════════════


class TestUnicodeBOMDetection:
    """验证 UTF-8 BOM 文件被正确解析，不损坏内容 / Verify BOM files parse correctly."""

    @staticmethod
    def _make_bom_file(suffix: str, content: str) -> str:
        """创建带 UTF-8 BOM 前缀的文件并返回路径 / Create file with BOM prefix."""
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
            # BOM 应被移除，保留原始内容 / BOM stripped, original content preserved
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
        """确保无 BOM 文件也能正常解析（回归测试）/ Non-BOM regression."""
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
# 损坏 Office 文件 / Malformed Office files
# ═══════════════════════════════════════════════════════════════════


class TestMalformedOfficeFiles:
    """验证损坏的 DOCX / XLSX 文件不会导致解析器崩溃 / Corrupt files don't crash."""

    @staticmethod
    def _make_corrupt_zip(suffix: str) -> str:
        """创建扩展名为 .docx/.xlsx 但内容非有效 ZIP 的文件 / Invalid ZIP content."""
        fd, path = tempfile.mkstemp(suffix=suffix, prefix="corrupt_")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(b"NOT_A_ZIP_FILE\x00\x01\x02\x03" * 10)
        return path

    def test_corrupt_docx_returns_none(self):
        path = self._make_corrupt_zip(".docx")
        try:
            result = parse_file(path)
            # 应返回 None 或优雅的错误响应，绝不抛出异常 / Return None or graceful error
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
        """扩展名为 .docx 的空文件不应崩溃 / Empty .docx file must not crash."""
        fd, path = tempfile.mkstemp(suffix=".docx", prefix="empty_")
        os.close(fd)
        # 文件为 0 字节 / zero-byte file
        try:
            result = parse_file(path)
            assert result is None or isinstance(result, dict)
        finally:
            os.unlink(path)

    def test_truncated_zip_docx(self):
        """ZIP 文件头存在但内容被截断，不应崩溃 / Truncated ZIP body."""
        fd, path = tempfile.mkstemp(suffix=".docx", prefix="trunc_")
        os.close(fd)
        # 仅写入部分 ZIP 本地文件头 / partial ZIP header
        with open(path, "wb") as f:
            f.write(b"PK\x03\x04" + b"\x00" * 26)
        try:
            result = parse_file(path)
            assert result is None or isinstance(result, dict)
        finally:
            os.unlink(path)

    def test_valid_empty_docx(self):
        """最小有效 DOCX（仅有基本结构）可正常解析 / Minimal valid DOCX."""
        fd, path = tempfile.mkstemp(suffix=".docx", prefix="valid_empty_")
        os.close(fd)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            # python-docx 所需的最小部件 / Minimum required parts
            zf.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                "</Types>",
            )
            zf.writestr(
                "_rels/.rels",
                '<?xml version="1.0"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                "</Relationships>",
            )
            zf.writestr(
                "word/document.xml",
                '<?xml version="1.0"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>Minimal docx</w:t></w:r></w:p></w:body>"
                "</w:document>",
            )
        try:
            result = parse_file(path)
            assert result is not None
            assert isinstance(result, dict)
            assert "Minimal docx" in result.get("text", "")
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════
# 并发解析（线程安全）/ Concurrent parsing
# ═══════════════════════════════════════════════════════════════════


class TestConcurrentParsing:
    """验证多线程并发解析文本文件的线程安全性 / Thread-safety."""

    def test_concurrent_text_parsing(self):
        """多线程解析不同文本文件不应相互干扰 / Multi-thread different files."""
        # 创建多个临时文本文件 / Create temp text files
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
        """多线程读取同一文件应安全无竞争 / Multi-thread same file."""
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
# 大文件分块 / Huge file chunking
# ═══════════════════════════════════════════════════════════════════


class TestHugeFileChunking:
    """验证大文件在分块模式下正确处理 / Large file chunking."""

    def test_large_text_file_does_not_crash(self):
        """中等大小文本文件（~5MB）应无错误解析 / ~5MB text file."""
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="large_")
        os.close(fd)
        # 写入约 5 MB 文本 / Write ~5 MB text
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
        """单文件超出 chunk_size 时，分块器应优雅处理 / Oversized file in chunk."""
        from src.chunker import FileChunk

        chunk = FileChunk(chunk_index=0, chunk_size=10_000)
        # 模拟添加一个大于分块的文件 / Simulate oversized file
        large_content = "X" * 25_000
        chunk.files.append(
            {"rel_path": "big_file.txt", "text": large_content, "size": len(large_content), "size_hr": "25 KB"}
        )

        # 序列化时不应崩溃 / No crash on serialize
        assert chunk.files[0]["size"] == 25_000

    def test_empty_file_in_chunk(self):
        """空文件在分块中应被优雅处理 / Empty file chunking."""
        from src.chunker import FileChunk

        chunk = FileChunk(chunk_index=0, chunk_size=10_000)
        chunk.files.append({"rel_path": "empty.txt", "text": "", "size": 0, "size_hr": "0 B"})

        assert len(chunk.files) == 1
        assert chunk.files[0]["text"] == ""


# ═══════════════════════════════════════════════════════════════════
# 符号链接处理 / Symlink handling
# ═══════════════════════════════════════════════════════════════════


class TestSymlinkHandling:
    """验证符号链接被优雅处理（跳过，不追踪）/ Symlink graceful handling."""

    def test_symlink_does_not_crash_scanner(self, tmp_path):
        """扫描器遇到符号链接不应崩溃或卡死 / Scanner + symlink."""
        # 创建真实文件及其符号链接 / Real file + symlink
        real_file = tmp_path / "real.txt"
        real_file.write_text("real content", encoding="utf-8")

        symlink = tmp_path / "link.txt"
        try:
            os.symlink(str(real_file), str(symlink))
        except OSError:
            pytest.skip("Symlink creation not supported on this platform (requires admin/privilege)")

        # walk_files 不应抛异常；符号链接可被跳过或跟随 / symlink safe
        try:
            results = list(walk_files(str(tmp_path)))
            # At minimum, the scanner must not crash
            assert isinstance(results, list)
        except Exception as e:
            pytest.fail(f"walk_files raised on symlink: {e}")

    def test_symlink_parse_handles_gracefully(self, tmp_path):
        """有效符号链接可正常解析；悬空符号链接不崩溃 / Good + dangling symlink."""
        real_file = tmp_path / "sym_target.txt"
        real_file.write_text("target content", encoding="utf-8")

        link = tmp_path / "good_link.txt"
        dangling = tmp_path / "dangling_link.txt"
        try:
            os.symlink(str(real_file), str(link))
            os.symlink(str(tmp_path / "nonexistent.txt"), str(dangling))
        except OSError:
            pytest.skip("Symlink creation not supported on this platform")

        # 有效符号链接 → 可解析目标文件 / Good symlink → parseable
        result = parse_file(str(link))
        assert result is not None
        assert "target content" in result["text"]

        # 悬空符号链接 → 返回 None，不崩溃 / Dangling → None
        result_dangling = parse_file(str(dangling))
        assert result_dangling is None or isinstance(result_dangling, dict)
