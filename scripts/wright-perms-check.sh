#!/usr/bin/env bash
# Wright permission-drift check: prove BOTH halves of the agent forge still
# carry a deny backstop that neutralizes every dangerous tool allow they would
# otherwise inherit, denies every sibling write surface AND each other's write
# tool, and never denies their own surfaces. Run by scripts/check.sh (and
# therefore by /preflight and CI's scad-check jobs).
#
# WHY THIS EXISTS, and why ONE script checks TWO backstops:
# .github/workflows/wright.yml runs claude-code-action twice — the propose
# half (/wright, backstop .claude/wright-settings.json) and the sign-off half
# (/reeve-signoff, backstop .claude/reeve-signoff-settings.json). The action
# loads .claude/settings.json (settingSources=project) whose dev allows merge
# ADDITIVELY, so each half closes that with its own --settings deny backstop:
# deny beats allow from every source.
#
# The two halves are separated ON PURPOSE, and this check is what keeps the
# separation real: the sign-off tool can APPLY `autonomy-ok` (the arming
# label), so the proposer must never hold it — wright-settings.json denies
# `mcp__reeve_signoff` — and the judge must never file the briefs it judges —
# reeve-signoff-settings.json denies `mcp__wright`. A single shared backstop
# could not express that (each file's "never deny" is the other's "must
# deny"), and coverage alone would never force either (neither MCP server is
# on settings.json's allow-list), so both cross-denies are pinned in explicit
# REQUIRED_DENIES sets — as are the four sibling wrappers (chunk-helper,
# label-helper, scout-helper, assessor-helper; none is the forge's surface)
# and the sibling MCP servers, the oracle-perms-check precedent.
#
# What each half must NOT deny: the shared read wrapper wright-helper.sh
# (both spellings — both halves read through it) and its OWN write tool
# (mcp__wright__file_agent_brief for propose,
# mcp__reeve_signoff__post_reeve_signoff for sign-off) — or the scheduled
# forge fails closed with no other CI signal.
#
# Usage:
#   scripts/wright-perms-check.sh            # check the real files
#   scripts/wright-perms-check.sh --selftest # prove the check can pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/settings.json"
WRIGHT=".claude/wright-settings.json"
SIGNOFF=".claude/reeve-signoff-settings.json"

