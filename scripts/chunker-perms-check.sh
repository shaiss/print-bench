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
# The wrapper is the one Bash surface the chunker IS allowed to run; it is
# identified by this basename and must never be denied.
WRAPPER_SUBSTR="chunk-helper.sh"

# Core comparison, pure function of two settings files. Prints a diagnosis and
# returns non-zero on any drift. Kept as a function so --selftest can point it
# at fixtures.
check_pair() {
  local settings_path="$1" chunker_path="$2"
  WRAPPER_SUBSTR="$WRAPPER_SUBSTR" python3 - "$settings_path" "$chunker_path" <<'PY'
import json, os, sys

settings_path, chunker_path = sys.argv[1], sys.argv[2]
wrapper = os.environ["WRAPPER_SUBSTR"]

def load(path):
    with open(path) as fh:
        return json.load(fh)

allow = load(settings_path).get("permissions", {}).get("allow", [])
deny  = set(load(chunker_path).get("permissions", {}).get("deny", []))

missing = []          # non-wrapper Bash allows the chunker fails to deny
wrapper_denied = []   # wrapper allows wrongly denied

for rule in allow:
    if not rule.startswith("Bash("):
        continue
    if wrapper in rule:
        if rule in deny:
            wrapper_denied.append(rule)
        continue
    if rule not in deny:
        missing.append(rule)

ok = True
if wrapper_denied:
    ok = False
    sys.stderr.write(
        "the wrapper allow is also denied — the chunker would lose its only "
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
