#!/usr/bin/env bash
# Reviewer permission-drift check: prove the auto-review deny backstops
# (.claude/reviewer-settings.json and .claude/design-coach-settings.json) still
# neutralize every Bash allow they would otherwise inherit from
# .claude/settings.json, always deny the render toolchain, and never deny the
# surface a review needs. Run by scripts/check.sh (and therefore by /preflight
# and CI's scad-check jobs).
#
# WHY THIS EXISTS:
# .github/workflows/auto-review.yml runs claude-code-action, which starts the
# SDK with settingSources:[user,project,local] — so it loads this repo's
# .claude/settings.json permissions.allow. That file carries dev entries the
# interactive agents need, including `Bash(xvfb-run:*)` (arbitrary command
# execution) and the render toolchain allows. Allow rules merge ADDITIVELY
# across sources, so nothing in the reviewer steps removes them. The reviewers
# close this with their own backstops (passed via --settings, under
# --permission-mode dontAsk — a bypassPermissions step ignores its own denies),
# where deny beats allow from every source. Issue #323: the reviewers consume
# CI's posted printcheck/slice results and must never install or run the
# render toolchain themselves.
#
# There are TWO reviewer backstops because their surfaces differ:
# - .claude/reviewer-settings.json: Jane, Drik, PM triage — read-only on the
#   repo, so it must deny Write/Edit/NotebookEdit (and tee, which coverage
#   forces, so a shell cannot stand in for the denied Write), and it denies
#   git OUTRIGHT (Bash(git:*)): a deny list cannot contain git — a subcommand
#   option the prefix never sees (`git fetch origin --upload-pack=…`), an exec
#   key in a repo config reached through a PR-committed directory — so the
#   reviewers get none, and auto-review.yml stages the PR head's design
#   directories for them in a trusted step instead (code-scanning finding on
#   #760).
# - .claude/design-coach-settings.json: the design coach — it pushes
#   iterations, so it must NOT deny Write/Edit (or git checkout/add/commit/
#   push); it still denies NotebookEdit and Write/Edit into .git/, and carries
#   the git floor below (no fetch/clone/pull/ls-remote — its job checks out
#   with full history — and no global options at all).
#
# The rules, the labeler/oracle precedent applied to the reviewers:
# 1. Coverage — EVERY Bash allow in settings.json must be denied verbatim,
#    except the backstop's REVIEW SURFACE: the exact allow rules a review
#    actually runs (gh to read the PR and post, jq and mktemp to shape a
#    comment body; plus, for the reviewer backstop only, the chunker's
#    chunk-helper.sh, whose `ensure-label needs-decision` verb is the PM
#    triage's HITL-gate step, pm SKILL.md §7/§8.7; for the coach only, git to
#    land its iterations). Not a hardcoded list of "toolchain" names: a new
#    script allow is drift the day it lands.
# 2. Floor — the render toolchain #323 names (apt/apt-get, openscad,
#    openscad-nightly, xvfb-run, prusa-slicer, printcheck, the gate/render/
#    check scripts and session-start.sh, both path spellings) must be denied
#    whatever settings.json allows today, plus both growth-desk MCP servers
#    (every sibling backstop denies them; a `Bash(mcp__…)` rule denies a
#    shell command of that name, not the server), plus the gh escape hatches
#    (alias/extension/config/auth/…, repo/pr checkout/browse) and the coach's
#    git floor — each present verbatim AND proven to block a representative
#    invocation under Claude Code's word-boundary `:*` matching.
# 3. Surface guard — no deny may block the review surface: a probe command
#    per need (gh pr view/diff/comment, gh api; the coach's git diff/log/
#    checkout/add/commit/push) is
#    matched against every Bash deny with wildcard and prefix semantics, so
#    `Bash(gh:*)`, `Bash(g*:*)` and `Bash(gh pr comment:*)` all fail while a
#    narrow `Bash(gh pr merge:*)` passes. Read/Grep/Glob must not be denied
#    (a bare, blanket or wildcard tool rule; a path-scoped Read(./x) is fine).
# 4. Posture — reviewer denies Write/Edit/NotebookEdit and Bash(git:*); the
#    coach never denies Write/Edit (wildcards included) but denies
#    Edit(./.git/**).
# 5. Hygiene — no deny rule twice: a duplicate is how the coach backstop once
#    carried `./scripts/regen-stamp.sh` twice and never its bare spelling.
#
# That backstop is only as good as its coverage. Add a Bash allow to
# settings.json tomorrow and, unless it is also denied here, the reviewers
# silently inherit it again — an invisible regression, because the thing being
# protected is the ABSENCE of a capability. Extra denies are fine (this
# asserts coverage, not equality) as long as none reaches the review surface.
# The WORKFLOW half — every reviewer ship step passes its backstop under
# dontAsk — is pinned by tools/model-registry/tests/
# test_reviewer_backstop_wiring.py, and the git environment lock plus the
# trusted head-staging step by test_reviewer_git_containment.py; this script
# holds the FILE half.
#
# Usage:
#   scripts/reviewer-perms-check.sh            # check the real files
#   scripts/reviewer-perms-check.sh --selftest # prove the check can pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

