# logic.py
"""Pure heading parse and extract. No Path, no exists, no print."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from urllib.parse import unquote

from surf.models import (
    CharOffset,
    CliTarget,
    ClosedSpan,
    Delimiter,
    ExtractedSection,
    FileRef,
    FrontmatterSplit,
    HeadingLevel,
    HeadingLineCount,
    HeadingPath,
    HeadingPathRemainder,
    HeadingRecord,
    HeadingText,
    LineIndex,
    ParsedLink,
    RenderedBody,
    ScanBuffer,
    TexCommand,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_TEX_LEVEL: Mapping[TexCommand, HeadingLevel] = {
    TexCommand.PART: HeadingLevel(1),
    TexCommand.CHAPTER: HeadingLevel(2),
    TexCommand.SECTION: HeadingLevel(3),
    TexCommand.SUBSECTION: HeadingLevel(4),
    TexCommand.SUBSUBSECTION: HeadingLevel(5),
    TexCommand.PARAGRAPH: HeadingLevel(6),
    TexCommand.SUBPARAGRAPH: HeadingLevel(7),
}
_TEX_COMMAND_BY_WORD: Mapping[str, TexCommand] = {command.value: command for command in TexCommand}
_TEX_CONTROL_WORD_RE = re.compile(r"^\s*\\([A-Za-z]+)")


def parse_heading_path(remainder: HeadingPathRemainder) -> HeadingPath | None:
    segments = tuple(HeadingText(part.strip()) for part in remainder.split("#") if part.strip())
    if not segments:
        return None
    return HeadingPath(segments=segments)


def parse_link(target: CliTarget) -> ParsedLink:
    """Parse a wikilink, markdown link, or plain path#heading into a ParsedLink.

    The first `#` splits file ref from heading-path remainder.
    """
    m = re.match(r"^\[\[([^|\]]+?)(?:\|[^\]]+)?\]\]$", target)
    if m:
        inner = m.group(1)
        if "#" in inner:
            raw_path, remainder = inner.split("#", 1)
            file_ref = FileRef(raw_path.strip()) if raw_path.strip() else None
            return ParsedLink(
                file_ref=file_ref,
                heading_path=parse_heading_path(HeadingPathRemainder(remainder)),
            )
        stripped = inner.strip()
        return ParsedLink(file_ref=FileRef(stripped) if stripped else None, heading_path=None)

    m = re.match(r"^\[([^\]]*)\]\((.+?)\)$", target)
    if m:
        raw = unquote(m.group(2))
        if "#" in raw:
            raw_path, remainder = raw.split("#", 1)
            file_ref = FileRef(raw_path.strip()) if raw_path.strip() else None
            return ParsedLink(
                file_ref=file_ref,
                heading_path=parse_heading_path(HeadingPathRemainder(remainder)),
            )
        stripped = raw.strip()
        return ParsedLink(file_ref=FileRef(stripped) if stripped else None, heading_path=None)

    if "#" in target:
        raw_path, remainder = target.split("#", 1)
        file_ref = FileRef(raw_path.strip()) if raw_path.strip() else None
        return ParsedLink(
            file_ref=file_ref,
            heading_path=parse_heading_path(HeadingPathRemainder(remainder)),
        )

    stripped = target.strip()
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
                    title_end_line=LineIndex(i),
                    text=HeadingText(m.group(2).strip()),
                )
            )
    return tuple(records)


def _delimited_span_end(
    buffer: ScanBuffer,
    start: CharOffset,
    opener: Delimiter,
    closer: Delimiter,
) -> CharOffset | None:
    if start >= len(buffer) or buffer[start] != opener:
        return None
    depth = 0
    for i in range(start, len(buffer)):
        char = buffer[i]
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return CharOffset(i + 1)
    return None


def _skip_horizontal(buffer: ScanBuffer, pos: CharOffset) -> CharOffset:
    i = int(pos)
    while i < len(buffer) and buffer[i] in " \t":
        i += 1
    return CharOffset(i)


def _extend_until_closed(
    lines: Sequence[str],
    start_line: LineIndex,
    rest: ScanBuffer,
    pos: CharOffset,
    opener: Delimiter,
    closer: Delimiter,
) -> ClosedSpan | None:
    end = _delimited_span_end(rest, pos, opener, closer)
    if end is not None:
        return ClosedSpan(buffer=rest, end=end, last_line=start_line)
    for j in range(start_line + 1, len(lines)):
        rest = ScanBuffer(rest + "\n" + lines[j])
        end = _delimited_span_end(rest, pos, opener, closer)
        if end is not None:
            return ClosedSpan(buffer=rest, end=end, last_line=LineIndex(j))
    return None


def _parse_tex_heading_at(
    lines: Sequence[str], line_index: LineIndex
) -> tuple[HeadingRecord, LineIndex] | None:
    line = lines[line_index]
    if line_index == 0:
        line = line.lstrip("\ufeff")
    m = _TEX_CONTROL_WORD_RE.match(line)
    if m is None:
        return None
    command = _TEX_COMMAND_BY_WORD.get(m.group(1))
    if command is None:
        return None
    rest = ScanBuffer(line[m.end() :])
    pos = CharOffset(0)
    if pos < len(rest) and rest[pos] == "*":
        pos = CharOffset(pos + 1)
    pos = _skip_horizontal(rest, pos)
    if pos < len(rest) and rest[pos] == "[":
        extended = _extend_until_closed(
            lines, line_index, rest, pos, Delimiter("["), Delimiter("]")
        )
        if extended is None:
            return None
        rest = extended.buffer
        pos = _skip_horizontal(extended.buffer, extended.end)
    if pos >= len(rest) or rest[pos] != "{":
        return None
    extended = _extend_until_closed(lines, line_index, rest, pos, Delimiter("{"), Delimiter("}"))
    if extended is None:
        return None
    rest = extended.buffer
    brace_end = extended.end
    title = re.sub(r"\s+", " ", rest[pos + 1 : brace_end - 1]).strip()
    if not title:
        return None
    return (
        HeadingRecord(
            level=_TEX_LEVEL[command],
            line_index=line_index,
            title_end_line=extended.last_line,
            text=HeadingText(title),
        ),
        extended.last_line,
    )


def parse_tex_headings(lines: Sequence[str]) -> tuple[HeadingRecord, ...]:
    records: list[HeadingRecord] = []
    i = LineIndex(0)
    while i < len(lines):
        parsed = _parse_tex_heading_at(lines, i)
        if parsed is None:
            i = LineIndex(i + 1)
            continue
        record, consumed_through = parsed
        records.append(record)
        i = LineIndex(consumed_through + 1)
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
    match_title_end: LineIndex | None = None

    for i, segment in enumerate(segments):
        needle = str(segment).lower()
        is_last = i == len(segments) - 1
        found: HeadingRecord | None = None
        for record in headings:
            if record.line_index <= bound_start or record.line_index >= bound_end:
                continue
            if i > 0 and record.level <= prev_level:
                continue
            if str(record.text).lower().strip() != needle:
                continue
            if is_last and level_filter is not None and record.level != level_filter:
                continue
            found = record
            break
        if found is None:
            return None
        match_level = found.level
        match_idx = found.line_index
        match_title_end = found.title_end_line
        bound_start = int(match_idx)
        prev_level = match_level
        bound_end = section_end(match_idx, match_level)

    if match_idx is None or match_level is None or match_title_end is None:
        return None
    return ExtractedSection(
        level=match_level,
        lines=tuple(lines[int(match_idx) : bound_end]),
        heading_line_count=HeadingLineCount(int(match_title_end) - int(match_idx) + 1),
    )


def format_heading_list(
    lines: Sequence[str],
    *,
    headings: tuple[HeadingRecord, ...] | None = None,
    level_filter: HeadingLevel | None = None,
) -> RenderedBody:
    records = parse_headings(lines) if headings is None else headings
    if level_filter is not None:
        records = tuple(record for record in records if record.level == level_filter)
    out: list[str] = []
    for record in records:
        indent = "  " * (int(record.level) - 1)
        out.append(f"{indent}- {record.text}")
    return RenderedBody("\n".join(out))


def format_file_index(
    split: FrontmatterSplit,
    *,
    headings: tuple[HeadingRecord, ...] | None = None,
    level_filter: HeadingLevel | None = None,
) -> RenderedBody:
    frontmatter = "\n".join(split.frontmatter) if split.frontmatter is not None else ""
    heading_list = format_heading_list(split.body, headings=headings, level_filter=level_filter)
    if frontmatter and heading_list:
        return RenderedBody(f"{frontmatter}\n\n{heading_list}")
    return RenderedBody(frontmatter or heading_list)
