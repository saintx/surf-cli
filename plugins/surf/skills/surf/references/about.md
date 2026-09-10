---
metadata:
  author:
    name: Alexander R. Saint Croix
    github_username: saintx
    email: alex@saintx.us
    twitter: alexsaintx
  surf-version: "0.7.1"
---
# Surf — About

## Overview

Progressive context disclosure — extract a heading, TeX section, or PDF outline item without loading the rest of the file. Default `surf ~/path/to/file.md` (no heading) is the file map: YAML (if present) plus the heading list, not the body. Same default on `.tex` and `.pdf`: the heading or outline list, or `no structural index` when there is none. Then `-f`, `--list`, or a heading for one index or one section. Wikilink resolution, batch metadata scanning, and batch section extraction across a directory. Use instead of Read to skim markdown, TeX, or PDF files.

## When to use

Invoke when skimming markdown, TeX, or PDF files, checking what a file contains, listing structure, extracting a named address, or batch-scanning metadata across a directory. See `surf --help` for CLI flags. Skip when the full body is already needed. Do not skip `.tex` or `.pdf`. Other existing UTF-8 files are addressed as ATX markdown. Do not use `surf ~/path/to/file.md` with no heading as a substitute for Read.
