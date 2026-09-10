# surf

List headings, or extract one section by name, from Markdown, TeX, or PDF.

Distribution `surf-cli`. Command `surf`. Python 3.12+; pypdf is the one runtime dependency, for PDF outlines. Only the section you name is printed, so the rest of the file never enters an agent's context.

## Install

```bash
uv tool install surf-cli      # or: pipx install surf-cli, or: pip install surf-cli
surf --version
```

With Nix:

```bash
nix profile install github:saintx/surf-cli          # add ?ref=X.Y.Z to pin a release
```

## Quick start

The examples run against the reference files shipped with the agent skill:

```bash
cd plugins/surf/skills/surf/references
```

A file with no heading named returns the map: frontmatter, then the heading tree, none of the body.

```
$ surf about.md
---
metadata:
  author:
    name: Alexander R. Saint Croix
    github_username: saintx
    email: alex@saintx.us
    twitter: alexsaintx
  surf-version: "0.7.1"
---

- Surf — About
  - Overview
  - When to use
```

A heading returns that section and stops at the next heading of the same or higher level.

```
$ surf about.md "When to use"
## When to use

Invoke when skimming markdown, TeX, or PDF files, checking what a file contains, ...
```

The same two commands work on TeX, addressed by sectioning commands and the `abstract` environment, and on PDF, addressed by outline bookmarks. `surf.tex` and `surf.pdf` are one paper in two forms and list the same tree from either.

```
$ surf surf.tex --list
- abstract
- Background
- A Thin Index Shaped by Intent
- Agentic Context Composition
- Skills You Can Check
- Indexes over Indexes
- Markdown, TeX, and PDF
- This Paper

$ surf surf.tex "Markdown, TeX, and PDF"
\section{Markdown, TeX, and PDF}

surf addresses a markdown file by its ATX headings, a TeX file by its sectioning
commands and its \texttt{abstract} environment, and a PDF by its outline. ...

$ surf surf.pdf "Markdown, TeX, and PDF"
```

## Addressing

Suppose `guide.md` is:

```markdown
---
title: Guide
tags: [cli, docs]
---
# Guide

Intro paragraph.

## Install

### Usage

Install usage text.

## API

### Usage

API usage text.

#### Examples

Deep example.
```

Its map is:

```
$ surf guide.md
---
title: Guide
tags: [cli, docs]
---

- Guide
  - Install
    - Usage
  - API
    - Usage
      - Examples
```

**Get one section.** Name the heading. The section runs to the next heading of the same or higher level, so a parent brings its children.

```
$ surf guide.md "API"
## API

### Usage

API usage text.

#### Examples

Deep example.
```

**Pick between two headings with the same name.** Write the path from the parent. A bare name matches the first occurrence in the file.

```
$ surf guide.md "API#Usage"
### Usage

API usage text.

#### Examples

Deep example.
```

**List only the top N levels.** `--level N` on a listing shows ranks 1 through N.

```
$ surf guide.md --list --level 2
- Guide
  - Install
  - API
```

**Extract only at an exact level.** `--level N` on an extract matches rank N and nothing else. `Usage` exists only at rank 3, so rank 2 is not found.

```
$ surf guide.md "Examples" --level 4
#### Examples

Deep example.

$ surf guide.md "Usage" --level 2
Error: heading "Usage" not found in guide.md.
```

**Use a link as the address.** Obsidian wikilinks and markdown links resolve directly, `#` segments included.

```bash
surf "[[guide#API#Usage]]"
surf "[API](guide.md#API)"
```

**Frontmatter only, or headings only.** `-f` prints the YAML block and nothing else. `--list` prints the tree and no YAML. `--full` prints the YAML and then the named section.

```bash
surf -f guide.md
surf --list guide.md
surf guide.md "Install" --full
```

**Drop the heading line, or write to a file.**

```bash
surf guide.md "API" --no-heading
surf guide.md "API" -o api.md
```

**What counts as a heading.** On markdown, the ATX heading text. On TeX, the brace title of a sectioning command, plus `abstract` for the abstract environment; `\input` and `\include` of `.tex` files expand relative to the file you name, while graphics, comments, shell pipes, absolute paths, `..` segments, and macro-built paths do not. On PDF, an outline bookmark title; the extract is the page text from that bookmark to the next, and when the next bookmark shares a page, that page is included. Rank 1 is `#` on markdown, the shallowest sectioning command in the TeX file (`\section` in an article), and the outline's top rank on PDF.

Matching ignores case. `surf guide` resolves to `guide.md`; `.tex` and `.pdf` need their suffix. Any other UTF-8 file is addressed as ATX markdown.

**When there is nothing to address.** A file with no headings, or a PDF with no outline, prints `no structural index` and line and byte counts (page and byte counts on PDF), and exits 0. A heading that is not there exits 1 with `Error: heading "X" not found in guide.md.` A missing file or bad usage exits 2.

**Scan a directory.** Frontmatter across many files, no body loaded:

```bash
ls docs/*.md | xargs -I {} surf -f {}
```

`surf --help` lists every flag.

## Agent skill

`plugins/surf` packages a skill that teaches an agent how to use surf. It carries a Claude Code manifest, an Agent Plugins 1.0.0 manifest, and the skill itself at `plugins/surf/skills/surf`, in the Agent Skills format that Claude Code, Codex, Gemini CLI, Cursor, and Grok Build read. The skill shells out to `surf`, so install the CLI first.

Claude Code installs it from the marketplace in this repo:

```bash
claude plugin marketplace add saintx/surf-cli
claude plugin install surf@surf-cli
```

Any harness that reads a skills directory takes a copy:

```bash
cp -R plugins/surf/skills/surf ~/.agents/skills/surf
```

This checkout links `.agents/skills/surf`, `.claude/skills/surf`, and `.grok/skills/surf` into the plugin, so an agent working in the repo already has it.

The paper in `plugins/surf/skills/surf/references/surf.pdf` (also `surf.tex`) is about what surf can be used to build. surf itself is the primitive.

## Contributing

Development setup, tests, and lint are in [CONTRIBUTING.md](https://github.com/saintx/surf-cli/blob/main/CONTRIBUTING.md). The release procedure is in [RELEASING.md](https://github.com/saintx/surf-cli/blob/main/RELEASING.md).

## License

[MIT](https://github.com/saintx/surf-cli/blob/main/LICENSE).
