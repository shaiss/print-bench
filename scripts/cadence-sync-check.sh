#!/usr/bin/env bash
# Cadence-parity check: for each scheduled autonomy routine, prove the
# `cadence:` key in its .github/<routine>.conf and the `cron:` literal in
# .github/workflows/<routine>.yml still describe the SAME schedule.
#
# WHY THIS EXISTS: GitHub Actions cannot read a file or a variable for
# `on.schedule`, so every routine's cadence is stored twice — in the conf
# (the committed, reviewed source of truth) and as the cron literal Actions
# actually fires on. The conf comments say "edit both, they must stay
# identical", but nothing enforced that. A one-sided edit ships a routine
# that fires on a schedule nobody reviewed, and no gate caught it — the
# drift in PR #275 was noticed by review bots, purely by luck (issue #276).
#
# WHAT IT PROVES — AND DELIBERATELY DOES NOT:
#   ✅ PARITY: the two literals agree with each other.
#   ❌ NOT CORRECTNESS: it does not verify a cron matches the schedule the
#      surrounding prose comments describe. PR #275's original `*/4` bug had
#      both files in sync while both contradicted the documented
#      01:11/05:11/… times — this check would have passed it. Prose-vs-cron
#      drift is a separate, harder problem and out of scope here; do not
#      read a green cadence-sync as "the schedule is what the docs say".
#
# PRESETS: a conf may store a preset NAME (`hourly`, `4x`, `2x`, `daily`,
# `weekly`) while the workflow always carries the resolved cron literal, so
# the check resolves presets before comparing — a naive string compare would
# false-positive on every preset-based routine. The mapping comes from
# tools/backlog-burn's own parser (`resolve_cadence`), the single source: a
# hand-copied preset table here would rebuild this exact drift footgun inside
# the checker that exists to catch it. backlog-burn is stdlib-only, so this
# imports it straight from the source tree — no pip step ahead of check.sh.
#
# Usage:
#   scripts/cadence-sync-check.sh            # check the real files
#   scripts/cadence-sync-check.sh --selftest # prove the check passes AND fails
#
# Run by scripts/check.sh (and therefore /preflight and CI's scad-check jobs).
set -euo pipefail

cd "$(dirname "$0")/.."

# The seven scheduled routines with a `cadence:` key — the four issue #276
# named (backlog-burn, design-run, chunker, labeler) plus the three issue
# #293 added (product-scout, backlog-groomer, reeve). Keep in sync with
# those issues' tables; a routine not listed here is not checked (see the
# script header for what that means) — extend the list only with the issue
# that asks for it.
#
# reeve and backlog-groomer confs are parsed by their own tools, not by
# `backlog-burn config` — the conf READER here is the same `key: value`
# house format every one of those parsers uses (see the Python docstring
# below), not a call into the shared parser.
ROUTINES=(backlog-burn design-run chunker labeler product-scout backlog-groomer reeve adoption-assessor)

# Compare one conf/workflow pair. Prints a diagnosis and returns non-zero on
# drift. Kept as a function so --selftest can point it at fixtures.
check_pair() {
  local routine="$1" conf="$2" workflow="$3"

  [[ -f "$conf" ]]     || { echo "FAIL  cadence-sync[$routine]: $conf not found"; return 1; }
  [[ -f "$workflow" ]] || { echo "FAIL  cadence-sync[$routine]: $workflow not found"; return 1; }

  python3 - "$routine" "$conf" "$workflow" <<'PY'
"""Compare one routine's conf cadence with its workflow cron literal.

Reads the raw `cadence:` line out of the conf (the same `key: value` house
format every routine's parser uses), resolves presets via backlog_burn's
own resolve_cadence (single source of the preset→cron mapping), extracts
the schedule cron literal from the workflow, and fails loudly on drift.
"""
import re
import sys

routine, conf_path, workflow_path = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, "tools/backlog-burn/src")
from backlog_burn.config import resolve_cadence  # noqa: E402

# --- conf side: the last `cadence:` line wins, mirroring the house parser's
# last-assignment-wins (printer-conf.scad's include, style tokens) and
# matching OpenSCAD's own override semantics the repo builds on.
conf_cadence = None
with open(conf_path, encoding="utf-8") as fh:
    for lineno, raw in enumerate(fh, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^cadence:\s*(.+?)\s*$", line)
        if m:
            conf_cadence = (m.group(1), lineno)
if conf_cadence is None:
    sys.stderr.write(
        f"cadence-sync[{routine}]: {conf_path} carries no `cadence:` key — a "
        f"routine without a cadence has nothing to keep in sync\n")
    sys.exit(1)
stored, lineno = conf_cadence
try:
    resolved = resolve_cadence(stored)
except ValueError as exc:
    sys.stderr.write(
        f"cadence-sync[{routine}]: {conf_path}:{lineno}: {exc}\n")
    sys.exit(1)

# --- workflow side: the `on.schedule` cron literal, i.e. the FIRST
# `- cron:` line — later ones, if any ever appear, belong to other triggers
# and must not be silently compared instead.
workflow_cron = None
with open(workflow_path, encoding="utf-8") as fh:
    for lineno, raw in enumerate(fh, 1):
        m = re.match(r"^\s*-\s*cron:\s*'([^']*)'\s*$", raw)
        if m:
            workflow_cron = (m.group(1), lineno)
            break
if workflow_cron is None:
    sys.stderr.write(
        f"cadence-sync[{routine}]: {workflow_path} carries no `- cron: '...'` "
        f"schedule literal to compare against\n")
    sys.exit(1)
cron, wf_lineno = workflow_cron

# --- compare on the resolved schedule, so a preset conf and its expanded
# workflow cron are the same cadence, not a false positive.
def canon(expr: str) -> str:
    return " ".join(expr.split())

if canon(resolved) != canon(cron):
    sys.stderr.write(
        f"cadence-sync[{routine}]: conf and workflow disagree\n"
        f"    {conf_path}:{lineno}          cadence: {stored!r}"
        f"{'' if stored == resolved else '  (resolves to ' + resolved + ')'}\n"
        f"    {workflow_path}:{wf_lineno}  cron:    {cron!r}\n"
        f"    → edit BOTH, or use `/backlog-burn set cadence <value>` on "
        f"backlog-burn (it patches both files in one commit).\n")
    sys.exit(1)
PY
}

