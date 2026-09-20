# fusecheck fixtures

The fixture surface behind `scripts/fusecheck-check.sh --selftest` (run by
`check.sh`): a tiny two-pose design and the manifests that drive the REAL
fusecheck runner over it, so the `assert` bound grammar — legacy `<min>`,
two-sided `<min> <max>`, `=N` — plus the malformed-line and exit-4 hard-fail
paths are proven to fire (issue #627).

- `fixtures.scad` — `part = "separable"` renders two gap-separated cubes
  (2 bodies); `part = "fused"` renders two face-sharing cubes (1 body);
  `assembled` is the ungated default. Plain cubes on purpose: the body count
  must stay 2 / 1 at any curve quality.
- `pass-legacy.fusecheck` — legacy floor and `=N` rows that must pass.
- `warn-legacy.fusecheck` — a floor the fused fixture cannot meet: the too-few
  exit (3) must WARN and the run must continue, never hard-fail.
- `pass-twosided.fusecheck` — `MIN MAX` with the count inside the bound.
- `fail-abovemax.fusecheck` — the count above the max: the too-many exit (4)
  must hard-FAIL, never downgrade to a WARN.
- `fail-malformed.fusecheck` — `max < min` and a non-numeric operand: the line
  itself must FAIL the manifest parse.

The selftest re-measures the fixtures' body counts with `fusecheck` itself
before trusting any manifest row — if the geometry ever drifts from the
numbers these manifests assume, the selftest says so instead of gating on a
stale expectation. This directory is selftest-only: no design gates against
it, and it never enters a release bundle.
