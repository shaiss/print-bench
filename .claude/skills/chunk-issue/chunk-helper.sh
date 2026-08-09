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
#
# That narrow --allowedTools is necessary but NOT sufficient on its own:
# claude-code-action loads .claude/settings.json (settingSources=project) and
# allow rules merge ADDITIVELY, so the repo's dev allows (e.g. Bash(xvfb-run:*)
# — arbitrary command execution) would otherwise leak into the run and defeat
# the list. The workflow closes that with a deny backstop passed via --settings
# (.claude/chunker-settings.json); deny beats allow from every source, and
# scripts/chunker-perms-check.sh keeps the backstop in sync with settings.json.
# See docs/actions-security.md (CR-A).
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

# If sub-issue linking fails AFTER the child issue was created, we must not
# leave an orphaned OPEN issue behind. A later /chunk-issue run keys "already
# chunked" on the LINKED sub-issue set (SKILL.md §0), not on an issue's mere
# existence, so an unlinked orphan is invisible to it and would be re-filed as a
# duplicate. Close the orphan (with a note) so the state is clean and the next
# run re-files exactly one set. Best-effort: never let cleanup mask the original
# failure, and never `die` from here (the caller does that).
orphan_cleanup() {
  local child="$1" parent="$2" reason="$3"
  gh issue comment "$child" --repo "$repo" --body \
"Auto-closing: created as a sub-issue of #$parent but the link could not be established ($reason). The chunker keys idempotency on linked sub-issues, so it will re-file this piece on its next run — this stray issue is safe to delete." \
    >/dev/null 2>&1 || true
  gh issue close "$child" --repo "$repo" --reason "not planned" >/dev/null 2>&1 || true
}

cmd="${1:-}"
if [ "$#" -gt 0 ]; then shift; fi

# Help must not require gh (or a repo), so handle it before resolving anything.
case "$cmd" in
  ""|-h|--help|help)
    # Print the whole leading comment block (line 2 through the last `#` line
    # before the first statement), so --help can never truncate as the header
    # grows. Skip the shebang; stop at the first non-comment line.
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
    # number — passing the number 404/422s. Every failure past this point leaves
    # a created-but-unlinked orphan, so each one closes it before dying.
    if ! child_id="$(gh api "repos/$repo/issues/$child" --jq .id)" || [ -z "$child_id" ]; then
      orphan_cleanup "$child" "$parent" "could not resolve its database id"
      die "create-child: could not resolve DB id for #$child (orphan closed)"
    fi
    if ! gh api --method POST \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "repos/$repo/issues/$parent/sub_issues" \
      -F "sub_issue_id=$child_id" >/dev/null; then
      orphan_cleanup "$child" "$parent" "sub_issues link request failed"
      die "create-child: #$child was created but the link request to #$parent failed (orphan closed)"
    fi

    # Verify the link took, failing loudly so the caller does not proceed to
    # parent cleanup on a created-but-unlinked issue. Capture first, then match:
    # piping straight into `grep -q` can SIGPIPE the paginating gh under
    # `set -o pipefail` and report a false failure.
    linked="$(gh api --paginate "repos/$repo/issues/$parent/sub_issues" --jq '.[].number')"
    if ! grep -qx "$child" <<<"$linked"; then
      orphan_cleanup "$child" "$parent" "link did not verify"
      die "create-child: #$child was created but not linked under #$parent (orphan closed)"
    fi
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

  *)
    die "unknown command: '$cmd' (run with --help)"
    ;;
esac
