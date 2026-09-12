# logic.py
"""Pure heading parse and extract. No Path, no exists, no print."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from urllib.parse import unquote

from surf.models import (
    ByteCount,
    CharOffset,
    CliTarget,
    ClosedSpan,
    Delimiter,
    DocumentLines,
    ErrorMessage,
    ExtractedOutline,
    ExtractedSection,
    FileRef,
    FrontmatterParse,
    FrontmatterReject,
    FrontmatterSplit,
    HeadingLevel,
    HeadingLineCount,
    HeadingPath,
    HeadingPathRemainder,
    HeadingRecord,
    HeadingText,
    LineCount,
    LineIndex,
    OutlineLevel,
    OutlinePageSpan,
    OutlineRecord,
    PageCount,
    PageIndex,
    ParsedLink,
    PdfDocument,
    RenderedBody,
    ScanBuffer,
    TexCommand,
    TexEnvironment,
    TexIncludeCommand,
    TexIncludeRelPath,
    WhereClause,
    YamlMap,
    YamlNode,
    YamlSeq,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*$")
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
_TEX_INCLUDE_BY_WORD: Mapping[str, TexIncludeCommand] = {
    command.value: command for command in TexIncludeCommand
}
_TEX_CONTROL_WORD_RE = re.compile(r"^\s*\\([A-Za-z]+)")
_TEX_UNBRACED_INCLUDE_STOP = frozenset(" \t%")


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


def _fence_open(line: str) -> str | None:
    """Return the fence string when line opens a fenced code block, else None.

    CommonMark: up to three spaces of indent, then three or more backticks or
    tildes. A backtick fence's info string may not contain a backtick.
    """
    m = _FENCE_OPEN_RE.match(line)
    if m is None:
        return None
    fence, info = m.group(1), m.group(2)
    if fence[0] == "`" and "`" in info:
        return None
    return fence


def _fence_closes(line: str, open_fence: str) -> bool:
    """A closing fence uses the same character and is at least as long."""
    m = _FENCE_CLOSE_RE.match(line)
    if m is None:
        return False
    fence = m.group(1)
    return fence[0] == open_fence[0] and len(fence) >= len(open_fence)


def parse_headings(lines: Sequence[str]) -> tuple[HeadingRecord, ...]:
    """ATX headings outside fenced code blocks. A `#` line inside a fence is code."""
    records: list[HeadingRecord] = []
    open_fence: str | None = None
    for i, line in enumerate(lines):
        if open_fence is not None:
            if _fence_closes(line, open_fence):
                open_fence = None
            continue
        open_fence = _fence_open(line)
        if open_fence is not None:
            continue
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
        return _parse_tex_abstract_at(line_index, line, m)
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


def _parse_tex_abstract_at(
    line_index: LineIndex,
    line: str,
    matched: re.Match[str],
) -> tuple[HeadingRecord, LineIndex] | None:
    if matched.group(1) != "begin":
        return None
    rest = ScanBuffer(line[matched.end() :])
    pos = _skip_horizontal(rest, CharOffset(0))
    if pos >= len(rest) or rest[pos] != "{":
        return None
    end = _delimited_span_end(rest, pos, Delimiter("{"), Delimiter("}"))
    if end is None:
        return None
    if rest[pos + 1 : end - 1].strip() != TexEnvironment.ABSTRACT:
        return None
    return (
        HeadingRecord(
            level=_TEX_LEVEL[TexCommand.SECTION],
            line_index=line_index,
            title_end_line=line_index,
            text=HeadingText(TexEnvironment.ABSTRACT),
        ),
        line_index,
    )


def _normalized_tex_include(raw: str) -> TexIncludeRelPath | None:
    path = raw.strip()
    if not path or path.startswith(("/", "~", "|")):
        return None
    if any(char in path for char in "\\{}|#"):
        return None
    segments = path.split("/")
    if any(segment in ("", "..") for segment in segments):
        return None
    name = segments[-1]
    if "." in name:
        suffix = name.rsplit(".", 1)[1]
        if suffix.lower() != "tex":
            return None
    else:
        path = f"{path}.tex"
    return TexIncludeRelPath(path)


def tex_include_path(line: str) -> TexIncludeRelPath | None:
    """Return a static \\input/\\include relative path, or None.

    Comments, graphics, shell pipes, macros, absolute paths, and non-.tex
    suffixes are not includes. A missing suffix becomes .tex.
    """
    if line.lstrip(" \t").startswith("%"):
        return None
    matched = _TEX_CONTROL_WORD_RE.match(line)
    if matched is None:
        return None
    command = _TEX_INCLUDE_BY_WORD.get(matched.group(1))
    if command is None:
        return None
    rest = ScanBuffer(line[matched.end() :])
    pos = _skip_horizontal(rest, CharOffset(0))
    if pos < len(rest) and rest[pos] == "{":
        end = _delimited_span_end(rest, pos, Delimiter("{"), Delimiter("}"))
        if end is None:
            return None
        return _normalized_tex_include(rest[pos + 1 : end - 1])
    if command is TexIncludeCommand.INCLUDE:
        return None
    if pos >= len(rest):
        return None
    stop = int(pos)
    while stop < len(rest) and rest[stop] not in _TEX_UNBRACED_INCLUDE_STOP:
        stop += 1
    return _normalized_tex_include(rest[pos:stop])


def relative_heading_levels(
    headings: tuple[HeadingRecord, ...],
) -> tuple[HeadingRecord, ...]:
    """Shift ranks so the shallowest heading in the file is level 1.

    LaTeX command ranks stay on the 1-7 map (part=1 ... subparagraph=7).
    An article whose top command is \\section then lists at --level 1, matching
    markdown's top-of-tree numbering. Gaps are preserved.
    """
    if not headings:
        return headings
    origin = min(int(record.level) for record in headings)
    if origin <= 1:
        return headings
    delta = origin - 1
    return tuple(
        HeadingRecord(
            level=HeadingLevel(int(record.level) - delta),
            line_index=record.line_index,
            title_end_line=record.title_end_line,
            text=record.text,
        )
        for record in headings
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
    return relative_heading_levels(tuple(records))


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
    """Extract by heading path. Same containment walk as the pre-split module.

    level_filter is an exact rank, so same-named headings at different
    levels stay distinguishable.
    """
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


def match_outline_span(
    outline: Sequence[OutlineRecord],
    heading_path: HeadingPath,
    *,
    level_filter: OutlineLevel | None = None,
) -> OutlinePageSpan | None:
    """Dest-to-next-dest page bounds. Does not read page text."""
    segments = heading_path.segments
    if not segments:
        return None

    def containment_end(start_idx: int, start_level: OutlineLevel) -> int:
        for j in range(start_idx + 1, len(outline)):
            if outline[j].level <= start_level:
                return j
        return len(outline)

    def next_dest_page(after_idx: int) -> PageIndex | None:
        for j in range(after_idx + 1, len(outline)):
            page = outline[j].page_index
            if page is not None:
                return page
        return None

    bound_start = -1
    bound_end = len(outline)
    prev_level = OutlineLevel(0)
    match_idx: int | None = None
    match_level: OutlineLevel | None = None

    for i, segment in enumerate(segments):
        target = str(segment).lower()
        is_last = i == len(segments) - 1
        found: OutlineRecord | None = None
        found_idx: int | None = None
        for j, record in enumerate(outline):
            if j <= bound_start or j >= bound_end:
                continue
            if i > 0 and record.level <= prev_level:
                continue
            if str(record.title).lower().strip() != target:
                continue
            if is_last and level_filter is not None and record.level != level_filter:
                continue
            found = record
            found_idx = j
            break
        if found is None or found_idx is None:
            return None
        match_level = found.level
        match_idx = found_idx
        bound_start = match_idx
        prev_level = match_level
        bound_end = containment_end(match_idx, match_level)

    if match_idx is None or match_level is None:
        return None
    return OutlinePageSpan(
        level=match_level,
        start_page=outline[match_idx].page_index,
        end_page=next_dest_page(match_idx),
    )


def exclusive_page_end(span: OutlinePageSpan) -> PageIndex | None:
    """Half-open end page. Same-page next dest includes the dest page."""
    if span.start_page is None:
        return None
    if span.end_page is None:
        return None
    if int(span.end_page) <= int(span.start_page):
        return PageIndex(int(span.start_page) + 1)
    return span.end_page


def extract_outline_section(
    document: PdfDocument,
    heading_path: HeadingPath,
    *,
    level_filter: OutlineLevel | None = None,
) -> ExtractedOutline | None:
    """Slice in-memory page text for a dest-to-next-dest span."""
    span = match_outline_span(document.outline, heading_path, level_filter=level_filter)
    if span is None:
        return None
    if span.start_page is None:
        return ExtractedOutline(level=span.level, pages=())
    start = int(span.start_page)
    end = exclusive_page_end(span)
    if end is None:
        page_slice = document.pages[start:]
    else:
        page_slice = document.pages[start : int(end)]
    return ExtractedOutline(level=span.level, pages=tuple(page_slice))


def format_empty_index(*, line_count: LineCount, byte_count: ByteCount) -> RenderedBody:
    return RenderedBody(f"no structural index\nlines: {int(line_count)}\nbytes: {int(byte_count)}")


def format_empty_pdf_index(*, page_count: PageCount, byte_count: ByteCount) -> RenderedBody:
    return RenderedBody(f"no structural index\npages: {int(page_count)}\nbytes: {int(byte_count)}")


def format_heading_list(
    lines: Sequence[str],
    *,
    headings: tuple[HeadingRecord, ...] | None = None,
    level_filter: HeadingLevel | None = None,
) -> RenderedBody:
    """List headings. level_filter is a maximum rank (1 through N)."""
    records = parse_headings(lines) if headings is None else headings
    if level_filter is not None:
        records = tuple(record for record in records if record.level <= level_filter)
    out: list[str] = []
    for record in records:
        indent = "  " * (int(record.level) - 1)
        out.append(f"{indent}- {record.text}")
    return RenderedBody("\n".join(out))


def format_outline_list(
    outline: Sequence[OutlineRecord],
    *,
    level_filter: OutlineLevel | None = None,
) -> RenderedBody:
    """List outline items. level_filter is a maximum rank (1 through N)."""
    records = outline
    if level_filter is not None:
        records = tuple(record for record in records if record.level <= level_filter)
    out: list[str] = []
    for record in records:
        indent = "  " * (int(record.level) - 1)
        out.append(f"{indent}- {record.title}")
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


def format_attributed(parts: Sequence[tuple[FileRef, RenderedBody]]) -> RenderedBody:
    if len(parts) == 1:
        return parts[0][1]
    blocks = [f"==> {path} <==\n{body}" for path, body in parts]
    return RenderedBody("\n\n".join(blocks))


def format_skip_heading(path: FileRef, heading: HeadingText) -> ErrorMessage:
    return ErrorMessage(f'{path}: heading "{heading}" not found, skipped')


_INTEGER_RE = re.compile(r"-?(0|[1-9][0-9]*)\Z")
_VALUE_START = frozenset(" \t#[]{}'\"|>&*")


class _Reject(Exception):
    def __init__(self, reason: FrontmatterReject) -> None:
        self.reason = reason


def frontmatter_interior(split: FrontmatterSplit) -> DocumentLines | None:
    block = split.frontmatter
    if block is None or len(block) < 2:
        return None
    if block[0].rstrip() != "---" or block[-1].rstrip() != "---":
        return None
    return block[1:-1]


def parse_frontmatter_yaml(lines: Sequence[str]) -> FrontmatterParse:
    try:
        root = _FrontmatterParser(lines).parse_root()
    except _Reject as exc:
        return FrontmatterParse(root=None, reject=exc.reason)
    return FrontmatterParse(root=root, reject=None)


def lookup(root: YamlMap, key_path: tuple[str, ...]) -> YamlNode | None:
    current: YamlNode = root
    for key in key_path:
        match current:
            case YamlMap(entries=entries):
                matched: YamlNode | None = None
                for entry_key, entry_value in entries:
                    if entry_key == key:
                        matched = entry_value
                        break
                if matched is None:
                    return None
                current = matched
            case _:
                return None
    return current


def match_where(root: YamlMap, clause: WhereClause) -> bool:
    if not clause.key_path:
        return False
    parent_path = clause.key_path[:-1]
    last = clause.key_path[-1]
    owner: YamlNode = root if not parent_path else lookup(root, parent_path)
    match owner:
        case YamlMap(entries=entries):
            present = False
            value: YamlNode | None = None
            for key, item in entries:
                if key == last:
                    present = True
                    value = item
                    break
            if not present:
                return False
        case _:
            return False
    match value:
        case YamlSeq(items=items):
            return any(_name_equal(item, clause.expected) for item in items)
        case YamlMap():
            return False
        case _:
            return _name_equal(value, clause.expected)


def _name_equal(value: YamlNode, expected: str) -> bool:
    match value:
        case bool():
            return expected == ("true" if value else "false")
        case None:
            return expected == "null"
        case int():
            return expected == str(value)
        case str():
            return value == expected
        case _:
            return False


def _split_indent(raw: str) -> tuple[int, str]:
    indent = 0
    for char in raw:
        if char == " ":
            indent += 1
            continue
        if char == "\t":
            raise _Reject(FrontmatterReject.SYNTAX)
        break
    return indent, raw[indent:]


def _split_mapping_line(content: str) -> tuple[str, str] | None:
    for i, char in enumerate(content):
        if char != ":":
            continue
        after = content[i + 1 :]
        if after == "" or after[0] in _VALUE_START:
            return content[:i].strip(), after
    return None


def _plain_until_comment(text: str) -> str:
    if text.startswith("#"):
        return ""
    index = text.find(" #")
    if index == -1:
        return text
    return text[:index]


def _expect_only_comment(rest: str) -> None:
    stripped = rest.strip()
    if stripped == "" or stripped.startswith("#"):
        return
    raise _Reject(FrontmatterReject.SYNTAX)


def _reject_special_tokens(text: str) -> None:
    if "{" in text:
        raise _Reject(FrontmatterReject.FLOW_MAP)
    for token in text.split():
        if token.startswith("&") or token.startswith("*"):
            raise _Reject(FrontmatterReject.ANCHOR)


def _parse_quoted(text: str) -> tuple[str, str]:
    quote = text[0]
    if quote not in "\"'":
        raise _Reject(FrontmatterReject.SYNTAX)
    i = 1
    chars: list[str] = []
    while i < len(text):
        char = text[i]
        if quote == "'" and char == "'":
            if i + 1 < len(text) and text[i + 1] == "'":
                chars.append("'")
                i += 2
                continue
            return "".join(chars), text[i + 1 :]
        if quote == '"' and char == '"':
            return "".join(chars), text[i + 1 :]
        if quote == '"' and char == "\\":
            if i + 1 >= len(text):
                raise _Reject(FrontmatterReject.SYNTAX)
            nxt = text[i + 1]
            if nxt in '"\\':
                chars.append(nxt)
                i += 2
                continue
            raise _Reject(FrontmatterReject.SYNTAX)
        chars.append(char)
        i += 1
    raise _Reject(FrontmatterReject.SYNTAX)


def _parse_flow_seq(text: str) -> tuple[YamlSeq, str]:
    if not text.startswith("["):
        raise _Reject(FrontmatterReject.SYNTAX)
    remaining = text[1:]
    items: list[YamlNode] = []
    expect_item = True
    while remaining:
        remaining = remaining.lstrip(" ")
        if remaining.startswith("]"):
            return YamlSeq(items=tuple(items)), remaining[1:]
        if remaining.startswith(","):
            if expect_item:
                raise _Reject(FrontmatterReject.SYNTAX)
            remaining = remaining[1:]
            expect_item = True
            continue
        if not expect_item:
            raise _Reject(FrontmatterReject.SYNTAX)
        if remaining.startswith("{"):
            raise _Reject(FrontmatterReject.FLOW_MAP)
        if remaining.startswith("&") or remaining.startswith("*"):
            raise _Reject(FrontmatterReject.ANCHOR)
        if remaining.startswith("["):
            item, remaining = _parse_flow_seq(remaining)
            items.append(item)
            expect_item = False
            continue
        if remaining.startswith('"') or remaining.startswith("'"):
            quoted, remaining = _parse_quoted(remaining)
            items.append(quoted)
            expect_item = False
            continue
        end = 0
        while end < len(remaining) and remaining[end] not in ",]":
            end += 1
        raw = remaining[:end].strip()
        remaining = remaining[end:]
        if not raw:
            raise _Reject(FrontmatterReject.SYNTAX)
        _reject_special_tokens(raw)
        items.append(_parse_plain_scalar(raw))
        expect_item = False
    raise _Reject(FrontmatterReject.SYNTAX)


def _parse_plain_scalar(body: str) -> str | int | bool | None:
    if body == "true":
        return True
    if body == "false":
        return False
    if body == "null":
        return None
    if _INTEGER_RE.fullmatch(body):
        return int(body)
    if body.startswith("!") or body.startswith("%"):
        raise _Reject(FrontmatterReject.SYNTAX)
    return body


def _parse_inline(text: str) -> tuple[YamlNode, str]:
    text = text.lstrip(" ")
    if not text or text.startswith("#"):
        return None, "plain"
    if text.startswith("{"):
        raise _Reject(FrontmatterReject.FLOW_MAP)
    if text.startswith("|") or text.startswith(">"):
        raise _Reject(FrontmatterReject.BLOCK_SCALAR)
    if text.startswith("&") or text.startswith("*"):
        raise _Reject(FrontmatterReject.ANCHOR)
    if text.startswith("!") or text.startswith("%"):
        raise _Reject(FrontmatterReject.SYNTAX)
    if text.startswith("["):
        node, rest = _parse_flow_seq(text)
        _expect_only_comment(rest)
        return node, "flow"
    if text.startswith('"') or text.startswith("'"):
        node, rest = _parse_quoted(text)
        _expect_only_comment(rest)
        return node, "quoted"
    body = _plain_until_comment(text).strip()
    _reject_special_tokens(body)
    return _parse_plain_scalar(body), "plain"


def _put_entry(entries: list[tuple[str, YamlNode]], key: str, value: YamlNode) -> None:
    for i, (existing, _) in enumerate(entries):
        if existing == key:
            entries[i] = (key, value)
            return
    entries.append((key, value))


class _FrontmatterParser:
    def __init__(self, lines: Sequence[str]) -> None:
        self._lines = tuple(lines)
        self._i = 0

    def parse_root(self) -> YamlMap:
        root = self._parse_map(min_indent=0)
        if self._peek() is not None:
            raise _Reject(FrontmatterReject.SYNTAX)
        return root

    def _peek(self) -> tuple[int, str] | None:
        found = self._next_content()
        if found is None:
            return None
        _, indent, content = found
        return indent, content

    def _advance(self) -> None:
        found = self._next_content()
        if found is None:
            raise _Reject(FrontmatterReject.SYNTAX)
        index, _, _ = found
        self._i = index + 1

    def _next_content(self) -> tuple[int, int, str] | None:
        i = self._i
        while i < len(self._lines):
            indent, rest = _split_indent(self._lines[i])
            if rest.strip() == "" or rest.lstrip().startswith("#"):
                i += 1
                continue
            if rest.startswith("%"):
                raise _Reject(FrontmatterReject.SYNTAX)
            return i, indent, rest
        return None

    def _parse_map(self, *, min_indent: int) -> YamlMap:
        entries: list[tuple[str, YamlNode]] = []
        map_indent: int | None = None
        while True:
            peeked = self._peek()
            if peeked is None:
                break
            indent, content = peeked
            if indent < min_indent:
                break
            if map_indent is None:
                map_indent = indent
            if indent != map_indent:
                if indent > map_indent:
                    raise _Reject(FrontmatterReject.SYNTAX)
                break
            split = _split_mapping_line(content)
            if split is None:
                raise _Reject(FrontmatterReject.SYNTAX)
            key, raw_value = split
            if key == "":
                raise _Reject(FrontmatterReject.SYNTAX)
            _reject_special_tokens(key)
            self._advance()
            value = self._parse_map_value(raw_value, key_indent=indent)
            _put_entry(entries, key, value)
        return YamlMap(entries=tuple(entries))

    def _parse_seq(self, *, seq_indent: int) -> YamlSeq:
        items: list[YamlNode] = []
        while True:
            peeked = self._peek()
            if peeked is None:
                break
            indent, content = peeked
            if indent != seq_indent:
                break
            if not (content.startswith("- ") or content == "-"):
                break
            self._advance()
            if content == "-":
                items.append(self._parse_nested(parent_indent=seq_indent))
            else:
                items.append(self._parse_map_value(content[2:], key_indent=seq_indent))
        return YamlSeq(items=tuple(items))

    def _parse_map_value(self, raw_value: str, *, key_indent: int) -> YamlNode:
        stripped = raw_value.strip()
        if stripped == "" or stripped.startswith("#"):
            return self._parse_nested(parent_indent=key_indent)
        node, kind = _parse_inline(raw_value)
        if kind == "plain" and isinstance(node, str):
            folded = self._collect_folded(parent_indent=key_indent)
            if folded:
                return f"{node} {folded}" if node else folded
        return node

    def _parse_nested(self, *, parent_indent: int) -> YamlNode:
        peeked = self._peek()
        if peeked is None or peeked[0] <= parent_indent:
            return None
        indent, content = peeked
        if content.startswith("- ") or content == "-":
            return self._parse_seq(seq_indent=indent)
        if _split_mapping_line(content) is not None:
            return self._parse_map(min_indent=parent_indent + 1)
        return self._parse_block_plain(parent_indent=parent_indent)

    def _parse_block_plain(self, *, parent_indent: int) -> YamlNode:
        peeked = self._peek()
        if peeked is None:
            raise _Reject(FrontmatterReject.SYNTAX)
        _, content = peeked
        self._advance()
        node, kind = _parse_inline(content)
        if kind == "plain" and isinstance(node, str):
            folded = self._collect_folded(parent_indent=parent_indent)
            if folded:
                return f"{node} {folded}" if node else folded
        return node

    def _collect_folded(self, *, parent_indent: int) -> str:
        parts: list[str] = []
        while True:
            peeked = self._peek()
            if peeked is None:
                break
            indent, content = peeked
            if indent <= parent_indent:
                break
            if content.startswith("- ") or content == "-":
                break
            if _split_mapping_line(content) is not None:
                break
            self._advance()
            piece = _plain_until_comment(content).strip()
            _reject_special_tokens(piece)
            if piece:
                parts.append(piece)
        return " ".join(parts)
