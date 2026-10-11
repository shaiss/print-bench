#!/usr/bin/env bash
# cog-check.sh — the gate-facing half of the CoG / tip-over stability check
# (issue #623): runs tools/cogcheck on a design's ci.cog manifest and re-emits
# its verdict as gate.sh's line shapes.
#
# The repo can prove a part prints; it could not prove an assembled object
# STANDS. Two heavy spheres cantilevered high on thin stalks over a low airy
# truss slices, scores 100/100, and tips over on a desk bump. tools/cogcheck
# measures the assembled object — mesh-derived CoG per part (volume-weighted
# tetrahedron decomposition), densities and non-printed masses from the
# manifest, support footprint as the convex hull of the contact geometry —
# and this wrapper maps that verdict onto the gate:
#
#   ok    cogcheck <name>: ...   the CoG projection clears the footprint
#   warn  cogcheck <name>: ...   TIP RISK — advisory, does NOT fail the gate
#   FAIL  cogcheck <name>: ...   the manifest/mesh is broken — a check that
#                                cannot run is not a check (hard fail)
#
# The WARN tier is the fusecheck precedent: a tip risk is a design call to
# look at, not a gate failure; promoting it to blocking is a separate human
# decision. gate.sh additionally enforces that every part: basename names an
# STL the gate actually rendered (a CoG computed on a stale or unsliced mesh
# proves nothing) — that check needs the gate's rendered-STL list, so it
# lives there, not here.
#
#   ./scripts/cog-check.sh <name>       check designs/<name>/ci.cog
#   ./scripts/cog-check.sh --selftest   prove the verdict discriminates: a
#                                       stable configuration passes AND one
#                                       whose CoG falls outside the footprint
#                                       is flagged (issue #37 — a check that
#                                       cannot fail is worthless)
set -euo pipefail

cd "$(dirname "$0")/.."

MODE="check"
name=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --selftest) MODE="selftest" ;;
    --) shift; break ;;
    -*) echo "cog-check.sh: unknown flag $1" >&2; exit 2 ;;
    *)
      if [[ -n "$name" ]]; then
        echo "cog-check.sh: only one design name allowed, got '$name' and '$1'" >&2
        echo "usage: cog-check.sh [--selftest] <name>" >&2
        exit 2
      fi
      name="$1"
      ;;
  esac
  shift
done

# The lineage.sh pattern: import the package from its src/ tree rather than
# requiring a pip install, so the check runs wherever gate.sh runs —
# stdlib-only by design (see tools/cogcheck/pyproject.toml).
run_tool() {  # <manifest> <stl-dir> — invokes the tool from its src/ tree
  env PYTHONPATH="$PWD/tools/cogcheck/src${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m cogcheck.cli "$1" --stl-dir "$2"
}

# One design's check: prints the gate lines, exits 0 for STABLE and TIP-RISK
# alike (the warn is advisory), 1 only for a broken manifest or mesh. The
# manifest/stl-dir args default to the gate's layout so the selftest can drive
# the same mapping on its fixtures.
check_design() {
  local name="$1" manifest="${2:-designs/${1}/ci.cog}" stldir="${3:-build}"
  local out rc verdict
  if [[ ! -f "$manifest" ]]; then
    # stdout, not stderr: gate.sh's log is captured with `| tee`, and a FAIL
    # the summary never sees is a FAIL nobody saw.
    echo "FAIL  cogcheck ${name}: ${manifest} not found"
    return 1
  fi
  echo "== ${name}: cogcheck (CoG / tip-over stability) =="
  # Exit 3 is a MEASURED TIP-RISK, not a tool failure — conflating the two is
  # how a tip risk ends up a hard FAIL instead of the advisory WARN it is
  # (caught by the gate-facing half of --selftest).
  rc=0
  out="$(run_tool "$manifest" "$stldir" 2>&1)" || rc=$?
  if [[ "$rc" != 0 && "$rc" != 3 ]]; then
    # Tool refused (unreadable STL, malformed manifest, unmeasurable mesh):
    # a check that cannot run is a hard FAIL, never a quiet pass.
    printf 'FAIL  cogcheck %s: %s\n' "$name" "$(printf '%s\n' "$out" | tail -1)"
    return 1
  fi
  rc=0
  verdict="$(printf '%s\n' "$out" | tail -1)"
  case "$verdict" in
    "VERDICT: STABLE — "*)
      printf 'ok    cogcheck %s: %s\n' "$name" "${verdict#VERDICT: STABLE — }" ;;
    "VERDICT: TIP-RISK — "*)
      # Advisory WARN: exit code stays 0 so the gate does not go red.
      printf 'warn  cogcheck %s: TIP RISK — %s\n' "$name" "${verdict#VERDICT: TIP-RISK — }" ;;
    *)
      printf 'FAIL  cogcheck %s: unrecognised verdict line: %s\n' "$name" "$verdict"
      rc=1 ;;
  esac
  return "$rc"
}

