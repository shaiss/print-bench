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
# The agent job does not push. It restores this file from the pinned start
# commit and runs `--write-bundle`, which commits safe dirty files and
# writes a git bundle of START_SHA..HEAD. A later job, on a fresh runner,
# checks out that same start commit, verifies the bundle, and only then
# runs this file from that checkout (`--bundle`). Nothing in the bundle
# is executed.
#
# A firing whose issue thread carries 🚢 DECLINED, 🚦 DECISION NEEDED, or
# 🚢 DEFERRED — the same markers routine-lock-cleanup.sh's
# decline_indicated / deferred_indicated score, including that script's
# window and author gate — is not delivered. --write-bundle writes no
# bundle (the run job's lock cleanup still runs) and --bundle does not
# push. The check reads comments with GH_TOKEN and runs --stop-only on
# the routine-lock-cleanup.sh blob at the start SHA, so a commit on the
# design branch cannot replace the gate.
#
# Then:
#   1. Only a branch named claude/issue-<N>-* is eligible. main is never
#      pushed.
#   2. Uncommitted files under designs/ and first-party lib/ are committed
#      onto that branch, and the commit lists only those paths. A file
#      already staged outside that set (a vendored tree, a repo-root doc)
#      stays in the index and out of the commit. Vendored trees, scripts/,
#      .github/, .claude/ and tools/ are not committed.
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

# Absolute path of this file. The agent-side copy lives in $RUNNER_TEMP, so
# this path is NOT the checkout and dirname/.. is NOT the repo. The checkout
# is only DELIVER_WORKTREE, checked against `git rev-parse --show-toplevel`.
SELF="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)/$(basename "$0")"

# ubuntu-latest ships these under /usr/bin. A GITHUB_PATH shim lands in
# /usr/local/bin, which the default PATH searches first, so the defaults
# are absolute. The step env sets the same paths; a test may point GH_BIN
# at a fake.
GIT_BIN="${GIT_BIN:-/usr/bin/git}"
GH_BIN="${GH_BIN:-/usr/bin/gh}"
JQ_BIN="${JQ_BIN:-/usr/bin/jq}"

gh() { "$GH_BIN" "$@"; }
jq() { "$JQ_BIN" "$@"; }

DELIVERED_LINE='🚢 design-run delivered — branch and draft PR verified'
PR_FIELDS='number,url,body,isDraft,headRefOid,isCrossRepository,headRepositoryOwner,headRepository'

usage() {
  [ $# -eq 0 ] || echo "design-run-deliver: $*" >&2
  cat >&2 <<'EOF'
usage: scripts/design-run-deliver.sh --repo <owner/name> --issue <N>
           --base <sha> --base-branch <name> --run-url <url>
           [--push-url <url>]
           [--write-bundle <path> | --bundle <path> --bundle-sha256 <hex>]
       scripts/design-run-deliver.sh --selftest
EOF
  exit 2
}

[ -x "$GIT_BIN" ] && [ -x "$GH_BIN" ] && [ -x "$JQ_BIN" ] || {
  echo "design-run-deliver: git, gh and jq are required (${GIT_BIN}, ${GH_BIN}, ${JQ_BIN})" >&2
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
# -c core.hooksPath=/dev/null, core.fsmonitor=false, commit.gpgSign=false
# and an empty core.sshCommand are placed AFTER any caller -c, so a caller
# cannot turn them back on. --no-replace-objects is a global option (not
# overridable by -c). GIT_CONFIG_GLOBAL=/dev/null and GIT_CONFIG_NOSYSTEM=1
# are set on the git process itself, so a caller export cannot point git
# at a global config. --no-verify is passed only to the subcommands that
# accept it (commit, push, merge, rebase, am). status, diff, config, log,
# ls-remote, add, rev-list, cat-file, show, bundle and fetch exit 129 or
# 128 when given --no-verify, so those get the hardening -c flags alone.
# rev-parse treats --no-verify as the negation of --verify.
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
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
        "$GIT_BIN" --no-replace-objects "${pre[@]}" \
        -c core.hooksPath=/dev/null \
        -c core.fsmonitor=false \
        -c commit.gpgSign=false \
        -c core.sshCommand= \
        "$sub" --no-verify "$@" ;;
    *)
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
        "$GIT_BIN" --no-replace-objects "${pre[@]}" \
        -c core.hooksPath=/dev/null \
        -c core.fsmonitor=false \
        -c commit.gpgSign=false \
        -c core.sshCommand= \
        "$sub" "$@" ;;
  esac
}

