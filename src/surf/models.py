# models.py
"""Immutable domain values for surf. No I/O."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType

HeadingText = NewType("HeadingText", str)
FileRef = NewType("FileRef", str)
HeadingLevel = NewType("HeadingLevel", int)
LineIndex = NewType("LineIndex", int)
ScanBuffer = NewType("ScanBuffer", str)
CharOffset = NewType("CharOffset", int)
Delimiter = NewType("Delimiter", str)
HeadingLineCount = NewType("HeadingLineCount", int)
CliTarget = NewType("CliTarget", str)
HeadingPathRemainder = NewType("HeadingPathRemainder", str)
RenderedBody = NewType("RenderedBody", str)
ErrorMessage = NewType("ErrorMessage", str)
ExitCode = NewType("ExitCode", int)
TexIncludeRelPath = NewType("TexIncludeRelPath", str)

type DocumentLines = tuple[str, ...]


class TexCommand(StrEnum):
    PART = "part"
    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"
    SUBSUBSECTION = "subsubsection"
    PARAGRAPH = "paragraph"
    SUBPARAGRAPH = "subparagraph"


class TexIncludeCommand(StrEnum):
    INPUT = "input"
    INCLUDE = "include"


@dataclass(frozen=True, slots=True)
class HeadingPath:
    segments: tuple[HeadingText, ...]


@dataclass(frozen=True, slots=True)
class HeadingRecord:
    level: HeadingLevel
    line_index: LineIndex
    title_end_line: LineIndex
    text: HeadingText


@dataclass(frozen=True, slots=True)
class ClosedSpan:
    buffer: ScanBuffer
    end: CharOffset
    last_line: LineIndex


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
    heading_line_count: HeadingLineCount


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
    body: RenderedBody


@dataclass(frozen=True, slots=True)
class CliFailure:
    message: ErrorMessage
    exit_code: ExitCode
