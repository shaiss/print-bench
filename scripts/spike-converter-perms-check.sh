#!/usr/bin/env bash
# Spike-converter permission-drift check: prove the scheduled spike converter's
# OWN deny backstop (.claude/spike-converter-settings.json) still neutralizes
# every dangerous tool allow it would otherwise inherit, never denies the
# converter's one read wrapper or one reused write tool, and that the REUSED
# scout filing surface it depends on has not rotted away. Run by
# scripts/check.sh (and therefore by /preflight and CI's scad-check jobs).
#
# WHY THIS EXISTS, and why it is SEPARATE from chunker-/labeler-/scout-/
# adoption-assessor-perms-check: .github/workflows/spike-converter.yml runs
# claude-code-action, which starts the SDK with settingSources:[user,project,
# local] — so it loads this repo's .claude/settings.json permissions.allow.
# That file carries dev entries the interactive / backlog-burn / design-run
# agents need, including `Bash(xvfb-run:*)` (arbitrary command execution), the
# chunker's chunk-helper.sh (which can create issues) and the labeler's
# label-helper.sh (which can APPLY routing labels, `autonomy-ok` included).
# Allow rules merge ADDITIVELY across sources, so the converter's narrow
# --allowedTools does NOT remove them. The converter closes this with its own
# backstop (.claude/spike-converter-settings.json, passed via --settings):
# deny beats allow from every source.
#
# The converter needs a backstop distinct from EVERY sibling, and uniquely it
# must deny the SCOUT's own wrapper: scout-helper.sh carries a file-brief verb
# (#439's rule — the converter files via the MCP tool only, so the shell
# filing path must not be reachable), while mcp__scout__file_design_brief
# (that same tool) is the converter's ONE approved write and must NEVER be
# denied. So the deny set is: every dangerous settings.json allow, plus
# chunk-helper, label-helper, assessor-helper AND scout-helper — but not the
# scout MCP server, the mirror image of every other sibling's backstop (they
# deny mcp__scout; this one depends on it).
#
# THE REUSE COUPLING (the part no sibling needs): the converter has no filing
# server of its own — it reuses the scout's, wired into the workflow as
# --mcp-config .claude/skills/product-scout/scout-mcp.json. If the scout ever
# renames or moves that server, the converter's only write silently becomes a
# denied tool and the armed routine fails closed with no other CI signal — or
# worse, the skill improvises a second filing path. So this check also pins:
#   * .claude/skills/product-scout/scout-mcp.json exists and still declares a
#     server named "scout" (the name the workflow's allow-list and the
#     mcp__scout__file_design_brief tool id are keyed on);
#   * the server file it launches (.claude/skills/product-scout/scout_mcp.py)
#     still exists;
#   * the backstop does not deny mcp__scout__file_design_brief, nor the
#     mcp__scout server prefix that would block every tool on that server.
#
# That backstop is only as good as its coverage. Add a Bash allow to
# settings.json tomorrow and, unless it is also denied here, the converter
# silently inherits it again — an invisible regression, because the thing
# being protected is the ABSENCE of a capability. This check makes that
# regression fail loudly: every non-wrapper Bash allow in settings.json must
# be denied in spike-converter-settings.json, the wrapper
# (converter-helper.sh) and the filing tool must NOT be denied (or the
# scheduled routine fails closed), and the four sibling write surfaces must
# stay denied whatever settings.json allows today. Extra denies are fine —
# this asserts coverage, not equality.
#
# Usage:
#   scripts/spike-converter-perms-check.sh            # check the real files
#   scripts/spike-converter-perms-check.sh --selftest # prove the check can
#                                                    # pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/settings.json"
CONVERTER=".claude/spike-converter-settings.json"
SCOUT_MCP_JSON=".claude/skills/product-scout/scout-mcp.json"
SCOUT_MCP_PY=".claude/skills/product-scout/scout_mcp.py"

