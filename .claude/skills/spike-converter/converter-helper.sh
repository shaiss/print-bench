#!/usr/bin/env bash
# converter-helper.sh — the ONLY shell surface the /spike-converter run reads
# through: the scout-helper.sh mold stripped of every write verb (#439).
#
# WHY THIS EXISTS: the converter reshapes a decided research recommendation
# into a design-brief issue (#245 child B). The WHICH-candidate half is the
# deterministic #438 extractor (tools/brief-sources), and this wrapper is the
# one place it is invoked from — so the skill itself never picks a candidate,
# and the unattended allow-list the workflow child will need carries no bare
# `python3` (every sibling deny backstop denies it).
#
# READ-ONLY BY CONSTRUCTION (unlike the scout's wrapper, which files): this
# script has no filing verb, no label verb, no push, no edit — `gh` appears
# only as `issue list` / `issue view` (GETs), and the only other program it
# runs is the extractor, which is itself AST-proven free of network and
# writes. Filing a brief is NOT here: it goes through the scout's MCP tool
# `mcp__scout__file_design_brief` (.claude/skills/product-scout/scout-mcp.json)
# — one filing surface, one audit (#439's "do not copy the server" rule).
#
# Keep this script side-effect-narrow, the scout mold's rules: NEVER eval,
# never run caller input as code, and pass every caller value as a quoted
# argument — never interpolated into a command line. Usage:
#
#   list-briefs  [--limit <n>]     # "#<n> <title>" for every OPEN design-brief
#                                  # issue (the dedup set, as the extractor
#                                  # sees it live)
#   read-thread  <issue>           # title, state, labels, body, and comments
#   select-candidate [--root <dir>] [--open-briefs <file>]
#                                  # the #438 extract + select: prints exactly
#                                  # ONE candidate with provenance, or NONE.
#                                  # --open-briefs defaults to the LIVE list
#                                  # (fetched below); pass a fixture file for
#                                  # dry-runs. --root defaults to this repo.
set -euo pipefail

die() { echo "converter-helper: $*" >&2; exit 1; }

# Caller-supplied issue numbers must be digits only, before they reach a gh
# positional slot or a REST path (no flag-injection, no path traversal).
need_num() { case "$1" in ''|*[!0-9]*) die "$2: '$1' is not an issue number";; esac; }

cmd="${1:-}"
if [ "$#" -gt 0 ]; then shift; fi

# Help must not need gh or the repo (so resolve nothing before it).
case "$cmd" in
  ""|-h|--help|help)
    awk 'NR==1{next} /^[^#]/{exit} {sub(/^# ?/,""); print}' "$0"
    exit 0
    ;;
esac

# This repo's root: the wrapper sits at .claude/skills/spike-converter/, three
# levels down. Defaulting --root here (not to the cwd) keeps a run from any
# directory selecting against the same committed docs/ the contract names.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

# The #438 extractor, from the tree beside this wrapper — never a pip install
# and never a copy. The package is stdlib-only, so putting its src/ on
# PYTHONPATH is the whole invocation; preferring it over any installed copy
# pins the wrapper to the committed extractor it was written against.
run_extractor() {
  PYTHONPATH="$repo_root/tools/brief-sources/src${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m brief_sources "$@"
}

# The live open-brief list in the shape --open-briefs reads: one
# "<number> <title>" per line. Resolve the repo the scout's way (the env the
# action provides, else what gh resolves from the checkout) so this works both
# attended and unattended.
briefs_repo="${GITHUB_REPOSITORY:-}"
[ -n "$briefs_repo" ] || briefs_repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
[ -n "$briefs_repo" ] || die "could not resolve repository (set GITHUB_REPOSITORY or run inside a checkout)"

live_open_briefs() {
  gh issue list --repo "$briefs_repo" --state open --label design-brief \
    --limit 200 --json number,title \
    --jq 'sort_by(.number) | .[] | "#\(.number) \(.title)"'
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
    gh issue list --repo "$briefs_repo" --state open --label design-brief \
      --limit "$limit" --json number,title \
      --jq 'sort_by(.number) | .[] | "#\(.number) \(.title)"'
    ;;

  read-thread)
    n="${1:?read-thread: issue number required}"; need_num "$n" read-thread
    echo "== issue #$n =="
    gh issue view "$n" --repo "$briefs_repo" --json number,title,state,labels,body \
      --template '{{.title}} ({{.state}})
labels: {{range .labels}}{{.name}} {{end}}

{{.body}}
'
    echo "== comments =="
    gh issue view "$n" --repo "$briefs_repo" --json comments \
      --template '{{range .comments}}--- {{.author.login}} @ {{.createdAt}} ---
{{.body}}

{{end}}'
    ;;

  select-candidate)
    root="$repo_root" briefs=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --root) root="${2:?--root needs a value}"; shift 2 ;;
        --open-briefs) briefs="${2:?--open-briefs needs a value}"; shift 2 ;;
        *) die "select-candidate: unexpected argument '$1'" ;;
      esac
    done
    [ -d "$root" ] || die "select-candidate: --root '$root' is not a directory"
    # NONE is an answer, not an error — but a bare "NONE" leaves the run to
    # guess WHY. Say why with extract's own census (statuses of every candidate
    # under the root), derived rather than re-derived: the rails themselves stay
    # the extractor's, never explained by re-implementing them here. stdout
    # keeps the extractor's exact contract (NONE or the candidate); the why goes
    # to stderr so a caller parsing stdout is unaffected.
    verdict="$(if [ -n "$briefs" ]; then
        [ -f "$briefs" ] || die "select-candidate: --open-briefs '$briefs' is not a file"
        run_extractor select --root "$root" --open-briefs "$briefs"
      else
        live_open_briefs | run_extractor select --root "$root" --open-briefs -
      fi)"
    echo "$verdict"
    if [ "$verdict" = "NONE" ]; then
      census="$(run_extractor extract --root "$root" \
        | awk -F' *\\| *' '{print $1 "=" $4}' | paste -sd, - | cut -c1-400)"
      count="$(run_extractor extract --root "$root" | wc -l)"
      echo "select returned NONE: nothing decided is left to file. Rails: status=briefed" \
           "never selects; duplicate slugs collapse; an open-brief match or an existing" \
           "designs/<name>/ drops the candidate. extract saw ${count} candidate(s) under" \
           "$root: ${census:-none}" >&2
    fi
    ;;

  *)
    die "unknown command: '$cmd' (run with --help)"
    ;;
esac
