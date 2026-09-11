---
feature: Section extraction
status: shipped
verified-against: "0.7.1"
---
# Section extraction

A heading returns that section, through the next heading of the same or higher level. Matching ignores case. Nested paths select a child inside a parent. `--level N` on an extract matches rank N exactly.

The fixture `guide.md` has the frontmatter block `title: Guide` and the headings `# Guide`, `## Install`, `### Usage`, `## API`, `### Usage`, `#### Examples`, with one body line under each Usage ("Install usage text.", "API usage text.") and under Examples ("Deep example.").

```gherkin
Feature: Section extraction
  A heading returns that section, through the next heading of the same or higher level.
  Matching ignores case. Nested paths select a child inside a parent.
  --level N on an extract matches rank N exactly.
  The fixture guide.md has the frontmatter block "title: Guide" and the headings
  "# Guide", "## Install", "### Usage", "## API", "### Usage", "#### Examples",
  with one body line under each Usage ("Install usage text.", "API usage text.")
  and under Examples ("Deep example.").
```

## One section, with its children

```gherkin
Scenario: One section, with its children
  Given the fixture file "guide.md"
  When I run "surf guide.md API"
  Then stdout is:
    """
    ## API

    ### Usage

    API usage text.

    #### Examples

    Deep example.
    """
  And the exit status is 0
```

## Section stops at the next heading of the same or higher level

```gherkin
Scenario: Section stops at the next heading of the same or higher level
  Given the fixture file "guide.md", in which "## API" is the next rank-2 heading after "## Install"
  When I run "surf guide.md Install"
  Then stdout is:
    """
    ## Install

    ### Usage

    Install usage text.
    """
  And stdout does not contain "## API"
```

## Bare name matches the first occurrence

```gherkin
Scenario: Bare name matches the first occurrence
  Given the fixture file "guide.md", in which "Usage" appears under Install and again under API
  When I run "surf guide.md Usage"
  Then stdout is:
    """
    ### Usage

    Install usage text.
    """
  And stdout does not contain "API usage text."
```

## Nested path selects the child inside the named parent

```gherkin
Scenario: Nested path selects the child inside the named parent
  Given the fixture file "guide.md"
  When I run "surf guide.md 'API#Usage'"
  Then stdout is:
    """
    ### Usage

    API usage text.

    #### Examples

    Deep example.
    """
  And stdout does not contain "Install usage text."
```

## Matching ignores case

```gherkin
Scenario: Matching ignores case
  Given the fixture file "references/about.md"
  When I run "surf references/about.md overview"
  Then stdout begins with "## Overview"
```

## Exact rank on extract

```gherkin
Scenario: Exact rank on extract
  Given the fixture file "guide.md", in which "Examples" exists only at rank 4
  When I run "surf guide.md Examples --level 4"
  Then stdout begins with "#### Examples"
```

## Heading at another rank is not found

```gherkin
Scenario: Heading at another rank is not found
  Given the fixture file "guide.md", in which "Usage" exists only at rank 3
  When I run "surf guide.md Usage --level 2"
  Then stderr is 'Error: heading "Usage" not found in guide.md.'
  And the exit status is 1
```

## Heading line omitted

```gherkin
Scenario: Heading line omitted
  Given the fixture file "guide.md"
  When I run "surf guide.md API --no-heading"
  Then stdout is:
    """

    ### Usage

    API usage text.

    #### Examples

    Deep example.
    """
```

## Frontmatter then the section

```gherkin
Scenario: Frontmatter then the section
  Given the fixture file "guide.md"
  When I run "surf guide.md Install --full"
  Then stdout begins with:
    """
    ---
    title: Guide
    tags: [cli, docs]
    ---
    ## Install
    """
```

## Output written to a file

```gherkin
Scenario: Output written to a file
  Given the fixture file "references/about.md"
  When I run "surf references/about.md Overview -o out.md"
  Then the file "out.md" begins with "## Overview"
  And stdout is empty
```
