# test_orchestrator.py
"""Orchestrator composition tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PageObject

from surf import __version__
from surf.models import (
    CliFailure,
    CliOptions,
    CliSuccess,
    FileRef,
    HeadingPath,
    HeadingText,
    WhereClause,
)
from surf.orchestrator import build_parser, main, options_from_namespace, run_argv
from surf.test_adapters import write_outline_pdf

SAMPLE = """---
title: Test Document
---
# Introduction

intro

## Details

Detail content here.
"""

NESTED = """## Foo

### Baz

Foo Baz body.

## Bar

### Baz

Bar Baz body.
"""

SAMPLE_TEX = r"""\section{What this corpus is}

corpus body

\subsection{A subsection}

sub body

\section{Sibling}

sibling body
"""

MD_WITH_TEX_COMMAND = r"""\section{Not a heading}

# Real
"""


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    path = tmp_path / "sample.md"
    path.write_text(SAMPLE)
    return path


@pytest.fixture
def nested_file(tmp_path: Path) -> Path:
    path = tmp_path / "nested.md"
    path.write_text(NESTED)
    return path


@pytest.fixture
def tex_file(tmp_path: Path) -> Path:
    path = tmp_path / "sample.tex"
    path.write_text(SAMPLE_TEX)
    return path


def rendered(argv: list[str]) -> str:
    result = run_argv(argv)
    if isinstance(result, CliFailure):
        return f"Error: {result.message}"
    return result.body


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """spec: command-line#Version flag prints the installed version"""
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f"surf {__version__}"


def test_extract_details(sample_file: Path) -> None:
    """spec: command-line#Positionals are target then heading
    spec: section-extraction#One section, with its children
    spec: section-extraction#Section stops at the next heading of the same or higher level
    """
    output = rendered([str(sample_file), "Details"])
    assert "title: Test Document" not in output
    assert "## Details" in output
    assert "Detail content" in output


def test_no_heading_does_not_dump(sample_file: Path) -> None:
    """spec: file-map#Map of a markdown file with frontmatter"""
    output = rendered([str(sample_file)])
    assert "title: Test Document" in output
    assert "- Introduction" in output
    assert "Detail content" not in output
    assert "intro" not in output.splitlines()


def test_list_level_filters_markdown_as_max_depth(tmp_path: Path) -> None:
    """spec: heading-tree#Listing limited to the top N ranks"""
    path = tmp_path / "sample.md"
    path.write_text("# Introduction\n\n## Details\n\n### Sub-details\n")
    output = rendered(["--list", "--level", "2", str(path)])
    assert output.splitlines() == ["- Introduction", "  - Details"]
    assert "Sub-details" not in output


def test_list_level_1_markdown_is_hash_not_hashhash(sample_file: Path) -> None:
    """spec: heading-tree#Rank 1 is the top of the tree"""
    output = rendered(["--list", "--level", "1", str(sample_file)])
    assert output.splitlines() == ["- Introduction"]


def test_markdown_hashhash_only_still_needs_level_2(tmp_path: Path) -> None:
    """spec: heading-tree#Rank 1 is the top of the tree
    spec: heading-tree#Listing indents a heading by its rank
    """
    path = tmp_path / "notes.md"
    path.write_text("## Details\n\nbody\n")
    assert "Details" not in rendered(["--list", "--level", "1", str(path)])
    assert rendered(["--list", "--level", "2", str(path)]).splitlines() == ["  - Details"]


def test_list_headings(sample_file: Path) -> None:
    """spec: heading-tree#Tree without frontmatter"""
    output = rendered(["--list", str(sample_file)])
    assert "- Introduction" in output
    assert "  - Details" in output
    assert "title:" not in output


def test_frontmatter_only(sample_file: Path) -> None:
    """spec: frontmatter-only#Frontmatter of a markdown file"""
    output = rendered(["-f", str(sample_file)])
    assert "title: Test Document" in output
    assert "- Introduction" not in output
    assert "Detail content" not in output


def test_nested_path(nested_file: Path) -> None:
    """spec: section-extraction#Nested path selects the child inside the named parent
    spec: link-targets#Wikilink with a heading extracts that section
    spec: link-targets#Nested path inside a link
    """
    output = rendered([f"[[{nested_file}#Foo#Baz]]"])
    assert "Foo Baz body" in output
    assert "Bar Baz body" not in output


def test_missing_file() -> None:
    """spec: errors-and-exit-codes#Missing file"""
    output = rendered(["/nonexistent/file.md"])
    assert "Error" in output
    assert "not found" in output.lower()


