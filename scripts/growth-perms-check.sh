#!/usr/bin/env bash
# Growth-agent permission-drift check: prove the Twitter/X growth agent's OWN
# deny backstop (.claude/growth-twitter-settings.json) still neutralizes every
# dangerous tool allow it would otherwise inherit, denies every sibling
# routine's write surface AND the queue-filing server, and never denies the
# one posting tool. Run by scripts/check.sh (and therefore by /preflight and
# CI's scad-check jobs).
#
# WHY THIS EXISTS, and why the growth agent gets the STRICTEST reading:
# .github/workflows/growth-twitter.yml runs claude-code-action, which starts
# the SDK with settingSources:[user,project,local] — so it loads this repo's
# .claude/settings.json permissions.allow. Allow rules merge ADDITIVELY, so
# the run's narrow --allowedTools does NOT remove them; the backstop passed
# via --settings is the actual boundary (deny beats allow from every source).
# Lark is oracle-shaped — NO shell wrapper at all: its reads are the file
# tools over workflow-assembled .growth-context/, and its ONE write is the
# MCP posting tool (mcp__growth_twitter__post_tweet, served by
# .claude/skills/growth-twitter/growth_mcp.py). So the coverage rule has no
# wrapper exemption — EVERY Bash allow in settings.json must be denied — and
# on top of that the backstop must deny each sibling's write surface
# explicitly (chunk-helper.sh, label-helper.sh, scout-helper.sh,
# assessor-helper.sh, wright-helper.sh, each in both path spellings, plus the
# sibling MCP servers AND the growth desk's own queue-filing server
# mcp__growth_queue — the poster must never be able to refill the very queue
# it drains), because those surfaces are not on settings.json's allow-list
# and coverage alone would never force them. The stakes are higher than any
# sibling's: this is the one write surface that can reach OUTSIDE the repo
# (a live post on a public channel), so an inherited stray capability is not
# just noise a human deletes.
#
# The one thing it must NOT deny is its own posting tool — exactly or by
# wildcard — or the scheduled growth agent fails closed with no other CI
# signal (its dry-run comments just silently stop).
#
# That backstop is only as good as its coverage: add a Bash allow to
# settings.json tomorrow and, unless it is also denied here, the growth agent
# silently inherits it — an invisible regression, because the thing being
# protected is the ABSENCE of a capability. This check makes that regression
# fail loudly. Extra denies are fine — this asserts coverage, not equality.
#
# Usage:
#   scripts/growth-perms-check.sh            # check the real files
#   scripts/growth-perms-check.sh --selftest # prove the check can pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/settings.json"
GROWTH=".claude/growth-twitter-settings.json"

# Core comparison, pure function of two settings files. Prints a diagnosis and
# returns non-zero on any drift. Kept as a function so --selftest can point it
# at fixtures.
check_pair() {
  local settings_path="$1" growth_path="$2"
  python3 - "$settings_path" "$growth_path" <<'PY'
import fnmatch, json, sys

settings_path, growth_path = sys.argv[1], sys.argv[2]

# The sibling routines' write surfaces plus the growth desk's own queue-filing
# server, which the growth agent must deny VERBATIM even though most never
# appear on settings.json's allow-list (the coverage rule below would never
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
    {"mcp__oracle", "mcp__oracle__post_oracle_review"},
    {"mcp__wright", "mcp__wright__file_agent_brief"},
    {"mcp__reeve_signoff", "mcp__reeve_signoff__post_reeve_signoff"},
    {"mcp__growth_queue", "mcp__growth_queue__queue_growth_post"},
    {"Write"},
    {"Edit"},
    {"NotebookEdit"},
]

# The growth agent's ONE write surface. No deny rule may match it — exactly
# or by wildcard — or the scheduled agent fails closed (it could never even
# dry-run) with no other CI signal.
POSTING_TOOL = "mcp__growth_twitter__post_tweet"
POSTING_SERVER = "mcp__growth_twitter"

def load(path):
    with open(path) as fh:
        return json.load(fh)

def deny_blocks_posting(rule):
    # An exact or wildcard deny naming the posting tool or its server blocks
    # the growth agent's only output channel. Bash(...) denies never do.
    if rule.startswith("Bash("):
        return False
    return (rule in (POSTING_TOOL, POSTING_SERVER)
            or fnmatch.fnmatch(POSTING_TOOL, rule)
            or fnmatch.fnmatch(POSTING_SERVER, rule))

