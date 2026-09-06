# surf

Extract one section of a markdown, TeX, or PDF file by its heading. The rest of the file never loads.

```bash
uv tool install surf-cli
cd plugins/surf/skills/surf/references
```

A file with no heading named returns the map, frontmatter and then headings, and none of the body:

```
$ surf about.md
---
metadata:
  author:
    name: Alexander R. Saint Croix
    github_username: saintx
    email: alex@saintx.us
    twitter: alexsaintx
  surf-version: "0.6.4"
---

- Surf — About
  - Overview
  - When to use
```

A heading returns that section and stops at the next heading of the same or higher level:

```
$ surf about.md "When to use"
## When to use

Invoke when skimming markdown, TeX, or PDF files, checking what a file contains,
listing structure, extracting a named address, or batch-scanning metadata across
a directory. See `surf --help` for CLI flags. Skip when the full body is already
needed. ...
```

The same two commands work on TeX, addressed by sectioning commands and the `abstract` environment, and on PDF, addressed by outline bookmarks. The whitepaper in this directory ships in both forms and lists the same tree from either:

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

$ surf surf.pdf "Skills You Can Check"
```

surf exists so that agent skills can be thin. The `SKILL.md` beside these files is a table of intents, each resolving to `surf path "Heading"`, over reference material the agent never reads whole. `surf.pdf` explains why the tool was built and what that pattern makes possible.

## Addressing

`surf --list file.md` is the heading tree without YAML. `surf -f file.md` is YAML only. Nested paths (`Overview#Usage`) select a child when the same name appears under different parents.

A heading is an address: ATX display text on markdown, brace title on TeX, the TeX `abstract` environment (addressed as `abstract`), or an outline bookmark title on PDF. On markdown and TeX the return value is that section through the next heading of the same or higher level. On PDF it is dest-to-next-dest page text; when the next dest is on the same page, that dest page is included.

`--level` is 1 at the top of the heading tree. On markdown that is `#`. On TeX it is the shallowest command in the file, so `--level 1` is `\section` in an article. On PDF it is the outline's native rank. Listing with `--level N` includes ranks 1 through N. Named extract uses N as an exact match.

TeX `\input` and `\include` of `.tex` files are expanded relative to the file you name. Graphics, comments, shell pipes, and macro-constructed paths are not.

If the file has no headings, or a PDF has no outline, surf prints that it has no structural index, with line and byte counts on markdown and TeX, or page and byte counts on PDF. It does not dump the body.

Python 3.12+. pypdf is the runtime dependency for PDF outline addressing.

## Agent skill

`plugins/surf` packages the skill for agents. It carries a Claude Code manifest, an Agent Plugins 1.0.0 manifest, and the skill itself at `plugins/surf/skills/surf`, in the Agent Skills format that Claude Code, Codex, Gemini CLI, Cursor, and Grok Build read.

Claude Code installs it from the marketplace in this repo:

```bash
claude plugin marketplace add saintx/surf-cli
claude plugin install surf@surf-cli
```

Any harness that reads a skills directory takes a copy of the skill:

```bash
cp -R plugins/surf/skills/surf ~/.agents/skills/surf
```

The repo also carries `.agents/skills/surf`, `.claude/skills/surf`, and `.grok/skills/surf` as symlinks into the plugin, so an agent working in this checkout has the skill available.

## Install

The distribution name is `surf-cli`. The command is `surf`. Python 3.12+.

```bash
uv tool install surf-cli
surf --version
```

```bash
pipx install surf-cli
surf --version
```

```bash
pip install surf-cli
```

### Nix

From a local clone, install the flake into the nix profile:

```bash
nix profile install "git+file://${PWD}"
surf --version
```

Pin a tagged release with `?ref=X.Y.Z`. If `surf` is already in the profile under a different flake URL, remove it first:

```bash
nix profile remove surf
nix profile install "git+file://${PWD}?ref=X.Y.Z"
```

`scripts/deploy.sh` syncs, tests, and retargets the profile at the latest local semver tag.

## Releasing

Version locations, the bump checklist, tagging, and nix profile deployment are in [RELEASING.md](RELEASING.md).

## Development

```bash
nix develop
```

## Tests

```bash
scripts/test.sh    # uv run pytest src/surf
```