def test_output_to_file(sample_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: section-extraction#Output written to a file"""
    outfile = tmp_path / "out.md"
    monkeypatch.setattr(
        "sys.argv",
        ["surf", "-o", str(outfile), "--list", str(sample_file)],
    )
    main()
    assert outfile.exists()
    assert "- Introduction" in outfile.read_text()


def test_parser_positional() -> None:
    converted = options_from_namespace(build_parser().parse_args(["file.md", "My Heading"]))
    assert isinstance(converted, CliOptions)
    assert converted.file_refs == (FileRef("file.md"),)
    assert converted.heading_path == HeadingPath(segments=(HeadingText("My Heading"),))
    assert converted.verbose is False
    assert converted.where_clauses == ()


def test_tex_list_headings(tex_file: Path) -> None:
    output = rendered(["--list", str(tex_file)])
    lines = output.splitlines()
    assert "- What this corpus is" in lines
    assert "  - A subsection" in lines
    assert "- Sibling" in lines
    assert "corpus body" not in output


def test_tex_extract_named_section(tex_file: Path) -> None:
    """spec: section-extraction#Section stops at the next heading of the same or higher level
    spec: tex-addressing#Extract stops at the next command of the same or higher rank
    """
    output = rendered([str(tex_file), "What this corpus is"])
    assert r"\section{What this corpus is}" in output
    assert "corpus body" in output
    assert r"\section{Sibling}" not in output
    assert "sibling body" not in output


def test_tex_missing_heading(tex_file: Path) -> None:
    """spec: errors-and-exit-codes#Heading not found"""
    result = run_argv([str(tex_file), "No such heading"])
    assert isinstance(result, CliFailure)
    assert result.exit_code == 1
    assert "not found" in result.message


def test_tex_no_heading_returns_index(tex_file: Path) -> None:
    """spec: file-map#Map of a TeX or PDF file"""
    output = rendered([str(tex_file)])
    assert output != ""
    assert "- What this corpus is" in output.splitlines()
    assert "  - A subsection" in output.splitlines()
    assert "corpus body" not in output
    assert "sibling body" not in output


def test_md_suffix_keeps_atx_not_tex_commands(tmp_path: Path) -> None:
    """spec: what-counts-as-a-heading#TeX commands in a markdown file are text"""
    path = tmp_path / "sample.md"
    path.write_text(MD_WITH_TEX_COMMAND)
    output = rendered(["--list", str(path)])
    assert "- Real" in output.splitlines()
    assert "Not a heading" not in output


def test_tex_bom_prefixed_list_and_extract(tmp_path: Path) -> None:
    """spec: what-counts-as-a-heading#A byte-order mark does not hide the first heading
    spec: what-counts-as-a-heading#Extract of a BOM-prefixed section drops the BOM
    """
    path = tmp_path / "bom.tex"
    path.write_bytes(b"\xef\xbb\xbf\\section{Related Work}\nbody\n")
    listed = rendered(["--list", str(path)])
    assert "Related Work" in listed
    extracted = rendered([str(path), "Related Work"])
    assert not extracted.startswith("\ufeff")
    assert r"\section{Related Work}" in extracted
    assert "body" in extracted


def test_tex_list_level_filters_to_sections(tex_file: Path) -> None:
    """spec: heading-tree#Rank 1 on TeX is the shallowest command in the file"""
    output = rendered(["--list", "--level", "1", str(tex_file)])
    assert "What this corpus is" in output
    assert "Sibling" in output
    assert "A subsection" not in output


def test_tex_extract_level_1_hits_section_not_subsection(tex_file: Path) -> None:
    """spec: section-extraction#One section, with its children
    spec: section-extraction#Exact rank on extract
    spec: section-extraction#Heading at another rank is not found
    """
    output = rendered(["--level", "1", str(tex_file), "What this corpus is"])
    assert "corpus body" in output
    assert "sub body" in output
    missing = run_argv(["--level", "2", str(tex_file), "What this corpus is"])
    assert isinstance(missing, CliFailure)


def test_tex_article_level_1_lists_section_not_empty(tmp_path: Path) -> None:
    """0.4.2 stored \\section at rank 3, so --level 1 printed nothing.
    spec: heading-tree#Rank 1 on TeX is the shallowest command in the file
    """
    path = tmp_path / "main.tex"
    path.write_text(
        "\\section{Introduction}\nintro\n"
        "\\subsection{Child}\nchild\n"
        "\\section{Related Work}\nrelated\n"
    )
    listed = rendered(["--list", "--level", "1", str(path)])
    assert listed.splitlines() == ["- Introduction", "- Related Work"]
    indexed = rendered(["--level", "1", str(path)])
    assert indexed.splitlines() == ["- Introduction", "- Related Work"]


def test_tex_article_list_level_is_max_depth_extract_is_exact(tmp_path: Path) -> None:
    """spec: section-extraction#Exact rank on extract
    spec: section-extraction#Heading at another rank is not found
    spec: heading-tree#Listing limited to the top N ranks
    """
    path = tmp_path / "main.tex"
    path.write_text(
        "\\section{Introduction}\nintro\n"
        "\\subsection{Child}\nchild\n"
        "\\subsubsection{Tiny}\ntiny\n"
        "\\section{Related Work}\nrelated\n"
    )
    assert rendered(["--list", "--level", "2", str(path)]).splitlines() == [
        "- Introduction",
        "  - Child",
        "- Related Work",
    ]
    assert rendered(["--list", "--level", "3", str(path)]).splitlines() == [
        "- Introduction",
        "  - Child",
        "    - Tiny",
        "- Related Work",
    ]
    extracted = run_argv(["--level", "3", str(path), "Introduction"])
    assert isinstance(extracted, CliFailure)
    assert extracted.exit_code == 1
    child = rendered(["--level", "2", str(path), "Child"])
    assert "child" in child
    assert "tiny" in child
    assert r"\section{Related Work}" not in child


def test_tex_book_list_level_is_max_depth(tmp_path: Path) -> None:
    path = tmp_path / "book.tex"
    path.write_text("\\chapter{One}\n\\section{Two}\n\\subsection{Three}\n")
    assert rendered(["--list", "--level", "1", str(path)]).splitlines() == ["- One"]
    assert rendered(["--list", "--level", "2", str(path)]).splitlines() == [
        "- One",
        "  - Two",
    ]
    assert rendered(["--list", "--level", "3", str(path)]).splitlines() == [
        "- One",
        "  - Two",
        "    - Three",
    ]


def test_tex_input_master_level_1_lists_chapter_sections(tmp_path: Path) -> None:
    """spec: tex-addressing#Included files expand
    spec: tex-addressing#Included section extracts with its body
    spec: heading-tree#Rank 1 on TeX is the shallowest command in the file
    """
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "1_introduction.tex").write_text("\\section{Introduction}\n\nintro body\n")
    (chapters / "2_related_work.tex").write_text(
        "\\section{Related Work}\n\\subsection{Prior}\nrelated body\n"
    )
    master = tmp_path / "main.tex"
    master.write_text("\\input{chapters/1_introduction}\n\\input{chapters/2_related_work}\n")
    listed = rendered(["--list", "--level", "1", str(master)])
    assert listed.splitlines() == ["- Introduction", "- Related Work"]
    assert rendered(["--list", "--level", "2", str(master)]).splitlines() == [
        "- Introduction",
        "- Related Work",
        "  - Prior",
    ]
    extracted = rendered(["--level", "1", str(master), "Introduction"])
    assert "intro body" in extracted
    assert "related body" not in extracted


