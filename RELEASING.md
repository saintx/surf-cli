# Releasing surf

How a version of surf is deployed to a nix profile, versioned, tagged, and pushed.

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

## Versioning

Version is semver (`X.Y.Z`). Git tags are the same string, and `surf --version` prints `surf X.Y.Z`. The version is written in these places, and all of them must agree:

| Location | Field |
|----------|-------|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `flake.nix` | `version = "X.Y.Z";` in `packages.default` |
| `src/surf/__init__.py` | `__version__ = "X.Y.Z"` |
| `plugins/surf/plugin.json` | `"version": "X.Y.Z"` |
| `plugins/surf/.claude-plugin/plugin.json` | `"version": "X.Y.Z"` |
| `.claude-plugin/marketplace.json` | `"version": "X.Y.Z"` twice: `metadata.version` and the `surf` plugin entry |
| `plugins/surf/skills/surf/SKILL.md` | `surf-version: "X.Y.Z"` in the frontmatter |
| `plugins/surf/skills/surf/references/about.md` | `surf-version: "X.Y.Z"` in the frontmatter |
| `plugins/surf/skills/surf/references/usage.md` | `surf-version: "X.Y.Z"` in the frontmatter |
| `README.md` | the `surf about.md` output at the top of the README repeats the `about.md` frontmatter |

The `.grok-plugin/marketplace.json` entry carries no version field.

Before tagging, confirm nothing still carries the old version:

```bash
grep -rn 'OLD_VERSION' --exclude-dir=.git --exclude-dir=.venv --exclude=uv.lock --exclude=surf.pdf .
```

Bump the version everywhere above, then:

```bash
git add pyproject.toml flake.nix src/surf/__init__.py plugins .claude-plugin README.md
git commit -m "Bump version to X.Y.Z"
git tag X.Y.Z
scripts/deploy.sh
git push origin X.Y.Z
```

`scripts/deploy.sh` runs uv sync, tests, and a nix profile rebuild against the new tag. Pushing the tag is what lets another environment install that version.
