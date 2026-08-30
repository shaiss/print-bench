#!/usr/bin/env bash
# Reeve-greenlight permission-drift check: prove the greenlight loop's OWN deny
# backstop (.claude/reeve-settings.json) still neutralizes every dangerous tool
# allow it would otherwise inherit, denies every sibling routine's write
# surface, AND never denies the greenlight loop's one wrapper. Run by
# scripts/check.sh (and therefore by /preflight and CI's scad-check jobs).
#
# WHY THIS EXISTS, and why it is SEPARATE from the labeler/scout siblings: the
# Reeve greenlight drafter (issue #296 stage 2; this backstop landed first in
# #442, the LLM step that needs it joins in #443) reads UNTRUSTED issue text
# — anyone can open or comment on a parked decision — and its job holds a
# provider API-key secret. claude-code-action starts the SDK with
# settingSources:[user,project,local], so it loads this repo's
# .claude/settings.json permissions.allow, which carries dev entries including
# `Bash(xvfb-run:*)` (arbitrary command execution) and
# `Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)` (an issue-creating
# wrapper). Allow rules merge ADDITIVELY across sources, so the greenlight
# step's narrow --allowedTools does NOT remove them. The step closes that with
# its own backstop (.claude/reeve-settings.json, passed via --settings): deny
# beats allow from every source.
#
# The greenlight loop's ONE approved shell surface is
# .claude/skills/reeve-greenlight/greenlight-helper.sh (a wrapper in the
# labeler's shape: reads + exactly one marker-carrying write verb, bounded to
# the workflow-selected issues and capped per run). So the coverage rule keeps
# the labeler's wrapper exemption — the wrapper's own allow rule is not a
# dangerous inherit — while everything else settings.json allows must be
# denied verbatim. On top of that, the backstop must deny each sibling
# routine's write surface EXPLICITLY (chunk-helper.sh, label-helper.sh,
# scout-helper.sh, assessor-helper.sh and the agent forge's wright-helper.sh,
# each in both path spellings, plus the sibling MCP write servers), because
# most of those surfaces are not on settings.json's allow-list and the
# coverage rule alone would never force them. The one thing it must NOT deny
# is the greenlight wrapper itself, or the scheduled run fails closed with no
# other CI signal.
#
# That backstop is only as good as its coverage: add a Bash allow to
# settings.json tomorrow and, unless it is also denied here, the greenlight
# run silently inherits it — an invisible regression, because the thing being
# protected is the ABSENCE of a capability. This check makes that regression
# fail loudly. Extra denies are fine — this asserts coverage, not equality.
#
# Usage:
#   scripts/reeve-perms-check.sh            # check the real files
#   scripts/reeve-perms-check.sh --selftest # prove the check can pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/settings.json"
REEVE=".claude/reeve-settings.json"

# Core comparison, pure function of two settings files. Prints a diagnosis and
# returns non-zero on any drift. Kept as a function so --selftest can point it
# at fixtures.
check_pair() {
  local settings_path="$1" reeve_path="$2"
  python3 - "$settings_path" "$reeve_path" <<'PY'
import fnmatch, json, sys

settings_path, reeve_path = sys.argv[1], sys.argv[2]

# The greenlight loop's ONE approved shell surface, identified by its EXACT
# allow rule (both the bare and ./-prefixed forms) — never by a loose
# substring. A same-basename rule on a different path is NOT the wrapper and
# must still be denied, so it must not be exempted here.
WRAPPER_RULES = {
    "Bash(.claude/skills/reeve-greenlight/greenlight-helper.sh:*)",
    "Bash(./.claude/skills/reeve-greenlight/greenlight-helper.sh:*)",
}
# The command paths a deny rule must never match, or the greenlight loop loses
# its only surface. Matched with wildcard semantics so a *broad* deny pattern
# can't slip past (e.g. Bash(.claude/skills/reeve-greenlight/*:*)).
WRAPPER_CMDS = [
    ".claude/skills/reeve-greenlight/greenlight-helper.sh",
    "./.claude/skills/reeve-greenlight/greenlight-helper.sh",
]

# The sibling routines' write surfaces, which the greenlight backstop must
# deny VERBATIM even though most never appear on settings.json's allow-list
# (the coverage rule below would never force them, so they are asserted
# explicitly — the dropped-cross-deny case coverage alone can never catch).
# `mcp` entries accept the server-level deny or the tool-level one.
REQUIRED_DENIES = [
    {"Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"},
    {"Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)"},
    {"Bash(.claude/skills/label-issues/label-helper.sh:*)"},
    {"Bash(./.claude/skills/label-issues/label-helper.sh:*)"},
    {"Bash(.claude/skills/product-scout/scout-helper.sh:*)"},
    {"Bash(./.claude/skills/product-scout/scout-helper.sh:*)"},
    {"Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)"},
    {"Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)"},
    {"Bash(.claude/skills/wright/wright-helper.sh:*)"},
    {"Bash(./.claude/skills/wright/wright-helper.sh:*)"},
    {"mcp__scout", "mcp__scout__file_design_brief"},
    {"mcp__assessor", "mcp__assessor__post_adoption_disposition"},
    {"mcp__oracle", "mcp__oracle__post_oracle_review"},
    {"mcp__wright", "mcp__wright__file_agent_brief"},
    {"mcp__reeve_signoff", "mcp__reeve_signoff__post_reeve_signoff"},
    {"mcp__growth_queue", "mcp__growth_queue__queue_growth_post"},
    {"mcp__growth_twitter", "mcp__growth_twitter__post_tweet"},
    {"Write"},
    {"Edit"},
    {"NotebookEdit"},
]

def load(path):
    with open(path) as fh:
        return json.load(fh)

def deny_blocks_wrapper(rule):
    # A Bash(<cmd>:<args>) deny whose command pattern matches the wrapper path
    # (wildcards included) would block the wrapper. Non-Bash denies (Write, …)
    # never do.
    if not (rule.startswith("Bash(") and rule.endswith(")")):
        return False
    cmd_pat = rule[len("Bash("):-1].split(":", 1)[0]
    return any(fnmatch.fnmatch(cmd, cmd_pat) for cmd in WRAPPER_CMDS)

allow = load(settings_path).get("permissions", {}).get("allow", [])
deny  = load(reeve_path).get("permissions", {}).get("deny", [])
deny_set = set(deny)

# Coverage: every non-wrapper Bash allow must be denied verbatim.
missing = [r for r in allow
           if r.startswith("Bash(") and r not in WRAPPER_RULES and r not in deny_set]
# The sibling surfaces + file-write tools, asserted explicitly.
missing_required = [sorted(alts) for alts in REQUIRED_DENIES
                    if not (alts & deny_set)]
# Safety: no deny rule may match the wrapper command, wildcards included.
wrapper_denied = [d for d in deny if deny_blocks_wrapper(d)]

ok = True
if wrapper_denied:
    ok = False
    sys.stderr.write(
        "a deny rule would block the greenlight wrapper — the scheduled run "
        "would fail closed:\n")
    for r in wrapper_denied:
        sys.stderr.write(f"    {r}\n")
if missing:
    ok = False
    sys.stderr.write(
        f"these Bash allows in {settings_path} are NOT denied in "
        f"{reeve_path} (the greenlight run inherits them via "
        f"settingSources=project):\n")
    for r in missing:
        sys.stderr.write(f"    {r}\n")
    sys.stderr.write(
        "  → add each to .claude/reeve-settings.json permissions.deny.\n")
if missing_required:
    ok = False
    sys.stderr.write(
        f"these required denies (sibling write surfaces / file-write tools) "
        f"are missing from {reeve_path}:\n")
    for alts in missing_required:
        sys.stderr.write(f"    {' or '.join(alts)}\n")

sys.exit(0 if ok else 1)
PY
}

