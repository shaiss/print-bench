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
# This step runs in the same job, after the agent and before lock cleanup.
# The workflow restores THIS file from the pinned start commit into
# $RUNNER_TEMP and executes that copy — the worktree copy is untrusted
# after bypassPermissions. Then:
#   1. Only a branch named claude/issue-<N>-* is eligible. main is never
#      pushed.
#   2. Uncommitted files under designs/ and first-party lib/ are committed
#      onto that branch. Vendored trees, scripts/, .github/, .claude/ and
#      tools/ are not.
#   3. Any commit since the job's start SHA that touches .github/, scripts/,
#      .claude/ or tools/ — including a path added and later deleted, or the
#      pre-image of a rename — refuses the push.
#   4. An open non-draft PR on the branch refuses the push. auto-arm.yml
#      arms auto-merge on non-draft claude/* PRs.
#   5. The branch is pushed and `git ls-remote` must return the local tip.
#   6. An open same-repo draft PR whose headRefOid is that tip and whose
#      body closes #<N> must exist (this step opens a draft when none does).
#   7. Only then is the success comment posted. A failed push or a PR that
#      does not qualify posts nothing that reads as success.
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
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# Selftest points this at a throwaway worktree. Live runs stay in the repo.
if [ -n "${DELIVER_WORKTREE:-}" ]; then
  cd "$DELIVER_WORKTREE"
fi

DELIVERED_LINE='🚢 design-run delivered — branch and draft PR verified'
PR_FIELDS='number,url,body,isDraft,headRefOid,isCrossRepository,headRepositoryOwner,headRepository'

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

# Every git invocation in this file goes through git_cmd.
#
# -c core.hooksPath=/dev/null is placed AFTER any caller -c, so a caller
# cannot turn hooks back on. --no-verify is passed only to the subcommands
# that accept it (commit, push, merge, rebase, am). status, diff, config,
# log, ls-remote, add, rev-list, cat-file and show exit 129 or 128 when
# given --no-verify, so those get hooksPath alone. rev-parse treats
# --no-verify as the negation of --verify, which is a different flag.
git_cmd() {
  local -a pre=()
  while [ $# -gt 0 ]; do
    case "$1" in
      -C|-c|--git-dir|--work-tree)
        [ $# -ge 2 ] || { echo "design-run-deliver: git_cmd missing value for $1" >&2; return 2; }
        pre+=("$1" "$2"); shift 2 ;;
      *) break ;;
    esac
  done
  [ $# -ge 1 ] || { echo "design-run-deliver: git_cmd missing subcommand" >&2; return 2; }
  local sub="$1"
  shift
  case "$sub" in
    commit|push|merge|rebase|am)
      git "${pre[@]}" -c core.hooksPath=/dev/null "$sub" --no-verify "$@" ;;
    *)
      git "${pre[@]}" -c core.hooksPath=/dev/null "$sub" "$@" ;;
  esac
}

# $1 body, $2 issue number. GitHub's nine closing keywords, the same
# boundary routine-lock-cleanup.sh uses so "#9" does not match "#95".
closes_issue() {
  printf '%s\n' "$1" | grep -qiP "\\b(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved):?\\s+#${2}\\b"
}

