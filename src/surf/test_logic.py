# test_logic.py
"""Unit tests for pure surf.logic."""

from __future__ import annotations

import textwrap

from surf.logic import (
    exclusive_page_end,
    extract_outline_section,
    extract_section,
    format_empty_index,
    format_empty_pdf_index,
    format_file_index,
    format_heading_list,
    format_outline_list,
    parse_heading_path,
    parse_headings,
    parse_link,
    split_frontmatter,
)
from surf.models import (
    ByteCount,
    CliTarget,
    FileRef,
    HeadingLevel,
    HeadingPath,
    HeadingPathRemainder,
    HeadingText,
    LineCount,
    OutlineLevel,
    OutlinePageSpan,
    OutlineRecord,
    PageCount,
    PageIndex,
    ParsedLink,
    PdfDocument,
)

SAMPLE_MD = textwrap.dedent("""\
    ---
    title: Test Document
    tags: [test, sample]
    ---
    # Introduction

    Some introductory text.

    ## Details

    Detail content here.

    ### Sub-details

    Nested content.

    ## Another Section

    More content.

    # Conclusion

    Final thoughts.
""")

SAMPLE_NO_FM = textwrap.dedent("""\
    # Top

    Hello world.

    ## Sub

    Sub content.
""")

NESTED_MD = textwrap.dedent("""\
    ## Foo

    Foo body.

    ### Baz

    Foo Baz body.

    ## Bar

    Bar body.

    ### Baz

    Bar Baz body.

    ## A

    A body.

    ### B

    B body.

    #### C

    C body.

    ##### D

    D body.

    ###### E

    E body.
""")

SIBLING_MD = textwrap.dedent("""\
    ## Foo

    Foo body.

    ## Baz

    Sibling Baz body.
""")


def hp(remainder: str) -> HeadingPath:
    parsed = parse_heading_path(HeadingPathRemainder(remainder))
    assert parsed is not None
    return parsed


def link(target: str) -> ParsedLink:
    return parse_link(CliTarget(target))


def test_parse_link_wikilink_with_heading() -> None:
    assert link("[[notes/foo#Bar]]") == ParsedLink(
        file_ref=FileRef("notes/foo"),
        heading_path=HeadingPath(segments=(HeadingText("Bar"),)),
    )


def test_parse_link_wikilink_alias() -> None:
    assert link("[[notes/foo#Bar|My Alias]]") == ParsedLink(
        file_ref=FileRef("notes/foo"),
        heading_path=HeadingPath(segments=(HeadingText("Bar"),)),
    )


def test_parse_link_wikilink_no_heading() -> None:
    assert link("[[notes/foo]]") == ParsedLink(file_ref=FileRef("notes/foo"), heading_path=None)


def test_parse_link_heading_only() -> None:
    assert link("[[#Heading]]") == ParsedLink(
        file_ref=None,
        heading_path=HeadingPath(segments=(HeadingText("Heading"),)),
    )


def test_parse_link_markdown() -> None:
    assert link("[My Link](path/to/file.md#Section)") == ParsedLink(
        file_ref=FileRef("path/to/file.md"),
        heading_path=HeadingPath(segments=(HeadingText("Section"),)),
    )


def test_parse_link_markdown_no_heading() -> None:
    assert link("[My Link](path/to/file.md)") == ParsedLink(
        file_ref=FileRef("path/to/file.md"),
        heading_path=None,
    )


def test_parse_link_url_encoded() -> None:
    parsed = link("[Link](my%20notes/the%20file.md#My%20Heading)")
    assert parsed.file_ref == FileRef("my notes/the file.md")
    assert parsed.heading_path == HeadingPath(segments=(HeadingText("My Heading"),))


def test_parse_link_plain() -> None:
    assert link("file.md#Section") == ParsedLink(
        file_ref=FileRef("file.md"),
        heading_path=HeadingPath(segments=(HeadingText("Section"),)),
    )
    assert link("file.md") == ParsedLink(file_ref=FileRef("file.md"), heading_path=None)


def test_parse_link_nested_remainder() -> None:
    expected = ParsedLink(
        file_ref=FileRef("note"),
        heading_path=HeadingPath(segments=(HeadingText("Foo"), HeadingText("Baz"))),
    )
    assert link("[[note#Foo#Baz]]") == expected
    assert link("[x](note.md#Foo#Baz)") == ParsedLink(
        file_ref=FileRef("note.md"),
        heading_path=expected.heading_path,
    )
    assert link("note.md#Foo#Baz") == ParsedLink(
        file_ref=FileRef("note.md"),
        heading_path=expected.heading_path,
    )


def test_split_frontmatter_present() -> None:
    split = split_frontmatter(SAMPLE_MD.splitlines())
    assert split.frontmatter is not None
    assert split.frontmatter[0] == "---"
    assert split.body[0] == "# Introduction"


