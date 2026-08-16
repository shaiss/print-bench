#!/usr/bin/env bash
# Labeler permission-drift check: prove the labeler's OWN deny backstop
# (.claude/labeler-settings.json) still neutralizes every dangerous tool allow it
# would otherwise inherit, AND never denies the labeler's one wrapper. Run by
# scripts/check.sh (and therefore by /preflight and CI's scad-check jobs).
#
# WHY THIS EXISTS, and why it is SEPARATE from chunker-perms-check.sh:
# .github/workflows/labeler.yml runs claude-code-action, which starts the SDK
# with settingSources:[user,project,local] — so it loads this repo's
# .claude/settings.json permissions.allow. That file carries dev entries the
# interactive / backlog-burn / design-run agents need, including
# `Bash(xvfb-run:*)` (arbitrary command execution) AND
# `Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)` (the chunker's wrapper,
# which can create issues and comments). Allow rules merge ADDITIVELY across
# sources, so the labeler's narrow --allowedTools does NOT remove them. The
# labeler closes this with its own backstop (.claude/labeler-settings.json,
# passed via --settings): deny beats allow from every source.
#
# The labeler needs a DIFFERENT backstop from the chunker because the two
# wrappers are not interchangeable: the chunker's backstop must LEAVE
# chunk-helper.sh usable (it is the chunker's only surface), whereas the labeler
# must DENY chunk-helper.sh (it is not the labeler's surface, and it can create
# issues — beyond the labeler's add-only intent). So the labeler's wrapper is
# label-helper.sh, and chunk-helper.sh is just another dangerous allow it must
# neutralize. Because label-helper.sh is NOT on settings.json's allow-list, the
# coverage rule below ("every non-wrapper Bash allow in settings.json must be
# denied") already forces chunk-helper.sh (and every other allow) to be denied —
# no special-case needed.
#
# That backstop is only as good as its coverage. Add a Bash allow to
# settings.json tomorrow and, unless it is also denied here, the labeler silently
# inherits it again — an invisible regression, because the thing being protected
# is the ABSENCE of a capability. This check makes that regression fail loudly:
# every non-wrapper Bash allow in settings.json must be denied in
# labeler-settings.json, and the wrapper (label-helper.sh) must NOT be denied
# (or the scheduled labeler fails closed with no other CI signal — the reliability
# gap Qodo flagged). Extra denies (Write, Edit, chunk-helper, …) are fine — this
# asserts coverage, not equality.
#
# Usage:
#   scripts/labeler-perms-check.sh            # check the real files
#   scripts/labeler-perms-check.sh --selftest # prove the check can pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/settings.json"
LABELER=".claude/labeler-settings.json"

# Core comparison, pure function of two settings files. Prints a diagnosis and
# returns non-zero on any drift. Kept as a function so --selftest can point it
# at fixtures.
check_pair() {
  local settings_path="$1" labeler_path="$2"
  python3 - "$settings_path" "$labeler_path" <<'PY'
import fnmatch, json, sys

settings_path, labeler_path = sys.argv[1], sys.argv[2]

# The labeler's ONE approved shell surface, identified by its EXACT allow rule
# (both the bare and ./-prefixed forms) — never by a loose substring. A
# same-basename rule on a different path is NOT the wrapper and must still be
# denied, so it must not be exempted here.
WRAPPER_RULES = {
    "Bash(.claude/skills/label-issues/label-helper.sh:*)",
    "Bash(./.claude/skills/label-issues/label-helper.sh:*)",
}
# The command paths a deny rule must never match, or the labeler loses its only
# surface. Matched with wildcard semantics so a *broad* deny pattern can't slip
# past (e.g. Bash(.claude/skills/label-issues/*:*) or Bash(*label-helper.sh:*)).
WRAPPER_CMDS = [
    ".claude/skills/label-issues/label-helper.sh",
    "./.claude/skills/label-issues/label-helper.sh",
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
deny  = load(labeler_path).get("permissions", {}).get("deny", [])
deny_set = set(deny)

# Coverage: every non-wrapper Bash allow must be denied verbatim. label-helper.sh
# is not on settings.json's allow-list, so this covers chunk-helper.sh too — the
# labeler must deny it, which is the whole point of a separate backstop.
missing = [r for r in allow
           if r.startswith("Bash(") and r not in WRAPPER_RULES and r not in deny_set]
# Safety: no deny rule may match the wrapper command, wildcards included.
wrapper_denied = [d for d in deny if deny_blocks_wrapper(d)]

ok = True
if wrapper_denied:
    ok = False
    sys.stderr.write(
        "a deny rule would block the labeler wrapper — the scheduled labeler "
        "would fail closed:\n")
    for r in wrapper_denied:
        sys.stderr.write(f"    {r}\n")
if missing:
    ok = False
    sys.stderr.write(
        f"these Bash allows in {settings_path} are NOT denied in "
        f"{labeler_path} (the labeler inherits them via settingSources=project):\n")
    for r in missing:
        sys.stderr.write(f"    {r}\n")
    sys.stderr.write(
        "  → add each to .claude/labeler-settings.json permissions.deny.\n")

sys.exit(0 if ok else 1)
PY
}

selftest() {
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # GOOD: every non-wrapper Bash allow (chunk-helper included) is denied; the
  # labeler wrapper is not denied.
  cat > "$tmp/good-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)"]}}
