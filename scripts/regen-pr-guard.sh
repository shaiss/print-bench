#!/usr/bin/env bash
# regen-pr-guard.sh — whether a pull request's human-authored diff (vs its base,
# excluding regen bot commit-backs) touches designs/.
#
#   ./scripts/regen-pr-guard.sh pr-author-touches-designs --base <sha> --head <sha>
#       Exit 0 when at least one non-regen commit on the first-parent line from
#       merge-base(base, head)..head changes a path under designs/; exit 1 when
#       none do; exit 2 on usage or git errors.
#
#   ./scripts/regen-pr-guard.sh --selftest
#
# CI's regen job uses this on pull_request events: lib-only PRs still regenerate
# locally for downstream gates, but do not receive a commit-back that only
# re-stamps previews (which would pollute the PR diff and re-open design review).
#
# Regen bot identity matches scripts/reviewer-signoff.sh (drift-pinned to ci.yml).
set -euo pipefail

REGEN_SUBJECT="CI: regenerate previews and product pages"
REGEN_AUTHOR="41898282+github-actions[bot]@users.noreply.github.com"

_is_regen_bot_commit() {
  local c="$1"
  [[ "$(git log -1 --format=%s "$c" 2>/dev/null || true)" == "$REGEN_SUBJECT" ]] \
    && [[ "$(git log -1 --format=%ae "$c" 2>/dev/null || true)" == "$REGEN_AUTHOR" ]]
}

# _path_under_designs PATH — 0 when PATH is under designs/
_path_under_designs() {
  [[ "$1" == designs/* ]]
}

# pr_author_touches_designs BASE HEAD — exit 0/1/2 (see header).
pr_author_touches_designs() {
  local base="${1:-}" head="${2:-}" mb c p
  if [[ -z "$base" || -z "$head" ]]; then
    echo "regen-pr-guard: pr-author-touches-designs needs --base and --head" >&2
    return 2
  fi
  git rev-parse --verify --quiet "${base}^{commit}" >/dev/null \
    || { echo "regen-pr-guard: --base '$base' is not a commit" >&2; return 2; }
  git rev-parse --verify --quiet "${head}^{commit}" >/dev/null \
    || { echo "regen-pr-guard: --head '$head' is not a commit" >&2; return 2; }

  mb="$(git merge-base "$base" "$head" 2>/dev/null)" || {
    echo "regen-pr-guard: cannot merge-base $base and $head" >&2
    return 2
  }

  while IFS= read -r c; do
    [[ -n "$c" ]] || continue
    if _is_regen_bot_commit "$c"; then
      continue
    fi
    while IFS= read -r p; do
      [[ -n "$p" ]] || continue
      if _path_under_designs "$p"; then
        return 0
      fi
    done < <(git diff-tree --no-commit-id --name-only -r --no-renames "$c" 2>/dev/null) \
      || { echo "regen-pr-guard: cannot read commit $c" >&2; return 2; }
  done < <(git rev-list --first-parent "$mb".."$head" 2>/dev/null) \
    || { echo "regen-pr-guard: cannot list commits $mb..$head" >&2; return 2; }

  return 1
}

selftest() {
  local pass=1 t r
  ok() { echo "selftest ok    $1"; }
  bad() { echo "SELFTEST FAIL  $1: $2"; pass=0; }

  as_bot() {
    GIT_AUTHOR_NAME='github-actions[bot]' \
    GIT_AUTHOR_EMAIL="$REGEN_AUTHOR" \
    GIT_COMMITTER_NAME='github-actions[bot]' \
    GIT_COMMITTER_EMAIL="$REGEN_AUTHOR" \
      git -C "$r" "$@"
  }
  human() {
    GIT_AUTHOR_NAME='human' GIT_AUTHOR_EMAIL='human@example.com' \
    GIT_COMMITTER_NAME='human' GIT_COMMITTER_EMAIL='human@example.com' \
      git -C "$r" "$@"
  }

  t="$(mktemp -d)"
  r="$t/repo"
  mkdir -p "$r"
  (
    set -e
    git -C "$r" init -q
    git -C "$r" config user.email 'human@example.com'
    git -C "$r" config user.name 'human'
    mkdir -p "$r/lib" "$r/designs/foo/previews"
    echo 'v0' > "$r/lib/x.scad"
    human add -A && human commit -qam 'lib only'
    git -C "$r" tag base-tip
    echo 'v1' > "$r/lib/x.scad"
    human add -A && human commit -qam 'lib bump'
    git -C "$r" tag lib-only-head
    mkdir -p "$r/designs/bar/previews"
    echo 'stamp' > "$r/designs/bar/previews/.regen-stamp"
    as_bot add -A && as_bot commit -qam "$REGEN_SUBJECT"
    git -C "$r" tag lib-then-bot
    echo 'v0' > "$r/designs/foo/foo.scad"
    human add -A && human commit -qam 'add design'
    git -C "$r" tag design-head
    echo 'stamp2' > "$r/designs/foo/previews/.regen-stamp"
    as_bot add -A && as_bot commit -qam "$REGEN_SUBJECT"
    git -C "$r" tag design-then-bot
  ) >/dev/null 2>&1 || { bad 'fixture' 'could not build throwaway repo'; rm -rf "$t"; return 1; }

  run_case() {
    local label="$1" base_ref="$2" head_ref="$3" want="$4"
    local base head rc=0
    base="$(git -C "$r" rev-parse "$base_ref")" \
      || { bad "$label" "unknown ref $base_ref"; return; }
    head="$(git -C "$r" rev-parse "$head_ref")" \
      || { bad "$label" "unknown ref $head_ref"; return; }
    ( cd "$r" && pr_author_touches_designs "$base" "$head" ) >/dev/null || rc=$?
    if [[ "$rc" -eq "$want" ]]; then
      ok "$label (exit $want)"
    else
      bad "$label" "expected exit $want, got $rc"
    fi
  }

  run_case 'lib-only PR' base-tip lib-only-head 1
  run_case 'design PR' base-tip design-head 0
  run_case 'lib then bot regen on top' base-tip lib-then-bot 1
  run_case 'design then bot regen on top' base-tip design-then-bot 0
  run_case 'NEGCTL bot-only since lib-only' lib-only-head lib-then-bot 1

  # Drift pin: ci.yml must invoke this guard before commit-push on PRs.
  local ci
  ci="$(dirname "$0")/../.github/workflows/ci.yml"
  if [[ ! -f "$ci" ]]; then
    bad 'regen-drift' "$ci not found"
  elif grep -qF 'regen-pr-guard.sh pr-author-touches-designs' "$ci"; then
    ok 'regen-drift ci.yml calls pr-author-touches-designs'
  else
    bad 'regen-drift' 'ci.yml no longer calls regen-pr-guard.sh pr-author-touches-designs'
  fi

  rm -rf "$t"
  if [[ "$pass" -eq 0 ]]; then
    echo "regen-pr-guard selftest: failed" >&2
    return 1
  fi
  echo "regen-pr-guard selftest: all cases passed"
}

usage() {
  echo "usage: $0 pr-author-touches-designs --base <sha> --head <sha>" >&2
  echo "       $0 --selftest" >&2
  exit 2
}

main() {
  case "${1:-}" in
    --selftest) selftest ;;
    pr-author-touches-designs)
      shift
      local base="" head=""
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --base) base="${2:-}"; shift 2 ;;
          --head) head="${2:-}"; shift 2 ;;
          *) usage ;;
        esac
      done
      pr_author_touches_designs "$base" "$head"
      ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
}

main "$@"