# Core comparison, pure function of two settings files plus which half is
# being checked ("wright" or "signoff"). Prints a diagnosis and returns
# non-zero on any drift. Kept as a function so --selftest can point it at
# fixtures.
check_pair() {
  local settings_path="$1" backstop_path="$2" half="$3"
  python3 - "$settings_path" "$backstop_path" "$half" <<'PY'
import fnmatch, json, sys

settings_path, backstop_path, half = sys.argv[1], sys.argv[2], sys.argv[3]

# The forge's ONE shared shell surface (read-only), identified by its EXACT
# allow rule (both spellings) — never a loose substring. A same-basename rule
# on a different path is NOT the wrapper and must still be denied.
WRAPPER_RULES = {
    "Bash(.claude/skills/wright/wright-helper.sh:*)",
    "Bash(./.claude/skills/wright/wright-helper.sh:*)",
}
WRAPPER_CMDS = [
    ".claude/skills/wright/wright-helper.sh",
    "./.claude/skills/wright/wright-helper.sh",
]

# Per half: the write tool this backstop must NEVER deny (its own), and the
# one it MUST deny (the other half's) — the separation that stops the
# proposer judging its own briefs and the judge filing its own.
if half == "wright":
    OWN_TOOL = "mcp__wright__file_agent_brief"
    OWN_SERVER = "mcp__wright"
    CROSS = {"mcp__reeve_signoff", "mcp__reeve_signoff__post_reeve_signoff"}
elif half == "signoff":
    OWN_TOOL = "mcp__reeve_signoff__post_reeve_signoff"
    OWN_SERVER = "mcp__reeve_signoff"
    CROSS = {"mcp__wright", "mcp__wright__file_agent_brief"}
else:
    sys.stderr.write(f"unknown half {half!r}\n")
    sys.exit(2)

# Required denies the backstop must ALWAYS carry, whatever settings.json
# allows today: all four sibling wrappers (both spellings), the sibling MCP
# servers, the file-mutating tools, and the OTHER half's tool. Alternative
# sets: an `mcp` surface may be denied at server or tool level.
REQUIRED_DENIES = [
    {"Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"},
    {"Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)"},
    {"Bash(.claude/skills/label-issues/label-helper.sh:*)"},
    {"Bash(./.claude/skills/label-issues/label-helper.sh:*)"},
    {"Bash(.claude/skills/product-scout/scout-helper.sh:*)"},
    {"Bash(./.claude/skills/product-scout/scout-helper.sh:*)"},
    {"Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)"},
    {"Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)"},
    {"mcp__scout", "mcp__scout__file_design_brief"},
    {"mcp__assessor", "mcp__assessor__post_adoption_disposition"},
    {"mcp__oracle", "mcp__oracle__post_oracle_review"},
    CROSS,
    {"Write"}, {"Edit"}, {"NotebookEdit"},
]

def load(path):
    with open(path) as fh:
        return json.load(fh)

def deny_blocks_wrapper(rule):
    if not (rule.startswith("Bash(") and rule.endswith(")")):
        return False
    cmd_pat = rule[len("Bash("):-1].split(":", 1)[0]
    return any(fnmatch.fnmatch(cmd, cmd_pat) for cmd in WRAPPER_CMDS)

def deny_blocks_own_tool(rule):
    # An exact or wildcard deny naming this half's own tool or server blocks
    # its only output channel. Bash(...) denies never do.
    if rule.startswith("Bash("):
        return False
    return (rule in (OWN_TOOL, OWN_SERVER)
            or fnmatch.fnmatch(OWN_TOOL, rule)
            or fnmatch.fnmatch(OWN_SERVER, rule))

allow = load(settings_path).get("permissions", {}).get("allow", [])
deny  = load(backstop_path).get("permissions", {}).get("deny", [])
deny_set = set(deny)

# Coverage: every non-wrapper Bash allow in settings.json must be denied
# verbatim (the additive-allow leak).
missing = [r for r in allow
           if r.startswith("Bash(") and r not in WRAPPER_RULES and r not in deny_set]
# The pinned surfaces coverage alone would never force.
missing_required = [sorted(alts) for alts in REQUIRED_DENIES
                    if not (alts & deny_set)]
# Fail-closed safety: neither the wrapper nor this half's own tool may be
# denied, wildcards included.
wrapper_denied = [d for d in deny if deny_blocks_wrapper(d)]
own_denied = [d for d in deny if deny_blocks_own_tool(d)]

ok = True
if wrapper_denied:
    ok = False
    sys.stderr.write(
        f"a deny rule would block the forge's read wrapper — the scheduled "
        f"{half} half would fail closed:\n")
    for r in wrapper_denied:
        sys.stderr.write(f"    {r}\n")
if own_denied:
    ok = False
    sys.stderr.write(
        f"a deny rule would block the {half} half's OWN write tool "
        f"({OWN_TOOL}) — it would fail closed with no other CI signal:\n")
    for r in own_denied:
        sys.stderr.write(f"    {r}\n")
if missing:
    ok = False
    sys.stderr.write(
        f"these Bash allows in {settings_path} are NOT denied in "
        f"{backstop_path} (the {half} half inherits them via "
        f"settingSources=project):\n")
    for r in missing:
        sys.stderr.write(f"    {r}\n")
    sys.stderr.write(f"  → add each to {backstop_path} permissions.deny.\n")
if missing_required:
    ok = False
    sys.stderr.write(
        f"required denies (sibling write surfaces / the other half's tool / "
        f"file-write tools) are missing from {backstop_path}:\n")
    for alts in missing_required:
        sys.stderr.write(f"    {' or '.join(alts)}\n")

sys.exit(0 if ok else 1)
PY
}

