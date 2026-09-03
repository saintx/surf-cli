"""surf - Extract markdown sections by heading with Obsidian link support.

Parses Obsidian wikilinks, markdown links, or positional arguments to locate
and extract sections from markdown files.
"""

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

# Package semver; git release tags are surf-v{__version__}.
__version__ = '0.2.2'
__version_tag__ = f'surf-v{__version__}'


# ---------------------------------------------------------------------------
# Link parsing
# ---------------------------------------------------------------------------

def parse_link(text: str) -> tuple[str | None, str | None]:
    """Parse a link reference into (path, heading).

    Supports:
      - Obsidian wikilink:  [[path#Heading]]  or  [[path#Heading|Alias]]
      - Markdown link:      [Text](path.md#Heading)
      - Plain path#heading

    The first `#` splits path from remainder. The remainder may be a single
    heading or a heading path (`Parent#Child#…`). Nested matching is done by
    extract_section, not here.

    Returns (path, heading) where heading may be None.
    """
    # Obsidian wikilink: [[path#Heading|Alias]] or [[path#Heading]] or [[path]]
    m = re.match(r'^\[\[([^|\]]+?)(?:\|[^\]]+)?\]\]$', text)
    if m:
        inner = m.group(1)
        if '#' in inner:
            path, heading = inner.split('#', 1)
            return (path.strip() or None, heading.strip() or None)
        return (inner.strip(), None)

    # Markdown link: [Text](path.md#Heading) or [Text](path.md)
    m = re.match(r'^\[([^\]]*)\]\((.+?)\)$', text)
    if m:
        raw = unquote(m.group(2))
        if '#' in raw:
            path, heading = raw.split('#', 1)
            return (path.strip() or None, heading.strip() or None)
        return (raw.strip(), None)

    # Plain path#heading
    if '#' in text:
        path, heading = text.split('#', 1)
        return (path.strip() or None, heading.strip() or None)

    # Just a path
    return (text.strip(), None)


# ---------------------------------------------------------------------------
# Markdown parsing helpers
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$')


def parse_headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """Return list of (level, line_index, heading_text) for all headings."""
    results = []
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        if m:
            results.append((len(m.group(1)), i, m.group(2).strip()))
    return results


def split_frontmatter(lines: list[str]) -> tuple[list[str] | None, list[str]]:
    """Split lines into (frontmatter_lines, body_lines).

    frontmatter_lines includes the opening and closing --- delimiters.
    Returns (None, lines) if no frontmatter is present.
    """
    if not lines or lines[0].rstrip() != '---':
        return (None, lines)

    for i in range(1, len(lines)):
        if lines[i].rstrip() == '---':
            return (lines[:i + 1], lines[i + 1:])

    # Opening --- but no closing --- : no valid frontmatter
    return (None, lines)


def extract_section(
    lines: list[str],
    heading: str,
    level_filter: int | None = None,
) -> tuple[int, list[str]] | None:
    """Extract a section by heading text or heading path.

    A heading path is `#`-separated segments (`Parent#Child#…`). Each next
    segment is the first heading (document order, case-insensitive) whose
    text matches, whose ATX level is strictly deeper than the previous match,
    and which lies inside the previous match's section (before the next
    heading of that match's level or higher). Intermediate ATX levels need
    not appear in the path.

    Returns (heading_level, section_lines) where section_lines includes the
    resolved heading line and all content until the next heading of same or
    higher level.

    If level_filter is set, only the resolved (final) heading is filtered by
    ATX level. Returns None if the path is empty or a segment is not found.
    """
    headings = parse_headings(lines)
    segments = [s.strip() for s in heading.split('#') if s.strip()]
    if not segments:
        return None

    def section_end(start_idx: int, start_level: int) -> int:
        for level, line_idx, _ in headings:
            if line_idx > start_idx and level <= start_level:
                return line_idx
        return len(lines)

    bound_start = -1
    bound_end = len(lines)
    prev_level = 0
    match_idx = None
    match_level = None

    for i, segment in enumerate(segments):
        target = segment.lower()
        is_last = i == len(segments) - 1
        found = None
        for level, line_idx, text in headings:
            if line_idx <= bound_start or line_idx >= bound_end:
                continue
            if i > 0 and level <= prev_level:
                continue
            if text.lower().strip() != target:
                continue
            if is_last and level_filter is not None and level != level_filter:
                continue
            found = (level, line_idx)
            break
        if found is None:
            return None
        match_level, match_idx = found
        bound_start = match_idx
        prev_level = match_level
        bound_end = section_end(match_idx, match_level)

    return (match_level, lines[match_idx:bound_end])


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_heading_list(lines: list[str]) -> str:
    """Format headings as indented list."""
    headings = parse_headings(lines)
    out = []
    for level, _, text in headings:
        indent = '  ' * (level - 1)
        out.append(f'{indent}- {text}')
    return '\n'.join(out)


