---
feature: Command line
status: shipped
verified-against: "0.7.1"
---
# Command line

The grammar of a call. The first positional is the target, a file path or a link; the second, when present, is the heading to extract.

```gherkin
Feature: Command line
  The first positional is the target, a file path or a link.
  The second, when present, is the heading to extract.
```

## Version flag prints the installed version

```gherkin
Scenario: Version flag prints the installed version
  When I run "surf --version"
  Then stdout is "surf " followed by the installed version number
  And that version number has the form MAJOR.MINOR.PATCH
  And the exit status is 0
```

## Positionals are target then heading

The order shows in the output: the first argument is opened, the second is looked up in it.

```gherkin
Scenario: Positionals are target then heading
  Given a file "file.md" containing:
    """
    # Doc

    ## My Heading

    Body.
    """
  When I run "surf file.md 'My Heading'"
  Then stdout begins with "## My Heading"
```

## Reversed positionals name a missing file

```gherkin
Scenario: Reversed positionals name a missing file
  Given a file "file.md" with a section "## My Heading"
  And no file named "My Heading" exists
  When I run "surf 'My Heading' file.md"
  Then stderr is "Error: File not found: My Heading"
  And the exit status is 2
```
