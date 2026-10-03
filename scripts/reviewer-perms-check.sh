#!/usr/bin/env bash
# Reviewer permission-drift check: prove the auto-review deny backstops
# (.claude/reviewer-settings.json and .claude/design-coach-settings.json) still
# neutralize every Bash allow they would otherwise inherit from
# .claude/settings.json, always deny the render toolchain, and never deny the
# surface a review needs. Run by scripts/check.sh (and therefore by /preflight
# and CI's scad-check jobs).
#
# WHY THIS EXISTS:
# .github/workflows/auto-review.yml runs claude-code-action, which starts the
# SDK with settingSources:[user,project,local] — so it loads this repo's
# .claude/settings.json permissions.allow. That file carries dev entries the
# interactive agents need, including `Bash(xvfb-run:*)` (arbitrary command
# execution) and the render toolchain allows. Allow rules merge ADDITIVELY
# across sources, so nothing in the reviewer steps removes them. The reviewers
# close this with their own backstops (passed via --settings, under
# --permission-mode dontAsk — a bypassPermissions step ignores its own denies),
# where deny beats allow from every source. Issue #323: the reviewers consume
# CI's posted printcheck/slice results and must never install or run the
# render toolchain themselves.
#
# There are TWO reviewer backstops because their surfaces differ:
# - .claude/reviewer-settings.json: Jane, Drik, PM triage — read-only on the
#   repo, so it must deny Write/Edit/NotebookEdit (and tee, which coverage
#   forces, so a shell cannot stand in for the denied Write).
# - .claude/design-coach-settings.json: the design coach — it pushes
#   iterations, so it must NOT deny Write/Edit (or git commit/push); it still
#   denies NotebookEdit.
#
# The rules, the labeler/oracle precedent applied to the reviewers:
# 1. Coverage — EVERY Bash allow in settings.json must be denied verbatim,
#    except the backstop's REVIEW SURFACE: the exact allow rules a review
#    actually runs (gh to read the PR and post, git to read the diff, jq and
#    mktemp to shape a comment body; plus, for the reviewer backstop only, the
#    chunker's chunk-helper.sh, whose `ensure-label needs-decision` verb is
#    the PM triage's HITL-gate step, pm SKILL.md §7/§8.7). Not a hardcoded
#    list of "toolchain" names: a new script allow is drift the day it lands.
# 2. Floor — the render toolchain #323 names (apt/apt-get, openscad,
#    openscad-nightly, xvfb-run, prusa-slicer, printcheck, the gate/render/
#    check scripts and session-start.sh, both path spellings) must be denied
#    whatever settings.json allows today, plus both growth-desk MCP servers
#    (every sibling backstop denies them; a `Bash(mcp__…)` rule denies a
#    shell command of that name, not the server).
# 3. Surface guard — no deny may block the review surface: a probe command
#    per need (gh pr view/diff/comment, gh api, git diff/log/fetch, …) is
#    matched against every Bash deny with wildcard and prefix semantics, so
#    `Bash(gh:*)`, `Bash(g*:*)` and `Bash(gh pr comment:*)` all fail while a
#    narrow `Bash(gh pr merge:*)` passes. Read/Grep/Glob must not be denied
#    (a bare, blanket or wildcard tool rule; a path-scoped Read(./x) is fine).
# 4. Posture — reviewer denies Write/Edit/NotebookEdit; the coach never
#    denies Write/Edit (wildcards included).
# 5. Hygiene — no deny rule twice: a duplicate is how the coach backstop once
#    carried `./scripts/regen-stamp.sh` twice and never its bare spelling.
#
# That backstop is only as good as its coverage. Add a Bash allow to
# settings.json tomorrow and, unless it is also denied here, the reviewers
# silently inherit it again — an invisible regression, because the thing being
# protected is the ABSENCE of a capability. Extra denies are fine (this
# asserts coverage, not equality) as long as none reaches the review surface.
# The WORKFLOW half — every reviewer ship step passes its backstop under
# dontAsk — is pinned by tools/model-registry/tests/
# test_reviewer_backstop_wiring.py; this script holds the FILE half.
#
# Usage:
#   scripts/reviewer-perms-check.sh            # check the real files
#   scripts/reviewer-perms-check.sh --selftest # prove the check can pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/settings.json"
REVIEWER=".claude/reviewer-settings.json"
COACH=".claude/design-coach-settings.json"

