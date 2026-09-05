# test_adapters.py
"""Filesystem adapter tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from pypdf import PageObject, PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    IndirectObject,
    NameObject,
    TreeObject,
)

from surf.adapters import (
    PdfIngestError,
    document_byte_count,
    read_document,
    read_pdf,
    resolve_file,
    resolve_tex_include,
    write_output,
)
from surf.models import FileRef, RenderedBody, TexIncludeRelPath

type OutlineSpec = tuple[str, int, Sequence["OutlineSpec"]]


def _page_with_text(text: str) -> PageObject:
    page = PageObject.create_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
        }
    )
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 24 Tf 72 700 Td ({escaped}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = stream
    return page


def write_outline_pdf(
    path: Path,
    *,
    page_count: int,
    outline: Sequence[OutlineSpec] = (),
    page_texts: Sequence[str] | None = None,
    password: str | None = None,
) -> Path:
    writer = PdfWriter()
    for i in range(page_count):
        text = page_texts[i] if page_texts is not None and i < len(page_texts) else ""
        if text:
            writer.add_page(_page_with_text(text))
        else:
            writer.add_blank_page(width=612, height=792)

    def add_items(
        items: Sequence[OutlineSpec],
        parent: TreeObject | IndirectObject | None = None,
    ) -> None:
        for title, page_index, children in items:
            node = writer.add_outline_item(title, page_index, parent=parent)
            if children:
                add_items(children, parent=node)

    add_items(outline)
    if password is not None:
        writer.encrypt(password)
    writer.write(path)
    return path


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


def test_resolve_tex_include_existing_and_missing(tmp_path: Path) -> None:
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    target = chapters / "1_introduction.tex"
    target.write_text("\\section{Introduction}\n")
    found = resolve_tex_include(tmp_path, TexIncludeRelPath("chapters/1_introduction.tex"))
    assert found == target
    assert resolve_tex_include(tmp_path, TexIncludeRelPath("chapters/missing.tex")) is None


def test_document_byte_count_matches_stat(tmp_path: Path) -> None:
    path = tmp_path / "a.tex"
    path.write_text("\\newcommand{\\foo}{bar}\n")
    assert int(document_byte_count(path)) == path.stat().st_size


def test_write_output_file(tmp_path: Path) -> None:
    dest = tmp_path / "out.md"
    write_output(RenderedBody("- Introduction"), FileRef(str(dest)))
    assert "- Introduction" in dest.read_text()


def test_read_pdf_nested_outline(tmp_path: Path) -> None:
    path = tmp_path / "nested.pdf"
    write_outline_pdf(
        path,
        page_count=2,
        outline=(("Parent", 0, (("Child", 1, ()),)),),
    )
    document = read_pdf(path)
    assert len(document.outline) == 2
    parent, child = document.outline
    assert str(parent.title) == "Parent"
    assert int(parent.level) == 1
    assert parent.page_index is not None
    assert int(parent.page_index) == 0
    assert str(child.title) == "Child"
    assert int(child.level) == 2
    assert child.page_index is not None
    assert int(child.page_index) == 1
    assert len(document.pages) == 2


def test_read_pdf_empty_outline(tmp_path: Path) -> None:
    path = tmp_path / "empty.pdf"
    write_outline_pdf(path, page_count=1)
    document = read_pdf(path)
    assert document.outline == ()
    assert len(document.pages) == 1
    assert document.pages[0] == ""


def test_read_pdf_garbage_raises(tmp_path: Path) -> None:
    path = tmp_path / "garbage.pdf"
    path.write_bytes(b"not a pdf")
    with pytest.raises(PdfIngestError):
        read_pdf(path)


def test_read_pdf_encrypted_raises(tmp_path: Path) -> None:
    path = tmp_path / "secret.pdf"
    write_outline_pdf(
        path,
        page_count=1,
        outline=(("Hidden", 0, ()),),
        password="secret",
    )
    with pytest.raises(PdfIngestError):
        read_pdf(path)