# Core comparison, pure function of the files. Prints a diagnosis and returns
# non-zero on any drift. Kept as a function so --selftest can point it at
# fixtures.
check_pair() {
  local settings_path="$1" converter_path="$2" mcp_json_path="$3" mcp_py_path="$4"
  python3 - "$settings_path" "$converter_path" "$mcp_json_path" "$mcp_py_path" <<'PY'
import fnmatch, json, os, sys

settings_path, converter_path = sys.argv[1], sys.argv[2]
mcp_json_path, mcp_py_path = sys.argv[3], sys.argv[4]

# The converter's ONE approved shell surface, identified by its EXACT allow
# rule (both the bare and ./-prefixed forms) — never by a loose substring. A
# same-basename rule on a different path is NOT the wrapper and must still be
# denied, so it must not be exempted here.
WRAPPER_RULES = {
    "Bash(.claude/skills/spike-converter/converter-helper.sh:*)",
    "Bash(./.claude/skills/spike-converter/converter-helper.sh:*)",
}
# The command paths a deny rule must never match, or the converter loses its
# only read surface. Matched with wildcard semantics so a *broad* deny pattern
# can't slip past (e.g. Bash(.claude/skills/spike-converter/*:*) or
# Bash(*converter-helper.sh:*)).
WRAPPER_CMDS = [
    ".claude/skills/spike-converter/converter-helper.sh",
    "./.claude/skills/spike-converter/converter-helper.sh",
]

# The converter's ONE approved write: the scout's REUSED filing tool, plus the
# server prefix a deny of which would block every tool on that server.
FILING_TOOL = "mcp__scout__file_design_brief"
FILING_SERVER = "mcp__scout"

# Required denies the backstop must ALWAYS carry, whatever settings.json
# allows today. The coverage rule below only forces denying what is CURRENTLY
# on settings.json's allow-list — so it catches chunk-helper.sh (which is on
# it) but NOT label-helper.sh / assessor-helper.sh / scout-helper.sh (which
# are not), and would let their deny, or the Write/Edit/NotebookEdit denies,
# be dropped silently. The issue #440 invariant is that ALL FOUR sibling write
# surfaces (both path spellings) and the file-mutating tools stay denied
# regardless — so require them explicitly.
REQUIRED_DENIES = {
    "Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)",
    "Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)",
    "Bash(.claude/skills/label-issues/label-helper.sh:*)",
    "Bash(./.claude/skills/label-issues/label-helper.sh:*)",
    "Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)",
    "Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)",
    "Bash(.claude/skills/product-scout/scout-helper.sh:*)",
    "Bash(./.claude/skills/product-scout/scout-helper.sh:*)",
    "Write", "Edit", "NotebookEdit",
}

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

problems = []

# --- the reuse coupling, FIRST: without it every other property guards a
# routine whose only write is already dead.
if not os.path.isfile(mcp_json_path):
    problems.append(
        f"{mcp_json_path} is gone — the converter's workflow wires it as "
        f"--mcp-config and its only write (the {FILING_TOOL} tool) is served "
        f"from there. A moved/renamed scout filing surface must travel with a "
        f"spike-converter.yml + allow-list edit, not silently strand it.")
else:
    try:
        servers = load(mcp_json_path).get("mcpServers", {})
    except (ValueError, OSError) as exc:
        servers, problems = None, problems + [f"{mcp_json_path} does not parse: {exc}"]
    if servers is not None and "scout" not in servers:
        problems.append(
            f"{mcp_json_path} no longer declares a server named 'scout' — the "
            f"workflow's allow-list names {FILING_TOOL}, whose id is keyed on "
            f"that server name; a rename strands the converter's only write.")
    if servers is not None and "scout" in servers:
        launched = " ".join(servers["scout"].get("args", []))
        if os.path.basename(mcp_py_path) not in launched:
            problems.append(
                f"{mcp_json_path}'s 'scout' server no longer launches "
                f"{os.path.basename(mcp_py_path)} — the server file this check "
                f"pins below.")
if not os.path.isfile(mcp_py_path):
    problems.append(
        f"{mcp_py_path} is gone — the reused scout filing server itself. The "
        f"converter has no filing path without it.")

allow = load(settings_path).get("permissions", {}).get("allow", [])
deny  = load(converter_path).get("permissions", {}).get("deny", [])
deny_set = set(deny)

# --- the write surface must stay open (this backstop's mirror-image rule:
# every sibling denies mcp__scout; this one must NOT).
for rule in (FILING_TOOL, FILING_SERVER):
    if rule in deny_set:
        problems.append(
            f"the backstop denies {rule!r} — that is the converter's ONLY "
            f"write (#439: filing goes through the reused scout MCP tool), so "
            f"the armed routine would fail closed with no other CI signal.")

# --- the read wrapper must stay open.
wrapper_denied = [d for d in deny if deny_blocks_wrapper(d)]
for rule in wrapper_denied:
    problems.append(
        f"a deny rule would block the converter wrapper — the scheduled "
        f"routine would fail closed: {rule}")

# --- coverage: every non-wrapper Bash allow must be denied verbatim.
missing = [r for r in allow
           if r.startswith("Bash(") and r not in WRAPPER_RULES and r not in deny_set]
for r in missing:
    problems.append(
        f"Bash allow in {settings_path} is NOT denied in {converter_path} "
        f"(the converter inherits it via settingSources=project): {r}")

# --- the sibling write surfaces, explicitly (coverage alone would not force
# these — see REQUIRED_DENIES above).
for r in sorted(REQUIRED_DENIES - deny_set):
    problems.append(
        f"the backstop no longer denies {r} — issue #440 requires all four "
        f"sibling write surfaces (chunk / label / assessor / scout helpers) "
        f"and the file-mutating tools to stay denied whatever settings.json "
        f"allows today.")

if problems:
    sys.stderr.write("spike-converter permission drift:\n")
    for p in problems:
        sys.stderr.write(f"    {p}\n")
    sys.exit(1)
PY
}

