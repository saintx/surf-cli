# surf

Extract a markdown section by heading without loading the rest of the file.

```bash
surf path/to/file.md "Heading"
surf -l path/to/file.md
surf -f path/to/file.md
```

A heading is an address. The return value is that section through the next heading of the same or higher level. Nested paths (`Parent#Child`) distinguish same-named headings under different parents, through ATX H1–H6.

Python 3.12+. No runtime dependencies.

## Setup

```bash
nix develop
```

## Tests

```bash
pytest
```
