---
feature: Multiple files
status: shipped
verified-against: "0.8.0"
---
# Multiple files

With `-f`, `--list`, `-s HEADING`, or `--where` present, every positional is a file. `-s HEADING` is the section flag: extract HEADING from each file. With no mode flag, `surf TARGET [HEADING]` is unchanged. When two or more files produce output, each result is printed under a `==> path <==` header; when exactly one file produces output, it is printed as the single-file form prints it. `-v` names each skipped file on stderr.

```gherkin
Feature: Multiple files
  With -f, --list, -s HEADING, or --where present, every positional is a file.
  -s HEADING is the section flag: extract HEADING from each file.
  With no mode flag, surf TARGET [HEADING] is unchanged.
  When two or more files produce output, each result is printed under a
  "==> path <==" header; when exactly one file produces output, it is printed
  as the single-file form prints it. -v names each skipped file on stderr.
```

## Section flag names the heading

```gherkin
Scenario: Section flag names the heading
  Given a file "a.md" containing:
    """
    ## Overview
    A text.
    """
  And a file "b.md" containing:
    """
    ## Overview
    B text.
    """
  When I run "surf -s Overview a.md b.md"
  Then stdout is:
    """
    ==> a.md <==
    ## Overview
    A text.

    ==> b.md <==
    ## Overview
    B text.
    """
  And the exit status is 0
```

## Single file prints no header

```gherkin
Scenario: Single file prints no header
  Given a file "a.md" containing:
    """
    ## Overview
    A text.
    """
  When I run "surf -s Overview a.md"
  Then stdout equals the output of "surf a.md Overview"
```

## Filter that narrows to one file prints no header

```gherkin
Scenario: Filter that narrows to one file prints no header
  Given a file "a.md" containing:
    """
    ---
    kind: note
    ---
    ## Overview
    A text.
    """
  And a file "b.md" containing:
    """
    ---
    kind: draft
    ---
    ## Overview
    B text.
    """
  When I run "surf --where kind=note -s Overview a.md b.md"
  Then stdout equals the output of "surf a.md Overview"
```

## Frontmatter across files

`surf -f a.md b.md` today prints a.md's frontmatter block and ignores b.md. This changes.

```gherkin
Scenario: Frontmatter across files
  Given a file "a.md" whose frontmatter block is "title: A"
  And a file "b.md" whose frontmatter block is "title: B"
  When I run "surf -f a.md b.md"
  Then stdout is:
    """
    ==> a.md <==
    ---
    title: A
    ---

    ==> b.md <==
    ---
    title: B
    ---
    """
```

## Files that lack the address are skipped

A skipped file does not count as producing output, so one surviving file of two prints without a header.

```gherkin
Scenario: Files that lack the address are skipped
  Given a file "a.md" containing:
    """
    ## Overview
    A text.
    """
  And a file "c.md" containing "## Other"
  When I run "surf -s Overview a.md c.md -v"
  Then stdout equals the output of "surf a.md Overview"
  # ASSUMPTION: the skip message reads 'c.md: heading "Overview" not found, skipped'
  And stderr is 'c.md: heading "Overview" not found, skipped'
  And the exit status is 0
```

## Nothing matched

```gherkin
Scenario: Nothing matched
  Given a file "c.md" containing "## Other"
  And a file "d.md" containing "## Other"
  When I run "surf -s Overview c.md d.md"
  Then stdout is empty
  And the exit status is 1
```

## Extra arguments without a multi-file flag

```gherkin
Scenario: Extra arguments without a multi-file flag
  Given a file "a.md"
  And a file "b.md"
  And a file "c.md"
  When I run "surf a.md b.md c.md"
  Then stderr is "Error: extra arguments; use -f, --list, -s/--section, or --where to address many files."
  And the exit status is 2
```


## Per-file flags apply to each file

```gherkin
Scenario: Per-file flags apply to each file
  Given a file "a.md" whose headings are "# A", "## A2", "### A3"
  And a file "b.md" whose headings are "# B", "## B2", "### B3"
  When I run "surf --list --level 2 a.md b.md"
  Then stdout is:
    """
    ==> a.md <==
    - A
      - A2

    ==> b.md <==
    - B
      - B2
    """
```
