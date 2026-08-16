#!/usr/bin/env bash
# scout-helper.sh — the ONLY shell surface the /product-scout agentic run is
# allowed to touch.
#
# WHY THIS EXISTS (security): the scout's claude-code-action run reads UNTRUSTED
# issue text (anyone can open or comment on an issue — the scout reads open
# issues to dedup its proposals) while the job holds a provider API-key secret.
# Granting the agent a general shell — or the file-Write tool — would let
# prompt-injection run arbitrary commands or OVERWRITE THIS WRAPPER and then
# execute it. So the run allow-lists ONLY
# `Bash(.claude/skills/product-scout/scout-helper.sh:*)` plus the read-only file
# tools (Read/Grep/Glob) — and NOT Write — so the agent cannot mutate any file,
# this script included, and can run only the fixed GitHub operations below. Issue
# bodies are passed INLINE (--body), never via a file path (no Write to author
# one, no arbitrary-path read to exfiltrate a runner file).
#
# That narrow --allowedTools is necessary but NOT sufficient on its own:
# claude-code-action loads .claude/settings.json (settingSources=project) and
# allow rules merge ADDITIVELY, so the repo's dev allows (e.g. Bash(xvfb-run:*)
# — arbitrary command execution, the chunker's chunk-helper.sh which can create
# issues, the labeler's label-helper.sh which can APPLY routing labels) would
# otherwise leak in and defeat the list. product-scout.yml closes that with the
# scout's OWN deny backstop (.claude/scout-settings.json, passed via --settings):
# deny beats allow from every source, and scripts/scout-perms-check.sh keeps that
# backstop in sync with settings.json (every Bash allow denied, chunk-helper and
# label-helper included, and this wrapper never denied). This wrapper is not on
# settings.json's allow-list, so that check never has to exempt it.
#
# Keep this script side-effect-narrow: NEVER eval, never run caller input as
# code, only ever call `gh` with fixed subcommands, and pass every caller value
# as a quoted argument — never interpolated into a command line.
#
# AUTHORIZATION (defence in depth against prompt injection): the agent that
# drives this wrapper reads UNTRUSTED issue text, so a crafted issue could try to
# steer it into filing spam, applying an arbitrary label, or arming the burn. The
# write verbs therefore do not trust their arguments:
#   * file-brief applies ONLY the `design-brief` label (hardcoded). The scout can
#     neither invent taxonomy nor mint an `autonomy-ok` / `declined-too-big` /
#     `needs-decision` issue — arming, chunking and parking are decisions the
#     scout does not get to make.
#   * file-brief requires the `Design brief:` title prefix, so its output is
#     always recognisable as a scout proposal a human can find and cull.
#   * file-brief caps the number of briefs one run may file at $SCOUT_MAX_BRIEFS
#     (a run-scoped counter the agent cannot reach), so a prompt-injected run can
#     at worst file a BOUNDED number of design-brief proposals — noise a human
#     closes, never an escalation.
#   * ensure-label restricts the label it creates to `design-brief`.
#
# The scout only ever CREATES `design-brief` issues; it never edits an existing
# issue's labels, never removes a label, and never pushes code. All verbs act on
# the current repository; gh is authenticated in the action from
# GH_TOKEN/GITHUB_TOKEN. Usage:
#
#   list-briefs  [--limit <n>]        # "#<n> <title>" for every OPEN design-brief
#                                     # issue (dedup against these before filing)
#   read-thread  <issue>              # title, state, labels, body, and comments
#   ensure-label                      # create the `design-brief` label if missing
#   file-brief   --title <t> --body <md>   # file ONE design-brief issue
set -euo pipefail

die() { echo "scout-helper: $*" >&2; exit 1; }

# The one label the scout may ever apply or create — its entire write taxonomy.
BRIEF_LABEL="design-brief"
BRIEF_LABEL_COLOR="1D76DB"
BRIEF_LABEL_DESC="Well-formed design brief a design session can pick up cold"

# Caller-supplied issue numbers must be digits only, before they reach a gh
# positional slot or a REST path (no flag-injection, no path traversal).
need_num() { case "$1" in ''|*[!0-9]*) die "$2: '$1' is not an issue number";; esac; }

# The per-run brief cap. The workflow exports SCOUT_MAX_BRIEFS; a run-scoped
# counter file (keyed on the Actions run id so it persists across the several
# file-brief invocations of ONE run, and is fresh for the next run) tracks how
# many have been filed. The agent's only Bash surface is this wrapper and it has
# no Write tool, so it cannot set the env var or tamper with the counter.
brief_count_file() { echo "${TMPDIR:-/tmp}/scout-brief-count-${GITHUB_RUN_ID:-local}"; }

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

# Create the design-brief label if it does not exist yet. Restricted to the one
# label the scout owns — it can invent no taxonomy. Enumerate ALL labels (the
# list defaults to 30; a match past the first page would else fall through to
# `label create` → 422 → set -e abort).
ensure_brief_label() {
  local existing
  existing="$(gh api --paginate "repos/$repo/labels" --jq '.[].name')"
  if grep -qxF "$BRIEF_LABEL" <<<"$existing"; then
    return 0
  fi
  gh label create --repo "$repo" --color "$BRIEF_LABEL_COLOR" \
    --description "$BRIEF_LABEL_DESC" -- "$BRIEF_LABEL" >/dev/null
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
    # Every OPEN issue carrying the design-brief label — the set the scout must
    # dedup against so it never re-proposes an idea already queued. `gh issue
    # list` returns issues only (never PRs).
    gh issue list --repo "$repo" --state open --label "$BRIEF_LABEL" \
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

  ensure-label)
    [ "$#" -eq 0 ] || die "ensure-label: takes no arguments (it creates only '$BRIEF_LABEL')"
    ensure_brief_label
    echo "LABEL ready: $BRIEF_LABEL"
    ;;

  file-brief)
    title="" body=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --title) title="${2:?--title needs a value}"; shift 2 ;;
        --body)  body="${2:?--body needs a value}"; shift 2 ;;
        *) die "file-brief: unexpected argument '$1'" ;;
      esac
    done
    [ -n "$title" ] || die "file-brief: --title required"
    [ -n "$body" ]  || die "file-brief: --body required"
    case "$title" in
      "Design brief:"*) : ;;
      *) die "file-brief: --title must start with 'Design brief:' (got '$title')" ;;
    esac

    # Enforce the per-run cap (default 3 when the workflow set nothing). The
    # counter persists across this run's file-brief calls and refuses beyond the
    # cap — a bounded blast radius for a prompt-injected run.
    max="${SCOUT_MAX_BRIEFS:-3}"; need_num "$max" "SCOUT_MAX_BRIEFS"
    cf="$(brief_count_file)"
    count=0
    [ -f "$cf" ] && count="$(cat "$cf")"
    need_num "$count" "brief counter"
    [ "$count" -lt "$max" ] || die "per-run brief cap reached ($count/$max); refusing to file more"

    ensure_brief_label
    # Flags first, then `--` so a title/body beginning with '-' can't be read as
    # a flag. The label is hardcoded — the scout applies no other.
    url="$(gh issue create --repo "$repo" --label "$BRIEF_LABEL" \
      --title "$title" --body "$body")"
    echo "$((count + 1))" > "$cf"
    echo "FILED $url"
    ;;

  *)
    die "unknown command: '$cmd' (run with --help)"
    ;;
esac
