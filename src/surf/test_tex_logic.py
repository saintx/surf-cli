# test_tex_logic.py
"""Unit tests for TeX sectioning parse and shared extract."""

from __future__ import annotations

import textwrap

from surf.logic import (
    _TEX_LEVEL,
    extract_section,
    format_file_index,
    format_heading_list,
    parse_heading_path,
    parse_tex_headings,
    split_frontmatter,
)
from surf.models import HeadingLevel, HeadingPath, HeadingPathRemainder, TexCommand


def hp(remainder: str) -> HeadingPath:
    parsed = parse_heading_path(HeadingPathRemainder(remainder))
    assert parsed is not None
    return parsed


def tex_lines(source: str) -> list[str]:
    return textwrap.dedent(source).strip("\n").splitlines()


def test_parse_section_and_subsection_levels() -> None:
    lines = tex_lines(r"""
        \section{What this corpus is}
        \subsection{Child}
        """)
    levels = {str(record.text): int(record.level) for record in parse_tex_headings(lines)}
    assert levels["What this corpus is"] == 3
    assert levels["Child"] == 4


def test_parse_paragraph_run_in_level_six() -> None:
    lines = [r"\paragraph{Run-in} body on the same line"]
    headings = parse_tex_headings(lines)
    assert len(headings) == 1
    assert int(headings[0].level) == 6
    assert str(headings[0].text) == "Run-in"
    result = extract_section(lines, hp("Run-in"), headings=headings)
    assert result is not None
    assert result.lines[0] == r"\paragraph{Run-in} body on the same line"


def test_parse_starred_section_and_subsection() -> None:
    lines = tex_lines(r"""
        \section*{Starred}
        starred body
        \subsection*{Also starred}
        """)
    headings = parse_tex_headings(lines)
    assert [(int(record.level), str(record.text)) for record in headings] == [
        (3, "Starred"),
        (4, "Also starred"),
    ]
    result = extract_section(lines, hp("Starred"), headings=headings)
    assert result is not None
    assert result.lines[0] == r"\section*{Starred}"
    assert "starred body" in "\n".join(result.lines)


def test_parse_optional_short_title_uses_long() -> None:
    lines = [r"\section[short]{long}"]
    headings = parse_tex_headings(lines)
    assert [str(record.text) for record in headings] == ["long"]
    result = extract_section(lines, hp("long"), headings=headings)
    assert result is not None
    assert extract_section(lines, hp("short"), headings=headings) is None


def test_parse_nested_braces_in_title() -> None:
    lines = [r"\section{Title \emph{x}}"]
    headings = parse_tex_headings(lines)
    assert [str(record.text) for record in headings] == [r"Title \emph{x}"]


def test_parse_math_source_title_exact() -> None:
    title = r"Type system: $\Theta$-annotations"
    lines = [rf"\section{{{title}}}"]
    headings = parse_tex_headings(lines)
    assert [str(record.text) for record in headings] == [title]
    result = extract_section(lines, hp(title), headings=headings)
    assert result is not None


def test_commented_section_is_not_a_heading() -> None:
    lines = tex_lines(r"""
        % \section{Commented}
        \section{Real}
        """)
    assert [str(record.text) for record in parse_tex_headings(lines)] == ["Real"]


def test_listing_line_is_a_heading() -> None:
    lines = [r"\section{Inside listing}"]
    headings = parse_tex_headings(lines)
    assert len(headings) == 1
    assert str(headings[0].text) == "Inside listing"


def test_leading_whitespace_section_matches() -> None:
    lines = [r"  \section{Indented}"]
    headings = parse_tex_headings(lines)
    assert [str(record.text) for record in headings] == ["Indented"]


def test_empty_section_is_not_a_heading() -> None:
    assert parse_tex_headings([r"\section{}"]) == ()


