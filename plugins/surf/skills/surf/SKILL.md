---
description: Use instead of Read to skim markdown, TeX, or PDF files. Progressive
  context disclosure by heading or outline. See `surf --help` for usage.
name: surf
metadata:
  author:
    name: Alexander R. Saint Croix
    github_username: saintx
    email: alex@saintx.us
    twitter: alexsaintx
  surf-version: "0.7.0"
---

# Surf: Progressive Context Disclosure

Extract a markdown heading, TeX section, or PDF outline item via `surf` without loading the rest of the file. Default `surf ~/path/to/file.md` (no heading) is the file map, not the body.

## Load units (section routing)

Resolve with `surf` against the section heading; do not bulk-ingest a whole reference for one fact.

### About / orientation

| Intent | Section extraction |
|--------|--------------------|
| Overview | `surf references/about.md "Overview"` |
| When to use | `surf references/about.md "When to use"` |

### Usage

| Intent | Section extraction |
|--------|--------------------|
| Default: file map | `surf references/usage.md "Default: file map"` |
| Frontmatter only | `surf references/usage.md "Frontmatter only"` |
| Heading tree only | `surf references/usage.md "Heading tree only"` |
| Targeted section | `surf references/usage.md "Targeted section"` |
| TeX | `surf references/usage.md "TeX"` |
| PDF | `surf references/usage.md "PDF"` |
| Level | `surf references/usage.md "Level"` |
| Wikilink and link input | `surf references/usage.md "Wikilink and link input"` |
| Batch scanning | `surf references/usage.md "Batch scanning"` |
| Platform aggregation (batch section extraction) | `surf references/usage.md "Platform aggregation (batch section extraction)"` |
| Additional options | `surf references/usage.md "Additional options"` |

### Whitepaper (TeX and PDF examples)

The same paper ships as `references/surf.tex` and `references/surf.pdf`; both list the same tree, so any row below works against either file.

| Intent | Section extraction |
|--------|--------------------|
| List a TeX paper's sections | `surf references/surf.tex --list` |
| List a PDF's outline | `surf references/surf.pdf --list` |
| Read the abstract | `surf references/surf.tex "abstract"` |
| Why surf exists | `surf references/surf.pdf "Background"` |
| What a thin index looks like | `surf references/surf.tex "A Thin Index Shaped by Intent"` |
| Who composes context | `surf references/surf.pdf "Agentic Context Composition"` |
| Check a skill mechanically | `surf references/surf.tex "Skills You Can Check"` |
| Compose indexes across skills | `surf references/surf.pdf "Indexes over Indexes"` |
| Formats and corpora surf addresses | `surf references/surf.tex "Markdown, TeX, and PDF"` |
| How the paper checks itself | `surf references/surf.pdf "This Paper"` |
