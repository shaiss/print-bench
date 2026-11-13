#!/usr/bin/env bash
# Backlog-burn agent Bash deny check (issue #1022): prove
# .claude/backlog-burn-settings.json still refuses issue comment/edit and
# label writes under Claude Code's matcher, while the burn's legitimate
# local git / read-only gh surface still passes.
#
# WHY THIS EXISTS:
# backlog-burn.yml runs the agent with github.token issues:write (comment
# scope) under --permission-mode dontAsk and
# --settings .claude/backlog-burn-settings.json. Deny beats allow from every
# settingSources layer, but only the rules that are actually present. A
# prompt-injected turn that can `gh issue comment` / `gh issue edit` /
# `gh label` / `gh api …/labels` (non-GET) can steer any issue in the repo.
# Issue #863 already denied autonomy-ok/design-brief steering shapes; #1022
# closes the remaining comment/edit/label write surface.
#
# This is a BEHAVIORAL check, not a grep: it loads the real settings file
# the agent runs with and asks the Claude Code Bash matcher (same
# transcription as scripts/reviewer-deny-canary.sh) whether each probe is
# refused. A rule that is present as text but matches nothing still fails.
#
# Usage:
#   scripts/backlog-burn-perms-check.sh            # check the real file
#   scripts/backlog-burn-perms-check.sh --selftest # prove pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/backlog-burn-settings.json"