# Core comparison, pure function of two settings files plus which backstop is
# being checked ("reviewer" or "coach"). Prints a diagnosis and returns
# non-zero on any drift. Kept as a function so --selftest can point it at
# fixtures.
check_pair() {
  local settings_path="$1" backstop_path="$2" kind="$3"
  python3 - "$settings_path" "$backstop_path" "$kind" <<'PY'
import collections, fnmatch, json, sys

settings_path, backstop_path, kind = sys.argv[1], sys.argv[2], sys.argv[3]

# The review surface, identified by EXACT allow rule (both path spellings for
# a wrapper) — never a loose substring, so a same-basename rule on a different
# path is not exempted. Exempt from coverage only; it is not "must allow".
SHARED_SURFACE = {"Bash(gh:*)", "Bash(git:*)", "Bash(jq:*)", "Bash(mktemp:*)"}
# Commands a deny must never block, matched with wildcard + prefix semantics.
SHARED_PROBES = [
    "gh pr view 1", "gh pr diff 1", "gh pr comment 1 --body x",
    "gh api repos/o/r/pulls/1/comments", "gh issue edit 1 --add-label x",
    "gh pr edit 1 --add-label x",
    "git diff", "git log", "git show HEAD", "git fetch origin",
    "git checkout HEAD -- designs",
]
if kind == "reviewer":
    # PM triage raises a blocking fork through the HITL gate with the
    # chunker's ensure-label verb (pm SKILL.md §7, run from §8.7). Every verb
    # the wrapper has is a subset of what Bash(gh:*) already grants this job,
    # so denying it buys no containment and breaks a documented gate step.
    SURFACE = SHARED_SURFACE | {
        "Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)",
        "Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)",
    }
    PROBES = SHARED_PROBES + [
        ".claude/skills/chunk-issue/chunk-helper.sh ensure-label needs-decision",
        "./.claude/skills/chunk-issue/chunk-helper.sh ensure-label needs-decision",
    ]
    # Read-only on the repo: no file-mutating tool.
    POSTURE_DENY = [{"Write"}, {"Edit"}, {"NotebookEdit"}]
    NEVER_DENY_TOOLS = ["Read", "Grep", "Glob"]
elif kind == "coach":
    SURFACE = set(SHARED_SURFACE)
    # The coach lands each round as a pushed iteration.
    PROBES = SHARED_PROBES + ["git add designs", "git commit -m x",
                              "git push origin HEAD"]
    POSTURE_DENY = [{"NotebookEdit"}]
    NEVER_DENY_TOOLS = ["Read", "Grep", "Glob", "Write", "Edit"]
else:
    sys.stderr.write(f"unknown backstop kind {kind!r}\n")
    sys.exit(2)

# Required denies the backstop must ALWAYS carry, whatever settings.json
# allows today: the render toolchain #323 exists to keep out of a review
# session, and the growth desk's two MCP servers (server- or tool-level).
REQUIRED_DENIES = [
    {"Bash(apt:*)"}, {"Bash(apt-get:*)"},
    {"Bash(openscad:*)"}, {"Bash(openscad-nightly:*)"},
    {"Bash(xvfb-run:*)"}, {"Bash(prusa-slicer:*)"}, {"Bash(printcheck:*)"},
    {"Bash(./scripts/gate.sh:*)"}, {"Bash(scripts/gate.sh:*)"},
    {"Bash(./scripts/render.sh:*)"}, {"Bash(scripts/render.sh:*)"},
    {"Bash(./scripts/check.sh:*)"}, {"Bash(scripts/check.sh:*)"},
    {"Bash(.claude/hooks/session-start.sh:*)"},
    {"Bash(./.claude/hooks/session-start.sh:*)"},
    {"mcp__growth_queue", "mcp__growth_queue__queue_growth_post"},
    {"mcp__growth_twitter", "mcp__growth_twitter__post_tweet"},
] + POSTURE_DENY

# A tool-rule specifier that scopes nothing — `Read(**)` denies Read outright.
BLANKET_SPECS = {"", "*", "**", "/**", "./**", "**/*", "//**"}

def load(path):
    with open(path) as fh:
        return json.load(fh)

def bash_deny_blocks(rule, command):
    # Deliberately generous to the deny (the safe direction for a guard): a
    # `:*` rule is treated as a bare prefix, with or without a word boundary,
    # and `*` matches across spaces and slashes. A bare `Bash` denies all.
    if rule == "Bash":
        return True
    if not (rule.startswith("Bash(") and rule.endswith(")")):
        return False
    spec = rule[len("Bash("):-1]
    if spec.endswith(":*"):
        return fnmatch.fnmatchcase(command, spec[:-2] + "*")
    return fnmatch.fnmatchcase(command, spec)

def tool_deny_blocks(rule, tool):
    # `Read`, `Read(**)`, `*` or `Re*` block the tool; a path-scoped
    # `Read(./.env)` leaves it usable. Bash rules are probed separately.
    name, paren, rest = rule.partition("(")
    if name == "Bash" or not fnmatch.fnmatchcase(tool, name):
        return False
    return not paren or rest[:-1].strip() in BLANKET_SPECS

allow = load(settings_path).get("permissions", {}).get("allow", [])
deny  = load(backstop_path).get("permissions", {}).get("deny", [])
deny_set = set(deny)

# 1. Coverage: every non-surface Bash allow must be denied verbatim.
missing = [r for r in allow
           if r.startswith("Bash(") and r not in SURFACE and r not in deny_set]
# 2 + 4. The floor and the posture, asserted whatever settings.json says.
missing_required = [sorted(alts) for alts in REQUIRED_DENIES
                    if not (alts & deny_set)]
# 3 + 4. Nothing may block the review surface or a tool the backstop needs.
blocked = [(d, p) for d in deny for p in PROBES if bash_deny_blocks(d, p)]
blocked += [(d, t) for d in deny for t in NEVER_DENY_TOOLS
            if tool_deny_blocks(d, t)]
# 5. A duplicate is the typo'd-twin symptom.
dupes = sorted(r for r, n in collections.Counter(deny).items() if n > 1)

ok = True
if blocked:
    ok = False
    sys.stderr.write(
        f"a deny rule in {backstop_path} blocks the {kind}'s review surface "
        f"— the session could no longer read the PR or post its review:\n")
    for rule, what in blocked:
        sys.stderr.write(f"    {rule}  (blocks: {what})\n")
if missing:
    ok = False
    sys.stderr.write(
        f"these Bash allows in {settings_path} are NOT denied in "
        f"{backstop_path} (the {kind} inherits them via "
        f"settingSources=project):\n")
    for r in missing:
        sys.stderr.write(f"    {r}\n")
    sys.stderr.write(f"  → add each to {backstop_path} permissions.deny.\n")
if missing_required:
    ok = False
    sys.stderr.write(
        f"required denies (render toolchain / growth-desk servers / the "
        f"{kind}'s file-tool posture) are missing from {backstop_path}:\n")
    for alts in missing_required:
        sys.stderr.write(f"    {' or '.join(alts)}\n")
if dupes:
    ok = False
    sys.stderr.write(
        f"duplicate deny rules in {backstop_path} (usually a typo'd twin — "
        f"the spelling it was meant to be is the one left undenied):\n")
    for r in dupes:
        sys.stderr.write(f"    {r}\n")

sys.exit(0 if ok else 1)
PY
}

