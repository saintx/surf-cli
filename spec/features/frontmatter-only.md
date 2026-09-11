---
feature: Frontmatter only
status: shipped
verified-against: "0.7.1"
---
# Frontmatter only

`-f` prints the frontmatter block verbatim and nothing else. surf does not parse it.

```gherkin
Feature: Frontmatter only
  -f prints the frontmatter block verbatim and nothing else. surf does not parse it.
```

## Frontmatter of a markdown file

```gherkin
Scenario: Frontmatter of a markdown file
  Given the fixture file "references/about.md", whose first body line begins "Progressive context disclosure"
  When I run "surf -f references/about.md"
  Then stdout is the frontmatter block from its opening "---" through its closing "---"
  And stdout does not contain "- Surf — About"
  And stdout does not contain "Progressive context disclosure"
  And the exit status is 0
```

## Frontmatter of a file without YAML

An empty answer is an answer.

```gherkin
Scenario: Frontmatter of a file without YAML
  Given the fixture file "noyaml.md" whose first line is "# T"
  When I run "surf -f noyaml.md"
  Then stdout is a single empty line
  And the exit status is 0
```

## Frontmatter of a PDF

PDF has no frontmatter block, so `-f` prints nothing.

```gherkin
Scenario: Frontmatter of a PDF
  Given the fixture file "references/surf.pdf"
  When I run "surf -f references/surf.pdf"
  Then stdout is a single empty line
  And the exit status is 0
```

## Frontmatter block is echoed, not parsed

The bytes out are the bytes in.

```gherkin
Scenario: Frontmatter block is echoed, not parsed
  Given a file "folded.md" whose frontmatter block is:
    """
    ---
    description: Use instead of Read to skim files. Progressive
      disclosure by heading or outline.
    name: surf
    ---
    """
  When I run "surf -f folded.md"
  Then stdout is:
    """
    ---
    description: Use instead of Read to skim files. Progressive
      disclosure by heading or outline.
    name: surf
    ---
    """
```