# The checkout is whatever the workflow named. A copy of this script in
# $RUNNER_TEMP must not discover a repo by walking up from its own path.
enter_worktree() {
  local top
  if [ -z "${DELIVER_WORKTREE:-}" ]; then
    echo "design-run-deliver: DELIVER_WORKTREE is required" >&2
    exit 1
  fi
  case "$DELIVER_WORKTREE" in
    /*) ;;
    *)
      echo "design-run-deliver: DELIVER_WORKTREE must be an absolute path" >&2
      exit 1
      ;;
  esac
  if [ ! -d "$DELIVER_WORKTREE" ]; then
    echo "design-run-deliver: DELIVER_WORKTREE is not a directory" >&2
    exit 1
  fi
  cd "$DELIVER_WORKTREE"
  if ! top="$(git_cmd rev-parse --show-toplevel 2>/dev/null)"; then
    echo "design-run-deliver: DELIVER_WORKTREE is not a git checkout" >&2
    exit 1
  fi
  if [ "$top" != "$DELIVER_WORKTREE" ]; then
    echo "design-run-deliver: refusing DELIVER_WORKTREE ${DELIVER_WORKTREE}; git toplevel is ${top}" >&2
    exit 1
  fi
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

# A caller-supplied global or system gitconfig is refused before any git
# command. git_cmd forces /dev/null itself; this catches the invocation
# environment, and the message does not print the path or the file.
refuse_incoming_global_gitconfig() {
  if [ -n "${GIT_CONFIG_GLOBAL:-}" ] && [ "$GIT_CONFIG_GLOBAL" != "/dev/null" ]; then
    echo "design-run-deliver: refusing to run with GIT_CONFIG_GLOBAL set" >&2
    return 1
  fi
  if [ -n "${GIT_CONFIG_SYSTEM:-}" ] && [ "$GIT_CONFIG_SYSTEM" != "/dev/null" ]; then
    echo "design-run-deliver: refusing to run with GIT_CONFIG_SYSTEM set" >&2
    return 1
  fi
}

# Local keys that smudge blobs, redirect git, or sign commits. Values can
# carry a token or a command, so the refusal prints neither key nor value.
refuse_hostile_local_config() {
  local keys
  keys="$(git_cmd config --local --name-only --get-regexp '^(filter\.|include|gpg\.|http\.|credential\.|core\.fsmonitor$|core\.sshcommand$)' || true)"
  if [ -n "$keys" ]; then
    echo "design-run-deliver: refusing to run with hostile local git config" >&2
    return 1
  fi
}

# gh reads hosts.yml and config.yml from this directory. A fresh one means
# a poisoned ~/.config/gh cannot redirect the PR call.
use_fresh_gh_config() {
  GH_CONFIG_DIR="$(mktemp -d)"
  export GH_CONFIG_DIR
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
  local entry xy path old added=0 status_file cached
  local -a drop=()
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
  # Unstage anything already in the index that is outside the safe set,
  # then commit with no pathspec. `git commit -- <path>` is --only: it
  # replays the worktree and drops a staged rename's deletion (the old
  # name is not a path `git add` can name). A bare commit records that
  # index rename, and the reset keeps a pre-staged vendored file or
  # repo-root doc out of the commit.
  while IFS= read -r -d '' cached || [ -n "${cached:-}" ]; do
    [ -n "$cached" ] || continue
    if ! safe_path "$cached"; then
      drop+=("$cached")
    fi
  done < <(git_cmd diff --cached --name-only -z)
  if [ "${#drop[@]}" -gt 0 ]; then
    git_cmd reset -q -- "${drop[@]}"
  fi
  git_cmd -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
      -c user.name="github-actions[bot]" \
      commit -m "Design for #${ISSUE}"
  note "committed uncommitted design files onto ${BRANCH} before push"
}

# `git diff BASE...HEAD` is the merge-base diff (what the branch changed
# since it left START_SHA). It hides a path that was added and then deleted,
# and a rename's old name. `git log -z --name-status` catches both, and the
# NUL records keep a newline inside a path from splitting the record.
refuse_forbidden_range() {  # $1 tip ref, default HEAD
  local tip="${1:-HEAD}"
  local path status old new diff_file log_file
  diff_file="$(mktemp)"
  log_file="$(mktemp)"
  git_cmd diff --name-only -z "${BASE}...${tip}" > "$diff_file"
  git_cmd log -z --name-status --find-renames --pretty=format: "${BASE}..${tip}" > "$log_file"
  while IFS= read -r -d '' path || [ -n "${path:-}" ]; do
    [ -n "$path" ] || continue
    if forbidden_path "$path"; then
      rm -f "$diff_file" "$log_file"
      echo "design-run-deliver: ${BASE}...HEAD touches ${path} — refusing to push" >&2
      return 1
    fi
  done < "$diff_file"
  while IFS= read -r -d '' status || [ -n "${status:-}" ]; do
    [ -n "$status" ] || continue
    IFS= read -r -d '' path || {
      rm -f "$diff_file" "$log_file"
      echo "design-run-deliver: truncated name-status record (${status})" >&2
      return 1
    }
    case "$status" in
      R*|C*)
        IFS= read -r -d '' new || {
          rm -f "$diff_file" "$log_file"
          echo "design-run-deliver: truncated rename record for ${path}" >&2
          return 1
        }
        old="$path"
        if forbidden_path "$old" || forbidden_path "$new"; then
          rm -f "$diff_file" "$log_file"
          echo "design-run-deliver: ${BASE}..HEAD touches ${old} -> ${new} — refusing to push" >&2
          return 1
        fi
        ;;
      *)
        if forbidden_path "$path"; then
          rm -f "$diff_file" "$log_file"
          echo "design-run-deliver: ${BASE}..HEAD touches ${path} — refusing to push" >&2
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
  head="$(git_cmd rev-parse "$DELIVER_REF")"
  remote="$(git_authed ls-remote "$PUSH_URL" "refs/heads/${BRANCH}" | awk 'NR==1{print $1}')"
  if [ "$remote" = "$head" ]; then
    note "remote ${BRANCH} already at ${head}"
    return 0
  fi
  if ! git_authed push "$PUSH_URL" "${DELIVER_REF}:refs/heads/${BRANCH}"; then
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
  tip="$(git_cmd rev-parse "$DELIVER_REF")"
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
  title="$(git_cmd log -1 --format=%s "$DELIVER_REF")"
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

# Read `git bundle verify` output. One contained ref. START_SHA (BASE)
# must be a prerequisite. Further prerequisites are accepted only when
# each is an ancestor of BASE; an unrelated prerequisite is rejected.
# `git bundle verify` (git 2.43) does not checksum the pack — a flipped
# pack byte still prints "is okay" — so the caller also fetches, and a
# corrupt pack dies there instead of being pushed.
parse_bundle_verify() {  # $1 verify text. Sets BUNDLE_HEAD_SHA, BUNDLE_HEAD_REF.
  local line state sha ref prereq base_present
  local -a prereqs=() heads=()
  state=none
  while IFS= read -r line || [ -n "${line:-}" ]; do
    case "$line" in
      *" is okay") state=none; continue ;;
      "The bundle contains this ref:"|"The bundle contains these "*refs:) state=contains; continue ;;
      "The bundle requires this ref:"|"The bundle requires these "*refs:) state=requires; continue ;;
      "The bundle records a complete history."|"The bundle records a complete history") state=none; continue ;;
      "The bundle uses this hash algorithm:"*) state=none; continue ;;
      "") continue ;;
    esac
    sha="${line%% *}"
    ref="${line#"${sha}"}"
    ref="${ref#" "}"
    if ! printf '%s' "$sha" | grep -Eq '^[0-9a-f]{40}$'; then
      state=none
      continue
    fi
    case "$state" in
      contains) heads+=("${sha} ${ref}") ;;
      requires) prereqs+=("$sha") ;;
    esac
  done <<< "$1"
  base_present=0
  for prereq in "${prereqs[@]}"; do
    if [ "$prereq" = "$BASE" ]; then
      base_present=1
    fi
    # Inclusive: BASE is an ancestor of itself. Any other prerequisite
    # must be a real ancestor, present in this checkout (the deliver job
    # fetches full history so the check can see it).
    if ! git_cmd merge-base --is-ancestor "$prereq" "$BASE"; then
      echo "design-run-deliver: prerequisite ${prereq} is not an ancestor of START_SHA" >&2
      return 1
    fi
  done
  if [ "$base_present" -ne 1 ]; then
    echo "design-run-deliver: ancestry does not start at START_SHA" >&2
    return 1
  fi
  if [ "${#heads[@]}" -ne 1 ]; then
    echo "design-run-deliver: bundle does not contain exactly one branch ref" >&2
    return 1
  fi
  BUNDLE_HEAD_SHA="${heads[0]%% *}"
  BUNDLE_HEAD_REF="${heads[0]#* }"
}

# Fetch the verified bundle into refs/deliver/tip. Does not check the
# worktree out: the checkout must stay the start commit so this script
# is never replaced by a commit inside the bundle.
apply_bundle() {
  local got verify_out
  if [ -z "$BUNDLE" ] || [ ! -f "$BUNDLE" ] || [ -L "$BUNDLE" ]; then
    echo "design-run-deliver: bundle file is missing" >&2
    return 1
  fi
  if ! printf '%s' "$BUNDLE_SHA256" | grep -Eq '^[0-9a-f]{64}$'; then
    echo "design-run-deliver: bundle sha256 does not match" >&2
    return 1
  fi
  got="$(sha256sum "$BUNDLE" | awk '{print $1}')"
  if [ "$got" != "$BUNDLE_SHA256" ]; then
    echo "design-run-deliver: bundle sha256 does not match" >&2
    return 1
  fi
  if ! verify_out="$(git_cmd bundle verify "$BUNDLE" 2>&1)"; then
    echo "design-run-deliver: git bundle verify failed" >&2
    return 1
  fi
  if ! parse_bundle_verify "$verify_out"; then
    return 1
  fi
  case "$BUNDLE_HEAD_REF" in
    refs/heads/claude/issue-${ISSUE}-*) ;;
    *)
      echo "design-run-deliver: bundle ref '${BUNDLE_HEAD_REF}' is not claude/issue-${ISSUE}-* — nothing pushed" >&2
      return 1
      ;;
  esac
  BRANCH="${BUNDLE_HEAD_REF#refs/heads/}"
  git_cmd update-ref -d refs/deliver/tip >/dev/null 2>&1 || true
  if ! git_cmd fetch --no-tags "$BUNDLE" "${BUNDLE_HEAD_REF}:refs/deliver/tip" >/dev/null; then
    echo "design-run-deliver: could not fetch the bundle" >&2
    return 1
  fi
  if [ "$(git_cmd rev-parse refs/deliver/tip)" != "$BUNDLE_HEAD_SHA" ]; then
    echo "design-run-deliver: fetched tip does not match the bundle ref" >&2
    return 1
  fi
  if ! git_cmd merge-base --is-ancestor "$BASE" refs/deliver/tip; then
    echo "design-run-deliver: ancestry does not start at START_SHA" >&2
    return 1
  fi
  DELIVER_REF=refs/deliver/tip
}

# Returns 0 when this firing's stop markers say do not deliver, 1 when
# they do not, 2 when the disposition could not be read. The markers are
# routine-lock-cleanup.sh's decline_indicated and deferred_indicated,
# executed from the blob at BASE (the pinned start SHA), not from the
# worktree copy the agent can rewrite.
delivery_stopped() {
  local comments cleanup stopped
  local -a window_args=()
  if [ -z "${GH_TOKEN:-}" ]; then
    echo "design-run-deliver: GH_TOKEN is required to read the run disposition" >&2
    return 2
  fi
  if ! comments="$(gh api --paginate "/repos/${REPO}/issues/${ISSUE}/comments?per_page=100" \
      --jq '.[] | {body: (.body // ""), created_at: .created_at, login: (.user.login // ""), type: (.user.type // "")}')"; then
    echo "design-run-deliver: could not read issue comments to derive the run disposition" >&2
    return 2
  fi
  if ! git_cmd cat-file -e "${BASE}^{commit}" 2>/dev/null; then
    echo "design-run-deliver: base ${BASE} is not a commit in this checkout" >&2
    return 2
  fi
  cleanup="$(mktemp)"
  if ! git_cmd show "${BASE}:scripts/routine-lock-cleanup.sh" > "$cleanup"; then
    rm -f "$cleanup"
    echo "design-run-deliver: could not read routine-lock-cleanup.sh from ${BASE}" >&2
    return 2
  fi
  if [ -n "${JOB_WINDOW_START:-}" ]; then
    window_args=(--run-started-at "$JOB_WINDOW_START")
  fi
  # A failing query is the || branch. Do not toggle set -e here: it is not
  # function-local, and a later `return 1` ("not stopped") would then abort
  # the caller.
  if ! stopped="$(printf '%s\n' "$comments" | bash "$cleanup" --stop-only --repo "$REPO" --issue "$ISSUE" "${window_args[@]}")"; then
    rm -f "$cleanup"
    echo "design-run-deliver: disposition query failed" >&2
    return 2
  fi
  rm -f "$cleanup"
  case "$stopped" in
    true) return 0 ;;
    false) return 1 ;;
  esac
  echo "design-run-deliver: disposition query returned '${stopped:-empty}'" >&2
  return 2
}

# Exit 0 with nothing delivered when this firing already stopped. A read
# failure exits 1 so a design is not pushed on an unknown disposition.
refuse_if_stopped() {
  local rc
  set +e
  delivery_stopped
  rc=$?
  set -e
  case "$rc" in
    0) finish false "a DECLINED, DECISION NEEDED, or DEFERRED stop from this run — nothing pushed" ;;
    1) return 0 ;;
    *) exit 1 ;;
  esac
}

# Commit safe dirty files and write START_SHA..HEAD. No token, no push.
# Exit 0 with no file when there is nothing to deliver (the workflow then
# records pending=false), including a declined / deferred stop. A protected
# path exits 1 and writes no file.
write_bundle() {
  local ahead
  BRANCH="$(git_cmd rev-parse --abbrev-ref HEAD)"
  if ! [[ "$BRANCH" =~ ^claude/issue-${ISSUE}- ]]; then
    finish false "HEAD is '${BRANCH}', not claude/issue-${ISSUE}-* — nothing pushed"
  fi
  refuse_if_stopped
  commit_safe_dirty
  if ! git_cmd cat-file -e "${BASE}^{commit}" 2>/dev/null; then
    echo "design-run-deliver: base ${BASE} is not a commit in this checkout" >&2
    exit 1
  fi
  ahead="$(git_cmd rev-list --count "${BASE}..HEAD")"
  if [ "$ahead" -eq 0 ]; then
    finish false "HEAD has no commits ahead of ${BASE} — nothing pushed"
  fi
  if ! refuse_forbidden_range HEAD; then
    exit 1
  fi
  if [ -L "$WRITE_BUNDLE" ]; then
    echo "design-run-deliver: refusing to write the bundle through a symlink" >&2
    exit 1
  fi
  rm -f "$WRITE_BUNDLE"
  git_cmd bundle create "$WRITE_BUNDLE" "^${BASE}" "refs/heads/${BRANCH}"
  exit 0
}

run_live() {
  local ahead head_sha pr_url
  if ! [[ "$ISSUE" =~ ^[0-9]+$ ]]; then
    echo "design-run-deliver: issue must be numeric, got '${ISSUE}'" >&2
    exit 2
  fi
  # A step env blanks these so a GITHUB_ENV poison cannot redirect git.
  # An empty value is still set, and an empty GIT_DIR breaks every command,
  # so drop them before the first git.
  unset GIT_DIR GIT_WORK_TREE GIT_CONFIG_PARAMETERS GIT_SSH_COMMAND || true
  if ! refuse_incoming_global_gitconfig; then
    emit delivered false
    exit 1
  fi
  enter_worktree
  use_fresh_gh_config
  if ! refuse_hostile_local_config || ! refuse_url_rewrites; then
    emit delivered false
    exit 1
  fi
  if [ -n "$WRITE_BUNDLE" ]; then
    write_bundle
  fi
  # --write-bundle already returned through finish/exit. This is the
  # deliver-job and direct-push gate: a stop writes no success and no push.
  refuse_if_stopped
  if [ -n "$BUNDLE" ]; then
    if ! apply_bundle; then
      emit delivered false
      exit 1
    fi
  else
    DELIVER_REF=HEAD
    BRANCH="$(git_cmd rev-parse --abbrev-ref HEAD)"
    if ! [[ "$BRANCH" =~ ^claude/issue-${ISSUE}- ]]; then
      finish false "HEAD is '${BRANCH}', not claude/issue-${ISSUE}-* — nothing pushed"
    fi
    commit_safe_dirty
  fi
  if ! git_cmd cat-file -e "${BASE}^{commit}" 2>/dev/null; then
    echo "design-run-deliver: base ${BASE} is not a commit in this checkout" >&2
    exit 1
  fi
  ahead="$(git_cmd rev-list --count "${BASE}..${DELIVER_REF}")"
  if [ "$ahead" -eq 0 ]; then
    finish false "HEAD has no commits ahead of ${BASE} — nothing pushed"
  fi
  if ! refuse_forbidden_range "$DELIVER_REF"; then
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
  head_sha="$(git_cmd rev-parse "$DELIVER_REF")"
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
  local repo_root="$1"
  local tmp root bare base
  tmp="$(mktemp -d)"
  root="${tmp}/repo"
  bare="${tmp}/bare.git"
  mkdir -p "$root/designs/nuggs-ladder" "$root/designs/old" "$root/designs/new" "$root/scripts"
  cp "$(dirname "$SELF")/routine-lock-cleanup.sh" "$root/scripts/routine-lock-cleanup.sh"
  git_cmd -C "$root" init -b main >/dev/null
  git_cmd -C "$root" add -- scripts/routine-lock-cleanup.sh
  git_cmd -C "$root" -c user.email=t@example.com -c user.name=t commit -m base >/dev/null
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
  # Already staged, and outside the safe set: a bare `git commit` would
  # record both under github-actions[bot]. The delivery commit must not.
  printf 'staged-vendor\n' > "$root/lib/Third/staged.scad"
  mkdir -p "$root/docs"
  printf 'staged-doc\n' > "$root/docs/staged.md"
  git_cmd -C "$root" add -- lib/Third/staged.scad docs/staged.md
  git_cmd -C "$root" init -b main --bare "$bare" >/dev/null

  # Fake gh: records invocations and serves the PR the create call wrote.
  mkdir -p "${tmp}/bin"
  cat > "${tmp}/bin/gh" <<EOF
#!/bin/sh
printf '%s\n' "\$*" >> "${tmp}/gh.log"
printf '%s\n' "\${GH_CONFIG_DIR:-unset}" >> "${tmp}/gh-config-dirs"
if [ "\$1" = "pr" ] && [ "\$2" = "list" ]; then
  if [ -f "${tmp}/pr.json" ]; then cat "${tmp}/pr.json"; else printf '%s\n' '[]'; fi
  exit 0
fi
if [ "\$1" = "pr" ] && [ "\$2" = "create" ]; then
  if [ "\${FAIL_PR_CREATE:-}" = "1" ]; then
    echo "pr create refused" >&2
    exit 1
  fi
  repo="\${GH_REPO:-${root}}"
  if git -C "\$repo" rev-parse --verify -q refs/deliver/tip >/dev/null 2>&1; then
    oid=\$(git -C "\$repo" -c core.hooksPath=/dev/null rev-parse refs/deliver/tip)
  else
    oid=\$(git -C "\$repo" -c core.hooksPath=/dev/null rev-parse HEAD)
  fi
  cat > "${tmp}/pr.json" <<JSON
[{"number":99,"url":"https://github.com/acme/print-bench/pull/99","body":"Closes #853\\n\\nDraft opened by the design-run delivery step.\\n","isDraft":true,"headRefOid":"\${oid}","isCrossRepository":false,"headRepositoryOwner":{"login":"acme"},"headRepository":{"name":"print-bench"}}]
JSON
  printf '%s\n' 'https://github.com/acme/print-bench/pull/99'
  exit 0
fi
if [ "\$1" = "api" ]; then
  # Comment GET (paginate) returns prior bodies; POST records the body.
  # The disposition read asks for created_at and wants comment NDJSON.
  # The success-comment count asks with a different --jq and wants 0 or 1.
  if printf '%s\n' "\$*" | grep -q 'created_at'; then
    if [ -f "${tmp}/comments.ndjson" ]; then
      cat "${tmp}/comments.ndjson"
    fi
    exit 0
  fi
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
    env PATH="${tmp}/bin:${PATH}" GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token COMMENT_TOKEN=comment-token \
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
  grep -q 'core.fsmonitor=false' "$SELF"
  grep -q 'core.sshCommand=' "$SELF"
  grep -q 'commit.gpgSign=false' "$SELF"
  grep -q 'GIT_CONFIG_GLOBAL=/dev/null' "$SELF"
  grep -q 'GIT_CONFIG_NOSYSTEM=1' "$SELF"
  grep -q 'refusing to run with GIT_CONFIG_GLOBAL set' "$SELF"
  grep -q -- '--no-replace-objects' "$SELF"
  grep -q -- '--no-verify' "$SELF"
  grep -q 'commit|push|merge|rebase|am' "$SELF"
  grep -q 'GH_CONFIG_DIR' "$SELF"
  grep -q 'DELIVER_WORKTREE is required' "$SELF"
  grep -q 'git_cmd log -z --name-status' "$SELF"
  grep -q 'diff --name-only -z "${BASE}...${tip}"' "$SELF"
  grep -q 'refusing to run with hostile local git config' "$SELF"
  # git_cmd is the only function that execs git. A second `git ` in command
  # position (the line starts with optional whitespace, then git) must pin
  # hooksPath. Mentions inside quotes are not invocations.
  if awk '
    /^[[:space:]]*#/ { next }
    /\\$/ { buf = buf $0 " "; next }
    {
      line = buf $0
      buf = ""
      if (line ~ /^[[:space:]]*git[[:space:]]/) {
        if (line ~ /core\.hooksPath=\/dev\/null/ && line ~ /--no-replace-objects/ && line ~ /core\.fsmonitor=false/ && line ~ /commit\.gpgSign=false/) next
        print
        bad = 1
      }
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
  if tree_has 'lib/Third/staged.scad'; then
    echo "selftest: staged vendored file was committed and pushed" >&2
    exit 1
  fi
  if tree_has 'docs/staged.md'; then
    echo "selftest: staged repo-root doc was committed and pushed" >&2
    exit 1
  fi
  if tree_has 'designs/old/a.scad'; then
    echo "selftest: rename source was still in the tree" >&2
    exit 1
  fi
  grep -q 'design-run delivered' "${tmp}/comment.body"
  grep -q 'https://github.com/acme/print-bench/pull/99' "${tmp}/comment.body"
  gh_cfg="$(tail -n 1 "${tmp}/gh-config-dirs")"
  [ -n "$gh_cfg" ] && [ "$gh_cfg" != "unset" ] && [ -d "$gh_cfg" ] || {
    echo "selftest: gh did not receive a fresh GH_CONFIG_DIR" >&2
    exit 1
  }
  [ ! -e "${gh_cfg}/PLANTED" ] || {
    echo "selftest: gh used a planted GH_CONFIG_DIR" >&2
    exit 1
  }
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

  # A planted GH_CONFIG_DIR is replaced before gh runs. This has to be a
  # successful gh-calling run, before any scripts/ commit makes the range
  # refuse and skip gh.
  local planted_gh recorded_gh
  planted_gh="${tmp}/planted-gh"
  mkdir -p "$planted_gh"
  printf 'planted\n' > "${planted_gh}/PLANTED"
  run_case 'fresh gh config' 0 keep env GH_CONFIG_DIR="$planted_gh"
  recorded_gh="$(tail -n 1 "${tmp}/gh-config-dirs")"
  [ "$recorded_gh" != "$planted_gh" ] && [ -d "$recorded_gh" ] && [ ! -e "${recorded_gh}/PLANTED" ] || {
    echo "selftest: planted GH_CONFIG_DIR was used (${recorded_gh})" >&2
    exit 1
  }

  # A caller-supplied global gitconfig is refused before any git command.
  # The file holds a stand-in token; the refusal must not print it, and
  # nothing is committed or pushed.
  local evil_git bare_now head_now
  evil_git="${tmp}/evil.gitconfig"
  printf '[url "https://evil.example/"]\n\tinsteadOf = https://user:SECRETTOKEN@github.com/\n' > "$evil_git"
  bare_now="$(bare_sha)"
  head_now="$(git_cmd -C "$root" rev-parse HEAD)"
  set +e
  stderr="$(env PATH="${tmp}/bin:${PATH}" GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token COMMENT_TOKEN=comment-token \
    GIT_CONFIG_GLOBAL="$evil_git" GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$root" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$base" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$bare" 2>&1 >/dev/null)"
  rc=$?
  set -e
  if [ "$rc" -ne 1 ]; then
    echo "selftest: GIT_CONFIG_GLOBAL exited ${rc}, expected 1" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  fi
  if printf '%s\n' "$stderr" | grep -q 'SECRETTOKEN'; then
    echo "selftest: GIT_CONFIG_GLOBAL refusal printed the file" >&2
    exit 1
  fi
  if ! printf '%s\n' "$stderr" | grep -q 'refusing to run with GIT_CONFIG_GLOBAL set'; then
    echo "selftest: GIT_CONFIG_GLOBAL did not report the refusal" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  fi
  [ "$(git_cmd -C "$root" rev-parse HEAD)" = "$head_now" ] || {
    echo "selftest: GIT_CONFIG_GLOBAL committed anyway" >&2
    exit 1
  }
  [ "$(bare_sha)" = "$bare_now" ] || {
    echo "selftest: GIT_CONFIG_GLOBAL pushed anyway" >&2
    exit 1
  }
  printf '[http]\n\tproxy = SECRETTOKEN\n' > "$evil_git"
  set +e
  stderr="$(env PATH="${tmp}/bin:${PATH}" GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM="$evil_git" \
    DELIVER_WORKTREE="$root" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$base" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$bare" 2>&1 >/dev/null)"
  rc=$?
  set -e
  if [ "$rc" -ne 1 ] || printf '%s\n' "$stderr" | grep -q 'SECRETTOKEN' \
      || ! printf '%s\n' "$stderr" | grep -q 'refusing to run with GIT_CONFIG_SYSTEM set'; then
    echo "selftest: GIT_CONFIG_SYSTEM was not refused" >&2
    printf '%s\n' "$stderr" >&2
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

  # A newline inside a scripts/ path must still refuse. Line-oriented
  # name-status would split the record; the -z walk keeps it one path.
  nl_path=$'scripts/has\nnewline.sh'
  printf 'nl\n' > "$root/$nl_path"
  git_cmd -C "$root" -c user.email=t@example.com -c user.name=t add -- "$nl_path"
  git_cmd -C "$root" -c user.email=t@example.com -c user.name=t commit -m 'newline path' >/dev/null
  bare_before="$(bare_sha)"
  run_case 'newline in scripts path' 1 fresh
  [ "$(bare_sha)" = "$bare_before" ] || {
    echo "selftest: newline scripts path was pushed" >&2
    exit 1
  }

  # Hostile local git config (smudge filters, includes, signing, http,
  # credentials, fsmonitor, sshCommand) refuses before any push. The value
  # is a stand-in token and must not be echoed.
  local hostile_key
  for hostile_key in \
    filter.lfs.clean \
    include.path \
    gpg.format \
    http.extraheader \
    credential.helper \
    core.fsmonitor \
    core.sshCommand
  do
    git_cmd -C "$root" config --local "$hostile_key" "SECRETTOKEN-${hostile_key}"
    set +e
    stderr="$(env PATH="${tmp}/bin:${PATH}" GH_TOKEN=test-token COMMENT_TOKEN=comment-token \
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
      DELIVER_WORKTREE="$root" \
      "$SELF" --repo acme/print-bench --issue 853 --base "$base" \
      --base-branch main --run-url https://example.test/run/1 --push-url "$bare" 2>&1 >/dev/null)"
    rc=$?
    set -e
    if [ "$rc" -ne 1 ]; then
      echo "selftest: ${hostile_key} exited ${rc}, expected 1" >&2
      exit 1
    fi
    if printf '%s\n' "$stderr" | grep -q 'SECRETTOKEN'; then
      echo "selftest: ${hostile_key} printed the config value" >&2
      exit 1
    fi
    if ! printf '%s\n' "$stderr" | grep -q 'hostile local git config'; then
      echo "selftest: ${hostile_key} did not report the refusal" >&2
      printf '%s\n' "$stderr" >&2
      exit 1
    fi
    git_cmd -C "$root" config --local --unset-all "$hostile_key"
  done

  # Bundle path. The agent-side --write-bundle commits safe dirty files
  # and writes START..HEAD. The deliver-side --bundle runs against a
  # checkout that has only the start commit: it checks the sha256, runs
  # git bundle verify, fetches into refs/deliver/tip, and refuses unless
  # that ref's ancestry starts at the start commit. It does not check the
  # bundle out, and it does not execute anything from the bundle.
  local bsrc bdel bbare bstart btip bsha bfile bhead
  bsrc="${tmp}/bsrc"
  bdel="${tmp}/bdel"
  bbare="${tmp}/bbare.git"
  bfile="${tmp}/design-run.bundle"
  mkdir -p "$bsrc/designs/nuggs-ladder" "$bsrc/scripts"
  cp "$(dirname "$SELF")/routine-lock-cleanup.sh" "$bsrc/scripts/routine-lock-cleanup.sh"
  git_cmd -C "$bsrc" init -b main >/dev/null
  git_cmd -C "$bsrc" add -- scripts/routine-lock-cleanup.sh
  git_cmd -C "$bsrc" -c user.email=t@example.com -c user.name=t commit -m start >/dev/null
  bstart="$(git_cmd -C "$bsrc" rev-parse HEAD)"
  git_cmd -C "$bsrc" checkout -b claude/issue-853-nuggs-ladder >/dev/null
  printf 'bundled\n' > "$bsrc/designs/nuggs-ladder/nuggs-ladder.scad"
  git_cmd -C "$bsrc" -c user.email=t@example.com -c user.name=t add -- designs/nuggs-ladder/nuggs-ladder.scad
  git_cmd -C "$bsrc" -c user.email=t@example.com -c user.name=t commit -m 'design' >/dev/null
  printf 'dirty\n' > "$bsrc/designs/nuggs-ladder/extra.scad"
  git_cmd init -b main --bare "$bbare" >/dev/null
  set +e
  env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$bsrc" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$bstart" \
    --base-branch main --run-url https://example.test/run/1 \
    --write-bundle "$bfile" >/dev/null
  rc=$?
  set -e
  [ "$rc" -eq 0 ] && [ -f "$bfile" ] || {
    echo "selftest: --write-bundle did not write a bundle (exit ${rc})" >&2
    exit 1
  }
  btip="$(git_cmd -C "$bsrc" rev-parse HEAD)"
  git_cmd -C "$bsrc" grep -q dirty "$btip" -- designs/nuggs-ladder/extra.scad || {
    echo "selftest: --write-bundle did not commit the dirty design file" >&2
    exit 1
  }
  git_cmd init -b main --bare "${tmp}/bstart.git" >/dev/null
  git_cmd -C "$bsrc" push "${tmp}/bstart.git" "$bstart:refs/heads/main" >/dev/null
  git_cmd clone -b main "${tmp}/bstart.git" "$bdel" >/dev/null
  bsha="$(sha256sum "$bfile" | awk '{print $1}')"
  rm -f "${tmp}/pr.json" "${tmp}/comment.body" "${tmp}/gh.log"
  set +e
  env GH_BIN="${tmp}/bin/gh" GH_REPO="$bdel" GH_TOKEN=test-token COMMENT_TOKEN=comment-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$bdel" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$bstart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$bbare" \
    --bundle "$bfile" --bundle-sha256 "$bsha" >/dev/null
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || { echo "selftest: bundle delivery exited ${rc}" >&2; exit 1; }
  [ "$(git_cmd -C "$bdel" rev-parse HEAD)" = "$bstart" ] || {
    echo "selftest: bundle delivery checked the bundle out over START_SHA" >&2
    exit 1
  }
  [ "$(git_cmd -C "$bdel" rev-parse refs/deliver/tip)" = "$btip" ] || {
    echo "selftest: refs/deliver/tip is not the bundled tip" >&2
    exit 1
  }
  [ "$(git_cmd --git-dir="$bbare" rev-parse refs/heads/claude/issue-853-nuggs-ladder)" = "$btip" ] || {
    echo "selftest: bundle was not pushed" >&2
    exit 1
  }
  git_cmd --git-dir="$bbare" grep -q dirty refs/heads/claude/issue-853-nuggs-ladder -- designs/nuggs-ladder/extra.scad
  grep -q 'design-run delivered' "${tmp}/comment.body" || {
    echo "selftest: bundle delivery did not post success" >&2
    exit 1
  }

  # Wrong sha256: the bundle is valid, the digest is not. Nothing is pushed.
  bhead="$(git_cmd --git-dir="$bbare" rev-parse refs/heads/claude/issue-853-nuggs-ladder)"
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_REPO="$bdel" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$bdel" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$bstart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$bbare" \
    --bundle "$bfile" --bundle-sha256 0000000000000000000000000000000000000000000000000000000000000000 \
    2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 1 ] || { echo "selftest: wrong bundle sha exited ${rc}" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep -q 'bundle sha256 does not match' || {
    echo "selftest: wrong bundle sha did not report the refusal" >&2
    exit 1
  }
  [ "$(git_cmd --git-dir="$bbare" rev-parse refs/heads/claude/issue-853-nuggs-ladder)" = "$bhead" ] || {
    echo "selftest: wrong bundle sha pushed" >&2
    exit 1
  }

  # Tampered pack. git bundle verify still says the bundle is okay (it does
  # not checksum the pack); the fetch must refuse it. The sha256 is of the
  # tampered bytes, so this is not the digest check. A fresh checkout that
  # has only START_SHA, so the objects are not already present and a
  # short-circuited fetch cannot look like success.
  local bdel2 bbare2
  bdel2="${tmp}/bdel2"
  bbare2="${tmp}/bbare2.git"
  git_cmd clone -b main "${tmp}/bstart.git" "$bdel2" >/dev/null
  git_cmd init -b main --bare "$bbare2" >/dev/null
  cp "$bfile" "${tmp}/tampered.bundle"
  python3 -c '
import pathlib, sys
p = pathlib.Path(sys.argv[1])
data = bytearray(p.read_bytes())
# The pack trailer is the checksum. Flipping it is what makes fetch
# report "pack is corrupted"; a byte just after the PACK header is not.
data[-10] ^= 0xFF
p.write_bytes(data)
' "${tmp}/tampered.bundle"
  bsha="$(sha256sum "${tmp}/tampered.bundle" | awk '{print $1}')"
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_REPO="$bdel2" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$bdel2" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$bstart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$bbare2" \
    --bundle "${tmp}/tampered.bundle" --bundle-sha256 "$bsha" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 1 ] || { echo "selftest: tampered bundle exited ${rc}" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep -Eq 'git bundle verify failed|could not fetch the bundle' || {
    echo "selftest: tampered bundle was not refused" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  if git_cmd --git-dir="$bbare2" rev-parse refs/heads/claude/issue-853-nuggs-ladder >/dev/null 2>&1; then
    echo "selftest: tampered bundle was pushed" >&2
    exit 1
  fi

  # Ancestry that does not start at START_SHA: a complete-history bundle
  # has no prerequisite, and a bundle whose prerequisite is the parent of
  # START_SHA is not START_SHA either.
  git_cmd -C "$bsrc" bundle create "${tmp}/orphan.bundle" refs/heads/claude/issue-853-nuggs-ladder
  bsha="$(sha256sum "${tmp}/orphan.bundle" | awk '{print $1}')"
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$bdel" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$bstart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$bbare" \
    --bundle "${tmp}/orphan.bundle" --bundle-sha256 "$bsha" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 1 ] || { echo "selftest: orphan bundle exited ${rc}" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep -q 'ancestry does not start at START_SHA' || {
    echo "selftest: orphan bundle did not refuse the ancestry" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  # A prerequisite that is a real ancestor, but not START_SHA. The
  # deliver checkout contains that ancestor (it is START_SHA's parent), so
  # `git bundle verify` succeeds and the refusal is the ancestry check.
  local asrc adel aroot astart
  asrc="${tmp}/asrc"
  adel="${tmp}/adel"
  mkdir -p "$asrc/designs/nuggs-ladder" "$asrc/scripts"
  cp "$(dirname "$SELF")/routine-lock-cleanup.sh" "$asrc/scripts/routine-lock-cleanup.sh"
  git_cmd -C "$asrc" init -b main >/dev/null
  git_cmd -C "$asrc" add -- scripts/routine-lock-cleanup.sh
  git_cmd -C "$asrc" -c user.email=t@example.com -c user.name=t commit -m root >/dev/null
  aroot="$(git_cmd -C "$asrc" rev-parse HEAD)"
  git_cmd -C "$asrc" -c user.email=t@example.com -c user.name=t commit --allow-empty -m start >/dev/null
  astart="$(git_cmd -C "$asrc" rev-parse HEAD)"
  git_cmd -C "$asrc" checkout -b claude/issue-853-nuggs-ladder >/dev/null
  printf 'later\n' > "$asrc/designs/nuggs-ladder/later.scad"
  git_cmd -C "$asrc" -c user.email=t@example.com -c user.name=t add -- designs/nuggs-ladder/later.scad
  git_cmd -C "$asrc" -c user.email=t@example.com -c user.name=t commit -m later >/dev/null
  git_cmd -C "$asrc" bundle create "${tmp}/older.bundle" "^${aroot}" refs/heads/claude/issue-853-nuggs-ladder
  git_cmd init -b main --bare "${tmp}/astart.git" >/dev/null
  git_cmd -C "$asrc" push "${tmp}/astart.git" "${astart}:refs/heads/main" >/dev/null
  git_cmd clone -b main "${tmp}/astart.git" "$adel" >/dev/null
  bsha="$(sha256sum "${tmp}/older.bundle" | awk '{print $1}')"
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$adel" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$astart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$bbare" \
    --bundle "${tmp}/older.bundle" --bundle-sha256 "$bsha" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 1 ] || { echo "selftest: older-prerequisite bundle exited ${rc}" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep -q 'ancestry does not start at START_SHA' || {
    echo "selftest: older prerequisite was accepted" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }

  # START_SHA plus an ancestor prerequisite is a valid boundary. An extra
  # prerequisite that is not an ancestor of START_SHA is rejected, and
  # nothing is pushed. The ancestor object has to be in the deliver
  # checkout (the workflow fetches the full history for this check).
  insert_prereq() {  # $1 src bundle, $2 dst, $3 sha
    python3 - "$1" "$2" "$3" <<'PY'
import pathlib, sys
src, dst, sha = sys.argv[1:]
data = pathlib.Path(src).read_bytes()
nl = data.find(b"\n\n")
if nl < 0:
    raise SystemExit("bundle header has no blank line")
header, rest = data[:nl], data[nl:]
pathlib.Path(dst).write_bytes(header + b"\n-" + sha.encode() + b" extra" + rest)
PY
  }
  local mbare mdel msha usha
  git_cmd -C "$asrc" bundle create "${tmp}/base-only.bundle" "^${astart}" refs/heads/claude/issue-853-nuggs-ladder
  insert_prereq "${tmp}/base-only.bundle" "${tmp}/ancestor-ok.bundle" "$aroot"
  mbare="${tmp}/mbare.git"
  mdel="${tmp}/mdel"
  git_cmd init -b main --bare "$mbare" >/dev/null
  git_cmd clone -b main "${tmp}/astart.git" "$mdel" >/dev/null
  bsha="$(sha256sum "${tmp}/ancestor-ok.bundle" | awk '{print $1}')"
  rm -f "${tmp}/pr.json" "${tmp}/comment.body"
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_REPO="$mdel" GH_TOKEN=test-token COMMENT_TOKEN=comment-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$mdel" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$astart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$mbare" \
    --bundle "${tmp}/ancestor-ok.bundle" --bundle-sha256 "$bsha" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || {
    echo "selftest: ancestor prerequisite bundle exited ${rc}" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  git_cmd --git-dir="$mbare" rev-parse refs/heads/claude/issue-853-nuggs-ladder >/dev/null || {
    echo "selftest: ancestor prerequisite bundle was not pushed" >&2
    exit 1
  }
  git_cmd -C "$mdel" checkout -b side >/dev/null
  git_cmd -C "$mdel" -c user.email=t@example.com -c user.name=t commit --allow-empty -m unrelated >/dev/null
  usha="$(git_cmd -C "$mdel" rev-parse HEAD)"
  git_cmd -C "$mdel" checkout main >/dev/null
  insert_prereq "${tmp}/base-only.bundle" "${tmp}/unrelated.bundle" "$usha"
  msha="$(sha256sum "${tmp}/unrelated.bundle" | awk '{print $1}')"
  local ubare
  ubare="${tmp}/ubare.git"
  git_cmd init -b main --bare "$ubare" >/dev/null
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$mdel" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$astart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$ubare" \
    --bundle "${tmp}/unrelated.bundle" --bundle-sha256 "$msha" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 1 ] || { echo "selftest: unrelated prerequisite bundle exited ${rc}" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep -q 'is not an ancestor of START_SHA' || {
    echo "selftest: unrelated prerequisite was accepted" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  if git_cmd --git-dir="$ubare" rev-parse refs/heads/claude/issue-853-nuggs-ladder >/dev/null 2>&1; then
    echo "selftest: unrelated prerequisite bundle was pushed" >&2
    exit 1
  fi

  # A protected-path commit inside an otherwise well-formed bundle is
  # refused after the fetch and is not pushed. Built with git directly so
  # --write-bundle's own refusal is not what we are measuring.
  git_cmd -C "$bsrc" checkout claude/issue-853-nuggs-ladder >/dev/null
  mkdir -p "$bsrc/scripts"
  printf 'nope\n' > "$bsrc/scripts/evil.sh"
  git_cmd -C "$bsrc" -c user.email=t@example.com -c user.name=t add -- scripts/evil.sh
  git_cmd -C "$bsrc" -c user.email=t@example.com -c user.name=t commit -m 'scripts touch' >/dev/null
  git_cmd -C "$bsrc" bundle create "${tmp}/protected.bundle" "^${bstart}" refs/heads/claude/issue-853-nuggs-ladder
  bsha="$(sha256sum "${tmp}/protected.bundle" | awk '{print $1}')"
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$bdel" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$bstart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$bbare" \
    --bundle "${tmp}/protected.bundle" --bundle-sha256 "$bsha" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 1 ] || { echo "selftest: protected-path bundle exited ${rc}" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep -q 'touches scripts/evil.sh' || {
    echo "selftest: protected-path bundle was not refused" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  [ "$(git_cmd --git-dir="$bbare" rev-parse refs/heads/claude/issue-853-nuggs-ladder)" = "$bhead" ] || {
    echo "selftest: protected-path bundle was pushed" >&2
    exit 1
  }
  [ "$(git_cmd -C "$bdel" rev-parse HEAD)" = "$bstart" ] || {
    echo "selftest: protected-path bundle moved the deliver checkout" >&2
    exit 1
  }

  # H1: the workflow restores the real script from START_SHA into a temp
  # dir outside the fixture repo and runs --write-bundle. The worktree
  # copy is poisoned. A missing DELIVER_WORKTREE and a worktree that is
  # not the git toplevel (a planted parent .git) both fail closed.
  local workflow deliver_run
  workflow="${repo_root}/.github/workflows/design-run.yml"
  deliver_run="$(awk '
    /^      - name: Bundle the design commits/ { in_step = 1 }
    in_step && /^        run: \|/ { printing = 1; next }
    in_step && printing && /^      - name:/ { exit }
    printing { print }
  ' "$workflow")"
  [ -n "$deliver_run" ] || { echo "selftest: could not extract the bundle run block" >&2; exit 1; }
  printf '%s\n' "$deliver_run" | grep -q '/usr/bin/git --no-replace-objects -c core.hooksPath=/dev/null -c core.fsmonitor=false -c core.sshCommand= show "$START_SHA:scripts/design-run-deliver.sh"' || {
    echo "selftest: bundle step does not git-show the pinned script" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep -q 'DELIVER_SHA256' || {
    echo "selftest: deliver step does not check the pre-agent sha256" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep -q 'objects/info/alternates' || {
    echo "selftest: deliver step does not refuse object alternates" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep -q 'GIT_ALTERNATE_OBJECT_DIRECTORIES' || {
    echo "selftest: deliver step does not drop GIT_ALTERNATE_OBJECT_DIRECTORIES" >&2
    exit 1
  }
  grep -q 'deliver_sha256=' "$workflow" || {
    echo "selftest: the pre-agent pin does not record deliver_sha256" >&2
    exit 1
  }
  grep -q 'DELIVER_WORKTREE: \${{ github.workspace }}' "$workflow" || {
    echo "selftest: deliver step does not pin DELIVER_WORKTREE to the checkout" >&2
    exit 1
  }
  grep -q 'shell: /usr/bin/bash --noprofile --norc' "$workflow" || {
    echo "selftest: deliver step does not pin an absolute shell" >&2
    exit 1
  }
  grep -q 'LD_PRELOAD: ""' "$workflow" || {
    echo "selftest: deliver step does not pin an empty LD_PRELOAD" >&2
    exit 1
  }
  grep -q 'BASH_ENV: ""' "$workflow" || {
    echo "selftest: deliver step does not pin an empty BASH_ENV" >&2
    exit 1
  }
  grep -q 'PATH: /usr/bin:/bin' "$workflow" || {
    echo "selftest: deliver step does not pin PATH to /usr/bin:/bin" >&2
    exit 1
  }
  grep -q 'GIT_CONFIG_GLOBAL: /dev/null' "$workflow" || {
    echo "selftest: deliver step does not pin GIT_CONFIG_GLOBAL=/dev/null" >&2
    exit 1
  }
  grep -q 'GIT_CONFIG_NOSYSTEM: "1"' "$workflow" || {
    echo "selftest: deliver step does not pin GIT_CONFIG_NOSYSTEM" >&2
    exit 1
  }
  grep -q 'NODE_OPTIONS: ""' "$workflow" || {
    echo "selftest: deliver step does not blank NODE_OPTIONS" >&2
    exit 1
  }
  grep -q 'PYTHONPATH: ""' "$workflow" || {
    echo "selftest: deliver step does not blank PYTHONPATH" >&2
    exit 1
  }
  grep -q 'GIT_SSH_COMMAND: ""' "$workflow" || {
    echo "selftest: deliver step does not blank GIT_SSH_COMMAND" >&2
    exit 1
  }
  grep -q 'GIT_DIR: ""' "$workflow" || {
    echo "selftest: deliver step does not blank GIT_DIR" >&2
    exit 1
  }
  grep -q 'GIT_WORK_TREE: ""' "$workflow" || {
    echo "selftest: deliver step does not blank GIT_WORK_TREE" >&2
    exit 1
  }
  grep -q 'GIT_BIN: /usr/bin/git' "$workflow" || {
    echo "selftest: deliver step does not pin GIT_BIN" >&2
    exit 1
  }
  grep -q 'actions/upload-artifact@v7' "$workflow" || {
    echo "selftest: the bundle is not uploaded" >&2
    exit 1
  }
  grep -q 'retention-days: 1' "$workflow" || {
    echo "selftest: the bundle artifact has no short retention" >&2
    exit 1
  }
  grep -q 'actions/download-artifact@v7' "$workflow" || {
    echo "selftest: the deliver job does not download the bundle" >&2
    exit 1
  }
  grep -q '\$GITHUB_WORKSPACE/scripts/design-run-deliver.sh' "$workflow" || {
    echo "selftest: the deliver job does not run the checkout script" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep -q -- '--write-bundle' || {
    echo "selftest: the bundle step does not pass --write-bundle" >&2
    exit 1
  }
  # The bundle step may read issue comments with the job token. The PAT
  # that can push stays on the deliver step; this run block must not see it.
  if printf '%s\n' "$deliver_run" | grep -q 'secrets.GH_TOKEN'; then
    echo "selftest: the bundle step run block mentions secrets.GH_TOKEN" >&2
    exit 1
  fi
  awk '
    /^      - name: Bundle the design commits/ { in_step = 1 }
    in_step && /^      - name: Upload the design bundle/ { exit }
    in_step { print }
  ' "$workflow" | grep -q 'GH_TOKEN: ${{ github.token }}' || {
    echo "selftest: the bundle step does not read comments with github.token" >&2
    exit 1
  }
  awk '
    /^      - name: Bundle the design commits/ { in_step = 1 }
    in_step && /^      - name: Upload the design bundle/ { exit }
    in_step { print }
  ' "$workflow" | grep -q 'JOB_WINDOW_START: ${{ steps.job_window.outputs.start }}' || {
    echo "selftest: the bundle step does not pin the job window from the step output" >&2
    exit 1
  }
  awk '
    /^  deliver:/ { in_d = 1 }
    in_d && /^  [a-zA-Z0-9_-]+:/ && !/^  deliver:/ { in_d = 0 }
    in_d && /fetch-depth: 0/ { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$workflow" || {
    echo "selftest: the deliver checkout does not fetch full history" >&2
    exit 1
  }
  if printf '%s\n' "$deliver_run" | grep -q 'GH_TOKEN'; then
    echo "selftest: the bundle step run block mentions GH_TOKEN" >&2
    exit 1
  fi
  printf '%s\n' "$deliver_run" | grep -q 'GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_OBJECT_DIRECTORY' || {
    echo "selftest: deliver step does not drop alternate object dirs" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep -q 'GIT_CONFIG_PARAMETERS' || {
    echo "selftest: deliver step does not drop GIT_CONFIG_PARAMETERS" >&2
    exit 1
  }
  grep -q 'git --no-replace-objects -c core.hooksPath=/dev/null checkout "$START_SHA" -- scripts/routine-lock-cleanup.sh' "$workflow" || {
    echo "selftest: lock-cleanup restore is missing --no-replace-objects and hooksPath" >&2
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

  h1_repo() {  # $1 dir. Commits THIS script, then poisons the worktree copy.
    local dir="$1"
    mkdir -p "$dir/scripts"
    cp "$SELF" "$dir/scripts/design-run-deliver.sh"
    chmod +x "$dir/scripts/design-run-deliver.sh"
    git_cmd -C "$dir" init -b main >/dev/null
    git_cmd -C "$dir" -c user.email=t@example.com -c user.name=t add -- scripts/design-run-deliver.sh
    git_cmd -C "$dir" -c user.email=t@example.com -c user.name=t commit -m trusted >/dev/null
    cat > "$dir/scripts/design-run-deliver.sh" <<'EOF'
#!/bin/sh
printf '%s\n' PWNED > "$H1_MARK"
exit 0
EOF
  }

  run_h1() {  # $1 dir, $2 runner temp, $3 mark, $4 sha256 mode (match|wrong|omit), $5 worktree (path|omit). Echoes the script's exit.
    local dir="$1" runner="$2" mark="$3" sha_mode="$4" wt_mode="$5" rc out want
    want="$(git_cmd -C "$dir" show "HEAD:scripts/design-run-deliver.sh" | sha256sum | awk '{print $1}')"
    set +e
    out="$(
      cd "$dir"
      START_SHA="$(git_cmd rev-parse HEAD)"
      export START_SHA RUNNER_TEMP="$runner" H1_MARK="$mark"
      export GITHUB_REPOSITORY=acme/print-bench ISSUE=853 BASE_BRANCH=main
      export RUN_URL=https://example.test/run/1
      export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
      case "$sha_mode" in
        match) export DELIVER_SHA256="$want" ;;
        wrong) export DELIVER_SHA256="0000000000000000000000000000000000000000000000000000000000000000" ;;
        omit) unset DELIVER_SHA256 || true ;;
      esac
      case "$wt_mode" in
        set) export DELIVER_WORKTREE="$dir" ;;
        omit) unset DELIVER_WORKTREE || true ;;
      esac
      bash -eo pipefail -c "$deliver_run" 2>&1
    )"
    rc=$?
    set -e
    # The workflow's ::error:: markers are real on a runner. Printed raw
    # inside check.sh they become job annotations, so the selftest rewrites
    # them after it has captured the exit code.
    printf '%s\n' "$out" | sed 's/::error::/error: /' > "${mark}.out"
    cat "${mark}.out" >&2
    printf '%s\n' "$rc"
  }

  # $1 script, $2 "-" to unset DELIVER_WORKTREE or an absolute path. Echoes rc.
  invoke_outside() {
    local script="$1" wt="$2" rc
    set +e
    if [ "$wt" = "-" ]; then
      env -u DELIVER_WORKTREE \
        GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
        GH_TOKEN=test-token \
        "$script" --repo acme/print-bench --issue 853 --base "$base" \
        --base-branch main --run-url https://example.test/run/1 --push-url "$bare" \
        >/dev/null 2>"${tmp}/outside.err"
    else
      env DELIVER_WORKTREE="$wt" \
        GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
        GH_TOKEN=test-token \
        "$script" --repo acme/print-bench --issue 853 --base "$base" \
        --base-branch main --run-url https://example.test/run/1 --push-url "$bare" \
        >/dev/null 2>"${tmp}/outside.err"
    fi
    rc=$?
    set -e
    printf '%s\n' "$rc"
  }

  local h1 mark runner poisoned rc canary outside plant plant_head git_dir
  local real_blob poison_blob plain_sha hard_sha
  h1="${tmp}/h1"
  mark="${tmp}/h1-mark"
  runner="${tmp}/h1-runner"
  mkdir -p "$runner"
  h1_repo "$h1"
  rc="$(run_h1 "$h1" "$runner" "$mark" match set)"
  [ "$rc" -eq 0 ] || { echo "selftest: H1 restore exited ${rc}" >&2; exit 1; }
  [ ! -e "$mark" ] || { echo "selftest: H1 ran the worktree script ($(cat "$mark"))" >&2; exit 1; }
  grep -q "not claude/issue-853-" "${mark}.out" || {
    echo "selftest: H1 did not execute the restored script" >&2
    exit 1
  }
  case "$runner" in
    "$h1"|"$h1"/*)
      echo "selftest: restored script is inside the fixture repo" >&2
      exit 1
      ;;
  esac
  if git_cmd -C "$runner" rev-parse --show-toplevel >/dev/null 2>&1; then
    echo "selftest: restored script dir is inside a git repo" >&2
    exit 1
  fi
  grep -q 'DELIVER_WORKTREE is required' "$runner/design-run-deliver.sh" || {
    echo "selftest: restored file is not the real script" >&2
    exit 1
  }
  [ "$(sha256sum "$runner/design-run-deliver.sh" | awk '{print $1}')" = \
    "$(git_cmd -C "$h1" show "HEAD:scripts/design-run-deliver.sh" | sha256sum | awk '{print $1}')" ] || {
    echo "selftest: restored file does not match the pinned blob" >&2
    exit 1
  }

  # The restored copy, run from outside any repo, with no DELIVER_WORKTREE.
  outside="${tmp}/outside"
  mkdir -p "$outside"
  cp "$runner/design-run-deliver.sh" "$outside/design-run-deliver.sh"
  chmod +x "$outside/design-run-deliver.sh"
  rc="$(invoke_outside "$outside/design-run-deliver.sh" -)"
  [ "$rc" -eq 1 ] || { echo "selftest: missing DELIVER_WORKTREE exited ${rc}, expected 1" >&2; exit 1; }
  grep -q 'DELIVER_WORKTREE is required' "${tmp}/outside.err" || {
    echo "selftest: missing DELIVER_WORKTREE did not fail closed" >&2
    cat "${tmp}/outside.err" >&2
    exit 1
  }

  # A planted parent .git. dirname($0)/.. is that repo; the script must not
  # walk up into it, and must not treat a nested directory as the checkout.
  plant="${tmp}/plant"
  mkdir -p "$plant/decoy"
  git_cmd -C "$plant" init -b main >/dev/null
  git_cmd -C "$plant" -c user.email=t@example.com -c user.name=t commit --allow-empty -m plant >/dev/null
  cp "$runner/design-run-deliver.sh" "$plant/decoy/design-run-deliver.sh"
  chmod +x "$plant/decoy/design-run-deliver.sh"
  plant_head="$(git_cmd -C "$plant" rev-parse HEAD)"
  rc="$(invoke_outside "$plant/decoy/design-run-deliver.sh" -)"
  [ "$rc" -eq 1 ] || { echo "selftest: planted parent without DELIVER_WORKTREE exited ${rc}" >&2; exit 1; }
  [ "$(git_cmd -C "$plant" rev-parse HEAD)" = "$plant_head" ] || {
    echo "selftest: planted parent moved HEAD" >&2
    exit 1
  }
  rc="$(invoke_outside "$plant/decoy/design-run-deliver.sh" "$plant/decoy")"
  [ "$rc" -eq 1 ] || { echo "selftest: nested DELIVER_WORKTREE exited ${rc}, expected 1" >&2; exit 1; }
  grep -q 'git toplevel is' "${tmp}/outside.err" || {
    echo "selftest: nested worktree was not refused" >&2
    cat "${tmp}/outside.err" >&2
    exit 1
  }
  [ "$(git_cmd -C "$plant" rev-parse HEAD)" = "$plant_head" ] || {
    echo "selftest: nested worktree moved the planted HEAD" >&2
    exit 1
  }
  set +e
  env GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    "$plant/decoy/design-run-deliver.sh" --selftest >/dev/null 2>"${tmp}/outside.err"
  rc=$?
  set -e
  [ "$rc" -ne 0 ] || { echo "selftest: --selftest ran from a copy inside a planted repo" >&2; exit 1; }
  grep -q 'refuses to run a copy outside the checkout' "${tmp}/outside.err" || {
    echo "selftest: outside-checkout --selftest did not refuse" >&2
    cat "${tmp}/outside.err" >&2
    exit 1
  }

  # Wrong or missing pre-agent sha256, and a missing DELIVER_WORKTREE in the
  # workflow step, all fail before the restored file is executed.
  rm -f "$mark"
  rc="$(run_h1 "$h1" "$runner" "$mark" wrong set)"
  [ "$rc" -ne 0 ] || { echo "selftest: wrong deliver sha256 was accepted" >&2; exit 1; }
  [ ! -e "$mark" ] || { echo "selftest: wrong sha256 executed the worktree script" >&2; exit 1; }
  rm -f "$mark"
  rc="$(run_h1 "$h1" "$runner" "$mark" omit set)"
  [ "$rc" -ne 0 ] || { echo "selftest: missing DELIVER_SHA256 was accepted" >&2; exit 1; }
  [ ! -e "$mark" ] || { echo "selftest: missing sha256 executed a script" >&2; exit 1; }
  rm -f "$mark"
  rc="$(run_h1 "$h1" "$runner" "$mark" match omit)"
  [ "$rc" -ne 0 ] || { echo "selftest: workflow accepted a missing DELIVER_WORKTREE" >&2; exit 1; }
  [ ! -e "$mark" ] || { echo "selftest: missing worktree executed a script" >&2; exit 1; }
  grep -q 'DELIVER_WORKTREE is empty' "${mark}.out" || {
    echo "selftest: workflow did not fail closed on an empty DELIVER_WORKTREE" >&2
    exit 1
  }

  # Object alternates are refused before git show.
  git_dir="$(git_cmd -C "$h1" rev-parse --git-dir)"
  case "$git_dir" in
    /*) ;;
    *) git_dir="$h1/$git_dir" ;;
  esac
  mkdir -p "${git_dir}/objects/info"
  printf '%s\n' "${tmp}/fake-alternates" > "${git_dir}/objects/info/alternates"
  rm -f "$mark"
  rc="$(run_h1 "$h1" "$runner" "$mark" match set)"
  [ "$rc" -ne 0 ] || { echo "selftest: object alternates were accepted" >&2; exit 1; }
  [ ! -e "$mark" ] || { echo "selftest: alternates executed a script" >&2; exit 1; }
  grep -q 'object alternates are present' "${mark}.out" || {
    echo "selftest: alternates refusal was not reported" >&2
    exit 1
  }
  rm -f "${git_dir}/objects/info/alternates"

  # A replace ref swaps the blob for a plain git show. --no-replace-objects
  # keeps the pinned bytes, so the restored file is still the real script.
  real_blob="$(git_cmd -C "$h1" rev-parse "HEAD:scripts/design-run-deliver.sh")"
  poison_blob="$(git_cmd -C "$h1" hash-object -w -- "$h1/scripts/design-run-deliver.sh")"
  git_cmd -C "$h1" replace "$real_blob" "$poison_blob"
  plain_sha="$(GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null git -C "$h1" show "HEAD:scripts/design-run-deliver.sh" | sha256sum | awk '{print $1}')"
  hard_sha="$(git_cmd -C "$h1" show "HEAD:scripts/design-run-deliver.sh" | sha256sum | awk '{print $1}')"
  [ "$plain_sha" != "$hard_sha" ] || {
    echo "selftest: replace ref did not change an unhardened git show" >&2
    exit 1
  }
  rm -f "$mark"
  rc="$(run_h1 "$h1" "$runner" "$mark" match set)"
  [ "$rc" -eq 0 ] || { echo "selftest: replace ref broke the hardened restore (${rc})" >&2; exit 1; }
  [ ! -e "$mark" ] || { echo "selftest: replace ref executed the poison script" >&2; exit 1; }
  grep -q 'DELIVER_WORKTREE is required' "$runner/design-run-deliver.sh" || {
    echo "selftest: replace ref restored the poison blob" >&2
    exit 1
  }
  git_cmd -C "$h1" replace -d "$real_blob"

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
  rc="$(run_h1 "$h1" "$runner" "$mark" match set)"
  [ "$rc" -ne 0 ] || { echo "selftest: symlinked scripts/ was accepted" >&2; exit 1; }
  [ ! -e "$mark" ] || { echo "selftest: symlinked scripts/ executed a script" >&2; exit 1; }

  # The script path itself as a symlink.
  rm -rf "$h1"
  h1_repo "$h1"
  rm -f "$h1/scripts/design-run-deliver.sh"
  ln -s "$poisoned/design-run-deliver.sh" "$h1/scripts/design-run-deliver.sh"
  rm -f "$mark"
  rc="$(run_h1 "$h1" "$runner" "$mark" match set)"
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
  rc="$(run_h1 "$h1" "$runner" "$mark" match set)"
  [ "$rc" -eq 0 ] || { echo "selftest: restore over a dest symlink exited ${rc}" >&2; exit 1; }
  [ "$(cat "$canary")" = "CANARY" ] || {
    echo "selftest: dest symlink was followed ($(cat "$canary"))" >&2
    exit 1
  }
  [ ! -L "$runner/design-run-deliver.sh" ] && [ -f "$runner/design-run-deliver.sh" ] || {
    echo "selftest: restored script is not a regular file" >&2
    exit 1
  }
  [ ! -e "$mark" ] || { echo "selftest: dest-symlink restore ran untrusted code" >&2; exit 1; }
  grep -q 'DELIVER_WORKTREE is required' "$runner/design-run-deliver.sh" || {
    echo "selftest: dest-symlink restore did not write the real script" >&2
    exit 1
  }

  # A declined / decision-needed / deferred stop must not write a bundle
  # and must not push one that already exists. An outsider's copy of the
  # marker is not this firing's stop (the lock-cleanup author gate).
  stop_case() {  # $1 name, $2 comment NDJSON, $3 refuse|deliver
    local name="$1" comments="$2" kind="$3"
    local sdir sbare sdel sfile sstart rc stderr
    sdir="${tmp}/stop-${name}"
    sbare="${tmp}/stop-${name}.git"
    sdel="${tmp}/stop-${name}-del"
    sfile="${tmp}/stop-${name}.bundle"
    rm -rf "$sdir" "$sbare" "$sdel" "$sfile"
    mkdir -p "$sdir/designs/nuggs-ladder" "$sdir/scripts"
    cp "$(dirname "$SELF")/routine-lock-cleanup.sh" "$sdir/scripts/routine-lock-cleanup.sh"
    git_cmd -C "$sdir" init -b main >/dev/null
    git_cmd -C "$sdir" add -- scripts/routine-lock-cleanup.sh
    git_cmd -C "$sdir" -c user.email=t@example.com -c user.name=t commit -m start >/dev/null
    sstart="$(git_cmd -C "$sdir" rev-parse HEAD)"
    git_cmd -C "$sdir" checkout -b claude/issue-853-nuggs-ladder >/dev/null
    printf 'wip\n' > "$sdir/designs/nuggs-ladder/nuggs-ladder.scad"
    git_cmd -C "$sdir" add -- designs/nuggs-ladder/nuggs-ladder.scad
    git_cmd -C "$sdir" -c user.email=t@example.com -c user.name=t commit -m wip >/dev/null
    printf '%s\n' "$comments" > "${tmp}/comments.ndjson"
    set +e
    stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
      JOB_WINDOW_START=2026-10-19T00:00:00Z \
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
      DELIVER_WORKTREE="$sdir" \
      "$SELF" --repo acme/print-bench --issue 853 --base "$sstart" \
      --base-branch main --run-url https://example.test/run/1 \
      --write-bundle "$sfile" 2>&1 >/dev/null)"
    rc=$?
    set -e
    if [ "$kind" = "refuse" ]; then
      [ "$rc" -eq 0 ] || { echo "selftest: ${name} write-bundle exited ${rc}" >&2; printf '%s\n' "$stderr" >&2; exit 1; }
      [ ! -e "$sfile" ] || { echo "selftest: ${name} wrote a bundle" >&2; exit 1; }
      printf '%s\n' "$stderr" | grep -q 'stop from this run — nothing pushed' || {
        echo "selftest: ${name} did not report the stop" >&2
        printf '%s\n' "$stderr" >&2
        exit 1
      }
      # A bundle built before the stop comment is visible must still not
      # be pushed once the comment is on the thread.
      rm -f "${tmp}/comments.ndjson" "$sfile"
      env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
        JOB_WINDOW_START=2026-10-19T00:00:00Z \
        GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
        DELIVER_WORKTREE="$sdir" \
        "$SELF" --repo acme/print-bench --issue 853 --base "$sstart" \
        --base-branch main --run-url https://example.test/run/1 \
        --write-bundle "$sfile" >/dev/null
      [ -f "$sfile" ] || { echo "selftest: ${name} could not build the control bundle" >&2; exit 1; }
      printf '%s\n' "$comments" > "${tmp}/comments.ndjson"
      git_cmd init -b main --bare "$sbare" >/dev/null
      git_cmd -C "$sdir" push "$sbare" "${sstart}:refs/heads/main" >/dev/null
      git_cmd clone -b main "$sbare" "$sdel" >/dev/null
      bsha="$(sha256sum "$sfile" | awk '{print $1}')"
      rm -f "${tmp}/pr.json" "${tmp}/comment.body"
      set +e
      stderr="$(env GH_BIN="${tmp}/bin/gh" GH_REPO="$sdel" GH_TOKEN=test-token COMMENT_TOKEN=comment-token \
        JOB_WINDOW_START=2026-10-19T00:00:00Z \
        GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
        DELIVER_WORKTREE="$sdel" \
        "$SELF" --repo acme/print-bench --issue 853 --base "$sstart" \
        --base-branch main --run-url https://example.test/run/1 --push-url "$sbare" \
        --bundle "$sfile" --bundle-sha256 "$bsha" 2>&1 >/dev/null)"
      rc=$?
      set -e
      [ "$rc" -eq 0 ] || { echo "selftest: ${name} deliver exited ${rc}" >&2; printf '%s\n' "$stderr" >&2; exit 1; }
      if git_cmd --git-dir="$sbare" rev-parse refs/heads/claude/issue-853-nuggs-ladder >/dev/null 2>&1; then
        echo "selftest: ${name} pushed a branch" >&2
        exit 1
      fi
      if [ -f "${tmp}/comment.body" ] && grep -q 'design-run delivered' "${tmp}/comment.body"; then
        echo "selftest: ${name} posted a delivery comment" >&2
        exit 1
      fi
      if [ -f "${tmp}/pr.json" ]; then
        echo "selftest: ${name} opened a pull request" >&2
        exit 1
      fi
    else
      [ "$rc" -eq 0 ] && [ -f "$sfile" ] || {
        echo "selftest: outsider stop blocked the bundle (exit ${rc})" >&2
        printf '%s\n' "$stderr" >&2
        exit 1
      }
    fi
    rm -f "${tmp}/comments.ndjson"
  }
  stop_case declined "$(cat <<'EOF'
{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-10-19T00:30:00Z", "login": "acme", "type": "User"}
{"body": "🚢 DECLINED — needs a decision\n\nstop", "created_at": "2026-10-19T01:00:00Z", "login": "acme", "type": "User"}
EOF
)" refuse
  stop_case decision "$(cat <<'EOF'
{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-10-19T00:30:00Z", "login": "acme", "type": "User"}
{"body": "🚦 DECISION NEEDED — `bay-width`\n\nparked", "created_at": "2026-10-19T01:00:00Z", "login": "acme", "type": "User"}
EOF
)" refuse
  stop_case deferred "$(cat <<'EOF'
{"body": "🚢 DEFERRED (re-check) — dependencies still not landed.\n\nwaiting", "created_at": "2026-10-19T01:00:00Z", "login": "acme", "type": "User"}
EOF
)" refuse
  stop_case outsider "$(cat <<'EOF'
{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-10-19T00:30:00Z", "login": "acme", "type": "User"}
{"body": "🚢 DECLINED — needs a decision\n\nspoof", "created_at": "2026-10-19T01:00:00Z", "login": "attacker", "type": "User"}
EOF
)" deliver

  echo "design-run-deliver selftest: ok"
}

REPO="" ISSUE="" BASE="" BASE_BRANCH="" RUN_URL="" PUSH_URL="" BRANCH="" ASKPASS=""
BUNDLE="" BUNDLE_SHA256="" WRITE_BUNDLE="" DELIVER_REF="HEAD"

if [ "${1:-}" = "--selftest" ]; then
  # Only the in-repo file may run the suite. A restored copy lives outside
  # the checkout; walking up from its path would land in a parent git dir.
  script_dir="$(cd "$(dirname "$SELF")" >/dev/null 2>&1 && pwd)"
  repo_root="$(git_cmd -C "$script_dir" rev-parse --show-toplevel)"
  if [ "$SELF" != "${repo_root}/scripts/design-run-deliver.sh" ]; then
    echo "design-run-deliver: --selftest refuses to run a copy outside the checkout" >&2
    exit 1
  fi
  selftest "$repo_root"
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
    --bundle) BUNDLE="${2:-}"; shift 2 ;;
    --bundle-sha256) BUNDLE_SHA256="${2:-}"; shift 2 ;;
    --write-bundle) WRITE_BUNDLE="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) usage "unknown argument: $1" ;;
  esac
done

[ -n "$REPO" ] && [ -n "$ISSUE" ] && [ -n "$BASE" ] && [ -n "$BASE_BRANCH" ] && [ -n "$RUN_URL" ] \
  || usage "missing required argument"
if [ -n "$WRITE_BUNDLE" ] && [ -n "$BUNDLE" ]; then
  usage "pass only one of --bundle and --write-bundle"
fi
if [ -n "$BUNDLE" ] && [ -z "$BUNDLE_SHA256" ]; then
  usage "--bundle requires --bundle-sha256"
fi
[ -z "$PUSH_URL" ] && PUSH_URL="https://github.com/${REPO}.git"

run_live