def test_split_frontmatter_absent() -> None:
    lines = SAMPLE_NO_FM.splitlines()
    split = split_frontmatter(lines)
    assert split.frontmatter is None
    assert split.body == tuple(lines)


def test_parse_headings_levels() -> None:
    split = split_frontmatter(SAMPLE_MD.splitlines())
    headings = parse_headings(split.body)
    levels = {str(record.text): int(record.level) for record in headings}
    assert levels["Introduction"] == 1
    assert levels["Details"] == 2
    assert levels["Sub-details"] == 3


def test_extract_h2() -> None:
    split = split_frontmatter(SAMPLE_MD.splitlines())
    result = extract_section(split.body, hp("Details"))
    assert result is not None
    assert int(result.level) == 2
    text = "\n".join(result.lines)
    assert "Detail content" in text
    assert "Another Section" not in text


def test_extract_bare_baz_first_hit() -> None:
    result = extract_section(NESTED_MD.splitlines(), hp("Baz"))
    assert result is not None
    text = "\n".join(result.lines)
    assert "Foo Baz body" in text
    assert "Bar Baz body" not in text


def test_extract_bar_baz() -> None:
    result = extract_section(NESTED_MD.splitlines(), hp("Bar#Baz"))
    assert result is not None
    text = "\n".join(result.lines)
    assert "Bar Baz body" in text
    assert "Foo Baz body" not in text


def test_extract_nested_foo_baz() -> None:
    result = extract_section(NESTED_MD.splitlines(), hp("Foo#Baz"))
    assert result is not None
    assert int(result.level) == 3
    text = "\n".join(result.lines)
    assert "Foo Baz body" in text
    assert "Bar Baz body" not in text


def test_extract_nested_through_h6() -> None:
    result = extract_section(NESTED_MD.splitlines(), hp("A#B#C#D#E"))
    assert result is not None
    assert int(result.level) == 6
    assert result.lines[0] == "###### E"


def test_extract_sibling_not_child() -> None:
    assert extract_section(SIBLING_MD.splitlines(), hp("Foo#Baz")) is None


def test_extract_level_filter() -> None:
    split = split_frontmatter(SAMPLE_MD.splitlines())
    assert extract_section(split.body, hp("Introduction"), level_filter=HeadingLevel(2)) is None


def test_format_heading_list() -> None:
    split = split_frontmatter(SAMPLE_MD.splitlines())
    text = format_heading_list(split.body)
    assert "- Introduction" in text
    assert "  - Details" in text


def test_format_heading_list_level_is_max_depth() -> None:
    split = split_frontmatter(SAMPLE_MD.splitlines())
    text = format_heading_list(split.body, level_filter=HeadingLevel(2))
    lines = text.splitlines()
    assert "- Introduction" in lines
    assert "  - Details" in lines
    assert "  - Another Section" in lines
    assert "- Conclusion" in lines
    assert "Sub-details" not in text


def test_format_outline_list() -> None:
    outline = (
        OutlineRecord(
            level=OutlineLevel(1),
            title=HeadingText("Parent"),
            page_index=PageIndex(0),
            top=None,
        ),
        OutlineRecord(
            level=OutlineLevel(2),
            title=HeadingText("Child"),
            page_index=PageIndex(1),
            top=None,
        ),
    )
    text = format_outline_list(outline)
    assert text.splitlines() == ["- Parent", "  - Child"]


def orec(
    level: int,
    title: str,
    page: int | None,
    top: float | None = None,
) -> OutlineRecord:
    return OutlineRecord(
        level=OutlineLevel(level),
        title=HeadingText(title),
        page_index=None if page is None else PageIndex(page),
        top=top,
    )


NESTED_OUTLINE = PdfDocument(
    outline=(
        orec(1, "Parent", 0),
        orec(2, "Child", 1),
        orec(1, "Other", 2),
        orec(2, "Child", 3),
    ),
    pages=("parent-page", "first-child", "other-page", "other-child"),
)


def test_extract_outline_nested_path_selects_child_of_parent() -> None:
    result = extract_outline_section(NESTED_OUTLINE, hp("Parent#Child"))
    assert result is not None
    assert int(result.level) == 2
    assert "\n".join(result.pages) == "first-child"
    later = extract_outline_section(NESTED_OUTLINE, hp("Other#Child"))
    assert later is not None
    assert "\n".join(later.pages) == "other-child"


def test_extract_outline_dest_to_next_dest_and_last_item() -> None:
    parent = extract_outline_section(NESTED_OUTLINE, hp("Parent"))
    assert parent is not None
    assert "\n".join(parent.pages) == "parent-page"
    last = extract_outline_section(NESTED_OUTLINE, hp("Other#Child"))
    assert last is not None
    assert "\n".join(last.pages) == "other-child"


