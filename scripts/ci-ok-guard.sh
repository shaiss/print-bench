#!/usr/bin/env bash
# ci-ok wiring guard: prove every job in .github/workflows/ci.yml is wired into
# the `ci-ok` aggregation job's `needs:` list — or is legitimately exempt
# because it is advisory (`continue-on-error: true`) — and that every `needs:`
# entry names a real job.
#
# WHY THIS EXISTS: branch protection is meant to require the single `ci-ok`
# context, which passes only when every job it `needs:` succeeded or was
# skipped by the classifier (the PR #50 reason `ci-ok` exists at all). But that
# `needs:` list is hand-maintained, and ci.yml says so in its own comment
# (search "A job missing from needs can fail without blocking the merge, and
# nothing detects the omission"). That is the hole: add a new gating job and
# forget to list it in `ci-ok.needs`, and the job can go RED while `ci-ok`
# stays green — because `ci-ok` never depended on it — so the PR merges with a
# failing gate. Nothing caught it. This check is that missing detector, in the
# same negative-control spirit as guard-check/mate-check/cadence-sync: an
# invariant the repo relies on is worthless until something proves it can fail.
#
# THE RULE (criterion-derived, not a hardcoded allowlist):
#   Every job EXCEPT `ci-ok` itself must appear in `ci-ok.needs`, UNLESS the
#   job is JOB-LEVEL `continue-on-error: true` — an advisory job (today:
#   geo-diff) that by construction cannot gate a merge and so must not be
#   required to. The exemption is read from the job's own flag, so a new
#   advisory job is exempt automatically and a new BLOCKING job is not — the
#   only way to dodge the requirement is to actually mark the job advisory,
#   which is the honest declaration, not a bypass. Additionally, every
#   `needs:` entry must name a real job, so a typo'd or stale dependency
#   (which silently makes `ci-ok` not wait for the intended job) fails too.
#
# WHAT IT PROVES — AND DELIBERATELY DOES NOT:
#   ✅ WIRING: every gating job is a dependency of ci-ok, and every dependency
#      of ci-ok is a real job.
#   ❌ NOT that branch protection actually requires `ci-ok` — that is a repo
#      setting GitHub holds, not a file in the tree, so no in-repo check can
#      see it (docs/actions-security.md territory). A green guard means "IF
#      protection requires ci-ok, no gating job can slip past it", not "it does".
#
# Usage:
#   scripts/ci-ok-guard.sh            # check .github/workflows/ci.yml
#   scripts/ci-ok-guard.sh --selftest # prove the check passes AND fails
#
# Run by scripts/check.sh (and therefore /preflight and CI's scad-check jobs).
set -euo pipefail

cd "$(dirname "$0")/.."

