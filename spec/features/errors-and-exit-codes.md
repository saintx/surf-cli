---
feature: Errors and exit codes
status: shipped
verified-against: "0.7.1"
---
# Errors and exit codes

Exit 0 on success, including "no structural index"; 1 when the address is not found or the file cannot be read as its format; 2 on usage errors and missing files.

```gherkin
Feature: Errors and exit codes
  Exit 0 on success, including "no structural index"; 1 when the address is not
  found or the file cannot be read as its format; 2 on usage errors and missing files.
```

## No target

```gherkin
Scenario: No target
  When I run "surf" with no arguments
  Then stderr is "Error: no target specified. Use surf --help for usage."
  And the exit status is 2
```

## Heading not found

```gherkin
Scenario: Heading not found
  Given the fixture file "guide.md", which has no heading "Nope"
  When I run "surf guide.md Nope"
  Then stderr is 'Error: heading "Nope" not found in guide.md.'
  And the exit status is 1
```

## Missing file

```gherkin
Scenario: Missing file
  Given no file named "nope.md" exists
  When I run "surf nope.md"
  Then stderr is "Error: File not found: nope.md"
  And the exit status is 2
```

## Unreadable PDF

The PDF library prints its own warnings first; the error line is surf's.

```gherkin
Scenario: Unreadable PDF
  Given a file "garbage.pdf" containing "not a pdf"
  When I run "surf garbage.pdf --list"
  Then stderr contains "Error: could not read PDF: garbage.pdf"
  And stderr does not contain "Traceback"
  And the exit status is 1
```

## Directory as target

Differs today: 0.7.1 raises `IsADirectoryError` with a traceback.

```gherkin
Scenario: Directory as target
  Given "." is a directory
  When I run "surf ."
  Then stderr is "Error: . is a directory"
  And stderr does not contain "Traceback"
  And the exit status is 2
```
