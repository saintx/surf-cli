# orchestrator.py
"""Laminate models, logic, and adapters. No heading regex."""

from __future__ import annotations

import argparse
import sys

from surf import __version__
from surf.adapters import read_document, resolve_file, write_output
from surf.logic import (
    extract_section,
    format_file_index,
    format_heading_list,
    parse_heading_path,
    parse_link,
    split_frontmatter,
)
from surf.models import (
    CliFailure,
    CliOptions,
    CliSuccess,
    FileRef,
    HeadingLevel,
    HeadingPath,
    HeadingText,
)

type CliResult = CliSuccess | CliFailure


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="surf",
        description="Extract markdown sections by heading with Obsidian link support.",
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
        "--level", type=int, default=None, help="Only match headings at this level (1-6)"
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
        return CliFailure(message="no target specified. Use surf --help for usage.", exit_code=2)
    parsed = parse_link(args.target)
    heading_path = parsed.heading_path
    if heading_path is None and args.heading is not None:
        heading_path = parse_heading_path(args.heading)
        if heading_path is None:
            heading_path = HeadingPath(segments=(HeadingText(args.heading),))
    level_filter = HeadingLevel(args.level) if args.level is not None else None
    output_ref = FileRef(args.output) if args.output else None
    return CliOptions(
        file_ref=parsed.file_ref,
        heading_path=heading_path,
        list_headings=bool(args.list_headings),
        frontmatter_only=bool(args.frontmatter_only),
        full=bool(args.full),
        no_heading=bool(args.no_heading),
        level_filter=level_filter,
        output_ref=output_ref,
    )


def run(options: CliOptions) -> CliResult:
    if options.file_ref is None:
        return CliFailure(message="could not parse file path from target.", exit_code=2)
    try:
        path = resolve_file(options.file_ref)
    except FileNotFoundError as exc:
        return CliFailure(message=str(exc), exit_code=2)
    lines = read_document(path)
    split = split_frontmatter(lines)

    if options.list_headings:
        return CliSuccess(body=format_heading_list(split.body))
    if options.frontmatter_only:
        if split.frontmatter is None:
            return CliSuccess(body="")
        return CliSuccess(body="\n".join(split.frontmatter))

    if options.heading_path is None:
        return CliSuccess(body=format_file_index(split))

    extracted = extract_section(
        split.body,
        options.heading_path,
        level_filter=options.level_filter,
    )
    if extracted is None:
        remainder = "#".join(str(seg) for seg in options.heading_path.segments)
        return CliFailure(message=f'heading "{remainder}" not found in {path}.', exit_code=1)

    section_lines = extracted.lines
    if options.no_heading and section_lines:
        section_lines = section_lines[1:]
    parts: list[str] = []
    if options.full and split.frontmatter is not None:
        parts.append("\n".join(split.frontmatter))
    parts.append("\n".join(section_lines))
    return CliSuccess(body="\n".join(parts).rstrip())


def run_argv(argv: list[str] | None = None) -> CliResult:
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