allow = load(settings_path).get("permissions", {}).get("allow", [])
deny  = load(growth_path).get("permissions", {}).get("deny", [])
deny_set = set(deny)

# Coverage: every Bash allow must be denied verbatim — the growth agent has
# no wrapper, so there is no exemption.
missing = [r for r in allow if r.startswith("Bash(") and r not in deny_set]
# The sibling surfaces + queue server + file-write tools, asserted explicitly.
missing_required = [sorted(alts) for alts in REQUIRED_DENIES
                    if not (alts & deny_set)]
# Safety: no deny rule may match the posting tool, wildcards included.
posting_denied = [d for d in deny if deny_blocks_posting(d)]

ok = True
if posting_denied:
    ok = False
    sys.stderr.write(
        "a deny rule would block the growth agent's posting tool — the "
        "unattended agent would fail closed, unable even to dry-run:\n")
    for r in posting_denied:
        sys.stderr.write(f"    {r}\n")
if missing:
    ok = False
    sys.stderr.write(
        f"these Bash allows in {settings_path} are NOT denied in "
        f"{growth_path} (the growth agent inherits them via settingSources=project):\n")
    for r in missing:
        sys.stderr.write(f"    {r}\n")
    sys.stderr.write(
        "  → add each to .claude/growth-twitter-settings.json permissions.deny.\n")
if missing_required:
    ok = False
    sys.stderr.write(
        f"these required denies (sibling write surfaces / the queue-filing "
        f"server / file-write tools) are missing from {growth_path}:\n")
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
  # surface, the queue server, and the file-write tools, plus the one Bash
  # allow the good settings fixture carries.
  cat > "$tmp/good-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  cat > "$tmp/good-growth.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","mcp__reeve_signoff","mcp__growth_queue","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/good-growth.json" 2>/dev/null; then
    echo "ok    selftest: complete deny coverage passes"
  else
    echo "FAIL  selftest: a complete deny list was rejected"; return 1
  fi

  # BAD 1: a dangerous Bash allow is left undenied → must fail. (There is no
  # wrapper exemption — ANY undenied Bash allow is drift.)
  cat > "$tmp/bad1-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(git:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  if check_pair "$tmp/bad1-settings.json" "$tmp/good-growth.json" 2>/dev/null; then
    echo "FAIL  selftest: an undenied Bash allow was NOT caught"; return 1
  else
    echo "ok    selftest: an undenied Bash allow fails the check"
  fi

  # BAD 2: the queue-filing server's deny is dropped — the poster could
  # refill the very queue it drains, closing the loop no human is in. It is
  # on no allow-list, which is exactly why the required-denies list exists.
  cat > "$tmp/bad2-growth.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","mcp__reeve_signoff","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad2-growth.json" 2>/dev/null; then
    echo "FAIL  selftest: a missing queue-server deny was NOT caught"; return 1
  else
    echo "ok    selftest: a missing queue-server deny fails the check"
  fi

  # BAD 3: the growth agent's own posting tool is denied → must fail (fails
  # closed).
  cat > "$tmp/bad3-growth.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","mcp__reeve_signoff","mcp__growth_queue","Write","Edit","NotebookEdit","mcp__growth_twitter__post_tweet"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad3-growth.json" 2>/dev/null; then
    echo "FAIL  selftest: a denied posting tool was NOT caught"; return 1
  else
    echo "ok    selftest: denying the posting tool fails the check"
  fi

  # BAD 4: a WILDCARD deny that covers the posting tool still blocks it.
  cat > "$tmp/bad4-growth.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","mcp__reeve_signoff","mcp__growth_queue","Write","Edit","NotebookEdit","mcp__growth_*"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad4-growth.json" 2>/dev/null; then
    echo "FAIL  selftest: a wildcard deny blocking the posting tool was NOT caught"; return 1
  else
    echo "ok    selftest: a wildcard deny blocking the posting tool fails the check"
  fi
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    growth-perms-check selftest passed"
  exit 0
fi

[[ -f "$SETTINGS" ]] || { echo "FAIL  growth-perms: $SETTINGS missing"; exit 1; }
[[ -f "$GROWTH"   ]] || { echo "FAIL  growth-perms: $GROWTH missing"; exit 1; }

if check_pair "$SETTINGS" "$GROWTH"; then
  echo "ok    growth deny backstop covers every Bash allow + all sibling write surfaces + the queue server, and leaves the posting tool usable"
else
  echo "FAIL  growth permission drift: $GROWTH does not neutralize every dangerous allow in $SETTINGS"
  exit 1
fi
