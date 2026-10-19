#!/usr/bin/env bash
# Push a design-run's local branch and open its draft PR, then comment.
#
# design-run.yml's agent step is claude-code-action. That action exits 0
# whenever the model ends its turn without an API error, whether or not a
# branch was pushed (issue #538). On 2026-10-19 the nuggs-ladder brief (#853)
# was claimed three times; the third run posted "gates green" and stopped
# while the runner still held the tree. Nothing in the workflow pushed that
# tree, so lock cleanup correctly scored the run dead and withdrew the
# SHIP-LOCK. Gate success is not delivery.
#
# This step runs in the same job, after the agent and before lock cleanup:
#   1. Only a branch named claude/issue-<N>-* is eligible. main is never
#      pushed.
#   2. Uncommitted files under designs/ and first-party lib/ are committed
#      onto that branch. Vendored trees, scripts/, and .github/ are not.
#   3. The branch is pushed and `git ls-remote` must return the local tip.
#   4. An open PR from that head whose body closes #<N> must exist (this
#      step opens a draft one when it does not).
#   5. Only then is the success comment posted. A failed push or a missing
#      PR posts nothing that reads as success.
#
# Usage:
#   scripts/design-run-deliver.sh --repo <owner/name> --issue <N> \
#       --base <sha> --base-branch <name> --run-url <url> \
#       [--push-url <url>]
#   scripts/design-run-deliver.sh --selftest
#
# Live mode needs GH_TOKEN to push and to open the PR (the design-run PAT,
# so the draft triggers CI). COMMENT_TOKEN, when set, is the token for the
# success comment; unset, the comment uses GH_TOKEN. Appends `delivered=`
# to $GITHUB_OUTPUT when that is set. Exit 0 when there is nothing to
# deliver or delivery verified; exit 1 when a delivery was required and
# verification failed; exit 2 on usage.
set -euo pipefail

SELF="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)/$(basename "$0")"
cd "$(dirname "$0")/.."
# Selftest points this at a throwaway worktree. Live runs stay in the repo.
if [ -n "${DELIVER_WORKTREE:-}" ]; then
  cd "$DELIVER_WORKTREE"
fi

DELIVERED_LINE='🚢 design-run delivered — branch and draft PR verified'