# Prove the verdict discriminates both ways, on synthetic fixtures (pure
# stdlib — no OpenSCAD, no slicer, no pytest): a centred 20x20x10 base is
# stable; the same base with a 4x-heavier mass cantilevered outside its
# footprint tips. Without the failing half, a regression to "always STABLE"
# would sail through every green run (issue #37).
selftest() {
  local t; t="$(mktemp -d)"; trap 'rm -rf "$t"' RETURN
  python3 - "$t" <<'PY'
import sys
from pathlib import Path

d = Path(sys.argv[1])


def box(x0, y0, z0, x1, y1, z1):
    a, b, c = (x0, y0, z0), (x1, y0, z0), (x1, y1, z0)
    dd, e, f = (x0, y1, z0), (x0, y0, z1), (x1, y0, z1)
    g, h = (x1, y1, z1), (x0, y1, z1)
    tris = [
        (a, dd, c), (a, c, b), (e, f, g), (e, g, h),
        (a, b, f), (a, f, e), (dd, h, g), (dd, g, c),
        (a, e, h), (a, h, dd), (b, c, g), (b, g, f),
    ]
    lines = ["solid base"]
    for p1, p2, p3 in tris:
        ux, uy, uz = (p2[i] - p1[i] for i in range(3))
        vx, vy, vz = (p3[i] - p1[i] for i in range(3))
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        lines.append(f"  facet normal {nx:.6f} {ny:.6f} {nz:.6f}")
        lines.append("    outer loop")
        for p in (p1, p2, p3):
            lines.append(f"      vertex {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append("endsolid base")
    (d / "base.stl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Stable: CoG dead centre, 10 mm of clearance on every side.
    (d / "stable.cog").write_text(
        "margin: 2\npart: base.stl | density: 1.24\n", encoding="utf-8"
    )
    # Tipping: base 4.96 g at x=0, boom 19.84 g at x=15 -> CoG x=12.0,
    # which is 2 mm OUTSIDE the +/-10 mm footprint.
    (d / "tipping.cog").write_text(
        "margin: 2\npart: base.stl | density: 1.24\n"
        "mass: boom | grams: 19.84 | at: 15,0,20\n",
        encoding="utf-8",
    )
    # Broken: a malformed manifest must fail loudly, not half-parse.
    (d / "broken.cog").write_text("part: base.stl\n", encoding="utf-8")


box(-10, -10, 0, 10, 10, 10)  # centred 20x20x10 base, ground at z=0
PY
  local pass=1 out rc
  out="$(run_tool "$t/stable.cog" "$t" 2>&1)" && rc=0 || rc=$?
  if [[ "$rc" == 0 && "$(printf '%s\n' "$out" | tail -1)" == "VERDICT: STABLE —"* ]]; then
    : # the stable half holds
  else
    echo "SELFTEST FAIL  the stable fixture did not pass cleanly (rc=$rc):"
    printf '%s\n' "$out" | tail -1 >&2
    pass=0
  fi
  out="$(run_tool "$t/tipping.cog" "$t" 2>&1)" && rc=0 || rc=$?
  if [[ "$rc" == 3 && "$(printf '%s\n' "$out" | tail -1)" == "VERDICT: TIP-RISK —"* ]]; then
    : # the tipping half fires
  else
    echo "SELFTEST FAIL  the out-of-footprint fixture was not flagged (rc=$rc):"
    printf '%s\n' "$out" | tail -1 >&2
    pass=0
  fi
  out="$(run_tool "$t/broken.cog" "$t" 2>&1)" && rc=0 || rc=$?
  if [[ "$rc" == 1 && "$out" == *"broken.cog:"* ]]; then
    : # the malformed manifest fails loudly, naming its file:line
  else
    echo "SELFTEST FAIL  the malformed manifest did not fail loudly (rc=$rc):"
    printf '%s\n' "$out" | tail -1 >&2
    pass=0
  fi
  # The gate-facing mapping, on the same fixtures: check_design must emit the
  # gate line shapes AND keep exit 0 for a TIP-RISK. The run_tool checks above
  # cannot catch a mix-up between "tool failed" (exit 1) and "tool measured a
  # risk" (exit 3) — that exact bug shipped the tip risk as a hard FAIL while
  # every run_tool assertion stayed green.
  local line
  out="$(check_design stable-fixture "$t/stable.cog" "$t" 2>&1)" && rc=0 || rc=$?
  line="$(printf '%s\n' "$out" | grep -E '^(ok|warn|FAIL) ' | tail -1)"
  if [[ "$rc" == 0 && "$line" == "ok    cogcheck stable-fixture: "* ]]; then
    : # the stable half maps to an ok row
  else
    echo "SELFTEST FAIL  the stable fixture did not map to an ok row (rc=$rc):"
    printf '%s\n' "$line" >&2
    pass=0
  fi
  out="$(check_design tipping-fixture "$t/tipping.cog" "$t" 2>&1)" && rc=0 || rc=$?
  line="$(printf '%s\n' "$out" | grep -E '^(ok|warn|FAIL) ' | tail -1)"
  if [[ "$rc" == 0 && "$line" == "warn  cogcheck tipping-fixture: TIP RISK — "* ]]; then
    : # the tip risk stays an advisory warn with a green exit
  else
    echo "SELFTEST FAIL  the tip risk did not map to a warn row with exit 0 (rc=$rc):"
    printf '%s\n' "$line" >&2
    pass=0
  fi
  out="$(check_design broken-fixture "$t/broken.cog" "$t" 2>&1)" && rc=0 || rc=$?
  line="$(printf '%s\n' "$out" | grep -E '^(ok|warn|FAIL) ' | tail -1)"
  if [[ "$rc" == 1 && "$line" == "FAIL  cogcheck broken-fixture: "* ]]; then
    : # the broken manifest stays a hard FAIL
  else
    echo "SELFTEST FAIL  the malformed manifest did not map to a FAIL row with exit 1 (rc=$rc):"
    printf '%s\n' "$line" >&2
    pass=0
  fi
  if [[ "$pass" == 1 ]]; then
    echo "cog-check.sh selftest OK — stable passes, out-of-footprint flags, malformed manifest fails loudly"
    return 0
  fi
  return 1
}

if [[ "$MODE" == "selftest" ]]; then
  selftest
  exit $?
fi

if [[ -z "$name" ]]; then
  echo "usage: cog-check.sh [--selftest] <name>" >&2
  exit 2
fi

check_design "$name"
