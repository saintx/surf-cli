---
feature: What counts as a heading
status: shipped
verified-against: "0.7.1"
---
# What counts as a heading

On markdown, a heading is an ATX heading, a line that starts with one to six `#` characters and a space, outside a fenced code block. Bold text is not a heading. Indented code is not a heading.

```gherkin
Feature: What counts as a heading
  On markdown, a heading is an ATX heading, a line that starts with one to six "#"
  characters and a space, outside a fenced code block. Bold text is not a heading.
  Indented code is not a heading.
```

## ATX headings inside fenced code blocks are ignored

Fixed in 0.7.1: a `#` line inside a fence is code.

```gherkin
Scenario: ATX headings inside fenced code blocks are ignored
  Given the fixture file "fenced.md", whose "## Real" section holds a fenced block containing "# Not a heading", followed by a section "## After"
  When I run "surf fenced.md --list"
  Then stdout is:
    """
    - Doc
      - Real
      - After
    """
```

## Fenced heading text is returned inside its section

```gherkin
Scenario: Fenced heading text is returned inside its section
  Given the fixture file "fenced.md", whose "## Real" section holds a fenced block containing "# Not a heading"
  When I run "surf fenced.md Real"
  Then stdout contains "# Not a heading"
```

## Fence rules follow CommonMark

```gherkin
Scenario Outline: Fence rules follow CommonMark
  Given a file "fence.md" whose body contains <construct>
  When I run "surf fence.md --list"
  Then stdout <verdict> "<heading>"

  Examples:
    # the shorter inner fence does not close the outer one
    | construct                                                   | heading | verdict        |
    | a ```` fence enclosing a ``` fence that encloses "# Inner"  | Inner   | does not list  |
    | a ~~~ fence enclosing "### Tilde"                           | Tilde   | does not list  |
    | a fence that is never closed, followed by "## Later"        | Later   | does not list  |
    # a backtick fence's info string may not contain a backtick, so this line is not a fence
    | the line "``` not `a` fence" followed by "## Heading"       | Heading | lists          |
```

## Indented code and bold labels are not headings

```gherkin
Scenario: Indented code and bold labels are not headings
  Given the fixture file "ind.md" containing:
    """
    # T

        # not a heading

    **Bold:** not a heading

    ## Real
    """
  When I run "surf ind.md --list"
  Then stdout is:
    """
    - T
      - Real
    """
```

## Any UTF-8 file is addressed as markdown

```gherkin
Scenario: Any UTF-8 file is addressed as markdown
  Given the fixture file "notes.txt" with headings "# Notes" and "## Real"
  When I run "surf notes.txt --list"
  Then stdout is:
    """
    - Notes
      - Real
    """
```

## A byte-order mark does not hide the first heading

```gherkin
Scenario: A byte-order mark does not hide the first heading
  Given a file "bom.tex" whose first bytes are the UTF-8 BOM followed by "\section{Related Work}"
  When I run "surf bom.tex --list"
  Then stdout is "- Related Work"
```

## Extract of a BOM-prefixed section drops the BOM

```gherkin
Scenario: Extract of a BOM-prefixed section drops the BOM
  Given a file "bom.tex" whose first bytes are the UTF-8 BOM followed by "\section{Related Work}"
  When I run "surf bom.tex 'Related Work'"
  Then stdout begins with "\section{Related Work}"
  And stdout does not begin with the BOM
```

## TeX commands in a markdown file are text

```gherkin
Scenario: TeX commands in a markdown file are text
  Given a file "sample.md" containing:
    """
    \section{Not a heading}
    \input{child}
    # Real
    """
  And a file "child.md" containing "# Secret"
  When I run "surf sample.md --list"
  Then stdout is "- Real"
```
