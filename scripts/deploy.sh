#!/usr/bin/env bash
# Deploy surf CLI to nix profile.
# Usage: ./scripts/deploy.sh [--skip-tests]
#
# Installs the latest local semver tag (X.Y.Z) via git+file so the profile
# tracks a release, not an untagged working tree. After tagging, run this
# script, then push the tag so other clones can install the same version.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SURF_ROOT="$(dirname "$SCRIPT_DIR")"

SKIP_TESTS=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--skip-tests]"
            exit 1
            ;;
    esac
done

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

success() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }

echo "╭────────────────────────────────────────╮"
echo "│           Deploying surf               │"
echo "╰────────────────────────────────────────╯"
echo ""

# Phase 1: Sync dependencies
echo "→ Phase 1: Syncing dependencies"
if (cd "$SURF_ROOT" && uv sync --quiet 2>/dev/null); then
    success "uv sync"
else
    warn "uv sync issues"
fi
echo ""

# Phase 2: Tests
if [[ "$SKIP_TESTS" == false ]]; then
    echo "→ Phase 2: Running tests"
    if [[ -x "$SURF_ROOT/scripts/test.sh" ]]; then
        if (cd "$SURF_ROOT" && ./scripts/test.sh); then
            success "pytest"
        else
            warn "tests failed — use --skip-tests to deploy anyway"
        fi
    else
        warn "scripts/test.sh not found"
    fi
    echo ""
fi

# Phase 3: Nix profile rebuild against latest (or HEAD-exact) semver tag
echo "→ Phase 3: Rebuilding nix profile"
HEAD_TAG="$(git -C "$SURF_ROOT" describe --tags --exact-match 2>/dev/null || true)"
LATEST_TAG=""
while IFS= read -r t; do
    if [[ "$t" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        LATEST_TAG="$t"
    fi
done < <(git -C "$SURF_ROOT" tag --list --sort=v:refname)
if [[ "$HEAD_TAG" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    TAG="$HEAD_TAG"
elif [[ -n "$LATEST_TAG" ]]; then
    TAG="$LATEST_TAG"
else
    TAG=""
fi

if [[ -n "$TAG" ]]; then
    FLAKE_URI="git+file://${SURF_ROOT}?ref=${TAG}"
    echo "  tag: $TAG"
else
    FLAKE_URI="git+file://${SURF_ROOT}"
    echo "  no semver tag; installing HEAD"
fi

nix profile remove surf 2>/dev/null || true
if nix profile install "$FLAKE_URI" 2>&1; then
    success "nix profile installed ($FLAKE_URI)"
else
    fail "nix profile install failed"
fi
echo ""

# Phase 4: Verify CLI from the profile binary
echo "→ Phase 4: Verifying surf"
PROFILE_BIN="${HOME}/.nix-profile/bin/surf"
if [[ -x "$PROFILE_BIN" ]]; then
    ver="$("$PROFILE_BIN" --version 2>&1)" || true
    success "$ver"
else
    warn "surf not on ${PROFILE_BIN}"
fi
echo ""

echo "╭────────────────────────────────────────╮"
echo "│            surf Deployed               │"
echo "╰────────────────────────────────────────╯"
