---
feature: Frontmatter grammar
status: shipped
verified-against: "0.8.0"
---
# Frontmatter grammar

For `--where`, surf parses a block-style YAML subset with no runtime dependency. The "Supported" scenarios are parser-conformance checks run only in development, against PyYAML; the "Rejected" scenarios are observable at the command line.

```gherkin
Feature: Frontmatter grammar
  For --where, surf parses a block-style YAML subset with no runtime dependency.
  The "Supported" scenarios are parser-conformance checks run only in development,
  against PyYAML; the "Rejected" scenarios are observable at the command line.
```

## Supported YAML constructs parse as PyYAML does

```gherkin
Scenario Outline: Supported YAML constructs parse as PyYAML does
  Given a file whose frontmatter block is "<snippet>"
  When surf parses that frontmatter block
  Then surf's parsed value equals PyYAML safe_load of the same block

  Examples:
    | construct                                   | snippet                       |
    | nested maps by indentation                  | a:\n  b: 1                    |
    | block lists with "- "                       | a:\n  - x\n  - y              |
    | flow lists like "[a, b]"                    | a: [x, y]                     |
    | quoted scalars                              | a: "x y"                      |
    | bare scalars                                | a: x                          |
    | a plain scalar folded across indented lines | a: one\n  two                 |
    | true, false, and null                       | a: true\nb: false\nc: null    |
    | integers                                    | a: 42                         |
    | "#" comments                                | a: x # note                   |
```

## Rejected YAML constructs make the file a non-match

```gherkin
Scenario Outline: Rejected YAML constructs make the file a non-match
  Given a file "a.md" whose frontmatter block is "<snippet>"
  When I run "surf --where name=x a.md -v"
  Then stdout is empty
  # ASSUMPTION: the skip message reads "a.md: frontmatter not parsed (<reason>), skipped"
  And stderr is "a.md: frontmatter not parsed (<reason>), skipped"
  And the exit status is 1

  Examples:
    | construct          | snippet                | reason       |
    | an anchor or alias | name: &n x\nalias: *n  | anchor       |
    | a block scalar "\|" | name: \|\n  text       | block scalar |
    | a block scalar ">" | name: >\n  text        | block scalar |
    | a flow map         | name: {b: 1}           | flow map     |
```
