# adapters.py
"""Razor-thin filesystem I/O. Models only."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import cast

from pypdf import PdfReader
from pypdf.generic import Destination

from surf.models import (
    ByteCount,
    DocumentLines,
    FileRef,
    HeadingText,
    OutlineLevel,
    OutlineRecord,
    PageIndex,
    PageText,
    PdfDocument,
    RenderedBody,
    TexIncludeRelPath,
)

type PypdfOutlineItem = Destination | list[PypdfOutlineItem]


class PdfIngestError(Exception):
    """PDF bytes could not be read as a document outline."""


def resolve_file(file_ref: FileRef) -> Path:
    path = Path(str(file_ref)).expanduser()
    if path.exists():
        return path
    if not path.suffix:
        with_md = path.with_suffix(".md")
        if with_md.exists():
            return with_md
    raise FileNotFoundError(f"File not found: {file_ref}")


def read_document(path: Path) -> DocumentLines:
    return tuple(path.read_text(encoding="utf-8-sig").splitlines())


def document_byte_count(path: Path) -> ByteCount:
    return ByteCount(path.stat().st_size)


def resolve_tex_include(base_dir: Path, rel: TexIncludeRelPath) -> Path | None:
    candidate = base_dir / str(rel)
    if candidate.is_file():
        return candidate
    return None


def write_output(text: RenderedBody, dest: FileRef | None) -> None:
    payload = text if text.endswith("\n") else text + "\n"
    if dest is None:
        print(text)
        return
    Path(str(dest)).write_text(payload, encoding="utf-8")


def _optional_float(value: object) -> float | None:
    match value:
        case None:
            return None
        case int() | float() | str():
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        case _:
            try:
                return float(str(value))
            except (TypeError, ValueError):
                return None


def _outline_record(reader: PdfReader, item: Destination, *, level: OutlineLevel) -> OutlineRecord:
    title = item.title
    page_number = reader.get_destination_page_number(item)
    page_index = PageIndex(page_number) if page_number is not None else None
    return OutlineRecord(
        level=level,
        title=HeadingText("" if title is None else str(title)),
        page_index=page_index,
        top=_optional_float(item.top),
    )


def _walk_outline(
    reader: PdfReader,
    items: Iterable[PypdfOutlineItem],
    *,
    level: OutlineLevel,
) -> Iterator[OutlineRecord]:
    for item in items:
        match item:
            case list():
                nested = cast(list[PypdfOutlineItem], item)
                yield from _walk_outline(reader, nested, level=OutlineLevel(int(level) + 1))
            case Destination():
                yield _outline_record(reader, item, level=level)


def read_pdf(path: Path) -> PdfDocument:
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise PdfIngestError(f"could not read PDF: {path}")
        outline_root = cast(Iterable[PypdfOutlineItem], reader.outline)
        outline = tuple(_walk_outline(reader, outline_root, level=OutlineLevel(1)))
        pages: tuple[PageText, ...] = tuple((page.extract_text() or "") for page in reader.pages)
        return PdfDocument(outline=outline, pages=pages)
    except PdfIngestError:
        raise
    except Exception as exc:
        raise PdfIngestError(f"could not read PDF: {path}") from exc
