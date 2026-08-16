#!/usr/bin/env bash
# Scout permission-drift check: prove the product scout's OWN deny backstop
# (.claude/scout-settings.json) still neutralizes every dangerous tool allow it
# would otherwise inherit, AND never denies the scout's one wrapper. Run by
# scripts/check.sh (and therefore by /preflight and CI's scad-check jobs).
#
# WHY THIS EXISTS, and why it is SEPARATE from chunker- and labeler-perms-check:
# .github/workflows/product-scout.yml runs claude-code-action, which starts the
# SDK with settingSources:[user,project,local] — so it loads this repo's
# .claude/settings.json permissions.allow. That file carries dev entries the
# interactive / backlog-burn / design-run agents need, including
# `Bash(xvfb-run:*)` (arbitrary command execution), the chunker's
# chunk-helper.sh (which can create issues) and — for the scout — the labeler's
# label-helper.sh (which can APPLY routing labels, `autonomy-ok` included).
# Allow rules merge ADDITIVELY across sources, so the scout's narrow
# --allowedTools does NOT remove them. The scout closes this with its own
# backstop (.claude/scout-settings.json, passed via --settings): deny beats
# allow from every source.
#
# The scout needs a backstop distinct from BOTH siblings: the chunker's must
# LEAVE chunk-helper usable, the labeler's must LEAVE label-helper usable — but
# the scout must DENY BOTH (neither is its surface; both can write beyond the
# scout's file-a-design-brief remit). The scout's wrapper is scout-helper.sh,
# and every other wrapper is just another dangerous allow it must neutralize.
# Because scout-helper.sh is NOT on settings.json's allow-list, the coverage
# rule below ("every non-wrapper Bash allow in settings.json must be denied")
# already forces chunk-helper.sh and label-helper.sh (and every other allow) to
# be denied — no special-case needed.
#
# That backstop is only as good as its coverage. Add a Bash allow to
# settings.json tomorrow and, unless it is also denied here, the scout silently
# inherits it again — an invisible regression, because the thing being protected
# is the ABSENCE of a capability. This check makes that regression fail loudly:
# every non-wrapper Bash allow in settings.json must be denied in
# scout-settings.json, and the wrapper (scout-helper.sh) must NOT be denied (or
# the scheduled scout fails closed with no other CI signal). Extra denies (Write,
# Edit, chunk-helper, label-helper, …) are fine — this asserts coverage, not
# equality.
#
# Usage:
#   scripts/scout-perms-check.sh            # check the real files
#   scripts/scout-perms-check.sh --selftest # prove the check can pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/settings.json"
SCOUT=".claude/scout-settings.json"

# Core comparison, pure function of two settings files. Prints a diagnosis and
# returns non-zero on any drift. Kept as a function so --selftest can point it
# at fixtures.
check_pair() {
  local settings_path="$1" scout_path="$2"
  python3 - "$settings_path" "$scout_path" <<'PY'
import fnmatch, json, sys

settings_path, scout_path = sys.argv[1], sys.argv[2]

# The scout's ONE approved shell surface, identified by its EXACT allow rule
# (both the bare and ./-prefixed forms) — never by a loose substring. A
# same-basename rule on a different path is NOT the wrapper and must still be
# denied, so it must not be exempted here.
WRAPPER_RULES = {
    "Bash(.claude/skills/product-scout/scout-helper.sh:*)",
    "Bash(./.claude/skills/product-scout/scout-helper.sh:*)",
}
# The command paths a deny rule must never match, or the scout loses its only
# surface. Matched with wildcard semantics so a *broad* deny pattern can't slip
# past (e.g. Bash(.claude/skills/product-scout/*:*) or Bash(*scout-helper.sh:*)).
WRAPPER_CMDS = [
    ".claude/skills/product-scout/scout-helper.sh",
    "./.claude/skills/product-scout/scout-helper.sh",
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
deny  = load(scout_path).get("permissions", {}).get("deny", [])
deny_set = set(deny)

# Coverage: every non-wrapper Bash allow must be denied verbatim. scout-helper.sh
# is not on settings.json's allow-list, so this covers chunk-helper.sh and
# label-helper.sh too — the scout must deny both, which is the whole point of a
# separate backstop.
missing = [r for r in allow
           if r.startswith("Bash(") and r not in WRAPPER_RULES and r not in deny_set]
# Safety: no deny rule may match the wrapper command, wildcards included.
wrapper_denied = [d for d in deny if deny_blocks_wrapper(d)]

ok = True
if wrapper_denied:
    ok = False
    sys.stderr.write(
        "a deny rule would block the scout wrapper — the scheduled scout "
        "would fail closed:\n")
    for r in wrapper_denied:
        sys.stderr.write(f"    {r}\n")
if missing:
    ok = False
    sys.stderr.write(
        f"these Bash allows in {settings_path} are NOT denied in "
        f"{scout_path} (the scout inherits them via settingSources=project):\n")
    for r in missing:
        sys.stderr.write(f"    {r}\n")
    sys.stderr.write(
        "  → add each to .claude/scout-settings.json permissions.deny.\n")

sys.exit(0 if ok else 1)
PY
}

selftest() {
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # GOOD: every non-wrapper Bash allow (chunk-helper AND label-helper included)
  # is denied; the scout wrapper is not denied.
  cat > "$tmp/good-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)"]}}
