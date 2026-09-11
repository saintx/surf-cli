#!/usr/bin/env python3
# scripts/spec-coverage.py
"""Which scenarios under spec/features/ are demonstrated by passing tests.

    python scripts/spec-coverage.py [--junit results.xml] [--tests 'src/surf/test_*.py'] [--strict]

Scenarios come from `surf spec/features/<slug>.md --list` for every feature file:
the H1 is the feature, each level-2 heading is a scenario, and a scenario's
address is "<slug>#<Scenario>".

A test cites the scenario it demonstrates with a docstring line:

    def test_nested_path_selects_child():
        \"\"\"spec: section-extraction#Nested path selects the child inside the named parent\"\"\"

One test may cite several scenarios, one per line. Outcomes come from pytest's
JUnit report; without --junit the script runs `uv run pytest src/surf --junitxml`
itself.

Forward check: every cited address exists in the spec (else "unknown address").
Reverse check: every scenario is cited by at least one passing test (else
"untested" or "failing"). Exit 1 on any failing or unknown; with --strict, also
on any untested.
"""

from __future__ import annotations

import argparse
import ast
import glob
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "spec" / "features"
_CITE_RE = re.compile(r"^\s*spec:\s*(.+?)\s*$")


def scenarios_from_spec() -> list[tuple[str, str, str, str]]:
    """(slug, feature name, status, scenario) in file order."""
    rows: list[tuple[str, str, str, str]] = []
    for path in sorted(FEATURES.glob("*.md")):
        slug = path.stem
        fm = subprocess.run(
            ["uv", "run", "surf", "-f", str(path)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        ).stdout
        status = next(
            (ln.split(":", 1)[1].strip() for ln in fm.splitlines() if ln.startswith("status:")),
            "?",
        )
        out = subprocess.run(
            ["uv", "run", "surf", str(path), "--list"],
            capture_output=True,
            text=True,
            check=True,
            cwd=ROOT,
        ).stdout
        feature = None
        for line in out.splitlines():
            indent = len(line) - len(line.lstrip(" "))
            text = line.strip()[2:]
            if indent == 0:
                feature = text
            elif indent == 2 and feature is not None:
                rows.append((slug, feature, status, text))
    return rows


def citations_from_tests(pattern: str) -> dict[str, list[str]]:
    cites: dict[str, list[str]] = {}
    for path in sorted(glob.glob(pattern, recursive=True)):
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        module = Path(path).stem
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test"
            ):
                doc = ast.get_docstring(node) or ""
                addrs = [m.group(1) for ln in doc.splitlines() if (m := _CITE_RE.match(ln))]
                if addrs:
                    cites[f"{module}::{node.name}"] = addrs
    return cites


def outcomes_from_junit(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        module = case.get("classname", "").split(".")[-1]
        name = case.get("name", "").split("[")[0]
        status = "passed"
        for child in case:
            if child.tag in ("failure", "error"):
                status = "failed"
            elif child.tag == "skipped":
                status = "skipped"
        key = f"{module}::{name}"
        if result.get(key) != "failed":
            result[key] = status
    return result


def run_pytest_junit() -> Path:
    tmp = Path(tempfile.mkdtemp()) / "results.xml"
    proc = subprocess.run(
        ["uv", "run", "pytest", "src/surf", "-q", f"--junitxml={tmp}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if not tmp.exists():
        sys.stderr.write("spec-coverage.py: pytest produced no JUnit report\n")
        sys.stderr.write(proc.stdout[-2000:] + proc.stderr[-2000:])
        sys.exit(2)
    return tmp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="spec-coverage.py", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument(
        "--junit", type=Path, help="pytest --junitxml report; runs pytest if omitted"
    )
    parser.add_argument(
        "--tests", default="src/surf/test_*.py", help="glob of test files to scan for citations"
    )
    parser.add_argument("--strict", action="store_true", help="also fail on untested scenarios")
    args = parser.parse_args(argv)

    rows = scenarios_from_spec()
    addresses = {f"{slug}#{scenario}" for slug, _, _, scenario in rows}
    pattern = args.tests if Path(args.tests).is_absolute() else str(ROOT / args.tests)
    cites = citations_from_tests(pattern)
    outcomes = outcomes_from_junit(args.junit or run_pytest_junit())

    by_address: dict[str, list[tuple[str, str]]] = defaultdict(list)
    unknown: list[tuple[str, str]] = []
    for test_id, addrs in cites.items():
        for addr in addrs:
            if addr in addresses:
                by_address[addr].append((test_id, outcomes.get(test_id, "not run")))
            else:
                unknown.append((test_id, addr))

    counts = {"passing": 0, "failing": 0, "untested": 0}
    per_status: dict[str, dict[str, int]] = defaultdict(
        lambda: {"passing": 0, "failing": 0, "untested": 0}
    )
    current = None
    for slug, feature, status, scenario in rows:
        if slug != current:
            current = slug
            print(f"\n{feature}  [{slug}, {status}]")
        tests = by_address.get(f"{slug}#{scenario}", [])
        if not tests:
            state = "untested"
        elif any(o == "passed" for _, o in tests) and not any(o == "failed" for _, o in tests):
            state = "passing"
        else:
            state = "failing"
        counts[state] += 1
        per_status[status][state] += 1
        mark = {"passing": "✓", "failing": "✗", "untested": "·"}[state]
        detail = ", ".join(t for t, _ in tests)
        print(f"  {mark} {scenario}" + (f"  [{detail}]" if detail else ""))

    if unknown:
        print("\nunknown addresses (cited by a test, absent from the spec):")
        for test_id, addr in unknown:
            print(f"  {test_id} -> {addr}")

    total = len(rows)
    by_status = "; ".join(
        f"{s}: {c['passing']} passing, {c['untested']} untested" for s, c in per_status.items()
    )
    print(
        f"\n{total} scenarios: {counts['passing']} passing, {counts['failing']} failing, "
        f"{counts['untested']} untested; {len(unknown)} unknown addresses ({by_status})"
    )
    bad = counts["failing"] or unknown or (args.strict and counts["untested"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
