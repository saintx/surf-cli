---
feature: Link targets
status: shipped
verified-against: "0.7.1"
---
# Link targets

A wikilink or markdown link is a target. The `.md` suffix is implicit for markdown; `.tex` and `.pdf` need theirs. Every scenario here runs in a working directory that holds a copy of the named fixture.

```gherkin
Feature: Link targets
  A wikilink or markdown link is a target. The .md suffix is implicit for markdown;
  .tex and .pdf need theirs.
```

## Wikilink with a heading extracts that section

```gherkin
Scenario: Wikilink with a heading extracts that section
  Given a copy of the fixture file "references/about.md" at "about.md" in the working directory
  When I run "surf '[[about#Overview]]'"
  Then stdout begins with "## Overview"
```

## Wikilink without a heading is the map

```gherkin
Scenario: Wikilink without a heading is the map
  Given a copy of the fixture file "references/about.md" at "about.md" in the working directory
  When I run "surf '[[about]]'"
  Then stdout equals the output of "surf about.md"
```

## Markdown link with a heading extracts that section

```gherkin
Scenario: Markdown link with a heading extracts that section
  Given a copy of the fixture file "references/about.md" at "about.md" in the working directory
  When I run "surf '[text](about.md#Overview)'"
  Then stdout begins with "## Overview"
```

## Nested path inside a link

```gherkin
Scenario: Nested path inside a link
  Given a copy of the fixture file "guide.md" at "guide.md" in the working directory
  When I run "surf '[[guide#API#Usage]]'"
  Then stdout begins with "### Usage"
  And stdout contains "API usage text."
  And stdout does not contain "Install usage text."
```

## Implicit .md suffix

```gherkin
Scenario: Implicit .md suffix
  Given a copy of the fixture file "references/about.md" at "about.md" in the working directory
  When I run "surf about Overview"
  Then stdout begins with "## Overview"
```
