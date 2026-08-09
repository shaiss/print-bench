#!/usr/bin/env bash
# chunk-helper.sh — the ONLY shell surface the /chunk-issue agentic run is
# allowed to touch.
#
# WHY THIS EXISTS (security): the chunker's claude-code-action run reads
# UNTRUSTED issue text (anyone can comment on a declined-too-big issue) while
# the job holds provider API-key secrets. Granting the agent a general shell —
# or the file-Write tool — would let prompt-injection run arbitrary commands or
# OVERWRITE THIS WRAPPER and then execute it. So the run allow-lists ONLY
# `Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)` plus the read-only file
# tools (Read/Grep/Glob) — and NOT Write — so the agent cannot mutate any file,
# this script included, and can run only the fixed GitHub operations below.
# Issue bodies are therefore passed INLINE (--body), never via a file path (no
# Write to author one, and no arbitrary-path read to exfiltrate a runner file).
# Keep this script side-effect-narrow: NEVER eval, never run caller input as
# code, only ever call `gh` with fixed subcommands, and pass every caller value
# as a quoted argument — never interpolated into a command line.
#
# All verbs act on the current repository; gh is authenticated in the action
# from GH_TOKEN/GITHUB_TOKEN. Usage:
#
#   read-thread   <issue>
#   list-children <issue>                         # prints "#<n> <title>" per child
#   create-child  --parent <n> --title <t> --body <md> [--label <l>]...
#   comment       <issue> --body <md>
#   add-label     <issue> <label>
#   remove-label  <issue> <label>
#   ensure-label  <name> [--color <hex>] [--desc <text>]
#
# create-child creates the issue, links it as a NATIVE sub-issue of <parent>
# (via the child's internal database id, not its number), applies any --label,
# verifies the link took, and prints "CREATED #<child> under #<parent>".
set -euo pipefail

die() { echo "chunk-helper: $*" >&2; exit 1; }

# Caller-supplied issue numbers must be digits only, before they reach a gh
# positional slot or a REST path (no flag-injection, no path traversal).
need_num() { case "$1" in ''|*[!0-9]*) die "$2: '$1' is not an issue number";; esac; }

cmd="${1:-}"
if [ "$#" -gt 0 ]; then shift; fi

# Help must not require gh (or a repo), so handle it before resolving anything.
case "$cmd" in
  ""|-h|--help|help)
    sed -n '2,45p' "$0" | sed 's/^# \{0,1\}//'
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

  list-children)
    n="${1:?list-children: issue number required}"; need_num "$n" list-children
    # A real API error must NOT read as "no children" — the skill's idempotency
    # check relies on this to avoid re-filing duplicates. Let gh's failure
    # propagate (set -e); an issue with no sub-issues returns an empty 200, which
    # prints nothing and exits 0.
    gh api --paginate "repos/$repo/issues/$n/sub_issues" \
      --jq '.[] | "#\(.number) \(.title)"'
    ;;

  create-child)
    parent="" title="" body=""
    labels=()
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --parent) parent="${2:?--parent needs a value}"; shift 2 ;;
        --title)  title="${2:?--title needs a value}"; shift 2 ;;
        --body)   body="${2:?--body needs a value}"; shift 2 ;;
        --label)  labels+=("${2:?--label needs a value}"); shift 2 ;;
        *) die "create-child: unexpected argument '$1'" ;;
      esac
    done
    [ -n "$parent" ] || die "create-child: --parent required"
    need_num "$parent" create-child
    [ -n "$title" ]  || die "create-child: --title required"
    [ -n "$body" ]   || die "create-child: --body required"

    create_args=(issue create --repo "$repo" --title "$title" --body "$body")
    if [ "${#labels[@]}" -gt 0 ]; then
      for l in "${labels[@]}"; do create_args+=(--label "$l"); done
    fi
    url="$(gh "${create_args[@]}")"
    child="${url##*/}"
    need_num "$child" "create-child (parsing '$url')"

    # Native sub-issue link needs the child's internal DB id (.id), NOT its
    # number — passing the number 404/422s.
    child_id="$(gh api "repos/$repo/issues/$child" --jq .id)"
    [ -n "$child_id" ] || die "create-child: could not resolve DB id for #$child"
    gh api --method POST \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "repos/$repo/issues/$parent/sub_issues" \
      -F "sub_issue_id=$child_id" >/dev/null

    # Verify the link took, failing loudly so the caller does not proceed to
    # parent cleanup on a created-but-unlinked issue. Capture first, then match:
    # piping straight into `grep -q` can SIGPIPE the paginating gh under
    # `set -o pipefail` and report a false failure.
    linked="$(gh api --paginate "repos/$repo/issues/$parent/sub_issues" --jq '.[].number')"
    grep -qx "$child" <<<"$linked" \
      || die "create-child: #$child was created but not linked under #$parent"
    echo "CREATED #$child under #$parent"
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

  add-label)
    n="${1:?add-label: issue number required}"; need_num "$n" add-label
    label="${2:?add-label: label required}"
    gh issue edit "$n" --repo "$repo" --add-label "$label" >/dev/null
    echo "LABELED #$n +$label"
    ;;

  remove-label)
    n="${1:?remove-label: issue number required}"; need_num "$n" remove-label
    label="${2:?remove-label: label required}"
    gh issue edit "$n" --repo "$repo" --remove-label "$label" >/dev/null
    echo "UNLABELED #$n -$label"
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
    # Capture then match (no `| grep -q` SIGPIPE under pipefail).
    existing="$(gh label list --repo "$repo" --json name --jq '.[].name')"
    if grep -qxF "$name" <<<"$existing"; then
      echo "LABEL exists: $name"
    else
      create_args=(label create "$name" --repo "$repo" --color "$color")
      [ -n "$desc" ] && create_args+=(--description "$desc")
      gh "${create_args[@]}" >/dev/null
      echo "LABEL created: $name"
    fi
    ;;

  *)
    die "unknown command: '$cmd' (run with --help)"
    ;;
esac
