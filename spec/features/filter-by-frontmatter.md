---
feature: Filter by frontmatter
status: proposed
target: "0.8.0"
---
# Filter by frontmatter

Proposed for 0.8.0. `--where KEY=VALUE` keeps files whose parsed frontmatter block matches. Repeatable and conjunctive. With no other mode flag, prints matching paths. `-v` names each skipped file on stderr.

```gherkin
Feature: Filter by frontmatter
  --where KEY=VALUE keeps files whose parsed frontmatter block matches.
  Repeatable and conjunctive. With no other mode flag, prints matching paths.
  -v names each skipped file on stderr.
```

## Paths that match

```gherkin
Scenario: Paths that match
  Given files "one.md", "two.md", and "three.md" whose frontmatter block is "metadata:\n  family: skill-authoring"
  And a file "other.md" whose frontmatter block is "metadata:\n  family: navigation"
  When I run "surf --where metadata.family=skill-authoring one.md two.md three.md other.md"
  Then stdout is:
    """
    one.md
    two.md
    three.md
    """
  And the exit status is 0
```

## Filter then extract

```gherkin
Scenario: Filter then extract
  Given a file "one.md" containing:
    """
    ---
    metadata:
      family: skill-authoring
    ---
    ## Overview
    One.
    """
  And a file "two.md" containing:
    """
    ---
    metadata:
      family: skill-authoring
    ---
    ## Overview
    Two.
    """
  And a file "other.md" containing:
    """
    ---
    metadata:
      family: navigation
    ---
    ## Overview
    Other.
    """
  When I run "surf --where metadata.family=skill-authoring -s Overview one.md two.md other.md"
  Then stdout is:
    """
    ==> one.md <==
    ## Overview
    One.

    ==> two.md <==
    ## Overview
    Two.
    """
```

## Dotted keys walk nested maps

```gherkin
Scenario: Dotted keys walk nested maps
  Given a file "a.md" whose frontmatter block is:
    """
    ---
    metadata:
      author:
        github_username: saintx
    ---
    """
  When I run "surf --where metadata.author.github_username=saintx a.md"
  Then stdout is "a.md"
```

## List values match on membership

```gherkin
Scenario: List values match on membership
  Given a file "a.md" whose frontmatter block is:
    """
    ---
    metadata:
      family: [skill-authoring, navigation]
    ---
    """
  When I run "surf --where metadata.family=navigation a.md"
  Then stdout is "a.md"
```

## Value absent from a list is a non-match

```gherkin
Scenario: Value absent from a list is a non-match
  Given a file "a.md" whose frontmatter block is:
    """
    ---
    metadata:
      family: [skill-authoring, navigation]
    ---
    """
  When I run "surf --where metadata.family=nope a.md"
  Then stdout is empty
  And the exit status is 1
```

## Repeated --where filters are conjunctive

```gherkin
Scenario: Repeated --where filters are conjunctive
  Given a file "a.md" whose frontmatter block is:
    """
    ---
    metadata:
      family: [navigation]
      mixins: [overview]
    ---
    """
  When I run "surf --where metadata.family=navigation --where metadata.mixins=overview a.md"
  Then stdout is "a.md"
```

## One failing --where rejects the file

```gherkin
Scenario: One failing --where rejects the file
  Given a file "a.md" whose frontmatter block is:
    """
    ---
    metadata:
      family: [navigation]
      mixins: [overview]
    ---
    """
  When I run "surf --where metadata.family=navigation --where metadata.mixins=nope a.md"
  Then stdout is empty
  And the exit status is 1
```

## Booleans and null compare by name

```gherkin
Scenario Outline: Booleans and null compare by name
  Given a file "a.md" whose frontmatter block is "<key>: <value>"
  When I run "surf --where <key>=<value> a.md"
  Then stdout is "a.md"

  Examples:
    | key                      | value |
    | disable-model-invocation | true  |
    | enabled                  | false |
    | owner                    | null  |
```

## Unparsable frontmatter is a non-match

```gherkin
Scenario: Unparsable frontmatter is a non-match
  Given a file "a.md" whose frontmatter block is:
    """
    ---
    name: &n x
    alias: *n
    ---
    """
  When I run "surf --where name=x a.md -v"
  Then stdout is empty
  # ASSUMPTION: the skip message reads "a.md: frontmatter not parsed (anchor), skipped"
  And stderr is "a.md: frontmatter not parsed (anchor), skipped"
  And the exit status is 1
```