def test_tex_no_heading_drops_wrapped_title_lines(tmp_path: Path) -> None:
    """spec: section-extraction#Heading line omitted
    spec: tex-addressing#Wrapped title is dropped whole by --no-heading
    """
    path = tmp_path / "wrap.tex"
    path.write_text(
        "\\section{Low Dimensions Suffice: Proof of \n"
        "\\texorpdfstring{Theorem~\\ref{thm:main}}{Main Theorem}}\n"
        "proof body\n"
        "\\section{Next}\n"
    )
    title = (
        r"Low Dimensions Suffice: Proof of "
        r"\texorpdfstring{Theorem~\ref{thm:main}}{Main Theorem}"
    )
    output = rendered(["--no-heading", str(path), title])
    assert r"\section{Low Dimensions Suffice: Proof of " not in output
    assert r"\texorpdfstring{Theorem~\ref{thm:main}}{Main Theorem}}" not in output
    assert "proof body" in output
    assert r"\section{Next}" not in output


def test_tex_input_master_lists_and_extracts_chapter_headings(tmp_path: Path) -> None:
    """spec: tex-addressing#Included files expand
    spec: tex-addressing#Included section extracts with its body
    """
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "1_introduction.tex").write_text("\\section{Introduction}\n\nintro body\n")
    (chapters / "2_related_work.tex").write_text("\\section{Related Work}\n\nrelated body\n")
    master = tmp_path / "main.tex"
    master.write_text("\\input{chapters/1_introduction}\n\\input{chapters/2_related_work}\n")
    listed = rendered(["--list", str(master)])
    assert "- Introduction" in listed.splitlines()
    assert "- Related Work" in listed.splitlines()
    index = rendered([str(master)])
    assert "- Introduction" in index.splitlines()
    extracted = rendered([str(master), "Introduction"])
    assert "intro body" in extracted
    assert r"\section{Introduction}" in extracted
    assert "related body" not in extracted
    assert r"\section{Related Work}" not in extracted


def test_tex_nested_input_resolves_from_master_dir(tmp_path: Path) -> None:
    """spec: tex-addressing#Included files expand
    spec: tex-addressing#Included section extracts with its body
    """
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    tables = tmp_path / "tables"
    tables.mkdir()
    (tables / "stats.tex").write_text("\\subsection{Stats}\n\nstat body\n")
    (chapters / "intro.tex").write_text(
        "\\section{Introduction}\nintro body\n\\input{tables/stats}\n"
    )
    master = tmp_path / "main.tex"
    master.write_text("\\input{chapters/intro}\n")
    listed = rendered(["--list", str(master)])
    assert "- Introduction" in listed.splitlines()
    assert "  - Stats" in listed.splitlines()
    extracted = rendered([str(master), "Introduction#Stats"])
    assert "stat body" in extracted
    assert "intro body" not in extracted


def test_tex_commented_input_is_not_expanded(tmp_path: Path) -> None:
    """spec: tex-addressing#What does not expand"""
    (tmp_path / "secret.tex").write_text("\\section{Secret}\n")
    master = tmp_path / "main.tex"
    master.write_text("% \\input{secret}\n\\section{Visible}\n")
    listed = rendered(["--list", str(master)])
    assert "Visible" in listed
    assert "Secret" not in listed


def test_tex_includegraphics_is_not_expanded(tmp_path: Path) -> None:
    """spec: tex-addressing#What does not expand"""
    (tmp_path / "fig.tex").write_text("\\section{Not a figure}\n")
    master = tmp_path / "main.tex"
    master.write_text("\\includegraphics{fig}\n\\section{Here}\n")
    listed = rendered(["--list", str(master)])
    assert listed.splitlines() == ["- Here"]


def test_tex_missing_input_keeps_other_headings(tmp_path: Path) -> None:
    """spec: tex-addressing#What does not expand"""
    master = tmp_path / "main.tex"
    master.write_text("\\input{chapters/missing}\n\\section{Here}\n")
    listed = rendered(["--list", str(master)])
    assert listed.splitlines() == ["- Here"]


def test_tex_input_cycle_does_not_hang(tmp_path: Path) -> None:
    (tmp_path / "a.tex").write_text("\\input{b}\n\\section{From A}\n")
    (tmp_path / "b.tex").write_text("\\input{a}\n\\section{From B}\n")
    listed = rendered(["--list", str(tmp_path / "a.tex")])
    assert "From A" in listed
    assert "From B" in listed


