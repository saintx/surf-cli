---
feature: PDF addressing
status: shipped
verified-against: "0.7.1"
---
# PDF addressing

A heading is an outline bookmark title. The extract is page text from that bookmark's page to the page before the next bookmark's page; when the next bookmark is on the same page, that page is returned. Rank is the outline's native rank.

```gherkin
Feature: PDF addressing
  A heading is an outline bookmark title. The extract is page text from that
  bookmark's page to the page before the next bookmark's page; when the next
  bookmark is on the same page, that page is returned. Rank is the outline's
  native rank.
```

## Outline is the tree

```gherkin
Scenario: Outline is the tree
  Given the fixture file "references/surf.pdf", compiled from "references/surf.tex" with an outline
  When I run "surf references/surf.pdf --list"
  Then stdout equals the output of "surf references/surf.tex --list"
```

## Extract is page-granular

The text returned starts at the top of the bookmark's page, which may be mid-paragraph of the previous section.

```gherkin
Scenario Outline: Extract is page-granular
  Given the fixture file "<file>", whose page N holds the text "Page N." for every page, with bookmark "Alpha" on page <alpha page> and "Beta" on page <beta page>
  When I run "surf <file> Alpha"
  Then stdout is "<expected>"

  Examples:
    | file     | alpha page | beta page | expected         |
    | doc.pdf  | 1          | 3         | Page 1.\nPage 2. |
    | same.pdf | 1          | 1         | Page 1.          |
```

## PDF without an outline

```gherkin
Scenario: PDF without an outline
  Given the fixture file "nooutline.pdf", a one-page PDF with no outline
  When I run "surf nooutline.pdf"
  Then stdout is:
    """
    no structural index
    pages: 1
    bytes: 451
    """
  And the exit status is 0
```

## Rank is the outline's native rank

```gherkin
Scenario: Rank is the outline's native rank
  Given the fixture file "deep.pdf", whose outline nests seven deep with "Deep" at rank 7 on a page holding the text "Deep text."
  When I run "surf deep.pdf Deep --level 7"
  Then stdout is "Deep text."
```

## Wrong rank on a PDF bookmark is not found

```gherkin
Scenario: Wrong rank on a PDF bookmark is not found
  Given the fixture file "deep.pdf", whose outline nests seven deep with "Deep" at rank 7
  When I run "surf deep.pdf Deep --level 1"
  Then stderr is 'Error: heading "Deep" not found in deep.pdf.'
  And the exit status is 1
```

## Markdown-only flags are no-ops on PDF

```gherkin
Scenario Outline: Markdown-only flags are no-ops on PDF
  Given the fixture file "parent.pdf", with bookmark "Parent" on a page holding the text "Parent text."
  When I run "surf parent.pdf Parent <flag>"
  Then stdout is "Parent text."

  Examples:
    | flag         |
    | --no-heading |
    | --full       |
```
