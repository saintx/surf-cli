# Contributing to surf

How to get a working tree, run the tests, and pass lint. The release procedure is in [RELEASING.md](https://github.com/saintx/surf-cli/blob/main/RELEASING.md).

## Environment

Python 3.12+ and [uv](https://docs.astral.sh/uv/). Either of these gives a shell with the dev dependencies installed:

```bash
nix develop        # python312 + uv, then uv sync
uv sync            # without Nix; the dev group is installed by default
```

Run the checkout's `surf` without installing it:

```bash
uv run surf --version
```

## Layout

```
src/surf/
  models.py        data types
  logic.py         heading trees, section extraction; pure, no I/O
  adapters.py      file reading, TeX expansion, pypdf
  orchestrator.py  CLI: argument parsing, dispatch, exit codes
  test_*.py        tests, beside the modules they cover
plugins/surf/      the agent skill and its manifests
scripts/           test.sh, lint.sh, deploy.sh
```

The layers only depend downward, and `pypdf` is confined to `adapters.py`. Four `import-linter` contracts in `pyproject.toml` enforce this, and `scripts/lint.sh` runs them.

## Tests

```bash
scripts/test.sh    # uv run pytest src/surf -q
```

Tests live in `src/surf/test_*.py` and are excluded from the wheel. The root `tests/` directory is unused.

## Lint

```bash
scripts/lint.sh
```

Runs, in order: `isort`, `black` (line length 100), `autoflake` (unused imports), `pyright` (basic mode, unused imports are errors), and `lint-imports` against the layer contracts. The first three rewrite files in place; run it before committing.

## Version

`surf --version` must agree with the version in every location listed in [RELEASING.md](https://github.com/saintx/surf-cli/blob/main/RELEASING.md). Changes that are not a release do not bump it.