def test_extract_case_insensitive() -> None:
    lines = tex_lines(r"""
        \section{What this corpus is}

        corpus body
        """)
    headings = parse_tex_headings(lines)
    result = extract_section(lines, hp("what this corpus is"), headings=headings)
    assert result is not None
    assert "corpus body" in "\n".join(result.lines)


def test_extract_first_hit_duplicate_sections() -> None:
    lines = tex_lines(r"""
        \section{Dup}

        first

        \section{Dup}

        second
        """)
    headings = parse_tex_headings(lines)
    result = extract_section(lines, hp("Dup"), headings=headings)
    assert result is not None
    text = "\n".join(result.lines)
    assert "first" in text
    assert "second" not in text


def test_extract_nested_parent_child() -> None:
    lines = tex_lines(r"""
        \section{Parent}

        parent body

        \subsection{Child}

        child body

        \section{Sibling}

        sibling body
        """)
    headings = parse_tex_headings(lines)
    result = extract_section(lines, hp("Parent#Child"), headings=headings)
    assert result is not None
    text = "\n".join(result.lines)
    assert "child body" in text
    assert r"\subsection{Child}" in text
    assert "sibling body" not in text
    assert r"\section{Sibling}" not in text
    assert "parent body" not in text


def test_extract_level_filter_hits_section_not_subsection() -> None:
    lines = tex_lines(r"""
        \section{Named}

        section body

        \subsection{Named}

        subsection body
        """)
    headings = parse_tex_headings(lines)
    section = extract_section(lines, hp("Named"), level_filter=HeadingLevel(3), headings=headings)
    assert section is not None
    assert int(section.level) == 3
    assert section.lines[0] == r"\section{Named}"
    assert "section body" in "\n".join(section.lines)
    subsection = extract_section(
        lines, hp("Named"), level_filter=HeadingLevel(4), headings=headings
    )
    assert subsection is not None
    assert int(subsection.level) == 4
    assert subsection.lines[0] == r"\subsection{Named}"


def test_format_heading_list_tex_indent() -> None:
    lines = tex_lines(r"""
        \section{What this corpus is}
        \subsection{Child}
        """)
    text = format_heading_list(lines, headings=parse_tex_headings(lines))
    assert text.splitlines() == [
        "    - What this corpus is",
        "      - Child",
    ]


def test_format_file_index_tex_equals_heading_list() -> None:
    lines = tex_lines(r"""
        \section{What this corpus is}
        body
        \subsection{Child}
        """)
    headings = parse_tex_headings(lines)
    split = split_frontmatter(lines)
    listed = format_heading_list(lines, headings=headings)
    assert split.frontmatter is None
    assert format_file_index(split, headings=headings) == listed
    assert listed == "    - What this corpus is\n      - Child"


def test_parse_subsubsection_level_five_not_subsection() -> None:
    lines = tex_lines(r"""
        \subsection{Sub}
        \subsubsection{Subsub}
        """)
    records = parse_tex_headings(lines)
    levels = {str(record.text): int(record.level) for record in records}
    assert levels["Sub"] == 4
    assert levels["Subsub"] == 5
    assert [str(record.text) for record in records] == ["Sub", "Subsub"]


def test_sectioning_is_not_a_heading() -> None:
    lines = [r"\sectioning{Not a heading}", r"\section{Real}"]
    assert [str(record.text) for record in parse_tex_headings(lines)] == ["Real"]


def test_parse_subparagraph_level_seven() -> None:
    lines = [r"\subparagraph{Tiny}"]
    headings = parse_tex_headings(lines)
    assert len(headings) == 1
    assert int(headings[0].level) == 7
    assert str(headings[0].text) == "Tiny"


def test_parse_bom_prefixed_section_is_a_heading() -> None:
    """Holdings p-000814 2_Related_Work.tex starts with UTF-8 BOM before \\section."""
    lines = ["\ufeff\\section{Related Work}", "body"]
    headings = parse_tex_headings(lines)
    assert [str(record.text) for record in headings] == ["Related Work"]
    result = extract_section(lines, hp("Related Work"), headings=headings)
    assert result is not None
    assert "body" in "\n".join(result.lines)