EOF
  cat > "$tmp/good-scout.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Write"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/good-scout.json" 2>/dev/null; then
    echo "ok    selftest: complete deny coverage passes"
  else
    echo "FAIL  selftest: a complete deny list was rejected"; return 1
  fi

  # BAD 1: chunk-helper is left undenied → must fail.
  cat > "$tmp/bad1-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)"]}}
EOF
  cat > "$tmp/bad1-scout.json" <<'EOF'
{"permissions":{"deny":["Write"]}}
EOF
  if check_pair "$tmp/bad1-settings.json" "$tmp/bad1-scout.json" 2>/dev/null; then
    echo "FAIL  selftest: an undenied chunk-helper allow was NOT caught"; return 1
  else
    echo "ok    selftest: an undenied chunk-helper allow fails the check"
  fi

  # BAD 1b: label-helper is left undenied → must fail (the scout must not be
  # able to apply routing labels — the distinguishing requirement vs the labeler).
  cat > "$tmp/bad1b-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)"]}}
EOF
  cat > "$tmp/bad1b-scout.json" <<'EOF'
{"permissions":{"deny":["Write"]}}
EOF
  if check_pair "$tmp/bad1b-settings.json" "$tmp/bad1b-scout.json" 2>/dev/null; then
    echo "FAIL  selftest: an undenied label-helper allow was NOT caught"; return 1
  else
    echo "ok    selftest: an undenied label-helper allow fails the check"
  fi

  # BAD 2: the scout wrapper itself is denied → must fail (fails closed).
  cat > "$tmp/bad2-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(.claude/skills/product-scout/scout-helper.sh:*)"]}}
EOF
  cat > "$tmp/bad2-scout.json" <<'EOF'
{"permissions":{"deny":["Bash(.claude/skills/product-scout/scout-helper.sh:*)"]}}
EOF
  if check_pair "$tmp/bad2-settings.json" "$tmp/bad2-scout.json" 2>/dev/null; then
    echo "FAIL  selftest: a denied wrapper was NOT caught"; return 1
  else
    echo "ok    selftest: denying the wrapper fails the check"
  fi

  # BAD 3: a BROAD deny pattern that matches the wrapper path still blocks it.
  cat > "$tmp/bad3-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(.claude/skills/product-scout/scout-helper.sh:*)"]}}
EOF
  cat > "$tmp/bad3-scout.json" <<'EOF'
{"permissions":{"deny":["Bash(.claude/skills/product-scout/*:*)"]}}
EOF
  if check_pair "$tmp/bad3-settings.json" "$tmp/bad3-scout.json" 2>/dev/null; then
    echo "FAIL  selftest: a wildcard deny blocking the wrapper was NOT caught"; return 1
  else
    echo "ok    selftest: a wildcard deny blocking the wrapper fails the check"
  fi
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    scout-perms-check selftest passed"
  exit 0
fi

[[ -f "$SETTINGS" ]] || { echo "FAIL  scout-perms: $SETTINGS missing"; exit 1; }
[[ -f "$SCOUT"    ]] || { echo "FAIL  scout-perms: $SCOUT missing"; exit 1; }

if check_pair "$SETTINGS" "$SCOUT"; then
  echo "ok    scout deny backstop covers every non-wrapper Bash allow (chunk-helper + label-helper included)"
else
  echo "FAIL  scout permission drift: $SCOUT does not neutralize every dangerous allow in $SETTINGS"
  exit 1
fi
