"""The fixture selftest: one valid spec must emit four clean sheets, and
every negative control must FAIL — with the check it names, not just any
failure.

A negative fixture is a *delta*: a few lines appended to ``valid.conf``.
The base passing first is what proves each control fails because of its own
lines and nothing else. Each delta declares the check it exercises on a
first-line comment::

    # expect: spec | bounds | collision

A check that cannot fail is worthless (issue #37), so the selftest also
fails when a control passes, fires the wrong check, or when the fixture set
stops covering all three acceptance-criteria classes (deleting a control
must not leave the run green).
"""

from __future__ import annotations

import re
from pathlib import Path

from .build import build_text
from .spec import SpecError

REQUIRED_CONTROLS = ("spec", "bounds", "collision")
_EXPECT = re.compile(r"^#\s*expect:\s*(spec|bounds|collision)\s*$")


def _verdict(text: str, path: str):
    """('spec', message) | (rule, first message) | ('pass', n_sheets)."""
    try:
        result = build_text(text, path)
    except SpecError as e:
        return "spec", str(e)
    if result.findings:
        rules = sorted({f.rule for f in result.findings})
        return ",".join(rules), str(result.findings[0])
    return "pass", result.sheets


def run(fixtures: Path, say=print) -> int:
    fails = 0
    base_path = fixtures / "valid.conf"
    base = base_path.read_text(encoding="utf-8")
    kind, detail = _verdict(base, str(base_path))
    if kind != "pass":
        say(f"FAIL [valid] the base fixture must emit four clean sheets — {kind}: {detail}")
        return 1
    missing = [s for s in ("exterior", "cutaway", "section", "exploded")
               if f"concept-{s}.svg" not in detail]
    if len(detail) != 4 or missing:
        say(f"FAIL [valid] expected the four canonical sheets, got {sorted(detail)}")
        return 1
    say(f"ok   [valid] {len(detail)} sheets: XML parses, in-bounds, no label collisions, "
        f"title block present")

    covered = set()
    negatives = sorted(fixtures.glob("neg-*.conf"))
    for neg in negatives:
        lines = neg.read_text(encoding="utf-8").splitlines()
        m = _EXPECT.match(lines[0]) if lines else None
        if not m:
            say(f"FAIL [{neg.stem}] first line must be '# expect: spec|bounds|collision'")
            fails += 1
            continue
        want = m.group(1)
        text = base.rstrip("\n") + "\n" + "\n".join(lines) + "\n"
        kind, detail = _verdict(text, f"{base_path.name}+{neg.name}")
        if kind == "pass":
            say(f"FAIL [{neg.stem}] negative control did not fire — expected a {want} failure, "
                f"the spec passed every check")
            fails += 1
        elif want not in kind.split(","):
            say(f"FAIL [{neg.stem}] fired the wrong check — expected {want}, got {kind}: {detail}")
            fails += 1
        else:
            covered.add(want)
            say(f"ok   [{neg.stem}] refused ({want}): {detail}")
    for want in REQUIRED_CONTROLS:
        if want not in covered:
            say(f"FAIL [coverage] no passing negative control exercises the {want} check")
            fails += 1
    if fails:
        say(f"concept-preview selftest: {fails} case(s) failed")
        return 1
    say(f"concept-preview selftest: valid fixture + {len(negatives)} negative controls passed")
    return 0
