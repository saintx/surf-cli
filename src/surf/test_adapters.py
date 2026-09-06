# test_adapters.py
"""Filesystem adapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from surf.adapters import read_document, resolve_file, write_output
from surf.models import FileRef, RenderedBody


def test_resolve_existing(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text("# Hi\n")
    assert resolve_file(FileRef(str(path))) == path


def test_resolve_auto_md(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("# Hi\n")
    stem = path.with_suffix("")
    assert resolve_file(FileRef(str(stem))) == path


def test_resolve_missing() -> None:
    with pytest.raises(FileNotFoundError):
        resolve_file(FileRef("/nonexistent/path/file.md"))


def test_read_document(tmp_path: Path) -> None:
    path = tmp_path / "a.md"
    path.write_text("# A\n\nbody\n")
    assert read_document(path)[0] == "# A"


def test_read_document_strips_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "bom.tex"
    path.write_bytes(b"\xef\xbb\xbf\\section{Related Work}\n")
    assert read_document(path)[0] == r"\section{Related Work}"


def test_write_output_file(tmp_path: Path) -> None:
    dest = tmp_path / "out.md"
    write_output(RenderedBody("- Introduction"), FileRef(str(dest)))
    assert "- Introduction" in dest.read_text()
