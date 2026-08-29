#!/usr/bin/env bash
# Oracle permission-drift check: prove the Oracle reviewer's OWN deny backstop
# (.claude/oracle-settings.json) still neutralizes every dangerous tool allow it
# would otherwise inherit, denies every sibling routine's write surface, AND
# never denies the Oracle's one posting tool. Run by scripts/check.sh (and
# therefore by /preflight and CI's scad-check jobs).
#
# WHY THIS EXISTS, and why it is SEPARATE from the chunker/labeler/scout checks:
# .github/workflows/oracle.yml runs claude-code-action, which starts the SDK
# with settingSources:[user,project,local] — so it loads this repo's
# .claude/settings.json permissions.allow. That file carries dev entries the
# interactive agents need, including `Bash(xvfb-run:*)` (arbitrary command
# execution) and `Bash(git:*)`/`Bash(gh:*)`. Allow rules merge ADDITIVELY
# across sources, so the Oracle's narrow --allowedTools does NOT remove them.
# The Oracle closes this with its own backstop (.claude/oracle-settings.json,
# passed via --settings): deny beats allow from every source.
#
# The Oracle's shape differs from all three siblings: it has NO shell wrapper
# at all. Its reads are the file tools over workflow-assembled context, and its
# ONE write is the MCP posting tool (mcp__oracle__post_oracle_review, served by
# .claude/skills/oracle-review/oracle_mcp.py). So the coverage rule here has no
# wrapper exemption — EVERY Bash allow in settings.json must be denied — and on
# top of that the backstop must deny each sibling's write surface explicitly
# (chunk-helper.sh, label-helper.sh, scout-helper.sh, assessor-helper.sh and
# the agent forge's wright-helper.sh, each in both path spellings, plus the
# sibling MCP servers — the scout's, the assessor's, and the forge's two,
# including the sign-off server that can APPLY the arming label), because most
# of those surfaces are not on settings.json's allow-list and would otherwise
# go unasserted. The one thing it must NOT deny is its own posting tool, or
# the unattended Oracle fails closed with no other CI signal.
#
# That backstop is only as good as its coverage: add a Bash allow to
# settings.json tomorrow and, unless it is also denied here, the Oracle
# silently inherits it — an invisible regression, because the thing being
# protected is the ABSENCE of a capability. This check makes that regression
# fail loudly. Extra denies are fine — this asserts coverage, not equality.
#
# Usage:
#   scripts/oracle-perms-check.sh            # check the real files
#   scripts/oracle-perms-check.sh --selftest # prove the check can pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/settings.json"
ORACLE=".claude/oracle-settings.json"

# Core comparison, pure function of two settings files. Prints a diagnosis and
# returns non-zero on any drift. Kept as a function so --selftest can point it
# at fixtures.
check_pair() {
  local settings_path="$1" oracle_path="$2"
  python3 - "$settings_path" "$oracle_path" <<'PY'
import fnmatch, json, sys

settings_path, oracle_path = sys.argv[1], sys.argv[2]

# The sibling routines' write surfaces, which the Oracle must deny VERBATIM
# even though not all of them appear on settings.json's allow-list (the
# labeler's and scout's wrappers do not — the coverage rule below would never
# force them, so they are asserted explicitly here). `mcp` entries accept the
# server-level deny or the tool-level one.
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
    {"mcp__wright", "mcp__wright__file_agent_brief"},
    {"mcp__reeve_signoff", "mcp__reeve_signoff__post_reeve_signoff"},
    {"Write"},
    {"Edit"},
    {"NotebookEdit"},
]

# The Oracle's ONE write surface. No deny rule may match it — exactly or by
# wildcard — or the scheduled Oracle fails closed (it could never post) with no
# other CI signal.
POSTING_TOOL = "mcp__oracle__post_oracle_review"
POSTING_SERVER = "mcp__oracle"

def load(path):
    with open(path) as fh:
        return json.load(fh)

def deny_blocks_posting(rule):
    # An exact or wildcard deny naming the posting tool or its server blocks
    # the Oracle's only output channel. Bash(...) denies never do.
    if rule.startswith("Bash("):
        return False
    return (rule in (POSTING_TOOL, POSTING_SERVER)
            or fnmatch.fnmatch(POSTING_TOOL, rule)
            or fnmatch.fnmatch(POSTING_SERVER, rule))