# Pure function of one settings file. Prints a diagnosis and returns
# non-zero on any drift. Kept as a function so --selftest can point it at
# fixtures.
check_settings() {
  local settings_path="$1"
  python3 - "$settings_path" <<'PY'
import json, re, sys

settings_path = sys.argv[1]

# --- Claude Code 2.1.301 Bash matcher (same algorithm as
# scripts/reviewer-deny-canary.sh). Behavioral probes must use THIS model,
# not substring greps on the JSON. ---

def kwe(spec: str):
    m = re.match(r"^(.+):\*$", spec)
    return m.group(1) if m else None


def v8r(spec: str) -> bool:
    if spec.endswith(":*"):
        return False
    for n, ch in enumerate(spec):
        if ch != "*":
            continue
        s = 0
        r = n - 1
        while r >= 0 and spec[r] == "\\":
            s += 1
            r -= 1
        if s % 2 == 0:
            return True
    return False


def dollar8(pattern: str, command: str, case_insensitive=False, collapse_ws=False) -> bool:
    if "\x00" in pattern:
        return False
    i = pattern.strip()
    d = re.sub(r"[ \t]+", " ", i) if collapse_ws else i
    c = re.sub(r"[ \t]+", " ", command) if collapse_ws else command
    p_parts = []
    g = 0
    while g < len(d):
        P = d[g]
        if P == "\\" and g + 1 < len(d):
            j = d[g + 1]
            if j == "*":
                p_parts.append("\x00ESCAPED_STAR\x00")
                g += 2
                continue
            if j == "\\":
                p_parts.append("\x00ESCAPED_BACKSLASH\x00")
                g += 2
                continue
        p_parts.append(P)
        g += 1
    p = "".join(p_parts)
    escaped = re.sub(r"""[.+?^${}()|[\]\\'"]""", lambda m: "\\" + m.group(0), p)
    escaped = re.sub(r"/(?:\*\*/)+", "\x00GLOBSTAR\x00", escaped)
    escaped = escaped.replace("*", ".*")
    escaped = escaped.replace("\x00GLOBSTAR\x00", "/(?:.*/)?")
    escaped = escaped.replace("\x00ESCAPED_STAR\x00", r"\*")
    escaped = escaped.replace("\x00ESCAPED_BACKSLASH\x00", r"\\")
    star_count = p.count("*")
    if escaped.endswith(" .*") and star_count == 1:
        escaped = escaped[:-3] + "( .*)?"
    flags = re.DOTALL | (re.IGNORECASE if case_insensitive else 0)
    try:
        return re.match(r"^" + escaped + r"$", c, flags) is not None
    except re.error:
        return False


def zqe(spec: str):
    prefix = kwe(spec)
    if prefix is not None:
        return "prefix", prefix
    if v8r(spec):
        return "wildcard", spec
    return "exact", spec


def bash_denied(spec: str, command: str) -> bool:
    kind, val = zqe(spec)
    if kind == "exact":
        return val.lower() == command.lower()
    if kind == "prefix":
        cl, pl = command.lower(), val.lower()
        return cl == pl or cl.startswith(pl + " ")
    return dollar8(val, command, case_insensitive=True, collapse_ws=True)


def parse_bash_rule(rule: str):
    if not (rule.startswith("Bash(") and rule.endswith(")")):
        return None
    return rule[len("Bash("):-1]


def denies_command(deny_rules, command: str) -> bool:
    for rule in deny_rules:
        spec = parse_bash_rule(rule)
        if spec is None:
            continue
        if bash_denied(spec, command):
            return True
    return False


# Write probes issue #1022 names — each MUST be refused by the live deny
# list under the matcher (not merely present as a JSON string).
MUST_DENY = [
    "gh issue comment 1022 --body x",
    "gh issue comment 1 -b hi",
    "gh issue edit 1022 --title x",
    "gh issue edit 1022 --add-label needs-decision",
    "gh issue edit 1022 --remove-label autonomy-ok",
    "gh label create foo",
    "gh label edit foo --name bar",
    "gh label delete foo",
    "gh api --method POST repos/o/r/issues/1/comments -f body=x",
    "gh api --method POST repos/o/r/issues/1/labels -f name=x",
    "gh api --method PUT repos/o/r/issues/1/labels -f name=x",
    "gh api --method PATCH repos/o/r/issues/1/comments/9 -f body=x",
    "gh api --method DELETE repos/o/r/issues/1/labels/foo",
    "gh api -X POST repos/o/r/issues/1/comments -f body=x",
    "gh api -X POST repos/o/r/issues/1/labels -f name=x",
    "gh api repos/o/r/issues/1/comments -f body=x",
    "gh api repos/o/r/issues/1/labels -f name=x",
    "gh api repos/o/r/issues/1/labels --input -",
    "curl -X POST https://api.github.com/repos/o/r/issues/1/comments -d body=x",
    "curl -X POST https://api.github.com/repos/o/r/issues/1/labels -d name=x",
    "curl -X DELETE https://api.github.com/repos/o/r/issues/1/labels/foo",
    "curl --request PATCH https://api.github.com/repos/o/r/issues/1/comments/9 -d body=x",
    # Autofind on #1027: close/reopen --comment, GraphQL addComment,
    # REST issue PATCH (edit without /comments|/labels), python3 token use.
    "gh issue close 5 --comment x",
    "gh issue reopen 5 -c x",
    "gh api graphql -f query='mutation{addComment(input:{subjectId:\"I_x\",body:\"y\"}){clientMutationId}}'",
    "gh api -X PATCH repos/o/r/issues/5 -f body=x",
    "gh api -X PATCH repos/o/r/issues/5 -f title=x",
    "gh api --method PATCH repos/o/r/issues/5 -f body=x",
    "gh api --method POST repos/o/r/issues/5 -f title=x",
    "python3 -c \"import urllib.request; urllib.request.urlopen('https://api.github.com/repos/o/r/issues/1/comments')\"",
]

# Pre-#1022 steering denies that must keep firing (issue #863).
MUST_DENY += [
    "gh issue edit 1 --add-label autonomy-ok",
    "gh issue edit 1 --add-label design-brief",
    "gh api -f name=autonomy-ok repos/o/r/issues/1/labels",
]

# Legitimate burn surface — must NOT be refused.
MUST_ALLOW = [
    "git status",
    "git checkout -b claude/issue-1022-foo",
    "git switch -c claude/issue-1022-foo",
    "git add designs/foo/foo.scad",
    "git commit -m x",
    "git diff",
    "git log -1",
    "git rev-parse HEAD",
    "git symbolic-ref HEAD",
    "gh issue view 1022",
    "gh pr view 1",
    "gh api repos/o/r/issues/1",
    "gh api repos/o/r/labels",
    "gh api repos/o/r/issues/1/comments",
    "gh api repos/o/r/issues/1/labels",
]

# Exact-string deny rules that must remain present (coverage floor for
# shapes the probe list already exercises behaviorally). Extra denies are
# fine; missing these is drift against the committed backstop contract.
REQUIRED_RULE_SUBSTRINGS = [
    "Bash(gh issue comment",
    "Bash(gh issue edit",
    "Bash(gh label",
    "Bash(gh issue close",
    "Bash(gh issue reopen",
    "Bash(gh api*graphql*addComment*)",
    "Bash(gh api*--method POST*comments*)",
    "Bash(gh api*--method POST*labels*)",
    "Bash(gh api*--method PATCH*issues/*)",
    "Bash(gh api*-X PATCH*issues/*)",
    "Bash(gh api*labels*-f*)",
    "Bash(curl*-X POST*comments*)",
    "Bash(curl*-X POST*labels*)",
    "Bash(python3",
    "Bash(git push",
    "Bash(gh pr create",
]

with open(settings_path) as fh:
    data = json.load(fh)

perms = data.get("permissions") or {}
deny = list(perms.get("deny") or [])
allow = list(perms.get("allow") or [])

ok = True

missing_rules = []
for needle in REQUIRED_RULE_SUBSTRINGS:
    if not any(needle in r for r in deny):
        missing_rules.append(needle)
if missing_rules:
    ok = False
    sys.stderr.write(
        f"backlog-burn settings {settings_path} missing required deny "
        f"rule shapes:\n")
    for r in missing_rules:
        sys.stderr.write(f"    {r}\n")

for cmd in MUST_DENY:
    if not denies_command(deny, cmd):
        ok = False
        sys.stderr.write(
            f"DENIED probe was ALLOWED by {settings_path} matcher:\n"
            f"    {cmd}\n")

for cmd in MUST_ALLOW:
    if denies_command(deny, cmd):
        ok = False
        sys.stderr.write(
            f"LEGITIMATE probe was DENIED by {settings_path} matcher:\n"
            f"    {cmd}\n")

# Allow list must not be widened into issue-write verbs (parity / no-widen).
forbidden_allows = [
    r for r in allow
    if r.startswith("Bash(") and any(
        bad in r for bad in (
            "gh issue comment", "gh issue edit", "gh label",
            "git push", "gh pr create",
        )
    )
]
if forbidden_allows:
    ok = False
    sys.stderr.write(
        f"allow list in {settings_path} widens into forbidden verbs:\n")
    for r in forbidden_allows:
        sys.stderr.write(f"    {r}\n")

sys.exit(0 if ok else 1)
PY
}

