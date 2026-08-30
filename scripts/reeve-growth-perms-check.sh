#!/usr/bin/env bash
# Reeve-growth permission-drift check: prove the scheduled PM-growth routine's
# OWN deny backstop (.claude/reeve-growth-settings.json) still neutralizes every
# dangerous tool allow it would otherwise inherit, denies every sibling
# routine's write surface AND the channel poster, and never denies its own
# queue-filing tool. Run by scripts/check.sh (and therefore /preflight and CI's
# scad-check jobs).
#
# THE INVERSION (why this is the mirror image of growth-perms-check.sh):
# the growth desk has two write surfaces on two agents. Lark, the POSTER
# (mcp__growth_twitter__post_tweet), may reach outside the repo; its backstop
# DENIES the queue server (the poster can never refill the queue it drains).
# Reeve-growth is the QUEUER (mcp__growth_queue__queue_growth_post): it files
# draft queue issues and must NEVER post, so its backstop is the mirror — it
# ALLOWS the queue tool and DENIES the poster. Every other sibling backstop
# denies BOTH growth servers (it owns neither); reeve-growth and growth-twitter
# are the two exceptions, each owning exactly one.
#
# Reeve-growth is oracle-shaped — NO shell wrapper at all: its reads are the
# file tools (Read/Grep/Glob) over the workflow-assembled .reeve-growth-context/
# plus the committed tree, and its ONE write is the MCP queue tool served by
# .claude/skills/growth-queue/queue_mcp.py. So the coverage rule has no wrapper
# exemption — EVERY Bash allow in settings.json must be denied — and on top of
# that the backstop must deny each sibling's write surface explicitly
# (chunk-helper.sh, label-helper.sh, scout-helper.sh, assessor-helper.sh,
# wright-helper.sh, each in both path spellings, plus the sibling MCP servers
# AND the channel poster mcp__growth_twitter), because those surfaces are not on
# settings.json's allow-list and coverage alone would never force them.
#
# The one thing it must NOT deny is its own queue-filing tool — exactly or by
# wildcard — or the scheduled routine fails closed with no other CI signal (it
# could never even file a draft).
#
# Extra denies are fine — this asserts coverage, not equality.
#
# Usage:
#   scripts/reeve-growth-perms-check.sh            # check the real files
#   scripts/reeve-growth-perms-check.sh --selftest # prove the check can pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/settings.json"
REEVE=".claude/reeve-growth-settings.json"

# Core comparison, pure function of two settings files. Prints a diagnosis and
# returns non-zero on any drift. Kept as a function so --selftest can point it
# at fixtures.
check_pair() {
  local settings_path="$1" reeve_path="$2"
  python3 - "$settings_path" "$reeve_path" <<'PY'
import fnmatch, json, sys

settings_path, reeve_path = sys.argv[1], sys.argv[2]

# The sibling routines' write surfaces plus the channel poster, which the
# queuer must deny VERBATIM even though most never appear on settings.json's
# allow-list (the coverage rule below would never force them, so they are
# asserted explicitly here). `mcp` entries accept the server-level deny or the
# tool-level one.
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
    # The channel poster — reeve-growth QUEUES, it never posts. This is the
    # inversion: growth-twitter's backstop denies the queue server here
    # instead.
    {"mcp__growth_twitter", "mcp__growth_twitter__post_tweet"},
    {"Write"},
    {"Edit"},
    {"NotebookEdit"},
]

# The queuer's ONE write surface. No deny rule may match it — exactly or by
# wildcard — or the scheduled routine fails closed (it could never even file a
# draft) with no other CI signal.
QUEUE_TOOL = "mcp__growth_queue__queue_growth_post"
QUEUE_SERVER = "mcp__growth_queue"

def load(path):
    with open(path) as fh:
        return json.load(fh)

def deny_blocks_queue(rule):
    # An exact or wildcard deny naming the queue tool or its server blocks the
    # routine's only output. Bash(...) denies never do.
    if rule.startswith("Bash("):
        return False
    return (rule in (QUEUE_TOOL, QUEUE_SERVER)
            or fnmatch.fnmatch(QUEUE_TOOL, rule)
            or fnmatch.fnmatch(QUEUE_SERVER, rule))

allow = load(settings_path).get("permissions", {}).get("allow", [])
deny  = load(reeve_path).get("permissions", {}).get("deny", [])
deny_set = set(deny)