SETTINGS=".claude/settings.json"
REVIEWER=".claude/reviewer-settings.json"
COACH=".claude/design-coach-settings.json"

# Core comparison, pure function of two settings files plus which backstop is
# being checked ("reviewer" or "coach"). Prints a diagnosis and returns
# non-zero on any drift. Kept as a function so --selftest can point it at
# fixtures.
check_pair() {
  local settings_path="$1" backstop_path="$2" kind="$3"
  python3 - "$settings_path" "$backstop_path" "$kind" <<'PY'
import collections, fnmatch, json, sys

settings_path, backstop_path, kind = sys.argv[1], sys.argv[2], sys.argv[3]

# The review surface, identified by EXACT allow rule (both path spellings for
# a wrapper) — never a loose substring, so a same-basename rule on a different
# path is not exempted. Exempt from coverage only; it is not "must allow".
# git is NOT shared: the read-only reviewers run with no git at all (the
# code-scanning finding on #760 — a deny list cannot contain git), so for them
# Bash(git:*) is an ordinary allow that coverage forces them to deny.
SHARED_SURFACE = {"Bash(gh:*)", "Bash(jq:*)", "Bash(mktemp:*)"}
# Commands a deny must never block, matched with wildcard + prefix semantics.
SHARED_PROBES = [
    "gh pr view 1", "gh pr diff 1", "gh pr comment 1 --body x",
    "gh api repos/o/r/pulls/1/comments", "gh issue edit 1 --add-label x",
    "gh pr edit 1 --add-label x",
]
if kind == "reviewer":
    # PM triage raises a blocking fork through the HITL gate with the
    # chunker's ensure-label verb (pm SKILL.md §7, run from §8.7). Every verb
    # the wrapper has is a subset of what Bash(gh:*) already grants this job,
    # so denying it buys no containment and breaks a documented gate step.
    SURFACE = SHARED_SURFACE | {
        "Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)",
        "Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)",
    }
    PROBES = SHARED_PROBES + [
        ".claude/skills/chunk-issue/chunk-helper.sh ensure-label needs-decision",
        "./.claude/skills/chunk-issue/chunk-helper.sh ensure-label needs-decision",
    ]
    # Read-only on the repo: no file-mutating tool. And no git: the PR head's
    # design directories are staged by a trusted workflow step before the
    # session starts (auto-review.yml), so nothing a review does needs git.
    POSTURE_DENY = [{"Write"}, {"Edit"}, {"NotebookEdit"}, {"Bash(git:*)"}]
    # The posting surface (issues #764 / #772): Jane/Drik use
    # mcp__reviewer__post_review and pm-triage uses
    # mcp__reviewer__post_triage, allowed per step by --allowedTools
    # (never by settings.json, so coverage rule 1 never sees them). A deny of
    # either tool spelling or the server would silently kill posting again,
    # so all three are protected here.
    NEVER_DENY_TOOLS = [
        "Read", "Grep", "Glob",
        "mcp__reviewer", "mcp__reviewer__post_review",
        "mcp__reviewer__post_triage",
    ]
    GIT_FLOOR = []
elif kind == "coach":
    # The coach lands each round as a pushed iteration, so it keeps git — but
    # only the local verbs: the job checks out with full history (every branch
    # head is already local), so it never fetches.
    SURFACE = SHARED_SURFACE | {"Bash(git:*)"}
    PROBES = SHARED_PROBES + [
        "git diff", "git log", "git show HEAD", "git status",
        "git checkout HEAD -- designs", "git checkout -B b origin/b",
        "git add designs", "git commit -m x", "git push origin HEAD",
    ]
    # NotebookEdit, plus Write/Edit into .git/ itself: the coach's file tools
    # stay usable on the tree, but a written .git/config could bind an exec
    # key (an alias, diff.external, a pager.<cmd>) the env lock does not pin.
    POSTURE_DENY = [{"NotebookEdit"}, {"Edit(./.git/**)"}]
    NEVER_DENY_TOOLS = [
        "Read", "Grep", "Glob", "Write", "Edit",
        "mcp__reviewer", "mcp__reviewer__post_coach",
    ]
    # The coach's git floor: global options and verbs that run a user command,
    # reach a non-origin repository, or move a credential. Each `:*` rule is a
    # WORD-BOUNDARY prefix in Claude Code (`git -c:*` is `git -c *`), so it does
    # NOT match the `=`/combined spellings (`git -cx=y`, `git --git-dir=x`);
    # the no-boundary `*` spellings beside them do, and `Bash(git -*)` refuses
    # every global option however the options are ordered (`git --no-pager -c
    # x=y log` starts with --no-pager). The strict matcher below models that,
    # so a rule spelled to match nothing fails ESCAPE_PROBES.
    GIT_FLOOR = [
        {"Bash(git -*)"},
        {"Bash(git -c:*)"}, {"Bash(git -c*)"}, {"Bash(git -C:*)"}, {"Bash(git -C*)"},
        {"Bash(git --config-env:*)"}, {"Bash(git --config-env*)"},
        {"Bash(git --exec-path:*)"}, {"Bash(git --exec-path*)"},
        {"Bash(git --git-dir:*)"}, {"Bash(git --git-dir*)"},
        {"Bash(git --work-tree:*)"}, {"Bash(git --work-tree*)"},
        {"Bash(git --bare:*)"}, {"Bash(git --bare*)"},
        {"Bash(git --namespace:*)"}, {"Bash(git --namespace*)"},
        {"Bash(git fetch:*)"}, {"Bash(git clone:*)"}, {"Bash(git pull:*)"},
        {"Bash(git ls-remote:*)"},
        {"Bash(git config:*)"}, {"Bash(git submodule:*)"},
        {"Bash(git bisect:*)"}, {"Bash(git rebase:*)"},
        {"Bash(git filter-branch:*)"}, {"Bash(git difftool:*)"},
        {"Bash(git mergetool:*)"}, {"Bash(git daemon:*)"},
        {"Bash(git archive:*)"}, {"Bash(git upload-pack:*)"},
        {"Bash(git upload-archive:*)"},
        {"Bash(git credential:*)"}, {"Bash(git credential*)"},
        {"Bash(git grep:*)"}, {"Bash(git remote-*)"},
        {"Bash(git instaweb:*)"}, {"Bash(git send-email:*)"},
    ]
else:
    sys.stderr.write(f"unknown backstop kind {kind!r}\n")
    sys.exit(2)

# Required denies the backstop must ALWAYS carry, whatever settings.json
# allows today: the render toolchain #323 exists to keep out of a review
# session, and the growth desk's two MCP servers (server- or tool-level).
REQUIRED_DENIES = [
    {"Bash(apt:*)"}, {"Bash(apt-get:*)"},
    {"Bash(openscad:*)"}, {"Bash(openscad-nightly:*)"},
    {"Bash(xvfb-run:*)"}, {"Bash(prusa-slicer:*)"}, {"Bash(printcheck:*)"},
    {"Bash(./scripts/gate.sh:*)"}, {"Bash(scripts/gate.sh:*)"},
    {"Bash(./scripts/render.sh:*)"}, {"Bash(scripts/render.sh:*)"},
    {"Bash(./scripts/check.sh:*)"}, {"Bash(scripts/check.sh:*)"},
    {"Bash(.claude/hooks/session-start.sh:*)"},
    {"Bash(./.claude/hooks/session-start.sh:*)"},
    {"mcp__growth_queue", "mcp__growth_queue__queue_growth_post"},
    {"mcp__growth_twitter", "mcp__growth_twitter__post_tweet"},
] + POSTURE_DENY

# Escape-hatch floor: gh subcommands (both backstops — Bash(gh:*) is the
# review surface, exempt from coverage rule 1, and allow rules merge
# additively, so the backstop cannot narrow it to read verbs: deny always beats
# allow but allow cannot be subtracted) plus the coach's GIT_FLOOR. alias/
# extension bind or run a shell; config set swaps pager/editor/browser to one;
# codespace runs remote commands; auth/secret/ssh-key/gpg-key print or plant
# credentials; workflow/run trigger or re-run CI; repo (clone/fork/sync) and
# pr checkout spawn git with caller-supplied arguments; browse launches a
# browser. None is a verb a review runs — SHARED_PROBES proves the real
# surface stays open under these denies.
#   Below the deny list sits the ENVIRONMENT lock every reviewer and coach job
# carries in auto-review.yml (GIT_ALLOW_PROTOCOL=https plus command-scope
# safe.bareRepository/core.fsmonitor/core.hooksPath/core.pager): git refuses
# the file/ext transports whatever the option order, so the subcommand options
# a prefix rule cannot see (`git fetch origin --upload-pack=…`, `git push
# --receive-pack=… .`) have nothing to execute. An env-prefixed command
# (`GIT_ALLOW_PROTOCOL=file git …`) does not start with `git`, so Bash(git:*)
# never grants it under dontAsk. That lock is pinned by
# tools/model-registry/tests/test_reviewer_git_containment.py, not here.
ESCAPE_HATCH_DENIES = [
    {"Bash(gh alias:*)"}, {"Bash(gh extension:*)"}, {"Bash(gh ext:*)"},
    {"Bash(gh config:*)"}, {"Bash(gh codespace:*)"}, {"Bash(gh cs:*)"},
    {"Bash(gh secret:*)"}, {"Bash(gh ssh-key:*)"}, {"Bash(gh gpg-key:*)"},
    {"Bash(gh auth:*)"}, {"Bash(gh workflow:*)"}, {"Bash(gh run:*)"},
    {"Bash(gh repo:*)"}, {"Bash(gh pr checkout:*)"}, {"Bash(gh browse:*)"},
] + GIT_FLOOR

# Representative dangerous invocations the deny list must actually BLOCK under
# Claude Code's real (strict) matching — the negative half of the floor
# (presence alone could pass with a rule spelled so it matches nothing). Both
# backstops: the reviewer blocks the git ones with Bash(git:*), the coach with
# its GIT_FLOOR. Benign placeholder args; these are matcher test strings, not
# runnable commands. Each must be blocked by >= 1 deny.
ESCAPE_PROBES = [
    "git -c core.pager=x log", "git -cx=y status",
    "git -C /path/to/repo status", "git -C/path status",
    "git --config-env=x=y status", "git --config-env x=y status",
    "git --exec-path=/path log", "git --exec-path /path log",
    "git --git-dir=/path log", "git --git-dir /path log",
    "git --work-tree=/path status", "git --work-tree /path status",
    "git --bare log", "git --bare=x log",
    "git --namespace=x log", "git --namespace x log",
    "git --no-pager -c x=y log", "git -p --git-dir=x log",
    "git fetch origin", "git fetch . --upload-pack=x", "git clone x y",
    "git pull origin", "git ls-remote .",
    "git config core.pager x", "git submodule foreach x",
    "git bisect run x", "git rebase --exec x HEAD~1",
    "git filter-branch --tree-filter x HEAD",
    "git difftool -x x HEAD", "git mergetool",
    "git daemon --export-all", "git archive --remote=x x HEAD",
    "git upload-pack .", "git upload-archive .",
    "git credential fill", "git credential-store get",
    "git grep -Ox y", "git remote-ext . x", "git instaweb --httpd=x",
    "git send-email x",
    "gh alias set x y", "gh extension install o/r", "gh ext exec x",
    "gh config set pager x", "gh codespace ssh", "gh cs ssh",
    "gh secret list", "gh ssh-key add k", "gh gpg-key add k",
    "gh auth token", "gh workflow run x", "gh run rerun 1",
    "gh repo clone o/r", "gh pr checkout 1", "gh browse",
]

# A tool-rule specifier that scopes nothing — `Read(**)` denies Read outright.
BLANKET_SPECS = {"", "*", "**", "/**", "./**", "**/*", "//**"}

def load(path):
    with open(path) as fh:
        return json.load(fh)

def bash_deny_blocks(rule, command):
    # GENEROUS to the deny (the safe direction for the surface guard: "could
    # this deny block a probe?"): a `:*` rule is treated as a bare prefix, with
    # or without a word boundary, and `*` matches across spaces and slashes.
    # A bare `Bash` denies all.
    if rule == "Bash":
        return True
    if not (rule.startswith("Bash(") and rule.endswith(")")):
        return False
    spec = rule[len("Bash("):-1]
    if spec.endswith(":*"):
        return fnmatch.fnmatchcase(command, spec[:-2] + "*")
    return fnmatch.fnmatchcase(command, spec)

def bash_deny_surely_blocks(rule, command):
    # STRICT (the safe direction for the floor: "does this deny really block
    # an escape?"): Claude Code's `:*` suffix is a word-boundary prefix — the
    # command is the prefix itself or the prefix plus a space — so
    # `Bash(git -c:*)` does NOT block `git -cx=y` or `Bash(git --git-dir:*)`
    # `git --git-dir=x`; a `*` elsewhere is a wildcard over any characters;
    # no `*` at all is an exact match. Generous matching here would let a
    # boundary rule pass for the `=` spellings it never sees.
    if rule == "Bash":
        return True
    if not (rule.startswith("Bash(") and rule.endswith(")")):
        return False
    spec = rule[len("Bash("):-1]
    if spec.endswith(":*"):
        prefix = spec[:-2]
        if "*" in prefix:
            return fnmatch.fnmatchcase(command, prefix) or \
                fnmatch.fnmatchcase(command, prefix + " *")
        return command == prefix or command.startswith(prefix + " ")
    return fnmatch.fnmatchcase(command, spec)

def tool_deny_blocks(rule, tool):
    # `Read`, `Read(**)`, `*` or `Re*` block the tool; a path-scoped
    # `Read(./.env)` leaves it usable. Bash rules are probed separately.
    name, paren, rest = rule.partition("(")
    if name == "Bash" or not fnmatch.fnmatchcase(tool, name):
        return False
    return not paren or rest[:-1].strip() in BLANKET_SPECS

allow = load(settings_path).get("permissions", {}).get("allow", [])
deny  = load(backstop_path).get("permissions", {}).get("deny", [])
deny_set = set(deny)

# 1. Coverage: every non-surface Bash allow must be denied verbatim.
missing = [r for r in allow
           if r.startswith("Bash(") and r not in SURFACE and r not in deny_set]
# 2 + 4. The floor and the posture, asserted whatever settings.json says.
missing_required = [sorted(alts) for alts in REQUIRED_DENIES
                    if not (alts & deny_set)]
# 2b. The git/gh escape-hatch floor: present verbatim AND actually matching.
missing_escape = [sorted(alts) for alts in ESCAPE_HATCH_DENIES
                  if not (alts & deny_set)]
unblocked_escape = [p for p in ESCAPE_PROBES
                    if not any(bash_deny_surely_blocks(d, p) for d in deny)]
# 3 + 4. Nothing may block the review surface or a tool the backstop needs.
blocked = [(d, p) for d in deny for p in PROBES if bash_deny_blocks(d, p)]
blocked += [(d, t) for d in deny for t in NEVER_DENY_TOOLS
            if tool_deny_blocks(d, t)]
# 5. A duplicate is the typo'd-twin symptom.
dupes = sorted(r for r, n in collections.Counter(deny).items() if n > 1)

ok = True
if blocked:
    ok = False
    sys.stderr.write(
        f"a deny rule in {backstop_path} blocks the {kind}'s review surface "
        f"— the session could no longer read the PR or post its review:\n")
    for rule, what in blocked:
        sys.stderr.write(f"    {rule}  (blocks: {what})\n")
if missing:
    ok = False
    sys.stderr.write(
        f"these Bash allows in {settings_path} are NOT denied in "
        f"{backstop_path} (the {kind} inherits them via "
        f"settingSources=project):\n")
    for r in missing:
        sys.stderr.write(f"    {r}\n")
    sys.stderr.write(f"  → add each to {backstop_path} permissions.deny.\n")
if missing_required:
    ok = False
    sys.stderr.write(
        f"required denies (render toolchain / growth-desk servers / the "
        f"{kind}'s file-tool and git posture) are missing from "
        f"{backstop_path}:\n")
    for alts in missing_required:
        sys.stderr.write(f"    {' or '.join(alts)}\n")
if missing_escape:
    ok = False
    sys.stderr.write(
        f"git/gh escape-hatch floor denies are missing from {backstop_path} "
        f"(the Bash(gh:*) review surface — and the coach's Bash(git:*) — is "
        f"exempt from coverage, so these command-execution/credential vectors "
        f"must be denied explicitly or the {kind} inherits them):\n")
    for alts in missing_escape:
        sys.stderr.write(f"    {' or '.join(alts)}\n")
if unblocked_escape:
    ok = False
    sys.stderr.write(
        f"escape-hatch floor denies in {backstop_path} do not actually block "
        f"these invocations under Claude Code's word-boundary `:*` matching "
        f"(a rule is present but spelled so it misses them):\n")
    for p in unblocked_escape:
        sys.stderr.write(f"    {p}\n")
if dupes:
    ok = False
    sys.stderr.write(
        f"duplicate deny rules in {backstop_path} (usually a typo'd twin — "
        f"the spelling it was meant to be is the one left undenied):\n")
    for r in dupes:
        sys.stderr.write(f"    {r}\n")

sys.exit(0 if ok else 1)
PY
}