selftest() {
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # Positive: a complete fixture (mirrors the real deny shapes) must pass.
  cat >"$tmp/good.json" <<'EOF'
{
  "permissions": {
    "allow": [
      "Bash(git commit:*)",
      "Bash(git add:*)",
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(git rev-parse:*)",
      "Bash(git symbolic-ref:*)",
      "Bash(git checkout -b claude/issue-*)",
      "Bash(git switch -c claude/issue-*)"
    ],
    "deny": [
      "Bash(git push)",
      "Bash(git push:*)",
      "Bash(git push*)",
      "Bash(gh pr create)",
      "Bash(gh pr create:*)",
      "Bash(gh pr create*)",
      "Bash(gh issue comment)",
      "Bash(gh issue comment:*)",
      "Bash(gh issue comment*)",
      "Bash(gh issue edit)",
      "Bash(gh issue edit:*)",
      "Bash(gh issue edit*)",
      "Bash(gh label)",
      "Bash(gh label:*)",
      "Bash(gh label*)",
      "Bash(gh api*--method POST*comments*)",
      "Bash(gh api*--method POST*labels*)",
      "Bash(gh api*--method PUT*labels*)",
      "Bash(gh api*--method PATCH*comments*)",
      "Bash(gh api*--method PATCH*labels*)",
      "Bash(gh api*--method DELETE*comments*)",
      "Bash(gh api*--method DELETE*labels*)",
      "Bash(gh api*comments*-f*)",
      "Bash(gh api*labels*-f*)",
      "Bash(gh api*-f*comments*)",
      "Bash(gh api*-f*labels*)",
      "Bash(gh api*comments*-F*)",
      "Bash(gh api*labels*-F*)",
      "Bash(gh api*-F*comments*)",
      "Bash(gh api*-F*labels*)",
      "Bash(gh api*comments*--input*)",
      "Bash(gh api*labels*--input*)",
      "Bash(gh api*--input*comments*)",
      "Bash(gh api*--input*labels*)",
      "Bash(gh api*-X POST*comments*)",
      "Bash(gh api*-X POST*labels*)",
      "Bash(gh api*autonomy-ok*)",
      "Bash(gh api*design-brief*)",
      "Bash(gh issue edit*autonomy-ok*)",
      "Bash(gh issue edit*design-brief*)",
      "Bash(gh issue close)",
      "Bash(gh issue close:*)",
      "Bash(gh issue close*)",
      "Bash(gh issue reopen)",
      "Bash(gh issue reopen:*)",
      "Bash(gh issue reopen*)",
      "Bash(gh api*graphql*addComment*)",
      "Bash(gh api*--method PATCH*issues/*)",
      "Bash(gh api*--method POST*issues/*)",
      "Bash(gh api*-X PATCH*issues/*)",
      "Bash(gh api*-X POST*issues/*)",
      "Bash(python3)",
      "Bash(python3:*)",
      "Bash(python3*)",
      "Bash(python)",
      "Bash(python:*)",
      "Bash(python*)",
      "Bash(curl*-X POST*comments*)",
      "Bash(curl*-X POST*labels*)",
      "Bash(curl*-X PUT*labels*)",
      "Bash(curl*-X PATCH*comments*)",
      "Bash(curl*-X PATCH*labels*)",
      "Bash(curl*-X DELETE*comments*)",
      "Bash(curl*-X DELETE*labels*)",
      "Bash(curl*-X PATCH*issues/*)",
      "Bash(curl*-X POST*issues/*)",
      "Bash(curl*--request POST*comments*)",
      "Bash(curl*--request POST*labels*)",
      "Bash(curl*--request PUT*labels*)",
      "Bash(curl*--request PATCH*comments*)",
      "Bash(curl*--request PATCH*labels*)",
      "Bash(curl*--request DELETE*comments*)",
      "Bash(curl*--request DELETE*labels*)"
    ]
  }
}
EOF
  if ! check_settings "$tmp/good.json"; then
    echo "FAIL  selftest: a complete deny fixture did not pass" >&2
    return 1
  fi
  echo "ok    selftest: complete deny fixture passes"

  # Negative: drop gh issue comment denies — must fail (behavioral, not grep).
  python3 - "$tmp/good.json" "$tmp/no-comment.json" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
data = json.load(open(src))
data["permissions"]["deny"] = [
    r for r in data["permissions"]["deny"]
    if "gh issue comment" not in r
]
json.dump(data, open(dst, "w"))
PY
  if check_settings "$tmp/no-comment.json"; then
    echo "FAIL  selftest: dropping gh issue comment denies was NOT caught" >&2
    return 1
  fi
  echo "ok    selftest: missing issue-comment denies fail"

  # Negative: a deny that is textually present but matches nothing for labels.
  python3 - "$tmp/good.json" "$tmp/weak-label.json" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
data = json.load(open(src))
data["permissions"]["deny"] = [
    r for r in data["permissions"]["deny"]
    if "gh label" not in r
] + ["Bash(gh label NEVERMATCH)"]
json.dump(data, open(dst, "w"))
PY
  if check_settings "$tmp/weak-label.json"; then
    echo "FAIL  selftest: a non-matching gh label deny was NOT caught" >&2
    return 1
  fi
  echo "ok    selftest: non-matching label deny fails behaviorally"

  # Negative: over-broad deny that blocks git status must fail.
  python3 - "$tmp/good.json" "$tmp/overbroad.json" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
data = json.load(open(src))
data["permissions"]["deny"].append("Bash(git:*)")
json.dump(data, open(dst, "w"))
PY
  if check_settings "$tmp/overbroad.json"; then
    echo "FAIL  selftest: over-broad git:* deny was NOT caught" >&2
    return 1
  fi
  echo "ok    selftest: over-broad git deny fails"

  echo "ok    backlog-burn-perms-check selftest passed"
}

case "${1:-}" in
  --selftest) selftest ;;
  "")
    check_settings "$SETTINGS"
    echo "ok    backlog-burn deny backstop refuses issue comment/edit/label writes and keeps the legitimate burn surface"
    ;;
  *)
    echo "usage: $0 [--selftest]" >&2
    exit 2
    ;;
esac