usage() {
  [ $# -eq 0 ] || echo "design-run-deliver: $*" >&2
  cat >&2 <<'EOF'
usage: scripts/design-run-deliver.sh --repo <owner/name> --issue <N>
           --base <sha> --base-branch <name> --run-url <url>
           [--push-url <url>]
       scripts/design-run-deliver.sh --selftest
EOF
  exit 2
}

command -v jq >/dev/null 2>&1 || {
  echo "design-run-deliver: jq is required" >&2
  exit 1
}

emit() {
  if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "$1=$2" >> "$GITHUB_OUTPUT"; fi
}

note() {
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then echo "$1" >> "$GITHUB_STEP_SUMMARY"; fi
  echo "design-run-deliver: $1" >&2
}

# $1 body, $2 issue number. GitHub's nine closing keywords, the same
# boundary routine-lock-cleanup.sh uses so "#9" does not match "#95".
closes_issue() {
  printf '%s\n' "$1" | grep -qiP "\\b(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved):?\\s+#${2}\\b"
}

# Paths the delivery commit may include. Vendored trees and anything
# outside the design stay on the runner.
safe_path() {
  case "$1" in
    designs/*) return 0 ;;
    lib/BOSL2/*|lib/NopSCADlib/*) return 1 ;;
    lib/*) return 0 ;;
    *) return 1 ;;
  esac
}

# Print porcelain paths eligible for the delivery commit, one per line.
# A rename line ("old -> new") is skipped rather than guessed.
safe_dirty_paths() {
  local line path
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    path="${line:3}"
    case "$path" in
      *" -> "*)
        echo "design-run-deliver: skipping rename line, not guessing a path: $path" >&2
        continue
        ;;
    esac
    if safe_path "$path"; then
      printf '%s\n' "$path"
    fi
  done < <(git status --porcelain)
}

git_authed() {
  if [[ "$PUSH_URL" == https://* ]]; then
    GIT_ASKPASS="$ASKPASS" GIT_TERMINAL_PROMPT=0 \
      git -c credential.helper= "$@"
  else
    git "$@"
  fi
}

write_askpass() {
  ASKPASS="$(mktemp)"
  cat > "$ASKPASS" <<'EOF'
#!/bin/sh
case "$1" in
  *Username*) printf '%s\n' 'x-access-token' ;;
  *) printf '%s\n' "$DELIVER_GH_TOKEN" ;;
esac
EOF
  chmod 700 "$ASKPASS"
}

# Commit eligible dirty files onto the current branch. No-op when none.
commit_safe_dirty() {
  local paths path
  paths="$(safe_dirty_paths)"
  [ -n "$paths" ] || return 0
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    git add -- "$path"
  done <<<"$paths"
  git -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
      -c user.name="github-actions[bot]" \
      commit -m "Design for #${ISSUE}"
  note "committed uncommitted design files onto ${BRANCH} before push"
}

# Remote tip must be this checkout's HEAD. Push when it is not.
verify_remote_tip() {
  local head remote
  head="$(git rev-parse HEAD)"
  remote="$(git_authed ls-remote "$PUSH_URL" "refs/heads/${BRANCH}" | awk 'NR==1{print $1}')"
  if [ "$remote" = "$head" ]; then
    note "remote ${BRANCH} already at ${head}"
    return 0
  fi
  if ! git_authed push "$PUSH_URL" "HEAD:refs/heads/${BRANCH}"; then
    note "push of ${BRANCH} failed — not opening a PR and not posting success"
    return 1
  fi
  remote="$(git_authed ls-remote "$PUSH_URL" "refs/heads/${BRANCH}" | awk 'NR==1{print $1}')"
  if [ "$remote" != "$head" ]; then
    note "ls-remote for ${BRANCH} returned '${remote:-empty}', local tip is ${head} — not posting success"
    return 1
  fi
  note "verified remote ${BRANCH} at ${head}"
  return 0
}

# Print the URL of an open PR from BRANCH whose body closes ISSUE, or
# nothing. Creates a draft when no such PR exists.
ensure_pr() {
  local json url body
  json="$(gh pr list --repo "$REPO" --head "$BRANCH" --state open \
    --json number,url,body)"
  url="$(printf '%s\n' "$json" | jq -r --arg n "$ISSUE" '
    def closes($b):
      ["close","closes","closed","fix","fixes","fixed",
       "resolve","resolves","resolved"]
      | any(. as $kw
            | ($b // "") | test("\\b" + $kw + ":?\\s+#" + $n + "\\b"; "i"));
    ([.[] | select(closes(.body))][0].url) // empty
  ')"
  if [ -n "$url" ]; then
    printf '%s\n' "$url"
    return 0
  fi
  local bodyfile title
  bodyfile="$(mktemp)"
  cat > "$bodyfile" <<EOF
Closes #${ISSUE}

Draft opened by the design-run delivery step after it verified \`${BRANCH}\` on the remote. The agent run ended without opening a PR; the gate evidence is the commits on this branch.
EOF
  title="$(git log -1 --format=%s)"
  title="${title:-Design for #${ISSUE}}"
  if ! gh pr create --repo "$REPO" --base "$BASE_BRANCH" --head "$BRANCH" \
      --draft --title "$title" --body-file "$bodyfile" >/dev/null; then
    note "gh pr create failed for ${BRANCH} — not posting success"
    return 1
  fi
  json="$(gh pr list --repo "$REPO" --head "$BRANCH" --state open \
    --json number,url,body)"
  url="$(printf '%s\n' "$json" | jq -r --arg n "$ISSUE" '
    def closes($b):
      ["close","closes","closed","fix","fixes","fixed",
       "resolve","resolves","resolved"]
      | any(. as $kw
            | ($b // "") | test("\\b" + $kw + ":?\\s+#" + $n + "\\b"; "i"));
    ([.[] | select(closes(.body))][0].url) // empty
  ')"
  if [ -z "$url" ]; then
    note "no open PR from ${BRANCH} closes #${ISSUE} after gh pr create — not posting success"
    return 1
  fi
  # The URL we are about to treat as verified must actually close the issue.
  body="$(printf '%s\n' "$json" | jq -r --arg u "$url" '.[] | select(.url==$u) | .body')"
  if ! closes_issue "$body" "$ISSUE"; then
    note "PR ${url} body does not close #${ISSUE} — not posting success"
    return 1
  fi
  printf '%s\n' "$url"
}

already_delivered_comment() {
  # gh --paginate runs --jq once per page, so sum the page counts. The
  # prefix is interpolated as a jq string (jq -Rn) because `gh api --jq`
  # has no --arg.
  local prefix_json n
  prefix_json="$(jq -Rn --arg p "$DELIVERED_LINE" '$p')"
  n="$(gh api --paginate "repos/${REPO}/issues/${ISSUE}/comments" \
    --jq "([.[] | (.body // \"\") | split(\"\\n\") | map(gsub(\"^[[:space:]]+|[[:space:]]+$\"; \"\")) | map(select(length>0)) | (.[0] // \"\") | select(startswith(${prefix_json}))] | length)" \
    | awk '{s+=$1} END {print s+0}')"
  [ "$n" -gt 0 ]
}

post_success() {  # $1 pr url, $2 sha
  local token body
  token="${COMMENT_TOKEN:-${GH_TOKEN}}"
  body="$(printf '%s\n\n- branch: `%s` (`%s`)\n- pull request: %s\n- run: %s\n\n`git ls-remote` matches the local tip and an open pull request from that branch closes this issue. This comment is posted only after both checks.' \
    "$DELIVERED_LINE" "$BRANCH" "$2" "$1" "$RUN_URL")"
  GH_TOKEN="$token" gh api --method POST "repos/${REPO}/issues/${ISSUE}/comments" -f body="$body" >/dev/null
}

finish() {  # delivered summary
  emit delivered "$1"
  note "$2"
  exit 0
}

run_live() {
  local ahead head_sha pr_url
  if ! [[ "$ISSUE" =~ ^[0-9]+$ ]]; then
    echo "design-run-deliver: issue must be numeric, got '${ISSUE}'" >&2
    exit 2
  fi
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  if ! [[ "$BRANCH" =~ ^claude/issue-${ISSUE}- ]]; then
    finish false "HEAD is '${BRANCH}', not claude/issue-${ISSUE}-* — nothing pushed"
  fi
  commit_safe_dirty
  if ! git cat-file -e "${BASE}^{commit}" 2>/dev/null; then
    echo "design-run-deliver: base ${BASE} is not a commit in this checkout" >&2
    exit 1
  fi
  ahead="$(git rev-list --count "${BASE}..HEAD")"
  if [ "$ahead" -eq 0 ]; then
    finish false "HEAD has no commits ahead of ${BASE} — nothing pushed"
  fi
  if [ -z "${GH_TOKEN:-}" ]; then
    echo "design-run-deliver: GH_TOKEN is required to push ${BRANCH}" >&2
    exit 1
  fi
  export DELIVER_GH_TOKEN="$GH_TOKEN"
  if [[ "$PUSH_URL" == https://* ]]; then
    write_askpass
  fi
  if ! verify_remote_tip; then
    emit delivered false
    exit 1
  fi
  if ! pr_url="$(ensure_pr)"; then
    emit delivered false
    exit 1
  fi
  head_sha="$(git rev-parse HEAD)"
  if already_delivered_comment; then
    finish true "delivery already recorded for ${BRANCH} (${pr_url})"
  fi
  # The branch and PR are the delivery. A comment-POST failure must not turn
  # a verified delivery into a red job (the red gate keys off the branch).
  if ! post_success "$pr_url" "$head_sha"; then
    note "verified ${BRANCH} at ${pr_url} but the success comment failed to post"
  fi
  finish true "delivered ${BRANCH} as ${pr_url}"
}

selftest() {
  local tmp root bare base
  tmp="$(mktemp -d)"
  root="${tmp}/repo"
  bare="${tmp}/bare.git"
  mkdir -p "$root/designs/nuggs-ladder" "$root/scripts"
  git -C "$root" init -b main >/dev/null
  git -C "$root" -c user.email=t@example.com -c user.name=t commit --allow-empty -m base >/dev/null
  base="$(git -C "$root" rev-parse HEAD)"
  git -C "$root" checkout -b claude/issue-853-nuggs-ladder >/dev/null
  printf 'x\n' > "$root/designs/nuggs-ladder/nuggs-ladder.scad"
  printf 'nope\n' > "$root/scripts/evil.sh"
  git -C "$root" init --bare "$bare" >/dev/null

  # Fake gh: records invocations and serves the PR the create call wrote.
  mkdir -p "${tmp}/bin"
  cat > "${tmp}/bin/gh" <<EOF
#!/bin/sh
printf '%s\n' "\$*" >> "${tmp}/gh.log"
if [ "\$1" = "pr" ] && [ "\$2" = "list" ]; then
  if [ -f "${tmp}/pr.json" ]; then cat "${tmp}/pr.json"; else printf '%s\n' '[]'; fi
  exit 0
fi
if [ "\$1" = "pr" ] && [ "\$2" = "create" ]; then
  if [ "\${FAIL_PR_CREATE:-}" = "1" ]; then
    echo "pr create refused" >&2
    exit 1
  fi
  cat > "${tmp}/pr.json" <<'JSON'
[{"number":99,"url":"https://github.com/acme/print-bench/pull/99","body":"Closes #853\n\nDraft opened by the design-run delivery step.\n"}]
JSON
  printf '%s\n' 'https://github.com/acme/print-bench/pull/99'
  exit 0
fi
if [ "\$1" = "api" ]; then
  # Comment GET (paginate) returns prior bodies; POST records the body.
  for arg in "\$@"; do
    case "\$arg" in
      --method) posting=1 ;;
      body=*) printf '%s\n' "\${arg#body=}" > "${tmp}/comment.body" ;;
    esac
  done
  if [ -n "\${posting:-}" ]; then
    printf '%s\n' '{"id":1}'
    exit 0
  fi
  # --jq path: one count per page, 1 when a prior success comment exists.
  if printf '%s\n' "\$*" | grep -q -- '--jq'; then
    if [ -f "${tmp}/comment.body" ] && head -n 1 "${tmp}/comment.body" | grep -q 'design-run delivered'; then
      printf '%s\n' 1
    else
      printf '%s\n' 0
    fi
    exit 0
  fi
  exit 0
fi
echo "unexpected gh \$*" >&2
exit 1
EOF
  chmod +x "${tmp}/bin/gh"

  run_case() {  # name, expect exit, keep|fresh, then a command prefix
    local name="$1" expect="$2" keep="$3"
    shift 3
    rm -f "${tmp}/gh.log"
    if [ "$keep" != "keep" ]; then
      rm -f "${tmp}/comment.body" "${tmp}/pr.json"
    fi
    set +e
    env PATH="${tmp}/bin:${PATH}" GH_TOKEN=test-token COMMENT_TOKEN=comment-token \
      DELIVER_WORKTREE="$root" \
      "$@" "$SELF" --repo acme/print-bench --issue 853 --base "$base" \
      --base-branch main --run-url https://example.test/run/1 --push-url "$bare"
    local rc=$?
    set -e
    if [ "$rc" -ne "$expect" ]; then
      echo "selftest: ${name} exited ${rc}, expected ${expect}" >&2
      exit 1
    fi
  }

  # Happy path: dirty design is committed and pushed; the evil script is
  # not; the success comment exists and names the verified PR; gh.log shows
  # the PR create before the comment POST.
  run_case happy 0 fresh
  git --git-dir="$bare" rev-parse refs/heads/claude/issue-853-nuggs-ladder >/dev/null
  git --git-dir="$bare" grep -q nope refs/heads/claude/issue-853-nuggs-ladder && {
    echo "selftest: scripts/evil.sh was pushed" >&2
    exit 1
  }
  git --git-dir="$bare" grep -q x refs/heads/claude/issue-853-nuggs-ladder:designs/nuggs-ladder/nuggs-ladder.scad
  grep -q 'design-run delivered' "${tmp}/comment.body"
  grep -q 'https://github.com/acme/print-bench/pull/99' "${tmp}/comment.body"
  create_line="$(grep -n 'pr create' "${tmp}/gh.log" | head -1 | cut -d: -f1)"
  comment_line="$(grep -n 'api --method POST' "${tmp}/gh.log" | head -1 | cut -d: -f1)"
  [ -n "$create_line" ] && [ -n "$comment_line" ] && [ "$comment_line" -gt "$create_line" ] || {
    echo "selftest: success comment was not after pr create" >&2
    echo "gh.log:" >&2
    cat "${tmp}/gh.log" >&2
    exit 1
  }

  # Second run verifies the existing tip and does not post again.
  run_case idempotent 0 keep
  if grep -q 'api --method POST' "${tmp}/gh.log"; then
    echo "selftest: idempotent rerun posted a second success comment" >&2
    exit 1
  fi

  # Push failure: no PR create, no success comment, non-zero exit.
  rm -rf "$bare"
  mkdir -p "$bare"
  run_case 'push failure' 1 fresh
  if [ -f "${tmp}/comment.body" ] || { [ -f "${tmp}/gh.log" ] && grep -q 'pr create' "${tmp}/gh.log"; }; then
    echo "selftest: push failure still created a PR or posted success" >&2
    exit 1
  fi

  # PR create failure after a good push: no success comment.
  rm -rf "$bare"
  git -C "$root" init --bare "$bare" >/dev/null
  run_case 'pr create failure' 1 fresh env FAIL_PR_CREATE=1
  if [ -f "${tmp}/comment.body" ]; then
    echo "selftest: failed pr create still posted success" >&2
    exit 1
  fi

  # Wrong branch name: dirty design on main is not committed or pushed.
  git -C "$root" checkout main >/dev/null
  mkdir -p "$root/designs/nuggs-ladder"
  printf 'y\n' > "$root/designs/nuggs-ladder/other.scad"
  run_case 'not the issue branch' 0 fresh
  if git --git-dir="$bare" rev-parse refs/heads/main >/dev/null 2>&1; then
    echo "selftest: pushed main" >&2
    exit 1
  fi
  if [ -f "${tmp}/comment.body" ]; then
    echo "selftest: wrong branch posted success" >&2
    exit 1
  fi

  echo "design-run-deliver selftest: ok"
}

REPO="" ISSUE="" BASE="" BASE_BRANCH="" RUN_URL="" PUSH_URL="" BRANCH="" ASKPASS=""

if [ "${1:-}" = "--selftest" ]; then
  selftest
  exit 0
fi

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    --issue) ISSUE="${2:-}"; shift 2 ;;
    --base) BASE="${2:-}"; shift 2 ;;
    --base-branch) BASE_BRANCH="${2:-}"; shift 2 ;;
    --run-url) RUN_URL="${2:-}"; shift 2 ;;
    --push-url) PUSH_URL="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) usage "unknown argument: $1" ;;
  esac
done

[ -n "$REPO" ] && [ -n "$ISSUE" ] && [ -n "$BASE" ] && [ -n "$BASE_BRANCH" ] && [ -n "$RUN_URL" ] \
  || usage "missing required argument"
[ -z "$PUSH_URL" ] && PUSH_URL="https://github.com/${REPO}.git"

run_live