# Paths the delivery commit may include. A first-party module is a single
# file under lib/. A lib subdirectory is a vendored third-party tree and
# stays on the runner, as does anything outside the design.
safe_path() {
  case "$1" in
    designs/*) return 0 ;;
    lib|lib/|lib/*/*) return 1 ;;
    lib/*) return 0 ;;
    *) return 1 ;;
  esac
}

# Paths a commit since the start SHA must not touch.
forbidden_path() {
  case "$1" in
    .github|.github/*|.claude|.claude/*|scripts|scripts/*|tools|tools/*) return 0 ;;
    *) return 1 ;;
  esac
}

# insteadOf rewrites the push URL. A value (or a key) can carry a token,
# so the refusal prints neither — only that a url.* key exists.
refuse_url_rewrites() {
  local raw
  raw="$(git_cmd config --get-regexp '^url\.' || true)"
  if [ -n "$raw" ]; then
    echo "design-run-deliver: refusing to run with git url.* rewrite configured" >&2
    return 1
  fi
}

git_authed() {
  if [[ "$PUSH_URL" == https://* ]]; then
    GIT_ASKPASS="$ASKPASS" GIT_TERMINAL_PROMPT=0 \
      git_cmd -c credential.helper= "$@"
  else
    git_cmd "$@"
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
# Porcelain is NUL-delimited so a quoted path (spaces, quotes) cannot
# split or trip `set -e` the way a line-oriented `read` does at EOF.
# A rename/copy record is `XY SP <new>\0<old>\0`; both sides are staged
# when each is a safe path.
commit_safe_dirty() {
  local entry xy path old added=0 status_file
  status_file="$(mktemp)"
  # -uall: an untracked directory is otherwise one line ("lib/"), and
  # `git add` of that line would stage the vendored subtree inside it.
  git_cmd status --porcelain -z -uall > "$status_file"
  while IFS= read -r -d '' entry || [ -n "${entry:-}" ]; do
    [ -n "$entry" ] || continue
    xy="${entry:0:2}"
    path="${entry:3}"
    old=""
    case "$xy" in
      *R*|*C*)
        IFS= read -r -d '' old || {
          rm -f "$status_file"
          echo "design-run-deliver: truncated rename record for ${path}" >&2
          return 1
        }
        ;;
    esac
    # git add refuses a pathspec that is gone from both the worktree and
    # the index. A staged rename's old name is already that, so skip it;
    # the index still carries the rename and the commit records it.
    if [ -n "$path" ] && safe_path "$path"; then
      if [ -e "$path" ] || [ -L "$path" ] || git_cmd ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
        git_cmd add -A -- "$path"
        added=1
      fi
    fi
    if [ -n "$old" ] && safe_path "$old"; then
      if [ -e "$old" ] || [ -L "$old" ] || git_cmd ls-files --error-unmatch -- "$old" >/dev/null 2>&1; then
        git_cmd add -A -- "$old"
        added=1
      fi
    fi
  done < "$status_file"
  rm -f "$status_file"
  [ "$added" -eq 1 ] || return 0
  git_cmd -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
      -c user.name="github-actions[bot]" \
      commit -m "Design for #${ISSUE}"
  note "committed uncommitted design files onto ${BRANCH} before push"
}

# Net `git diff --name-only BASE..HEAD` hides a path that was added and
# then deleted, and a rename's old name. The log walk catches both.
refuse_forbidden_range() {
  local path line status rest old new diff_file log_file
  diff_file="$(mktemp)"
  log_file="$(mktemp)"
  git_cmd diff --name-only -z "${BASE}..HEAD" > "$diff_file"
  git_cmd log --name-status --find-renames --pretty=format: "${BASE}..HEAD" > "$log_file"
  while IFS= read -r -d '' path || [ -n "${path:-}" ]; do
    [ -n "$path" ] || continue
    if forbidden_path "$path"; then
      rm -f "$diff_file" "$log_file"
      echo "design-run-deliver: ${BASE}..HEAD touches ${path} — refusing to push" >&2
      return 1
    fi
  done < "$diff_file"
  while IFS= read -r line || [ -n "${line:-}" ]; do
    [ -n "$line" ] || continue
    status="${line%%$'\t'*}"
    rest="${line#*$'\t'}"
    case "$status" in
      R*|C*)
        old="${rest%%$'\t'*}"
        new="${rest#*$'\t'}"
        if forbidden_path "$old" || forbidden_path "$new"; then
          rm -f "$diff_file" "$log_file"
          echo "design-run-deliver: ${BASE}..HEAD touches ${old} -> ${new} — refusing to push" >&2
          return 1
        fi
        ;;
      *)
        if forbidden_path "$rest"; then
          rm -f "$diff_file" "$log_file"
          echo "design-run-deliver: ${BASE}..HEAD touches ${rest} — refusing to push" >&2
          return 1
        fi
        ;;
    esac
  done < "$log_file"
  rm -f "$diff_file" "$log_file"
}

# Remote tip must be this checkout's HEAD. Push when it is not.
verify_remote_tip() {
  local head remote
  head="$(git_cmd rev-parse HEAD)"
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

pr_list_json() {
  gh pr list --repo "$REPO" --head "$BRANCH" --state open --json "$PR_FIELDS"
}

# $1 json, $2 local tip. Prints the URL of a qualifying PR, or nothing.
qualifying_url() {
  printf '%s\n' "$1" | jq -r --arg n "$ISSUE" --arg tip "$2" --arg repo "$REPO" '
    def closes($b):
      ["close","closes","closed","fix","fixes","fixed",
       "resolve","resolves","resolved"]
      | any(. as $kw
            | ($b // "") | test("\\b" + $kw + ":?\\s+#" + $n + "\\b"; "i"));
    ([.[] | select(
        .isDraft == true
        and .headRefOid == $tip
        and .isCrossRepository == false
        and (((.headRepositoryOwner.login // "") + "/" + (.headRepository.name // "")) == $repo)
        and closes(.body)
      )][0].url) // empty
  '
}

# An open non-draft on this head is refused before push. Pushing would
# move that PR, and auto-arm.yml merges non-draft claude/* PRs.
refuse_open_nondraft() {
  local json
  if ! json="$(pr_list_json)"; then
    note "gh pr list failed for ${BRANCH} — refusing to push"
    return 1
  fi
  if printf '%s\n' "$json" | jq -e 'any(.[]; .isDraft == false)' >/dev/null; then
    note "open non-draft PR on ${BRANCH} — refusing to push (auto-arm.yml arms auto-merge on non-draft claude/* PRs)"
    return 1
  fi
}

# Print the URL of an open same-repo draft PR at the local tip whose body
# closes ISSUE, or nothing. Creates a draft only when the list is empty.
# A non-empty list that does not qualify fails closed — no second PR.
ensure_pr() {
  local json url count tip bodyfile title body
  tip="$(git_cmd rev-parse HEAD)"
  if ! json="$(pr_list_json)"; then
    note "gh pr list failed for ${BRANCH} — not posting success"
    return 1
  fi
  url="$(qualifying_url "$json" "$tip")"
  if [ -n "$url" ]; then
    printf '%s\n' "$url"
    return 0
  fi
  count="$(printf '%s\n' "$json" | jq 'length')"
  if [ "$count" -gt 0 ]; then
    note "open PR on ${BRANCH} is not a same-repo draft at ${tip} closing #${ISSUE} — not opening another and not posting success"
    return 1
  fi
  bodyfile="$(mktemp)"
  cat > "$bodyfile" <<EOF
Closes #${ISSUE}

Draft opened by the design-run delivery step after it verified \`${BRANCH}\` on the remote. The agent run ended without opening a PR; the gate evidence is the commits on this branch.
EOF
  title="$(git_cmd log -1 --format=%s)"
  title="${title:-Design for #${ISSUE}}"
  if ! gh pr create --repo "$REPO" --base "$BASE_BRANCH" --head "$BRANCH" \
      --draft --title "$title" --body-file "$bodyfile" >/dev/null; then
    note "gh pr create failed for ${BRANCH} — not posting success"
    return 1
  fi
  if ! json="$(pr_list_json)"; then
    note "gh pr list failed after create for ${BRANCH} — not posting success"
    return 1
  fi
  url="$(qualifying_url "$json" "$tip")"
  if [ -z "$url" ]; then
    note "no same-repo draft PR at ${tip} from ${BRANCH} closes #${ISSUE} after gh pr create — not posting success"
    return 1
  fi
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
  body="$(printf '%s\n\n- branch: `%s` (`%s`)\n- pull request: %s\n- run: %s\n\n`git ls-remote` matches the local tip and an open draft pull request in this repo from that tip closes this issue. This comment is posted only after both checks.' \
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
  if ! refuse_url_rewrites; then
    emit delivered false
    exit 1
  fi
  BRANCH="$(git_cmd rev-parse --abbrev-ref HEAD)"
  if ! [[ "$BRANCH" =~ ^claude/issue-${ISSUE}- ]]; then
    finish false "HEAD is '${BRANCH}', not claude/issue-${ISSUE}-* — nothing pushed"
  fi
  commit_safe_dirty
  if ! git_cmd cat-file -e "${BASE}^{commit}" 2>/dev/null; then
    echo "design-run-deliver: base ${BASE} is not a commit in this checkout" >&2
    exit 1
  fi
  ahead="$(git_cmd rev-list --count "${BASE}..HEAD")"
  if [ "$ahead" -eq 0 ]; then
    finish false "HEAD has no commits ahead of ${BASE} — nothing pushed"
  fi
  if ! refuse_forbidden_range; then
    emit delivered false
    exit 1
  fi
  if [ -z "${GH_TOKEN:-}" ]; then
    echo "design-run-deliver: GH_TOKEN is required to push ${BRANCH}" >&2
    exit 1
  fi
  export DELIVER_GH_TOKEN="$GH_TOKEN"
  if [[ "$PUSH_URL" == https://* ]]; then
    write_askpass
  fi
  if ! refuse_open_nondraft; then
    emit delivered false
    exit 1
  fi
  if ! verify_remote_tip; then
    emit delivered false
    exit 1
  fi
  if ! pr_url="$(ensure_pr)"; then
    emit delivered false
    exit 1
  fi
  head_sha="$(git_cmd rev-parse HEAD)"
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
  mkdir -p "$root/designs/nuggs-ladder" "$root/designs/old" "$root/designs/new" "$root/scripts"
  git_cmd -C "$root" init -b main >/dev/null
  git_cmd -C "$root" -c user.email=t@example.com -c user.name=t commit --allow-empty -m base >/dev/null
  base="$(git_cmd -C "$root" rev-parse HEAD)"
  git_cmd -C "$root" checkout -b claude/issue-853-nuggs-ladder >/dev/null 2>&1
  printf 'x\n' > "$root/designs/nuggs-ladder/nuggs-ladder.scad"
  printf 'space\n' > "$root/designs/old/my file.scad"
  printf 'quote\n' > "$root/designs/new/quote\"name.scad"
  printf 'a\n' > "$root/designs/old/a.scad"
  git_cmd -C "$root" -c user.email=t@example.com -c user.name=t add -- "designs/old/a.scad"
  git_cmd -C "$root" -c user.email=t@example.com -c user.name=t commit -m 'add a' >/dev/null
  git_cmd -C "$root" mv -- "designs/old/a.scad" "designs/new/a.scad"
  printf 'nope\n' > "$root/scripts/evil.sh"
  mkdir -p "$root/lib/Third"
  printf 'vendored\n' > "$root/lib/Third/secret.scad"
  printf 'libok\n' > "$root/lib/note.scad"
  git_cmd -C "$root" init -b main --bare "$bare" >/dev/null

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
  oid=\$(git -C "${root}" -c core.hooksPath=/dev/null rev-parse HEAD)
  cat > "${tmp}/pr.json" <<JSON
[{"number":99,"url":"https://github.com/acme/print-bench/pull/99","body":"Closes #853\\n\\nDraft opened by the design-run delivery step.\\n","isDraft":true,"headRefOid":"\${oid}","isCrossRepository":false,"headRepositoryOwner":{"login":"acme"},"headRepository":{"name":"print-bench"}}]
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

  bare_sha() {
    git_cmd --git-dir="$bare" rev-parse -q --verify "refs/heads/claude/issue-853-nuggs-ladder" 2>/dev/null || true
  }

  run_case() {  # name, expect exit, keep|fresh, then a command prefix
    local name="$1" expect="$2" keep="$3"
    shift 3
    rm -f "${tmp}/gh.log"
    if [ "$keep" != "keep" ]; then
      rm -f "${tmp}/comment.body" "${tmp}/pr.json"
    fi
    if [ -n "${PR_SEED:-}" ]; then
      cp "$PR_SEED" "${tmp}/pr.json"
    fi
    # This VM's global gitconfig carries url.insteadOf credential
    # rewrites. The check under test is unscoped on purpose; the fixture
    # hides that ambient config so a local url.* key is the only one visible.
    set +e
    env PATH="${tmp}/bin:${PATH}" GH_TOKEN=test-token COMMENT_TOKEN=comment-token \
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
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

  # git_cmd is the only git binary entry. Subcommands other than
  # commit/push/merge/rebase/am cannot take --no-verify (they exit 129).
  grep -q 'core.hooksPath=/dev/null' "$SELF"
  grep -q -- '--no-verify' "$SELF"
  grep -q 'commit|push|merge|rebase|am' "$SELF"
  # git_cmd is the only function that execs git. A second `git ` in command
  # position (the line starts with optional whitespace, then git) must pin
  # hooksPath. Mentions inside quotes are not invocations.
  if awk '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*git[[:space:]]/ {
      if ($0 ~ /core\.hooksPath=\/dev\/null/) next
      print
      bad = 1
    }
    END { exit bad ? 1 : 0 }
  ' "$SELF"; then
    :
  else
    echo "selftest: raw git call without core.hooksPath=/dev/null" >&2
    exit 1
  fi

  # Happy path: dirty design is committed and pushed, including a quoted
  # path, a space in the name, and a rename. The evil script is not. The
  # success comment exists and names the verified PR; gh.log shows the PR
  # create before the comment POST.
  run_case happy 0 fresh
  git_cmd --git-dir="$bare" rev-parse refs/heads/claude/issue-853-nuggs-ladder >/dev/null
  git_cmd --git-dir="$bare" grep -q nope refs/heads/claude/issue-853-nuggs-ladder && {
    echo "selftest: scripts/evil.sh was pushed" >&2
    exit 1
  }
  git_cmd --git-dir="$bare" grep -q x refs/heads/claude/issue-853-nuggs-ladder:designs/nuggs-ladder/nuggs-ladder.scad
  # -z so a quote or space in a path is not C-quoted by ls-tree.
  tree_has() {
    git_cmd --git-dir="$bare" ls-tree -r -z --name-only refs/heads/claude/issue-853-nuggs-ladder \
      | grep -zqxF "$1"
  }
  tree_has 'designs/old/my file.scad' || {
    echo "selftest: space in path was not pushed" >&2
    exit 1
  }
  tree_has 'designs/new/quote"name.scad' || {
    echo "selftest: quoted path was not pushed" >&2
    exit 1
  }
  tree_has 'designs/new/a.scad' || {
    echo "selftest: rename destination was not pushed" >&2
    exit 1
  }
  tree_has 'lib/note.scad' || {
    echo "selftest: first-party lib file was not pushed" >&2
    exit 1
  }
  if tree_has 'lib/Third/secret.scad'; then
    echo "selftest: vendored lib subtree was pushed" >&2
    exit 1
  fi
  if tree_has 'designs/old/a.scad'; then
    echo "selftest: rename source was still in the tree" >&2
    exit 1
  fi
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
  git_cmd -C "$root" init -b main --bare "$bare" >/dev/null
  run_case 'pr create failure' 1 fresh env FAIL_PR_CREATE=1
  if [ -f "${tmp}/comment.body" ]; then
    echo "selftest: failed pr create still posted success" >&2
    exit 1
  fi

  # Wrong branch name: dirty design on main is not committed or pushed.
  git_cmd -C "$root" checkout main >/dev/null
  mkdir -p "$root/designs/nuggs-ladder"
  printf 'y\n' > "$root/designs/nuggs-ladder/other.scad"
  run_case 'not the issue branch' 0 fresh
  if git_cmd --git-dir="$bare" rev-parse refs/heads/main >/dev/null 2>&1; then
    echo "selftest: pushed main" >&2
    exit 1
  fi
  if [ -f "${tmp}/comment.body" ]; then
    echo "selftest: wrong branch posted success" >&2
    exit 1
  fi

  git_cmd -C "$root" checkout claude/issue-853-nuggs-ladder >/dev/null
  local head_before bare_before stderr
  head_before="$(git_cmd -C "$root" rev-parse HEAD)"
  bare_before="$(bare_sha)"

  # M1: a url.* insteadOf (token redirect) refuses before any commit or push.
  # The secret stays in the config value and must not be echoed.
  printf 'm1\n' > "$root/designs/nuggs-ladder/m1.scad"
  git_cmd -C "$root" config url.https://evil.example/.insteadOf 'https://user:SECRETTOKEN@github.com/'
  set +e
  stderr="$(env PATH="${tmp}/bin:${PATH}" GH_TOKEN=test-token COMMENT_TOKEN=comment-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$root" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$base" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$bare" 2>&1 >/dev/null)"
  local rc=$?
  set -e
  if [ "$rc" -ne 1 ]; then
    echo "selftest: url rewrite exited ${rc}, expected 1" >&2
    exit 1
  fi
  if printf '%s\n' "$stderr" | grep -q 'SECRETTOKEN'; then
    echo "selftest: url rewrite printed the config value" >&2
    exit 1
  fi
  if ! printf '%s\n' "$stderr" | grep -q 'url\.\*'; then
    echo "selftest: url rewrite did not report the refusal" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  fi
  [ "$(git_cmd -C "$root" rev-parse HEAD)" = "$head_before" ] || {
    echo "selftest: url rewrite committed anyway" >&2
    exit 1
  }
  [ "$(bare_sha)" = "$bare_before" ] || {
    echo "selftest: url rewrite pushed anyway" >&2
    exit 1
  }
  git_cmd -C "$root" config --unset-all url.https://evil.example/.insteadof
  rm -f "$root/designs/nuggs-ladder/m1.scad"
  if [ -n "$(GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null git_cmd -C "$root" config --get-regexp '^url\.' || true)" ]; then
    echo "selftest: url rewrite config still set" >&2
    exit 1
  fi

  # M2: a non-draft PR on the branch refuses the push.
  printf 'm2\n' > "$root/designs/nuggs-ladder/m2.scad"
  cat > "${tmp}/nondraft.json" <<'JSON'
[{"number":7,"url":"https://github.com/acme/print-bench/pull/7","body":"Closes #853\n","isDraft":false,"headRefOid":"deadbeef","isCrossRepository":false,"headRepositoryOwner":{"login":"acme"},"headRepository":{"name":"print-bench"}}]
JSON
  PR_SEED="${tmp}/nondraft.json"
  bare_before="$(bare_sha)"
  run_case 'non-draft PR' 1 fresh
  unset PR_SEED
  [ "$(bare_sha)" = "$bare_before" ] || {
    echo "selftest: non-draft PR was pushed" >&2
    exit 1
  }
  if [ -f "${tmp}/comment.body" ] || grep -q 'pr create' "${tmp}/gh.log"; then
    echo "selftest: non-draft PR created a PR or posted success" >&2
    exit 1
  fi

  # M2: a draft whose headRefOid is not the local tip does not qualify.
  # The push itself is allowed (it would move a real draft); success is not.
  cat > "${tmp}/wrong-oid.json" <<'JSON'
[{"number":8,"url":"https://github.com/acme/print-bench/pull/8","body":"Closes #853\n","isDraft":true,"headRefOid":"deadbeefdeadbeefdeadbeefdeadbeefdeadbeef","isCrossRepository":false,"headRepositoryOwner":{"login":"acme"},"headRepository":{"name":"print-bench"}}]
JSON
  PR_SEED="${tmp}/wrong-oid.json"
  run_case 'draft oid mismatch' 1 fresh
  unset PR_SEED
  if [ -f "${tmp}/comment.body" ] || grep -q 'pr create' "${tmp}/gh.log"; then
    echo "selftest: oid mismatch created another PR or posted success" >&2
    exit 1
  fi

  # M2: a cross-repo PR at the right tip does not qualify and is not duplicated.
  local tip_now
  tip_now="$(git_cmd -C "$root" rev-parse HEAD)"
  cat > "${tmp}/cross.json" <<JSON
[{"number":6,"url":"https://github.com/acme/print-bench/pull/6","body":"Closes #853\n","isDraft":true,"headRefOid":"${tip_now}","isCrossRepository":true,"headRepositoryOwner":{"login":"attacker"},"headRepository":{"name":"print-bench"}}]
JSON
  PR_SEED="${tmp}/cross.json"
  bare_before="$(bare_sha)"
  run_case 'cross-repo PR' 1 fresh
  unset PR_SEED
  [ "$(bare_sha)" = "$bare_before" ] || {
    echo "selftest: cross-repo case moved the remote" >&2
    exit 1
  }
  if [ -f "${tmp}/comment.body" ] || grep -q 'pr create' "${tmp}/gh.log"; then
    echo "selftest: cross-repo PR created another PR or posted success" >&2
    exit 1
  fi

  # M3: an add-then-delete of scripts/ is invisible to the net diff and
  # must still refuse. The remote tip stays put.
  printf 'tracked\n' > "$root/scripts/tracked.sh"
  git_cmd -C "$root" -c user.email=t@example.com -c user.name=t add -- scripts/tracked.sh
  git_cmd -C "$root" -c user.email=t@example.com -c user.name=t commit -m 'add tracked' >/dev/null
  git_cmd -C "$root" rm -q -- scripts/tracked.sh >/dev/null
  git_cmd -C "$root" -c user.email=t@example.com -c user.name=t commit -m 'drop tracked' >/dev/null
  bare_before="$(bare_sha)"
  run_case 'hidden scripts touch' 1 fresh
  [ "$(bare_sha)" = "$bare_before" ] || {
    echo "selftest: add-then-delete of scripts/ was pushed" >&2
    exit 1
  }
  if [ -f "${tmp}/comment.body" ]; then
    echo "selftest: hidden scripts touch posted success" >&2
    exit 1
  fi

  # M3: a rename out of scripts/ shows only the new path in name-only.
  printf 'from\n' > "$root/scripts/from.sh"
  git_cmd -C "$root" -c user.email=t@example.com -c user.name=t add -- scripts/from.sh
  git_cmd -C "$root" -c user.email=t@example.com -c user.name=t commit -m 'add from' >/dev/null
  git_cmd -C "$root" mv -- scripts/from.sh designs/nuggs-ladder/from.sh
  git_cmd -C "$root" -c user.email=t@example.com -c user.name=t commit -m 'rename from' >/dev/null
  bare_before="$(bare_sha)"
  run_case 'rename out of scripts' 1 fresh
  [ "$(bare_sha)" = "$bare_before" ] || {
    echo "selftest: rename out of scripts/ was pushed" >&2
    exit 1
  }
  if [ -f "${tmp}/comment.body" ]; then
    echo "selftest: scripts rename posted success" >&2
    exit 1
  fi

  # H1: the workflow restores the script from START_SHA into RUNNER_TEMP.
  # A poisoned worktree copy, a symlinked scripts/, and a symlinked script
  # must not run. A symlink already at the restore path is unlinked, not
  # followed.
  local workflow deliver_run
  workflow="${ROOT}/.github/workflows/design-run.yml"
  deliver_run="$(awk '
    /^      - name: Deliver the branch and draft PR/ { in_step = 1 }
    in_step && /^        run: \|/ { printing = 1; next }
    in_step && printing && /^      - name:/ { exit }
    printing { print }
  ' "$workflow")"
  [ -n "$deliver_run" ] || { echo "selftest: could not extract the deliver run block" >&2; exit 1; }
  printf '%s\n' "$deliver_run" | grep -q 'git -c core.hooksPath=/dev/null show "$START_SHA:scripts/design-run-deliver.sh"' || {
    echo "selftest: deliver step does not git-show the pinned script" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep -q 'RUNNER_TEMP' || {
    echo "selftest: deliver step does not stage the script in RUNNER_TEMP" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep -q 'refusing to restore design-run-deliver' || {
    echo "selftest: deliver step does not refuse a symlink restore" >&2
    exit 1
  }
  if printf '%s\n' "$deliver_run" | grep -q './scripts/design-run-deliver.sh'; then
    echo "selftest: deliver step still executes the worktree script" >&2
    exit 1
  fi

  h1_repo() {  # $1 dir. Commits a trusted script, then poisons the worktree.
    local dir="$1"
    mkdir -p "$dir/scripts"
    cat > "$dir/scripts/design-run-deliver.sh" <<'EOF'
#!/bin/sh
printf '%s\n' TRUSTED > "$H1_MARK"
exit 0
EOF
    git_cmd -C "$dir" init -b main >/dev/null
    git_cmd -C "$dir" -c user.email=t@example.com -c user.name=t add -- scripts/design-run-deliver.sh
    git_cmd -C "$dir" -c user.email=t@example.com -c user.name=t commit -m trusted >/dev/null
    cat > "$dir/scripts/design-run-deliver.sh" <<'EOF'
#!/bin/sh
printf '%s\n' PWNED > "$H1_MARK"
exit 0
EOF
  }

  run_h1() {  # $1 dir, $2 runner temp, $3 mark file. Echoes the script's exit.
    local dir="$1" runner="$2" mark="$3" rc out
    set +e
    out="$(
      cd "$dir"
      START_SHA="$(git_cmd rev-parse HEAD)" \
        RUNNER_TEMP="$runner" \
        H1_MARK="$mark" \
        GITHUB_REPOSITORY=acme/print-bench \
        ISSUE=853 \
        BASE_BRANCH=main \
        RUN_URL=https://example.test/run/1 \
        bash -eo pipefail -c "$deliver_run" 2>&1
    )"
    rc=$?
    set -e
    # The workflow's ::error:: markers are real on a runner. Printed raw
    # inside check.sh they become job annotations, so the selftest rewrites
    # them after it has captured the exit code.
    printf '%s\n' "$out" | sed 's/::error::/error: /' >&2
    printf '%s\n' "$rc"
  }

  local h1 mark runner poisoned rc canary
  h1="${tmp}/h1"
  mark="${tmp}/h1-mark"
  runner="${tmp}/h1-runner"
  mkdir -p "$runner"
  h1_repo "$h1"
  rc="$(run_h1 "$h1" "$runner" "$mark")"
  [ "$rc" -eq 0 ] || { echo "selftest: H1 restore exited ${rc}" >&2; exit 1; }
  [ "$(cat "$mark")" = "TRUSTED" ] || {
    echo "selftest: H1 ran the worktree script ($(cat "$mark"))" >&2
    exit 1
  }

  # scripts/ as a symlink.
  poisoned="${tmp}/poison-dir"
  mkdir -p "$poisoned"
  cat > "$poisoned/design-run-deliver.sh" <<'EOF'
#!/bin/sh
printf '%s\n' PWNED > "$H1_MARK"
exit 0
EOF
  chmod +x "$poisoned/design-run-deliver.sh"
  rm -rf "$h1/scripts"
  ln -s "$poisoned" "$h1/scripts"
  rm -f "$mark"
  rc="$(run_h1 "$h1" "$runner" "$mark")"
  [ "$rc" -ne 0 ] || { echo "selftest: symlinked scripts/ was accepted" >&2; exit 1; }
  [ ! -e "$mark" ] || { echo "selftest: symlinked scripts/ executed a script" >&2; exit 1; }

  # The script path itself as a symlink.
  rm -rf "$h1"
  h1_repo "$h1"
  rm -f "$h1/scripts/design-run-deliver.sh"
  ln -s "$poisoned/design-run-deliver.sh" "$h1/scripts/design-run-deliver.sh"
  rm -f "$mark"
  rc="$(run_h1 "$h1" "$runner" "$mark")"
  [ "$rc" -ne 0 ] || { echo "selftest: symlinked script was accepted" >&2; exit 1; }
  [ ! -e "$mark" ] || { echo "selftest: symlinked script executed" >&2; exit 1; }

  # A symlink already sitting at $RUNNER_TEMP/design-run-deliver.sh is
  # removed, not followed, and the restored file is a regular file.
  rm -rf "$h1"
  h1_repo "$h1"
  canary="${tmp}/canary"
  printf '%s\n' CANARY > "$canary"
  ln -sfn "$canary" "$runner/design-run-deliver.sh"
  rm -f "$mark"
  rc="$(run_h1 "$h1" "$runner" "$mark")"
  [ "$rc" -eq 0 ] || { echo "selftest: restore over a dest symlink exited ${rc}" >&2; exit 1; }
  [ "$(cat "$canary")" = "CANARY" ] || {
    echo "selftest: dest symlink was followed ($(cat "$canary"))" >&2
    exit 1
  }
  [ ! -L "$runner/design-run-deliver.sh" ] && [ -f "$runner/design-run-deliver.sh" ] || {
    echo "selftest: restored script is not a regular file" >&2
    exit 1
  }
  [ "$(cat "$mark")" = "TRUSTED" ] || {
    echo "selftest: dest-symlink restore ran untrusted code" >&2
    exit 1
  }

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
