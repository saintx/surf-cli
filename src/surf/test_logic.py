# test_logic.py
"""Unit tests for pure surf.logic."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from surf.logic import (
    exclusive_page_end,
    extract_outline_section,
    extract_section,
    format_attributed,
    format_empty_index,
    format_empty_pdf_index,
    format_file_index,
    format_heading_list,
    format_outline_list,
    format_skip_heading,
    frontmatter_interior,
    lookup,
    match_outline_span,
    match_where,
    parse_frontmatter_yaml,
    parse_heading_path,
    parse_headings,
    parse_link,
    split_frontmatter,
)
from surf.models import (
    ByteCount,
    CliTarget,
    FileRef,
    FrontmatterReject,
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
    RenderedBody,
    WhereClause,
    YamlMap,
    YamlNode,
    YamlSeq,
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
    """spec: link-targets#Wikilink with a heading extracts that section"""
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
    """spec: link-targets#Nested path inside a link"""
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
    """spec: frontmatter-only#Frontmatter block is echoed, not parsed"""
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
    """spec: section-extraction#Section stops at the next heading of the same or higher level"""
    split = split_frontmatter(SAMPLE_MD.splitlines())
    result = extract_section(split.body, hp("Details"))
    assert result is not None
    assert int(result.level) == 2
    text = "\n".join(result.lines)
    assert "Detail content" in text
    assert "Another Section" not in text


def test_extract_bare_baz_first_hit() -> None:
    """spec: section-extraction#Bare name matches the first occurrence"""
    result = extract_section(NESTED_MD.splitlines(), hp("Baz"))
    assert result is not None
    text = "\n".join(result.lines)
    assert "Foo Baz body" in text
    assert "Bar Baz body" not in text


def test_extract_bar_baz() -> None:
    """spec: section-extraction#Nested path selects the child inside the named parent"""
    result = extract_section(NESTED_MD.splitlines(), hp("Bar#Baz"))
    assert result is not None
    text = "\n".join(result.lines)
    assert "Bar Baz body" in text
    assert "Foo Baz body" not in text


def test_extract_nested_foo_baz() -> None:
    """spec: section-extraction#Nested path selects the child inside the named parent"""
    result = extract_section(NESTED_MD.splitlines(), hp("Foo#Baz"))
    assert result is not None
    assert int(result.level) == 3
    text = "\n".join(result.lines)
    assert "Foo Baz body" in text
    assert "Bar Baz body" not in text


def test_extract_nested_through_h6() -> None:
    """spec: section-extraction#Nested path selects the child inside the named parent"""
    result = extract_section(NESTED_MD.splitlines(), hp("A#B#C#D#E"))
    assert result is not None
    assert int(result.level) == 6
    assert result.lines[0] == "###### E"


def test_extract_sibling_not_child() -> None:
    """spec: section-extraction#Nested path selects the child inside the named parent"""
    assert extract_section(SIBLING_MD.splitlines(), hp("Foo#Baz")) is None


def test_extract_level_filter() -> None:
    """spec: section-extraction#Heading at another rank is not found"""
    split = split_frontmatter(SAMPLE_MD.splitlines())
    assert extract_section(split.body, hp("Introduction"), level_filter=HeadingLevel(2)) is None


def test_format_heading_list() -> None:
    split = split_frontmatter(SAMPLE_MD.splitlines())
    text = format_heading_list(split.body)
    assert "- Introduction" in text
    assert "  - Details" in text


def test_format_heading_list_level_is_max_depth() -> None:
    """spec: heading-tree#Listing limited to the top N ranks"""
    split = split_frontmatter(SAMPLE_MD.splitlines())
    text = format_heading_list(split.body, level_filter=HeadingLevel(2))
    lines = text.splitlines()
    assert "- Introduction" in lines
    assert "  - Details" in lines
    assert "  - Another Section" in lines
    assert "- Conclusion" in lines
    assert "Sub-details" not in text


def test_format_outline_list() -> None:
    """spec: pdf-addressing#Outline is the tree"""
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
    """spec: pdf-addressing#Extract is page-granular"""
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
    """spec: pdf-addressing#Extract is page-granular"""
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


SAME_PAGE_APPENDIX = PdfDocument(
    outline=(
        orec(1, "Additional Experimental Details", 0),
        orec(2, "Retrieval Details", 0),
        orec(2, "Inference Settings", 0),
        orec(2, "Prompt Template Example", 0),
        orec(1, "Societal Impact", 1),
        orec(1, "Later Section", 1),
    ),
    pages=("appendix-page", "societal-page"),
)


def test_same_page_next_dest_span_extracts_dest_page() -> None:
    cases = (
        ("Additional Experimental Details#Retrieval Details", 0),
        ("Additional Experimental Details#Inference Settings", 0),
        ("Societal Impact", 1),
    )
    for path, dest_page in cases:
        span = match_outline_span(SAME_PAGE_APPENDIX.outline, hp(path))
        assert span is not None
        assert span.start_page == span.end_page == PageIndex(dest_page)
        assert exclusive_page_end(span) == PageIndex(dest_page + 1)