def test_exclusive_page_end() -> None:
    def span(start: int | None, end: int | None) -> OutlinePageSpan:
        return OutlinePageSpan(
            level=OutlineLevel(1),
            start_page=None if start is None else PageIndex(start),
            end_page=None if end is None else PageIndex(end),
        )

    assert exclusive_page_end(span(29, 29)) == PageIndex(30)
    assert exclusive_page_end(span(0, 2)) == PageIndex(2)
    assert exclusive_page_end(span(2, None)) is None
    assert exclusive_page_end(span(None, 1)) is None


def test_extract_outline_same_page_includes_dest_page() -> None:
    document = PdfDocument(
        outline=(orec(1, "Alpha", 0), orec(1, "Beta", 0)),
        pages=("shared-page",),
    )
    earlier = extract_outline_section(document, hp("Alpha"))
    assert earlier is not None
    assert "\n".join(earlier.pages) == "shared-page"
    later = extract_outline_section(document, hp("Beta"))
    assert later is not None
    assert "\n".join(later.pages) == "shared-page"


def test_extract_outline_level_filter_native_above_six() -> None:
    document = PdfDocument(
        outline=(orec(7, "Deep", 0),),
        pages=("deep-page",),
    )
    found = extract_outline_section(document, hp("Deep"), level_filter=OutlineLevel(7))
    assert found is not None
    assert int(found.level) == 7
    assert "\n".join(found.pages) == "deep-page"
    assert extract_outline_section(document, hp("Deep"), level_filter=OutlineLevel(1)) is None


def test_extract_outline_case_insensitive_strip() -> None:
    document = PdfDocument(
        outline=(orec(1, "  Mixed Case  ", 0),),
        pages=("mixed-page",),
    )
    result = extract_outline_section(document, hp("mixed case"))
    assert result is not None
    assert "\n".join(result.pages) == "mixed-page"


def test_extract_outline_unknown_title_returns_none() -> None:
    assert extract_outline_section(NESTED_OUTLINE, hp("Missing")) is None


def test_extract_outline_empty_outline_returns_none() -> None:
    document = PdfDocument(outline=(), pages=("page",))
    assert extract_outline_section(document, hp("Parent")) is None


def test_extract_outline_missing_dest_is_empty_found() -> None:
    document = PdfDocument(
        outline=(orec(1, "Ghost", None),),
        pages=("page",),
    )
    result = extract_outline_section(document, hp("Ghost"))
    assert result is not None
    assert int(result.level) == 1
    assert result.pages == ()


def test_extract_outline_skips_ghost_dest_to_later_dest() -> None:
    document = PdfDocument(
        outline=(orec(1, "Alpha", 0), orec(1, "Ghost", None), orec(1, "Beta", 2)),
        pages=("alpha", "mid", "beta"),
    )
    alpha = extract_outline_section(document, hp("Alpha"))
    assert alpha is not None
    assert "\n".join(alpha.pages) == "alpha\nmid"
    assert "beta" not in alpha.pages
    beta = extract_outline_section(document, hp("Beta"))
    assert beta is not None
    assert "\n".join(beta.pages) == "beta"


def test_format_file_index_yaml_and_headings() -> None:
    split = split_frontmatter(SAMPLE_MD.splitlines())
    text = format_file_index(split)
    assert "title: Test Document" in text
    assert "- Introduction" in text
    assert "  - Details" in text
    assert "Detail content" not in text
    assert "Some introductory text" not in text


def test_format_file_index_yaml_only() -> None:
    split = split_frontmatter(textwrap.dedent("""\
            ---
            title: YAML Only
            ---
            Body without headings.
        """).splitlines())
    text = format_file_index(split)
    assert "title: YAML Only" in text
    assert "Body without headings" not in text
    assert "- " not in text


def test_format_file_index_headings_only() -> None:
    split = split_frontmatter(SAMPLE_NO_FM.splitlines())
    text = format_file_index(split)
    assert split.frontmatter is None
    assert "- Top" in text
    assert "  - Sub" in text
    assert "Hello world" not in text
    assert "Sub content" not in text
    assert "title:" not in text


def test_format_empty_index_reports_lines_and_bytes() -> None:
    text = format_empty_index(line_count=LineCount(142), byte_count=ByteCount(1685))
    assert text.splitlines() == [
        "no structural index",
        "lines: 142",
        "bytes: 1685",
    ]


def test_format_empty_pdf_index_reports_pages_and_bytes() -> None:
    text = format_empty_pdf_index(page_count=PageCount(18), byte_count=ByteCount(13153200))
    assert text.splitlines() == [
        "no structural index",
        "pages: 18",
        "bytes: 13153200",
    ]
