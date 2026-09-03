# models.py
"""Immutable domain values for surf. No I/O."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

HeadingText = NewType("HeadingText", str)
FileRef = NewType("FileRef", str)
HeadingLevel = NewType("HeadingLevel", int)
LineIndex = NewType("LineIndex", int)

type DocumentLines = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HeadingPath:
    segments: tuple[HeadingText, ...]


@dataclass(frozen=True, slots=True)
class HeadingRecord:
    level: HeadingLevel
    line_index: LineIndex
    text: HeadingText


@dataclass(frozen=True, slots=True)
class ParsedLink:
    file_ref: FileRef | None
    heading_path: HeadingPath | None


@dataclass(frozen=True, slots=True)
class FrontmatterSplit:
    frontmatter: DocumentLines | None
    body: DocumentLines


@dataclass(frozen=True, slots=True)
class ExtractedSection:
    level: HeadingLevel
    lines: DocumentLines


@dataclass(frozen=True, slots=True)
class CliOptions:
    file_ref: FileRef | None
    heading_path: HeadingPath | None
    list_headings: bool
    frontmatter_only: bool
    full: bool
    no_heading: bool
    level_filter: HeadingLevel | None
    output_ref: FileRef | None


@dataclass(frozen=True, slots=True)
class CliSuccess:
    body: str


@dataclass(frozen=True, slots=True)
class CliFailure:
    message: str
    exit_code: int
