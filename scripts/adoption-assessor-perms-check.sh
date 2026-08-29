#!/usr/bin/env bash
# Adoption-assessor permission-drift check: prove the adoption-study assessor's
# OWN deny backstop (.claude/adoption-assessor-settings.json) still neutralizes
# every dangerous tool allow it would otherwise inherit, AND never denies the
# assessor's one wrapper. Run by scripts/check.sh (and therefore by /preflight
# and CI's scad-check jobs).
#
# WHY THIS EXISTS, and why it is SEPARATE from chunker-/labeler-/scout-perms-check:
# .github/workflows/adoption-assessor.yml runs claude-code-action, which starts
# the SDK with settingSources:[user,project,local] — so it loads this repo's
# .claude/settings.json permissions.allow. That file carries dev entries the
# interactive / backlog-burn / design-run agents need, including
# `Bash(xvfb-run:*)` (arbitrary command execution), the chunker's
# chunk-helper.sh (which can create issues), the labeler's label-helper.sh
# (which can APPLY routing labels), and the scout's scout-helper.sh (which
# reads the brief backlog for its filing tool). Allow rules merge ADDITIVELY
# across sources, so the assessor's narrow --allowedTools does NOT remove them.
# The assessor closes this with its own backstop
# (.claude/adoption-assessor-settings.json, passed via --settings): deny beats
# allow from every source.
#
# The assessor needs a backstop distinct from EVERY sibling: the chunker's must
# LEAVE chunk-helper usable, the labeler's must LEAVE label-helper usable, the
# scout's must LEAVE scout-helper usable — but the assessor must DENY ALL THREE
# (none is its surface; each is another issue-/label-writing capability it must
# not inherit). This is the widest deny set of the family. The assessor's
# wrapper is assessor-helper.sh, and every other wrapper is just another
# dangerous allow it must neutralize. Because assessor-helper.sh is NOT on
# settings.json's allow-list, the coverage rule below ("every non-wrapper Bash
# allow in settings.json must be denied") already forces chunk-helper.sh to be
# denied; scout-helper.sh and label-helper.sh are NOT on that allow-list, so
# coverage alone would not require them — the check therefore pins all three
# sibling wrappers (both path spellings) plus Write/Edit/NotebookEdit in an
# explicit REQUIRED_DENIES set, so dropping any one of them fails loudly.
#
# That backstop is only as good as its coverage. Add a Bash allow to
# settings.json tomorrow and, unless it is also denied here, the assessor
# silently inherits it again — an invisible regression, because the thing being
# protected is the ABSENCE of a capability. This check makes that regression
# fail loudly: every non-wrapper Bash allow in settings.json must be denied in
# adoption-assessor-settings.json, and the wrapper (assessor-helper.sh) must NOT
# be denied (or the scheduled assessor fails closed with no other CI signal).
# Extra denies (Write, Edit, chunk-helper, label-helper, scout-helper, …) are
# fine — this asserts coverage, not equality.
#
# Usage:
#   scripts/adoption-assessor-perms-check.sh            # check the real files
#   scripts/adoption-assessor-perms-check.sh --selftest # prove it can pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/settings.json"
ASSESSOR=".claude/adoption-assessor-settings.json"

# Core comparison, pure function of two settings files. Prints a diagnosis and
# returns non-zero on any drift. Kept as a function so --selftest can point it
# at fixtures.
check_pair() {
  local settings_path="$1" assessor_path="$2"
  python3 - "$settings_path" "$assessor_path" <<'PY'
import fnmatch, json, sys

settings_path, assessor_path = sys.argv[1], sys.argv[2]

# The assessor's ONE approved shell surface, identified by its EXACT allow rule
# (both the bare and ./-prefixed forms) — never by a loose substring. A
# same-basename rule on a different path is NOT the wrapper and must still be
# denied, so it must not be exempted here.
WRAPPER_RULES = {
    "Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)",
    "Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)",
}
# The command paths a deny rule must never match, or the assessor loses its only
# surface. Matched with wildcard semantics so a *broad* deny pattern can't slip
# past (e.g. Bash(.claude/skills/adoption-assessor/*:*) or Bash(*assessor-helper.sh:*)).
WRAPPER_CMDS = [
    ".claude/skills/adoption-assessor/assessor-helper.sh",
    "./.claude/skills/adoption-assessor/assessor-helper.sh",
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
deny  = load(assessor_path).get("permissions", {}).get("deny", [])
deny_set = set(deny)

# Required denies the backstop must ALWAYS carry, whatever settings.json allows
# today. The coverage rule below only forces denying what is CURRENTLY on
# settings.json's allow-list — so it catches chunk-helper.sh (which is on it) but
# NOT label-helper.sh / scout-helper.sh (which are not), and would let their deny,
# or the Write/Edit/NotebookEdit denies, be dropped silently. The "widest backstop
# in the family" invariant is that ALL THREE sibling wrappers (both path spellings)
# and the file-mutating tools stay denied regardless — so require them explicitly.
REQUIRED_DENIES = {
    "Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)",
    "Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)",
    "Bash(.claude/skills/label-issues/label-helper.sh:*)",
    "Bash(./.claude/skills/label-issues/label-helper.sh:*)",
    "Bash(.claude/skills/product-scout/scout-helper.sh:*)",
    "Bash(./.claude/skills/product-scout/scout-helper.sh:*)",
    "Bash(.claude/skills/wright/wright-helper.sh:*)",
    "Bash(./.claude/skills/wright/wright-helper.sh:*)",
    "Write", "Edit", "NotebookEdit",
}
missing_required = sorted(REQUIRED_DENIES - deny_set)

# Coverage: every non-wrapper Bash allow must be denied verbatim. assessor-helper.sh
# is not on settings.json's allow-list, so this covers chunk-helper.sh too; the
# sibling wrappers and file-mutating tools are additionally pinned by
# REQUIRED_DENIES above so their deny cannot be dropped without failing this check.
missing = [r for r in allow
           if r.startswith("Bash(") and r not in WRAPPER_RULES and r not in deny_set]
# Safety: no deny rule may match the wrapper command, wildcards included.
wrapper_denied = [d for d in deny if deny_blocks_wrapper(d)]

ok = True
if wrapper_denied:
    ok = False
    sys.stderr.write(
        "a deny rule would block the assessor wrapper — the scheduled assessor "
        "would fail closed:\n")
    for r in wrapper_denied:
        sys.stderr.write(f"    {r}\n")
if missing:
    ok = False
    sys.stderr.write(
        f"these Bash allows in {settings_path} are NOT denied in "
        f"{assessor_path} (the assessor inherits them via settingSources=project):\n")
    for r in missing:
        sys.stderr.write(f"    {r}\n")
    sys.stderr.write(
        "  → add each to .claude/adoption-assessor-settings.json permissions.deny.\n")
if missing_required:
    ok = False
    sys.stderr.write(
        f"required assessor deny rules are missing from {assessor_path} — the "
        "widest backstop must deny all three sibling wrappers (both spellings) and "
        "Write/Edit/NotebookEdit regardless of settings.json:\n")
    for r in missing_required:
        sys.stderr.write(f"    {r}\n")

sys.exit(0 if ok else 1)
PY
}

selftest() {
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # GOOD: every non-wrapper Bash allow (all three sibling wrappers included) is
  # denied; the assessor wrapper is not denied.
  cat > "$tmp/good-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)"]}}
