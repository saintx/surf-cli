# orchestrator.py
"""Laminate models, logic, and adapters. No heading regex."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from surf import __version__
from surf.adapters import (
    PdfIngestError,
    document_byte_count,
    read_document,
    read_pdf_outline,
    read_pdf_pages,
    resolve_file,
    resolve_tex_include,
    write_output,
)
from surf.logic import (
    extract_section,
    format_empty_index,
    format_file_index,
    format_heading_list,
    format_outline_list,
    match_outline_span,
    parse_heading_path,
    parse_headings,
    parse_link,
    parse_tex_headings,
    split_frontmatter,
    tex_include_path,
)
from surf.models import (
    CliFailure,
    CliOptions,
    CliSuccess,
    CliTarget,
    DocumentLines,
    ErrorMessage,
    ExitCode,
    FileRef,
    HeadingLevel,
    HeadingPath,
    HeadingPathRemainder,
    HeadingText,
    LineCount,
    OutlineLevel,
    RenderedBody,
)

type CliResult = CliSuccess | CliFailure


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="surf",
        description="Extract markdown, TeX, or PDF outline sections with Obsidian link support.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "target",
        nargs="?",
        help="Link or file path: [[path#Heading]], [Text](path#Heading), or file path",
    )
    parser.add_argument(
        "heading",
        nargs="?",
        help="Heading text (when target is a plain file path)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="Output frontmatter + section content")
    mode.add_argument(
        "--content-only",
        "--body-only",
        action="store_true",
        dest="content_only",
        help="Section content without frontmatter (default)",
    )
    mode.add_argument(
        "--frontmatter-only",
        "-f",
        action="store_true",
        dest="frontmatter_only",
        help="Output only the YAML frontmatter",
    )
    mode.add_argument(
        "--list",
        "-l",
        action="store_true",
        dest="list_headings",
        help="List all headings in the file",
    )
    parser.add_argument(
        "--level",
        type=int,
        default=None,
        help="Max heading level when listing (1..N); exact level when extracting",
    )
    parser.add_argument(
        "--no-heading", action="store_true", help="Exclude the heading line from output"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None, help="Write output to file instead of stdout"
    )
    return parser


def options_from_namespace(args: argparse.Namespace) -> CliOptions | CliFailure:
    if args.target is None:
        return CliFailure(
            message=ErrorMessage("no target specified. Use surf --help for usage."),
            exit_code=ExitCode(2),
        )
    parsed = parse_link(CliTarget(args.target))
    heading_path = parsed.heading_path
    if heading_path is None and args.heading is not None:
        heading_path = parse_heading_path(HeadingPathRemainder(args.heading))
        if heading_path is None:
            heading_path = HeadingPath(segments=(HeadingText(args.heading),))
    output_ref = FileRef(args.output) if args.output else None
    return CliOptions(
        file_ref=parsed.file_ref,
        heading_path=heading_path,
        list_headings=bool(args.list_headings),
        frontmatter_only=bool(args.frontmatter_only),
        full=bool(args.full),
        no_heading=bool(args.no_heading),
        level_filter=args.level,
        output_ref=output_ref,
    )


def _run_pdf(path: Path, options: CliOptions) -> CliResult:
    try:
        outline = read_pdf_outline(path)
    except PdfIngestError as exc:
        return CliFailure(message=ErrorMessage(str(exc)), exit_code=ExitCode(1))
    outline_level = OutlineLevel(options.level_filter) if options.level_filter is not None else None
    if options.frontmatter_only:
        return CliSuccess(body=RenderedBody(""))
    if options.list_headings or options.heading_path is None:
        return CliSuccess(body=format_outline_list(outline, level_filter=outline_level))
    span = match_outline_span(outline, options.heading_path, level_filter=outline_level)
    if span is None:
        remainder = "#".join(str(seg) for seg in options.heading_path.segments)
        return CliFailure(
            message=ErrorMessage(f'heading "{remainder}" not found in {path}.'),
            exit_code=ExitCode(1),
        )
    if span.start_page is None:
        return CliSuccess(body=RenderedBody(""))
    try:
        pages = read_pdf_pages(path, span.start_page, span.end_page)
    except PdfIngestError as exc:
        return CliFailure(message=ErrorMessage(str(exc)), exit_code=ExitCode(1))
    return CliSuccess(body=RenderedBody("\n".join(pages).rstrip()))


def run(options: CliOptions) -> CliResult:
    if options.file_ref is None:
        return CliFailure(
            message=ErrorMessage("could not parse file path from target."),
            exit_code=ExitCode(2),
        )
    try:
        path = resolve_file(options.file_ref)
    except FileNotFoundError as exc:
        return CliFailure(message=ErrorMessage(str(exc)), exit_code=ExitCode(2))
    if path.suffix.lower() == ".pdf":
        return _run_pdf(path, options)
    try:
        lines = read_document(path)
    except UnicodeDecodeError:
        return CliFailure(
            message=ErrorMessage(f"could not decode {path} as UTF-8."),
            exit_code=ExitCode(1),
        )
    line_count = LineCount(len(lines))
    byte_count = document_byte_count(path)
    if path.suffix.lower() == ".tex":
        lines = _expand_tex_inputs(
            lines,
            root_dir=path.parent,
            current=path,
            seen=frozenset(),
        )
    split = split_frontmatter(lines)
    headings = (
        parse_tex_headings(split.body)
        if path.suffix.lower() == ".tex"
        else parse_headings(split.body)
    )
    empty_index = format_empty_index(line_count=line_count, byte_count=byte_count)
    heading_level = HeadingLevel(options.level_filter) if options.level_filter is not None else None

    if options.list_headings:
        if not headings:
            return CliSuccess(body=empty_index)
        return CliSuccess(
            body=format_heading_list(split.body, headings=headings, level_filter=heading_level)
        )
    if options.frontmatter_only:
        if split.frontmatter is None:
            return CliSuccess(body=RenderedBody(""))
        return CliSuccess(body=RenderedBody("\n".join(split.frontmatter)))

    if options.heading_path is None:
        if not headings and split.frontmatter is None:
            return CliSuccess(body=empty_index)
        return CliSuccess(
            body=format_file_index(split, headings=headings, level_filter=heading_level)
        )

    extracted = extract_section(
        split.body,
        options.heading_path,
        level_filter=heading_level,
        headings=headings,
    )
    if extracted is None:
        remainder = "#".join(str(seg) for seg in options.heading_path.segments)
        return CliFailure(
            message=ErrorMessage(f'heading "{remainder}" not found in {path}.'),
            exit_code=ExitCode(1),
        )

    section_lines = extracted.lines
    if options.no_heading and section_lines:
        section_lines = section_lines[int(extracted.heading_line_count) :]
    parts: list[str] = []
    if options.full and split.frontmatter is not None:
        parts.append("\n".join(split.frontmatter))
    parts.append("\n".join(section_lines))
    return CliSuccess(body=RenderedBody("\n".join(parts).rstrip()))


def _expand_tex_inputs(
    lines: DocumentLines,
    *,
    root_dir: Path,
    current: Path,
    seen: frozenset[Path],
) -> DocumentLines:
    resolved = current.resolve()
    if resolved in seen:
        return ()
    loaded = seen | {resolved}
    out: list[str] = []
    for line in lines:
        rel = tex_include_path(line)
        if rel is None:
            out.append(line)
            continue
        child = resolve_tex_include(root_dir, rel)
        if child is None:
            out.append(line)
            continue
        out.extend(
            _expand_tex_inputs(
                read_document(child),
                root_dir=root_dir,
                current=child,
                seen=loaded,
            )
        )
    return tuple(out)


def run_argv(argv: Sequence[str] | None = None) -> CliResult:
    parser = build_parser()
    args = parser.parse_args(argv)
    converted = options_from_namespace(args)
    if isinstance(converted, CliFailure):
        return converted
    return run(converted)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    converted = options_from_namespace(args)
    if isinstance(converted, CliFailure):
        print(f"Error: {converted.message}", file=sys.stderr)
        raise SystemExit(converted.exit_code)
    result = run(converted)
    if isinstance(result, CliFailure):
        print(f"Error: {result.message}", file=sys.stderr)
        raise SystemExit(result.exit_code)
    write_output(result.body, converted.output_ref)
