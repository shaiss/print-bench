#!/usr/bin/env bash
# chunk-helper.sh — the ONLY shell surface the /chunk-issue agentic run is
# allowed to touch.
#
# WHY THIS EXISTS (security): the chunker's claude-code-action run reads
# UNTRUSTED issue text (anyone can comment on a declined-too-big issue) while
# the job holds provider API-key secrets. Granting the agent unrestricted Bash
# would turn issue-comment prompt-injection into arbitrary shell / key
# exfiltration. So the workflow allow-lists ONLY
# `Bash(.claude/skills/chunk-issue/chunk-helper.sh:*)` (plus Read/Grep/Glob/Write
# for local files) — the agent can run exactly the GitHub operations below and
# nothing else. Keep this script side-effect-narrow: it must NEVER eval, never
# run caller-supplied strings as code, and only ever call `gh` with fixed
# subcommands. Every value from the agent arrives as a positional argument or a
# file path and is passed to `gh` quoted — never interpolated into a shell line.
#
# All verbs act on the current repository. gh is authenticated in the action
# from GH_TOKEN/GITHUB_TOKEN. Usage:
#
#   read-thread   <issue>
#   list-children <issue>                       # prints "#<n> <title>" per child
#   create-child  --parent <n> --title <t> --body-file <f> [--label <l>]...
#   comment       <issue> --body-file <f>
#   add-label     <issue> <label>
#   remove-label  <issue> <label>
#   ensure-label  <name> [--color <hex>] [--desc <text>]
#
# create-child creates the issue, links it as a NATIVE sub-issue of <parent>
# (via the child's internal database id, not its number), applies any --label,
# verifies the link took, and prints "CREATED #<child> under #<parent>".
set -euo pipefail

die() { echo "chunk-helper: $*" >&2; exit 1; }

cmd="${1:-}"
if [ "$#" -gt 0 ]; then shift; fi

# Help must not require gh (or a repo), so handle it before resolving anything.
case "$cmd" in
  ""|-h|--help|help)
    sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
esac

# Resolve the repo from the checkout so this does not depend on
# $GITHUB_REPOSITORY being set (CodeRabbit #150): prefer the env the action
# provides, fall back to what gh resolves from the current checkout / GH_REPO.
repo="${GITHUB_REPOSITORY:-}"
[ -n "$repo" ] || repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
[ -n "$repo" ] || die "could not resolve repository (set GITHUB_REPOSITORY or run inside a checkout)"

case "$cmd" in
  read-thread)
    n="${1:?read-thread: issue number required}"
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
    n="${1:?list-children: issue number required}"
    # No --slurp+--jq (gh rejects that combo, CodeRabbit #150): paginate and let
    # --jq stream each page. Empty / not-found is not an error here.
    gh api --paginate "repos/$repo/issues/$n/sub_issues" \
      --jq '.[] | "#\(.number) \(.title)"' 2>/dev/null || true
    ;;

  create-child)
    parent="" title="" bodyfile=""
    labels=()
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --parent)    parent="${2:?--parent needs a value}"; shift 2 ;;
        --title)     title="${2:?--title needs a value}"; shift 2 ;;
        --body-file) bodyfile="${2:?--body-file needs a value}"; shift 2 ;;
        --label)     labels+=("${2:?--label needs a value}"); shift 2 ;;
        *) die "create-child: unexpected argument '$1'" ;;
      esac
    done
    [ -n "$parent" ]   || die "create-child: --parent required"
    [ -n "$title" ]    || die "create-child: --title required"
    [ -n "$bodyfile" ] || die "create-child: --body-file required"
    [ -f "$bodyfile" ] || die "create-child: body file not found: $bodyfile"

    create_args=(issue create --repo "$repo" --title "$title" --body-file "$bodyfile")
    if [ "${#labels[@]}" -gt 0 ]; then
      for l in "${labels[@]}"; do create_args+=(--label "$l"); done
    fi
    url="$(gh "${create_args[@]}")"
    child="${url##*/}"
    case "$child" in
      ''|*[!0-9]*) die "create-child: could not parse new issue number from '$url'" ;;
    esac

    # Native sub-issue link needs the child's internal DB id (.id), NOT its
    # number — passing the number 404/422s (CodeRabbit #150).
    child_id="$(gh api "repos/$repo/issues/$child" --jq .id)"
    [ -n "$child_id" ] || die "create-child: could not resolve DB id for #$child"
    gh api --method POST \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "repos/$repo/issues/$parent/sub_issues" \
      -F "sub_issue_id=$child_id" >/dev/null

    # Verify the link actually took; fail loudly so the caller does not proceed
    # to parent cleanup on a created-but-unlinked issue (CodeRabbit #150).
    if ! gh api --paginate "repos/$repo/issues/$parent/sub_issues" --jq '.[].number' \
         | grep -qx "$child"; then
      die "create-child: #$child was created but not linked under #$parent"
    fi
    echo "CREATED #$child under #$parent"
    ;;

  comment)
    n="${1:?comment: issue number required}"; shift || true
    bodyfile=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --body-file) bodyfile="${2:?--body-file needs a value}"; shift 2 ;;
        *) die "comment: unexpected argument '$1'" ;;
      esac
    done
    [ -n "$bodyfile" ] || die "comment: --body-file required"
    [ -f "$bodyfile" ] || die "comment: body file not found: $bodyfile"
    gh issue comment "$n" --repo "$repo" --body-file "$bodyfile" >/dev/null
    echo "COMMENTED on #$n"
    ;;

  add-label)
    n="${1:?add-label: issue number required}"
    label="${2:?add-label: label required}"
    gh issue edit "$n" --repo "$repo" --add-label "$label" >/dev/null
    echo "LABELED #$n +$label"
    ;;

  remove-label)
    n="${1:?remove-label: issue number required}"
    label="${2:?remove-label: label required}"
    gh issue edit "$n" --repo "$repo" --remove-label "$label" >/dev/null
    echo "UNLABELED #$n -$label"
    ;;

  ensure-label)
    name="${1:?ensure-label: label name required}"; shift || true
    color="ededed" desc=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --color) color="${2:?--color needs a value}"; shift 2 ;;
        --desc)  desc="${2:?--desc needs a value}"; shift 2 ;;
        *) die "ensure-label: unexpected argument '$1'" ;;
      esac
    done
    if gh label list --repo "$repo" --json name --jq '.[].name' | grep -qxF "$name"; then
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