selftest() {
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # Fixtures are written with quoted heredocs (not printf) so the cron's
  # single quotes need no shell escaping — the escape is easy to get wrong
  # and a mis-parsed fixture would quietly test the wrong thing.

  # GOOD 1: raw-cron conf matching its workflow cron (design-run/chunker/
  # labeler shape). Must PASS.
  cat > "$tmp/raw.conf" <<'EOF'
enabled: true
label: x
cadence: 23 * * * *
EOF
  cat > "$tmp/raw.yml" <<'EOF'
name: T
on:
  schedule:
    - cron: '23 * * * *'
EOF
  if check_pair rawtest "$tmp/raw.conf" "$tmp/raw.yml" 2>/dev/null; then
    echo "ok    selftest: a matched raw-cron pair passes"
  else
    echo "FAIL  selftest: a matched raw-cron pair was rejected"; return 1
  fi

  # GOOD 2: PRESET conf whose workflow carries the RESOLVED cron
  # (backlog-burn's shape — the subtlety a naive string compare false-
  # positives on). `hourly` resolves to '17 * * * *', which must equal the
  # workflow literal, not the preset name.
  cat > "$tmp/preset.conf" <<'EOF'
enabled: true
label: x
cadence: hourly
EOF
  cat > "$tmp/preset.yml" <<'EOF'
name: T
on:
  schedule:
    - cron: '17 * * * *'
EOF
  if check_pair presettest "$tmp/preset.conf" "$tmp/preset.yml" 2>/dev/null; then
    echo "ok    selftest: a preset conf vs its resolved workflow cron passes"
  else
    echo "FAIL  selftest: a preset conf was rejected against its resolved cron"
    return 1
  fi

  # BAD 1: one-sided cadence edit (the exact footgun). Must FAIL.
  cat > "$tmp/drift.conf" <<'EOF'
enabled: true
label: x
cadence: 29 5 * * *
EOF
  cat > "$tmp/drift.yml" <<'EOF'
name: T
on:
  schedule:
    - cron: '30 5 * * *'
EOF
  if check_pair drifttest "$tmp/drift.conf" "$tmp/drift.yml" 2>/dev/null; then
    echo "FAIL  selftest: a mismatched pair was NOT caught"; return 1
  else
    echo "ok    selftest: a one-sided cadence edit fails the check"
  fi

  # BAD 2: preset-vs-drifted-cron — the preset subtlety in the FAILING
  # direction. `daily` resolves to '17 6 * * *'; a workflow still carrying
  # yesterday's `hourly` cron must fail, not compare the strings and pass.
  cat > "$tmp/pdrift.conf" <<'EOF'
enabled: true
label: x
cadence: daily
EOF
  cat > "$tmp/pdrift.yml" <<'EOF'
name: T
on:
  schedule:
    - cron: '17 * * * *'
EOF
  if check_pair pdrifttest "$tmp/pdrift.conf" "$tmp/pdrift.yml" 2>/dev/null; then
    echo "FAIL  selftest: preset-vs-drifted-cron was NOT caught"; return 1
  else
    echo "ok    selftest: a preset conf vs a drifted cron fails the check"
  fi

  # BAD 3: a conf whose cadence is neither preset nor cron must fail loudly
  # rather than being silently skipped (typo'd preset name = silent no-sched-
  # check otherwise).
  cat > "$tmp/typo.conf" <<'EOF'
enabled: true
label: x
cadence: hourlyy
EOF
  cat > "$tmp/typo.yml" <<'EOF'
name: T
on:
  schedule:
    - cron: '17 * * * *'
EOF
  if check_pair typotest "$tmp/typo.conf" "$tmp/typo.yml" 2>/dev/null; then
    echo "FAIL  selftest: a typo'd cadence value was NOT caught"; return 1
  else
    echo "ok    selftest: a typo'd cadence value fails the check"
  fi

  # BAD 4: a workflow with no cron literal at all must fail, not pass by
  # having nothing to compare.
  cat > "$tmp/nocron.conf" <<'EOF'
enabled: true
label: x
cadence: hourly
EOF
  cat > "$tmp/nocron.yml" <<'EOF'
name: T
on:
  push:
    branches: [main]
EOF
  if check_pair nocrontest "$tmp/nocron.conf" "$tmp/nocron.yml" 2>/dev/null; then
    echo "FAIL  selftest: a missing workflow cron was NOT caught"; return 1
  else
    echo "ok    selftest: a conf with no matching workflow cron fails the check"
  fi
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    cadence-sync-check selftest passed"
  exit 0
fi

fail=0
for routine in "${ROUTINES[@]}"; do
  if check_pair "$routine" ".github/${routine}.conf" ".github/workflows/${routine}.yml"; then
    echo "ok    ${routine}: conf cadence matches workflow cron"
  else
    fail=1
  fi
done
exit "$fail"