selftest() {
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # A minimal-but-complete deny list the good fixtures share: every sibling
  # surface and file-write tool, plus the one Bash allow the good settings
  # fixture carries.
  cat > "$tmp/good-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  cat > "$tmp/good-reeve.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","mcp__reeve_signoff","mcp__growth_queue","mcp__growth_twitter","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/good-reeve.json" 2>/dev/null; then
    echo "ok    selftest: complete deny coverage passes"
  else
    echo "FAIL  selftest: a complete deny list was rejected"; return 1
  fi

  # BAD 1: a dangerous Bash allow is left undenied → must fail (the greenlight
  # run would inherit it).
  cat > "$tmp/bad1-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(git:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  if check_pair "$tmp/bad1-settings.json" "$tmp/good-reeve.json" 2>/dev/null; then
    echo "FAIL  selftest: an undenied Bash allow was NOT caught"; return 1
  else
    echo "ok    selftest: an undenied Bash allow fails the check"
  fi

  # BAD 2: a sibling write surface (the labeler's wrapper) is not denied →
  # must fail, even though it never appears on settings.json's allow-list —
  # exactly why the required-denies list exists (the dropped-cross-deny case
  # coverage alone can never catch).
  cat > "$tmp/bad2-reeve.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","mcp__reeve_signoff","mcp__growth_queue","mcp__growth_twitter","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad2-reeve.json" 2>/dev/null; then
    echo "FAIL  selftest: a missing label-helper deny was NOT caught"; return 1
  else
    echo "ok    selftest: a missing sibling-wrapper deny fails the check"
  fi

  # BAD 3: the greenlight wrapper itself is denied → must fail (fails closed).
  cat > "$tmp/bad3-reeve.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","mcp__reeve_signoff","mcp__growth_queue","mcp__growth_twitter","Write","Edit","NotebookEdit","Bash(.claude/skills/reeve-greenlight/greenlight-helper.sh:*)"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad3-reeve.json" 2>/dev/null; then
    echo "FAIL  selftest: a denied wrapper was NOT caught"; return 1
  else
    echo "ok    selftest: denying the wrapper fails the check"
  fi

  # BAD 4: a BROAD deny pattern that matches the wrapper path still blocks it.
  cat > "$tmp/bad4-reeve.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","mcp__reeve_signoff","mcp__growth_queue","mcp__growth_twitter","Write","Edit","NotebookEdit","Bash(.claude/skills/reeve-greenlight/*:*)"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad4-reeve.json" 2>/dev/null; then
    echo "FAIL  selftest: a wildcard deny blocking the wrapper was NOT caught"; return 1
  else
    echo "ok    selftest: a wildcard deny blocking the wrapper fails the check"
  fi
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    reeve-perms-check selftest passed"
  exit 0
fi

[[ -f "$SETTINGS" ]] || { echo "FAIL  reeve-perms: $SETTINGS missing"; exit 1; }
[[ -f "$REEVE"   ]] || { echo "FAIL  reeve-perms: $REEVE missing"; exit 1; }

if check_pair "$SETTINGS" "$REEVE"; then
  echo "ok    reeve deny backstop covers every non-wrapper Bash allow + all sibling write surfaces, and leaves greenlight-helper.sh usable"
else
  echo "FAIL  reeve permission drift: $REEVE does not neutralize every dangerous allow in $SETTINGS"
  exit 1
fi