selftest() {
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # A stand-in for the scout's filing surface, so the reuse-coupling cases
  # below test THIS check rather than the real tree.
  mkdir -p "$tmp/.claude/skills/product-scout"
  cat > "$tmp/.claude/skills/product-scout/scout-mcp.json" <<'EOF'
{"mcpServers": {"scout": {"command": "python3", "args": [".claude/skills/product-scout/scout_mcp.py"]}}}
EOF
  echo '# server' > "$tmp/.claude/skills/product-scout/scout_mcp.py"

  # GOOD: every non-wrapper Bash allow (chunk-helper AND label-helper
  # included) is denied, all four sibling surfaces are denied, the wrapper and
  # the filing tool are not, and the reused scout surface is intact.
  cat > "$tmp/good-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)"]}}
EOF
  cat > "$tmp/good-converter.json" <<'EOF'
{"permissions":{"deny":["Bash(xvfb-run:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(.claude/skills/product-scout/scout-helper.sh:*)","Bash(./.claude/skills/product-scout/scout-helper.sh:*)","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/good-converter.json" \
      "$tmp/.claude/skills/product-scout/scout-mcp.json" \
      "$tmp/.claude/skills/product-scout/scout_mcp.py" 2>/dev/null; then
    echo "ok    selftest: complete deny coverage + intact reuse passes"
  else
    echo "FAIL  selftest: a complete backstop was rejected"; return 1
  fi

  # BAD 1: an allow (chunk-helper) left undenied → must fail.
  cat > "$tmp/bad1-settings.json" <<'EOF'
{"permissions":{"allow":["Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  cat > "$tmp/bad1-converter.json" <<'EOF'
{"permissions":{"deny":["Write"]}}
EOF
  if check_pair "$tmp/bad1-settings.json" "$tmp/bad1-converter.json" \
      "$tmp/.claude/skills/product-scout/scout-mcp.json" \
      "$tmp/.claude/skills/product-scout/scout_mcp.py" 2>/dev/null; then
    echo "FAIL  selftest: an undenied chunk-helper allow was NOT caught"; return 1
  else
    echo "ok    selftest: an undenied allow fails the check"
  fi

  # BAD 2: the converter wrapper itself is denied → must fail (fails closed).
  cat > "$tmp/bad2-settings.json" <<'EOF'
{"permissions":{"allow":[]}}
EOF
  cat > "$tmp/bad2-converter.json" <<'EOF'
{"permissions":{"deny":["Bash(.claude/skills/spike-converter/converter-helper.sh:*)"]}}
EOF
  if check_pair "$tmp/bad2-settings.json" "$tmp/bad2-converter.json" \
      "$tmp/.claude/skills/product-scout/scout-mcp.json" \
      "$tmp/.claude/skills/product-scout/scout_mcp.py" 2>/dev/null; then
    echo "FAIL  selftest: a denied wrapper was NOT caught"; return 1
  else
    echo "ok    selftest: denying the wrapper fails the check"
  fi

  # BAD 2b: a BROAD deny pattern that matches the wrapper path still blocks it.
  cat > "$tmp/bad2b-converter.json" <<'EOF'
{"permissions":{"deny":["Bash(.claude/skills/spike-converter/*:*)"]}}
EOF
  if check_pair "$tmp/bad2-settings.json" "$tmp/bad2b-converter.json" \
      "$tmp/.claude/skills/product-scout/scout-mcp.json" \
      "$tmp/.claude/skills/product-scout/scout_mcp.py" 2>/dev/null; then
    echo "FAIL  selftest: a wildcard deny blocking the wrapper was NOT caught"; return 1
  else
    echo "ok    selftest: a wildcard deny blocking the wrapper fails the check"
  fi

  # BAD 3: a REQUIRED sibling deny (the scout's wrapper — the converter's
  # distinguishing requirement) is dropped → must fail even though coverage of
  # settings.json allows is complete (scout-helper is not on that allow-list).
  cat > "$tmp/bad3-settings.json" <<'EOF'
{"permissions":{"allow":[]}}
EOF
  cat > "$tmp/bad3-converter.json" <<'EOF'
{"permissions":{"deny":["Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(.claude/skills/label-issues/label-helper.sh:*)","Bash(./.claude/skills/label-issues/label-helper.sh:*)","Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)","Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*)","Write","Edit","NotebookEdit"]}}
EOF
  if check_pair "$tmp/bad3-settings.json" "$tmp/bad3-converter.json" \
      "$tmp/.claude/skills/product-scout/scout-mcp.json" \
      "$tmp/.claude/skills/product-scout/scout_mcp.py" 2>/dev/null; then
    echo "FAIL  selftest: a dropped scout-helper deny was NOT caught"; return 1
  else
    echo "ok    selftest: dropping a sibling deny fails the check"
  fi

  # BAD 4: the filing tool itself is denied → must fail. This backstop's
  # mirror-image rule — every sibling denies mcp__scout, this one depends on it.
  cat > "$tmp/bad4-converter.json" <<'EOF'
{"permissions":{"deny":["mcp__scout__file_design_brief"]}}
EOF
  if check_pair "$tmp/bad2-settings.json" "$tmp/bad4-converter.json" \
      "$tmp/.claude/skills/product-scout/scout-mcp.json" \
      "$tmp/.claude/skills/product-scout/scout_mcp.py" 2>/dev/null; then
    echo "FAIL  selftest: a denied filing tool was NOT caught"; return 1
  else
    echo "ok    selftest: denying the reused filing tool fails the check"
  fi

  # BAD 4b: same, via the SERVER prefix (blocks every tool on the server).
  cat > "$tmp/bad4b-converter.json" <<'EOF'
{"permissions":{"deny":["mcp__scout"]}}
EOF
  if check_pair "$tmp/bad2-settings.json" "$tmp/bad4b-converter.json" \
      "$tmp/.claude/skills/product-scout/scout-mcp.json" \
      "$tmp/.claude/skills/product-scout/scout_mcp.py" 2>/dev/null; then
    echo "FAIL  selftest: a server-prefix deny blocking the filing tool was NOT caught"; return 1
  else
    echo "ok    selftest: a server-prefix deny blocking the filing tool fails the check"
  fi

  # BAD 5 (the reuse coupling, the part unique to this check): the scout's
  # mcp config is GONE → must fail, even with a perfect deny list.
  if check_pair "$tmp/good-settings.json" "$tmp/good-converter.json" \
      "$tmp/.claude/skills/product-scout/nope.json" \
      "$tmp/.claude/skills/product-scout/scout_mcp.py" 2>/dev/null; then
    echo "FAIL  selftest: a missing scout mcp config was NOT caught"; return 1
  else
    echo "ok    selftest: a missing scout mcp config fails the check"
  fi

  # BAD 5b: the server is renamed inside the config → the tool id the
  # workflow's allow-list names is keyed on that name, so it must fail.
  cat > "$tmp/.claude/skills/product-scout/renamed-mcp.json" <<'EOF'
{"mcpServers": {"briefs": {"command": "python3", "args": [".claude/skills/product-scout/scout_mcp.py"]}}}
EOF
  if check_pair "$tmp/good-settings.json" "$tmp/good-converter.json" \
      "$tmp/.claude/skills/product-scout/renamed-mcp.json" \
      "$tmp/.claude/skills/product-scout/scout_mcp.py" 2>/dev/null; then
    echo "FAIL  selftest: a renamed scout server was NOT caught"; return 1
  else
    echo "ok    selftest: a renamed scout server fails the check"
  fi

  # BAD 5c: the server FILE is gone → must fail.
  if check_pair "$tmp/good-settings.json" "$tmp/good-converter.json" \
      "$tmp/.claude/skills/product-scout/scout-mcp.json" \
      "$tmp/.claude/skills/product-scout/nope.py" 2>/dev/null; then
    echo "FAIL  selftest: a missing scout server file was NOT caught"; return 1
  else
    echo "ok    selftest: a missing scout server file fails the check"
  fi
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    spike-converter-perms-check selftest passed"
  exit 0
fi

[[ -f "$SETTINGS"   ]] || { echo "FAIL  spike-converter-perms: $SETTINGS missing"; exit 1; }
[[ -f "$CONVERTER"  ]] || { echo "FAIL  spike-converter-perms: $CONVERTER missing"; exit 1; }
[[ -f "$SCOUT_MCP_JSON" ]] || { echo "FAIL  spike-converter-perms: $SCOUT_MCP_JSON missing"; exit 1; }
[[ -f "$SCOUT_MCP_PY"   ]] || { echo "FAIL  spike-converter-perms: $SCOUT_MCP_PY missing"; exit 1; }

if check_pair "$SETTINGS" "$CONVERTER" "$SCOUT_MCP_JSON" "$SCOUT_MCP_PY"; then
  echo "ok    spike-converter deny backstop covers every non-wrapper Bash allow (chunk/label/assessor/scout helpers included), never denies converter-helper.sh or mcp__scout__file_design_brief, and the reused scout filing surface is intact"
else
  echo "FAIL  spike-converter permission drift: $CONVERTER does not neutralize every dangerous allow, or the reused scout filing surface has rotted"
  exit 1
fi