# Coverage: every Bash allow must be denied verbatim — the routine has no
# wrapper, so there is no exemption.
missing = [r for r in allow if r.startswith("Bash(") and r not in deny_set]
# The sibling surfaces + the poster + file-write tools, asserted explicitly.
missing_required = [sorted(alts) for alts in REQUIRED_DENIES
                    if not (alts & deny_set)]
# Safety: no deny rule may match the queue tool, wildcards included.
queue_denied = [d for d in deny if deny_blocks_queue(d)]

ok = True
if queue_denied:
    ok = False
    sys.stderr.write(
        "a deny rule would block the routine's queue-filing tool — the "
        "unattended routine would fail closed, unable even to file a draft:\n")
    for r in queue_denied:
        sys.stderr.write(f"    {r}\n")
if missing:
    ok = False
    sys.stderr.write(
        f"these Bash allows in {settings_path} are NOT denied in "
        f"{reeve_path} (the routine inherits them via settingSources=project):\n")
    for r in missing:
        sys.stderr.write(f"    {r}\n")
    sys.stderr.write(
        "  → add each to .claude/reeve-growth-settings.json permissions.deny.\n")
if missing_required:
    ok = False
    sys.stderr.write(
        f"these required denies (sibling write surfaces / the channel poster / "
        f"file-write tools) are missing from {reeve_path}:\n")
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
  # surface, the channel poster, and the file-write tools, plus the one Bash
  # allow the good settings fixture carries. Note it does NOT deny the queue
  # server — that is the routine's own surface.
  cat > "$tmp/good-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  cat > "$tmp/good-reeve.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","mcp__reeve_signoff","mcp__growth_twitter","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/good-reeve.json" 2>/dev/null; then
    echo "ok    selftest: complete deny coverage passes"
  else
    echo "FAIL  selftest: a complete deny list was rejected"; return 1
  fi

  # BAD 1: a dangerous Bash allow is left undenied → must fail. (There is no
  # wrapper exemption — ANY undenied Bash allow is drift.)
  cat > "$tmp/bad1-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(git:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  if check_pair "$tmp/bad1-settings.json" "$tmp/good-reeve.json" 2>/dev/null; then
    echo "FAIL  selftest: an undenied Bash allow was NOT caught"; return 1
  else
    echo "ok    selftest: an undenied Bash allow fails the check"
  fi

  # BAD 2: the channel poster's deny is dropped — the queuer could reach the
  # channel it feeds, the one thing it must never do. It is on no allow-list,
  # which is exactly why the required-denies list exists.
  cat > "$tmp/bad2-reeve.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","mcp__reeve_signoff","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad2-reeve.json" 2>/dev/null; then
    echo "FAIL  selftest: a missing poster deny was NOT caught"; return 1
  else
    echo "ok    selftest: a missing channel-poster deny fails the check"
  fi

  # BAD 3: the routine's own queue tool is denied → must fail (fails closed).
  cat > "$tmp/bad3-reeve.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","mcp__reeve_signoff","mcp__growth_twitter","Write","Edit","NotebookEdit","mcp__growth_queue__queue_growth_post"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad3-reeve.json" 2>/dev/null; then
    echo "FAIL  selftest: a denied queue tool was NOT caught"; return 1
  else
    echo "ok    selftest: denying the queue tool fails the check"
  fi

  # BAD 4: a WILDCARD deny that covers the queue tool still blocks it.
  cat > "$tmp/bad4-reeve.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/wright/wright-helper.sh:*)","Bash(./.claude/skills/wright/wright-helper.sh:*)","mcp__scout","mcp__assessor","mcp__oracle","mcp__wright","mcp__reeve_signoff","mcp__growth_twitter","Write","Edit","NotebookEdit","mcp__growth_*"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/bad4-reeve.json" 2>/dev/null; then
    echo "FAIL  selftest: a wildcard deny blocking the queue tool was NOT caught"; return 1
  else
    echo "ok    selftest: a wildcard deny blocking the queue tool fails the check"
  fi
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    reeve-growth-perms-check selftest passed"
  exit 0
fi

[[ -f "$SETTINGS" ]] || { echo "FAIL  reeve-growth-perms: $SETTINGS missing"; exit 1; }
[[ -f "$REEVE"    ]] || { echo "FAIL  reeve-growth-perms: $REEVE missing"; exit 1; }

if check_pair "$SETTINGS" "$REEVE"; then
  echo "ok    reeve-growth deny backstop covers every Bash allow + all sibling write surfaces + the channel poster, and leaves the queue tool usable"
else
  echo "FAIL  reeve-growth permission drift: $REEVE does not neutralize every dangerous allow in $SETTINGS"
  exit 1
fi
