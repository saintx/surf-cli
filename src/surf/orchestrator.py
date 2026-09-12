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
    read_pdf_catalog,
    read_pdf_pages,
    resolve_file,
    resolve_tex_include,
    write_output,
)
from surf.logic import (
    exclusive_page_end,
    extract_section,
    format_attributed,
    format_empty_index,
    format_empty_pdf_index,
    format_file_index,
    format_heading_list,
    format_outline_list,
    format_skip_heading,
    format_skip_parse,
    frontmatter_interior,
    match_outline_span,
    match_where,
    parse_frontmatter_yaml,
    parse_heading_path,
    parse_headings,
    parse_link,
    parse_tex_headings,
    parse_where_token,
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
    FrontmatterReject,
    HeadingLevel,
    HeadingPath,
    HeadingPathRemainder,
    HeadingText,
    LineCount,
    OutlineLevel,
    RenderedBody,
    WhereClause,
)

type CliResult = CliSuccess | CliFailure


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="surf",
        description="Extract markdown, TeX, or PDF outline sections with Obsidian link support.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "targets",
        nargs="*",
        help="Link or file path: [[path#Heading]], [Text](path#Heading), or file path; "
        "heading as the second positional in single-target form",
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
        help="List headings or PDF outline titles",
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
        "-s",
        "--section",
        default=None,
        help="Heading or outline title to extract from each file",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Name skipped files on stderr",
    )
    parser.add_argument(
        "--where",
        action="append",
        metavar="KEY=VALUE",
        help="Keep files whose frontmatter matches KEY=VALUE (repeatable, conjunctive)",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None, help="Write output to file instead of stdout"
    )
    return parser


def _heading_from_token(token: str) -> HeadingPath:
    heading_path = parse_heading_path(HeadingPathRemainder(token))
    if heading_path is None:
        return HeadingPath(segments=(HeadingText(token),))
    return heading_path


def options_from_namespace(args: argparse.Namespace) -> CliOptions | CliFailure:
    targets: list[str] = list(args.targets)
    section: str | None = args.section
    list_headings = bool(args.list_headings)
    frontmatter_only = bool(args.frontmatter_only)
    where_raw: list[str] = list(args.where or [])
    multi = frontmatter_only or list_headings or (section is not None) or bool(where_raw)
    if not targets:
        return CliFailure(
            message=ErrorMessage("no target specified. Use surf --help for usage."),
            exit_code=ExitCode(2),
        )
    if section is not None and (list_headings or frontmatter_only):
        return CliFailure(
            message=ErrorMessage("-s/--section cannot combine with --list or -f."),
            exit_code=ExitCode(2),
        )
    if not multi and len(targets) >= 3:
        return CliFailure(
            message=ErrorMessage(
                "extra arguments; use -f, --list, -s/--section, or --where to address many files."
            ),
            exit_code=ExitCode(2),
        )
    where_clauses: list[WhereClause] = []
    for raw in where_raw:
        clause = parse_where_token(raw)
        if clause is None:
            return CliFailure(
                message=ErrorMessage("--where requires KEY=VALUE."),
                exit_code=ExitCode(2),
            )
        where_clauses.append(clause)
    heading_path: HeadingPath | None = None
    file_refs: list[FileRef] = []
    if multi:
        for target in targets:
            parsed = parse_link(CliTarget(target))
            if parsed.file_ref is None:
                return CliFailure(
                    message=ErrorMessage("could not parse file path from target."),
                    exit_code=ExitCode(2),
                )
            file_refs.append(parsed.file_ref)
        if section is not None:
            heading_path = _heading_from_token(section)
    else:
        parsed = parse_link(CliTarget(targets[0]))
        heading_path = parsed.heading_path
        if parsed.file_ref is not None:
            file_refs.append(parsed.file_ref)
        if len(targets) == 2 and heading_path is None:
            heading_path = _heading_from_token(targets[1])
    output_ref = FileRef(args.output) if args.output else None
    return CliOptions(
        file_refs=tuple(file_refs),
        heading_path=heading_path,
        list_headings=list_headings,
        frontmatter_only=frontmatter_only,
        full=bool(args.full),
        no_heading=bool(args.no_heading),
        level_filter=args.level,
        output_ref=output_ref,
        verbose=bool(args.verbose),
        where_clauses=tuple(where_clauses),
    )