allow = load(settings_path).get("permissions", {}).get("allow", [])
deny  = load(oracle_path).get("permissions", {}).get("deny", [])
deny_set = set(deny)

# Coverage: every Bash allow must be denied verbatim — the Oracle has no
# wrapper, so there is no exemption.
missing = [r for r in allow if r.startswith("Bash(") and r not in deny_set]
# The sibling surfaces + file-write tools, asserted explicitly.
missing_required = [sorted(alts) for alts in REQUIRED_DENIES
                    if not (alts & deny_set)]
# Safety: no deny rule may match the posting tool, wildcards included.
posting_denied = [d for d in deny if deny_blocks_posting(d)]

ok = True
if posting_denied:
    ok = False
    sys.stderr.write(
        "a deny rule would block the Oracle's posting tool — the unattended "
        "Oracle would fail closed, unable to post its review:\n")
    for r in posting_denied:
        sys.stderr.write(f"    {r}\n")
if missing:
    ok = False
    sys.stderr.write(
        f"these Bash allows in {settings_path} are NOT denied in "
        f"{oracle_path} (the Oracle inherits them via settingSources=project):\n")
    for r in missing:
        sys.stderr.write(f"    {r}\n")
    sys.stderr.write(
        "  → add each to .claude/oracle-settings.json permissions.deny.\n")
if missing_required:
    ok = False
    sys.stderr.write(
        f"these required denies (sibling write surfaces / file-write tools) "
        f"are missing from {oracle_path}:\n")
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
  cat > "$tmp/good-oracle.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__wright","mcp__reeve_signoff","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/good-oracle.json" 2>/dev/null; then
    echo "ok    selftest: complete deny coverage passes"
  else
    echo "FAIL  selftest: a complete deny list was rejected"; return 1
  fi

  # BAD 1: a dangerous Bash allow is left undenied → must fail. (There is no
  # wrapper exemption — ANY undenied Bash allow is drift.)
  cat > "$tmp/bad1-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(git:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  if check_pair "$tmp/bad1-settings.json" "$tmp/good-oracle.json" 2>/dev/null; then
    echo "FAIL  selftest: an undenied Bash allow was NOT caught"; return 1
  else
    echo "ok    selftest: an undenied Bash allow fails the check"
  fi

  # BAD 2: a sibling write surface (the scout's MCP tool) is not denied → must
  # fail, even though it never appears on settings.json's allow-list — that is
  # exactly why the required-denies list exists.
  cat > "$tmp/bad2-oracle.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__assessor","mcp__wright","mcp__reeve_signoff","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad2-oracle.json" 2>/dev/null; then
    echo "FAIL  selftest: a missing scout-MCP deny was NOT caught"; return 1
  else
    echo "ok    selftest: a missing sibling-surface deny fails the check"
  fi

  # BAD 3: the Oracle's own posting tool is denied → must fail (fails closed).
  cat > "$tmp/bad3-oracle.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__wright","mcp__reeve_signoff","Write","Edit","NotebookEdit","mcp__oracle__post_oracle_review"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad3-oracle.json" 2>/dev/null; then
    echo "FAIL  selftest: a denied posting tool was NOT caught"; return 1
  else
    echo "ok    selftest: denying the posting tool fails the check"
  fi

  # BAD 4: a WILDCARD deny that covers the posting tool still blocks it.
  cat > "$tmp/bad4-oracle.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__wright","mcp__reeve_signoff","Write","Edit","NotebookEdit","mcp__*"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad4-oracle.json" 2>/dev/null; then
    echo "FAIL  selftest: a wildcard deny blocking the posting tool was NOT caught"; return 1
  else
    echo "ok    selftest: a wildcard deny blocking the posting tool fails the check"
  fi
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    oracle-perms-check selftest passed"
  exit 0
fi

[[ -f "$SETTINGS" ]] || { echo "FAIL  oracle-perms: $SETTINGS missing"; exit 1; }
[[ -f "$ORACLE"   ]] || { echo "FAIL  oracle-perms: $ORACLE missing"; exit 1; }

if check_pair "$SETTINGS" "$ORACLE"; then
  echo "ok    oracle deny backstop covers every Bash allow + all sibling write surfaces, and leaves the posting tool usable"
else
  echo "FAIL  oracle permission drift: $ORACLE does not neutralize every dangerous allow in $SETTINGS"
  exit 1
fi
