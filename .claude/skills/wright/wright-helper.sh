#!/usr/bin/env bash
# wright-helper.sh — the ONLY shell surface the /wright and /reeve-signoff
# agentic runs are allowed to touch, and it is READ-ONLY.
#
# WHY THIS EXISTS (security): both halves of the agent forge read UNTRUSTED
# issue text (anyone can open or comment on an issue — Wright reads open
# issues to dedup its proposals, the sign-off reads brief bodies to judge
# them) while the job holds a provider API-key secret. Granting either agent a
# general shell — or the file-Write tool — would let prompt-injection run
# arbitrary commands or OVERWRITE THIS WRAPPER and then execute it. So each
# run allow-lists ONLY `Bash(.claude/skills/wright/wright-helper.sh:*)` plus
# the read-only file tools (Read/Grep/Glob) and its ONE write MCP tool — and
# NOT Write, NOT a general Bash. This wrapper itself performs NO write: every
# verb reads. The writes in the routine are the two MCP tools
# (wright_mcp.py's file_agent_brief, signoff_mcp.py's post_reeve_signoff),
# whose bodies travel as JSON (never a command line) and which validate their
# targets at write time.
#
# That narrow --allowedTools is necessary but NOT sufficient on its own:
# claude-code-action loads .claude/settings.json (settingSources=project) and
# allow rules merge ADDITIVELY, so the repo's dev allows (e.g. Bash(xvfb-run:*)
# — arbitrary command execution, and the sibling routines' write wrappers
# chunk-helper.sh / label-helper.sh / scout-helper.sh) would otherwise leak in
# and defeat the list. wright.yml closes that with each half's OWN deny
# backstop (.claude/wright-settings.json for propose,
# .claude/reeve-signoff-settings.json for sign-off, passed via --settings):
# deny beats allow from every source, and scripts/wright-perms-check.sh keeps
# both backstops in sync with settings.json (every Bash allow denied — the
# sibling wrappers included — and this wrapper never denied). This wrapper is
# not on settings.json's allow-list, so that check never has to exempt it.
#
# Keep this script side-effect-narrow: NEVER eval, never run caller input as
# code, only ever call `gh` with fixed READ subcommands, and pass every caller
# value as a quoted argument. All verbs act on the current repository; gh is
# authenticated in the action from GH_TOKEN/GITHUB_TOKEN. Usage:
#
#   list-briefs  [--limit <n>]   # "#<n> [labels] <title>" for every OPEN
#                                # agent-brief issue (dedup + sign-off state)
#   read-thread  <issue>         # title, state, labels, body, and comments
#   pulse                        # the two sticky ops reports (Reeve's
#                                # bench-health + the groomer report), verbatim
#   run-health   [--limit <n>]   # recent run conclusions for the scheduled
#                                # routines + the review pipeline — the live
#                                # half of the pulse (a red streak nobody has
#                                # filed is Wright's strongest signal)
set -euo pipefail

die() { echo "wright-helper: $*" >&2; exit 1; }

BRIEF_LABEL="agent-brief"

# The workflows whose run health constitutes the live pulse. Read-only: this
# lists conclusions, it never re-runs, cancels, or dispatches anything.
HEALTH_WORKFLOWS=(
  auto-review.yml
  backlog-burn.yml
  design-run.yml
  chunker.yml
  labeler.yml
  product-scout.yml
  backlog-groomer.yml
  reeve.yml
  adoption-assessor.yml
  oracle.yml
  wright.yml
)

# Caller-supplied issue numbers must be digits only, before they reach a gh
# positional slot or a REST path (no flag-injection, no path traversal).
need_num() { case "$1" in ''|*[!0-9]*) die "$2: '$1' is not an issue number";; esac; }

cmd="${1:-}"
if [ "$#" -gt 0 ]; then shift; fi

# Help must not require gh (or a repo), so handle it before resolving anything.
case "$cmd" in
  ""|-h|--help|help)
    awk 'NR==1{next} /^[^#]/{exit} {sub(/^# ?/,""); print}' "$0"
    exit 0
    ;;
