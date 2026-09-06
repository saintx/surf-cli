# test_orchestrator.py
"""Orchestrator composition tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from surf import __version__
from surf.models import CliFailure
from surf.orchestrator import build_parser, main, run_argv

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


def test_list_level_filters_markdown(sample_file: Path) -> None:
    output = rendered(["--list", "--level", "2", str(sample_file)])
    assert "Details" in output
    assert "Introduction" not in output


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