# Fixture helper: copy a settings file, applying +rule / -rule edits to one
# permissions list. A `-rule` the source does not carry is an error, so a
# control can never pass because its mutation silently missed.
derive() {
  local src="$1" dst="$2" key="$3"
  shift 3
  python3 - "$src" "$dst" "$key" "$@" <<'PY'
import json, sys
src, dst, key, *edits = sys.argv[1:]
with open(src) as fh:
    data = json.load(fh)
rules = data.setdefault("permissions", {}).setdefault(key, [])
for edit in edits:
    op, rule = edit[:1], edit[1:]
    if op == "+":
        rules.append(rule)
    elif op == "-" and rule in rules:
        rules[:] = [r for r in rules if r != rule]
    else:
        sys.exit(f"derive: cannot apply {edit!r} to {src} {key} — the fixture is stale")
with open(dst, "w") as fh:
    json.dump(data, fh)
PY
}

selftest() {
  local tmp bad=0 n=0
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # expect <pass|fail> <what> <settings> <backstop> <kind>
  expect() {
    local want="$1" what="$2" got
    shift 2
    n=$((n + 1))
    if check_pair "$@" 2>/dev/null; then got=pass; else got=fail; fi
    if [[ "$got" == "$want" ]]; then
      echo "ok    selftest: $what"
    else
      echo "FAIL  selftest: $what (check said $got, want $want)"
      bad=1
    fi
  }

  # A minimal-but-complete settings.json: a toolchain allow, a script-path
  # allow, a shell file-writer, the shared review surface, and the chunker's
  # wrapper (reviewer surface, coach drift).
  cat > "$tmp/settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(./scripts/gate.sh:*)","Bash(tee:*)","Bash(gh:*)","Bash(git:*)","Bash(jq:*)","Bash(mktemp:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  # The matching good backstops: the floor, the growth servers, the covered
  # allows, and each one's posture.
  cat > "$tmp/reviewer.json" <<'EOF'
{"permissions":{"deny":["Bash(apt:*)","Bash(apt-get:*)","Bash(openscad:*)","Bash(openscad-nightly:*)","Bash(xvfb-run:*)","Bash(prusa-slicer:*)","Bash(printcheck:*)","Bash(./scripts/gate.sh:*)","Bash(scripts/gate.sh:*)","Bash(./scripts/render.sh:*)","Bash(scripts/render.sh:*)","Bash(./scripts/check.sh:*)","Bash(scripts/check.sh:*)","Bash(.claude/hooks/session-start.sh:*)","Bash(./.claude/hooks/session-start.sh:*)","mcp__growth_queue","mcp__growth_twitter","Bash(tee:*)","Write","Edit","NotebookEdit"]}}
EOF
  derive "$tmp/reviewer.json" "$tmp/coach.json" deny -Write -Edit \
    "+Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)" \
    "+Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)"

  local S="$tmp/settings.json" R="$tmp/reviewer.json" C="$tmp/coach.json" f
  expect pass "complete reviewer backstop passes" "$S" "$R" reviewer
  expect pass "complete design-coach backstop passes" "$S" "$C" coach

  # Coverage: a new script-path allow the old toolchain-name rule never saw.
  derive "$S" "$tmp/s1.json" allow "+Bash(./scripts/plate.sh:*)"
  expect fail "an undenied script-path allow fails the check" "$tmp/s1.json" "$R" reviewer
  # Floor: apt-get is on no allow list, so only the floor can see it go.
  derive "$R" "$tmp/r.json" deny "-Bash(apt-get:*)"
  expect fail "a dropped toolchain floor deny (apt-get) fails the check" "$S" "$tmp/r.json" reviewer
  derive "$C" "$tmp/c.json" deny "-Bash(scripts/render.sh:*)"
  expect fail "a dropped floor deny in the coach backstop fails the check" "$S" "$tmp/c.json" coach
  # Surface guard: exact, wildcard and narrow-prefix denies on gh/git.
  for f in "Bash(gh:*)" "Bash(git:*)" "Bash(g*:*)" "Bash(gh pr comment:*)" "Bash(*)" "Bash"; do
    derive "$R" "$tmp/r.json" deny "+$f"
    expect fail "denying the review surface with $f fails the check" "$S" "$tmp/r.json" reviewer
  done
  # …and its precision: a narrow deny off the surface is fine.
  derive "$R" "$tmp/r.json" deny "+Bash(gh pr merge:*)"
  expect pass "a narrow deny off the review surface (gh pr merge) passes" "$S" "$tmp/r.json" reviewer
  derive "$C" "$tmp/c.json" deny "+Bash(git push:*)"
  expect fail "denying the coach's git push fails the check" "$S" "$tmp/c.json" coach
  derive "$R" "$tmp/r.json" deny "+Bash(.claude/skills/chunk-issue/*:*)"
  expect fail "denying PM triage's ensure-label wrapper fails the check" "$S" "$tmp/r.json" reviewer
  # File tools: blanket and wildcard read denies fail, a path-scoped one passes.
  for f in "Read" "Grep" "Glob" "Read(**)" "*"; do
    derive "$R" "$tmp/r.json" deny "+$f"
    expect fail "denying a read tool with $f fails the check" "$S" "$tmp/r.json" reviewer
  done
  derive "$R" "$tmp/r.json" deny "+Read(./.env)"
  expect pass "a path-scoped Read deny passes" "$S" "$tmp/r.json" reviewer
  # Posture: the reviewer must deny Write; the coach must not deny Edit.
  derive "$R" "$tmp/r.json" deny -Write
  expect fail "a reviewer backstop without a Write deny fails the check" "$S" "$tmp/r.json" reviewer
  derive "$C" "$tmp/c.json" deny +Edit
  expect fail "a coach backstop that denies Edit fails the check" "$S" "$tmp/c.json" coach
  derive "$C" "$tmp/c.json" deny "+Wr*"
  expect fail "a coach backstop that wildcard-denies Write fails the check" "$S" "$tmp/c.json" coach
  # The surfaces are per-backstop: the coach has no use for chunk-helper.
  derive "$C" "$tmp/c.json" deny "-Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)"
  expect fail "a coach backstop leaving chunk-helper undenied fails the check" "$S" "$tmp/c.json" coach
  # Growth servers: the old Bash(mcp__…) spelling denies a shell command.
  derive "$R" "$tmp/r.json" deny -mcp__growth_queue "+Bash(mcp__growth_queue:*)"
  expect fail "a growth-server deny spelled as a Bash rule fails the check" "$S" "$tmp/r.json" reviewer
  # Hygiene: a duplicated rule.
  derive "$C" "$tmp/c.json" deny "+Bash(./scripts/gate.sh:*)"
  expect fail "a duplicate deny rule fails the check" "$S" "$tmp/c.json" coach

  echo "      selftest: $n cases"
  return "$bad"
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    reviewer-perms-check selftest passed"
  exit 0
fi

[[ -f "$SETTINGS" ]] || { echo "FAIL  reviewer-perms: $SETTINGS missing"; exit 1; }
[[ -f "$REVIEWER" ]] || { echo "FAIL  reviewer-perms: $REVIEWER missing"; exit 1; }
[[ -f "$COACH"    ]] || { echo "FAIL  reviewer-perms: $COACH missing"; exit 1; }

fail=0
if check_pair "$SETTINGS" "$REVIEWER" reviewer; then
  echo "ok    reviewer deny backstop covers every non-surface Bash allow + the toolchain floor, and leaves the review surface usable"
else
  echo "FAIL  reviewer permission drift: $REVIEWER does not neutralize $SETTINGS (or blocks the review surface)"
  fail=1
fi
if check_pair "$SETTINGS" "$COACH" coach; then
  echo "ok    design-coach deny backstop covers every non-surface Bash allow + the toolchain floor, and leaves the review surface and Write/Edit usable"
else
  echo "FAIL  reviewer permission drift: $COACH does not neutralize $SETTINGS (or blocks the coach's surface)"
  fail=1
fi
exit "$fail"