def test_md_input_command_is_not_expanded(tmp_path: Path) -> None:
    """spec: what-counts-as-a-heading#TeX commands in a markdown file are text"""
    (tmp_path / "child.md").write_text("# Secret\n")
    path = tmp_path / "sample.md"
    path.write_text("\\input{child}\n# Real\n")
    listed = rendered(["--list", str(path)])
    assert listed.splitlines() == ["- Real"]


def test_tex_multiline_title_list_and_extract(tmp_path: Path) -> None:
    """spec: tex-addressing#Title forms that become addresses"""
    path = tmp_path / "wrap.tex"
    path.write_text(
        "\\section{Low Dimensions Suffice: Proof of \n"
        "\\texorpdfstring{Theorem~\\ref{thm:main}}{Main Theorem}}\n"
        "proof body\n"
        "\\section{Next}\n"
    )
    listed = rendered(["--list", str(path)])
    assert "Low Dimensions Suffice: Proof of" in listed
    assert "Main Theorem" in listed
    title = (
        r"Low Dimensions Suffice: Proof of "
        r"\texorpdfstring{Theorem~\ref{thm:main}}{Main Theorem}"
    )
    extracted = rendered([str(path), title])
    assert "proof body" in extracted
    assert r"\section{Next}" not in extracted


def empty_index_text(path: Path, contents: str) -> str:
    path.write_text(contents)
    lines = contents.splitlines()
    return f"no structural index\nlines: {len(lines)}\nbytes: {path.stat().st_size}"


def test_headingless_tex_reports_empty_index_not_body(tmp_path: Path) -> None:
    """spec: no-structural-index#TeX with no sectioning commands"""
    path = tmp_path / "macros.tex"
    expected = empty_index_text(path, "\\newcommand{\\foo}{bar}\n" * 3)
    listed = rendered(["--list", str(path)])
    indexed = rendered([str(path)])
    assert listed == expected
    assert indexed == expected
    assert "\\newcommand" not in listed
    assert "foo" not in listed


def test_headingless_markdown_reports_empty_index(tmp_path: Path) -> None:
    """spec: no-structural-index#Markdown with no headings"""
    path = tmp_path / "notes.md"
    expected = empty_index_text(path, "just a paragraph\nwith two lines\n")
    assert rendered(["--list", str(path)]) == expected
    assert rendered([str(path)]) == expected
    assert "just a paragraph" not in rendered([str(path)])


def test_markdown_frontmatter_without_headings_keeps_yaml_index(tmp_path: Path) -> None:
    """spec: no-structural-index#Frontmatter but no headings
    spec: no-structural-index#Tree of a frontmatter-only file is empty
    """
    path = tmp_path / "notes.md"
    path.write_text("---\ntitle: YAML Only\n---\nBody without headings.\n")
    indexed = rendered([str(path)])
    assert "title: YAML Only" in indexed
    assert "Body without headings" not in indexed
    listed = rendered(["--list", str(path)])
    assert listed.splitlines()[0] == "no structural index"
    assert "Body without headings" not in listed


def test_tex_abstract_list_and_extract(tmp_path: Path) -> None:
    """spec: tex-addressing#Sections and the abstract are addresses
    spec: tex-addressing#Abstract extract begins at its environment
    """
    path = tmp_path / "paper.tex"
    path.write_text(
        "\\begin{abstract}\nabstract body\n\\end{abstract}\n"
        "\\section{Introduction}\nintro body\n"
    )
    listed = rendered(["--list", str(path)])
    assert listed.splitlines() == [
        "- abstract",
        "- Introduction",
    ]
    extracted = rendered([str(path), "abstract"])
    assert r"\begin{abstract}" in extracted
    assert "abstract body" in extracted
    assert "intro body" not in extracted
    assert r"\section{Introduction}" not in extracted


def test_tex_abstract_via_input(tmp_path: Path) -> None:
    """spec: tex-addressing#Abstract extract begins at its environment
    spec: tex-addressing#Included section extracts with its body
    """
    (tmp_path / "00abstract.tex").write_text("spliced abstract body\n")
    master = tmp_path / "main.tex"
    master.write_text("\\begin{abstract}\n\\input{00abstract}\n\\end{abstract}\n")
    listed = rendered(["--list", str(master)])
    assert listed.splitlines() == ["- abstract"]
    extracted = rendered([str(master), "Abstract"])
    assert "spliced abstract body" in extracted
    assert r"\begin{abstract}" in extracted


def test_tex_no_heading_drops_begin_abstract_line(tmp_path: Path) -> None:
    """spec: section-extraction#Heading line omitted"""
    path = tmp_path / "paper.tex"
    path.write_text("\\begin{abstract}\nabstract body\n\\end{abstract}\n")
    output = rendered(["--no-heading", str(path), "abstract"])
    assert r"\begin{abstract}" not in output
    assert "abstract body" in output
    assert r"\end{abstract}" in output


def test_pdf_list_headings(tmp_path: Path) -> None:
    """spec: pdf-addressing#Outline is the tree"""
    path = tmp_path / "doc.pdf"
    write_outline_pdf(
        path,
        page_count=2,
        outline=(("Parent", 0, (("Child", 1, ()),)),),
    )
    output = rendered(["--list", str(path)])
    assert output.splitlines() == ["- Parent", "  - Child"]


