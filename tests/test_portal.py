"""
Tests for the portal generator module.
"""

import os
import tempfile

from src.generator.portal import (
    generate_portal,
    generate_portal_split,
    extract_keywords,
)
from src.utils import human_readable_size


def test_human_readable_size():
    """Test size formatting."""
    assert "B" in human_readable_size(500)
    assert "KB" in human_readable_size(2048)
    assert "MB" in human_readable_size(1048576 * 2)


def test_extract_keywords():
    """Test keyword extraction from text."""
    text = """
    本文介绍了人工智能在医疗领域的应用。
    人工智能技术可以辅助医生进行诊断。
    机器学习算法能够分析医学影像数据。
    深度学习模型在疾病预测方面表现优异。
    AI technology helps doctors diagnose diseases.
    Machine learning improves medical imaging analysis.
    """
    keywords = extract_keywords(text, max_words=5)
    assert len(keywords) <= 5
    assert len(keywords) > 0
    # Should not contain stop words
    for kw in keywords:
        assert kw not in ("的", "了", "在", "是", "the", "and", "for")


def test_extract_keywords_stop_words():
    """Test that stop words are filtered out."""
    text = "这是一个测试文件，其中的内容主要是用于测试功能。"
    keywords = extract_keywords(text, max_words=5)
    for kw in keywords:
        assert kw not in ("的", "了", "是", "一", "一个", "在")