def test_parse_multiline_section_title() -> None:
    """Holdings p-001645 JL.tex wraps \\section{...} across lines."""
    lines = [
        r"\section{Low Dimensions Suffice: Proof of ",
        r"\texorpdfstring{Theorem~\ref{thm:main}}{Main Theorem}}",
        r"\label{sec:mainthmproof}",
        "proof body",
        r"\section{Next}",
    ]
    headings = parse_tex_headings(lines)
    assert [str(record.text) for record in headings] == [
        r"Low Dimensions Suffice: Proof of \texorpdfstring{Theorem~\ref{thm:main}}{Main Theorem}",
        "Next",
    ]
    result = extract_section(
        lines,
        hp(
            r"Low Dimensions Suffice: Proof of "
            r"\texorpdfstring{Theorem~\ref{thm:main}}{Main Theorem}"
        ),
        headings=headings,
    )
    assert result is not None
    text = "\n".join(result.lines)
    assert "proof body" in text
    assert r"\section{Next}" not in text


def test_parse_multiline_paragraph_title() -> None:
    """Holdings p-001654 05_results.tex wraps \\paragraph titles at column wrap."""
    lines = [
        r"\paragraph{The skill setting asks the same question with a harder probe, and",
        r"the winner depends on who consumes the memory.} Under the",
        r"stronger agent the verbatim lead holds.",
        r"\paragraph{Later}",
    ]
    headings = parse_tex_headings(lines)
    assert [str(record.text) for record in headings] == [
        "The skill setting asks the same question with a harder probe, and "
        "the winner depends on who consumes the memory.",
        "Later",
    ]
    result = extract_section(
        lines,
        hp(
            "The skill setting asks the same question with a harder probe, and "
            "the winner depends on who consumes the memory."
        ),
        headings=headings,
    )
    assert result is not None
    assert "verbatim lead holds" in "\n".join(result.lines)
    assert r"\paragraph{Later}" not in "\n".join(result.lines)


def test_unclosed_title_at_eof_is_not_a_heading() -> None:
    assert parse_tex_headings([r"\section{Never closed"]) == ()


def test_tex_command_level_map() -> None:
    assert _TEX_LEVEL[TexCommand("part")] == HeadingLevel(1)
    assert _TEX_LEVEL[TexCommand("chapter")] == HeadingLevel(2)
    assert _TEX_LEVEL[TexCommand("section")] == HeadingLevel(3)
    assert _TEX_LEVEL[TexCommand("subsection")] == HeadingLevel(4)
    assert _TEX_LEVEL[TexCommand("subsubsection")] == HeadingLevel(5)
    assert _TEX_LEVEL[TexCommand("paragraph")] == HeadingLevel(6)
    assert _TEX_LEVEL[TexCommand("subparagraph")] == HeadingLevel(7)


def test_parse_space_between_optional_and_long_title() -> None:
    lines = [r"\section[short] {long}"]
    headings = parse_tex_headings(lines)
    assert [str(record.text) for record in headings] == ["long"]
    assert extract_section(lines, hp("short"), headings=headings) is None
    result = extract_section(lines, hp("long"), headings=headings)
    assert result is not None


def test_wrapped_title_heading_line_count() -> None:
    lines = [
        r"\section{Low Dimensions Suffice: Proof of ",
        r"\texorpdfstring{Theorem~\ref{thm:main}}{Main Theorem}}",
        "proof body",
        r"\section{Next}",
    ]
    headings = parse_tex_headings(lines)
    result = extract_section(
        lines,
        hp(
            r"Low Dimensions Suffice: Proof of "
            r"\texorpdfstring{Theorem~\ref{thm:main}}{Main Theorem}"
        ),
        headings=headings,
    )
    assert result is not None
    assert int(result.heading_line_count) == 2
    assert int(headings[0].title_end_line) == 1
