#!/usr/bin/env bash
# Chunker permission-drift check: prove the chunker's deny backstop still
# neutralizes every dangerous tool allow it would otherwise inherit. Run by
# scripts/check.sh (and therefore by /preflight and CI's scad-check jobs).
#
# WHY THIS EXISTS (the negative a wrapper cannot prove on its own):
# .github/workflows/chunker.yml runs claude-code-action, which starts the SDK
# with settingSources:[user,project,local] — so it loads this repo's
# .claude/settings.json permissions.allow. That file carries dev entries the
# interactive / backlog-burn / design-run agents need, including
# `Bash(xvfb-run:*)` — arbitrary command execution. Allow rules merge
# ADDITIVELY across sources, so the chunker's narrow --allowedTools does NOT
# remove them: on its own, the wrapper allow-list is not exclusive, and a
# prompt-injection from untrusted issue text could reach xvfb-run and exfiltrate
# the provider-key secret. The chunker closes this with a deny backstop
# (.claude/chunker-settings.json, passed via --settings): deny rules beat allow
# rules from every source, so each dangerous allow is neutralized.
#
# That backstop is only as good as its coverage. Add a Bash allow to
# settings.json tomorrow and, unless it is also denied here, the chunker
# silently inherits it again — a regression that is invisible because the thing
# being protected is the ABSENCE of a capability. This check makes that
# regression fail loudly: every non-wrapper Bash allow in settings.json must be
# denied in chunker-settings.json, and the wrapper itself must NOT be denied
# (or the chunker loses its only shell surface). Extra denies (Write, Edit, …)
# are fine — this asserts coverage, not equality.
#
# Usage:
#   scripts/chunker-perms-check.sh            # check the real files
#   scripts/chunker-perms-check.sh --selftest # prove the check can pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/settings.json"
CHUNKER=".claude/chunker-settings.json"

# Core comparison, pure function of two settings files. Prints a diagnosis and
# returns non-zero on any drift. Kept as a function so --selftest can point it
# at fixtures.
check_pair() {
  local settings_path="$1" chunker_path="$2"
  python3 - "$settings_path" "$chunker_path" <<'PY'
import fnmatch, json, sys

settings_path, chunker_path = sys.argv[1], sys.argv[2]

# The chunker's ONE approved shell surface, identified by its EXACT allow rule
# (both the bare and ./-prefixed forms committed in settings.json) — never by a
# loose "contains chunk-helper.sh" substring. A same-basename rule on a
# different path (e.g. Bash(/tmp/chunk-helper.sh:*)) is NOT the wrapper and must
# still be denied, so it must not be exempted here.
WRAPPER_RULES = {
    "Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)",
    "Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)",
}
# The command paths a deny rule must never match, or the chunker loses its only
# surface. Matched with wildcard semantics so a *broad* deny pattern can't slip
# past (e.g. Bash(.claude/skills/chunk-issue/*:*) or Bash(*chunk-helper.sh:*)).
WRAPPER_CMDS = [
    ".claude/skills/chunk-issue/chunk-helper.sh",
    "./.claude/skills/chunk-issue/chunk-helper.sh",
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
deny  = load(chunker_path).get("permissions", {}).get("deny", [])
deny_set = set(deny)

# Coverage: every non-wrapper Bash allow must be denied verbatim (exact-rule
# exemption for the wrapper — a rogue same-basename path is not exempt).
missing = [r for r in allow
           if r.startswith("Bash(") and r not in WRAPPER_RULES and r not in deny_set]
# Safety: no deny rule may match the wrapper command, wildcards included.
wrapper_denied = [d for d in deny if deny_blocks_wrapper(d)]

ok = True
if wrapper_denied:
    ok = False
    sys.stderr.write(
        "a deny rule would block the wrapper — the chunker would lose its only "
        "shell surface:\n")
    for r in wrapper_denied:
        sys.stderr.write(f"    {r}\n")
if missing:
    ok = False
    sys.stderr.write(
        f"these Bash allows in {settings_path} are NOT denied in "
        f"{chunker_path} (the chunker inherits them via settingSources=project):\n")
    for r in missing:
        sys.stderr.write(f"    {r}\n")
    sys.stderr.write(
        "  → add each to .claude/chunker-settings.json permissions.deny.\n")

sys.exit(0 if ok else 1)
PY
}

selftest() {
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # GOOD: every non-wrapper Bash allow is denied; wrapper is not denied.
  cat > "$tmp/good-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  cat > "$tmp/good-chunker.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Write"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/good-chunker.json" 2>/dev/null; then
    echo "ok    selftest: complete deny coverage passes"
  else
    echo "FAIL  selftest: a complete deny list was rejected"; return 1
  fi

  # BAD 1: a dangerous allow is left undenied → must fail.
  cat > "$tmp/bad-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(rm:*)"]}}
EOF
  cat > "$tmp/bad-chunker.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)"]}}
EOF
  if check_pair "$tmp/bad-settings.json" "$tmp/bad-chunker.json" 2>/dev/null; then
    echo "FAIL  selftest: an undenied dangerous allow was NOT caught"; return 1
  else
    echo "ok    selftest: an undenied dangerous allow fails the check"
  fi

  # BAD 2: the wrapper itself is denied → must fail.
  cat > "$tmp/wd-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  cat > "$tmp/wd-chunker.json" <<'EOF'
{"permissions":{"deny":["Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  if check_pair "$tmp/wd-settings.json" "$tmp/wd-chunker.json" 2>/dev/null; then
    echo "FAIL  selftest: a denied wrapper was NOT caught"; return 1
  else
    echo "ok    selftest: denying the wrapper fails the check"
  fi

  # BAD 3: a rogue allow with the wrapper's BASENAME but a different path is NOT
  # the wrapper — it must not be exempted, so an undenied one must fail.
  cat > "$tmp/rogue-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(/tmp/chunk-helper.sh:*)"]}}
EOF
  cat > "$tmp/rogue-chunker.json" <<'EOF'
{"permissions":{"deny":[]}}
EOF
  if check_pair "$tmp/rogue-settings.json" "$tmp/rogue-chunker.json" 2>/dev/null; then
    echo "FAIL  selftest: a same-basename rogue path was wrongly exempted"; return 1
  else
    echo "ok    selftest: a same-basename rogue path is not exempt from deny"
  fi

  # BAD 4: a BROAD deny pattern that matches the wrapper path (not the verbatim
  # wrapper rule) still blocks the wrapper → must fail.
  cat > "$tmp/broad-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  cat > "$tmp/broad-chunker.json" <<'EOF'
{"permissions":{"deny":["Bash(.claude/skills/chunk-issue/*:*)"]}}
EOF
  if check_pair "$tmp/broad-settings.json" "$tmp/broad-chunker.json" 2>/dev/null; then
    echo "FAIL  selftest: a wildcard deny blocking the wrapper was NOT caught"; return 1
  else
    echo "ok    selftest: a wildcard deny blocking the wrapper fails the check"
  fi
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    chunker-perms-check selftest passed"
  exit 0
fi

[[ -f "$SETTINGS" ]] || { echo "FAIL  chunker-perms: $SETTINGS missing"; exit 1; }
[[ -f "$CHUNKER"  ]] || { echo "FAIL  chunker-perms: $CHUNKER missing"; exit 1; }

if check_pair "$SETTINGS" "$CHUNKER"; then
  echo "ok    chunker deny backstop covers every non-wrapper Bash allow"
else
  echo "FAIL  chunker permission drift: $CHUNKER does not neutralize every dangerous allow in $SETTINGS"
  exit 1
fi