def test_extract_nested_same_page_dests_include_dest_page() -> None:
    """spec: pdf-addressing#Extract is page-granular"""
    retrieval = extract_outline_section(
        SAME_PAGE_APPENDIX, hp("Additional Experimental Details#Retrieval Details")
    )
    assert retrieval is not None
    assert retrieval.pages != ()
    assert "\n".join(retrieval.pages) == "appendix-page"

    inference = extract_outline_section(
        SAME_PAGE_APPENDIX, hp("Additional Experimental Details#Inference Settings")
    )
    assert inference is not None
    assert inference.pages != ()
    assert "\n".join(inference.pages) == "appendix-page"

    societal = extract_outline_section(SAME_PAGE_APPENDIX, hp("Societal Impact"))
    assert societal is not None
    assert societal.pages != ()
    assert "\n".join(societal.pages) == "societal-page"


def test_extract_outline_level_filter_native_above_six() -> None:
    """spec: pdf-addressing#Rank is the outline's native rank
    spec: pdf-addressing#Wrong rank on a PDF bookmark is not found
    """
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
    """spec: section-extraction#Matching ignores case"""
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
    """spec: file-map#Map of a markdown file with frontmatter"""
    split = split_frontmatter(SAMPLE_MD.splitlines())
    text = format_file_index(split)
    assert "title: Test Document" in text
    assert "- Introduction" in text
    assert "  - Details" in text
    assert "Detail content" not in text
    assert "Some introductory text" not in text


def test_format_file_index_yaml_only() -> None:
    """spec: no-structural-index#Frontmatter but no headings"""
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
    """spec: file-map#Map of a file without frontmatter"""
    split = split_frontmatter(SAMPLE_NO_FM.splitlines())
    text = format_file_index(split)
    assert split.frontmatter is None
    assert "- Top" in text
    assert "  - Sub" in text
    assert "Hello world" not in text
    assert "Sub content" not in text
    assert "title:" not in text


def test_format_empty_index_reports_lines_and_bytes() -> None:
    """spec: no-structural-index#Markdown with no headings"""
    text = format_empty_index(line_count=LineCount(142), byte_count=ByteCount(1685))
    assert text.splitlines() == [
        "no structural index",
        "lines: 142",
        "bytes: 1685",
    ]


def test_format_empty_pdf_index_reports_pages_and_bytes() -> None:
    """spec: pdf-addressing#PDF without an outline"""
    text = format_empty_pdf_index(page_count=PageCount(18), byte_count=ByteCount(13153200))
    assert text.splitlines() == [
        "no structural index",
        "pages: 18",
        "bytes: 13153200",
    ]


FENCED_MD = """# Doc

## Real

```markdown
# Not a heading
## Also not
```

~~~
### Tilde fenced
~~~

````md
```
# Nested shorter fence stays open
```
````

## After

    # Indented code, not a heading

```
# Unclosed fence runs to the end
## Still code
"""


def test_parse_headings_skips_fenced_code_blocks() -> None:
    """spec: what-counts-as-a-heading#ATX headings inside fenced code blocks are ignored
    spec: what-counts-as-a-heading#Fence rules follow CommonMark
    """
    headings = parse_headings(FENCED_MD.splitlines())
    assert [str(record.text) for record in headings] == ["Doc", "Real", "After"]


def test_extract_section_keeps_fenced_hash_lines_in_body() -> None:
    """spec: what-counts-as-a-heading#Fenced heading text is returned inside its section"""
    lines = FENCED_MD.splitlines()
    result = extract_section(lines, hp("Real"))
    assert result is not None
    body = "\n".join(result.lines)
    assert "# Not a heading" in body
    assert "### Tilde fenced" in body
    assert "# Nested shorter fence stays open" in body
    assert "## After" not in body


def test_backtick_fence_info_string_with_backtick_is_not_a_fence() -> None:
    """spec: what-counts-as-a-heading#Fence rules follow CommonMark"""
    lines = ["# Top", "``` not `a` fence", "## Heading", "```"]
    headings = parse_headings(lines)
    assert [str(record.text) for record in headings] == ["Top", "Heading"]


def test_closing_fence_must_match_char_and_length() -> None:
    """spec: what-counts-as-a-heading#Fence rules follow CommonMark"""
    lines = ["# Top", "````", "~~~~", "```", "## Inside", "````", "## Outside"]
    headings = parse_headings(lines)
    assert [str(record.text) for record in headings] == ["Top", "Outside"]


def test_format_attributed_one_file_is_bare() -> None:
    body = RenderedBody("## Overview\nA text.")
    assert format_attributed(((FileRef("a.md"), body),)) == body


