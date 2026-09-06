# surf

Extract a markdown or TeX section by heading without loading the rest of the file.

```bash
surf path/to/file.md "Heading"
surf -l path/to/file.md
surf -f path/to/file.md
surf -l path/to/file.tex
surf path/to/file.tex "Heading"
```

A heading is an address: ATX display text on markdown, brace title on TeX. The return value is that section through the next heading of the same or higher level. Nested paths (`Parent#Child`) distinguish same-named headings under different parents.

TeX `\input` and `\include` of `.tex` files are expanded relative to the file you name. Graphics, comments, shell pipes, and macro-constructed paths are not.

## Install

Packaged as a nix flake. The `surf` CLI is installed globally via nix profile.

Requires Nix with flakes, and SSH access to the private repository `git@github.com:saintx/surf-cli.git`.

```bash
nix profile install 'git+ssh://git@github.com:saintx/surf-cli.git'
surf --version
```

That tracks the default branch (most recent commit). To pin a tagged release, list tags and append `?ref=X.Y.Z`:

```bash
git ls-remote --tags git@github.com:saintx/surf-cli.git
nix profile install 'git+ssh://git@github.com:saintx/surf-cli.git?ref=X.Y.Z'
surf --version
```

If no tags are listed, use the default-branch install above. Version is semver (`X.Y.Z`); `surf --version` prints `surf X.Y.Z`.

From a local clone, use a `git+file` URL, or run `scripts/deploy.sh` to sync, test, and install the latest local semver tag:

```bash
git clone git@github.com:saintx/surf-cli.git
cd surf-cli
nix profile install "git+file://${PWD}?ref=X.Y.Z"
surf --version
```

If `surf` is already in the profile under a different flake URL, remove it first:

```bash
nix profile remove surf
nix profile install 'git+ssh://git@github.com:saintx/surf-cli.git?ref=X.Y.Z'
```

## Deployment

```bash
scripts/deploy.sh            # sync + test + install latest local semver tag
nix profile upgrade surf     # rebuild the currently installed flake URL
surf --version               # verify
```

`nix profile upgrade surf` rebuilds whatever flake URL is already in the profile. It does not follow a newly created tag. After tagging, retarget the profile (or run `scripts/deploy.sh`, which does this):

```bash
nix profile remove surf
nix profile install "git+file://${PWD}?ref=X.Y.Z"
surf --version
```

### Releasing

Version is semver (`X.Y.Z`) and is defined in three places that must stay in sync:

- `pyproject.toml` — `version = "x.y.z"`
- `flake.nix` — `version = "x.y.z"`
- `src/surf/__init__.py` — `__version__ = "x.y.z"`

Git tags are the same string. `surf --version` prints `surf X.Y.Z`.

Bump version in those three files, then:

```bash
git add pyproject.toml flake.nix src/surf/__init__.py
git commit -m "Bump version to x.y.z"
git tag x.y.z
scripts/deploy.sh
git push origin x.y.z
```

`scripts/deploy.sh` runs uv sync, tests, and a nix profile rebuild against the new tag. Pushing the tag is what lets another environment install that version.

## Development

```bash
nix develop
```

## Tests

```bash
scripts/test.sh    # uv run pytest src/surf
```