def test_pdf_no_heading_lists_outline(tmp_path: Path) -> None:
    """spec: file-map#Map of a TeX or PDF file"""
    path = tmp_path / "doc.pdf"
    write_outline_pdf(
        path,
        page_count=2,
        outline=(("Parent", 0, (("Child", 1, ()),)),),
    )
    output = rendered([str(path)])
    assert output.splitlines() == ["- Parent", "  - Child"]
    assert "Traceback" not in output


def test_pdf_list_does_not_extract_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: file-map#Map of a TeX or PDF file
    spec: pdf-addressing#Outline is the tree
    """
    path = tmp_path / "doc.pdf"
    write_outline_pdf(
        path,
        page_count=2,
        outline=(("Parent", 0, (("Child", 1, ()),)),),
        page_texts=("secret-a", "secret-b"),
    )

    def boom(self: object, *args: object, **kwargs: object) -> str:
        raise AssertionError("extract_text called on PDF list")

    monkeypatch.setattr(PageObject, "extract_text", boom)
    listed = rendered(["--list", str(path)])
    default = rendered([str(path)])
    assert listed.splitlines() == ["- Parent", "  - Child"]
    assert default.splitlines() == ["- Parent", "  - Child"]
    assert "secret-a" not in listed
    assert "secret-b" not in default


def test_pdf_without_outline_reports_empty_index(tmp_path: Path) -> None:
    """spec: pdf-addressing#PDF without an outline"""
    path = tmp_path / "plain.pdf"
    write_outline_pdf(path, page_count=3)
    expected = f"no structural index\npages: 3\nbytes: {path.stat().st_size}"
    assert rendered(["--list", str(path)]) == expected
    assert rendered([str(path)]) == expected


def test_pdf_frontmatter_only_empty(tmp_path: Path) -> None:
    """spec: frontmatter-only#Frontmatter of a PDF"""
    path = tmp_path / "doc.pdf"
    write_outline_pdf(path, page_count=1, outline=(("Parent", 0, ()),))
    output = rendered(["-f", str(path)])
    assert output == ""


def test_pdf_garbage_is_cli_failure(tmp_path: Path) -> None:
    """spec: errors-and-exit-codes#Unreadable PDF"""
    path = tmp_path / "garbage.pdf"
    path.write_bytes(b"not a pdf")
    result = run_argv(["--list", str(path)])
    assert isinstance(result, CliFailure)
    assert result.exit_code == 1
    assert "Traceback" not in result.message
    assert "UnicodeDecodeError" not in result.message


def _nested_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "nested.pdf"
    write_outline_pdf(
        path,
        page_count=4,
        outline=(
            ("Parent", 0, (("Child", 1, ()),)),
            ("Other", 2, (("Child", 3, ()),)),
        ),
        page_texts=("parent-page", "first-child", "other-page", "other-child"),
    )
    return path


def test_pdf_nested_path(tmp_path: Path) -> None:
    """spec: section-extraction#Nested path selects the child inside the named parent
    spec: link-targets#Nested path inside a link
    """
    path = _nested_pdf(tmp_path)
    output = rendered([f"[[{path}#Parent#Child]]"])
    assert "first-child" in output
    assert "other-child" not in output
    assert "parent-page" not in output


def test_pdf_same_page_dest_extracts_page(tmp_path: Path) -> None:
    """spec: pdf-addressing#Extract is page-granular"""
    path = tmp_path / "same.pdf"
    write_outline_pdf(
        path,
        page_count=1,
        outline=(("Alpha", 0, ()), ("Beta", 0, ())),
        page_texts=("shared-page",),
    )
    assert "shared-page" in rendered([str(path), "Alpha"])
    assert "shared-page" in rendered([str(path), "Beta"])


def _same_page_appendix_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "appendix.pdf"
    write_outline_pdf(
        path,
        page_count=2,
        outline=(
            (
                "Additional Experimental Details",
                0,
                (
                    ("Retrieval Details", 0, ()),
                    ("Inference Settings", 0, ()),
                    ("Prompt Template Example", 0, ()),
                ),
            ),
            ("Societal Impact", 1, ()),
            ("Later Section", 1, ()),
        ),
        page_texts=("appendix-page", "societal-page"),
    )
    return path


def test_pdf_nested_same_page_heading_paths_extract_dest_page(tmp_path: Path) -> None:
    """spec: pdf-addressing#Extract is page-granular"""
    path = _same_page_appendix_pdf(tmp_path)
    cases = (
        ("Additional Experimental Details#Retrieval Details", "appendix-page", "societal-page"),
        ("Additional Experimental Details#Inference Settings", "appendix-page", "societal-page"),
        ("Societal Impact", "societal-page", "appendix-page"),
    )
    for heading, present, absent in cases:
        result = run_argv([str(path), heading])
        assert isinstance(result, CliSuccess)
        assert result.body.strip() != ""
        assert present in result.body
        assert absent not in result.body


def test_pdf_missing_outline_title(tmp_path: Path) -> None:
    """spec: errors-and-exit-codes#Heading not found"""
    path = _nested_pdf(tmp_path)
    result = run_argv([str(path), "NoSuch"])
    assert isinstance(result, CliFailure)
    assert result.exit_code == 1
    assert result.message == f'heading "NoSuch" not found in {path}.'


def test_pdf_no_heading_does_not_change_body(tmp_path: Path) -> None:
    """spec: pdf-addressing#Markdown-only flags are no-ops on PDF"""
    path = _nested_pdf(tmp_path)
    default = rendered([str(path), "Parent"])
    no_heading = rendered(["--no-heading", str(path), "Parent"])
    assert default == no_heading
    assert "parent-page" in default


