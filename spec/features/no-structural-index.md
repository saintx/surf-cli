---
feature: No structural index
status: shipped
verified-against: "0.7.1"
---
# No structural index

A file with nothing to address says so, with its size, and never dumps the body.

```gherkin
Feature: No structural index
  A file with nothing to address says so, with its size, and never dumps the body.
```

## Markdown with no headings

```gherkin
Scenario: Markdown with no headings
  Given the fixture file "x.md" containing:
    """
    plain text
    no headings
    """
  When I run "surf x.md"
  Then stdout is:
    """
    no structural index
    lines: 2
    bytes: 23
    """
  And the exit status is 0
```

## Frontmatter but no headings

The map keeps the frontmatter block.

```gherkin
Scenario: Frontmatter but no headings
  Given the fixture file "notes.md" containing:
    """
    ---
    title: YAML Only
    ---
    Just prose.
    """
  When I run "surf notes.md"
  Then stdout is:
    """
    ---
    title: YAML Only
    ---
    """
  And stdout does not contain "Just prose."
```

## Tree of a frontmatter-only file is empty

```gherkin
Scenario: Tree of a frontmatter-only file is empty
  Given the fixture file "notes.md", whose frontmatter block is "title: YAML Only" and whose body is the single line "Just prose."
  When I run "surf notes.md --list"
  Then stdout is:
    """
    no structural index
    lines: 4
    bytes: 37
    """
```

## TeX with no sectioning commands

```gherkin
Scenario: TeX with no sectioning commands
  Given the fixture file "macros.tex" containing:
    """
    \newcommand{\foo}{bar}
    \newcommand{\foo}{bar}
    \newcommand{\foo}{bar}
    """
  When I run "surf macros.tex"
  Then stdout is:
    """
    no structural index
    lines: 3
    bytes: 69
    """
```