def test_generate_portal_empty_folder():
    """Test portal generation with an empty folder."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        result = generate_portal(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )
        assert result["doc_count"] == 0
        assert result["total_chars"] == 0
        assert result["index_file"] is None


def test_generate_portal_with_text_file():
    """Test portal generation with a single text file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        test_file = os.path.join(source_dir, "test_doc.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("This is a test document for portal generation.")

        result = generate_portal(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )

        assert result["doc_count"] >= 1
        assert result["total_chars"] > 0
        assert result["index_file"] is not None
        assert os.path.exists(result["index_file"])

        with open(result["index_file"], encoding="utf-8") as f:
            content = f.read()
        assert "test_doc.txt" in content
        assert "This is a test document for portal generation." in content


def test_generate_portal_output_dir_exists():
    """Test portal generation when output dir already exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)
        os.makedirs(output_dir)

        dummy = os.path.join(output_dir, "dummy.txt")
        with open(dummy, "w") as f:
            f.write("dummy")

        test_file = os.path.join(source_dir, "test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Test content")

        result = generate_portal(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )
        assert result["doc_count"] >= 1
        assert os.path.exists(result["index_file"])


def test_generate_portal_doc_sorting():
    """Test that documents are sorted alphabetically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        files = ["b_file.txt", "a_file.txt", "c_file.txt"]
        for fname in files:
            with open(os.path.join(source_dir, fname), "w", encoding="utf-8") as f:
                f.write(f"Content of {fname}")

        result = generate_portal(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )
        assert result["doc_count"] == 3
        assert result["index_file"] is not None
        assert os.path.exists(result["index_file"])


# ──────────────────────────────────────────────
#  Always-expanded content tests
# ──────────────────────────────────────────────


def test_doc_content_always_visible():
    """
    Verify that .doc-content blocks are always visible (no display:none)
    in the generated portal.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        test_file = os.path.join(source_dir, "sample.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("This is visible content for AI reading.")

        result = generate_portal(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )

        assert result["index_file"] is not None
        with open(result["index_file"], encoding="utf-8") as f:
            content = f.read()

        assert 'style="display:none"' not in content, (
            "doc-content should not have display:none (content should always be visible)"
        )
        assert "This is visible content for AI reading." in content, (
            "File content should be present and visible in the DOM"
        )
        assert 'aria-hidden="true"' not in content, "sr-only block should not exist in Portal mode"


def test_each_file_block_has_copy_button():
    """
    Verify that every file block in the portal contains a copy button.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        for i, fname in enumerate(["alpha.txt", "beta.txt", "gamma.txt"]):
            with open(os.path.join(source_dir, fname), "w", encoding="utf-8") as f:
                f.write(f"Content of {fname}.")

        result = generate_portal(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )

        assert result["index_file"] is not None
        with open(result["index_file"], encoding="utf-8") as f:
            content = f.read()

        copy_btn_count = content.count('class="copy-file-btn"')
        assert copy_btn_count == 3, f"Expected 3 copy-file-btn elements, found {copy_btn_count}"

        import re

        indices = re.findall(r'data-file-index="(\d+)"', content)
        assert len(indices) == 3, f"Expected 3 data-file-index attributes, found {len(indices)}"
        assert set(indices) == {"0", "1", "2"}, f"Expected data-file-indices 0,1,2, got {set(indices)}"

        for i in range(3):
            assert f'id="file-content-{i}"' in content, f"Expected pre element with id='file-content-{i}'"


def test_copy_button_calls_copy_function():
    """
    Verify that copy buttons invoke the copyFileContent JavaScript function.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        test_file = os.path.join(source_dir, "test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Test content for copy.")

        result = generate_portal(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )

        assert result["index_file"] is not None
        with open(result["index_file"], encoding="utf-8") as f:
            content = f.read()

        assert 'onclick="copyFileContent(this)"' in content, "Copy button should call copyFileContent(this) on click"
        assert "function copyFileContent" in content, "copyFileContent JavaScript function should be defined"


def test_no_sr_only_block_in_portal():
    """
    Verify that the sr-only block with AI-readable text is NOT present
    in the generated portal page.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        test_file = os.path.join(source_dir, "test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Content for Portal mode.")

        result = generate_portal(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )

        assert result["index_file"] is not None
        with open(result["index_file"], encoding="utf-8") as f:
            content = f.read()

        assert "KNOWLEDGE PORTAL" not in content, "Old sr-only KNOWLEDGE PORTAL header should not exist"
        assert "AI-READABLE TEXT EXTRACT" not in content, "Old AI-READABLE TEXT EXTRACT label should not exist"
        assert "END OF AI-READABLE TEXT EXTRACT" not in content, "Old sr-only end marker should not exist"


def test_portal_uses_minimal_font_and_compact_layout():
    """
    Verify that the portal uses the minimal font size (3px) and compact
    layout to maximize code density for AI text extraction.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        test_file = os.path.join(source_dir, "test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Test content.")

        result = generate_portal(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )

        assert result["index_file"] is not None
        with open(result["index_file"], encoding="utf-8") as f:
            content = f.read()

        assert "font-size: 3px" in content or "font-size:3px" in content, (
            "CSS should have font-size: 3px for .doc-content pre"
        )
        assert "white-space: pre-wrap" in content or "white-space:pre-wrap" in content, (
            "CSS should have white-space: pre-wrap for wrapping"
        )
        assert "word-break: break-all" in content or "word-break:break-all" in content, (
            "CSS should have word-break: break-all"
        )
        assert "overflow-x: hidden" in content or "overflow-x:hidden" in content, "CSS should have overflow-x: hidden"
        assert "line-height: 1.2" in content or "line-height:1.2" in content, "CSS should have line-height: 1.2"


# ──────────────────────────────────────────────
#  Skipped file behavior tests
# ──────────────────────────────────────────────


def _create_folder_with_unsupported_file(tmpdir: str) -> str:
    """Create a folder with a supported .txt and an unsupported file type."""
    folder = os.path.join(tmpdir, "mixed_docs")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "readable.txt"), "w", encoding="utf-8") as f:
        f.write("Supported content for portal test.")
    with open(os.path.join(folder, "notes.bin"), "wb") as f:
        f.write(b"\x00\x01\x02\x03\xff\xfe\xfd\xfc" * 32)
    return folder


def test_skipped_files_do_not_generate_pages():
    """
    Verify that unsupported/skipped files do NOT have doc-blocks
    in the index page (portal is single-page, no separate docs/ dir).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = _create_folder_with_unsupported_file(tmpdir)
        output_dir = os.path.join(tmpdir, "output")

        result = generate_portal(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
            include_skipped=True,
        )

        docs_dir = os.path.join(output_dir, "docs")
        assert not os.path.isdir(docs_dir), "docs/ directory should NOT exist (single-page portal)"

        assert result["index_file"] and os.path.exists(result["index_file"])
        with open(result["index_file"], encoding="utf-8") as f:
            content = f.read()

        import re

        file_content_ids = re.findall(r'id="file-content-\d+"', content)
        assert "notes.bin" in content, "notes.bin should appear in file tree"
        assert len(file_content_ids) == 1, (
            f"Expected exactly 1 file-content block (for readable.txt), found {len(file_content_ids)}"
        )
        assert 'id="file-content-0"' in content, "readable.txt should have file-content-0"
        assert 'id="file-content-1"' not in content, "notes.bin should not have a file-content block"

        assert result["skipped"] >= 1, f"Expected at least 1 skipped, got {result['skipped']}"
        assert result["doc_count"] == 1, f"Expected 1 parsed doc, got {result['doc_count']}"


def test_skipped_files_appear_in_file_tree():
    """Verify that skipped files appear in the file tree when include_skipped=True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = _create_folder_with_unsupported_file(tmpdir)
        output_dir = os.path.join(tmpdir, "output")

        result = generate_portal(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
            include_skipped=True,
        )

        index_path = result["index_file"]
        assert index_path and os.path.exists(index_path)
        with open(index_path, encoding="utf-8") as f:
            content = f.read()

        assert "notes.bin" in content, "Skipped file 'notes.bin' should appear in file tree"
        assert "skipped" in content.lower() or "\u23ed\ufe0f" in content or "tree-file.skipped" in content, (
            "Skipped file styling indicator expected in page"
        )


def test_skipped_files_excluded_from_file_tree_when_disabled():
    """Verify that skipped files do NOT appear in the file tree when include_skipped=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = _create_folder_with_unsupported_file(tmpdir)
        output_dir = os.path.join(tmpdir, "output")

        result = generate_portal(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
            include_skipped=False,
        )

        if result["index_file"]:
            with open(result["index_file"], encoding="utf-8") as f:
                content = f.read()
            assert "notes.bin" not in content, "Skipped file should not appear in index when include_skipped=False"


def test_skipped_page_template_unused_by_portal():
    """
    Verify that wrap_skipped_html is available as a public API
    but the portal generator doesn't use it for skipped files.
    """
    from src.generator.templates import wrap_skipped_html

    assert callable(wrap_skipped_html), "wrap_skipped_html should be importable and callable"

    sample_html = wrap_skipped_html(
        title="test.xyz",
        folder_name="test_folder",
        file_size_hr="1.0 KB",
        filepath="/path/to/test.xyz",
    )
    assert "<!DOCTYPE html>" in sample_html
    assert "test.xyz" in sample_html


# ──────────────────────────────────────────────
#  generate_portal_split tests
# ──────────────────────────────────────────────


def test_generate_portal_split_creates_docs_dir():
    """
    Verify that generate_portal_split creates a docs/ subdirectory
    containing individual subpages for each parsed file.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        files = ["doc_a.txt", "doc_b.txt", "doc_c.txt"]
        for fname in files:
            with open(os.path.join(source_dir, fname), "w", encoding="utf-8") as f:
                f.write(f"This is content of {fname}.")

        result = generate_portal_split(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )

        docs_dir = os.path.join(output_dir, "docs")
        assert os.path.isdir(docs_dir), "docs/ directory should be created in split mode"

        for fname in files:
            subpage_name = fname + ".html"
            subpage_path = os.path.join(docs_dir, subpage_name)
            assert os.path.isfile(subpage_path), f"Subpage not found for {fname}: expected {subpage_path}"

        assert result["doc_count"] == 3, f"Expected 3 docs, got {result['doc_count']}"
        assert result["index_file"] is not None
        assert os.path.isfile(result["index_file"])


def test_generate_portal_split_index_has_no_file_contents():
    """
    Verify that in split mode, the generated index.html does NOT contain
    embedded file content blocks (doc-block elements with file-content-*).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        test_file = os.path.join(source_dir, "sample.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("This content should only appear in the subpage, not in index.")

        result = generate_portal_split(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )

        assert result["index_file"] is not None
        with open(result["index_file"], encoding="utf-8") as f:
            index_content = f.read()

        import re

        file_content_ids = re.findall(r'id="file-content-\d+"', index_content)
        assert len(file_content_ids) == 0, "Index page should not contain file-content-* elements in split mode"

        assert "file-blocks-section" in index_content, "file-blocks-section div should exist"
        assert "file-blocks-header" in index_content, "file-blocks-header should exist"
        assert "split-mode-info" in index_content, "split-mode-info section should be present in split mode"


def test_generate_portal_split_subpages_have_correct_content():
    """
    Verify that each generated subpage under docs/ contains the correct
    file content, proper back-link to index, and correct file metadata.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        files_content = {
            "readme.txt": "This is the README file with important information.",
            "src/main.py": "def hello():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    hello()",
            "config/settings.json": '{"version": 1, "debug": true, "port": 8080}',
        }
        for rel_path, content in files_content.items():
            full_path = os.path.join(source_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        result = generate_portal_split(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )

        assert result["doc_count"] == 3
        docs_dir = os.path.join(output_dir, "docs")
        assert os.path.isdir(docs_dir)

        for rel_path, expected_content in files_content.items():
            subpage_name = rel_path.replace("\\", "/").replace("/", "_") + ".html"
            subpage_path = os.path.join(docs_dir, subpage_name)
            assert os.path.isfile(subpage_path), f"Subpage not found for {rel_path}: expected {subpage_path}"

            with open(subpage_path, encoding="utf-8") as f:
                subpage_content = f.read()

            if rel_path == "readme.txt":
                assert "This is the README file with important information." in subpage_content, (
                    "Subpage should contain original file content"
                )
            elif rel_path == "src/main.py":
                assert "def hello():" in subpage_content, "Subpage should contain Python function definition"
                assert "Hello, World!" in subpage_content, "Subpage should contain string from Python code"
            elif rel_path == "config/settings.json":
                assert "version" in subpage_content, "Subpage should contain JSON content"

            assert "index.html" in subpage_content or "../index.html" in subpage_content, (
                f"Subpage for {rel_path} should contain back-link to index"
            )

            assert os.path.basename(rel_path) in subpage_content, f"Subpage for {rel_path} should display the filename"


def test_generate_portal_split_search_count_in_tip():
    """
    Verify that the search result count mechanism works in split mode.
    The JS replaces the .tip text with 'Found X matching files' when searching.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        files = ["alpha.txt", "beta.txt", "gamma.txt"]
        for fname in files:
            with open(os.path.join(source_dir, fname), "w", encoding="utf-8") as f:
                f.write(f"Content of {fname} with unique data.")

        result = generate_portal_split(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )

        assert result["index_file"] is not None
        with open(result["index_file"], encoding="utf-8") as f:
            content = f.read()

        assert ".tip" in content or 'class="tip"' in content, (
            "The .tip element should exist for displaying search results count"
        )

        assert "matching files" in content or "\u5339\u914d\u6587\u4ef6" in content or "matching file" in content, (
            "JS should contain 'matching files' string for count display"
        )


def test_generate_portal_split_empty_folder():
    """
    Verify that generate_portal_split handles an empty folder gracefully.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        result = generate_portal_split(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )

        assert result["doc_count"] == 0
        assert result["total_chars"] == 0
        assert result["index_file"] is None
        assert result["folder_name"] == "source"

        docs_dir = os.path.join(output_dir, "docs")
        if os.path.isdir(docs_dir):
            subpage_files = os.listdir(docs_dir)
            assert len(subpage_files) == 0, f"No subpages should exist for empty folder, found: {subpage_files}"


def test_generate_portal_split_output_dir_exists():
    """
    Verify that generate_portal_split works when the output directory
    already exists.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)
        os.makedirs(output_dir)

        test_file = os.path.join(source_dir, "test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Test content for split mode.")

        result = generate_portal_split(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )

        assert result["doc_count"] == 1
        assert result["index_file"] is not None
        assert os.path.isfile(result["index_file"])

        docs_dir = os.path.join(output_dir, "docs")
        assert os.path.isdir(docs_dir)
        subpage_path = os.path.join(docs_dir, "test.txt.html")
        assert os.path.isfile(subpage_path), "Subpage should be created even when output dir already exists"


def test_generate_portal_split_tree_links_to_subpages():
    """
    Verify that the file tree in split mode contains links pointing to
    the docs/ subpages (href='docs/...') rather than inline anchors.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(source_dir)

        files = ["note.txt", "script.py"]
        for fname in files:
            with open(os.path.join(source_dir, fname), "w", encoding="utf-8") as f:
                f.write(f"Content of {fname}.")

        result = generate_portal_split(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
        )

        assert result["index_file"] is not None
        with open(result["index_file"], encoding="utf-8") as f:
            content = f.read()

        assert 'href="docs/' in content, "File tree links should point to docs/ subpages in split mode"

        assert 'onclick="jumpToFile' not in content, (
            "Split mode tree should not use jumpToFile (single-page mode function)"
        )


def test_generate_portal_split_skipped_behavior():
    """
    Verify that in split mode, skipped files appear in the file tree
    but do NOT have corresponding subpages in the docs/ directory.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = _create_folder_with_unsupported_file(tmpdir)
        output_dir = os.path.join(tmpdir, "output")

        result = generate_portal_split(
            folder_path=source_dir,
            output_dir=output_dir,
            show_progress=False,
            include_skipped=True,
        )

        docs_dir = os.path.join(output_dir, "docs")
        assert os.path.isdir(docs_dir), "docs/ directory should exist"

        readable_subpage = os.path.join(docs_dir, "readable.txt.html")
        assert os.path.isfile(readable_subpage), "Parsed file should have a subpage"

        notes_subpage = os.path.join(docs_dir, "notes.bin.html")
        assert not os.path.isfile(notes_subpage), "Skipped file should not have a subpage"

        assert result["index_file"] is not None
        with open(result["index_file"], encoding="utf-8") as f:
            content = f.read()
        assert "notes.bin" in content, "Skipped file should appear in file tree"

        assert result["doc_count"] == 1, f"Expected 1 parsed doc, got {result['doc_count']}"
        assert result["skipped"] >= 1, f"Expected at least 1 skipped, got {result['skipped']}"
