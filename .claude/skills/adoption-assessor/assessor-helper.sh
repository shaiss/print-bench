#!/usr/bin/env bash
# assessor-helper.sh — the ONLY shell surface the /adoption-assessor agentic run
# is allowed to touch, and it is READ-ONLY.
#
# WHY THIS EXISTS (security): the assessor's claude-code-action run reads
# UNTRUSTED issue text (a vendor — anyone — opens the adoption-study issue and
# writes its body) while the job holds a provider API-key secret. Granting the
# agent a general shell — or the file-Write tool — would let prompt-injection run
# arbitrary commands or OVERWRITE THIS WRAPPER and then execute it. So the run
# allow-lists ONLY `Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*)`
# plus the read-only file tools (Read/Grep/Glob) and the ONE write MCP tool
# (mcp__assessor__post_adoption_disposition) — and NOT Write, NOT a general Bash.
# This wrapper itself performs NO write: its only verbs read issues. The single
# write in the whole routine is the MCP tool, whose body travels as JSON (never a
# command line) and which validates its target at write time.
#
# That narrow --allowedTools is necessary but NOT sufficient on its own:
# claude-code-action loads .claude/settings.json (settingSources=project) and
# allow rules merge ADDITIVELY, so the repo's dev allows (e.g. Bash(xvfb-run:*) —
# arbitrary command execution, and the sibling routines' write wrappers
# chunk-helper.sh / label-helper.sh / scout-helper.sh) would otherwise leak in and
# defeat the list. adoption-assessor.yml closes that with the assessor's OWN deny
# backstop (.claude/adoption-assessor-settings.json, passed via --settings): deny
# beats allow from every source, and scripts/adoption-assessor-perms-check.sh
# keeps that backstop in sync with settings.json (every Bash allow denied — all
# three sibling wrappers included — and this wrapper never denied). This wrapper
# is not on settings.json's allow-list, so that check never has to exempt it.
#
# Keep this script side-effect-narrow: NEVER eval, never run caller input as
# code, only ever call `gh` with fixed READ subcommands, and pass every caller
# value as a quoted argument. All verbs act on the current repository; gh is
# authenticated in the action from GH_TOKEN/GITHUB_TOKEN. Usage:
#
#   list-awaiting [--limit <n>]   # "#<n> <title>" for every OPEN adoption-study
#                                 # issue with no disposition:* label — the studies
#                                 # awaiting a verdict (the assessor's work-list)
#   read-thread   <issue>         # title, state, labels, body, and comments
set -euo pipefail

die() { echo "assessor-helper: $*" >&2; exit 1; }

STUDY_LABEL="adoption-study"

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
# $GITHUB_REPOSITORY being set: prefer the env the action provides, else what gh
# resolves from the current checkout / GH_REPO.
repo="${GITHUB_REPOSITORY:-}"
[ -n "$repo" ] || repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
[ -n "$repo" ] || die "could not resolve repository (set GITHUB_REPOSITORY or run inside a checkout)"

case "$cmd" in
  list-awaiting)
    limit=50
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --limit) limit="${2:?--limit needs a value}"; need_num "$limit" "list-awaiting --limit"; shift 2 ;;
        *) die "list-awaiting: unexpected argument '$1'" ;;
      esac
    done
    # Every OPEN adoption-study issue that has no disposition:* label yet — the
    # studies awaiting a verdict. Filter by the LABEL SET (any label starting
    # `disposition:`), not the two known names, so a future disposition label is
    # excluded too. `gh issue list` returns issues only (never PRs).
    gh issue list --repo "$repo" --state open --label "$STUDY_LABEL" \
      --limit "$limit" --json number,title,labels \
      --jq 'sort_by(.number) | .[]
            | select([.labels[].name | startswith("disposition:")] | any | not)
            | "#\(.number) \(.title)"'
    ;;

  read-thread)
    n="${1:?read-thread: issue number required}"; need_num "$n" read-thread
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

  *)
    die "unknown command: '$cmd' (run with --help)"
    ;;
esac
