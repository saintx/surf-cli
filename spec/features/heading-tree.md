---
feature: Heading tree
status: shipped
verified-against: "0.7.1"
---
# Heading tree

`--list` prints the heading tree without the frontmatter block. `--level N` on a listing shows ranks 1 through N.

```gherkin
Feature: Heading tree
  --list prints the heading tree without the frontmatter block.
  --level N on a listing shows ranks 1 through N.
```

## Tree without frontmatter

```gherkin
Scenario: Tree without frontmatter
  Given the fixture file "references/about.md"
  When I run "surf --list references/about.md"
  Then stdout is:
    """
    - Surf — About
      - Overview
      - When to use
    """
  And stdout contains no "---" line
  And the exit status is 0
```

## Listing limited to the top N ranks

```gherkin
Scenario: Listing limited to the top N ranks
  Given the fixture file "guide.md", whose headings are:
    """
    # Guide
    ## Install
    ### Usage
    ## API
    ### Usage
    #### Examples
    """
  When I run "surf guide.md --list --level 2"
  Then stdout is:
    """
    - Guide
      - Install
      - API
    """
```

## Listing indents a heading by its rank

A lone `###` heading is listed at rank 3 indentation.

```gherkin
Scenario: Listing indents a heading by its rank
  Given the fixture file "bug-fix.md" whose only heading is "### Bug fix"
  When I run "surf bug-fix.md --list"
  Then stdout is "    - Bug fix"
```

## Rank 1 is the top of the tree

On markdown rank 1 is `#`; a file whose first heading is `###` shows nothing at `--level 1`.

```gherkin
Scenario: Rank 1 is the top of the tree
  Given the fixture file "bug-fix.md" whose only heading is "### Bug fix"
  When I run "surf bug-fix.md --list --level 1"
  Then stdout is empty
```

## Rank 1 on TeX is the shallowest command in the file

```gherkin
Scenario: Rank 1 on TeX is the shallowest command in the file
  Given the fixture file "article.tex" containing:
    """
    \section{Introduction}
    intro
    \subsection{Child}
    child
    \section{Related Work}
    related
    """
  When I run "surf article.tex --list --level 1"
  Then stdout is:
    """
    - Introduction
    - Related Work
    """
  And stdout does not contain "Child"
```