# Fixture helper: copy a settings file, applying +rule / -rule edits to one
# permissions list. A `-rule` the source does not carry is an error, so a
# control can never pass because its mutation silently missed.
derive() {
  local src="$1" dst="$2" key="$3"
  shift 3
  python3 - "$src" "$dst" "$key" "$@" <<'PY'
import json, sys
src, dst, key, *edits = sys.argv[1:]
with open(src) as fh:
    data = json.load(fh)
rules = data.setdefault("permissions", {}).setdefault(key, [])
for edit in edits:
    op, rule = edit[:1], edit[1:]
    if op == "+":
        rules.append(rule)
    elif op == "-" and rule in rules:
        rules[:] = [r for r in rules if r != rule]
    else:
        sys.exit(f"derive: cannot apply {edit!r} to {src} {key} — the fixture is stale")
with open(dst, "w") as fh:
    json.dump(data, fh)
PY
}

selftest() {
  local tmp bad=0 n=0
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # expect <pass|fail> <what> <settings> <backstop> <kind>
  expect() {
    local want="$1" what="$2" got
    shift 2
    n=$((n + 1))
    if check_pair "$@" 2>/dev/null; then got=pass; else got=fail; fi
    if [[ "$got" == "$want" ]]; then
      echo "ok    selftest: $what"
    else
      echo "FAIL  selftest: $what (check said $got, want $want)"
      bad=1
    fi
  }

  # A minimal-but-complete settings.json: a toolchain allow, a script-path
  # allow, a shell file-writer, the review surface (gh/jq/mktemp, and git —
  # the coach's surface, the reviewer's forced deny), and the chunker's
  # wrapper (reviewer surface, coach drift).
  cat > "$tmp/settings.json" <<'EOF'
{"permissions":{"allow":["Bash(xvfb-run:*)","Bash(./scripts/gate.sh:*)","Bash(tee:*)","Bash(gh:*)","Bash(git:*)","Bash(jq:*)","Bash(mktemp:*)","Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)","Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)"]}}
EOF
  # The matching good reviewer backstop: the toolchain floor, the growth
  # servers, the gh escape hatches, the covered allows (git among them), and
  # its read-only posture.
  local GH_FLOOR=(
    "Bash(gh alias:*)" "Bash(gh extension:*)" "Bash(gh ext:*)" "Bash(gh config:*)"
    "Bash(gh codespace:*)" "Bash(gh cs:*)" "Bash(gh secret:*)" "Bash(gh ssh-key:*)"
    "Bash(gh gpg-key:*)" "Bash(gh auth:*)" "Bash(gh workflow:*)" "Bash(gh run:*)"
    "Bash(gh repo:*)" "Bash(gh pr checkout:*)" "Bash(gh browse:*)"
  )
  # The coach's git floor (it keeps git, so these are what stand between it
  # and a command-running option).
  local GIT_FLOOR=(
    "Bash(git -*)"
    "Bash(git -c:*)" "Bash(git -c*)" "Bash(git -C:*)" "Bash(git -C*)"
    "Bash(git --config-env:*)" "Bash(git --config-env*)"
    "Bash(git --exec-path:*)" "Bash(git --exec-path*)"
    "Bash(git --git-dir:*)" "Bash(git --git-dir*)"
    "Bash(git --work-tree:*)" "Bash(git --work-tree*)"
    "Bash(git --bare:*)" "Bash(git --bare*)"
    "Bash(git --namespace:*)" "Bash(git --namespace*)"
    "Bash(git fetch:*)" "Bash(git clone:*)" "Bash(git pull:*)" "Bash(git ls-remote:*)"
    "Bash(git config:*)" "Bash(git submodule:*)" "Bash(git bisect:*)" "Bash(git rebase:*)"
    "Bash(git filter-branch:*)" "Bash(git difftool:*)" "Bash(git mergetool:*)"
    "Bash(git daemon:*)" "Bash(git archive:*)" "Bash(git upload-pack:*)"
    "Bash(git upload-archive:*)" "Bash(git credential:*)" "Bash(git credential*)"
    "Bash(git grep:*)" "Bash(git remote-*)" "Bash(git instaweb:*)" "Bash(git send-email:*)"
  )
  python3 - "$tmp/reviewer.json" "${GH_FLOOR[@]}" <<'PY2'
import json, sys
out, *gh = sys.argv[1:]
deny = ["Bash(apt:*)","Bash(apt-get:*)","Bash(openscad:*)","Bash(openscad-nightly:*)",
        "Bash(xvfb-run:*)","Bash(prusa-slicer:*)","Bash(printcheck:*)",
        "Bash(./scripts/gate.sh:*)","Bash(scripts/gate.sh:*)",
        "Bash(./scripts/render.sh:*)","Bash(scripts/render.sh:*)",
        "Bash(./scripts/check.sh:*)","Bash(scripts/check.sh:*)",
        "Bash(.claude/hooks/session-start.sh:*)","Bash(./.claude/hooks/session-start.sh:*)",
        "mcp__growth_queue","mcp__growth_twitter",
        *gh, "Bash(git:*)", "Bash(tee:*)", "Write", "Edit", "NotebookEdit"]
json.dump({"permissions": {"deny": deny}}, open(out, "w"))
PY2
  local coach_edits=(-Write -Edit "-Bash(git:*)" "+Edit(./.git/**)"
    "+Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)"
    "+Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)")
  for f in "${GIT_FLOOR[@]}"; do coach_edits+=("+$f"); done
  derive "$tmp/reviewer.json" "$tmp/coach.json" deny "${coach_edits[@]}"

  local S="$tmp/settings.json" R="$tmp/reviewer.json" C="$tmp/coach.json" f
  expect pass "complete reviewer backstop passes" "$S" "$R" reviewer
  expect pass "complete design-coach backstop passes" "$S" "$C" coach

  # Coverage: a new script-path allow the old toolchain-name rule never saw.
  derive "$S" "$tmp/s1.json" allow "+Bash(./scripts/plate.sh:*)"
  expect fail "an undenied script-path allow fails the check" "$tmp/s1.json" "$R" reviewer
  # Floor: apt-get is on no allow list, so only the floor can see it go.
  derive "$R" "$tmp/r.json" deny "-Bash(apt-get:*)"
  expect fail "a dropped toolchain floor deny (apt-get) fails the check" "$S" "$tmp/r.json" reviewer
  derive "$C" "$tmp/c.json" deny "-Bash(scripts/render.sh:*)"
  expect fail "a dropped floor deny in the coach backstop fails the check" "$S" "$tmp/c.json" coach
  # No git for the reviewers: Bash(git:*) is a forced deny (coverage AND the
  # posture floor), never surface — dropping it fails, and so does a backstop
  # whose settings.json no longer allows git (the posture holds regardless).
  derive "$R" "$tmp/r.json" deny "-Bash(git:*)"
  expect fail "a reviewer backstop that lets git through fails the check" "$S" "$tmp/r.json" reviewer
  derive "$S" "$tmp/s2.json" allow "-Bash(git:*)"
  expect fail "the reviewer git deny is required even with no git allow" "$tmp/s2.json" "$tmp/r.json" reviewer
  # …and the coach keeps git: denying it outright breaks its push surface.
  derive "$C" "$tmp/c.json" deny "+Bash(git:*)"
  expect fail "a coach backstop that denies git outright fails the check" "$S" "$tmp/c.json" coach
  # Surface guard: exact, wildcard and narrow-prefix denies on gh.
  for f in "Bash(gh:*)" "Bash(g*:*)" "Bash(gh pr comment:*)" "Bash(*)" "Bash"; do
    derive "$R" "$tmp/r.json" deny "+$f"
    expect fail "denying the review surface with $f fails the check" "$S" "$tmp/r.json" reviewer
  done
  # …and its precision: a narrow deny off the surface is fine.
  derive "$R" "$tmp/r.json" deny "+Bash(gh pr merge:*)"
  expect pass "a narrow deny off the review surface (gh pr merge) passes" "$S" "$tmp/r.json" reviewer
  for f in "Bash(git push:*)" "Bash(git commit:*)" "Bash(git checkout:*)" "Bash(git c*)"; do
    derive "$C" "$tmp/c.json" deny "+$f"
    expect fail "denying the coach's git surface with $f fails the check" "$S" "$tmp/c.json" coach
  done
  derive "$R" "$tmp/r.json" deny "+Bash(.claude/skills/chunk-issue/*:*)"
  expect fail "denying PM triage's ensure-label wrapper fails the check" "$S" "$tmp/r.json" reviewer
  # File tools: blanket and wildcard read denies fail, a path-scoped one passes.
  for f in "Read" "Grep" "Glob" "Read(**)" "*"; do
    derive "$R" "$tmp/r.json" deny "+$f"
    expect fail "denying a read tool with $f fails the check" "$S" "$tmp/r.json" reviewer
  done
  derive "$R" "$tmp/r.json" deny "+Read(./.env)"
  expect pass "a path-scoped Read deny passes" "$S" "$tmp/r.json" reviewer
  # Posting surface (issue #764): denying the reviewers' ONE write — either
  # spelling, the tool or its server — kills every sign-off again; the check
  # must catch it.
  for f in "mcp__reviewer__post_review" "mcp__reviewer__post_triage" "mcp__reviewer"; do
    derive "$R" "$tmp/r.json" deny "+$f"
    expect fail "denying the posting surface with $f fails the check" "$S" "$tmp/r.json" reviewer
  done
  for f in "mcp__reviewer__post_coach" "mcp__reviewer"; do
    derive "$C" "$tmp/c.json" deny "+$f"
    expect fail "denying the coach posting surface with $f fails the check" "$S" "$tmp/c.json" coach
  done
  # Posture: the reviewer must deny Write; the coach must not deny Edit, and
  # must deny Edit into .git/ (a written .git/config binds exec keys).
  derive "$R" "$tmp/r.json" deny -Write
  expect fail "a reviewer backstop without a Write deny fails the check" "$S" "$tmp/r.json" reviewer
  derive "$C" "$tmp/c.json" deny +Edit
  expect fail "a coach backstop that denies Edit fails the check" "$S" "$tmp/c.json" coach
  derive "$C" "$tmp/c.json" deny "+Wr*"
  expect fail "a coach backstop that wildcard-denies Write fails the check" "$S" "$tmp/c.json" coach
  derive "$C" "$tmp/c.json" deny "-Edit(./.git/**)"
  expect fail "a coach backstop that lets Edit reach .git/ fails the check" "$S" "$tmp/c.json" coach
  # The surfaces are per-backstop: the coach has no use for chunk-helper.
  derive "$C" "$tmp/c.json" deny "-Bash(./.claude/skills/chunk-issue/chunk-helper.sh:*)"
  expect fail "a coach backstop leaving chunk-helper undenied fails the check" "$S" "$tmp/c.json" coach
  # Growth servers: the old Bash(mcp__…) spelling denies a shell command.
  derive "$R" "$tmp/r.json" deny -mcp__growth_queue "+Bash(mcp__growth_queue:*)"
  expect fail "a growth-server deny spelled as a Bash rule fails the check" "$S" "$tmp/r.json" reviewer
  # Hygiene: a duplicated rule.
  derive "$C" "$tmp/c.json" deny "+Bash(./scripts/gate.sh:*)"
  expect fail "a duplicate deny rule fails the check" "$S" "$tmp/c.json" coach

  # Escape-hatch floor: dropping ANY one of the gh denies must fail the check
  # in BOTH backstops, and ANY one of the git floor denies in the coach's —
  # the negative control per floor rule. The complete-backstop pass cases
  # above are the positive control.
  for f in "${GH_FLOOR[@]}"; do
    derive "$R" "$tmp/r.json" deny "-$f"
    expect fail "dropping escape-hatch floor deny $f fails the check (reviewer)" "$S" "$tmp/r.json" reviewer
    derive "$C" "$tmp/c.json" deny "-$f"
    expect fail "dropping escape-hatch floor deny $f fails the check (coach)" "$S" "$tmp/c.json" coach
  done
  for f in "${GIT_FLOOR[@]}"; do
    derive "$C" "$tmp/c.json" deny "-$f"
    expect fail "dropping git floor deny $f fails the check (coach)" "$S" "$tmp/c.json" coach
  done
  # The strict matcher, not presence alone: with the no-boundary spellings and
  # the global-option catch-all gone, the `:*` rules are still PRESENT but
  # Claude Code's word-boundary match misses the `=` spellings — so the probe
  # half must fail on its own. The presence floor would fail these fixtures
  # anyway, so the case reads the probe diagnosis, not the exit code.
  # (Captured, not piped: under pipefail the failing check_pair would make
  # the whole `| grep -q` pipeline fail even when the line is there.)
  local diag
  derive "$C" "$tmp/c.json" deny "-Bash(git -*)" "-Bash(git --git-dir*)"
  diag="$(check_pair "$S" "$tmp/c.json" coach 2>&1 >/dev/null || true)"
  if grep -qx '    git --git-dir=/path log' <<<"$diag"; then
    n=$((n + 1)); echo "ok    selftest: a boundary-only Bash(git --git-dir:*) does not block git --git-dir=x (strict matcher)"
  else
    n=$((n + 1)); echo "FAIL  selftest: the strict matcher let Bash(git --git-dir:*) cover git --git-dir=x"; bad=1
  fi
  derive "$C" "$tmp/c.json" deny "-Bash(git -*)" "-Bash(git -c*)"
  diag="$(check_pair "$S" "$tmp/c.json" coach 2>&1 >/dev/null || true)"
  if grep -qx '    git -cx=y status' <<<"$diag"; then
    n=$((n + 1)); echo "ok    selftest: a boundary-only Bash(git -c:*) does not block git -cx=y (strict matcher)"
  else
    n=$((n + 1)); echo "FAIL  selftest: the strict matcher let Bash(git -c:*) cover git -cx=y"; bad=1
  fi
  # And the floor must not cost the real surface: the complete coach backstop
  # (which carries the floor) still passes with its push verbs intact — the
  # per-rule drops above would also catch a floor deny that swallowed a probe.
  expect pass "the floor leaves the coach's git checkout/add/commit/push surface open" "$S" "$C" coach

  echo "      selftest: $n cases"
  return "$bad"
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    reviewer-perms-check selftest passed"
  exit 0
fi

[[ -f "$SETTINGS" ]] || { echo "FAIL  reviewer-perms: $SETTINGS missing"; exit 1; }
[[ -f "$REVIEWER" ]] || { echo "FAIL  reviewer-perms: $REVIEWER missing"; exit 1; }
[[ -f "$COACH"    ]] || { echo "FAIL  reviewer-perms: $COACH missing"; exit 1; }

fail=0
if check_pair "$SETTINGS" "$REVIEWER" reviewer; then
  echo "ok    reviewer deny backstop covers every non-surface Bash allow + the toolchain floor, and leaves the review surface usable"
else
  echo "FAIL  reviewer permission drift: $REVIEWER does not neutralize $SETTINGS (or blocks the review surface)"
  fail=1
fi
if check_pair "$SETTINGS" "$COACH" coach; then
  echo "ok    design-coach deny backstop covers every non-surface Bash allow + the toolchain floor, and leaves the review surface and Write/Edit usable"
else
  echo "FAIL  reviewer permission drift: $COACH does not neutralize $SETTINGS (or blocks the coach's surface)"
  fail=1
fi
exit "$fail"
