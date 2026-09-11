---
feature: TeX addressing
status: shipped
verified-against: "0.7.1"
---
# TeX addressing

A heading is the brace title of a sectioning command, or `abstract` for the abstract environment. `\input` and `\include` of `.tex` files expand relative to the named file.

```gherkin
Feature: TeX addressing
  A heading is the brace title of a sectioning command, or "abstract" for the
  abstract environment. \input and \include of .tex files expand relative to
  the named file.
```

## Sections and the abstract are addresses

```gherkin
Scenario: Sections and the abstract are addresses
  Given the fixture file "main.tex" containing:
    """
    \documentclass{article}
    \begin{document}
    \begin{abstract}
    Abs text.
    \end{abstract}
    \section{Intro}
    Body.
    \input{part}
    \end{document}
    """
  And the fixture file "part.tex" containing:
    """
    \section{From Part}
    Part body.
    """
  When I run "surf main.tex --list"
  Then stdout is:
    """
    - abstract
    - Intro
    - From Part
    """
```

## Abstract extract begins at its environment

```gherkin
Scenario: Abstract extract begins at its environment
  Given the fixture file "main.tex", whose abstract environment holds "Abs text."
  When I run "surf main.tex abstract"
  Then stdout is:
    """
    \begin{abstract}
    Abs text.
    \end{abstract}
    """
```

## Title forms that become addresses

Starred commands count. An optional short title is ignored and the long title is the address. A title wrapped across lines is joined. Commented commands, `\begin{figure}`, and `\sectioning` are not headings, so a file holding only one of them has no structural index.

```gherkin
Scenario Outline: Title forms that become addresses
  Given a file "t.tex" containing <source> followed by the line "body"
  When I run "surf t.tex --list"
  Then stdout begins with "<first line>"
  And stdout does not contain "<absent>"

  Examples:
    | source                               | first line                | absent        |
    | \\section*{Starred}                  | - Starred                 | body          |
    | \\section[Short]{Long Title}         | - Long Title              | Short         |
    | \\section{Wrapped Title\nContinued}  | - Wrapped Title Continued | body          |
    | % \\section{Commented}               | no structural index       | Commented     |
    | \\begin{figure}                      | no structural index       | figure        |
    | \\sectioning{Not a heading}          | no structural index       | Not a heading |
```

## Wrapped title is dropped whole by --no-heading

```gherkin
Scenario: Wrapped title is dropped whole by --no-heading
  Given a file "w.tex" containing:
    """
    \section{Wrapped Title
    Continued}
    Body.
    """
  When I run "surf w.tex 'Wrapped Title Continued' --no-heading"
  Then stdout begins with "Body."
```

## Included files expand

```gherkin
Scenario: Included files expand
  Given a file "master.tex" containing:
    """
    \section{Main}
    \input{part}
    """
  And a file "part.tex" containing:
    """
    \section{From Part}
    Part body.
    """
  When I run "surf master.tex --list"
  Then stdout is:
    """
    - Main
    - From Part
    """
```

## Included section extracts with its body

```gherkin
Scenario: Included section extracts with its body
  Given a file "master.tex" containing:
    """
    \section{Main}
    \input{part}
    """
  And a file "part.tex" containing:
    """
    \section{From Part}
    Part body.
    """
  When I run "surf master.tex 'From Part'"
  Then stdout begins with "\section{From Part}"
  And stdout contains "Part body."
```

## What does not expand

```gherkin
Scenario Outline: What does not expand
  Given a file "main.tex" containing the line <line>
  And a file "<trap file>" containing "\section{Hidden}"
  When I run "surf main.tex --list"
  Then stdout does not contain "Hidden"

  # ASSUMPTION: an absolute path is never opened, so no trap file is created for that row
  Examples:
    | line                       | trap file      |
    | % \\input{hidden}          | hidden.tex     |
    | \\includegraphics{hidden}  | hidden.tex     |
    | \\input{/abs/hidden}       | (none)         |
    | \\input{../hidden}         | ../hidden.tex  |
    | \\input{hidden.pdf}        | hidden.pdf     |
    | \\input{\\macro}           | hidden.tex     |
    | \\input{\|shell}           | hidden.tex     |
```

## Extract stops at the next command of the same or higher rank

```gherkin
Scenario: Extract stops at the next command of the same or higher rank
  Given the fixture file "references/surf.tex", in which "\section{A Thin Index Shaped by Intent}" follows "\section{Background}"
  When I run "surf references/surf.tex Background"
  Then stdout begins with "\section{Background}"
  And stdout contains "Three approaches to giving a language model context have a defect in common."
  And stdout does not contain "\section{A Thin Index Shaped by Intent}"
```

## Last section carries the document end

The final section of a file runs to the end of the file, so it includes `\end{document}`. This is current behavior, recorded rather than endorsed.

```gherkin
Scenario: Last section carries the document end
  Given the fixture file "main.tex", whose last section "From Part" comes from an \input file
  When I run "surf main.tex 'From Part'"
  Then stdout ends with "\end{document}"
```