def _run_pdf(path: Path, options: CliOptions) -> CliResult:
    catalog = read_pdf_catalog(path)
    outline_level = OutlineLevel(options.level_filter) if options.level_filter is not None else None
    if options.frontmatter_only:
        return CliSuccess(body=RenderedBody(""))
    if options.list_headings or options.heading_path is None:
        if not catalog.outline:
            return CliSuccess(
                body=format_empty_pdf_index(
                    page_count=catalog.page_count, byte_count=catalog.byte_count
                )
            )
        return CliSuccess(body=format_outline_list(catalog.outline, level_filter=outline_level))
    span = match_outline_span(catalog.outline, options.heading_path, level_filter=outline_level)
    if span is None:
        remainder = "#".join(str(seg) for seg in options.heading_path.segments)
        return CliFailure(
            message=ErrorMessage(f'heading "{remainder}" not found in {path}.'),
            exit_code=ExitCode(1),
        )
    if span.start_page is None:
        return CliSuccess(body=RenderedBody(""))
    pages = read_pdf_pages(path, span.start_page, exclusive_page_end(span))
    return CliSuccess(body=RenderedBody("\n".join(pages).rstrip()))


def _run_one(path: Path, options: CliOptions) -> CliResult:
    if path.suffix.lower() == ".pdf":
        return _run_pdf(path, options)
    lines = read_document(path)
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


def _skip_heading_notice(file_ref: FileRef, heading_path: HeadingPath | None) -> ErrorMessage:
    remainder = (
        "#".join(str(seg) for seg in heading_path.segments) if heading_path is not None else ""
    )
    return format_skip_heading(file_ref, HeadingText(remainder))


def _apply_where(path: Path, options: CliOptions) -> bool | FrontmatterReject:
    if path.suffix.lower() == ".pdf":
        return False
    lines = read_document(path)
    if path.suffix.lower() == ".tex":
        lines = _expand_tex_inputs(
            lines,
            root_dir=path.parent,
            current=path,
            seen=frozenset(),
        )
    interior = frontmatter_interior(split_frontmatter(lines))
    if interior is None:
        return False
    parsed = parse_frontmatter_yaml(interior)
    if parsed.root is None:
        return parsed.reject if parsed.reject is not None else False
    return all(match_where(parsed.root, clause) for clause in options.where_clauses)


def run(options: CliOptions) -> CliResult:
    if not options.file_refs:
        return CliFailure(
            message=ErrorMessage("could not parse file path from target."),
            exit_code=ExitCode(2),
        )
    successes: list[tuple[FileRef, RenderedBody]] = []
    notices: list[ErrorMessage] = []
    multi = len(options.file_refs) > 1
    filter_only = bool(options.where_clauses) and not (
        options.frontmatter_only or options.list_headings or options.heading_path is not None
    )
    for file_ref in options.file_refs:
        try:
            path = resolve_file(file_ref)
        except FileNotFoundError as exc:
            return CliFailure(message=ErrorMessage(str(exc)), exit_code=ExitCode(2))
        except IsADirectoryError:
            return CliFailure(
                message=ErrorMessage(f"{file_ref} is a directory"),
                exit_code=ExitCode(2),
            )
        try:
            if options.where_clauses:
                decision = _apply_where(path, options)
                if decision is not True:
                    if isinstance(decision, FrontmatterReject) and options.verbose:
                        notices.append(format_skip_parse(file_ref, decision))
                    continue
            if filter_only:
                successes.append((file_ref, RenderedBody(str(file_ref))))
                continue
            result = _run_one(path, options)
        except UnicodeDecodeError:
            return CliFailure(
                message=ErrorMessage(f"could not decode {path} as UTF-8."),
                exit_code=ExitCode(1),
            )
        except PdfIngestError as exc:
            return CliFailure(message=ErrorMessage(str(exc)), exit_code=ExitCode(1))
        if isinstance(result, CliFailure):
            if not multi:
                return result
            if options.verbose:
                notices.append(_skip_heading_notice(file_ref, options.heading_path))
            continue
        successes.append((file_ref, result.body))
    if not successes:
        return CliFailure(
            message=ErrorMessage(""),
            exit_code=ExitCode(1),
            notices=tuple(notices),
        )
    body = (
        RenderedBody("\n".join(part for _, part in successes))
        if filter_only
        else format_attributed(successes)
    )
    return CliSuccess(body=body, notices=tuple(notices))


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


def _print_notices(notices: tuple[ErrorMessage, ...]) -> None:
    for notice in notices:
        print(notice, file=sys.stderr)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    converted = options_from_namespace(args)
    if isinstance(converted, CliFailure):
        _print_notices(converted.notices)
        if converted.message:
            print(f"Error: {converted.message}", file=sys.stderr)
        raise SystemExit(converted.exit_code)
    result = run(converted)
    _print_notices(result.notices)
    if isinstance(result, CliFailure):
        if result.message:
            print(f"Error: {result.message}", file=sys.stderr)
        raise SystemExit(result.exit_code)
    write_output(result.body, converted.output_ref)
