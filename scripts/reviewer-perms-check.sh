#!/usr/bin/env bash
# Reviewer permission-drift check: prove the reviewer deny backstops
# (.claude/reviewer-settings.json and .claude/design-coach-settings.json) still
# neutralize every toolchain allow they would otherwise inherit from
# .claude/settings.json. Run by scripts/check.sh.
#
# WHY THIS EXISTS:
# .github/workflows/auto-review.yml runs claude-code-action, which starts the
# SDK with settingSources:[user,project,local] — so it loads this repo's
# .claude/settings.json permissions.allow. That file carries dev entries the
# interactive agents need, including `Bash(xvfb-run:*)` (arbitrary command
# execution) and render toolchain allows. Allow rules merge ADDITIVELY across
# sources, so the reviewers' narrow --allowedTools does NOT remove them. The
# reviewers close this with their own backstops (passed via --settings), where
# deny beats allow from every source.
#
# There are TWO reviewer backstops because their surfaces differ:
# - .claude/reviewer-settings.json: Jane, Drik, PM triage (read-only, deny
#   Write/Edit/NotebookEdit)
# - .claude/design-coach-settings.json: Design coach (pushes iterations,
#   allows Write/Edit, denies NotebookEdit)
#
# That backstop is only as good as its coverage. Add a Bash allow to
# settings.json tomorrow and, unless it is also denied here, the reviewers
# silently inherit it again — an invisible regression, because the thing being
# protected is the ABSENCE of a capability. This check makes that regression
# fail loudly: every non-wrapper Bash allow in settings.json must be denied in
# the reviewer backstops. Extra denies are fine — this asserts coverage, not
# equality.
#
# Usage:
#   scripts/reviewer-perms-check.sh            # check the real files
#   scripts/reviewer-perms-check.sh --selftest # prove the check can pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/settings.json"
REVIEWER=".claude/reviewer-settings.json"
COACH=".claude/design-coach-settings.json"

# Core comparison, pure function of two settings files. Prints a diagnosis and
# returns non-zero on any drift. Kept as a function so --selftest can point it
# at fixtures.
check_pair() {
  local settings_path="$1"
  local backstop_path="$2"
  local backstop_name="$3"

  python3 - "$settings_path" "$backstop_path" "$backstop_name" <<'PY'
import fnmatch, json, sys

settings_path, backstop_path, backstop_name = sys.argv[1], sys.argv[2], sys.argv[3]

# Toolchain commands the reviewer backstops MUST deny. These are the render
# and check toolchain commands reviewers should never run — the regression
# this check exists to catch.
TOOLCHAIN_CMDS = {
    "apt", "apt-get", "openscad", "openscad-nightly", "xvfb-run",
    "prusa-slicer", "printcheck", "stylelift", "sca2d",
    "python3", "python", "pip", "pip3", "pytest", "shellcheck",
    "actionlint", "montage", "convert", "gifsicle", "ffmpeg",
    "backlog-burn",
}

def load(path):
    with open(path) as fh:
        return json.load(fh)

def is_toolchain_allow(rule):
    """True if this allow rule matches a toolchain command."""
    if not (rule.startswith("Bash(") and rule.endswith(")")):
        return False
    cmd = rule[len("Bash("):-1].split(":", 1)[0].strip()
    # Match if cmd is a toolchain command or starts with one (e.g. "python3 -m")
    cmd_base = cmd.split()[0]
    return cmd_base in TOOLCHAIN_CMDS

allow = load(settings_path).get("permissions", {}).get("allow", [])
deny  = load(backstop_path).get("permissions", {}).get("deny", [])
deny_set = set(deny)

# Coverage: every toolchain Bash allow must be denied.
toolchain_allows = [r for r in allow if is_toolchain_allow(r)]
missing = [r for r in toolchain_allows if r not in deny_set]

ok = True
if missing:
    ok = False
    sys.stderr.write(
        f"these toolchain allows in {settings_path} are NOT denied in "
        f"{backstop_path} (the {backstop_name} would inherit them):\n")
    for r in missing:
        sys.stderr.write(f"    {r}\n")
    sys.stderr.write(
        f"  → add each to {backstop_path} permissions.deny.\n")

sys.exit(0 if ok else 1)
PY
}

selftest() {
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # GOOD: every toolchain Bash allow is denied.
  cat > "$tmp/good-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(openscad:*)","Bash(gh:*)","Bash(git:*)"]}}
EOF
  cat > "$tmp/good-reviewer.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(openscad:*)","Write","Edit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/good-reviewer.json" "reviewer" 2>/dev/null; then
    echo "ok    selftest: complete toolchain deny coverage passes"
  else
    echo "FAIL  selftest: a complete deny list was rejected"; return 1
  fi

  # BAD: openscad is left undenied → must fail.
  cat > "$tmp/bad-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(openscad:*)","Bash(gh:*)"]}}
EOF
  cat > "$tmp/bad-reviewer.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Write"]}}
EOF
  if check_pair "$tmp/bad-settings.json" "$tmp/bad-reviewer.json" "reviewer" 2>/dev/null; then
    echo "FAIL  selftest: an undenied toolchain allow was NOT caught"; return 1
  else
    echo "ok    selftest: an undenied toolchain allow fails the check"
  fi
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    reviewer-perms-check selftest passed"
  exit 0
fi

[[ -f "$SETTINGS" ]] || { echo "FAIL  reviewer-perms: $SETTINGS missing"; exit 1; }
[[ -f "$REVIEWER" ]] || { echo "FAIL  reviewer-perms: $REVIEWER missing"; exit 1; }
[[ -f "$COACH"   ]] || { echo "FAIL  reviewer-perms: $COACH missing"; exit 1; }

if check_pair "$SETTINGS" "$REVIEWER" "reviewer backstop"; then
  echo "ok    reviewer deny backstop covers every toolchain allow"
else
  echo "FAIL  reviewer permission drift: $REVIEWER does not neutralize every toolchain allow in $SETTINGS"
  exit 1
fi

if check_pair "$SETTINGS" "$COACH" "design-coach backstop"; then
  echo "ok    design-coach deny backstop covers every toolchain allow"
else
  echo "FAIL  reviewer permission drift: $COACH does not neutralize every toolchain allow in $SETTINGS"
  exit 1
fi