selftest() {
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # A minimal-but-complete good pair: one dangerous allow, every required
  # deny present, neither the wrapper nor the half's own tool denied.
  cat > "$tmp/good-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  cat > "$tmp/good-wright.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__reeve_signoff","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/good-wright.json" wright 2>/dev/null; then
    echo "ok    selftest: complete wright deny coverage passes"
  else
    echo "FAIL  selftest: a complete wright deny list was rejected"; return 1
  fi

  # The same list works as the signoff half only with the cross-deny swapped.
  cat > "$tmp/good-signoff.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/good-signoff.json" signoff 2>/dev/null; then
    echo "ok    selftest: complete signoff deny coverage passes"
  else
    echo "FAIL  selftest: a complete signoff deny list was rejected"; return 1
  fi

  # BAD 1: an undenied dangerous allow → must fail.
  cat > "$tmp/bad1-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(git:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  if check_pair "$tmp/bad1-settings.json" "$tmp/good-wright.json" wright 2>/dev/null; then
    echo "FAIL  selftest: an undenied Bash allow was NOT caught"; return 1
  else
    echo "ok    selftest: an undenied Bash allow fails the check"
  fi

  # BAD 2: the CROSS deny is dropped — wright-settings without
  # mcp__reeve_signoff would let the proposer hold the arming tool. Coverage
  # alone would never catch it (the server is on no allow list).
  cat > "$tmp/bad2-wright.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad2-wright.json" wright 2>/dev/null; then
    echo "FAIL  selftest: a dropped cross-tool deny (mcp__reeve_signoff) was NOT caught"; return 1
  else
    echo "ok    selftest: dropping the cross-tool deny fails the check"
  fi

  # BAD 3: a required sibling-wrapper deny is dropped (assessor-helper's
  # ./-form) — the assessor-check BAD 4 pattern.
  cat > "$tmp/bad3-wright.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__reeve_signoff","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad3-wright.json" wright 2>/dev/null; then
    echo "FAIL  selftest: a dropped sibling-wrapper deny was NOT caught"; return 1
  else
    echo "ok    selftest: a dropped required sibling-wrapper deny fails the check"
  fi

  # BAD 4: the shared read wrapper itself is denied → must fail (fails closed).
  cat > "$tmp/bad4-wright.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__reeve_signoff","Write","Edit","NotebookEdit","Bash(.claude/skills/wright/wright-helper.sh:*)"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad4-wright.json" wright 2>/dev/null; then
    echo "FAIL  selftest: a denied read wrapper was NOT caught"; return 1
  else
    echo "ok    selftest: denying the read wrapper fails the check"
  fi

  # BAD 5: the signoff backstop denies its OWN posting tool (here via a
  # wildcard) → must fail — the scheduled sign-off could never rule.
  cat > "$tmp/bad5-signoff.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","Write","Edit","NotebookEdit","mcp__reeve_*"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad5-signoff.json" signoff 2>/dev/null; then
    echo "FAIL  selftest: a wildcard deny blocking the sign-off tool was NOT caught"; return 1
  else
    echo "ok    selftest: a wildcard deny blocking the own tool fails the check"
  fi
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    wright-perms-check selftest passed"
  exit 0
fi

[[ -f "$SETTINGS" ]] || { echo "FAIL  wright-perms: $SETTINGS missing"; exit 1; }
[[ -f "$WRIGHT"   ]] || { echo "FAIL  wright-perms: $WRIGHT missing"; exit 1; }
[[ -f "$SIGNOFF"  ]] || { echo "FAIL  wright-perms: $SIGNOFF missing"; exit 1; }

fail=0
if check_pair "$SETTINGS" "$WRIGHT" wright; then
  echo "ok    wright (propose) deny backstop covers every non-wrapper Bash allow + all sibling surfaces + the sign-off tool"
else
  echo "FAIL  wright permission drift: $WRIGHT does not neutralize every dangerous allow in $SETTINGS"
  fail=1
fi
if check_pair "$SETTINGS" "$SIGNOFF" signoff; then
  echo "ok    reeve-signoff deny backstop covers every non-wrapper Bash allow + all sibling surfaces + the filing tool"
else
  echo "FAIL  reeve-signoff permission drift: $SIGNOFF does not neutralize every dangerous allow in $SETTINGS"
  fail=1
fi
exit "$fail"
