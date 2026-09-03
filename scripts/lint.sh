#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

uv run isort src
uv run black src
uv run autoflake --remove-all-unused-imports --in-place --recursive src
uv run pyright src
uv run lint-imports --config "${PWD}/pyproject.toml"