esac

# Resolve the repo from the checkout so this does not depend on
# $GITHUB_REPOSITORY being set: prefer the env the action provides, else what
# gh resolves from the current checkout / GH_REPO.
repo="${GITHUB_REPOSITORY:-}"
[ -n "$repo" ] || repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
[ -n "$repo" ] || die "could not resolve repository (set GITHUB_REPOSITORY or run inside a checkout)"

# Print one sticky report issue's body by its label + body marker (the same
# belt-and-braces find the upsert steps use); says so when none exists yet.
# The marker is one of two CONSTANTS from this file (never caller input) and
# contains no quotes/backslashes, so embedding it in the jq program is safe —
# gh's --jq takes only the program string, not jq's own --arg flag.
print_sticky_report() {
  local label="$1" marker="$2" title="$3" body
  body="$(gh issue list --repo "$repo" --state open --label "$label" \
    --limit 10 --json body \
    --jq "map(select(.body | startswith(\"$marker\"))) | .[0].body // \"\"")"
  echo "== $title =="
  if [ -n "$body" ]; then
    printf '%s\n' "$body"
  else
    echo "(no sticky report issue found — the routine may not have fired yet)"
  fi
}

case "$cmd" in
  list-briefs)
    limit=50
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --limit) limit="${2:?--limit needs a value}"; need_num "$limit" "list-briefs --limit"; shift 2 ;;
        *) die "list-briefs: unexpected argument '$1'" ;;
      esac
    done
    # Every OPEN issue carrying the agent-brief label, with its labels shown
    # so the verdict state (autonomy-ok / needs-decision / wright-declined /
    # none-yet) is visible at a glance. `gh issue list` returns issues only
    # (never PRs).
    gh issue list --repo "$repo" --state open --label "$BRIEF_LABEL" \
      --limit "$limit" --json number,title,labels \
      --jq 'sort_by(.number) | .[] | "#\(.number) [\([.labels[].name] | join(","))] \(.title)"'
    ;;

  read-thread)
    n="${1:?read-thread: issue number required}"; need_num "$n" read-thread
    shift
    [ "$#" -eq 0 ] || die "read-thread: unexpected argument '$1'"
    echo "== issue #$n =="
    gh issue view "$n" --repo "$repo" --json number,title,state,labels,body \
      --template '{{.title}} ({{.state}})
labels: {{range .labels}}{{.name}} {{end}}

{{.body}}
'
    echo "== comments =="
    gh issue view "$n" --repo "$repo" --json comments \
      --template '{{range .comments}}--- {{.author.login}} @ {{.createdAt}} ---
{{.body}}

{{end}}'
    ;;

  pulse)
    [ "$#" -eq 0 ] || die "pulse: takes no arguments"
    print_sticky_report "reeve-report" "<!-- reeve-bench-health -->" "Reeve — bench health report"
    echo
    print_sticky_report "groomer-report" "<!-- backlog-groomer-report -->" "Backlog grooming report"
    ;;

  run-health)
    limit=5
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --limit) limit="${2:?--limit needs a value}"; need_num "$limit" "run-health --limit"; shift 2 ;;
        *) die "run-health: unexpected argument '$1'" ;;
      esac
    done
    # Recent conclusions per watched workflow. A workflow with no runs (or not
    # yet created) prints an empty section rather than failing the verb — the
    # pulse must degrade, not abort, when a routine is new.
    for wf in "${HEALTH_WORKFLOWS[@]}"; do
      echo "== $wf =="
      gh run list --repo "$repo" --workflow "$wf" --limit "$limit" \
        --json conclusion,event,createdAt,displayTitle \
        --jq '.[] | "\(.createdAt) \(.conclusion // "in-progress") [\(.event)] \(.displayTitle)"' \
        2>/dev/null || echo "(no runs)"
    done
    ;;

  *)
    die "unknown command: '$cmd' (run with --help)"
    ;;
esac