def test_pdf_full_equals_default_extract(tmp_path: Path) -> None:
    """spec: pdf-addressing#Markdown-only flags are no-ops on PDF"""
    path = _nested_pdf(tmp_path)
    assert rendered(["--full", str(path), "Parent"]) == rendered([str(path), "Parent"])


def test_pdf_level_7_matches_native_outline(tmp_path: Path) -> None:
    """spec: pdf-addressing#Rank is the outline's native rank
    spec: pdf-addressing#Wrong rank on a PDF bookmark is not found
    """
    path = tmp_path / "deep.pdf"
    deep = ("Deep", 0, ())
    level6 = ("L6", 0, (deep,))
    level5 = ("L5", 0, (level6,))
    level4 = ("L4", 0, (level5,))
    level3 = ("L3", 0, (level4,))
    level2 = ("L2", 0, (level3,))
    level1 = ("L1", 0, (level2,))
    write_outline_pdf(
        path,
        page_count=1,
        outline=(level1,),
        page_texts=("deep-page",),
    )
    output = rendered(["--level", "7", str(path), "Deep"])
    assert "deep-page" in output
    result = run_argv(["--level", "1", str(path), "Deep"])
    assert isinstance(result, CliFailure)
    assert result.exit_code == 1


def test_section_flag_names_the_heading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: multiple-files#Section flag names the heading"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("## Overview\nA text.\n")
    (tmp_path / "b.md").write_text("## Overview\nB text.\n")
    output = rendered(["-s", "Overview", "a.md", "b.md"])
    assert output == ("==> a.md <==\n## Overview\nA text.\n\n==> b.md <==\n## Overview\nB text.")