# ---------------------------------------------------------------------------
# File resolution
# ---------------------------------------------------------------------------

def resolve_file(path_str: str) -> Path:
    """Resolve a file path, trying .md extension if not found."""
    p = Path(path_str).expanduser()
    if p.exists():
        return p
    if not p.suffix:
        p_md = p.with_suffix('.md')
        if p_md.exists():
            return p_md
    raise FileNotFoundError(f'File not found: {path_str}')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='surf',
        description='Extract markdown sections by heading with Obsidian link support.',
    )
    parser.add_argument(
        '--version',
        action='version',
        version=__version_tag__,
    )

    parser.add_argument(
        'target',
        nargs='?',
        help='Link or file path: [[path#Heading]], [Text](path#Heading), or file path',
    )
    parser.add_argument(
        'heading',
        nargs='?',
        help='Heading text (when target is a plain file path)',
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        '--full',
        action='store_true',
        help='Output frontmatter + section content',
    )
    mode.add_argument(
        '--content-only', '--body-only',
        action='store_true',
        dest='content_only',
        help='Section content without frontmatter (default)',
    )
    mode.add_argument(
        '--frontmatter-only', '-f',
        action='store_true',
        dest='frontmatter_only',
        help='Output only the YAML frontmatter',
    )
    mode.add_argument(
        '--list', '-l',
        action='store_true',
        dest='list_headings',
        help='List all headings in the file',
    )

    parser.add_argument(
        '--level',
        type=int,
        default=None,
        help='Only match headings at this level (1-6)',
    )
    parser.add_argument(
        '--no-heading',
        action='store_true',
        help='Exclude the heading line from output',
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Write output to file instead of stdout',
    )

    return parser


def run(args: argparse.Namespace) -> str:
    """Execute the surf command and return the output string."""
    if args.target is None:
        return 'Error: no target specified. Use surf --help for usage.'

    # Parse the target to get file path and heading
    file_path_str, heading = parse_link(args.target)

    # If heading came from positional arg, use that
    if heading is None and args.heading is not None:
        heading = args.heading

    if file_path_str is None:
        return 'Error: could not parse file path from target.'

    # Resolve the file
    try:
        file_path = resolve_file(file_path_str)
    except FileNotFoundError as e:
        return f'Error: {e}'

    # Read the file
    text = file_path.read_text(encoding='utf-8')
    all_lines = text.splitlines()

    # Split frontmatter
    fm_lines, body_lines = split_frontmatter(all_lines)

    # --- Mode: list headings ---
    if args.list_headings:
        return format_heading_list(body_lines)

    # --- Mode: frontmatter only ---
    if args.frontmatter_only:
        if fm_lines is None:
            return ''
        return '\n'.join(fm_lines)

    # --- Section extraction modes ---
    # Default: body/section content only. --full opts into frontmatter.
    if heading is None:
        # No heading specified: output entire body (or full file with --full)
        if args.full:
            return text.rstrip('\n')
        return '\n'.join(body_lines)

    # Extract the section from body lines
    result = extract_section(body_lines, heading, args.level)
    if result is None:
        return f'Error: heading "{heading}" not found in {file_path}.'

    section_level, section_lines = result

    if args.no_heading and section_lines:
        # Drop the heading line
        section_lines = section_lines[1:]

    # Build output
    parts = []
    if args.full and fm_lines is not None:
        parts.append('\n'.join(fm_lines))
    parts.append('\n'.join(section_lines))

    output = '\n'.join(parts)
    # Strip trailing whitespace but preserve one trailing newline
    return output.rstrip()


def main():
    parser = build_parser()
    args = parser.parse_args()
    output = run(args)

    if args.output:
        Path(args.output).write_text(output + '\n', encoding='utf-8')
    else:
        print(output)


if __name__ == '__main__':
    main()
