# test_orchestrator.py
"""Orchestrator composition tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PageObject

from surf import __version__
from surf.models import CliFailure
from surf.orchestrator import build_parser, main, run_argv
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
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f"surf {__version__}"


def test_extract_details(sample_file: Path) -> None:
    output = rendered([str(sample_file), "Details"])
    assert "title: Test Document" not in output
    assert "## Details" in output
    assert "Detail content" in output


def test_no_heading_does_not_dump(sample_file: Path) -> None:
    output = rendered([str(sample_file)])
    assert "title: Test Document" in output
    assert "- Introduction" in output
    assert "Detail content" not in output
    assert "intro" not in output.splitlines()


def test_list_level_filters_markdown_as_max_depth(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text("# Introduction\n\n## Details\n\n### Sub-details\n")
    output = rendered(["--list", "--level", "2", str(path)])
    assert output.splitlines() == ["- Introduction", "  - Details"]
    assert "Sub-details" not in output


def test_list_level_1_markdown_is_hash_not_hashhash(sample_file: Path) -> None:
    output = rendered(["--list", "--level", "1", str(sample_file)])
    assert output.splitlines() == ["- Introduction"]


def test_markdown_hashhash_only_still_needs_level_2(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("## Details\n\nbody\n")
    assert "Details" not in rendered(["--list", "--level", "1", str(path)])
    assert rendered(["--list", "--level", "2", str(path)]).splitlines() == ["  - Details"]


def test_list_headings(sample_file: Path) -> None:
    output = rendered(["--list", str(sample_file)])
    assert "- Introduction" in output
    assert "  - Details" in output
    assert "title:" not in output


def test_frontmatter_only(sample_file: Path) -> None:
    output = rendered(["-f", str(sample_file)])
    assert "title: Test Document" in output
    assert "- Introduction" not in output
    assert "Detail content" not in output


def test_nested_path(nested_file: Path) -> None:
    output = rendered([f"[[{nested_file}#Foo#Baz]]"])
    assert "Foo Baz body" in output
    assert "Bar Baz body" not in output


def test_missing_file() -> None:
    output = rendered(["/nonexistent/file.md"])
    assert "Error" in output
    assert "not found" in output.lower()


def test_output_to_file(sample_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outfile = tmp_path / "out.md"
    monkeypatch.setattr(
        "sys.argv",
        ["surf", "-o", str(outfile), "--list", str(sample_file)],
    )
    main()
    assert outfile.exists()
    assert "- Introduction" in outfile.read_text()


def test_parser_positional() -> None:
    args = build_parser().parse_args(["file.md", "My Heading"])
    assert args.target == "file.md"
    assert args.heading == "My Heading"


def test_tex_list_headings(tex_file: Path) -> None:
    output = rendered(["--list", str(tex_file)])
    lines = output.splitlines()
    assert "- What this corpus is" in lines
    assert "  - A subsection" in lines
    assert "- Sibling" in lines
    assert "corpus body" not in output


def test_tex_extract_named_section(tex_file: Path) -> None:
    output = rendered([str(tex_file), "What this corpus is"])
    assert r"\section{What this corpus is}" in output
    assert "corpus body" in output
    assert r"\section{Sibling}" not in output
    assert "sibling body" not in output


def test_tex_missing_heading(tex_file: Path) -> None:
    result = run_argv([str(tex_file), "No such heading"])
    assert isinstance(result, CliFailure)
    assert result.exit_code == 1
    assert "not found" in result.message


def test_tex_no_heading_returns_index(tex_file: Path) -> None:
    output = rendered([str(tex_file)])
    assert output != ""
    assert "- What this corpus is" in output.splitlines()
    assert "  - A subsection" in output.splitlines()
    assert "corpus body" not in output
    assert "sibling body" not in output


def test_md_suffix_keeps_atx_not_tex_commands(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text(MD_WITH_TEX_COMMAND)
    output = rendered(["--list", str(path)])
    assert "- Real" in output.splitlines()
    assert "Not a heading" not in output


def test_tex_bom_prefixed_list_and_extract(tmp_path: Path) -> None:
    path = tmp_path / "bom.tex"
    path.write_bytes(b"\xef\xbb\xbf\\section{Related Work}\nbody\n")
    listed = rendered(["--list", str(path)])
    assert "Related Work" in listed
    extracted = rendered([str(path), "Related Work"])
    assert not extracted.startswith("\ufeff")
    assert r"\section{Related Work}" in extracted
    assert "body" in extracted


def test_tex_list_level_filters_to_sections(tex_file: Path) -> None:
    output = rendered(["--list", "--level", "1", str(tex_file)])
    assert "What this corpus is" in output
    assert "Sibling" in output
    assert "A subsection" not in output


def test_tex_extract_level_1_hits_section_not_subsection(tex_file: Path) -> None:
    output = rendered(["--level", "1", str(tex_file), "What this corpus is"])
    assert "corpus body" in output
    assert "sub body" in output
    missing = run_argv(["--level", "2", str(tex_file), "What this corpus is"])
    assert isinstance(missing, CliFailure)


def test_tex_article_level_1_lists_section_not_empty(tmp_path: Path) -> None:
    """0.4.2 stored \\section at rank 3, so --level 1 printed nothing."""
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
    (tmp_path / "secret.tex").write_text("\\section{Secret}\n")
    master = tmp_path / "main.tex"
    master.write_text("% \\input{secret}\n\\section{Visible}\n")
    listed = rendered(["--list", str(master)])
    assert "Visible" in listed
    assert "Secret" not in listed


def test_tex_includegraphics_is_not_expanded(tmp_path: Path) -> None:
    (tmp_path / "fig.tex").write_text("\\section{Not a figure}\n")
    master = tmp_path / "main.tex"
    master.write_text("\\includegraphics{fig}\n\\section{Here}\n")
    listed = rendered(["--list", str(master)])
    assert listed.splitlines() == ["- Here"]


def test_tex_missing_input_keeps_other_headings(tmp_path: Path) -> None:
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
    (tmp_path / "child.md").write_text("# Secret\n")
    path = tmp_path / "sample.md"
    path.write_text("\\input{child}\n# Real\n")
    listed = rendered(["--list", str(path)])
    assert listed.splitlines() == ["- Real"]


def test_tex_multiline_title_list_and_extract(tmp_path: Path) -> None:
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
    path = tmp_path / "macros.tex"
    expected = empty_index_text(path, "\\newcommand{\\foo}{bar}\n" * 3)
    listed = rendered(["--list", str(path)])
    indexed = rendered([str(path)])
    assert listed == expected
    assert indexed == expected
    assert "\\newcommand" not in listed
    assert "foo" not in listed


def test_headingless_markdown_reports_empty_index(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    expected = empty_index_text(path, "just a paragraph\nwith two lines\n")
    assert rendered(["--list", str(path)]) == expected
    assert rendered([str(path)]) == expected
    assert "just a paragraph" not in rendered([str(path)])


def test_markdown_frontmatter_without_headings_keeps_yaml_index(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("---\ntitle: YAML Only\n---\nBody without headings.\n")
    indexed = rendered([str(path)])
    assert "title: YAML Only" in indexed
    assert "Body without headings" not in indexed
    listed = rendered(["--list", str(path)])
    assert listed.splitlines()[0] == "no structural index"
    assert "Body without headings" not in listed


def test_tex_abstract_list_and_extract(tmp_path: Path) -> None:
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
    (tmp_path / "00abstract.tex").write_text("spliced abstract body\n")
    master = tmp_path / "main.tex"
    master.write_text("\\begin{abstract}\n\\input{00abstract}\n\\end{abstract}\n")
    listed = rendered(["--list", str(master)])
    assert listed.splitlines() == ["- abstract"]
    extracted = rendered([str(master), "Abstract"])
    assert "spliced abstract body" in extracted
    assert r"\begin{abstract}" in extracted


def test_tex_no_heading_drops_begin_abstract_line(tmp_path: Path) -> None:
    path = tmp_path / "paper.tex"
    path.write_text("\\begin{abstract}\nabstract body\n\\end{abstract}\n")
    output = rendered(["--no-heading", str(path), "abstract"])
    assert r"\begin{abstract}" not in output
    assert "abstract body" in output
    assert r"\end{abstract}" in output


def test_pdf_list_headings(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    write_outline_pdf(
        path,
        page_count=2,
        outline=(("Parent", 0, (("Child", 1, ()),)),),
    )
    output = rendered(["--list", str(path)])
    assert output.splitlines() == ["- Parent", "  - Child"]


def test_pdf_no_heading_lists_outline(tmp_path: Path) -> None:
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


def test_pdf_frontmatter_only_empty(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    write_outline_pdf(path, page_count=1, outline=(("Parent", 0, ()),))
    output = rendered(["-f", str(path)])
    assert output == ""


def test_pdf_garbage_is_cli_failure(tmp_path: Path) -> None:
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
    path = _nested_pdf(tmp_path)
    output = rendered([f"[[{path}#Parent#Child]]"])
    assert "first-child" in output
    assert "other-child" not in output
    assert "parent-page" not in output


def test_pdf_missing_outline_title(tmp_path: Path) -> None:
    path = _nested_pdf(tmp_path)
    result = run_argv([str(path), "NoSuch"])
    assert isinstance(result, CliFailure)
    assert result.exit_code == 1
    assert result.message == f'heading "NoSuch" not found in {path}.'


def test_pdf_no_heading_does_not_change_body(tmp_path: Path) -> None:
    path = _nested_pdf(tmp_path)
    default = rendered([str(path), "Parent"])
    no_heading = rendered(["--no-heading", str(path), "Parent"])
    assert default == no_heading
    assert "parent-page" in default


def test_pdf_full_equals_default_extract(tmp_path: Path) -> None:
    path = _nested_pdf(tmp_path)
    assert rendered(["--full", str(path), "Parent"]) == rendered([str(path), "Parent"])


def test_pdf_level_7_matches_native_outline(tmp_path: Path) -> None:
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
