---
feature: File map
status: shipped
verified-against: "0.7.1"
---
# File map

A file named with no heading returns its map: the frontmatter block if present, then the heading tree, and none of the body.

```gherkin
Feature: File map
  A file named with no heading returns its map: the frontmatter block if present,
  then the heading tree, and none of the body.
```

## Map of a markdown file with frontmatter

The default call shows both halves of the map and nothing else. The first body line of `references/about.md` is "Progressive context disclosure".

```gherkin
Scenario: Map of a markdown file with frontmatter
  Given the fixture file "references/about.md", whose first body line begins "Progressive context disclosure"
  When I run "surf references/about.md"
  Then stdout begins with the frontmatter block, from its opening "---" through its closing "---"
  And stdout ends with:
    """
    - Surf — About
      - Overview
      - When to use
    """
  And stdout does not contain "Progressive context disclosure"
  And the exit status is 0
```

## Map of a file without frontmatter

With no frontmatter block the map is the heading tree alone.

```gherkin
Scenario: Map of a file without frontmatter
  Given the fixture file "nofm.md" containing:
    """
    # Readme

    Intro text.

    ## Install
    """
  When I run "surf nofm.md"
  Then stdout is:
    """
    - Readme
      - Install
    """
  And stdout does not contain "Intro text."
  And the exit status is 0
```

## Map of a TeX or PDF file

The same call on TeX or PDF prints the section list or outline, never the body.

```gherkin
Scenario Outline: Map of a TeX or PDF file
  Given the fixture file "<file>"
  When I run "surf <file>"
  Then stdout is:
    """
    - abstract
    - Background
    - A Thin Index Shaped by Intent
    - Agentic Context Composition
    - Skills You Can Check
    - Indexes over Indexes
    - Markdown, TeX, and PDF
    - This Paper
    """
  And the exit status is 0

  Examples:
    | file                |
    | references/surf.tex |
    | references/surf.pdf |
```

## Full map is the map

`--full` with no heading is the default map, not the whole file.

```gherkin
Scenario: Full map is the map
  Given the fixture file "references/about.md", whose first body line begins "Progressive context disclosure"
  When I run "surf --full references/about.md"
  Then stdout equals the output of "surf references/about.md"
  And stdout does not contain "Progressive context disclosure"
```
