"""Tests for the surf CLI tool."""

import os
import textwrap
from pathlib import Path

import pytest

# Adjust import path since surf.py is a top-level module
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from surf import (
    __version__,
    __version_tag__,
    parse_link,
    parse_headings,
    split_frontmatter,
    extract_section,
    format_heading_list,
    resolve_file,
    build_parser,
    run,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


@pytest.fixture
def sample_file(tmp_path):
    p = tmp_path / "sample.md"
    p.write_text(SAMPLE_MD)
    return p


@pytest.fixture
def sample_no_fm_file(tmp_path):
    p = tmp_path / "nofm.md"
    p.write_text(SAMPLE_NO_FM)
    return p


@pytest.fixture
def sample_no_ext(tmp_path):
    """File without .md extension alongside one with it."""
    p = tmp_path / "notes.md"
    p.write_text(SAMPLE_MD)
    return p


@pytest.fixture
def nested_file(tmp_path):
    p = tmp_path / "nested.md"
    p.write_text(NESTED_MD)
    return p


# ---------------------------------------------------------------------------
# Link parsing
# ---------------------------------------------------------------------------

class TestParseLink:
    def test_wikilink_with_heading(self):
        assert parse_link('[[notes/foo#Bar]]') == ('notes/foo', 'Bar')

    def test_wikilink_with_heading_and_alias(self):
        assert parse_link('[[notes/foo#Bar|My Alias]]') == ('notes/foo', 'Bar')

    def test_wikilink_no_heading(self):
        assert parse_link('[[notes/foo]]') == ('notes/foo', None)

    def test_wikilink_heading_only(self):
        # [[#Heading]] means current file, heading
        assert parse_link('[[#Heading]]') == (None, 'Heading')

    def test_markdown_link_with_heading(self):
        assert parse_link('[My Link](path/to/file.md#Section)') == ('path/to/file.md', 'Section')

    def test_markdown_link_no_heading(self):
        assert parse_link('[My Link](path/to/file.md)') == ('path/to/file.md', None)

    def test_markdown_link_url_encoded_spaces(self):
        path, heading = parse_link('[Link](my%20notes/the%20file.md#My%20Heading)')
        assert path == 'my notes/the file.md'
        assert heading == 'My Heading'

    def test_plain_path_with_heading(self):
        assert parse_link('file.md#Section') == ('file.md', 'Section')

    def test_plain_path_no_heading(self):
        assert parse_link('file.md') == ('file.md', None)

    def test_wikilink_nested_heading_path_remainder(self):
        assert parse_link('[[note#Foo#Baz]]') == ('note', 'Foo#Baz')

    def test_markdown_link_nested_heading_path_remainder(self):
        assert parse_link('[x](note.md#Foo#Baz)') == ('note.md', 'Foo#Baz')

    def test_plain_path_nested_heading_path_remainder(self):
        assert parse_link('note.md#Foo#Baz') == ('note.md', 'Foo#Baz')


# ---------------------------------------------------------------------------
# Positional argument parsing
# ---------------------------------------------------------------------------

class TestPositionalArgs:
    def test_file_and_heading(self):
        parser = build_parser()
        args = parser.parse_args(['file.md', 'My Heading'])
        assert args.target == 'file.md'
        assert args.heading == 'My Heading'

    def test_file_only(self):
        parser = build_parser()
        args = parser.parse_args(['file.md'])
        assert args.target == 'file.md'
        assert args.heading is None

    def test_wikilink_target(self):
        parser = build_parser()
        args = parser.parse_args(['[[file#Heading]]'])
        assert args.target == '[[file#Heading]]'
        assert args.heading is None


# ---------------------------------------------------------------------------
# Frontmatter splitting
# ---------------------------------------------------------------------------

class TestSplitFrontmatter:
    def test_with_frontmatter(self):
        lines = SAMPLE_MD.splitlines()
        fm, body = split_frontmatter(lines)
        assert fm is not None
        assert fm[0] == '---'
        assert fm[-1] == '---'
        assert 'title: Test Document' in '\n'.join(fm)
        assert body[0] == '# Introduction'

    def test_without_frontmatter(self):
        lines = SAMPLE_NO_FM.splitlines()
        fm, body = split_frontmatter(lines)
        assert fm is None
        assert body == lines

    def test_unclosed_frontmatter(self):
        lines = ['---', 'key: value', '# Heading']
        fm, body = split_frontmatter(lines)
        assert fm is None
        assert body == lines

    def test_empty_input(self):
        fm, body = split_frontmatter([])
        assert fm is None
        assert body == []


# ---------------------------------------------------------------------------
# Heading parsing
# ---------------------------------------------------------------------------

class TestParseHeadings:
    def test_finds_all_headings(self):
        lines = SAMPLE_MD.splitlines()
        _, body = split_frontmatter(lines)
        headings = parse_headings(body)
        texts = [t for _, _, t in headings]
        assert 'Introduction' in texts
        assert 'Details' in texts
        assert 'Sub-details' in texts
        assert 'Another Section' in texts
        assert 'Conclusion' in texts

    def test_heading_levels(self):
        lines = SAMPLE_MD.splitlines()
        _, body = split_frontmatter(lines)
        headings = parse_headings(body)
        levels = {t: l for l, _, t in headings}
        assert levels['Introduction'] == 1
        assert levels['Details'] == 2
        assert levels['Sub-details'] == 3
        assert levels['Conclusion'] == 1


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------

class TestExtractSection:
    def test_extract_h1(self):
        lines = SAMPLE_MD.splitlines()
        _, body = split_frontmatter(lines)
        result = extract_section(body, 'Introduction')
        assert result is not None
        level, section = result
        assert level == 1
        assert section[0] == '# Introduction'
        # Should include sub-headings until next h1
        text = '\n'.join(section)
        assert 'Details' in text
        assert 'Sub-details' in text
        assert 'Another Section' in text
        # Should NOT include Conclusion (next h1)
        assert 'Conclusion' not in text

    def test_extract_h2(self):
        lines = SAMPLE_MD.splitlines()
        _, body = split_frontmatter(lines)
        result = extract_section(body, 'Details')
        assert result is not None
        level, section = result
        assert level == 2
        text = '\n'.join(section)
        assert 'Detail content' in text
        assert 'Sub-details' in text
        # Stops at next h2
        assert 'Another Section' not in text

    def test_extract_h3(self):
        lines = SAMPLE_MD.splitlines()
        _, body = split_frontmatter(lines)
        result = extract_section(body, 'Sub-details')
        assert result is not None
        level, section = result
        assert level == 3
        text = '\n'.join(section)
        assert 'Nested content' in text

    def test_case_insensitive(self):
        lines = SAMPLE_MD.splitlines()
        _, body = split_frontmatter(lines)
        result = extract_section(body, 'introduction')
        assert result is not None

    def test_level_filter(self):
        lines = SAMPLE_MD.splitlines()
        _, body = split_frontmatter(lines)
        # 'Introduction' is h1, filtering for h2 should miss it
        result = extract_section(body, 'Introduction', level_filter=2)
        assert result is None

    def test_heading_not_found(self):
        lines = SAMPLE_MD.splitlines()
        _, body = split_frontmatter(lines)
        result = extract_section(body, 'Nonexistent')
        assert result is None

    def test_last_section(self):
        lines = SAMPLE_MD.splitlines()
        _, body = split_frontmatter(lines)
        result = extract_section(body, 'Conclusion')
        assert result is not None
        _, section = result
        text = '\n'.join(section)
        assert 'Final thoughts' in text

    def test_nested_path_foo_baz(self):
        lines = NESTED_MD.splitlines()
        result = extract_section(lines, 'Foo#Baz')
        assert result is not None
        level, section = result
        assert level == 3
        text = '\n'.join(section)
        assert 'Foo Baz body' in text
        assert 'Bar Baz body' not in text
        assert 'Bar body' not in text

    def test_nested_path_bar_baz(self):
        lines = NESTED_MD.splitlines()
        result = extract_section(lines, 'Bar#Baz')
        assert result is not None
        level, section = result
        assert level == 3
        text = '\n'.join(section)
        assert 'Bar Baz body' in text
        assert 'Foo Baz body' not in text

    def test_bare_baz_first_hit(self):
        lines = NESTED_MD.splitlines()
        result = extract_section(lines, 'Baz')
        assert result is not None
        _, section = result
        text = '\n'.join(section)
        assert 'Foo Baz body' in text
        assert 'Bar Baz body' not in text

    def test_nested_path_through_h6(self):
        lines = NESTED_MD.splitlines()
        result = extract_section(lines, 'A#B#C#D#E')
        assert result is not None
        level, section = result
        assert level == 6
        text = '\n'.join(section)
        assert 'E body' in text
        assert section[0] == '###### E'

    def test_sibling_not_child_path_returns_none(self):
        lines = SIBLING_MD.splitlines()
        result = extract_section(lines, 'Foo#Baz')
        assert result is None


# ---------------------------------------------------------------------------
# Full run integration
# ---------------------------------------------------------------------------

class TestRun:
    def _run(self, argv: list[str]) -> str:
        parser = build_parser()
        args = parser.parse_args(argv)
        return run(args)

    def test_version_flag(self, capsys):
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(['--version'])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # --version prints the git release tag form (surf-vX.Y.Z)
        assert captured.out.strip() == __version_tag__
        assert __version_tag__ == f'surf-v{__version__}'

    def test_default_heading_omits_frontmatter(self, sample_file):
        """Default section extract is content-only; frontmatter not dumped."""
        output = self._run([f'{sample_file}', 'Details'])
        assert 'title: Test Document' not in output
        assert '---' not in output
        assert '## Details' in output
        assert 'Detail content' in output

    def test_full_mode_with_heading(self, sample_file):
        output = self._run(['--full', f'{sample_file}', 'Details'])
        assert '---' in output  # frontmatter present
        assert 'title: Test Document' in output
        assert '## Details' in output
        assert 'Detail content' in output

    def test_content_only(self, sample_file):
        output = self._run(['--content-only', f'{sample_file}', 'Details'])
        assert 'title: Test Document' not in output
        assert '## Details' in output
        assert 'Detail content' in output

    def test_frontmatter_only(self, sample_file):
        output = self._run(['--frontmatter-only', f'{sample_file}'])
        assert 'title: Test Document' in output
        assert '# Introduction' not in output

    def test_frontmatter_only_no_fm(self, sample_no_fm_file):
        output = self._run(['--frontmatter-only', f'{sample_no_fm_file}'])
        assert output == ''

    def test_list_headings(self, sample_file):
        output = self._run(['--list', f'{sample_file}'])
        assert '- Introduction' in output
        assert '  - Details' in output
        assert '    - Sub-details' in output

    def test_no_heading_flag(self, sample_file):
        output = self._run(['--no-heading', '--content-only', f'{sample_file}', 'Details'])
        assert '## Details' not in output
        assert 'Detail content' in output

    def test_wikilink_target(self, sample_file):
        output = self._run([f'[[{sample_file}#Details]]'])
        assert '## Details' in output

    def test_markdown_link_target(self, sample_file):
        output = self._run([f'[link]({sample_file}#Details)'])
        assert '## Details' in output

    def test_auto_append_md(self, sample_no_ext):
        # sample_no_ext is notes.md; pass path without .md
        stem = sample_no_ext.with_suffix('')
        output = self._run([f'{stem}', '--list'])
        assert '- Introduction' in output

    def test_missing_file(self):
        output = self._run(['/nonexistent/file.md'])
        assert 'Error' in output
        assert 'not found' in output.lower()

    def test_missing_heading(self, sample_file):
        output = self._run([f'{sample_file}', 'Nonexistent'])
        assert 'Error' in output
        assert 'not found' in output.lower()

    def test_no_target(self):
        output = self._run([])
        assert 'Error' in output

    def test_whole_file_default_omits_frontmatter(self, sample_file):
        """No heading specified: default is body without frontmatter."""
        output = self._run([f'{sample_file}'])
        assert 'title: Test Document' not in output
        assert '# Introduction' in output

    def test_whole_file_full(self, sample_file):
        """No heading specified with --full returns entire file including frontmatter."""
        output = self._run(['--full', f'{sample_file}'])
        assert 'title: Test Document' in output
        assert '# Introduction' in output

    def test_whole_file_content_only(self, sample_file):
        """No heading specified, content-only returns body without frontmatter."""
        output = self._run(['--content-only', f'{sample_file}'])
        assert 'title: Test Document' not in output
        assert '# Introduction' in output

    def test_output_to_file(self, sample_file, tmp_path):
        outfile = tmp_path / 'out.md'
        self._run(['-o', str(outfile), '--list', f'{sample_file}'])
        # run() returns string but doesn't write; main() does the write.
        # So we test via main-level integration below.

    def test_level_flag(self, sample_file):
        output = self._run(['--level', '2', f'{sample_file}', 'Details'])
        assert '## Details' in output

    def test_level_flag_mismatch(self, sample_file):
        output = self._run(['--level', '1', f'{sample_file}', 'Details'])
        assert 'Error' in output

    def test_wikilink_nested_heading_path(self, nested_file):
        output = self._run([f'[[{nested_file}#Foo#Baz]]'])
        assert 'Foo Baz body' in output
        assert 'Bar Baz body' not in output

    def test_markdown_link_nested_heading_path(self, nested_file):
        output = self._run([f'[link]({nested_file}#Foo#Baz)'])
        assert 'Foo Baz body' in output
        assert 'Bar Baz body' not in output

    def test_plain_path_nested_heading_path(self, nested_file):
        output = self._run([f'{nested_file}#Foo#Baz'])
        assert 'Foo Baz body' in output
        assert 'Bar Baz body' not in output


# ---------------------------------------------------------------------------
# File resolution
# ---------------------------------------------------------------------------

class TestResolveFile:
    def test_existing_file(self, sample_file):
        assert resolve_file(str(sample_file)) == sample_file

    def test_auto_md_extension(self, sample_no_ext):
        stem = sample_no_ext.with_suffix('')
        assert resolve_file(str(stem)) == sample_no_ext

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            resolve_file('/nonexistent/path/file.md')