def test_format_attributed_two_files_use_headers() -> None:
    body_a = RenderedBody("## Overview\nA text.")
    body_b = RenderedBody("## Overview\nB text.")
    assert format_attributed(((FileRef("a.md"), body_a), (FileRef("b.md"), body_b))) == (
        "==> a.md <==\n## Overview\nA text.\n\n==> b.md <==\n## Overview\nB text."
    )


def test_format_skip_heading() -> None:
    assert (
        format_skip_heading(FileRef("c.md"), HeadingText("Overview"))
        == 'c.md: heading "Overview" not found, skipped'
    )


def _yaml_node_from_safe_load(value: object) -> YamlNode:
    match value:
        case dict():
            return YamlMap(
                entries=tuple(
                    (str(key), _yaml_node_from_safe_load(item)) for key, item in value.items()
                )
            )
        case list():
            return YamlSeq(items=tuple(_yaml_node_from_safe_load(item) for item in value))
        case bool() | str() | int() | None:
            return value
        case _:
            raise AssertionError(f"unsupported PyYAML node: {value!r}")


@pytest.mark.parametrize(
    "snippet",
    [
        "a:\n  b: 1",
        "a:\n  - x\n  - y",
        "a: [x, y]",
        'a: "x y"',
        "a: x",
        "a: one\n  two",
        "a: true\nb: false\nc: null",
        "a: 42",
        "a: x # note",
    ],
    ids=[
        "nested maps by indentation",
        "block lists with '- '",
        "flow lists like [a, b]",
        "quoted scalars",
        "bare scalars",
        "plain scalar folded across indented lines",
        "true, false, and null",
        "integers",
        "# comments",
    ],
)
def test_supported_yaml_constructs_parse_as_pyyaml(snippet: str) -> None:
    """spec: frontmatter-grammar#Supported YAML constructs parse as PyYAML does"""
    parsed = parse_frontmatter_yaml(snippet.splitlines())
    loaded = yaml.safe_load(snippet)
    assert parsed.reject is None
    assert parsed.root == _yaml_node_from_safe_load(loaded)


@pytest.mark.parametrize(
    ("snippet", "reason"),
    [
        ("name: &n x\nalias: *n", FrontmatterReject.ANCHOR),
        ("name: |\n  text", FrontmatterReject.BLOCK_SCALAR),
        ("name: >\n  text", FrontmatterReject.BLOCK_SCALAR),
        ("name: {b: 1}", FrontmatterReject.FLOW_MAP),
    ],
    ids=["anchor or alias", "block scalar |", "block scalar >", "flow map"],
)
def test_rejected_yaml_constructs(snippet: str, reason: FrontmatterReject) -> None:
    parsed = parse_frontmatter_yaml(snippet.splitlines())
    assert parsed.root is None
    assert parsed.reject is reason


def test_lookup_dotted_nested_map() -> None:
    parsed = parse_frontmatter_yaml(
        "metadata:\n  author:\n    github_username: saintx".splitlines()
    )
    assert parsed.root is not None
    assert lookup(parsed.root, ("metadata", "author", "github_username")) == "saintx"


def test_match_where_list_membership() -> None:
    parsed = parse_frontmatter_yaml("family: [skill-authoring, navigation]".splitlines())
    assert parsed.root is not None
    assert match_where(parsed.root, WhereClause(key_path=("family",), expected="navigation"))
    assert not match_where(parsed.root, WhereClause(key_path=("family",), expected="nope"))


def test_match_where_bool_and_null() -> None:
    parsed = parse_frontmatter_yaml("a: true\nb: false\nc: null".splitlines())
    assert parsed.root is not None
    assert match_where(parsed.root, WhereClause(key_path=("a",), expected="true"))
    assert match_where(parsed.root, WhereClause(key_path=("b",), expected="false"))
    assert match_where(parsed.root, WhereClause(key_path=("c",), expected="null"))
    assert not match_where(parsed.root, WhereClause(key_path=("a",), expected="false"))


def test_plugin_skill_frontmatter_parses() -> None:
    skill_dir = Path(__file__).resolve().parents[2] / "plugins/surf/skills/surf"
    skill_root = None
    for relative in ("SKILL.md", "references/about.md", "references/usage.md"):
        split = split_frontmatter((skill_dir / relative).read_text(encoding="utf-8").splitlines())
        interior = frontmatter_interior(split)
        assert interior is not None
        parsed = parse_frontmatter_yaml(interior)
        assert parsed.reject is None
        assert parsed.root is not None
        assert lookup(parsed.root, ("metadata", "author", "github_username")) == "saintx"
        if relative == "SKILL.md":
            skill_root = parsed.root
    assert skill_root is not None
    description = lookup(skill_root, ("description",))
    assert isinstance(description, str)
    assert "Progressive context disclosure" in description