EOF
  cat > "$tmp/good-labeler.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Write"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/good-labeler.json" 2>/dev/null; then
    echo "ok    selftest: complete deny coverage passes"
  else
    echo "FAIL  selftest: a complete deny list was rejected"; return 1
  fi

  # BAD 1: chunk-helper is left undenied → must fail (the labeler would inherit
  # the chunker's issue-creating wrapper).
  cat > "$tmp/bad-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)"]}}
EOF
  cat > "$tmp/bad-labeler.json" <<'EOF'
{"permissions":{"deny":["Write"]}}
EOF
  if check_pair "$tmp/bad-settings.json" "$tmp/bad-labeler.json" 2>/dev/null; then
    echo "FAIL  selftest: an undenied chunk-helper allow was NOT caught"; return 1
  else
    echo "ok    selftest: an undenied chunk-helper allow fails the check"
  fi

  # BAD 2: the labeler wrapper itself is denied → must fail (fails closed).
  cat > "$tmp/wd-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(.claude/skills/label-issues/label-helper.sh:*)"]}}
EOF
  cat > "$tmp/wd-labeler.json" <<'EOF'
{"permissions":{"deny":["Bash(.claude/skills/label-issues/label-helper.sh:*)"]}}
EOF
  if check_pair "$tmp/wd-settings.json" "$tmp/wd-labeler.json" 2>/dev/null; then
    echo "FAIL  selftest: a denied wrapper was NOT caught"; return 1
  else
    echo "ok    selftest: denying the wrapper fails the check"
  fi

  # BAD 3: a BROAD deny pattern that matches the wrapper path still blocks it.
  cat > "$tmp/broad-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(.claude/skills/label-issues/label-helper.sh:*)"]}}
EOF
  cat > "$tmp/broad-labeler.json" <<'EOF'
{"permissions":{"deny":["Bash(.claude/skills/label-issues/*:*)"]}}
EOF
  if check_pair "$tmp/broad-settings.json" "$tmp/broad-labeler.json" 2>/dev/null; then
    echo "FAIL  selftest: a wildcard deny blocking the wrapper was NOT caught"; return 1
  else
    echo "ok    selftest: a wildcard deny blocking the wrapper fails the check"
  fi
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    labeler-perms-check selftest passed"
  exit 0
fi

[[ -f "$SETTINGS" ]] || { echo "FAIL  labeler-perms: $SETTINGS missing"; exit 1; }
[[ -f "$LABELER"  ]] || { echo "FAIL  labeler-perms: $LABELER missing"; exit 1; }

if check_pair "$SETTINGS" "$LABELER"; then
  echo "ok    labeler deny backstop covers every non-wrapper Bash allow (chunk-helper included)"
else
  echo "FAIL  labeler permission drift: $LABELER does not neutralize every dangerous allow in $SETTINGS"
  exit 1
fi