EOF
  cat > "$tmp/good-assessor.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/good-assessor.json" 2>/dev/null; then
    echo "ok    selftest: complete deny coverage passes"
  else
    echo "FAIL  selftest: a complete deny list was rejected"; return 1
  fi

  # BAD 1: an undenied dangerous allow (xvfb-run left off the deny list) → must fail.
  cat > "$tmp/bad1-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)"]}}
EOF
  cat > "$tmp/bad1-assessor.json" <<'EOF'
{"permissions":{"deny":["Write"]}}
EOF
  if check_pair "$tmp/bad1-settings.json" "$tmp/bad1-assessor.json" 2>/dev/null; then
    echo "FAIL  selftest: an undenied dangerous allow was NOT caught"; return 1
  else
    echo "ok    selftest: an undenied dangerous allow fails the check"
  fi

  # BAD 2: the assessor wrapper itself is denied → must fail (fails closed).
  cat > "$tmp/bad2-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)"]}}
EOF
  cat > "$tmp/bad2-assessor.json" <<'EOF'
{"permissions":{"deny":["Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)"]}}
EOF
  if check_pair "$tmp/bad2-settings.json" "$tmp/bad2-assessor.json" 2>/dev/null; then
    echo "FAIL  selftest: a denied wrapper was NOT caught"; return 1
  else
    echo "ok    selftest: denying the wrapper fails the check"
  fi

  # BAD 3: a BROAD deny pattern that matches the wrapper path still blocks it.
  cat > "$tmp/bad3-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)"]}}
EOF
  cat > "$tmp/bad3-assessor.json" <<'EOF'
{"permissions":{"deny":["Bash(.claude/skills/adoption-assessor/*:*)"]}}
EOF
  if check_pair "$tmp/bad3-settings.json" "$tmp/bad3-assessor.json" 2>/dev/null; then
    echo "FAIL  selftest: a wildcard deny blocking the wrapper was NOT caught"; return 1
  else
    echo "ok    selftest: a wildcard deny blocking the wrapper fails the check"
  fi

  # BAD 4: a REQUIRED sibling-wrapper deny is dropped (here scout-helper's ./-form)
  # even though settings.json does not allow it — coverage alone would pass, so the
  # explicit REQUIRED_DENIES set must catch it (the widest-backstop invariant).
  cat > "$tmp/bad4-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)"]}}
EOF
  cat > "$tmp/bad4-assessor.json" <<'EOF'
{"permissions":{"deny":["Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/bad4-settings.json" "$tmp/bad4-assessor.json" 2>/dev/null; then
    echo "FAIL  selftest: a dropped required sibling-wrapper deny was NOT caught"; return 1
  else
    echo "ok    selftest: a dropped required sibling-wrapper deny fails the check"
  fi
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    adoption-assessor-perms-check selftest passed"
  exit 0
fi

[[ -f "$SETTINGS" ]] || { echo "FAIL  adoption-assessor-perms: $SETTINGS missing"; exit 1; }
[[ -f "$ASSESSOR" ]] || { echo "FAIL  adoption-assessor-perms: $ASSESSOR missing"; exit 1; }

if check_pair "$SETTINGS" "$ASSESSOR"; then
  echo "ok    adoption-assessor deny backstop covers every non-wrapper Bash allow (chunk-helper + label-helper + scout-helper included)"
else
  echo "FAIL  adoption-assessor permission drift: $ASSESSOR does not neutralize every dangerous allow in $SETTINGS"
  exit 1
fi
