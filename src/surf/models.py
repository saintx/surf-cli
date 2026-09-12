# models.py
"""Immutable domain values for surf. No I/O."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType

HeadingText = NewType("HeadingText", str)
FileRef = NewType("FileRef", str)
HeadingLevel = NewType("HeadingLevel", int)
OutlineLevel = NewType("OutlineLevel", int)
LineIndex = NewType("LineIndex", int)
PageIndex = NewType("PageIndex", int)
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
LineCount = NewType("LineCount", int)
ByteCount = NewType("ByteCount", int)
PageCount = NewType("PageCount", int)

type DocumentLines = tuple[str, ...]
type PageText = str


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


class TexEnvironment(StrEnum):
    ABSTRACT = "abstract"


class FrontmatterReject(StrEnum):
    ANCHOR = "anchor"
    BLOCK_SCALAR = "block scalar"
    FLOW_MAP = "flow map"
    SYNTAX = "syntax"


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
class OutlineRecord:
    level: OutlineLevel
    title: HeadingText
    page_index: PageIndex | None
    top: float | None


@dataclass(frozen=True, slots=True)
class PdfDocument:
    outline: tuple[OutlineRecord, ...]
    pages: tuple[PageText, ...]


@dataclass(frozen=True, slots=True)
class PdfCatalog:
    outline: tuple[OutlineRecord, ...]
    page_count: PageCount
    byte_count: ByteCount


@dataclass(frozen=True, slots=True)
class OutlinePageSpan:
    """Dest-to-next-dest page range. start_page None means found but no dest."""

    level: OutlineLevel
    start_page: PageIndex | None
    end_page: PageIndex | None


@dataclass(frozen=True, slots=True)
class ParsedLink:
    file_ref: FileRef | None
    heading_path: HeadingPath | None


@dataclass(frozen=True, slots=True)
class FrontmatterSplit:
    frontmatter: DocumentLines | None
    body: DocumentLines


type YamlNode = str | int | bool | None | YamlMap | YamlSeq


@dataclass(frozen=True, slots=True)
class YamlMap:
    entries: tuple[tuple[str, YamlNode], ...]


@dataclass(frozen=True, slots=True)
class YamlSeq:
    items: tuple[YamlNode, ...]


@dataclass(frozen=True, slots=True)
class FrontmatterParse:
    root: YamlMap | None
    reject: FrontmatterReject | None


@dataclass(frozen=True, slots=True)
class WhereClause:
    key_path: tuple[str, ...]
    expected: str


@dataclass(frozen=True, slots=True)
class ExtractedSection:
    level: HeadingLevel
    lines: DocumentLines
    heading_line_count: HeadingLineCount


@dataclass(frozen=True, slots=True)
class ExtractedOutline:
    level: OutlineLevel
    pages: tuple[PageText, ...]


@dataclass(frozen=True, slots=True)
class CliOptions:
    file_refs: tuple[FileRef, ...]
    heading_path: HeadingPath | None
    list_headings: bool
    frontmatter_only: bool
    full: bool
    no_heading: bool
    level_filter: int | None
    output_ref: FileRef | None
    verbose: bool
    where_clauses: tuple[WhereClause, ...]


@dataclass(frozen=True, slots=True)
class CliSuccess:
    body: RenderedBody
    notices: tuple[ErrorMessage, ...] = ()


@dataclass(frozen=True, slots=True)
class CliFailure:
    message: ErrorMessage
    exit_code: ExitCode
    notices: tuple[ErrorMessage, ...] = ()
