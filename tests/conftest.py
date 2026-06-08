"""
Shared pytest fixtures for FolderKnowledgeSiteGeneratorForAI tests.
"""

import os
import tempfile

import pytest


@pytest.fixture(scope="function")
def sample_text_file():
    """Create a temporary text file for parser tests."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("Hello world")
        fname = f.name
    yield fname
    if os.path.exists(fname):
        os.unlink(fname)


@pytest.fixture(scope="function")
def sample_pdf_file():
    """Create a temporary minimal PDF for parser tests."""
    # Minimal valid PDF content (no external dependency needed to create it)
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>/Contents 4 0 R>>endobj\n"
        b"4 0 obj<</Length 44>>stream\n"
        b"BT /F1 12 Tf 100 700 Td (Hello PDF) Tj ET\n"
        b"endstream\n"
        b"endobj\n"
        b"xref\n"
        b"0 5\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000266 00000 n \n"
        b"trailer<</Size 5/Root 1 0 R>>\n"
        b"startxref\n"
        b"375\n"
        b"%%%%EOF"
    )
    with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        fname = f.name
    yield fname
    if os.path.exists(fname):
        os.unlink(fname)
