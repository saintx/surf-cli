# logic.py
"""Pure heading parse and extract. No Path, no exists, no print."""

from __future__ import annotations

import re
from collections.abc import Sequence
from urllib.parse import unquote

from surf.models import (
    ExtractedSection,
    FileRef,
    FrontmatterSplit,
    HeadingLevel,
    HeadingPath,
    HeadingRecord,
    HeadingText,
    LineIndex,
    ParsedLink,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_TEX_LEVEL = {
    "part": 1,
    "chapter": 2,
    "section": 3,
    "subsection": 4,
    "subsubsection": 5,
    "paragraph": 6,
    "subparagraph": 7,
}
_TEX_COMMAND_RE = re.compile(
    r"^\s*\\("
    r"subparagraph|subsubsection|subsection|paragraph|chapter|section|part"
    r")(?![A-Za-z])"
)


def parse_heading_path(remainder: str) -> HeadingPath | None:
    segments = tuple(HeadingText(part.strip()) for part in remainder.split("#") if part.strip())
    if not segments:
        return None
    return HeadingPath(segments=segments)


def parse_link(text: str) -> ParsedLink:
    """Parse a wikilink, markdown link, or plain path#heading into a ParsedLink.

    The first `#` splits file ref from heading-path remainder.
    """
    m = re.match(r"^\[\[([^|\]]+?)(?:\|[^\]]+)?\]\]$", text)
    if m:
        inner = m.group(1)
        if "#" in inner:
            raw_path, remainder = inner.split("#", 1)
            file_ref = FileRef(raw_path.strip()) if raw_path.strip() else None
            return ParsedLink(file_ref=file_ref, heading_path=parse_heading_path(remainder))
        stripped = inner.strip()
        return ParsedLink(file_ref=FileRef(stripped) if stripped else None, heading_path=None)

    m = re.match(r"^\[([^\]]*)\]\((.+?)\)$", text)
    if m:
        raw = unquote(m.group(2))
        if "#" in raw:
            raw_path, remainder = raw.split("#", 1)
            file_ref = FileRef(raw_path.strip()) if raw_path.strip() else None
            return ParsedLink(file_ref=file_ref, heading_path=parse_heading_path(remainder))
        stripped = raw.strip()
        return ParsedLink(file_ref=FileRef(stripped) if stripped else None, heading_path=None)

    if "#" in text:
        raw_path, remainder = text.split("#", 1)
        file_ref = FileRef(raw_path.strip()) if raw_path.strip() else None
        return ParsedLink(file_ref=file_ref, heading_path=parse_heading_path(remainder))

    stripped = text.strip()
    return ParsedLink(file_ref=FileRef(stripped) if stripped else None, heading_path=None)


def parse_headings(lines: Sequence[str]) -> tuple[HeadingRecord, ...]:
    records: list[HeadingRecord] = []
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        if m:
            records.append(
                HeadingRecord(
                    level=HeadingLevel(len(m.group(1))),
                    line_index=LineIndex(i),
                    text=HeadingText(m.group(2).strip()),
                )
            )
    return tuple(records)


def _delimited_span_end(text: str, start: int, opener: str, closer: str) -> int | None:
    if start >= len(text) or text[start] != opener:
        return None
    depth = 0
    for i in range(start, len(text)):
        char = text[i]
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def _extend_until_closed(
    lines: Sequence[str],
    start_line: int,
    rest: str,
    pos: int,
    opener: str,
    closer: str,
) -> tuple[str, int, int] | None:
    end = _delimited_span_end(rest, pos, opener, closer)
    if end is not None:
        return rest, end, start_line
    for j in range(start_line + 1, len(lines)):
        rest = rest + "\n" + lines[j]
        end = _delimited_span_end(rest, pos, opener, closer)
        if end is not None:
            return rest, end, j
    return None


def _parse_tex_heading_at(
    lines: Sequence[str], line_index: int
) -> tuple[HeadingRecord, int] | None:
    line = lines[line_index]
    if line_index == 0:
        line = line.lstrip("\ufeff")
    m = _TEX_COMMAND_RE.match(line)
    if m is None:
        return None
    rest = line[m.end() :]
    pos = 0
    if pos < len(rest) and rest[pos] == "*":
        pos += 1
    if pos < len(rest) and rest[pos] == "[":
        extended = _extend_until_closed(lines, line_index, rest, pos, "[", "]")
        if extended is None:
            return None
        rest, pos, _ = extended
    if pos >= len(rest) or rest[pos] != "{":
        return None
    extended = _extend_until_closed(lines, line_index, rest, pos, "{", "}")
    if extended is None:
        return None
    rest, brace_end, last_line = extended
    title = re.sub(r"\s+", " ", rest[pos + 1 : brace_end - 1]).strip()
    if not title:
        return None
    return (
        HeadingRecord(
            level=HeadingLevel(_TEX_LEVEL[m.group(1)]),
            line_index=LineIndex(line_index),
            text=HeadingText(title),
        ),
        last_line,
    )


def parse_tex_headings(lines: Sequence[str]) -> tuple[HeadingRecord, ...]:
    records: list[HeadingRecord] = []
    i = 0
    while i < len(lines):
        parsed = _parse_tex_heading_at(lines, i)
        if parsed is None:
            i += 1
            continue
        record, consumed_through = parsed
        records.append(record)
        i = consumed_through + 1
    return tuple(records)


def split_frontmatter(lines: Sequence[str]) -> FrontmatterSplit:
    body = tuple(lines)
    if not body or body[0].rstrip() != "---":
        return FrontmatterSplit(frontmatter=None, body=body)
    for i in range(1, len(body)):
        if body[i].rstrip() == "---":
            return FrontmatterSplit(frontmatter=body[: i + 1], body=body[i + 1 :])
    return FrontmatterSplit(frontmatter=None, body=body)


def extract_section(
    lines: Sequence[str],
    heading_path: HeadingPath,
    *,
    level_filter: HeadingLevel | None = None,
    headings: tuple[HeadingRecord, ...] | None = None,
) -> ExtractedSection | None:
    """Extract by heading path. Same containment walk as the pre-split module."""
    if headings is None:
        headings = parse_headings(lines)
    segments = heading_path.segments
    if not segments:
        return None

    def section_end(start_idx: LineIndex, start_level: HeadingLevel) -> int:
        for record in headings:
            if record.line_index > start_idx and record.level <= start_level:
                return int(record.line_index)
        return len(lines)

    bound_start = -1
    bound_end = len(lines)
    prev_level = HeadingLevel(0)
    match_idx: LineIndex | None = None
    match_level: HeadingLevel | None = None

    for i, segment in enumerate(segments):
        target = str(segment).lower()
        is_last = i == len(segments) - 1
        found: HeadingRecord | None = None
        for record in headings:
            if record.line_index <= bound_start or record.line_index >= bound_end:
                continue
            if i > 0 and record.level <= prev_level:
                continue
            if str(record.text).lower().strip() != target:
                continue
            if is_last and level_filter is not None and record.level != level_filter:
                continue
            found = record
            break
        if found is None:
            return None
        match_level = found.level
        match_idx = found.line_index
        bound_start = int(match_idx)
        prev_level = match_level
        bound_end = section_end(match_idx, match_level)

    if match_idx is None or match_level is None:
        return None
    return ExtractedSection(level=match_level, lines=tuple(lines[int(match_idx) : bound_end]))


def format_heading_list(
    lines: Sequence[str],
    *,
    headings: tuple[HeadingRecord, ...] | None = None,
) -> str:
    records = parse_headings(lines) if headings is None else headings
    out: list[str] = []
    for record in records:
        indent = "  " * (int(record.level) - 1)
        out.append(f"{indent}- {record.text}")
    return "\n".join(out)


def format_file_index(
    split: FrontmatterSplit,
    *,
    headings: tuple[HeadingRecord, ...] | None = None,
) -> str:
    frontmatter = "\n".join(split.frontmatter) if split.frontmatter is not None else ""
    heading_list = format_heading_list(split.body, headings=headings)
    if frontmatter and heading_list:
        return f"{frontmatter}\n\n{heading_list}"
    return frontmatter or heading_list
