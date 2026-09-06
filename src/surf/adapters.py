# adapters.py
"""Razor-thin filesystem I/O. Models only."""

from __future__ import annotations

from pathlib import Path

from surf.models import DocumentLines, FileRef, RenderedBody


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


def write_output(text: RenderedBody, dest: FileRef | None) -> None:
    payload = text if text.endswith("\n") else text + "\n"
    if dest is None:
        print(text)
        return
    Path(str(dest)).write_text(payload, encoding="utf-8")