def test_single_file_prints_no_header(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: multiple-files#Single file prints no header"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("## Overview\nA text.\n")
    assert rendered(["-s", "Overview", "a.md"]) == rendered(["a.md", "Overview"])


def test_frontmatter_across_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: multiple-files#Frontmatter across files"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("---\ntitle: A\n---\n")
    (tmp_path / "b.md").write_text("---\ntitle: B\n---\n")
    output = rendered(["-f", "a.md", "b.md"])
    assert output == "==> a.md <==\n---\ntitle: A\n---\n\n==> b.md <==\n---\ntitle: B\n---"


def test_files_that_lack_the_address_are_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """spec: multiple-files#Files that lack the address are skipped"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("## Overview\nA text.\n")
    (tmp_path / "c.md").write_text("## Other\n")
    expected = run_argv(["a.md", "Overview"])
    assert isinstance(expected, CliSuccess)
    monkeypatch.setattr("sys.argv", ["surf", "-s", "Overview", "a.md", "c.md", "-v"])
    main()
    captured = capsys.readouterr()
    assert captured.out == expected.body + "\n"
    assert captured.err == 'c.md: heading "Overview" not found, skipped\n'


def test_nothing_matched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """spec: multiple-files#Nothing matched"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "c.md").write_text("## Other\n")
    (tmp_path / "d.md").write_text("## Other\n")
    monkeypatch.setattr("sys.argv", ["surf", "-s", "Overview", "c.md", "d.md"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_per_file_flags_apply_to_each_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: multiple-files#Per-file flags apply to each file"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("# A\n## A2\n### A3\n")
    (tmp_path / "b.md").write_text("# B\n## B2\n### B3\n")
    output = rendered(["--list", "--level", "2", "a.md", "b.md"])
    assert output == "==> a.md <==\n- A\n  - A2\n\n==> b.md <==\n- B\n  - B2"


def test_extra_arguments_without_a_multi_file_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """spec: multiple-files#Extra arguments without a multi-file flag"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("# A\n")
    (tmp_path / "b.md").write_text("# B\n")
    (tmp_path / "c.md").write_text("# C\n")
    monkeypatch.setattr("sys.argv", ["surf", "a.md", "b.md", "c.md"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == (
        "Error: extra arguments; use -f, --list, -s/--section, or --where "
        "to address many files.\n"
    )


def test_directory_as_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """spec: errors-and-exit-codes#Directory as target"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["surf", "."])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == "Error: . is a directory\n"
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_two_positionals_remain_single_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "about.md").write_text("# Hi\n")
    (tmp_path / "usage.md").write_text("# Usage\n")
    result = run_argv(["about.md", "usage.md"])
    assert isinstance(result, CliFailure)
    assert result.exit_code == 1
    assert result.message == 'heading "usage.md" not found in about.md.'


def test_frontmatter_only_wikilink_one_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("---\ntitle: A\n---\n")
    assert rendered(["-f", "[[a.md]]"]) == "---\ntitle: A\n---"


def test_parser_section_multi_file() -> None:
    converted = options_from_namespace(build_parser().parse_args(["-s", "Foo#Baz", "a.md", "b.md"]))
    assert isinstance(converted, CliOptions)
    assert converted.file_refs == (FileRef("a.md"), FileRef("b.md"))
    assert converted.heading_path == HeadingPath(segments=(HeadingText("Foo"), HeadingText("Baz")))


def test_section_cannot_combine_with_list_or_frontmatter() -> None:
    listed = run_argv(["-s", "Overview", "--list", "a.md"])
    assert isinstance(listed, CliFailure)
    assert listed.exit_code == 2
    assert listed.message == "-s/--section cannot combine with --list or -f."
    frontmatter = run_argv(["-s", "Overview", "-f", "a.md"])
    assert isinstance(frontmatter, CliFailure)
    assert frontmatter.exit_code == 2
    assert frontmatter.message == listed.message


def test_pdf_ingest_abort_discards_prior_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("## Overview\nA text.\n")
    (tmp_path / "bad.pdf").write_bytes(b"%PDF-1.4 truncated")
    monkeypatch.setattr("sys.argv", ["surf", "-s", "Overview", "a.md", "bad.pdf"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "==>" not in captured.out
    assert captured.err.startswith("Error:")
    assert "Traceback" not in captured.err
    assert "could not read PDF" in captured.err


def test_utf8_ingest_abort_discards_prior_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("---\ntitle: A\n---\n")
    (tmp_path / "undecodable.bin").write_bytes(b"\xff\xfe")
    monkeypatch.setattr("sys.argv", ["surf", "-f", "a.md", "undecodable.bin"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "==>" not in captured.out
    assert captured.err == "Error: could not decode undecodable.bin as UTF-8.\n"


def test_paths_that_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: filter-by-frontmatter#Paths that match"""
    monkeypatch.chdir(tmp_path)
    matching = "---\nmetadata:\n  family: skill-authoring\n---\n"
    (tmp_path / "one.md").write_text(matching)
    (tmp_path / "two.md").write_text(matching)
    (tmp_path / "three.md").write_text(matching)
    (tmp_path / "other.md").write_text("---\nmetadata:\n  family: navigation\n---\n")
    output = rendered(
        [
            "--where",
            "metadata.family=skill-authoring",
            "one.md",
            "two.md",
            "three.md",
            "other.md",
        ]
    )
    assert output == "one.md\ntwo.md\nthree.md"


def test_filter_then_extract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: filter-by-frontmatter#Filter then extract"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "one.md").write_text(
        "---\nmetadata:\n  family: skill-authoring\n---\n## Overview\nOne.\n"
    )
    (tmp_path / "two.md").write_text(
        "---\nmetadata:\n  family: skill-authoring\n---\n## Overview\nTwo.\n"
    )
    (tmp_path / "other.md").write_text(
        "---\nmetadata:\n  family: navigation\n---\n## Overview\nOther.\n"
    )
    output = rendered(
        [
            "--where",
            "metadata.family=skill-authoring",
            "-s",
            "Overview",
            "one.md",
            "two.md",
            "other.md",
        ]
    )
    assert output == ("==> one.md <==\n## Overview\nOne.\n\n==> two.md <==\n## Overview\nTwo.")


def test_dotted_keys_walk_nested_maps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: filter-by-frontmatter#Dotted keys walk nested maps"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("---\nmetadata:\n  author:\n    github_username: saintx\n---\n")
    assert rendered(["--where", "metadata.author.github_username=saintx", "a.md"]) == "a.md"


def test_list_values_match_on_membership(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: filter-by-frontmatter#List values match on membership"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("---\nmetadata:\n  family: [skill-authoring, navigation]\n---\n")
    assert rendered(["--where", "metadata.family=navigation", "a.md"]) == "a.md"


def test_value_absent_from_a_list_is_a_non_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """spec: filter-by-frontmatter#Value absent from a list is a non-match"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("---\nmetadata:\n  family: [skill-authoring, navigation]\n---\n")
    monkeypatch.setattr("sys.argv", ["surf", "--where", "metadata.family=nope", "a.md"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_repeated_where_filters_are_conjunctive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """spec: filter-by-frontmatter#Repeated --where filters are conjunctive"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text(
        "---\nmetadata:\n  family: [navigation]\n  mixins: [overview]\n---\n"
    )
    assert (
        rendered(
            [
                "--where",
                "metadata.family=navigation",
                "--where",
                "metadata.mixins=overview",
                "a.md",
            ]
        )
        == "a.md"
    )


def test_one_failing_where_rejects_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """spec: filter-by-frontmatter#One failing --where rejects the file"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text(
        "---\nmetadata:\n  family: [navigation]\n  mixins: [overview]\n---\n"
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "surf",
            "--where",
            "metadata.family=navigation",
            "--where",
            "metadata.mixins=nope",
            "a.md",
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("disable-model-invocation", "true"),
        ("enabled", "false"),
        ("owner", "null"),
    ],
)
def test_booleans_and_null_compare_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str, value: str
) -> None:
    """spec: filter-by-frontmatter#Booleans and null compare by name"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text(f"---\n{key}: {value}\n---\n")
    assert rendered(["--where", f"{key}={value}", "a.md"]) == "a.md"


def test_unparsable_frontmatter_is_a_non_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """spec: filter-by-frontmatter#Unparsable frontmatter is a non-match"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("---\nname: &n x\nalias: *n\n---\n")
    monkeypatch.setattr("sys.argv", ["surf", "--where", "name=x", "a.md", "-v"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "a.md: frontmatter not parsed (anchor), skipped\n"


def test_filter_that_narrows_to_one_file_prints_no_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """spec: multiple-files#Filter that narrows to one file prints no header"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("---\nkind: note\n---\n## Overview\nA text.\n")
    (tmp_path / "b.md").write_text("---\nkind: draft\n---\n## Overview\nB text.\n")
    assert rendered(["--where", "kind=note", "-s", "Overview", "a.md", "b.md"]) == rendered(
        ["a.md", "Overview"]
    )


@pytest.mark.parametrize(
    ("snippet", "reason"),
    [
        ("name: &n x\nalias: *n", "anchor"),
        ("name: |\n  text", "block scalar"),
        ("name: >\n  text", "block scalar"),
        ("name: {b: 1}", "flow map"),
    ],
    ids=["anchor or alias", "block scalar |", "block scalar >", "flow map"],
)
def test_rejected_yaml_constructs_make_the_file_a_non_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    snippet: str,
    reason: str,
) -> None:
    """spec: frontmatter-grammar#Rejected YAML constructs make the file a non-match"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text(f"---\n{snippet}\n---\n")
    monkeypatch.setattr("sys.argv", ["surf", "--where", "name=x", "a.md", "-v"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"a.md: frontmatter not parsed ({reason}), skipped\n"


def test_skill_family_list_membership(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: filter-by-frontmatter#List values match on membership"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "fixture.md").write_text("---\nmetadata:\n  skill-family: [tooling]\n---\n")
    assert rendered(["--where", "metadata.skill-family=tooling", "fixture.md"]) == "fixture.md"


def test_malformed_where_token_is_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("# A\n")
    monkeypatch.setattr("sys.argv", ["surf", "--where", "nope", "a.md"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == "Error: --where requires KEY=VALUE.\n"


def test_where_then_frontmatter_is_byte_for_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("---\nkind: note\n---\nbody\n")
    output = rendered(["-f", "--where", "kind=note", "a.md"])
    assert output == "---\nkind: note\n---"
    assert output.startswith("---")
    assert "YamlMap" not in output


def test_where_on_pdf_is_silent_non_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    write_outline_pdf(tmp_path / "doc.pdf", page_count=1)
    monkeypatch.setattr("sys.argv", ["surf", "--where", "kind=note", "doc.pdf", "-v"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_where_on_tex_without_fence_is_silent_non_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "doc.tex").write_text("\\section{Hi}\n")
    monkeypatch.setattr("sys.argv", ["surf", "--where", "kind=note", "doc.tex", "-v"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_parser_where_clauses() -> None:
    converted = options_from_namespace(
        build_parser().parse_args(
            ["--where", "metadata.family=skill-authoring", "--where", "kind=note", "a.md"]
        )
    )
    assert isinstance(converted, CliOptions)
    assert converted.file_refs == (FileRef("a.md"),)
    assert converted.heading_path is None
    assert converted.where_clauses == (
        WhereClause(key_path=("metadata", "family"), expected="skill-authoring"),
        WhereClause(key_path=("kind",), expected="note"),
    )


def test_reversed_positionals_name_a_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """spec: command-line#Reversed positionals name a missing file"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "file.md").write_text("## My Heading\nbody\n")
    monkeypatch.setattr("sys.argv", ["surf", "My Heading", "file.md"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == "Error: File not found: My Heading\n"


def test_no_target(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """spec: errors-and-exit-codes#No target"""
    monkeypatch.setattr("sys.argv", ["surf"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == "Error: no target specified. Use surf --help for usage.\n"


def test_full_map_is_the_map(tmp_path: Path) -> None:
    """spec: file-map#Full map is the map"""
    path = tmp_path / "about.md"
    path.write_text("# Title\n\nProgressive context disclosure lives in the body.\n")
    assert rendered(["--full", str(path)]) == rendered([str(path)])
    assert "Progressive context disclosure" not in rendered(["--full", str(path)])


def test_frontmatter_of_a_file_without_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """spec: frontmatter-only#Frontmatter of a file without YAML"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "noyaml.md").write_text("# T\n")
    monkeypatch.setattr("sys.argv", ["surf", "-f", "noyaml.md"])
    main()
    captured = capsys.readouterr()
    assert captured.out == "\n"
    assert captured.err == ""


def test_wikilink_without_a_heading_is_the_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """spec: link-targets#Wikilink without a heading is the map"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "about.md").write_text("---\ntitle: About\n---\n# Surf\n\nbody\n")
    assert rendered(["[[about]]"]) == rendered(["about.md"])


def test_markdown_link_with_a_heading_extracts_that_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """spec: link-targets#Markdown link with a heading extracts that section"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "about.md").write_text("# Surf\n\n## Overview\n\nThe overview.\n")
    output = rendered(["[text](about.md#Overview)"])
    assert output.startswith("## Overview")


def test_frontmatter_then_the_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spec: section-extraction#Frontmatter then the section"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "guide.md").write_text("---\ntitle: Guide\ntags: [cli, docs]\n---\n## Install\npip\n")
    output = rendered(["guide.md", "Install", "--full"])
    assert output.startswith("---\ntitle: Guide\ntags: [cli, docs]\n---\n## Install")


def test_last_section_carries_the_document_end(tmp_path: Path) -> None:
    """spec: tex-addressing#Last section carries the document end"""
    (tmp_path / "part.tex").write_text("\\section{From Part}\npart body\n")
    (tmp_path / "main.tex").write_text("\\input{part}\n\\end{document}\n")
    output = rendered([str(tmp_path / "main.tex"), "From Part"])
    assert output.endswith(r"\end{document}")


def test_indented_code_and_bold_labels_are_not_headings(tmp_path: Path) -> None:
    """spec: what-counts-as-a-heading#Indented code and bold labels are not headings"""
    path = tmp_path / "ind.md"
    path.write_text("# T\n\n    # not a heading\n\n**Bold:** not a heading\n\n## Real\n")
    assert rendered(["--list", str(path)]) == "- T\n  - Real"


def test_any_utf8_file_is_addressed_as_markdown(tmp_path: Path) -> None:
    """spec: what-counts-as-a-heading#Any UTF-8 file is addressed as markdown"""
    path = tmp_path / "notes.txt"
    path.write_text("# Notes\n\n## Real\n")
    assert rendered(["--list", str(path)]) == "- Notes\n  - Real"

