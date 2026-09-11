# surf specification

One file per feature under `features/`. Each file carries frontmatter (`feature`, `status`, and the version it was verified against or targets), an H1 with the feature name, a `Feature:` fence, and one H2 per scenario with an intent line and a `Scenario:` fence. A feature's fences concatenate into a valid `.feature` file.

Every scenario in a file marked `status: shipped` was run against surf 0.7.1 and prints what it says. A file marked `status: proposed` describes 0.8.0 and is not implemented. A scenario whose intent line says *differs today* states intended behavior 0.7.1 does not yet have.

Addresses: `surf spec/features/<slug>.md --list` lists a feature's scenarios; `surf spec/features/<slug>.md "Scenario"` returns one. The status board is `for f in spec/features/*.md; do surf -f "$f"; done` today, and `surf -f spec/features/*.md` once the proposed Multiple files feature ships. Tests cite a scenario with a docstring line `spec: <slug>#Scenario`; `python scripts/spec-coverage.py` reports which scenarios are demonstrated by passing tests.

Fixtures: `references/` means `plugins/surf/skills/surf/references/` (`about.md`, `usage.md`, `surf.tex`, `surf.pdf`, one paper as TeX and as PDF). Other files a scenario names are given in full by the scenario's `Given` steps.

| Slug | Feature | Status |
|------|---------|--------|
| command-line | Command line | shipped |
| file-map | File map | shipped |
| frontmatter-only | Frontmatter only | shipped |
| heading-tree | Heading tree | shipped |
| section-extraction | Section extraction | shipped |
| link-targets | Link targets | shipped |
| what-counts-as-a-heading | What counts as a heading | shipped |
| tex-addressing | TeX addressing | shipped |
| pdf-addressing | PDF addressing | shipped |
| no-structural-index | No structural index | shipped |
| errors-and-exit-codes | Errors and exit codes | shipped |
| multiple-files | Multiple files | proposed |
| filter-by-frontmatter | Filter by frontmatter | proposed |
| frontmatter-grammar | Frontmatter grammar | proposed |