# Check one ci.yml-shaped file against one aggregator job name. Prints a
# diagnosis and returns non-zero on any wiring problem. A function so
# --selftest can point it at fixtures.
check_file() {
  local workflow="$1" aggregator="$2"

  [[ -f "$workflow" ]] || { echo "FAIL  ci-ok-guard: $workflow not found"; return 1; }

  python3 - "$workflow" "$aggregator" <<'PY'
"""Prove every job in a workflow is wired into the aggregator's needs list.

Parses top-level job names out of the `jobs:` block, the aggregator job's
`needs:` list, and each job's JOB-LEVEL `continue-on-error` flag — all with
stdlib regexes (no PyYAML: the parse is line-shaped and CI installs nothing
ahead of check.sh, matching every other stdlib parser in this repo). Fails
loudly, naming every offender, on any of: a gating job absent from needs, a
needs entry naming no real job, or a missing/empty aggregator.
"""
import re
import sys

workflow_path, aggregator = sys.argv[1], sys.argv[2]
with open(workflow_path, encoding="utf-8") as fh:
    lines = fh.read().splitlines()

# --- locate the single top-level `jobs:` block. Job headers are the 2-space-
# indented keys inside it; scanning stops at the next top-level (0-indent) key
# so sibling top-level blocks (on:, permissions:, concurrency:) never leak in.
jobs_start = next((i for i, ln in enumerate(lines)
                   if re.match(r"^jobs:\s*(?:#.*)?$", ln)), None)
if jobs_start is None:
    sys.stderr.write(f"ci-ok-guard: {workflow_path} has no top-level `jobs:` block\n")
    sys.exit(1)

# (name, start_line_index) for every job header, in file order.
job_headers = []
for i in range(jobs_start + 1, len(lines)):
    ln = lines[i]
    if ln.strip() == "" or ln.lstrip().startswith("#"):
        continue
    if re.match(r"^\S", ln):          # a new top-level key → jobs block ended
        break
    m = re.match(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$", ln)
    if m:
        job_headers.append((m.group(1), i))

if not job_headers:
    sys.stderr.write(f"ci-ok-guard: {workflow_path} defines no jobs under `jobs:`\n")
    sys.exit(1)

# Job body spans from a header to the next header (or end of file) — used to
# read each job's own JOB-LEVEL keys (4-space indent).
bounds = {}
for idx, (name, start) in enumerate(job_headers):
    end = job_headers[idx + 1][1] if idx + 1 < len(job_headers) else len(lines)
    bounds[name] = (start, end)
job_names = [n for n, _ in job_headers]
job_set = set(job_names)

def is_job_level_advisory(name):
    """True iff the job carries JOB-LEVEL `continue-on-error: true` (4-space
    indent). Step-level flags (8+ spaces, inside `steps:`) are NOT this — they
    make one step non-fatal, not the whole job advisory."""
    start, end = bounds[name]
    for ln in lines[start + 1:end]:
        if re.match(r"^    continue-on-error:\s*true\s*(?:#.*)?$", ln):
            return True
    return False

# --- the aggregator's needs list.
if aggregator not in job_set:
    sys.stderr.write(
        f"ci-ok-guard: {workflow_path} has no `{aggregator}` job to aggregate the gates\n")
    sys.exit(1)

a_start, a_end = bounds[aggregator]
needs = []
seen_needs_key = False
i = a_start + 1
while i < a_end:
    ln = lines[i]
    m = re.match(r"^    needs:\s*(.*?)\s*(?:#.*)?$", ln)
    if m:
        seen_needs_key = True
        rest = m.group(1)
        if rest.startswith("["):                     # flow list: needs: [a, b]
            needs += [t.strip() for t in rest.strip("[]").split(",") if t.strip()]
        elif rest and not rest.startswith("#"):       # single scalar: needs: a
            needs.append(rest)
        else:                                         # block list on next lines
            j = i + 1
            while j < a_end:
                b = re.match(r"^      -\s*([A-Za-z0-9_-]+)\s*(?:#.*)?$", lines[j])
                if b:
                    needs.append(b.group(1))
                    j += 1
                elif lines[j].strip() == "" or lines[j].lstrip().startswith("#"):
                    j += 1
                else:
                    break
            i = j
            continue
    i += 1

if not seen_needs_key or not needs:
    sys.stderr.write(
        f"ci-ok-guard: `{aggregator}` has no `needs:` list — it would aggregate nothing\n")
    sys.exit(1)

needs_set = set(needs)

# --- Check 1: every needs entry names a real job (catch typos / stale needs
# that silently make ci-ok not wait for the intended gate).
phantom = sorted(n for n in needs_set if n not in job_set)

# --- Check 2: every job except the aggregator is either in needs or is
# job-level advisory. A blocking job absent from needs is the footgun.
missing = sorted(
    n for n in job_names
    if n != aggregator and n not in needs_set and not is_job_level_advisory(n))

# Report advisory exemptions so a reader sees WHY a job is legitimately absent.
exempt = sorted(
    n for n in job_names
    if n != aggregator and n not in needs_set and is_job_level_advisory(n))

ok = True
if phantom:
    ok = False
    sys.stderr.write(
        f"ci-ok-guard: `{aggregator}.needs` names job(s) that do not exist: "
        f"{', '.join(phantom)}\n"
        f"    → a typo'd or stale dependency: ci-ok would not actually wait for it.\n")
if missing:
    ok = False
    sys.stderr.write(
        f"ci-ok-guard: gating job(s) NOT wired into `{aggregator}.needs`: "
        f"{', '.join(missing)}\n"
        f"    → add each to `{aggregator}.needs`, or mark it "
        f"`continue-on-error: true` if it is genuinely advisory.\n"
        f"    Without this, the job can fail RED while `{aggregator}` stays green.\n")
if not ok:
    sys.exit(1)

detail = f" ({len(exempt)} advisory exempt: {', '.join(exempt)})" if exempt else ""
print(f"    {len(needs_set)} gating job(s) wired into {aggregator}{detail}")
PY
}

selftest() {
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # Fixtures are ci.yml-shaped: a `jobs:` block with 2-space job headers,
  # 4-space job keys, a block `needs:` list. Quoted heredocs so nothing needs
  # shell escaping.

  # GOOD 1: every blocking job wired; one advisory (continue-on-error) job
  # legitimately absent from needs. Must PASS.
  cat > "$tmp/good.yml" <<'EOF'
name: T
on: [push]
permissions:
  contents: read
jobs:
  changes:
    runs-on: ubuntu-latest
  build:
    runs-on: ubuntu-latest
  advisory:
    runs-on: ubuntu-latest
    continue-on-error: true
  ci-ok:
    needs:
      - changes
      - build
    runs-on: ubuntu-latest
EOF
  if check_file "$tmp/good.yml" ci-ok >/dev/null 2>&1; then
    echo "ok    selftest: fully-wired workflow (advisory job exempt) passes"
  else
    echo "FAIL  selftest: a fully-wired workflow was rejected"; return 1
  fi

  # GOOD 2: the exemption is by the FLAG, not by absence — turn the advisory
  # job into a blocking one AND wire it. Must still PASS.
  cat > "$tmp/good2.yml" <<'EOF'
name: T
on: [push]
jobs:
  changes:
    runs-on: ubuntu-latest
  advisory:
    runs-on: ubuntu-latest
  ci-ok:
    needs:
      - changes
      - advisory
    runs-on: ubuntu-latest
EOF
  if check_file "$tmp/good2.yml" ci-ok >/dev/null 2>&1; then
    echo "ok    selftest: a wired formerly-advisory job passes"
  else
    echo "FAIL  selftest: a wired job was rejected"; return 1
  fi

  # BAD 1: the footgun — a new BLOCKING job absent from needs. Must FAIL.
  cat > "$tmp/unwired.yml" <<'EOF'
name: T
on: [push]
jobs:
  changes:
    runs-on: ubuntu-latest
  newgate:
    runs-on: ubuntu-latest
  ci-ok:
    needs:
      - changes
    runs-on: ubuntu-latest
EOF
  if check_file "$tmp/unwired.yml" ci-ok >/dev/null 2>&1; then
    echo "FAIL  selftest: an unwired blocking job was NOT caught"; return 1
  else
    echo "ok    selftest: an unwired blocking job fails the check"
  fi

  # BAD 2: a needs entry naming a job that does not exist (typo/stale). Must FAIL.
  cat > "$tmp/phantom.yml" <<'EOF'
name: T
on: [push]
jobs:
  changes:
    runs-on: ubuntu-latest
  ci-ok:
    needs:
      - changes
      - chnages
    runs-on: ubuntu-latest
EOF
  if check_file "$tmp/phantom.yml" ci-ok >/dev/null 2>&1; then
    echo "FAIL  selftest: a phantom needs entry was NOT caught"; return 1
  else
    echo "ok    selftest: a phantom needs entry fails the check"
  fi

  # BAD 3: no aggregator job at all — nothing to gate through. Must FAIL.
  cat > "$tmp/noagg.yml" <<'EOF'
name: T
on: [push]
jobs:
  changes:
    runs-on: ubuntu-latest
  build:
    runs-on: ubuntu-latest
EOF
  if check_file "$tmp/noagg.yml" ci-ok >/dev/null 2>&1; then
    echo "FAIL  selftest: a missing aggregator was NOT caught"; return 1
  else
    echo "ok    selftest: a missing aggregator fails the check"
  fi

  # BAD 4: a "looks advisory by name" job that lacks the flag and is unwired —
  # proves the exemption is the FLAG, not the name. Must FAIL.
  cat > "$tmp/fakeadvisory.yml" <<'EOF'
name: T
on: [push]
jobs:
  changes:
    runs-on: ubuntu-latest
  advisory:
    runs-on: ubuntu-latest
  ci-ok:
    needs:
      - changes
    runs-on: ubuntu-latest
EOF
  if check_file "$tmp/fakeadvisory.yml" ci-ok >/dev/null 2>&1; then
    echo "FAIL  selftest: an advisory-NAMED but non-flagged unwired job was NOT caught"
    return 1
  else
    echo "ok    selftest: an unflagged 'advisory' job still must be wired"
  fi
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    ci-ok-guard selftest passed"
  exit 0
fi

if check_file ".github/workflows/ci.yml" ci-ok; then
  echo "ok    ci-ok: every gating job is wired into ci-ok.needs"
else
  exit 1
fi
