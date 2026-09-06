---
metadata:
  author:
    name: Alexander R. Saint Croix
    github_username: saintx
    email: alex@saintx.us
    twitter: alexsaintx
  surf-version: "0.6.4"
---
# Surf Usage

`surf` extracts a markdown heading, a TeX section, or a PDF outline item.

Name a heading to get that section. `--full` with a named heading prints YAML frontmatter, then that section. `--full` without a heading is the file map. Neither form prints the whole file.

## Default: file map

```bash
surf ~/path/to/file.md
```

No heading. This is the file map: YAML frontmatter if present, then the heading list. It does not print the body.

If there is no frontmatter, you get the heading list only. If there are no headings and no YAML, you get `no structural index` and a size line. Markdown and TeX print lines and bytes. PDF prints pages and bytes. The same command on a `.tex` or `.pdf` file prints that file's heading or outline list, not the body.

`surf` with no file path exits 2. It prints `Error: no target specified. Use surf --help for usage.`

## Frontmatter only

```bash
surf -f ~/path/to/file.md
```

Returns YAML frontmatter. No body. No heading list. Use this to read YAML metadata. PDF has no YAML, so this prints nothing.

## Heading tree only

```bash
surf --list ~/path/to/file.md
```

Returns the heading hierarchy. No YAML. Use this when you want headings and not frontmatter.

## Targeted section

```bash
surf ~/path/to/file.md "<heading text>"
```

Returns content under the matched heading, down to the next same-or-higher-level heading. Nested paths (`Parent#Child`) select a child inside that parent.

On markdown, the address is the heading text after the `#` marks. On TeX, the address is the title in braces. The TeX `abstract` environment is addressed as `abstract`. On PDF, the address is the outline bookmark title.

Heading match ignores case.

## TeX

```bash
surf ~/path/to/file.tex
surf --list ~/path/to/file.tex
surf ~/path/to/file.tex "Heading"
```

Address is the brace title. The `abstract` environment is addressed as `abstract`. `\input` and `\include` expand `.tex` files relative to the file you named. They do not expand graphics, comments, shell pipes, or paths built by macros. They also skip absolute paths, `..` path segments, and files that are not `.tex`.

## PDF

```bash
surf ~/path/to/file.pdf
surf --list ~/path/to/file.pdf
surf ~/path/to/file.pdf "Heading"
```

Address is the outline bookmark title. The extract is the page text from this bookmark to the next bookmark. If the next bookmark is on the same page, that page is included. Listing the outline does not print page text.

## Level

`--level 1` is the top rank. On markdown, rank 1 is `#`. A file whose first heading is `##` needs `--level 2` to list it. On TeX, rank 1 is the shallowest command in that file. In an article that starts at `\section`, `--level 1` is `\section`. On PDF, rank 1 is the top outline rank.

`--list --level N` prints ranks 1 through N. A named heading with `--level N` matches only a heading at rank N.

## Wikilink and link input

`surf` accepts wikilinks and markdown links as targets:

```bash
surf "[[path/to/file]]"
surf "[[path/to/file#Heading]]"
```

```bash
surf "[Text](path/to/file.md#Heading)"
```

A wikilink with no `#Heading` is the file map, not the full page. A wikilink with `#Heading` extracts that section. A markdown link with a `#Heading` extracts that section. A markdown link with no `#Heading` is the file map.

The `.md` extension is implicit. `surf ~/path/to/file` resolves to `~/path/to/file.md`. `.tex` and `.pdf` need the suffix.

## Batch scanning

Scan YAML across a directory without loading any body:

```bash
ls ~/path/to/*.md | xargs -I {} surf -f {}
```

Same pattern on nested trees:

```bash
ls ~/path/to/*/file.md | xargs -I {} surf -f {}
```

## Platform aggregation (batch section extraction)

Print the path, then one heading, for each matching file:

```bash
find ~/path/to -path '*/subdir/file.md' | sort \
  | xargs -I{} sh -c 'echo "### {}" && surf {} "Some Heading" && echo'
```

Change the `find` root, the path glob, and the heading text to match the files you have.

## Additional options

| Flag | Effect |
|------|--------|
| no heading | File map (YAML if any, then headings or outline). Not the body. |
| heading, no flag | Section content without frontmatter |
| `--list` | Heading tree only |
| `-f` / `--frontmatter-only` | YAML only |
| `--full` | With a named heading: YAML frontmatter, then that section. Without a heading: the file map. |
| `--content-only` / `--body-only` | Same as a named heading with no flag. This is the default extract. |
| `--level N` | List: ranks 1 through N. Extract: exact rank N. |
| `--no-heading` | Omit the heading line from section output |
| `-o <file>` | Write output to a file. |
