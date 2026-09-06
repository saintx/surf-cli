# test_logic.py
"""Unit tests for pure surf.logic."""

from __future__ import annotations

import textwrap

from surf.logic import (
    extract_section,
    format_empty_index,
    format_file_index,
    format_heading_list,
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
    ParsedLink,
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
