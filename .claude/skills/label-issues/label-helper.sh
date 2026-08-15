#!/usr/bin/env bash
# label-helper.sh — the ONLY shell surface the /label-issues agentic run is
# allowed to touch.
#
# WHY THIS EXISTS (security): the labeler's claude-code-action run reads
# UNTRUSTED issue text (anyone can open or comment on an issue) while the job
# holds a provider API-key secret. Granting the agent a general shell — or the
# file-Write tool — would let prompt-injection run arbitrary commands or
# OVERWRITE THIS WRAPPER and then execute it. So the run allow-lists ONLY
# `Bash(.claude/skills/label-issues/label-helper.sh:*)` plus the read-only file
# tools (Read/Grep/Glob) — and NOT Write — so the agent cannot mutate any file,
# this script included, and can run only the fixed GitHub operations below.
# Issue bodies and comments are therefore passed INLINE (--body), never via a
# file path (no Write to author one, no arbitrary-path read to exfiltrate a
# runner file).
#
# That narrow --allowedTools is necessary but NOT sufficient on its own:
# claude-code-action loads .claude/settings.json (settingSources=project) and
# allow rules merge ADDITIVELY, so the repo's dev allows (e.g. Bash(xvfb-run:*)
# — arbitrary command execution) would otherwise leak into the run and defeat
# the list. labeler.yml closes that with the SAME deny backstop the chunker uses
# (.claude/chunker-settings.json, passed via --settings): deny beats allow from
# every source, and scripts/chunker-perms-check.sh keeps that backstop in sync
# with settings.json. This wrapper is not on settings.json's allow-list, so that
# check never has to exempt it. See docs/actions-security.md (CR-A).
#
# Keep this script side-effect-narrow: NEVER eval, never run caller input as
# code, only ever call `gh` with fixed subcommands, and pass every caller value
# as a quoted argument — never interpolated into a command line.
#
# The labeler only ADDS routing labels to issues that carry NONE of them (see
# ROUTING_LABELS); it never removes a label and never pushes code. All verbs act
# on the current repository; gh is authenticated in the action from
# GH_TOKEN/GITHUB_TOKEN. Usage:
#
#   list-untriaged [--limit <n>]   # prints "#<n> <title>" for every OPEN issue
#                                  # carrying none of the routing labels
#   read-thread    <issue>         # title, state, labels, body, and comments
#   add-label      <issue> <label>
#   ensure-label   <name> [--color <hex>] [--desc <text>]
#   comment        <issue> --body <md>
set -euo pipefail

die() { echo "label-helper: $*" >&2; exit 1; }

# Caller-supplied issue numbers must be digits only, before they reach a gh
# positional slot or a REST path (no flag-injection, no path traversal).
need_num() { case "$1" in ''|*[!0-9]*) die "$2: '$1' is not an issue number";; esac; }

# The mutually-exclusive routing labels the autonomy routines consume. An issue
# carrying ANY of these has already been triaged, so `list-untriaged` excludes
# it and the skill leaves it alone. Kept here so the exclusion query and the
# skill's taxonomy cannot drift.
ROUTING_LABELS=(autonomy-ok declined-too-big design-brief needs-decision)

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
  list-untriaged)
    limit=30
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --limit) limit="${2:?--limit needs a value}"; need_num "$limit" "list-untriaged --limit"; shift 2 ;;
        *) die "list-untriaged: unexpected argument '$1'" ;;
      esac
    done
    # Exclude every routing label with a `-label:` search qualifier, so only
    # issues carrying NONE of them come back. `gh issue list` returns issues
    # only (never PRs). Oldest-first mirrors the burn/chunker selection bias:
    # the longest-waiting untriaged issue is triaged first.
    search=""
    for l in "${ROUTING_LABELS[@]}"; do search="${search}-label:${l} "; done
    gh issue list --repo "$repo" --state open --search "$search" \
      --limit "$limit" --json number,title \
      --jq 'sort_by(.number) | .[] | "#\(.number) \(.title)"'
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

  add-label)
    n="${1:?add-label: issue number required}"; need_num "$n" add-label
    label="${2:?add-label: label required}"
    gh issue edit "$n" --repo "$repo" --add-label "$label" >/dev/null
    echo "LABELED #$n +$label"
    ;;

  ensure-label)
    name="${1:?ensure-label: label name required}"; shift
    color="ededed" desc=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --color) color="${2:?--color needs a value}"; shift 2 ;;
        --desc)  desc="${2:?--desc needs a value}"; shift 2 ;;
        *) die "ensure-label: unexpected argument '$1'" ;;
      esac
    done
    # Enumerate ALL labels (gh label list defaults to 30; a match past the first
    # 30 would else fall through to `label create` → 422 → set -e abort).
    # Capture then match (no `| grep -q` SIGPIPE under pipefail).
    existing="$(gh api --paginate "repos/$repo/labels" --jq '.[].name')"
    if grep -qxF "$name" <<<"$existing"; then
      echo "LABEL exists: $name"
    else
      # Flags first, then `--` so a name beginning with '-' can't be read as a
      # flag (the one caller value that reaches a gh positional slot).
      create_args=(label create --repo "$repo" --color "$color")
      [ -n "$desc" ] && create_args+=(--description "$desc")
      create_args+=(-- "$name")
      gh "${create_args[@]}" >/dev/null
      echo "LABEL created: $name"
    fi
    ;;

  comment)
    n="${1:?comment: issue number required}"; need_num "$n" comment; shift
    body=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --body) body="${2:?--body needs a value}"; shift 2 ;;
        *) die "comment: unexpected argument '$1'" ;;
      esac
    done
    [ -n "$body" ] || die "comment: --body required"
    gh issue comment "$n" --repo "$repo" --body "$body" >/dev/null
    echo "COMMENTED on #$n"
    ;;

  *)
    die "unknown command: '$cmd' (run with --help)"
    ;;
esac
