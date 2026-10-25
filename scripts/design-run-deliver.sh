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
# is executed. Then:
#   1. Only a branch named claude/issue-<N>-* is eligible. main is never
#      pushed.
#   2. Uncommitted files under designs/ and first-party lib/ are committed
#      onto that branch. Vendored trees, scripts/, .github/, **/.claude/
#      and tools/ are not. A path already staged that is not one of those
#      safe paths is unstaged before the commit; if it is still staged, the
#      commit is refused. `git commit` records the whole index.
#   3. Any commit since the job's start SHA that touches .github/, scripts/,
#      **/.claude/ (any depth) or tools/ — including a path added and later
#      deleted, the pre-image of a rename, a commit brought in by merging
#      main, or a change made inside a merge commit and removed by a later
#      merge — refuses the push. The bundle must list START_SHA as a
#      prerequisite. Every other prerequisite must pass
#      `git merge-base --is-ancestor <p> START_SHA` in this script.
#   4. An open non-draft PR on the branch refuses the push. auto-arm.yml
#      arms auto-merge on non-draft claude/* PRs.
#   5. The branch is pushed and `git ls-remote` must return the local tip.
#   6. An open same-repo draft PR whose headRefOid is that tip and whose
#      body closes #<N> must exist (this step opens a draft when none does).
#   7. Only then is the success comment posted. A failed push or a PR that
#      does not qualify posts nothing that reads as success.
#   8. A this-run hard stop on the issue — a first-line 🚢 DECLINED,
#      🚦 DECISION NEEDED, or 🚢 DEFERRED, the same markers and author/window
#      test as routine-lock-cleanup.sh — writes no bundle, pushes nothing,
#      and posts no success comment. Lock cleanup then scores the run
#      declined. The stop is read before the commit and again before the push.
#      The agent job carries no issues: write (issue #862), so the stop also
#      arrives as an intents file: a stop-marker first line on a comment
#      intent targeting the selected issue suppresses the bundle the same way.
#   9. Issue intents. Unattended, the agent cannot write the issue thread at
#      all — its token is issues: read — so the /design-run protocol has it
#      declare its owed comments and labels in an untracked worktree file,
#      .design-run-intents.json ({"version":1,"intents":[{issue,action,body}
#      for comments and {issue,action,label} for labels]}). This file never
#      rides the git bundle: a declined run writes no bundle to ride, and a
#      committed copy would reach main through the delivered PR and poison
#      later runs with a stale stop. Instead the trusted bundle step copies
#      it (--write-intents), the workflow uploads it as the
#      design-run-intents artifact under the same reap-and-digest discipline
#      as the bundle, and settle applies it (--apply-intents). The applier is
#      the only issue-writing surface in the pipeline after #862: an intent
#      is posted only when it targets the SELECTED issue, only with a label
#      from the allowlist (needs-decision — never design-brief or
#      autonomy-ok), and only within per-run caps (8 KiB/comment body,
#      64 KiB payload). Bare ASCII SHIP-LOCK first lines and HTML comment
#      markers are rejected. Off-issue and non-allowlisted intents are
#      dropped with a ::warning::, never posted. A stop-marker intent
#      defers the settle SHIP-LOCK and skips it only after a validated
#      stop comment actually posts; a rejected or failed stop falls back
#      to posting the lock (Cipher L2, #884).
#
# Usage:
#   scripts/design-run-deliver.sh --repo <owner/name> --issue <N> \
#       --base <sha> --base-branch <name> --run-url <url> \
#       [--push-url <url>] [--routine <design-run|backlog-burn>]
#   scripts/design-run-deliver.sh --selftest
#
# The routine parameter adapts the per-routine wording and the *safe*
# commit surface only (issues #863 / #869): design-run (the default, and
# the behavior before the flag existed) delivers a design — only designs/
# and single-file lib/ modules may be committed — while backlog-burn runs
# /ship-issue and may commit any non-protected path (docs/, designs/,
# people/, …). Both routines refuse the same protected prefixes —
# `.github/**`, `**/.claude/**` (any depth), `scripts/**`, `tools/**` —
# and agent-instruction paths at ANY depth after case-folding
# normalization: `**/CLAUDE.md`, `**/CLAUDE.local.md`, `**/AGENTS.md`,
# `**/.mcp.json`, `**/.cursor/**`, `**/.cursorrules` — because a delivered
# workflow, hook, CI script or agent instruction file would run with repo
# secrets on the next push or agent session (Cipher on #869 / #879).
# Symlinks (including absolute targets), case folding, `../`, backslashes
# and gitlinks that land under a protected path are refused the same way.
# An unknown routine is a usage error.
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
ROUTINE='design-run'

usage() {
  [ $# -eq 0 ] || echo "design-run-deliver: $*" >&2
  cat >&2 <<'EOF'
usage: scripts/design-run-deliver.sh --repo <owner/name> --issue <N>
           --base <sha> --base-branch <name> --run-url <url>
           [--push-url <url>] [--routine <design-run|backlog-burn>]
           [--write-bundle <path> [--write-intents <path>]
            | --bundle <path> --bundle-sha256 <hex>]
           [--apply-intents <path>]
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
# at a global config. GIT_LITERAL_PATHSPECS=1 makes every pathspec argument
# literal (issue #879): without it, a root-level name like `:^y` is pathspec
# magic for `ls-tree`/`add`/`reset`/`ls-files`/`diff`, so a symlink
# `:^y -> .claude/x` skips the protected-target lookup. All path arguments
# in this file are repo paths from status/diff, never intentional magic, so
# literal mode is the safe default for add/reset/ls-files/diff/ls-tree alike.
# --no-verify is passed only to the subcommands that accept it (commit, push,
# merge, rebase, am). status, diff, config, log, ls-remote, add, rev-list,
# cat-file, show, bundle and fetch exit 129 or 128 when given --no-verify,
# so those get the hardening -c flags alone. rev-parse treats --no-verify as
# the negation of --verify.
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
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_LITERAL_PATHSPECS=1 \
        "$GIT_BIN" --no-replace-objects "${pre[@]}" \
        -c core.hooksPath=/dev/null \
        -c core.fsmonitor=false \
        -c commit.gpgSign=false \
        -c core.sshCommand= \
        "$sub" --no-verify "$@" ;;
    *)
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_LITERAL_PATHSPECS=1 \
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

# Normalize a repo-relative path for protected-prefix matching: lowercase,
# strip empty/`.` segments, resolve `..`. Prints the normalized path.
# Returns 1 (and prints nothing) when the path is not a safe repo-relative
# name — absolute, backslash, NUL/newline, or a `..` that escapes the root.
# Callers fail closed: a failed normalize is treated as protected.
normalize_repo_path() {
  local raw="$1" part
  local -a parts out
  case "$raw" in
    ''|*$'\n'*|*$'\r'*|/*|[A-Za-z]:*|*$'\\'*) return 1 ;;
  esac
  raw="$(printf '%s' "$raw" | tr 'A-Z' 'a-z')"
  IFS=/ read -r -a parts <<< "$raw" || true
  out=()
  for part in "${parts[@]}"; do
    case "$part" in
      ''|'.') continue ;;
      '..')
        if [ "${#out[@]}" -eq 0 ]; then
          return 1
        fi
        out=("${out[@]:0:${#out[@]}-1}")
        ;;
      *) out+=("$part") ;;
    esac
  done
  local IFS=/
  printf '%s\n' "${out[*]}"
}

# Return 0 when $1 is a protected delivery path after normalization
# (case, `./`, `../`). Protected:
#   prefixes: `.github`, `scripts`, `tools` (repo-root)
#   `**/.claude/**` at ANY depth (issue #879; a nested agent tree is as
#     dangerous as the root one — e.g. `docs/.claude/skills/...`)
#   agent-instruction files at ANY depth (bash `case` `*` matches `/`):
#     `**/CLAUDE.md`, `**/CLAUDE.local.md`, `**/AGENTS.md`, `**/.mcp.json`,
#     `**/.cursorrules`, and `**/.cursor/**`
# Filenames/dirs are matched lowercased because normalize_repo_path folds
# case. Fail closed: an unnormalizable path counts as protected (issue #869).
is_protected_path() {
  local norm
  norm="$(normalize_repo_path "$1")" || return 0
  case "$norm" in
    .github|.github/*|scripts|scripts/*|tools|tools/*) return 0 ;;
    # agent-instruction-path-drift (issue #869 / #879): any-depth, case-folded.
    # Keep these patterns in sync with the drift guard in
    # tools/model-registry/tests/test_workflow_drift.py.
    .claude|.claude/*|*/.claude|*/.claude/*) return 0 ;;
    claude.md|*/claude.md) return 0 ;;
    claude.local.md|*/claude.local.md) return 0 ;;
    agents.md|*/agents.md) return 0 ;;
    .mcp.json|*/.mcp.json) return 0 ;;
    .cursorrules|*/.cursorrules) return 0 ;;
    .cursor|.cursor/*|*/.cursor|*/.cursor/*) return 0 ;;
    *) return 1 ;;
  esac
}

# Return 0 when symlink at repo path $1 with target $2 resolves under a
# protected prefix. Absolute targets and unnormalizable joins fail closed.
symlink_points_under_protected() {
  local path="$1" target="$2" base joined
  [ -n "$target" ] || return 1
  case "$target" in
    /*|[A-Za-z]:*|*$'\\'*) return 0 ;;
  esac
  base="$(dirname -- "$path")"
  if [ "$base" = "." ]; then
    joined="$target"
  else
    joined="${base}/${target}"
  fi
  is_protected_path "$joined"
}

# Paths the delivery commit may include. A first-party module is a single
# file under lib/. A lib subdirectory is a vendored third-party tree and
# stays on the runner. Both routines refuse the protected prefixes
# (`.github/**`, `**/.claude/**`, `scripts/**`, `tools/**`) and agent-
# instruction paths at any depth (`**/CLAUDE.md`, `**/CLAUDE.local.md`,
# `**/AGENTS.md`, `**/.mcp.json`, `**/.cursor/**`, `**/.cursorrules`) —
# a workflow, hook, CI script or instruction file pushed with the PAT
# runs with repo secrets on the next check or agent session (issues
# #863 / #869 / #879). backlog-burn may still commit any other non-protected
# path (docs/, designs/, people/, …); design-run stays designs/ +
# single-file lib/ only.
safe_path() {
  local target
  if is_protected_path "$1"; then
    return 1
  fi
  # A worktree symlink whose target resolves under a protected prefix
  # (e.g. docs/hook -> ../.claude/hooks/evil.sh) must not be staged.
  if [ -L "$1" ]; then
    target="$(readlink -- "$1" 2>/dev/null || true)"
    if symlink_points_under_protected "$1" "$target"; then
      return 1
    fi
  fi
  case "$ROUTINE" in
    design-run) ;;
    backlog-burn) return 0 ;;
  esac
  case "$1" in
    designs/*) return 0 ;;
    lib|lib/|lib/*/*) return 1 ;;
    lib/*) return 0 ;;
    *) return 1 ;;
  esac
}

# Paths a commit since the start SHA must not touch. Both routines refuse
# the same protected prefixes after normalization (case / `../` / symlink
# target / gitlink path). refuse_open_nondraft, the delivery pin and CI
# still apply on top. The intents file (.design-run-intents.json) is also
# forbidden on every routine (case-folded like the other protected names):
# it is a run-scoped handoff to settle, never repo state — a committed
# copy would ride the delivered PR onto main and poison every later run
# on that branch with a stale stop intent (#862).
forbidden_path() {
  local norm
  norm="$(normalize_repo_path "$1")" || return 0
  case "$norm" in
    .design-run-intents.json) return 0 ;;
  esac
  is_protected_path "$1"
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

# Drop every staged path `safe_path` rejects. `git commit` writes the
# whole index, so a path the agent staged and did not commit (CLAUDE.md,
# README.md, a vendored tree) would otherwise ride out under the
# github-actions[bot] identity. A rename is unstaged on both sides when
# either side is unsafe. Returns 1 when an unsafe path is still staged.
unstage_unsafe_index() {
  local status path new staged
  staged="$(mktemp)"
  git_cmd diff --cached --name-status -z > "$staged"
  while IFS= read -r -d '' status || [ -n "${status:-}" ]; do
    [ -n "$status" ] || continue
    IFS= read -r -d '' path || {
      rm -f "$staged"
      echo "design-run-deliver: truncated staged name-status record (${status})" >&2
      return 1
    }
    case "$status" in
      R*|C*)
        IFS= read -r -d '' new || {
          rm -f "$staged"
          echo "design-run-deliver: truncated staged rename record for ${path}" >&2
          return 1
        }
        if ! safe_path "$path" || ! safe_path "$new"; then
          git_cmd reset -q -- "$path" "$new" || {
            rm -f "$staged"
            echo "design-run-deliver: could not unstage ${path} -> ${new}" >&2
            return 1
          }
        fi
        ;;
      *)
        if ! safe_path "$path"; then
          git_cmd reset -q -- "$path" || {
            rm -f "$staged"
            echo "design-run-deliver: could not unstage ${path}" >&2
            return 1
          }
        fi
        ;;
    esac
  done < "$staged"
  rm -f "$staged"
  staged="$(mktemp)"
  git_cmd diff --cached --name-status -z > "$staged"
  while IFS= read -r -d '' status || [ -n "${status:-}" ]; do
    [ -n "$status" ] || continue
    IFS= read -r -d '' path || {
      rm -f "$staged"
      echo "design-run-deliver: truncated staged name-status record (${status})" >&2
      return 1
    }
    case "$status" in
      R*|C*)
        IFS= read -r -d '' new || {
          rm -f "$staged"
          echo "design-run-deliver: truncated staged rename record for ${path}" >&2
          return 1
        }
        if ! safe_path "$path" || ! safe_path "$new"; then
          rm -f "$staged"
          echo "design-run-deliver: refusing to commit; index still has ${path} -> ${new}" >&2
          return 1
        fi
        ;;
      *)
        if ! safe_path "$path"; then
          rm -f "$staged"
          echo "design-run-deliver: refusing to commit; index still has ${path}" >&2
          return 1
        fi
        ;;
    esac
  done < "$staged"
  rm -f "$staged"
}

# Commit eligible dirty files onto the current branch. No-op when none.
# Porcelain is NUL-delimited so a quoted path (spaces, quotes) cannot
# split or trip `set -e` the way a line-oriented `read` does at EOF.
# A rename/copy record is `XY SP <new>\0<old>\0`; both sides are staged
# when each is a safe path. Anything else already in the index is
# unstaged first; the commit is refused if an unsafe path remains.
commit_safe_dirty() {
  local entry xy path old status_file
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
      fi
    fi
    if [ -n "$old" ] && safe_path "$old"; then
      if [ -e "$old" ] || [ -L "$old" ] || git_cmd ls-files --error-unmatch -- "$old" >/dev/null 2>&1; then
        git_cmd add -A -- "$old"
      fi
    fi
  done < "$status_file"
  rm -f "$status_file"
  if ! unstage_unsafe_index; then
    return 1
  fi
  # Nothing safe left in the index (the only dirty files were unsafe, or
  # there was nothing to add). Do not commit.
  if git_cmd diff --cached --quiet; then
    return 0
  fi
  git_cmd -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
      -c user.name="github-actions[bot]" \
      commit -m "$COMMIT_SUBJECT"
  note "committed uncommitted files onto ${BRANCH} before push"
}

# `git diff BASE...HEAD` is the merge-base diff (what the branch changed
# since it left START_SHA). It hides a path that was added and then deleted,
# and a rename's old name. `git log -z -m --name-status` catches both. -m
# diffs a merge against each parent, so a protected path introduced inside
# a merge and removed by a later merge is still listed. The NUL records
# keep a newline inside a path from splitting the record.
# If $2 exists at $1 as a symlink whose target resolves under a protected
# prefix, or as a gitlink (mode 160000) whose path is protected, print a
# refusal and return 1. Missing / ordinary-blob paths are fine.
# ls-tree pathspecs are literal via git_cmd's GIT_LITERAL_PATHSPECS=1
# (issue #879). Fail closed on a non-zero ls-tree: an empty lookup used to
# skip the check, which is how a pathspec-magic name bypassed it.
refuse_symlink_or_gitlink_into_protected() {
  local tip="$1" path="$2" meta mode target
  if ! meta="$(git_cmd ls-tree -z "$tip" -- "$path" 2>/dev/null | tr '\0' '\n' | head -n 1)"; then
    echo "design-run-deliver: ${BASE}..HEAD ls-tree failed for ${path} — refusing to push" >&2
    return 1
  fi
  [ -n "$meta" ] || return 0
  mode="${meta%% *}"
  case "$mode" in
    160000)
      if is_protected_path "$path"; then
        echo "design-run-deliver: ${BASE}..HEAD gitlink ${path} is under a protected prefix — refusing to push" >&2
        return 1
      fi
      return 0
      ;;
    120000)
      target="$(git_cmd cat-file -p "${tip}:${path}" 2>/dev/null || true)"
      [ -n "$target" ] || return 0
      if symlink_points_under_protected "$path" "$target"; then
        echo "design-run-deliver: ${BASE}..HEAD symlink ${path} -> ${target} points under a protected prefix — refusing to push" >&2
        return 1
      fi
      return 0
      ;;
    *) return 0 ;;
  esac
}

refuse_forbidden_range() {  # $1 tip ref, default HEAD
  local tip="${1:-HEAD}"
  local path status old new diff_file log_file
  diff_file="$(mktemp)"
  log_file="$(mktemp)"
  git_cmd diff --name-only -z "${BASE}...${tip}" > "$diff_file"
  git_cmd log -z -m --name-status --find-renames --pretty=format: "${BASE}..${tip}" > "$log_file"
  while IFS= read -r -d '' path || [ -n "${path:-}" ]; do
    [ -n "$path" ] || continue
    if forbidden_path "$path"; then
      rm -f "$diff_file" "$log_file"
      echo "design-run-deliver: ${BASE}...HEAD touches ${path} — refusing to push" >&2
      return 1
    fi
    if ! refuse_symlink_or_gitlink_into_protected "$tip" "$path"; then
      rm -f "$diff_file" "$log_file"
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
        if ! refuse_symlink_or_gitlink_into_protected "$tip" "$old" \
            || ! refuse_symlink_or_gitlink_into_protected "$tip" "$new"; then
          rm -f "$diff_file" "$log_file"
          return 1
        fi
        ;;
      *)
        if forbidden_path "$path"; then
          rm -f "$diff_file" "$log_file"
          echo "design-run-deliver: ${BASE}..HEAD touches ${path} — refusing to push" >&2
          return 1
        fi
        if ! refuse_symlink_or_gitlink_into_protected "$tip" "$path"; then
          rm -f "$diff_file" "$log_file"
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

Draft opened by the ${ROUTINE} delivery step after it verified \`${BRANCH}\` on the remote. The agent run ended without opening a PR; the gate evidence is the commits on this branch.
EOF
  title="$(git_cmd log -1 --format=%s "$DELIVER_REF")"
  title="${title:-$PR_TITLE_FALLBACK}"
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

# Same first-line markers routine-lock-cleanup.sh treats as this firing's
# stop. A previous run's comment must not vouch for this one, and an
# outsider on a public issue must not be able to suppress delivery.
STOP_MARKER_DECLINED='🚢 DECLINED'
STOP_MARKER_DECISION='🚦 DECISION NEEDED'
STOP_MARKER_DEFERRED='🚢 DEFERRED'
# Visible first line for humans. A comment is a lock ONLY when it also
# carries SHIP_LOCK_HTML_MARKER and is authored by SHIP_LOCK_AUTHOR_LOGIN —
# never because it merely starts with this string (Cipher, #864).
STOP_LOCK_MARKER='🚢 SHIP-LOCK'
# Hidden authenticity marker. Settle's lock writer emits it; intents reject
# `<!--` so an applied intent can never forge a lock.
SHIP_LOCK_HTML_MARKER='<!-- design-run-ship-lock:v1 -->'
# Exact GitHub logins that may author a lock (space-separated; no generic
# "[bot]" match). Cipher, #864:
#   github-actions[bot] — settle apply-intents (GH_TOKEN=${{ github.token }})
#   shaiss              — attended hand-run / PAT (repo owner)
# cursor[bot] is NOT listed (shared Cursor App login — Bugbot, Security/
# Approval Agents, every Cursor cloud agent). Attended runs post as shaiss
# or not at all. backlog-burn can also post as shaiss (#872).
SHIP_LOCK_AUTHOR_LOGINS='github-actions[bot] shaiss'
# Constant settle-claim body — built here, never from intent text.
SHIP_LOCK_SETTLE_BODY="${STOP_LOCK_MARKER} — settle claim

${SHIP_LOCK_HTML_MARKER}
"

# The agent's issue intents (item 9 above). The file name is the contract
# with .claude/skills/design-run/SKILL.md and .gitignore; it is also in the
# forbidden_path set so a committed copy refuses delivery.
INTENTS_FILENAME='.design-run-intents.json'
# Labels an intent may set, ever. design-brief and autonomy-ok are the
# opt-in labels this pipeline exists to keep out of the agent's hands.
INTENTS_ALLOWLIST='needs-decision'
INTENTS_MAX_COMMENTS=8
INTENTS_MAX_LABELS=2
INTENTS_MAX_ENTRIES=32
# Worktree / apply payload ceiling (64 KiB). write_intents drops an
# oversize copy; apply_intents fails closed (Cipher LOW, #864).
INTENTS_MAX_BYTES=65536
# Per-comment body cap on apply (8 KiB). Fail closed per intent.
INTENTS_BODY_MAX=8192

# Normalize an intent comment body (stdin → stdout): Unicode NFKC, strip
# every Cf (format) character including zero-width joiners/BOM, then
# collapse whitespace per line. Exit 1 on any failure (fail closed).
normalize_intent_body() {
  python3 -c '
import re, sys, unicodedata
try:
    text = unicodedata.normalize("NFKC", sys.stdin.read())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    out = []
    for line in text.splitlines():
        out.append(re.sub(r"\s+", " ", line.strip()))
    sys.stdout.write("\n".join(out))
except Exception as exc:
    print("normalize_intent_body: %s" % (exc,), file=sys.stderr)
    sys.exit(1)
'
}

# Return 0 when the normalized body (stdin) has any line matching
# /ship[\s_-]*lock/i — the lock-spoof forms intents must never post.
normalized_body_has_ship_lock() {
  python3 -c '
import re, sys
pat = re.compile(r"ship[\s_-]*lock", re.I)
text = sys.stdin.read()
sys.exit(0 if any(pat.search(line) for line in text.splitlines()) else 1)
'
}

# Post the settle SHIP-LOCK claim. Body is the SHIP_LOCK_SETTLE_BODY
# constant — never intent text. Intents cannot forge the HTML marker.
post_settle_ship_lock() {
  local token="${COMMENT_TOKEN:-${GH_TOKEN:-}}"
  if [ -z "$token" ]; then
    echo "design-run-deliver: no token to post the settle SHIP-LOCK" >&2
    exit 1
  fi
  if ! GH_TOKEN="$token" gh api --method POST "repos/${REPO}/issues/${ISSUE}/comments" \
    -f body="$SHIP_LOCK_SETTLE_BODY" >/dev/null; then
    echo "design-run-deliver: failed to post the settle SHIP-LOCK on #${ISSUE}" >&2
    exit 1
  fi
  note "posted settle SHIP-LOCK on #${ISSUE}"
}

# stdin: one JSON array of {body, created_at, login, type} per line (one
# gh --paginate page each). $1: this run's start (UTC ISO-8601), or empty.
# Prints true when a this-run decline, decision-needed, or defer is on
# the thread. The predicate is the lock-cleanup pair
# (decline_indicated + deferred_indicated): after the latest authentic
# SHIP-LOCK (HTML marker + trusted author) when one exists, otherwise the
# latest comment, inside the job window, from a Bot or the repo owner.
hard_stop_from_comments() {  # [run-started-at]
  jq -s --arg html_marker "$SHIP_LOCK_HTML_MARKER" \
    --arg settle_logins "$SHIP_LOCK_AUTHOR_LOGINS" \
    --arg d1 "$STOP_MARKER_DECLINED" --arg d2 "$STOP_MARKER_DECISION" \
    --arg d3 "$STOP_MARKER_DEFERRED" \
    --arg since "${1:-}" --arg owner "${REPO%%/*}" '
      def fl($b): ($b // "") | split("\n")
        | map(gsub("^[[:space:]]+|[[:space:]]+$"; ""))
        | map(select(length > 0)) | (.[0] // "");
      # Stops may come from github-actions[bot] (settle intents) or the
      # repo owner (attended PAT). Locks use the named allowlist — see is_lock.
      def stop_trusted:
        ((.login // "") | length) > 0 and ((.type // "") | length) > 0
        and (
          .type == "Bot"
          or (($owner | length) > 0
              and ((.login | ascii_downcase) == ($owner | ascii_downcase)))
        );
      def lock_logins:
        ($settle_logins / " ") | map(select(length > 0) | ascii_downcase);
      # A lock is the HTML marker PLUS an allowlisted login — never a bare
      # SHIP-LOCK first line, never an unlisted Bot (Cipher, #864).
      def is_lock:
        ((.body // "") | contains($html_marker))
        and (((.login // "") | ascii_downcase) as $l
             | (lock_logins | index($l)) != null);
      def latest_lock:
        [ .[] | select(is_lock) ]
        | if length == 0 then null
          else (reduce .[] as $c (.[0]; if $c.created_at > .created_at then $c else . end))
          end;
      def in_window: ($since | length) == 0 or .created_at > $since;
      # Same-second ties (GitHub created_at is second-precision) break by
      # higher comment id — settle skip-lock can post contract then DECLINED
      # in one second (Bugbot MED, #864); keep in sync with
      # routine-lock-cleanup.sh JQ_THIS_RUN. sort_by keeps the last of equal
      # keys, so higher id wins (missing id sorts as 0).
      def claimless_stop(is_stop):
        if ($since | length) == 0 or length == 0 then false
        else (sort_by(.created_at, ((.id // 0) | tonumber)) | last)
             | (fl(.body) | is_stop) and (.created_at > $since) and stop_trusted
        end;
      def indicated(pred):
        latest_lock as $l
        | if $l == null then claimless_stop(pred)
          else
            [ .[]
              | select(.created_at > $l.created_at)
              | select(in_window)
              | select(fl(.body) | pred)
              | select(stop_trusted) ]
            | length > 0
          end;
      (add // []) as $comments
      | $comments
      | (indicated(startswith($d1) or startswith($d2)) or indicated(startswith($d3)))
    '
}

fetch_issue_comments() {
  local token
  # The bundle step has no push PAT. ISSUE_READ_TOKEN is github.token.
  # COMMENT_TOKEN is the same token on the deliver step. GH_TOKEN is the
  # last resort so a local run with only the push token can still read.
  token="${ISSUE_READ_TOKEN:-${COMMENT_TOKEN:-${GITHUB_TOKEN:-${GH_TOKEN:-}}}}"
  if [ -z "$token" ]; then
    echo "design-run-deliver: no token to read issue comments — refusing to deliver" >&2
    return 1
  fi
  GH_TOKEN="$token" gh api --paginate "repos/${REPO}/issues/${ISSUE}/comments?per_page=100" \
    --jq '[.[] | {body: (.body // ""), created_at: .created_at, login: (.user.login // ""), type: (.user.type // ""), id: (.id // 0)}]'
}

# A this-run hard stop is not a delivery. Exit 0 with delivered=false and
# do not return. Exit 1 (via return) when the thread cannot be read.
refuse_if_hard_stop() {
  local comments verdict since
  since="${JOB_WINDOW_START:-}"
  if ! comments="$(fetch_issue_comments)"; then
    echo "design-run-deliver: could not read issue comments — refusing to deliver" >&2
    return 1
  fi
  if ! verdict="$(hard_stop_from_comments "$since" <<<"$comments")"; then
    echo "design-run-deliver: could not read issue comments — refusing to deliver" >&2
    return 1
  fi
  if [ "$verdict" = "true" ]; then
    finish false "a DECLINED, DECISION NEEDED, or DEFERRED comment from this run is on #${ISSUE} — nothing pushed"
  fi
}

# Indices of intents entries the stop/order jq filters must skip: a
# non-object element, or a comment whose body is not a string. Either
# shape makes an unguarded `.action` / `split(.body)` abort jq (Bugbot /
# CodeRabbit on #909), so both paths skip these with a warning and keep
# going. Prints one index per line; empty when the file is unreadable.
intents_malformed_indices() {
  local f="$1"
  jq -r '
    (.intents // []) | to_entries[]
    | select(
        (.value | type) != "object"
        or (
          ((.value.action // "") == "comment")
          and ((.value.body | type) != "string")
        )
      )
    | .key
  ' "$f" 2>/dev/null || true
}

# ::warning:: each malformed intents entry (see intents_malformed_indices).
# Prints the warned indices on stdout so a caller can count rejections.
warn_malformed_intents() {
  local f="$1" idx
  while IFS= read -r idx; do
    [ -n "$idx" ] || continue
    echo "::warning::intents entry ${idx} is malformed (want an object; comment body must be a string) — skipped" >&2
    printf '%s\n' "$idx"
  done < <(intents_malformed_indices "$f")
}

# A stop can no longer arrive as a comment from the agent (issues: read),
# so the bundle step also reads the agent's intents file: a comment intent
# on the selected issue whose first non-empty body line leads with a stop
# marker is the same hard stop refuse_if_hard_stop reads on the thread.
# A malformed or missing file indicates nothing (the applier warns on it
# separately); this predicate never fails the run. Non-object entries and
# non-string comment bodies are skipped with a warning so a valid sibling
# stop still indicates (Bugbot / CodeRabbit on #909).
# $1 optional path (default INTENTS_FILENAME). True when a selected-issue
# comment intent leads with a stop marker.
intents_stop_indicated() {
  local f="${1:-${INTENTS_FILENAME}}"
  [ -f "$f" ] && [ ! -L "$f" ] || return 1
  # Skip+warn malformed entries so a bad sibling cannot hide a real stop.
  # apply_intents sets INTENTS_STOP_QUIET=1 and warns once on the apply path.
  if [ "${INTENTS_STOP_QUIET:-}" != 1 ]; then
    warn_malformed_intents "$f" >/dev/null
  fi
  jq -e --arg issue "$ISSUE" \
    --arg d1 "$STOP_MARKER_DECLINED" --arg d2 "$STOP_MARKER_DECISION" \
    --arg d3 "$STOP_MARKER_DEFERRED" '
    def fl($b):
      if ($b | type) != "string" then ""
      else ($b | split("\n")
        | map(gsub("^[[:space:]]+|[[:space:]]+$"; ""))
        | map(select(length > 0)) | (.[0] // ""))
      end;
    [ (.intents // [])[]
      | select(type == "object")
      | select(((.issue // 0) | tostring) == $issue)
      | select((.action // "") == "comment")
      | select((.body | type) == "string")
      | fl(.body)
      | select(startswith($d1) or startswith($d2) or startswith($d3)) ]
    | length > 0
  ' "$f" >/dev/null 2>&1
}

# Copy the agent's worktree intents file to $WRITE_INTENTS for the trusted
# upload. Content is NOT judged here — settle's applier does that — so a
# malformed file still travels (its ::warning:: is the visible trace that an
# intent was lost). Only the file being unreadable, huge, or a symlink is an
# error. Returns (does not exit) so --write-bundle still follows.
write_intents() {
  rm -f "$WRITE_INTENTS"
  local src="${INTENTS_FILENAME}" size
  if [ ! -e "$src" ] && [ ! -L "$src" ]; then
    return 0
  fi
  if [ -L "$src" ] || [ ! -f "$src" ]; then
    echo "design-run-deliver: ${src} is not a regular file — refusing to copy intents" >&2
    exit 1
  fi
  size="$(wc -c < "$src" | tr -d '[:space:]')"
  case "$size" in
    ''|*[!0-9]*)
      echo "design-run-deliver: could not size ${src}" >&2
      exit 1
      ;;
  esac
  if [ "$size" -gt "$INTENTS_MAX_BYTES" ]; then
    echo "design-run-deliver: ${src} is ${size} bytes (over ${INTENTS_MAX_BYTES}) — intents dropped" >&2
    return 0
  fi
  if [ -L "$WRITE_INTENTS" ]; then
    echo "design-run-deliver: refusing to write intents through a symlink" >&2
    exit 1
  fi
  cat -- "$src" > "$WRITE_INTENTS" || {
    echo "design-run-deliver: could not copy ${src}" >&2
    exit 1
  }
}

# True when $1's first non-empty line leads with a hard-stop marker
# (DECLINED / DECISION NEEDED / DEFERRED). Same first-line rule as
# intents_stop_indicated / hard_stop_from_comments — reuse their jq
# fl() so Unicode whitespace (U+00A0/U+3000/U+0085/U+2028) matches.
# awk's ASCII-only [[:space:]] left those prefixes on the line, so a
# stop posted but stop_posted stayed unset and settle locked (#893).
body_is_stop_comment() {
  jq -ne --arg b "${1:-}" \
    --arg d1 "$STOP_MARKER_DECLINED" \
    --arg d2 "$STOP_MARKER_DECISION" \
    --arg d3 "$STOP_MARKER_DEFERRED" '
    def fl($b): ($b // "") | split("\n")
      | map(gsub("^[[:space:]]+|[[:space:]]+$"; ""))
      | map(select(length > 0)) | (.[0] // "");
    fl($b) | startswith($d1) or startswith($d2) or startswith($d3)
  ' >/dev/null 2>&1
}

# Apply the agent's issue intents (settle job, trusted artifact download).
# Posts the settle SHIP-LOCK claim (constant body with HTML marker)
# first, then applies intents — except when intents indicate a hard stop,
# in which case the lock is deferred and skipped only after a validated
# stop comment actually posts (Cipher L2, #884). Stop comment intents are
# applied last (Cipher, #894): skip-lock settle leaves the thread claimless,
# and lock-cleanup's claimless_stop requires the latest comment to be the
# stop — array order stop-then-other would otherwise post the other comment
# with a higher id and score the run dead. When a stop is indicated, one
# comment slot under INTENTS_MAX_COMMENTS is reserved for it so the cap
# never cuts a valid stop queued last (Cipher LOW, #910). One intent posts
# only when: it targets THIS issue, its action is comment or label, its
# label is in INTENTS_ALLOWLIST, and the per-run caps hold. Comment bodies
# are NFKC-normalized (Cf stripped, whitespace collapsed) before the
# ship-lock regex; HTML comment markers and oversize bodies are rejected
# (Cipher, #864). Everything else is dropped with a ::warning:: naming why.
# Exit 0 for agent-side problems (the run's disposition comes from the
# thread, not from here); exit 1 only for an unreadable/oversized file, a
# normalizer failure, or broken arguments — an applier that cannot read its
# input must not look like "no intents".
apply_intents() {
  local path="$1" i applied=0 rejected=0 comments=0 labels=0
  local intent_issue action body label size normalized order
  local defer_settle_lock=0 stop_posted=0
  if ! [[ "$ISSUE" =~ ^[0-9]+$ ]]; then
    echo "design-run-deliver: issue must be numeric, got '${ISSUE}'" >&2
    exit 2
  fi
  if [ -L "$path" ]; then
    echo "design-run-deliver: refusing to apply intents through a symlink" >&2
    exit 1
  fi
  if [ ! -f "$path" ]; then
    echo "design-run-deliver: intents file '${path}' is missing or not a regular file" >&2
    exit 1
  fi
  size="$(wc -c < "$path" | tr -d '[:space:]')"
  case "$size" in
    ''|*[!0-9]*)
      echo "design-run-deliver: could not size intents file '${path}'" >&2
      exit 1
      ;;
  esac
  if [ "$size" -gt "$INTENTS_MAX_BYTES" ]; then
    echo "design-run-deliver: intents file '${path}' is ${size} bytes (over ${INTENTS_MAX_BYTES}) — refusing to apply" >&2
    exit 1
  fi
  if ! jq -e --argjson max "$INTENTS_MAX_ENTRIES" '
    (type == "object") and (.version == 1) and (.intents | type == "array")
    and ((.intents | length) <= $max)
  ' "$path" >/dev/null 2>&1; then
    echo "::warning::intents file is malformed (want {version:1,intents:[...]} of at most '${INTENTS_MAX_ENTRIES}' entries) — no intents applied" >&2
    exit 0
  fi
  # Settle claim: constant body, never intent text. When intents carry a
  # stop (DECLINED / DECISION NEEDED / DEFERRED), defer the lock until
  # after intents apply — skip only once a validated stop actually posts
  # (Cipher L2, #884). A rejected or failed stop falls back to the normal
  # lock so settle never posts nothing. Posting lock-then-stop would leave
  # an active claim cleanup treats as declined-after-claim and does not
  # withdraw (Bugbot MED, #864); deferring avoids that without the silent
  # skip-on-indication hole.
  # Warn-skip malformed entries once for this apply (stop detection is
  # quieted below so the same indices are not double-warned).
  local mal_idx
  while IFS= read -r mal_idx; do
    [ -n "$mal_idx" ] || continue
    rejected=$((rejected + 1))
  done < <(warn_malformed_intents "$path")
  if INTENTS_STOP_QUIET=1 intents_stop_indicated "$path"; then
    defer_settle_lock=1
  else
    post_settle_ship_lock
  fi
  # Cipher (#894): non-stop intents (comments + labels) keep relative order,
  # then stop comments keep theirs. Same first-line markers as
  # intents_stop_indicated / body_is_stop_comment. Type-guard objects and
  # string bodies so a bad sibling cannot abort the whole batch (#909).
  if ! order="$(jq -r --arg d1 "$STOP_MARKER_DECLINED" \
      --arg d2 "$STOP_MARKER_DECISION" --arg d3 "$STOP_MARKER_DEFERRED" '
    def fl($b):
      if ($b | type) != "string" then ""
      else ($b | split("\n")
        | map(gsub("^[[:space:]]+|[[:space:]]+$"; ""))
        | map(select(length > 0)) | (.[0] // ""))
      end;
    def usable:
      (type == "object")
      and (
        ((.action // "") != "comment")
        or ((.body | type) == "string")
      );
    def is_stop_comment:
      usable
      and ((.action // "") == "comment")
      and (fl(.body) | startswith($d1) or startswith($d2) or startswith($d3));
    [.intents | to_entries[] | select(.value | usable) | select(.value | is_stop_comment | not) | .key]
    + [.intents | to_entries[] | select(.value | usable) | select(.value | is_stop_comment) | .key]
    | .[]
  ' "$path")"; then
    echo "design-run-deliver: could not order intents — refusing to apply" >&2
    exit 1
  fi
  # Word-split of newline-separated indices is intentional.
  # shellcheck disable=SC2086
  for i in $order; do
    if ! intent_issue="$(jq -r --argjson i "$i" '.intents[$i].issue // "" | if type == "number" then tostring else . end' "$path")" \
      || ! action="$(jq -r --argjson i "$i" '.intents[$i].action // ""' "$path")"; then
      echo "::warning::intents entry ${i} is unreadable — skipped" >&2
      rejected=$((rejected + 1))
      continue
    fi
    if ! [[ "$intent_issue" =~ ^[0-9]+$ ]] || [ "$intent_issue" != "$ISSUE" ]; then
      echo "::warning::intent ${i} targets issue '${intent_issue}', not the selected #${ISSUE} — rejected (off-issue writes are the attack #862 closes)" >&2
      rejected=$((rejected + 1))
      continue
    fi
    case "$action" in
      comment)
        if ! body="$(jq -r --argjson i "$i" '.intents[$i].body // ""' "$path")"; then
          echo "::warning::comment intent ${i} is unreadable — skipped" >&2
          rejected=$((rejected + 1))
          continue
        fi
        local blen
        blen="$(printf '%s' "$body" | wc -c | tr -d '[:space:]')"
        if [ -z "$body" ] || [ "${blen:-0}" -gt "$INTENTS_BODY_MAX" ]; then
          echo "::warning::comment intent ${i} has an empty or over-length body (cap ${INTENTS_BODY_MAX} bytes) — rejected" >&2
          rejected=$((rejected + 1))
          continue
        fi
        case "$body" in
          *'<!--'*|*'-->'*)
            echo "::warning::comment intent ${i} contains an HTML comment marker — rejected" >&2
            rejected=$((rejected + 1))
            continue
            ;;
        esac
        if ! normalized="$(printf '%s' "$body" | normalize_intent_body)"; then
          echo "design-run-deliver: comment intent ${i}: body normalizer failed — refusing to apply" >&2
          exit 1
        fi
        if printf '%s' "$normalized" | normalized_body_has_ship_lock; then
          echo "::warning::comment intent ${i} matches ship-lock after normalization — rejected (intents cannot author a lock; see #872 for burn residual)" >&2
          rejected=$((rejected + 1))
          continue
        fi
        # When a hard stop is indicated, reserve one slot under the
        # comment cap for a stop applied last (#910). Without this, 8
        # non-stop notes fill the cap and the stop is rejected; settle
        # then falls back to SHIP-LOCK and lock-cleanup scores claimed
        # instead of declined.
        local comment_cap="$INTENTS_MAX_COMMENTS"
        if [ "$defer_settle_lock" -eq 1 ] && ! body_is_stop_comment "$body"; then
          comment_cap=$((INTENTS_MAX_COMMENTS - 1))
        fi
        if [ "$comments" -ge "$comment_cap" ]; then
          echo "::warning::comment intent ${i} exceeds the ${INTENTS_MAX_COMMENTS}-comment cap — rejected" >&2
          rejected=$((rejected + 1))
          continue
        fi
        if ! gh api --method POST "repos/${REPO}/issues/${ISSUE}/comments" \
          -f body="$body" >/dev/null; then
          echo "::warning::comment intent ${i} failed to post on #${ISSUE}" >&2
          rejected=$((rejected + 1))
          continue
        fi
        if body_is_stop_comment "$body"; then
          stop_posted=1
        fi
        comments=$((comments + 1))
        applied=$((applied + 1))
        ;;
      label)
        if ! label="$(jq -r --argjson i "$i" '.intents[$i].label // ""' "$path")"; then
          echo "::warning::label intent ${i} is unreadable — skipped" >&2
          rejected=$((rejected + 1))
          continue
        fi
        local allowed=0 wl
        for wl in $INTENTS_ALLOWLIST; do
          [ "$label" = "$wl" ] && allowed=1
        done
        if [ "$allowed" -ne 1 ]; then
          echo "::warning::label intent ${i} names '${label}', which is not in the allowlist (${INTENTS_ALLOWLIST}) — rejected" >&2
          rejected=$((rejected + 1))
          continue
        fi
        if [ "$labels" -ge "$INTENTS_MAX_LABELS" ]; then
          echo "::warning::label intent ${i} exceeds the ${INTENTS_MAX_LABELS}-label cap — rejected" >&2
          rejected=$((rejected + 1))
          continue
        fi
        # Ensure-then-add (the §9 idiom): create the label if this repo has
        # none yet, then attach it to the selected issue.
        if ! gh api "repos/${REPO}/labels/${label}" >/dev/null 2>&1; then
          if ! gh api --method POST "repos/${REPO}/labels" -f name="$label" -f color=d876e3 >/dev/null; then
            echo "::warning::label intent ${i}: '${label}' is absent and could not be created — skipped" >&2
            rejected=$((rejected + 1))
            continue
          fi
        fi
        if ! gh api --method POST "repos/${REPO}/issues/${ISSUE}/labels" -f "labels[]=${label}" >/dev/null; then
          echo "::warning::label intent ${i} failed to add '${label}' on #${ISSUE}" >&2
          rejected=$((rejected + 1))
          continue
        fi
        labels=$((labels + 1))
        applied=$((applied + 1))
        ;;
      *)
        echo "::warning::intent ${i} has action '${action}' (want comment or label) — rejected" >&2
        rejected=$((rejected + 1))
        ;;
    esac
  done
  # Cipher L2 (#884): lock skip is earned by a posted stop, not by
  # indication alone. Rejected / failed stops fall back to the lock.
  if [ "$defer_settle_lock" -eq 1 ]; then
    if [ "$stop_posted" -eq 1 ]; then
      note "skipping settle SHIP-LOCK — validated stop posted on #${ISSUE}"
    else
      note "stop indicated but none posted — posting settle SHIP-LOCK on #${ISSUE}"
      post_settle_ship_lock
    fi
  fi
  note "applied ${applied} issue intent(s) on #${ISSUE} (${comments} comment(s), ${labels} label(s)); ${rejected} rejected"
  exit 0
}

# Read `git bundle verify` output. One contained ref. START_SHA (BASE)
# must be a prerequisite. Every other prerequisite must pass
# `git merge-base --is-ancestor <p> START_SHA` in this script. A commit
# that is merely reachable from a branch, remote, or tag is not enough.
# `git bundle verify` (git 2.43) does not checksum the pack — a flipped
# pack byte still prints "is okay" — so the caller also fetches with
# transfer.fsckObjects, and a corrupt pack dies there.
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
  if [ "${#heads[@]}" -ne 1 ]; then
    echo "design-run-deliver: bundle does not contain exactly one branch ref" >&2
    return 1
  fi
  base_present=0
  for prereq in "${prereqs[@]}"; do
    if [ "$prereq" = "$BASE" ]; then
      base_present=1
    fi
    # Inclusive: START_SHA is an ancestor of itself. The object has to be
    # in this checkout; a missing object fails the ancestor check.
    if ! git_cmd merge-base --is-ancestor "$prereq" "$BASE"; then
      echo "design-run-deliver: prerequisite ${prereq} is not an ancestor of START_SHA" >&2
      return 1
    fi
  done
  if [ "$base_present" -ne 1 ]; then
    echo "design-run-deliver: ancestry does not start at START_SHA" >&2
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
  if ! git_cmd -c transfer.fsckObjects=true fetch --no-tags "$BUNDLE" "${BUNDLE_HEAD_REF}:refs/deliver/tip" >/dev/null; then
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

# Commit safe dirty files and write START_SHA..HEAD. No token, no push.
# Exit 0 with no file when there is nothing to deliver (the workflow then
# records pending=false). A protected path exits 1 and writes no file.
# A leftover or planted file at the bundle path is removed first: the
# finish-false paths return before the later rm, and the workflow marks
# the run pending whenever that path is still a regular file.
write_bundle() {
  local ahead
  rm -f "$WRITE_BUNDLE"
  BRANCH="$(git_cmd rev-parse --abbrev-ref HEAD)"
  if ! [[ "$BRANCH" =~ ^claude/issue-${ISSUE}- ]]; then
    finish false "HEAD is '${BRANCH}', not claude/issue-${ISSUE}-* — nothing pushed"
  fi
  if ! refuse_if_hard_stop; then
    exit 1
  fi
  # The agent could not post its stop as a comment (issues: read), so the
  # same markers are read from its intents file before anything is bundled.
  if intents_stop_indicated; then
    finish false "a DECLINED, DECISION NEEDED, or DEFERRED intent is in ${INTENTS_FILENAME} — nothing pushed"
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
  if [ -n "$APPLY_INTENTS" ]; then
    apply_intents "$APPLY_INTENTS"
  fi
  # The intents copy happens before write_bundle on purpose: write_bundle
  # exits on its no-delivery paths (including an intents stop), and the
  # intents still owe settle their comments — a decline travels even when
  # (especially when) no bundle is written.
  if [ -n "$WRITE_INTENTS" ]; then
    write_intents
  fi
  if [ -n "$WRITE_BUNDLE" ]; then
    write_bundle
  fi
  if [ -n "$BUNDLE" ]; then
    if ! refuse_if_hard_stop; then
      emit delivered false
      exit 1
    fi
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
    if ! refuse_if_hard_stop; then
      emit delivered false
      exit 1
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
  # Again, immediately before the push. A stop that landed after the
  # bundle was written must not be pushed or scored as a delivery.
  if ! refuse_if_hard_stop; then
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
  for arg in "\$@"; do
    case "\$arg" in
      --method) posting=1 ;;
      body=*) printf '%s\n' "\${arg#body=}" > "${tmp}/comment.body" ;;
    esac
  done
  if [ -n "\${posting:-}" ]; then
    # Optional: fail a comment POST whose argv matches FAIL_COMMENT_POST_MATCH
    # (used by the #884 stop-post-failure selftest). Settle lock posts omit
    # the match string so the fallback lock still succeeds.
    if [ -n "\${FAIL_COMMENT_POST_MATCH:-}" ] \
      && printf '%s\n' "\$*" | grep -- '--method POST' >/dev/null \
      && printf '%s\n' "\$*" | grep -F -- "\${FAIL_COMMENT_POST_MATCH}" >/dev/null; then
      echo "comment post refused" >&2
      exit 1
    fi
    printf '%s\n' '{"id":1}'
    exit 0
  fi
  # Hard-stop read: one JSON array of comments. Empty when the fixture
  # has not planted a thread.
  if printf '%s\n' "\$*" | grep 'created_at' >/dev/null; then
    if [ -f "${tmp}/comments.json" ]; then
      cat "${tmp}/comments.json"
    else
      printf '%s\n' '[]'
    fi
    exit 0
  fi
  # --jq path: one count per page, 1 when a prior success comment exists.
  if printf '%s\n' "\$*" | grep -- '--jq' >/dev/null; then
    if [ -f "${tmp}/comment.body" ] && head -n 1 "${tmp}/comment.body" | grep 'design-run delivered' >/dev/null; then
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
  grep -q 'GIT_LITERAL_PATHSPECS=1' "$SELF" || {
    echo "selftest: git_cmd does not set GIT_LITERAL_PATHSPECS=1" >&2
    exit 1
  }
  grep -q 'ls-tree failed for' "$SELF" || {
    echo "selftest: refuse_symlink_or_gitlink_into_protected does not fail closed on ls-tree errors" >&2
    exit 1
  }
  grep -q 'refusing to run with GIT_CONFIG_GLOBAL set' "$SELF"
  grep -q -- '--no-replace-objects' "$SELF"
  grep -q -- '--no-verify' "$SELF"
  grep -q 'commit|push|merge|rebase|am' "$SELF"
  grep -q 'GH_CONFIG_DIR' "$SELF"
  grep -q 'DELIVER_WORKTREE is required' "$SELF"
  grep -q 'git_cmd log -z -m --name-status' "$SELF"
  grep -q 'diff --name-only -z "${BASE}...${tip}"' "$SELF"
  grep -q 'merge-base --is-ancestor "$prereq" "$BASE"' "$SELF" || {
    echo "selftest: prerequisites are not checked with merge-base --is-ancestor" >&2
    exit 1
  }
  if grep -q '^prereq_in_history()' "$SELF"; then
    echo "selftest: history-reachable prerequisite helper is still defined" >&2
    exit 1
  fi
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
      | grep -zxF "$1" >/dev/null
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
  # An unsafe path already in the index must not ride out on the delivery
  # commit. The safe dirty file still does.
  printf 'second\n' > "$root/designs/nuggs-ladder/second.scad"
  printf 'root\n' > "$root/CLAUDE.md"
  mkdir -p "$root/lib/VendorTree"
  printf 'vendored-staged\n' > "$root/lib/VendorTree/plant.scad"
  git_cmd -C "$root" add -- CLAUDE.md lib/VendorTree/plant.scad scripts/evil.sh
  run_case 'staged unsafe index' 0 fresh
  tree_has 'designs/nuggs-ladder/second.scad' || {
    echo "selftest: safe dirty file was not committed alongside a staged unsafe path" >&2
    exit 1
  }
  if tree_has 'CLAUDE.md'; then
    echo "selftest: staged CLAUDE.md was committed" >&2
    exit 1
  fi
  if tree_has 'lib/VendorTree/plant.scad'; then
    echo "selftest: staged vendored file was committed" >&2
    exit 1
  fi
  if tree_has 'scripts/evil.sh'; then
    echo "selftest: staged scripts/evil.sh was committed" >&2
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
  if printf '%s\n' "$stderr" | grep 'SECRETTOKEN' >/dev/null; then
    echo "selftest: GIT_CONFIG_GLOBAL refusal printed the file" >&2
    exit 1
  fi
  if ! printf '%s\n' "$stderr" | grep 'refusing to run with GIT_CONFIG_GLOBAL set' >/dev/null; then
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
  if [ "$rc" -ne 1 ] || printf '%s\n' "$stderr" | grep 'SECRETTOKEN' >/dev/null \
      || ! printf '%s\n' "$stderr" | grep 'refusing to run with GIT_CONFIG_SYSTEM set' >/dev/null; then
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
  if printf '%s\n' "$stderr" | grep 'SECRETTOKEN' >/dev/null; then
    echo "selftest: url rewrite printed the config value" >&2
    exit 1
  fi
  if ! printf '%s\n' "$stderr" | grep 'url\.\*' >/dev/null; then
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
  if [ -f "${tmp}/comment.body" ] || grep 'pr create' "${tmp}/gh.log" >/dev/null; then
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
  if [ -f "${tmp}/comment.body" ] || grep 'pr create' "${tmp}/gh.log" >/dev/null; then
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
  if [ -f "${tmp}/comment.body" ] || grep 'pr create' "${tmp}/gh.log" >/dev/null; then
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
    if printf '%s\n' "$stderr" | grep 'SECRETTOKEN' >/dev/null; then
      echo "selftest: ${hostile_key} printed the config value" >&2
      exit 1
    fi
    if ! printf '%s\n' "$stderr" | grep 'hostile local git config' >/dev/null; then
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
  mkdir -p "$bsrc/designs/nuggs-ladder"
  git_cmd -C "$bsrc" init -b main >/dev/null
  git_cmd -C "$bsrc" -c user.email=t@example.com -c user.name=t commit --allow-empty -m start >/dev/null
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
  printf '%s\n' "$stderr" | grep 'bundle sha256 does not match' >/dev/null || {
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
  printf '%s\n' "$stderr" | grep -E 'git bundle verify failed|could not fetch the bundle' >/dev/null || {
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
  printf '%s\n' "$stderr" | grep 'ancestry does not start at START_SHA' >/dev/null || {
    echo "selftest: orphan bundle did not refuse the ancestry" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  # A prerequisite that is in repo history, but the tip does not contain
  # START_SHA (the branch was cut from START_SHA's parent). The parent is
  # a verified ancestor; the push still refuses because START_SHA is not
  # an ancestor of the tip.
  local asrc adel aroot astart
  asrc="${tmp}/asrc"
  adel="${tmp}/adel"
  mkdir -p "$asrc/designs/nuggs-ladder"
  git_cmd -C "$asrc" init -b main >/dev/null
  git_cmd -C "$asrc" -c user.email=t@example.com -c user.name=t commit --allow-empty -m root >/dev/null
  aroot="$(git_cmd -C "$asrc" rev-parse HEAD)"
  git_cmd -C "$asrc" -c user.email=t@example.com -c user.name=t commit --allow-empty -m start >/dev/null
  astart="$(git_cmd -C "$asrc" rev-parse HEAD)"
  git_cmd -C "$asrc" checkout -b claude/issue-853-nuggs-ladder "$aroot" >/dev/null
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
  printf '%s\n' "$stderr" | grep 'ancestry does not start at START_SHA' >/dev/null || {
    echo "selftest: older prerequisite was accepted" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }

  # Issue intents (item 9). The settle job's --apply-intents is the only
  # issue-writing surface left in the pipeline: an intent posts only when
  # it targets the SELECTED issue and its label is allowlisted. Every case
  # below drives the real entrypoint against the recording fake gh.
  local isrc ibase ifile stderr rc
  isrc="${tmp}/isrc"
  mkdir -p "$isrc"
  git_cmd -C "$isrc" init -b main >/dev/null
  git_cmd -C "$isrc" -c user.email=t@example.com -c user.name=t commit --allow-empty -m base >/dev/null
  ibase="$(git_cmd -C "$isrc" rev-parse HEAD)"
  run_intents() {  # $1 intents file, $2 expected exit. Captures stderr+rc.
    # Optional FAIL_COMMENT_POST_MATCH is forwarded so the fake gh can
    # refuse a matching comment POST (Cipher L2, #884 case c).
    : > "${tmp}/gh.log"
    set +e
    stderr="$(env PATH="${tmp}/bin:${PATH}" GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
      DELIVER_WORKTREE="$isrc" \
      FAIL_COMMENT_POST_MATCH="${FAIL_COMMENT_POST_MATCH:-}" \
      "$SELF" --repo acme/print-bench --issue 853 --base "$ibase" \
      --base-branch main --run-url https://example.test/run/1 \
      --apply-intents "$1" 2>&1 >/dev/null)"
    rc=$?
    set -e
    if [ "$rc" -ne "$2" ]; then
      echo "selftest: apply-intents $1 exited ${rc}, expected ${2}" >&2
      printf '%s\n' "$stderr" >&2
      exit 1
    fi
  }
  comment_posts() {
    grep -c -- 'api --method POST repos/acme/print-bench/issues/853/comments' "${tmp}/gh.log" || true
  }
  label_posts() {
    grep -c -- 'api --method POST repos/acme/print-bench/issues/853/labels' "${tmp}/gh.log" || true
  }

  # Happy path: settle posts its constant SHIP-LOCK first, then the
  # agent's non-lock comments and a needs-decision label, in file order.
  # SHIP-LOCK must never appear in intent text (rejected below).
  ifile="${tmp}/intents-happy.json"
  cat > "$ifile" <<'EOF'
{"version":1,"intents":[
 {"issue":853,"action":"comment","body":"Acceptance contract body"},
 {"issue":853,"action":"comment","body":"Amendment body"},
 {"issue":853,"action":"label","label":"needs-decision"}
]}
EOF
  run_intents "$ifile" 0
  # settle lock + 2 intent comments
  [ "$(comment_posts)" -eq 3 ] || { echo "selftest: happy intents did not post settle lock + both comments (posted $(comment_posts))" >&2; exit 1; }
  [ "$(label_posts)" -eq 1 ] || { echo "selftest: happy intents did not post the label" >&2; exit 1; }
  grep -qF -- "$SHIP_LOCK_HTML_MARKER" "${tmp}/gh.log" || {
    echo "selftest: settle SHIP-LOCK did not carry the HTML authenticity marker" >&2
    exit 1
  }
  grep -qF -- "$STOP_LOCK_MARKER — settle claim" "${tmp}/gh.log" || {
    echo "selftest: settle SHIP-LOCK did not use the constant visible line" >&2
    exit 1
  }
  settle_line="$(grep -nF -- "$SHIP_LOCK_HTML_MARKER" "${tmp}/gh.log" | head -1 | cut -d: -f1)"
  contract_line="$(grep -n -- 'Acceptance contract body' "${tmp}/gh.log" | head -1 | cut -d: -f1)"
  amend_line="$(grep -n -- 'Amendment body' "${tmp}/gh.log" | head -1 | cut -d: -f1)"
  [ -n "$settle_line" ] && [ -n "$contract_line" ] && [ -n "$amend_line" ] \
    && [ "$settle_line" -lt "$contract_line" ] && [ "$contract_line" -lt "$amend_line" ] || {
    echo "selftest: settle lock / comments were not posted in order" >&2
    exit 1
  }
  grep -q -- 'labels\[\]=needs-decision' "${tmp}/gh.log" || {
    echo "selftest: the label intent did not add needs-decision" >&2
    exit 1
  }

  # THE #862 case: an off-issue label intent must be rejected — never
  # posted, no matter what it names.
  ifile="${tmp}/intents-offissue-label.json"
  cat > "$ifile" <<'EOF'
{"version":1,"intents":[
 {"issue":999,"action":"label","label":"needs-decision"},
 {"issue":853,"action":"comment","body":"on-issue comment survives"}
]}
EOF
  run_intents "$ifile" 0
  [ "$(label_posts)" -eq 0 ] || { echo "selftest: an off-issue label intent was posted" >&2; exit 1; }
  # settle lock + the surviving on-issue comment
  [ "$(comment_posts)" -eq 2 ] || { echo "selftest: the on-issue comment was dropped with the off-issue label (posted $(comment_posts))" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep "targets issue '999', not the selected #853" >/dev/null || {
    echo "selftest: the off-issue rejection did not name the reason" >&2
    exit 1
  }

  # Off-issue comment intents are rejected the same way.
  ifile="${tmp}/intents-offissue-comment.json"
  cat > "$ifile" <<'EOF'
{"version":1,"intents":[
 {"issue":999,"action":"comment","body":"off-issue spoof body"}
]}
EOF
  run_intents "$ifile" 0
  # settle lock only — the off-issue comment never posts
  [ "$(comment_posts)" -eq 1 ] || { echo "selftest: an off-issue comment intent was posted (posted $(comment_posts))" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep "targets issue '999'" >/dev/null || {
    echo "selftest: the off-issue comment rejection did not name the reason" >&2
    exit 1
  }

  # An allowlist rejection: autonomy-ok on the SELECTED issue — the exact
  # injection the finding describes — still never posts.
  ifile="${tmp}/intents-badlabel.json"
  cat > "$ifile" <<'EOF'
{"version":1,"intents":[
 {"issue":853,"action":"label","label":"autonomy-ok"},
 {"issue":853,"action":"label","label":"design-brief"}
]}
EOF
  run_intents "$ifile" 0
  [ "$(label_posts)" -eq 0 ] || { echo "selftest: a non-allowlisted label intent was posted" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep "not in the allowlist" >/dev/null || {
    echo "selftest: the allowlist rejection did not name the reason" >&2
    exit 1
  }

  # Caps: nine comment intents post eight.
  ifile="${tmp}/intents-cap.json"
  {
    printf '%s\n' '{"version":1,"intents":['
    for ci in 1 2 3 4 5 6 7 8 9; do
      printf ' {"issue":853,"action":"comment","body":"c%d"}%s\n' "$ci" "$([ "$ci" -lt 9 ] && echo , || echo '')"
    done
    printf '%s\n' ']}'
  } > "$ifile"
  run_intents "$ifile" 0
  # settle lock + 8 capped comments
  [ "$(comment_posts)" -eq 9 ] || { echo "selftest: the comment cap did not hold (posted $(comment_posts))" >&2; exit 1; }

  # Cipher (#864): every ship-lock shape is rejected after NFKC / Cf-strip /
  # whitespace collapse — including emoji, case, separators, zero-width,
  # fullwidth, and non-first-line forms. Settle still posts its own lock.
  reject_shiplock_case() {  # $1 name, $2 body
    ifile="${tmp}/intents-sl-$1.json"
    jq -n --arg b "$2" \
      '{"version":1,"intents":[{"issue":853,"action":"comment","body":$b},{"issue":853,"action":"comment","body":"safe sibling survives"}]}' \
      > "$ifile"
    run_intents "$ifile" 0
    # settle lock + safe sibling only
    [ "$(comment_posts)" -eq 2 ] || {
      echo "selftest: ship-lock case '$1' was not rejected (posted $(comment_posts))" >&2
      exit 1
    }
    grep -q -- 'safe sibling survives' "${tmp}/gh.log" || {
      echo "selftest: ship-lock case '$1' dropped its safe sibling" >&2
      exit 1
    }
    printf '%s\n' "$stderr" | grep 'matches ship-lock after normalization' >/dev/null || {
      echo "selftest: ship-lock case '$1' did not name the reason" >&2
      exit 1
    }
  }
  reject_shiplock_case emoji $'🚢 SHIP-LOCK — claim via intent'
  reject_shiplock_case lower 'ship-lock spoof'
  reject_shiplock_case spaced 'ship lock spoof'
  reject_shiplock_case underscored 'ship_lock spoof'
  # U+200B zero-width space inside SHIP-LOCK
  reject_shiplock_case zwsp "$(python3 -c 'print("SHIP\u200b-LOCK spoof")')"
  # Fullwidth ＳＨＩＰ－ＬＯＣＫ (NFKC → SHIP-LOCK)
  reject_shiplock_case fullwidth "$(python3 -c 'print("\uff33\uff28\uff29\uff30\uff0d\uff2c\uff2f\uff23\uff2b spoof")')"
  reject_shiplock_case line2 $'preamble\nSHIP-LOCK on line two'

  # Cipher / Bugbot MED (#864) + Cipher L2 (#884 case a): a valid
  # DECLINED-only intents payload posts the stop and skips the settle
  # lock (cleanup would leave lock-then-stop active as declined-after-claim).
  # Skip is earned only after the stop posts — see cases b/c below.
  ifile="${tmp}/intents-declined-only.json"
  cat > "$ifile" <<'EOF'
{"version":1,"intents":[
 {"issue":853,"action":"comment","body":"🚢 DECLINED — needs a decision\n\nparked"}
]}
EOF
  run_intents "$ifile" 0
  [ "$(comment_posts)" -eq 1 ] || {
    echo "selftest: DECLINED-only intents posted settle lock (posted $(comment_posts))" >&2
    exit 1
  }
  grep -qF -- "$SHIP_LOCK_HTML_MARKER" "${tmp}/gh.log" && {
    echo "selftest: DECLINED-only intents still posted the settle SHIP-LOCK marker" >&2
    exit 1
  }
  grep -q -- 'DECLINED — needs a decision' "${tmp}/gh.log" || {
    echo "selftest: DECLINED-only intents did not post the stop comment" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'skipping settle SHIP-LOCK — validated stop posted' >/dev/null || {
    echo "selftest: DECLINED-only path did not note skipping the settle lock after a posted stop" >&2
    exit 1
  }

  # Cipher CLEAR of #892 / #893: body_is_stop_comment must agree with the
  # jq readers on Unicode whitespace. A leading NBSP (or U+3000 / U+2028)
  # used to leave intents_stop_indicated true but body_is_stop_comment
  # false — settle posted the stop then the lock, and the run scored dead.
  stop_unicode_ws_case() {  # $1 name, $2 python unicode escape for leading ws
    ifile="${tmp}/intents-stop-ws-$1.json"
    body="$(python3 -c "print('${2}' + '🚢 DECLINED — unicode-ws ${1}\\n\\nparked')")"
    jq -n --arg b "$body" \
      '{"version":1,"intents":[{"issue":853,"action":"comment","body":$b}]}' \
      > "$ifile"
    run_intents "$ifile" 0
    [ "$(comment_posts)" -eq 1 ] || {
      echo "selftest: stop with leading $1 posted settle lock (posted $(comment_posts))" >&2
      exit 1
    }
    grep -qF -- "$SHIP_LOCK_HTML_MARKER" "${tmp}/gh.log" && {
      echo "selftest: stop with leading $1 still posted the settle SHIP-LOCK marker" >&2
      exit 1
    }
    grep -q -- "DECLINED — unicode-ws ${1}" "${tmp}/gh.log" || {
      echo "selftest: stop with leading $1 did not post the stop comment" >&2
      exit 1
    }
    printf '%s\n' "$stderr" | grep -q 'skipping settle SHIP-LOCK — validated stop posted' || {
      echo "selftest: stop with leading $1 did not skip the settle lock after posting" >&2
      exit 1
    }
  }
  stop_unicode_ws_case nbsp '\u00a0'
  stop_unicode_ws_case ideographic '\u3000'
  stop_unicode_ws_case linesep '\u2028'
  stop_unicode_ws_case nel '\u0085'

  # Cipher L2 (#884 case b): a stop intent that fails validation (HTML
  # comment marker) must NOT silently skip the lock — fall back to posting it.
  ifile="${tmp}/intents-stop-rejected.json"
  cat > "$ifile" <<'EOF'
{"version":1,"intents":[
 {"issue":853,"action":"comment","body":"🚢 DECLINED — parked <!-- spoof -->"}
]}
EOF
  run_intents "$ifile" 0
  [ "$(comment_posts)" -eq 1 ] || {
    echo "selftest: rejected-stop intents did not fall back to the settle lock (posted $(comment_posts))" >&2
    exit 1
  }
  grep -qF -- "$SHIP_LOCK_HTML_MARKER" "${tmp}/gh.log" || {
    echo "selftest: rejected-stop intents silently skipped the settle SHIP-LOCK" >&2
    exit 1
  }
  grep -q -- 'DECLINED — parked' "${tmp}/gh.log" && {
    echo "selftest: rejected-stop intents still posted the invalid stop body" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'HTML comment marker' >/dev/null || {
    echo "selftest: rejected-stop path did not name the HTML rejection" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'stop indicated but none posted — posting settle SHIP-LOCK' >/dev/null || {
    echo "selftest: rejected-stop path did not note the lock fallback" >&2
    exit 1
  }

  # Cipher L2 (#884 case c): a validated stop whose POST fails must NOT
  # skip the lock — fall back to posting it.
  ifile="${tmp}/intents-stop-post-fail.json"
  cat > "$ifile" <<'EOF'
{"version":1,"intents":[
 {"issue":853,"action":"comment","body":"🚢 DECLINED — needs a decision\n\nparked"}
]}
EOF
  FAIL_COMMENT_POST_MATCH='DECLINED — needs a decision' run_intents "$ifile" 0
  # Fake gh logs the refused stop POST before exiting 1, then the lock POST
  # succeeds — two comment API calls, one of which carries the authenticity
  # marker. Indication alone must not have skipped the lock.
  [ "$(comment_posts)" -eq 2 ] || {
    echo "selftest: failed-stop-post expected stop-attempt + settle lock (posted $(comment_posts))" >&2
    exit 1
  }
  grep -qF -- "$SHIP_LOCK_HTML_MARKER" "${tmp}/gh.log" || {
    echo "selftest: failed-stop-post silently skipped the settle SHIP-LOCK" >&2
    exit 1
  }
  grep -q -- 'DECLINED — needs a decision' "${tmp}/gh.log" || {
    echo "selftest: failed-stop-post never attempted the stop comment" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'failed to post' >/dev/null || {
    echo "selftest: failed-stop-post path did not warn about the post failure" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'stop indicated but none posted — posting settle SHIP-LOCK' >/dev/null || {
    echo "selftest: failed-stop-post path did not note the lock fallback" >&2
    exit 1
  }

  # Cipher (#894): stop-then-other in the intents array must still leave the
  # stop as the latest posted comment. Skip-lock settle is claimless;
  # claimless_stop scores dead when a non-stop follows the stop. Apply
  # stops last so post order is other then stop regardless of array order.
  ifile="${tmp}/intents-stop-then-other.json"
  cat > "$ifile" <<'EOF'
{"version":1,"intents":[
 {"issue":853,"action":"comment","body":"🚢 DECLINED — needs a decision\n\nparked"},
 {"issue":853,"action":"comment","body":"**Design name:** widget\n\n**Gate contract**\n- [ ] G1"}
]}
EOF
  run_intents "$ifile" 0
  [ "$(comment_posts)" -eq 2 ] || {
    echo "selftest: stop-then-other expected 2 comments, no lock (posted $(comment_posts))" >&2
    exit 1
  }
  grep -qF -- "$SHIP_LOCK_HTML_MARKER" "${tmp}/gh.log" && {
    echo "selftest: stop-then-other still posted the settle SHIP-LOCK" >&2
    exit 1
  }
  other_line="$(grep -n -- 'Gate contract' "${tmp}/gh.log" | head -1 | cut -d: -f1)"
  stop_line="$(grep -n -- 'DECLINED — needs a decision' "${tmp}/gh.log" | head -1 | cut -d: -f1)"
  [ -n "$other_line" ] && [ -n "$stop_line" ] && [ "$other_line" -lt "$stop_line" ] || {
    echo "selftest: stop-then-other did not post the non-stop before the stop (other=${other_line:-?} stop=${stop_line:-?})" >&2
    cat "${tmp}/gh.log" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'skipping settle SHIP-LOCK — validated stop posted' >/dev/null || {
    echo "selftest: stop-then-other path did not skip the settle lock after posting the stop" >&2
    exit 1
  }

  # Bugbot / CodeRabbit (#909): non-object entries and non-string comment
  # bodies must not abort the order jq or hide stop detection. Mixed with
  # valid intents, the bad ones warn-skip; valid non-stops then stop still
  # post in that order, and the settle lock stays deferred.
  ifile="${tmp}/intents-malformed-entries.json"
  cat > "$ifile" <<'EOF'
{"version":1,"intents":[
 null,
 "not-an-object",
 {"issue":853,"action":"comment","body":42},
 {"issue":853,"action":"comment","body":"**Design name:** widget\n\n**Gate contract**\n- [ ] G1"},
 {"issue":853,"action":"comment","body":"🚢 DECLINED — needs a decision\n\nparked"},
 {"issue":853,"action":"label","label":"needs-decision"}
]}
EOF
  run_intents "$ifile" 0
  [ "$(comment_posts)" -eq 2 ] || {
    echo "selftest: malformed-entries expected non-stop + stop, no lock (posted $(comment_posts))" >&2
    cat "${tmp}/gh.log" >&2
    exit 1
  }
  [ "$(label_posts)" -eq 1 ] || {
    echo "selftest: malformed-entries did not post the valid label sibling" >&2
    exit 1
  }
  grep -qF -- "$SHIP_LOCK_HTML_MARKER" "${tmp}/gh.log" && {
    echo "selftest: malformed-entries still posted the settle SHIP-LOCK (stop detection missed)" >&2
    exit 1
  }
  other_line="$(grep -n -- 'Gate contract' "${tmp}/gh.log" | head -1 | cut -d: -f1)"
  stop_line="$(grep -n -- 'DECLINED — needs a decision' "${tmp}/gh.log" | head -1 | cut -d: -f1)"
  label_line="$(grep -n -- 'labels\[\]=needs-decision' "${tmp}/gh.log" | head -1 | cut -d: -f1)"
  [ -n "$other_line" ] && [ -n "$label_line" ] && [ -n "$stop_line" ] \
    && [ "$other_line" -lt "$label_line" ] && [ "$label_line" -lt "$stop_line" ] || {
    echo "selftest: malformed-entries did not keep non-stop then stop order (other=${other_line:-?} label=${label_line:-?} stop=${stop_line:-?})" >&2
    cat "${tmp}/gh.log" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'intents entry 0 is malformed' >/dev/null || {
    echo "selftest: malformed-entries did not warn about the null entry" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'intents entry 2 is malformed' >/dev/null || {
    echo "selftest: malformed-entries did not warn about the non-string body" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'skipping settle SHIP-LOCK — validated stop posted' >/dev/null || {
    echo "selftest: malformed-entries path did not skip the settle lock after posting the stop" >&2
    exit 1
  }
  # Standalone stop detection (write-bundle path) must also warn-skip and
  # still see the valid stop among malformed siblings.
  ISSUE=853
  stderr_stop="$(intents_stop_indicated "$ifile" 2>&1)" && stop_rc=0 || stop_rc=$?
  [ "$stop_rc" -eq 0 ] || {
    echo "selftest: intents_stop_indicated missed the valid stop among malformed entries" >&2
    printf '%s\n' "$stderr_stop" >&2
    exit 1
  }
  printf '%s\n' "$stderr_stop" | grep 'intents entry 1 is malformed' >/dev/null || {
    echo "selftest: intents_stop_indicated did not warn about a malformed entry" >&2
    printf '%s\n' "$stderr_stop" >&2
    exit 1
  }

  # Cipher LOW (#910): 8 non-stop notes + 1 stop must still post the stop
  # (one slot reserved under the comment cap). Without the reserve, the
  # stop is cut after #909's stop-last ordering and settle falls back to
  # SHIP-LOCK — lock-cleanup then scores claimed instead of declined.
  ifile="${tmp}/intents-cap-reserve-stop.json"
  {
    printf '%s\n' '{"version":1,"intents":['
    for ci in 1 2 3 4 5 6 7 8; do
      printf ' {"issue":853,"action":"comment","body":"note %d gate text"},\n' "$ci"
    done
    printf ' {"issue":853,"action":"comment","body":"🚢 DECLINED — needs a decision\\n\\nparked"}\n'
    printf '%s\n' ']}'
  } > "$ifile"
  run_intents "$ifile" 0
  # 7 notes (one cut for the reserved slot) + stop; no settle lock.
  [ "$(comment_posts)" -eq 8 ] || {
    echo "selftest: 8-notes+stop expected 7 notes + stop (posted $(comment_posts))" >&2
    cat "${tmp}/gh.log" >&2
    exit 1
  }
  grep -q -- 'DECLINED — needs a decision' "${tmp}/gh.log" || {
    echo "selftest: 8-notes+stop did not post the stop (cap cut it)" >&2
    cat "${tmp}/gh.log" >&2
    exit 1
  }
  grep -qF -- "$SHIP_LOCK_HTML_MARKER" "${tmp}/gh.log" && {
    echo "selftest: 8-notes+stop fell back to settle SHIP-LOCK (would score claimed)" >&2
    cat "${tmp}/gh.log" >&2
    exit 1
  }
  note_n="$(grep -c -- 'note [0-9] gate text' "${tmp}/gh.log" || true)"
  [ "$note_n" -eq 7 ] || {
    echo "selftest: 8-notes+stop expected 7 notes under the reserved cap (got ${note_n})" >&2
    cat "${tmp}/gh.log" >&2
    exit 1
  }
  last_note_line="$(grep -n -- 'note [0-9] gate text' "${tmp}/gh.log" | tail -1 | cut -d: -f1)"
  stop_line="$(grep -n -- 'DECLINED — needs a decision' "${tmp}/gh.log" | head -1 | cut -d: -f1)"
  [ -n "$last_note_line" ] && [ -n "$stop_line" ] && [ "$last_note_line" -lt "$stop_line" ] || {
    echo "selftest: 8-notes+stop did not keep stop last (note=${last_note_line:-?} stop=${stop_line:-?})" >&2
    cat "${tmp}/gh.log" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep -q 'skipping settle SHIP-LOCK — validated stop posted' || {
    echo "selftest: 8-notes+stop path did not skip the settle lock after posting the stop" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep -q 'exceeds the .*comment cap' || {
    echo "selftest: 8-notes+stop did not warn about the cut non-stop under the reserved cap" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }

  # Cipher (#864): HTML comment markers anywhere in the body → reject.
  ifile="${tmp}/intents-html-comment.json"
  cat > "$ifile" <<'EOF'
{"version":1,"intents":[
 {"issue":853,"action":"comment","body":"visible <!-- hidden --> text"},
 {"issue":853,"action":"comment","body":"trailing -->"},
 {"issue":853,"action":"comment","body":"no markers here"}
]}
EOF
  run_intents "$ifile" 0
  # settle lock + no-markers sibling
  [ "$(comment_posts)" -eq 2 ] || { echo "selftest: HTML-marker bodies were not rejected (posted $(comment_posts))" >&2; exit 1; }
  grep -q -- 'no markers here' "${tmp}/gh.log" || {
    echo "selftest: the sibling of an HTML-marker body was dropped" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'HTML comment marker' >/dev/null || {
    echo "selftest: HTML-marker rejection did not name the reason" >&2
    exit 1
  }

  # Cipher (#864): per-comment 8 KiB body cap, and a 64 KiB apply-side
  # payload ceiling that fails closed (exit 1) before any intent posts.
  ifile="${tmp}/intents-body-cap.json"
  big="$(printf 'x%.0s' {1..8193})"
  jq -n --arg b "$big" \
    '{"version":1,"intents":[{"issue":853,"action":"comment","body":$b},{"issue":853,"action":"comment","body":"tiny"}]}' \
    > "$ifile"
  run_intents "$ifile" 0
  # settle lock + tiny
  [ "$(comment_posts)" -eq 2 ] || { echo "selftest: over-length comment body was posted (posted $(comment_posts))" >&2; exit 1; }
  grep -q -- 'tiny' "${tmp}/gh.log" || {
    echo "selftest: the sibling of an over-length body was dropped" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'over-length body' >/dev/null || {
    echo "selftest: over-length body rejection did not name the reason" >&2
    exit 1
  }

  ifile="${tmp}/intents-file-huge.json"
  # A valid envelope padded past INTENTS_MAX_BYTES — apply must refuse
  # before posting, even though the JSON itself would otherwise parse.
  printf '%s' '{"version":1,"intents":[{"issue":853,"action":"comment","body":"pad"}]}' > "$ifile"
  # shellcheck disable=SC2188
  dd if=/dev/zero bs=1 count=70000 >> "$ifile" 2>/dev/null
  run_intents "$ifile" 1
  [ "$(comment_posts)" -eq 0 ] || {
    echo "selftest: an oversized intents file still posted" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'refusing to apply' >/dev/null || {
    echo "selftest: an oversized intents file did not fail closed" >&2
    exit 1
  }

  # A malformed file applies nothing and does not fail the settle job.
  printf '%s\n' '{not json' > "${tmp}/intents-malformed.json"
  run_intents "${tmp}/intents-malformed.json" 0
  [ "$(comment_posts)" -eq 0 ] && [ "$(label_posts)" -eq 0 ] || {
    echo "selftest: a malformed intents file still posted" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'intents file is malformed' >/dev/null || {
    echo "selftest: a malformed intents file did not warn" >&2
    exit 1
  }

  # A missing file is an infra failure (exit 1), never a silent no-op.
  run_intents "${tmp}/intents-absent.json" 1
  printf '%s\n' "$stderr" | grep 'missing or not a regular file' >/dev/null || {
    echo "selftest: a missing intents file did not fail loudly" >&2
    exit 1
  }

  # The write side. --write-bundle refuses to bundle when the agent's
  # intents carry a stop marker for the selected issue, and --write-intents
  # still copies the file so settle can post the decline.
  local ssrc sbase sfile sint
  ssrc="${tmp}/ssrc"
  sfile="${tmp}/stop.bundle"
  sint="${tmp}/stop-intents.json"
  mkdir -p "$ssrc/designs/nuggs-ladder"
  git_cmd -C "$ssrc" init -b main >/dev/null
  git_cmd -C "$ssrc" -c user.email=t@example.com -c user.name=t commit --allow-empty -m start >/dev/null
  sbase="$(git_cmd -C "$ssrc" rev-parse HEAD)"
  git_cmd -C "$ssrc" checkout -b claude/issue-853-nuggs-ladder >/dev/null
  printf 'work\n' > "$ssrc/designs/nuggs-ladder/work.scad"
  git_cmd -C "$ssrc" -c user.email=t@example.com -c user.name=t add -- designs/nuggs-ladder/work.scad
  git_cmd -C "$ssrc" -c user.email=t@example.com -c user.name=t commit -m work >/dev/null
  cat > "$sint" <<'EOF'
{"version":1,"intents":[
 {"issue":853,"action":"comment","body":"🚢 DECLINED — needs a decision\n\nThe brief asks for two deliverables."},
 {"issue":999,"action":"comment","body":"🚢 DECLINED — off-issue stop must not count"}
]}
EOF
  cp "$sint" "$ssrc/.design-run-intents.json"
  # The thread fixture would refuse via refuse_if_hard_stop for its own
  # reason; these cases test the intents channel alone.
  rm -f "${tmp}/comments.json"
  set +e
  env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$ssrc" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$sbase" \
    --base-branch main --run-url https://example.test/run/1 \
    --write-intents "${tmp}/stop-intents-copy.json" \
    --write-bundle "$sfile" >/dev/null
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || { echo "selftest: intents stop exited ${rc}, expected 0" >&2; exit 1; }
  [ ! -f "$sfile" ] || { echo "selftest: a stop intent still wrote a bundle" >&2; exit 1; }
  [ -f "${tmp}/stop-intents-copy.json" ] || { echo "selftest: the stop run did not copy its intents" >&2; exit 1; }

  # A stop aimed at a DIFFERENT issue does not stop the bundle (the
  # off-issue half of the same rule), and a healthy intents file does not
  # stop it either.
  rm -f "$sfile" "${tmp}/stop-intents-copy.json" "$ssrc/.design-run-intents.json" "${tmp}/comments.json"
  cat > "$ssrc/.design-run-intents.json" <<'EOF'
{"version":1,"intents":[
 {"issue":999,"action":"comment","body":"🚢 DECLINED — other issue"},
 {"issue":853,"action":"comment","body":"Progress note, not a stop"}
]}
EOF
  set +e
  env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$ssrc" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$sbase" \
    --base-branch main --run-url https://example.test/run/1 \
    --write-intents "${tmp}/stop-intents-copy.json" \
    --write-bundle "$sfile" >/dev/null
  rc=$?
  set -e
  [ "$rc" -eq 0 ] && [ -f "$sfile" ] || { echo "selftest: an off-issue stop suppressed the bundle (exit ${rc})" >&2; exit 1; }

  # A COMMITTED intents file refuses the delivery outright: it must never
  # ride the PR onto main.
  rm -f "$sfile" "$ssrc/.design-run-intents.json" "${tmp}/comments.json"
  cat > "$ssrc/.design-run-intents.json" <<'EOF'
{"version":1,"intents":[{"issue":853,"action":"comment","body":"stale"}]}
EOF
  git_cmd -C "$ssrc" -c user.email=t@example.com -c user.name=t add -- .design-run-intents.json
  git_cmd -C "$ssrc" -c user.email=t@example.com -c user.name=t commit -m 'stale intents' >/dev/null
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$ssrc" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$sbase" \
    --base-branch main --run-url https://example.test/run/1 \
    --write-bundle "$sfile" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 1 ] || { echo "selftest: a committed intents file exited ${rc}, expected 1" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep 'design-run-intents.json' >/dev/null || {
    echo "selftest: a committed intents file did not name the refusal" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  [ ! -f "$sfile" ] || { echo "selftest: a committed intents file still bundled" >&2; exit 1; }

  # Accept: a depth-1 clone merges newer main. Newer main itself merges a
  # side branch forked before START_SHA. The bundle is what --write-bundle
  # writes (`^START_SHA refs/heads/<branch>`), not a hand-built `^mmain`
  # boundary. START_SHA is the prerequisite. Strict accepts it. The deliver
  # checkout is the full history, detached at START_SHA.
  local msrc mdel mshallow mstart mmain mtip mbare msha mhare
  msrc="${tmp}/msrc"
  mdel="${tmp}/mdel"
  mshallow="${tmp}/mshallow"
  mbare="${tmp}/mbare.git"
  mhare="${tmp}/mhare.git"
  mkdir -p "$msrc/designs/nuggs-ladder"
  git_cmd -C "$msrc" init -b main >/dev/null
  git_cmd -C "$msrc" -c user.email=t@example.com -c user.name=t commit --allow-empty -m root >/dev/null
  git_cmd -C "$msrc" checkout -b side >/dev/null
  mkdir -p "$msrc/designs/nuggs-ladder"
  printf 'side\n' > "$msrc/designs/nuggs-ladder/side.scad"
  git_cmd -C "$msrc" -c user.email=t@example.com -c user.name=t add -- designs/nuggs-ladder/side.scad
  git_cmd -C "$msrc" -c user.email=t@example.com -c user.name=t commit -m side >/dev/null
  git_cmd -C "$msrc" checkout main >/dev/null
  git_cmd -C "$msrc" -c user.email=t@example.com -c user.name=t commit --allow-empty -m start >/dev/null
  mstart="$(git_cmd -C "$msrc" rev-parse HEAD)"
  mkdir -p "$msrc/designs/nuggs-ladder"
  printf 'from-main\n' > "$msrc/designs/nuggs-ladder/from-main.scad"
  git_cmd -C "$msrc" -c user.email=t@example.com -c user.name=t add -- designs/nuggs-ladder/from-main.scad
  git_cmd -C "$msrc" -c user.email=t@example.com -c user.name=t commit -m 'newer main' >/dev/null
  git_cmd -C "$msrc" -c user.email=t@example.com -c user.name=t merge --no-ff -m 'merge side into main' side >/dev/null
  mmain="$(git_cmd -C "$msrc" rev-parse HEAD)"
  git_cmd init -b main --bare "$mhare" >/dev/null
  git_cmd -C "$msrc" push "$mhare" "${mstart}:refs/heads/start" "${mmain}:refs/heads/main" >/dev/null
  # Local clones ignore --depth. file:// is what makes the clone shallow.
  git_cmd clone --depth 1 -b start "file://${mhare}" "$mshallow" >/dev/null
  grep -qx "$mstart" "$mshallow/.git/shallow" || {
    echo "selftest: merged-main clone was not depth-1 at START_SHA" >&2
    exit 1
  }
  git_cmd -C "$mshallow" checkout -b claude/issue-853-nuggs-ladder >/dev/null
  mkdir -p "$mshallow/designs/nuggs-ladder"
  printf 'own\n' > "$mshallow/designs/nuggs-ladder/own.scad"
  git_cmd -C "$mshallow" -c user.email=t@example.com -c user.name=t add -- designs/nuggs-ladder/own.scad
  git_cmd -C "$mshallow" -c user.email=t@example.com -c user.name=t commit -m own >/dev/null
  git_cmd -C "$mshallow" fetch origin "+refs/heads/main:refs/remotes/origin/main" >/dev/null
  git_cmd -C "$mshallow" -c user.email=t@example.com -c user.name=t merge --no-ff -m 'merge newer' origin/main >/dev/null
  mtip="$(git_cmd -C "$mshallow" rev-parse HEAD)"
  git_cmd -C "$mshallow" bundle create "${tmp}/merged.bundle" "^${mstart}" "refs/heads/claude/issue-853-nuggs-ladder"
  git_cmd clone -b start "$mhare" "$mdel" >/dev/null
  git_cmd -C "$mdel" checkout --detach "$mstart" >/dev/null
  git_cmd init -b main --bare "$mbare" >/dev/null
  msha="$(sha256sum "${tmp}/merged.bundle" | awk '{print $1}')"
  rm -f "${tmp}/pr.json" "${tmp}/comment.body" "${tmp}/comments.json"
  set +e
  env GH_BIN="${tmp}/bin/gh" GH_REPO="$mdel" GH_TOKEN=test-token COMMENT_TOKEN=comment-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$mdel" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$mstart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$mbare" \
    --bundle "${tmp}/merged.bundle" --bundle-sha256 "$msha" >/dev/null
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || { echo "selftest: merged-main bundle exited ${rc}" >&2; exit 1; }
  [ "$(git_cmd --git-dir="$mbare" rev-parse refs/heads/claude/issue-853-nuggs-ladder)" = "$mtip" ] || {
    echo "selftest: merged-main bundle was not pushed" >&2
    exit 1
  }
  git_cmd --git-dir="$mbare" grep -q from-main refs/heads/claude/issue-853-nuggs-ladder -- designs/nuggs-ladder/from-main.scad
  git_cmd --git-dir="$mbare" grep -q side refs/heads/claude/issue-853-nuggs-ladder -- designs/nuggs-ladder/side.scad
  [ "$(git_cmd -C "$mdel" rev-parse HEAD)" = "$mstart" ] || {
    echo "selftest: merged-main bundle checked the bundle out over START_SHA" >&2
    exit 1
  }

  # Reject: a prerequisite that is not an ancestor of START_SHA. The bundle
  # lists START_SHA and the newer-main tip. The deliver checkout still has
  # the newer-main object, but only as a dangling object: its branch and
  # remote are gone. merge-base --is-ancestor fails. Nothing is pushed.
  local mdel2
  mdel2="${tmp}/mdel2"
  git_cmd -C "$msrc" checkout -B claude/issue-853-nuggs-ladder "$mstart" >/dev/null
  mkdir -p "$msrc/designs/nuggs-ladder"
  printf 'dang\n' > "$msrc/designs/nuggs-ladder/dang.scad"
  git_cmd -C "$msrc" -c user.email=t@example.com -c user.name=t add -- designs/nuggs-ladder/dang.scad
  git_cmd -C "$msrc" -c user.email=t@example.com -c user.name=t commit -m dang >/dev/null
  git_cmd -C "$msrc" -c user.email=t@example.com -c user.name=t merge --no-ff -m 'merge for dangling prereq' "$mmain" >/dev/null
  git_cmd -C "$msrc" bundle create "${tmp}/dangling.bundle" "^${mstart}" "^${mmain}" refs/heads/claude/issue-853-nuggs-ladder
  git_cmd init -b main --bare "${tmp}/mhist.git" >/dev/null
  git_cmd -C "$msrc" push "${tmp}/mhist.git" "${mmain}:refs/heads/main" >/dev/null
  git_cmd clone -b main "${tmp}/mhist.git" "$mdel2" >/dev/null
  git_cmd -C "$mdel2" checkout --detach "$mstart" >/dev/null
  git_cmd -C "$mdel2" branch -D main >/dev/null
  git_cmd -C "$mdel2" remote remove origin
  msha="$(sha256sum "${tmp}/dangling.bundle" | awk '{print $1}')"
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$mdel2" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$mstart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$mbare" \
    --bundle "${tmp}/dangling.bundle" --bundle-sha256 "$msha" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 1 ] || { echo "selftest: dangling-prerequisite bundle exited ${rc}" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep 'is not an ancestor of START_SHA' >/dev/null || {
    echo "selftest: dangling prerequisite was accepted" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  [ "$(git_cmd --git-dir="$mbare" rev-parse refs/heads/claude/issue-853-nuggs-ladder)" = "$mtip" ] || {
    echo "selftest: dangling prerequisite was pushed" >&2
    exit 1
  }

  # Reject: newer main touches scripts/. The bundle is again
  # `^START_SHA refs/heads/<branch>`, so the scripts commit is inside the
  # pack and the prerequisite check passes. The forbidden-path walk refuses.
  git_cmd -C "$msrc" checkout main >/dev/null
  mkdir -p "$msrc/scripts"
  printf 'script\n' > "$msrc/scripts/from-main.sh"
  git_cmd -C "$msrc" -c user.email=t@example.com -c user.name=t add -- scripts/from-main.sh
  git_cmd -C "$msrc" -c user.email=t@example.com -c user.name=t commit -m 'main scripts' >/dev/null
  mmain="$(git_cmd -C "$msrc" rev-parse HEAD)"
  git_cmd -C "$msrc" checkout claude/issue-853-nuggs-ladder >/dev/null
  git_cmd -C "$msrc" -c user.email=t@example.com -c user.name=t merge --no-ff -m 'merge scripts' "$mmain" >/dev/null
  git_cmd -C "$msrc" bundle create "${tmp}/merged-scripts.bundle" "^${mstart}" refs/heads/claude/issue-853-nuggs-ladder
  msha="$(sha256sum "${tmp}/merged-scripts.bundle" | awk '{print $1}')"
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$mdel" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$mstart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$mbare" \
    --bundle "${tmp}/merged-scripts.bundle" --bundle-sha256 "$msha" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 1 ] || { echo "selftest: merged scripts bundle exited ${rc}" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep 'touches scripts/from-main.sh' >/dev/null || {
    echo "selftest: merged scripts path was not refused" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  [ "$(git_cmd --git-dir="$mbare" rev-parse refs/heads/claude/issue-853-nuggs-ladder)" = "$mtip" ] || {
    echo "selftest: merged scripts bundle was pushed" >&2
    exit 1
  }

  # Reject: a protected path is added inside a merge commit and removed by
  # a later merge. `git log` without -m does not show either merge's path,
  # and the three-dot diff does not either, because the tip no longer has
  # the file. -m on the range log lists it.
  local esrc edel estart
  esrc="${tmp}/esrc"
  edel="${tmp}/edel"
  mkdir -p "$esrc/designs/nuggs-ladder"
  git_cmd -C "$esrc" init -b main >/dev/null
  git_cmd -C "$esrc" -c user.email=t@example.com -c user.name=t commit --allow-empty -m start >/dev/null
  estart="$(git_cmd -C "$esrc" rev-parse HEAD)"
  git_cmd -C "$esrc" checkout -b claude/issue-853-nuggs-ladder >/dev/null
  printf 'own\n' > "$esrc/designs/nuggs-ladder/own.scad"
  git_cmd -C "$esrc" -c user.email=t@example.com -c user.name=t add -- designs/nuggs-ladder/own.scad
  git_cmd -C "$esrc" -c user.email=t@example.com -c user.name=t commit -m own >/dev/null
  git_cmd -C "$esrc" checkout main >/dev/null
  mkdir -p "$esrc/designs/nuggs-ladder"
  printf 'b\n' > "$esrc/designs/nuggs-ladder/b.scad"
  git_cmd -C "$esrc" -c user.email=t@example.com -c user.name=t add -- designs/nuggs-ladder/b.scad
  git_cmd -C "$esrc" -c user.email=t@example.com -c user.name=t commit -m mainfile >/dev/null
  git_cmd -C "$esrc" checkout claude/issue-853-nuggs-ladder >/dev/null
  git_cmd -C "$esrc" -c user.email=t@example.com -c user.name=t merge --no-ff --no-commit main >/dev/null
  mkdir -p "$esrc/scripts"
  printf 'evil\n' > "$esrc/scripts/evil.sh"
  git_cmd -C "$esrc" -c user.email=t@example.com -c user.name=t add -- scripts/evil.sh
  git_cmd -C "$esrc" -c user.email=t@example.com -c user.name=t commit -m 'evil merge' >/dev/null
  git_cmd -C "$esrc" checkout -b cleaner "$estart" >/dev/null
  mkdir -p "$esrc/designs/nuggs-ladder"
  printf 'c\n' > "$esrc/designs/nuggs-ladder/c.scad"
  git_cmd -C "$esrc" -c user.email=t@example.com -c user.name=t add -- designs/nuggs-ladder/c.scad
  git_cmd -C "$esrc" -c user.email=t@example.com -c user.name=t commit -m cleaner >/dev/null
  git_cmd -C "$esrc" checkout claude/issue-853-nuggs-ladder >/dev/null
  git_cmd -C "$esrc" -c user.email=t@example.com -c user.name=t merge --no-ff --no-commit cleaner >/dev/null
  git_cmd -C "$esrc" rm -q -- scripts/evil.sh >/dev/null
  git_cmd -C "$esrc" -c user.email=t@example.com -c user.name=t commit -m 'merge delete' >/dev/null
  git_cmd -C "$esrc" bundle create "${tmp}/evil-merge.bundle" "^${estart}" refs/heads/claude/issue-853-nuggs-ladder
  git_cmd init -b main --bare "${tmp}/ehist.git" >/dev/null
  git_cmd -C "$esrc" push "${tmp}/ehist.git" "${estart}:refs/heads/main" >/dev/null
  git_cmd clone -b main "${tmp}/ehist.git" "$edel" >/dev/null
  msha="$(sha256sum "${tmp}/evil-merge.bundle" | awk '{print $1}')"
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$edel" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$estart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$mbare" \
    --bundle "${tmp}/evil-merge.bundle" --bundle-sha256 "$msha" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 1 ] || { echo "selftest: evil-merge bundle exited ${rc}" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep 'touches scripts/evil.sh' >/dev/null || {
    echo "selftest: merge-only protected path was not refused" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  [ "$(git_cmd --git-dir="$mbare" rev-parse refs/heads/claude/issue-853-nuggs-ladder)" = "$mtip" ] || {
    echo "selftest: evil-merge bundle was pushed" >&2
    exit 1
  }

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
  printf '%s\n' "$stderr" | grep 'touches scripts/evil.sh' >/dev/null || {
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

  # A this-run hard stop writes no bundle and pushes nothing. The marker
  # is the first line, the author is the repo owner or a Bot, and the
  # comment is inside the job window after the claim. An outsider's
  # marker, and a stop from before the window, still deliver.
  local hsrc hdel hstart hbare hsha htip hbefore marker
  hsrc="${tmp}/hsrc"
  hdel="${tmp}/hdel"
  hbare="${tmp}/hbare.git"
  mkdir -p "$hsrc/designs/nuggs-ladder"
  git_cmd -C "$hsrc" init -b main >/dev/null
  git_cmd -C "$hsrc" -c user.email=t@example.com -c user.name=t commit --allow-empty -m start >/dev/null
  hstart="$(git_cmd -C "$hsrc" rev-parse HEAD)"
  git_cmd -C "$hsrc" checkout -b claude/issue-853-nuggs-ladder >/dev/null
  printf 'held\n' > "$hsrc/designs/nuggs-ladder/held.scad"
  git_cmd -C "$hsrc" -c user.email=t@example.com -c user.name=t add -- designs/nuggs-ladder/held.scad
  git_cmd -C "$hsrc" -c user.email=t@example.com -c user.name=t commit -m held >/dev/null
  git_cmd init -b main --bare "${tmp}/hhist.git" >/dev/null
  git_cmd -C "$hsrc" push "${tmp}/hhist.git" "${hstart}:refs/heads/main" >/dev/null
  git_cmd clone -b main "${tmp}/hhist.git" "$hdel" >/dev/null
  git_cmd init -b main --bare "$hbare" >/dev/null
  plant_stop() {  # body, login, type, created_at
    # Authentic settle lock: visible line + HTML marker + settle login.
    jq -n --arg body "$1" --arg login "$2" --arg type "$3" --arg at "$4" \
      --arg lock "$SHIP_LOCK_SETTLE_BODY" \
      '[{body:$lock,created_at:"2026-10-19T00:00:00Z",login:"github-actions[bot]",type:"Bot"},
        {body:$body,created_at:$at,login:$login,type:$type}]' > "${tmp}/comments.json"
  }
  for marker in '🚢 DECLINED — needs a decision' '🚦 DECISION NEEDED — bay-width' '🚢 DEFERRED — dependencies'; do
    plant_stop "${marker}"$'\n\nstop' acme User 2026-10-19T01:00:00Z
    printf 'dirty-stop\n' > "$hsrc/designs/nuggs-ladder/dirty-stop.scad"
    hbefore="$(git_cmd -C "$hsrc" rev-parse HEAD)"
    rm -f "${tmp}/stop.bundle"
    set +e
    env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
      JOB_WINDOW_START=2026-10-19T00:30:00Z \
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
      DELIVER_WORKTREE="$hsrc" \
      "$SELF" --repo acme/print-bench --issue 853 --base "$hstart" \
      --base-branch main --run-url https://example.test/run/1 \
      --write-bundle "${tmp}/stop.bundle" >/dev/null
    rc=$?
    set -e
    [ "$rc" -eq 0 ] || { echo "selftest: hard stop ${marker} exited ${rc}" >&2; exit 1; }
    [ ! -e "${tmp}/stop.bundle" ] || { echo "selftest: hard stop ${marker} wrote a bundle" >&2; exit 1; }
    [ "$(git_cmd -C "$hsrc" rev-parse HEAD)" = "$hbefore" ] || {
      echo "selftest: hard stop ${marker} committed" >&2
      exit 1
    }
  done
  # Cipher (#864): a comment that merely starts with SHIP-LOCK / 🚢 SHIP-LOCK
  # but lacks the HTML authenticity marker is NOT a lock — hard-stop stays
  # claimless (the later stop still fires as claimless). REPO must be set so
  # author_trusted can match the owner login.
  REPO=acme/print-bench
  jq -n --arg body $'🚢 DECLINED — needs a decision\n\nstop' \
    '[{body:"🚢 SHIP-LOCK\n\nspoofed without marker",created_at:"2026-10-19T00:00:00Z",login:"acme",type:"User"},
      {body:$body,created_at:"2026-10-19T01:00:00Z",login:"acme",type:"User"}]' \
    > "${tmp}/comments.json"
  [ "$(hard_stop_from_comments 2026-10-19T00:30:00Z <"${tmp}/comments.json")" = "true" ] || {
    echo "selftest: claimless stop after a marker-less SHIP-LOCK did not fire" >&2
    exit 1
  }
  # Settle-written claim (marker + trusted author) IS a lock: a stop after
  # it is indicated; the same stop before the window is not.
  jq -n --arg lock "$SHIP_LOCK_SETTLE_BODY" --arg body $'🚢 DECLINED — needs a decision\n\nstop' \
    '[{body:$lock,created_at:"2026-10-19T00:00:00Z",login:"github-actions[bot]",type:"Bot"},
      {body:$body,created_at:"2026-10-19T01:00:00Z",login:"github-actions[bot]",type:"Bot"}]' \
    > "${tmp}/comments.json"
  [ "$(hard_stop_from_comments 2026-10-19T00:30:00Z <"${tmp}/comments.json")" = "true" ] || {
    echo "selftest: settle-written SHIP-LOCK was not treated as a lock" >&2
    exit 1
  }
  # Marker present but untrusted author → not a lock.
  jq -n --arg lock "$SHIP_LOCK_SETTLE_BODY" \
    '[{body:$lock,created_at:"2026-10-19T00:00:00Z",login:"attacker",type:"User"}]' \
    > "${tmp}/comments.json"
  [ "$(hard_stop_from_comments 2026-10-19T00:30:00Z <"${tmp}/comments.json")" = "false" ] || {
    echo "selftest: marker+untrusted-author was treated as a lock" >&2
    exit 1
  }
  # Allowlisted logins (settle + attended shaiss) count.
  for ok_login in 'github-actions[bot]' 'shaiss'; do
    jq -n --arg lock "$SHIP_LOCK_SETTLE_BODY" --arg login "$ok_login" \
      --arg body $'🚢 DECLINED — needs a decision\n\nstop' \
      '[{body:$lock,created_at:"2026-10-19T00:00:00Z",login:$login,type:(if $login=="shaiss" then "User" else "Bot" end)},
        {body:$body,created_at:"2026-10-19T01:00:00Z",login:"github-actions[bot]",type:"Bot"}]' \
      > "${tmp}/comments.json"
    [ "$(hard_stop_from_comments 2026-10-19T00:30:00Z <"${tmp}/comments.json")" = "true" ] || {
      echo "selftest: marker+${ok_login} was not treated as a lock" >&2
      exit 1
    }
  done
  # cursor[bot] must NOT count — shared Cursor App (Bugbot / agents).
  jq -n --arg lock "$SHIP_LOCK_SETTLE_BODY" \
    '[{body:$lock,created_at:"2026-10-19T00:00:00Z",login:"cursor[bot]",type:"Bot"}]' \
    > "${tmp}/comments.json"
  [ "$(hard_stop_from_comments 2026-10-19T00:30:00Z <"${tmp}/comments.json")" = "false" ] || {
    echo "selftest: marker+cursor[bot] was treated as a lock" >&2
    exit 1
  }
  # Unlisted Bot (claude[bot]) must NOT count — no generic [bot] match.
  jq -n --arg lock "$SHIP_LOCK_SETTLE_BODY" \
    '[{body:$lock,created_at:"2026-10-19T00:00:00Z",login:"claude[bot]",type:"Bot"}]' \
    > "${tmp}/comments.json"
  [ "$(hard_stop_from_comments 2026-10-19T00:30:00Z <"${tmp}/comments.json")" = "false" ] || {
    echo "selftest: marker+claude[bot] was treated as a lock" >&2
    exit 1
  }

  # Bot author, claimless (no lock): still this run's stop.
  jq -n --arg body $'🚦 DECISION NEEDED — bay-width\n\nstop' \
    '[{body:$body,created_at:"2026-10-19T01:00:00Z",login:"github-actions[bot]",type:"Bot"}]' \
    > "${tmp}/comments.json"
  rm -f "${tmp}/stop.bundle"
  set +e
  env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    JOB_WINDOW_START=2026-10-19T00:30:00Z \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$hsrc" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$hstart" \
    --base-branch main --run-url https://example.test/run/1 \
    --write-bundle "${tmp}/stop.bundle" >/dev/null
  rc=$?
  set -e
  [ "$rc" -eq 0 ] && [ ! -e "${tmp}/stop.bundle" ] || {
    echo "selftest: claimless bot decision was delivered (exit ${rc})" >&2
    exit 1
  }
  # Same-second contract + DECLINED (skip-lock settle): higher id wins so
  # the stop still fires as claimless (Bugbot MED, #864).
  jq -n \
    '[{body:"**Design name:** widget\n\n**Gate contract**\n- [ ] G1",
       created_at:"2026-10-19T01:00:00Z",login:"github-actions[bot]",type:"Bot",id:100},
      {body:"🚢 DECLINED — needs a decision\n\nstop",
       created_at:"2026-10-19T01:00:00Z",login:"github-actions[bot]",type:"Bot",id:101}]' \
    > "${tmp}/comments.json"
  [ "$(hard_stop_from_comments 2026-10-19T00:30:00Z <"${tmp}/comments.json")" = "true" ] || {
    echo "selftest: same-second claimless contract+DECLINED (stop higher id) did not fire" >&2
    exit 1
  }
  jq -n \
    '[{body:"🚢 DECLINED — needs a decision\n\nstop",
       created_at:"2026-10-19T01:00:00Z",login:"github-actions[bot]",type:"Bot",id:100},
      {body:"**Design name:** widget\n\n**Gate contract**\n- [ ] G1",
       created_at:"2026-10-19T01:00:00Z",login:"github-actions[bot]",type:"Bot",id:101}]' \
    > "${tmp}/comments.json"
  [ "$(hard_stop_from_comments 2026-10-19T00:30:00Z <"${tmp}/comments.json")" = "false" ] || {
    echo "selftest: same-second DECLINED followed by higher-id contract still fired as stop" >&2
    exit 1
  }
  # Outsider marker does not stop the run. The bundle is written.
  plant_stop $'🚢 DECLINED — needs a decision\n\nspoof' attacker User 2026-10-19T01:00:00Z
  rm -f "${tmp}/stop.bundle"
  set +e
  env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    JOB_WINDOW_START=2026-10-19T00:30:00Z \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$hsrc" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$hstart" \
    --base-branch main --run-url https://example.test/run/1 \
    --write-bundle "${tmp}/stop.bundle" >/dev/null
  rc=$?
  set -e
  [ "$rc" -eq 0 ] && [ -f "${tmp}/stop.bundle" ] || {
    echo "selftest: outsider decline suppressed the bundle (exit ${rc})" >&2
    exit 1
  }
  # A stop from before this run's window does not suppress delivery.
  plant_stop $'🚢 DECLINED — needs a decision\n\nold' acme User 2026-10-18T01:00:00Z
  rm -f "${tmp}/stop.bundle"
  set +e
  env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    JOB_WINDOW_START=2026-10-19T00:30:00Z \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$hsrc" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$hstart" \
    --base-branch main --run-url https://example.test/run/1 \
    --write-bundle "${tmp}/old-stop.bundle" >/dev/null
  rc=$?
  set -e
  [ "$rc" -eq 0 ] && [ -f "${tmp}/old-stop.bundle" ] || {
    echo "selftest: a stop from before the window suppressed the bundle (exit ${rc})" >&2
    exit 1
  }
  # Deliver side: a valid bundle is not pushed when the thread has since stopped.
  hsha="$(sha256sum "${tmp}/old-stop.bundle" | awk '{print $1}')"
  htip="$(git_cmd -C "$hsrc" rev-parse HEAD)"
  plant_stop $'🚢 DEFERRED — dependencies\n\nwait' acme User 2026-10-19T01:00:00Z
  rm -f "${tmp}/comment.body" "${tmp}/pr.json"
  set +e
  env GH_BIN="${tmp}/bin/gh" GH_REPO="$hdel" GH_TOKEN=test-token COMMENT_TOKEN=comment-token \
    JOB_WINDOW_START=2026-10-19T00:30:00Z \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$hdel" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$hstart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$hbare" \
    --bundle "${tmp}/old-stop.bundle" --bundle-sha256 "$hsha" >/dev/null
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || { echo "selftest: deferred deliver exited ${rc}" >&2; exit 1; }
  if git_cmd --git-dir="$hbare" rev-parse refs/heads/claude/issue-853-nuggs-ladder >/dev/null 2>&1; then
    echo "selftest: deferred run was pushed" >&2
    exit 1
  fi
  if [ -f "${tmp}/comment.body" ]; then
    echo "selftest: deferred run posted success" >&2
    exit 1
  fi
  [ "$(git_cmd -C "$hdel" rev-parse HEAD)" = "$hstart" ] || {
    echo "selftest: deferred run moved the deliver checkout" >&2
    exit 1
  }
  # The same bundle without the stop does push, so the refusal above is the stop.
  rm -f "${tmp}/comments.json" "${tmp}/comment.body" "${tmp}/pr.json"
  set +e
  env GH_BIN="${tmp}/bin/gh" GH_REPO="$hdel" GH_TOKEN=test-token COMMENT_TOKEN=comment-token \
    JOB_WINDOW_START=2026-10-19T00:30:00Z \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$hdel" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$hstart" \
    --base-branch main --run-url https://example.test/run/1 --push-url "$hbare" \
    --bundle "${tmp}/old-stop.bundle" --bundle-sha256 "$hsha" >/dev/null
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || { echo "selftest: bundle after clearing the stop exited ${rc}" >&2; exit 1; }
  [ "$(git_cmd --git-dir="$hbare" rev-parse refs/heads/claude/issue-853-nuggs-ladder)" = "$htip" ] || {
    echo "selftest: clearing the stop did not deliver" >&2
    exit 1
  }
  rm -f "${tmp}/comments.json"

  # A file planted at the bundle path must not survive a finish-false
  # write_bundle. The workflow marks the run pending when that file exists.
  local psrc pstart pout
  psrc="${tmp}/psrc"
  pout="${tmp}/planted-output"
  mkdir -p "$psrc"
  git_cmd -C "$psrc" init -b main >/dev/null
  git_cmd -C "$psrc" -c user.email=t@example.com -c user.name=t commit --allow-empty -m start >/dev/null
  pstart="$(git_cmd -C "$psrc" rev-parse HEAD)"
  printf 'planted\n' > "${tmp}/planted.bundle"
  : > "$pout"
  set +e
  env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GITHUB_OUTPUT="$pout" \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$psrc" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$pstart" \
    --base-branch main --run-url https://example.test/run/1 \
    --write-bundle "${tmp}/planted.bundle" >/dev/null
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || { echo "selftest: planted bundle on main exited ${rc}" >&2; exit 1; }
  [ ! -e "${tmp}/planted.bundle" ] || {
    echo "selftest: failing write_bundle left the planted bundle" >&2
    exit 1
  }
  if [ -f "${tmp}/planted.bundle" ]; then
    echo "pending=true" >> "$pout"
  else
    echo "pending=false" >> "$pout"
  fi
  grep -qx 'pending=false' "$pout" || {
    echo "selftest: planted bundle marked the run pending" >&2
    exit 1
  }
  grep -qx 'delivered=false' "$pout" || {
    echo "selftest: planted bundle did not record delivered=false" >&2
    exit 1
  }

  # The other finish-false path: the branch name matches, but HEAD has no
  # commit ahead of START_SHA. A planted file must still be removed.
  local psrc2 pstart2 pout2
  psrc2="${tmp}/psrc2"
  pout2="${tmp}/planted-output-ahead"
  mkdir -p "$psrc2"
  git_cmd -C "$psrc2" init -b main >/dev/null
  git_cmd -C "$psrc2" -c user.email=t@example.com -c user.name=t commit --allow-empty -m start >/dev/null
  pstart2="$(git_cmd -C "$psrc2" rev-parse HEAD)"
  git_cmd -C "$psrc2" checkout -b claude/issue-853-planted >/dev/null
  printf 'planted\n' > "${tmp}/planted-ahead.bundle"
  : > "$pout2"
  set +e
  env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GITHUB_OUTPUT="$pout2" \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$psrc2" \
    "$SELF" --repo acme/print-bench --issue 853 --base "$pstart2" \
    --base-branch main --run-url https://example.test/run/1 \
    --write-bundle "${tmp}/planted-ahead.bundle" >/dev/null
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || { echo "selftest: planted bundle with nothing ahead exited ${rc}" >&2; exit 1; }
  [ ! -e "${tmp}/planted-ahead.bundle" ] || {
    echo "selftest: no-commits-ahead write_bundle left the planted bundle" >&2
    exit 1
  }
  if [ -f "${tmp}/planted-ahead.bundle" ]; then
    echo "pending=true" >> "$pout2"
  else
    echo "pending=false" >> "$pout2"
  fi
  grep -qx 'pending=false' "$pout2" || {
    echo "selftest: no-commits-ahead planted bundle marked the run pending" >&2
    exit 1
  }
  grep -qx 'delivered=false' "$pout2" || {
    echo "selftest: no-commits-ahead planted bundle did not record delivered=false" >&2
    exit 1
  }

  # H1: the workflow restores the real script from START_SHA into a temp
  # dir outside the fixture repo and runs --write-bundle. The worktree
  # copy is poisoned. A missing DELIVER_WORKTREE and a worktree that is
  # not the git toplevel (a planted parent .git) both fail closed.
  local workflow deliver_run deliver_workflow push_step deliver_job
  workflow="${repo_root}/.github/workflows/design-run.yml"
  deliver_run="$(awk '
    /^      - name: Bundle the design commits/ { in_step = 1 }
    in_step && /^        run: \|/ { printing = 1; next }
    in_step && printing && /^      - name:/ { exit }
    printing { print }
  ' "$workflow")"
  [ -n "$deliver_run" ] || { echo "selftest: could not extract the bundle run block" >&2; exit 1; }
  printf '%s\n' "$deliver_run" | grep '/usr/bin/git --no-replace-objects -c core.hooksPath=/dev/null -c core.fsmonitor=false -c core.sshCommand= show "$START_SHA:scripts/design-run-deliver.sh"' >/dev/null || {
    echo "selftest: bundle step does not git-show the pinned script" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep 'DELIVER_SHA256' >/dev/null || {
    echo "selftest: deliver step does not check the pre-agent sha256" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep 'objects/info/alternates' >/dev/null || {
    echo "selftest: deliver step does not refuse object alternates" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep 'GIT_ALTERNATE_OBJECT_DIRECTORIES' >/dev/null || {
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
  grep -q 'actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9' "$workflow" || {
    echo "selftest: the bundle is not uploaded from the pinned v7 action" >&2
    exit 1
  }
  if grep -q 'actions/upload-artifact@v7' "$workflow" || grep 'actions/checkout@v7' "$workflow" >/dev/null || grep -q 'actions/setup-python@v7' "$workflow"; then
    echo "selftest: design-run.yml still uses a floating v7 action tag" >&2
    exit 1
  fi
  grep -q 'retention-days: 1' "$workflow" || {
    echo "selftest: the bundle artifact has no short retention" >&2
    exit 1
  }
  grep -q 'name: design-run-meta' "$workflow" || {
    echo "selftest: the run job does not upload delivery metadata" >&2
    exit 1
  }
  deliver_workflow="${repo_root}/.github/workflows/design-run-deliver.yml"
  [ -f "$deliver_workflow" ] || { echo "selftest: design-run-deliver.yml is missing" >&2; exit 1; }
  grep -q 'workflow_run:' "$deliver_workflow" || {
    echo "selftest: delivery is not a workflow_run workflow" >&2
    exit 1
  }
  grep -q 'workflows: \["Design run (scheduled idea→PR pipeline)"\]' "$deliver_workflow" || {
    echo "selftest: delivery workflow_run does not name the design-run workflow" >&2
    exit 1
  }
  grep -q 'actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131' "$deliver_workflow" || {
    echo "selftest: the deliver workflow does not download the bundle from the pinned v7 action" >&2
    exit 1
  }
  if grep -q 'actions/download-artifact@v7' "$deliver_workflow" || grep 'actions/checkout@v7' "$deliver_workflow" >/dev/null; then
    echo "selftest: design-run-deliver.yml still uses a floating v7 action tag" >&2
    exit 1
  fi
  grep -q '\$GITHUB_WORKSPACE/scripts/design-run-deliver.sh' "$deliver_workflow" || {
    echo "selftest: the deliver workflow does not run the checkout script" >&2
    exit 1
  }
  if grep -q 'anthropics/claude-code-action' "$deliver_workflow"; then
    echo "selftest: the deliver workflow runs agent code" >&2
    exit 1
  fi
  local push_step deliver_job
  push_step="$(awk '
    /^      - name: Verify the bundle and push/ { printing = 1 }
    printing && /^      - name:/ && !/^      - name: Verify the bundle and push/ { exit }
    printing { print }
  ' "$deliver_workflow")"
  [ -n "$push_step" ] || { echo "selftest: could not extract the deliver push step" >&2; exit 1; }
  printf '%s\n' "$push_step" | grep 'timeout-minutes: 10' >/dev/null || {
    echo "selftest: the deliver push step has no timeout under the job budget" >&2
    exit 1
  }
  printf '%s\n' "$push_step" | grep 'GH_TOKEN: \${{ secrets.GH_TOKEN }}' >/dev/null || {
    echo "selftest: the deliver push step does not hold the push PAT" >&2
    exit 1
  }
  deliver_job="$(awk '
    /^  deliver:/ { printing = 1 }
    printing && /^  [A-Za-z]/ && !/^  deliver:/ { exit }
    printing { print }
  ' "$deliver_workflow")"
  [ -n "$deliver_job" ] || { echo "selftest: could not extract the deliver job" >&2; exit 1; }
  printf '%s\n' "$deliver_job" | awk '
    /uses: actions\/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1/ { found = 1; n = 0 }
    found { n++; if ($0 ~ /timeout-minutes: 2/) ok = 1 }
    found && n > 6 { exit }
    END { exit ok ? 0 : 1 }
  ' || {
    echo "selftest: the deliver checkout has no 2-minute timeout" >&2
    exit 1
  }
  printf '%s\n' "$deliver_job" | awk '
    /name: Download the design bundle/ { found = 1; n = 0 }
    found { n++; if ($0 ~ /timeout-minutes: 2/) ok = 1 }
    found && n > 6 { exit }
    END { exit ok ? 0 : 1 }
  ' || {
    echo "selftest: the bundle download has no 2-minute timeout" >&2
    exit 1
  }
  printf '%s\n' "$deliver_job" | awk '
    /name: Release the SHIP-LOCK after delivery/ { found = 1; n = 0 }
    found { n++; if ($0 ~ /timeout-minutes: 3/) ok = 1 }
    found && n > 8 { exit }
    END { exit ok ? 0 : 1 }
  ' || {
    echo "selftest: the deliver lock cleanup has no 3-minute timeout" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep -- '--write-bundle' >/dev/null || {
    echo "selftest: the bundle step does not pass --write-bundle" >&2
    exit 1
  }
  if printf '%s\n' "$deliver_run" | grep 'GH_TOKEN' >/dev/null; then
    echo "selftest: the bundle step run block mentions GH_TOKEN" >&2
    exit 1
  fi

  # #862: the agent job must not carry issues: write — the whole fix. The
  # run job may READ the thread (the selector snapshot and the hard-stop
  # read), but a comment or label POST has to 403. The pins read the
  # permissions STANZA, not the job's prose — a comment saying "no
  # issues: write" must be able to exist without failing (or satisfying)
  # the check.
  local run_job run_perms
  run_job="$(awk '
    /^  run:/ { printing = 1 }
    printing && /^  [A-Za-z]/ && !/^  run:/ { exit }
    printing { print }
  ' "$workflow")"
  [ -n "$run_job" ] || { echo "selftest: could not extract the run job" >&2; exit 1; }
  run_perms="$(awk '/^    permissions:/ { p = 1; next } p && /^      [-a-z]+:/ { print; next } p && /^      #/ { next } p { exit }' <<<"$run_job")"
  grep -q 'issues: read' <<<"$run_perms" || {
    echo "selftest: the run job cannot read issues (the selector snapshot needs it)" >&2
    exit 1
  }
  if grep -q 'issues: write' <<<"$run_perms"; then
    echo "selftest: the agent job still carries issues: write — the #862 injection is open" >&2
    exit 1
  fi
  # The intents file is captured and re-digested around the post-bundle
  # reap, exactly like the bundle: an orphan rewriting it between the two
  # reads must invalidate the upload.
  grep -q -- '--write-intents' <<<"$deliver_run" || {
    echo "selftest: the bundle step does not carry the intents file" >&2
    exit 1
  }
  grep -q 'intents_now' <<<"$deliver_run" && grep -q 'intents_captured' <<<"$deliver_run" || {
    echo "selftest: the bundle step does not digest the intents file around the reap" >&2
    exit 1
  }
  grep -q 'rm -f "\$intents_path"' <<<"$deliver_run" || {
    echo "selftest: a changed intents digest does not drop the file" >&2
    exit 1
  }
  # The trusted upload: pinned action, short retention, hard-fail when the
  # trusted copy is missing, and a note step settle can key on.
  local intents_upload_step
  intents_upload_step="$(awk '
    /^      - name: Upload the design intents/ { printing = 1 }
    printing && /^      - name:/ && !/^      - name: Upload the design intents/ { exit }
    printing { print }
  ' "$workflow")"
  [ -n "$intents_upload_step" ] || { echo "selftest: could not extract the intents upload step" >&2; exit 1; }
  grep -q 'name: design-run-intents' <<<"$intents_upload_step" || {
    echo "selftest: the intents artifact is not named design-run-intents" >&2
    exit 1
  }
  grep -q 'if-no-files-found: error' <<<"$intents_upload_step" || {
    echo "selftest: the intents upload does not fail on a missing file" >&2
    exit 1
  }
  grep -q 'retention-days: 1' <<<"$intents_upload_step" || {
    echo "selftest: the intents artifact has no short retention" >&2
    exit 1
  }
  grep -q 'intents_uploaded: \${{ steps.intents_upload.outputs.ready }}' "$workflow" || {
    echo "selftest: the run job does not surface intents_uploaded" >&2
    exit 1
  }
  # The applier: settle downloads the same-run artifact with the pinned
  # action, restores this script from the pre-agent pin, and applies only
  # when the trusted upload happened.
  local settle_job apply_step
  settle_job="$(awk '
    /^  settle:/ { printing = 1 }
    printing && /^  [A-Za-z]/ && !/^  settle:/ { exit }
    printing { print }
  ' "$workflow")"
  [ -n "$settle_job" ] || { echo "selftest: could not extract the settle job" >&2; exit 1; }
  apply_step="$(printf '%s\n' "$settle_job" | awk '
    /^      - name: Apply the agent.s issue intents/ { printing = 1 }
    printing && /^      - name:/ && !/^      - name: Apply the agent.s issue intents/ { exit }
    printing { print }
  ')"
  [ -n "$apply_step" ] || { echo "selftest: settle has no Apply the agent's issue intents step" >&2; exit 1; }
  grep -q -- '--apply-intents' <<<"$apply_step" || {
    echo "selftest: the settle applier does not pass --apply-intents" >&2
    exit 1
  }
  grep -q 'intents_uploaded' <<<"$apply_step" || {
    echo "selftest: the settle applier does not gate on the trusted upload" >&2
    exit 1
  }
  grep -q 'DELIVER_SHA256' <<<"$apply_step" || {
    echo "selftest: the settle applier does not verify the pinned script hash" >&2
    exit 1
  }
  grep -q 'actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131' <<<"$settle_job" || {
    echo "selftest: settle does not download the intents with the pinned action" >&2
    exit 1
  }
  # The settle job is the one issue-writing job left in this workflow —
  # checked against its permissions stanza, not its prose (the run-job
  # rule above).
  local settle_perms
  settle_perms="$(awk '/^    permissions:/ { p = 1; next } p && /^      [-a-z]+:/ { print; next } p && /^      #/ { next } p { exit }' <<<"$settle_job")"
  grep -q 'issues: write' <<<"$settle_perms" || {
    echo "selftest: settle cannot write issues (the applier lives there)" >&2
    exit 1
  }
  # The skill the agent runs must teach the intents protocol, or an
  # unattended run posts nothing at all.
  local skill_doc
  skill_doc="${repo_root}/.claude/skills/design-run/SKILL.md"
  [ -f "$skill_doc" ] || { echo "selftest: design-run SKILL.md is missing" >&2; exit 1; }
  grep -q '\.design-run-intents\.json' "$skill_doc" || {
    echo "selftest: the design-run skill does not document the intents file" >&2
    exit 1
  }
  # The worktree file must be ignored (never committed) and forbidden by
  # the bundle's path check.
  grep -q '^\.design-run-intents\.json$' "${repo_root}/.gitignore" || {
    echo "selftest: .gitignore does not list the intents file" >&2
    exit 1
  }
  grep -q '\.design-run-intents\.json' "$SELF" || {
    echo "selftest: forbidden_path does not refuse the intents file" >&2
    exit 1
  }
  grep -q 'transfer.fsckObjects=true' "$SELF" || {
    echo "selftest: bundle fetch does not set transfer.fsckObjects" >&2
    exit 1
  }
  grep -q 'fetch-depth: 0' "$deliver_workflow" || {
    echo "selftest: deliver checkout is not a full history" >&2
    exit 1
  }
  grep -q 'fetch-depth: 0' "$workflow" || {
    echo "selftest: triage checkout is not a full history" >&2
    exit 1
  }
  grep -q 'START_SHA" != "$GITHUB_SHA"' "$workflow" || {
    echo "selftest: triage job does not assert START_SHA against github.sha" >&2
    exit 1
  }
  grep -q 'merge-base --is-ancestor "$GITHUB_SHA" "$START_SHA"' "$workflow" || {
    echo "selftest: triage job does not allow a newer default-branch pin" >&2
    exit 1
  }
  grep -q 'START_SHA" != "$WORKFLOW_HEAD_SHA"' "$deliver_workflow" || {
    echo "selftest: deliver job does not assert START_SHA against the triggering head" >&2
    exit 1
  }
  grep -q 'merge-base --is-ancestor "$WORKFLOW_HEAD_SHA" "$START_SHA"' "$deliver_workflow" || {
    echo "selftest: deliver job does not allow a newer default-branch pin" >&2
    exit 1
  }
  if grep -q 'merge-base --is-ancestor "$GITHUB_SHA" "$START_SHA"' "$deliver_workflow"; then
    echo "selftest: deliver job compares START_SHA to workflow_run GITHUB_SHA" >&2
    exit 1
  fi
  grep -q 'merge-base --is-ancestor "$START_SHA" "origin/${BASE_BRANCH}"' "$deliver_workflow" || {
    echo "selftest: deliver job does not require START_SHA on the default branch" >&2
    exit 1
  }
  grep -q 'head_branch == github.event.repository.default_branch' "$deliver_workflow" || {
    echo "selftest: deliver job does not require the triggering head branch" >&2
    exit 1
  }
  pin_line="$(grep -n 'name: Verify the delivery pin' "$deliver_workflow" | head -1 | cut -d: -f1)"
  checkout_line="$(grep -n 'name: Checkout the default branch' "$deliver_workflow" | head -1 | cut -d: -f1)"
  [ -n "$pin_line" ] && [ -n "$checkout_line" ] && [ "$pin_line" -lt "$checkout_line" ] || {
    echo "selftest: the delivery pin is not verified before checkout" >&2
    exit 1
  }
  if grep -q 'ref: ${{ steps.parsed.outputs.start_sha }}' "$deliver_workflow"; then
    echo "selftest: checkout still uses the artifact start_sha" >&2
    exit 1
  fi
  if grep -q 'git fetch' "$deliver_workflow"; then
    echo "selftest: delivery fetches a commit by id" >&2
    exit 1
  fi
  pin_gates="$(grep -c "steps.pin.outcome == 'success'" "$deliver_workflow" || true)"
  [ "$pin_gates" -eq 3 ] || {
    echo "selftest: download, deliver, and the red step must be gated on the pin, and lock cleanup must not be (found ${pin_gates})" >&2
    exit 1
  }
  if awk '
    /name: Release the SHIP-LOCK after delivery/ { found = 1; n = 0 }
    found { n++; if ($0 ~ /steps.pin.outcome/) bad = 1 }
    found && n > 12 { exit }
    END { exit bad ? 1 : 0 }
  ' "$deliver_workflow"; then
    :
  else
    echo "selftest: lock cleanup is still gated on the delivery pin" >&2
    exit 1
  fi
  grep -q 'metadata issue' "$deliver_workflow" || {
    echo "selftest: deliver does not require the metadata issue to match the pre-agent lock" >&2
    exit 1
  }
  grep -q 'Upload the delivery metadata' "$deliver_workflow" || {
    echo "selftest: deliver does not require the trusted metadata upload step" >&2
    exit 1
  }
  grep -q "always() && (steps.lock_parsed.outcome == 'success' || steps.parsed.outcome == 'success')" "$deliver_workflow" || {
    echo "selftest: deliver checkout is skipped when an earlier step failed" >&2
    exit 1
  }
  grep -q 'RUNNER_TEMP: \${{ runner.temp }}' "$workflow" || {
    echo "selftest: post-agent steps do not pin RUNNER_TEMP to runner.temp" >&2
    exit 1
  }
  grep -q 'show "$WORKFLOW_HEAD_SHA:scripts/routine-lock-cleanup.sh"' "$deliver_workflow" || {
    echo "selftest: lock cleanup does not read the script from the triggering head" >&2
    exit 1
  }
  if grep -q 'START_SHA:scripts/routine-lock-cleanup.sh' "$deliver_workflow" \
    || grep 'checkout "$START_SHA" -- scripts/routine-lock-cleanup.sh' "$deliver_workflow" >/dev/null; then
    echo "selftest: lock cleanup still takes its script from START_SHA" >&2
    exit 1
  fi
  pin_run="$(awk '
    /^      - name: Verify the delivery pin/ { in_step = 1 }
    in_step && /^        run: \|/ { printing = 1; next }
    in_step && printing && /^      - name:/ { exit }
    printing { print }
  ' "$deliver_workflow")"
  [ -n "$pin_run" ] || { echo "selftest: could not extract the pin step" >&2; exit 1; }
  pin_stub="${tmp}/pin-bin"
  pin_log="${tmp}/pin.log"
  pin_map="${tmp}/pin.map"
  pin_out="${tmp}/pin.out"
  pin_err="${tmp}/pin.err"
  mkdir -p "$pin_stub"
  cat > "$pin_stub/gh" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> "${GH_LOG:?}"
url=""
for a in "$@"; do
  case "$a" in
    repos/*/compare/*) url="$a" ;;
  esac
done
spec="${url##*compare/}"
[ -n "$spec" ] || { echo "gh: no compare url" >&2; exit 2; }
[ -f "${GH_MAP:?}" ] || { echo "gh: no map" >&2; exit 2; }
status="$(awk -v s="$spec" '$1 == s { print $2; found = 1 } END { exit found ? 0 : 1 }' "$GH_MAP")" || {
  echo "gh: unmapped ${spec}" >&2
  exit 2
}
printf '%s\n' "$status"
EOF
  chmod +x "$pin_stub/gh"
  run_pin() {
    local start="$1" head="$2" branch="$3" map="$4" rc
    : > "$pin_log"
    printf '%s\n' "$map" > "$pin_map"
    : > "$pin_out"
    set +e
    START_SHA="$start" WORKFLOW_HEAD_SHA="$head" BASE_BRANCH="$branch" \
      GITHUB_REPOSITORY=acme/print-bench GITHUB_OUTPUT="$pin_out" \
      GH_LOG="$pin_log" GH_MAP="$pin_map" \
      PATH="$pin_stub:/usr/bin:/bin" \
      bash -eo pipefail -c "$pin_run" >"$pin_err" 2>&1
    rc=$?
    set -e
    printf '%s\n' "$rc"
  }
  pin_a="1111111111111111111111111111111111111111"
  pin_b="2222222222222222222222222222222222222222"
  pin_c="3333333333333333333333333333333333333333"
  [ "$(run_pin "$pin_a" "$pin_a" main "")" -eq 0 ] || {
    echo "selftest: a pin equal to the triggering head was refused" >&2
    cat "$pin_err" >&2
    exit 1
  }
  [ ! -s "$pin_log" ] || {
    echo "selftest: an equal pin called the compare API" >&2
    exit 1
  }
  grep -qx 'verified=head' "$pin_out" || {
    echo "selftest: an equal pin did not record verified=head" >&2
    exit 1
  }
  [ "$(run_pin "$pin_c" "$pin_a" main "${pin_a}...${pin_c} diverged")" -ne 0 ] || {
    echo "selftest: a mismatched start_sha was accepted" >&2
    exit 1
  }
  [ "$(run_pin "$pin_b" "$pin_a" main "$(printf '%s\n' "${pin_a}...${pin_b} ahead" "${pin_b}...main ahead")")" -eq 0 ] || {
    echo "selftest: a start_sha on the default branch ahead of the triggering head was refused" >&2
    cat "$pin_err" >&2
    exit 1
  }
  grep -qx 'verified=ancestor' "$pin_out" || {
    echo "selftest: an ancestor pin did not record verified=ancestor" >&2
    exit 1
  }
  [ "$(run_pin "$pin_c" "$pin_a" main "$(printf '%s\n' "${pin_a}...${pin_c} ahead" "${pin_c}...main diverged")")" -ne 0 ] || {
    echo "selftest: a start_sha that is not an ancestor of the default branch was accepted" >&2
    exit 1
  }
  if awk '
    /^permissions:/ { p = 1; next }
    p && /^[^ ]/ { exit }
    p && /^  actions:/ { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$workflow"; then
    echo "selftest: workflow permissions still grant actions" >&2
    exit 1
  fi
  if awk '
    /^permissions:/ { p = 1; next }
    p && /^[^ ]/ { exit }
    p && /^  actions: write/ { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$deliver_workflow"; then
    echo "selftest: deliver workflow grants actions: write" >&2
    exit 1
  fi
  grep -q '^  actions: read$' "$deliver_workflow" || {
    echo "selftest: deliver workflow does not grant actions: read" >&2
    exit 1
  }
  skill="${repo_root}/.claude/skills/design-run/SKILL.md"
  grep -q 'subscribe_pr_activity' "$skill" || {
    echo "selftest: SKILL.md does not mention subscribe_pr_activity" >&2
    exit 1
  }
  grep -q 'Do not call `subscribe_pr_activity`' "$skill" || {
    echo "selftest: SKILL.md does not forbid subscribe_pr_activity" >&2
    exit 1
  }
  grep -q 'does not exist yet' "$skill" || {
    echo "selftest: SKILL.md does not say a deliver-job PR does not exist yet" >&2
    exit 1
  }
  grep -q 'Do not `git push`' "$skill" || {
    echo "selftest: SKILL.md still tells the agent it may push" >&2
    exit 1
  }
  grep -q 'do not `gh pr create`' "$skill" || {
    echo "selftest: SKILL.md does not forbid gh pr create" >&2
    exit 1
  }
  if grep -q 'You may `git push`' "$skill"; then
    echo "selftest: SKILL.md still authorizes git push" >&2
    exit 1
  fi
  if grep -q 'secrets.GH_TOKEN' "$workflow" || grep 'HAS_GH_TOKEN' "$workflow" >/dev/null; then
    echo "selftest: the run workflow still references the push PAT" >&2
    exit 1
  fi
  if grep -q 'github_token: \${{ secrets.GH_TOKEN }}' "$workflow" || grep 'github_token: \${{ secrets.GH_TOKEN }}' "$deliver_workflow" >/dev/null; then
    echo "selftest: an agent step still receives the push PAT" >&2
    exit 1
  fi
  agent_token_n="$(grep -c 'github_token: \${{ github.token }}' "$workflow" || true)"
  [ "$agent_token_n" -eq 5 ] || {
    echo "selftest: expected 5 agent github.token wires, found ${agent_token_n}" >&2
    exit 1
  }
  pat_n="$(grep -c 'GH_TOKEN: \${{ secrets.GH_TOKEN }}' "$deliver_workflow" || true)"
  [ "$pat_n" -eq 1 ] || {
    echo "selftest: the push PAT must appear on exactly one deliver step, found ${pat_n}" >&2
    exit 1
  }
  scrub_n="$(grep -c 'CLAUDE_CODE_SUBPROCESS_ENV_SCRUB: "1"' "$workflow" || true)"
  [ "$scrub_n" -eq 5 ] || {
    echo "selftest: expected 5 subprocess env scrubs, found ${scrub_n}" >&2
    exit 1
  }
  if grep -q 'CLAUDE_CODE_SUBPROCESS_ENV_SCRUB: "0"' "$workflow"; then
    echo "selftest: design-run must not set SCRUB=0 (issue #875 / Cipher #876)" >&2
    exit 1
  fi
  if grep -Eiq 'sysctl -w kernel\.apparmor_restrict_unprivileged_userns=0|echo 0 \| sudo tee /proc/sys/kernel/apparmor_restrict_unprivileged_userns' "$workflow"; then
    echo "selftest: design-run must not clear apparmor_restrict_unprivileged_userns (Cipher #876)" >&2
    exit 1
  fi
  if grep -Eiq 'curl .*install\.sh(\s|\|)|install\.sh \| bash|bootstrap\.sh' "$workflow"; then
    echo "selftest: design-run must not curl|bash install.sh (Cipher #876)" >&2
    exit 1
  fi
  preflight_line="$(grep -n 'name: Install bubblewrap and pinned Claude Code before disabling sudo' "$workflow" | head -1 | cut -d: -f1)"
  sudo_line="$(grep -n 'name: Disable sudo before the agent' "$workflow" | head -1 | cut -d: -f1)"
  smoke_line="$(grep -n 'name: Smoke-test Claude SCRUB=1 sandbox as the agent user' "$workflow" | head -1 | cut -d: -f1)"
  verify1_line="$(grep -n 'name: Verify Claude Code pin (before link 1)' "$workflow" | head -1 | cut -d: -f1)"
  agent_line="$(grep -n 'name: Run via Z.AI (GLM, chain link 1)' "$workflow" | head -1 | cut -d: -f1)"
  [ -n "$preflight_line" ] && [ -n "$sudo_line" ] && [ -n "$smoke_line" ] \
    && [ -n "$verify1_line" ] && [ -n "$agent_line" ] \
    && [ "$preflight_line" -lt "$sudo_line" ] && [ "$sudo_line" -lt "$smoke_line" ] \
    && [ "$smoke_line" -lt "$verify1_line" ] && [ "$verify1_line" -lt "$agent_line" ] || {
    echo "selftest: design-run preflight → disable-sudo → scrub smoke → verify → agent (Cipher #876)" >&2
    exit 1
  }
  grep -q 'bubblewrap apparmor-profiles' "$workflow" && grep -q 'ripgrep' "$workflow" || {
    echo "selftest: design-run preflight does not apt-get bubblewrap+apparmor-profiles+ripgrep" >&2
    exit 1
  }
  grep -q 'setup-bwrap-apparmor.sh' "$workflow" || {
    echo "selftest: design-run missing setup-bwrap-apparmor.sh" >&2
    exit 1
  }
  grep -q 'install-claude-code-pin.sh' "$workflow" || {
    echo "selftest: design-run missing install-claude-code-pin.sh" >&2
    exit 1
  }
  grep -q 'smoke-claude-scrub-sandbox.sh' "$workflow" || {
    echo "selftest: design-run missing smoke-claude-scrub-sandbox.sh" >&2
    exit 1
  }
  grep -q 'verify-claude-code-pin.sh' "$workflow" || {
    echo "selftest: design-run missing verify-claude-code-pin.sh" >&2
    exit 1
  }
  path_pin_n="$(grep -c 'path_to_claude_code_executable: \${{ steps.preflight.outputs.claude_bin }}' "$workflow" || true)"
  [ "$path_pin_n" -eq 5 ] || {
    echo "selftest: expected 5 design-run path_to_claude_code_executable pins, found ${path_pin_n}" >&2
    exit 1
  }
  for gate in "steps.preflight.outcome == 'success'" "steps.disable_sudo.outcome == 'success'" \
    "steps.scrub_smoke.outcome == 'success'"; do
    gate_n="$(grep -c "$gate" "$workflow" || true)"
    # 5 agent + 5 verify + smoke/disable references vary; require >= 5 on agent path
    [ "$gate_n" -ge 5 ] || {
      echo "selftest: design-run expected >=5 gates on ${gate}, found ${gate_n}" >&2
      exit 1
    }
  done
  verify_gate_n="$(grep -c "steps.verify_claude_[1-5].outcome == 'success'" "$workflow" || true)"
  [ "$verify_gate_n" -eq 5 ] || {
    echo "selftest: expected 5 design-run agent steps gated on verify_claude_N, found ${verify_gate_n}" >&2
    exit 1
  }
  verify_step_n="$(grep -c 'name: Verify Claude Code pin (before link' "$workflow" || true)"
  [ "$verify_step_n" -eq 5 ] || {
    echo "selftest: expected 5 design-run per-link verify steps, found ${verify_step_n}" >&2
    exit 1
  }
  grep -q 'sudo -n true' "$workflow" || {
    echo "selftest: the sudo disable step does not prove sudo is gone" >&2
    exit 1
  }
  grep -q 'docker info' "$workflow" || {
    echo "selftest: the sudo disable step does not prove docker is unreachable" >&2
    exit 1
  }
  grep -q '/var/run/docker.sock' "$workflow" || {
    echo "selftest: the sudo disable step does not remove the docker socket" >&2
    exit 1
  }
  grep -q -- '--slurp' "$workflow" || {
    echo "selftest: the label strip does not merge paginated event pages" >&2
    exit 1
  }
  grep -q 'AGENT_WINDOW_END' "$workflow" || {
    echo "selftest: the label strip does not bound the agent window" >&2
    exit 1
  }
  run_perms="$(awk '/^  run:/{p=1} p && /^  [A-Za-z]/ && !/^  run:/{exit} p' "$workflow")"
  # A pipe into grep -q dies with SIGPIPE under pipefail: the match is near
  # the top of the job and grep exits before printf finishes writing.
  case "$run_perms" in
    *"pull-requests: read"*) ;;
    *) echo "selftest: the run job does not set pull-requests: read" >&2; exit 1 ;;
  esac
  case "$run_perms" in
    *"pull-requests: write"*)
      echo "selftest: the run job still grants pull-requests: write" >&2
      exit 1 ;;
  esac
  settings="${repo_root}/.claude/design-run-settings.json"
  for rule in 'Bash(git push:*)' 'Bash(git push*)' 'Bash(gh pr create:*)' 'Bash(gh pr create*)' \
    'Bash(gh issue edit*design-brief*)' 'Bash(gh issue edit*autonomy-ok*)' \
    'Bash(gh api*design-brief*)' 'Bash(gh api*autonomy-ok*)' \
    'Bash(curl*design-brief*)' 'Bash(curl*autonomy-ok*)'; do
    grep -qF "\"${rule}\"" "$settings" || {
      echo "selftest: design-run settings missing deny ${rule}" >&2
      exit 1
    }
  done
  grep -q 'name: Strip bot-added opt-in labels' "$workflow" || {
    echo "selftest: bot-added opt-in labels are not stripped" >&2
    exit 1
  }
  grep -q 'github-actions\[bot\]' "$workflow" || {
    echo "selftest: the label strip does not key on the bot actor" >&2
    exit 1
  }
  grep -q 'needs-decision is never removed' "$workflow" || {
    echo "selftest: the label strip does not leave needs-decision alone" >&2
    exit 1
  }
  grep -q '  settle:' "$workflow" || {
    echo "selftest: label strip and lock cleanup are not in a fresh settle job" >&2
    exit 1
  }
  if grep -q 'name: Drop agent PATH and env plants' "$workflow"; then
    echo "selftest: the run job still claims to neutralize GITHUB_PATH and GITHUB_ENV" >&2
    exit 1
  fi
  dontask_n="$(grep -c -- '--permission-mode dontAsk --settings .claude/design-run-settings.json' "$workflow" || true)"
  [ "$dontask_n" -eq 5 ] || {
    echo "selftest: expected 5 dontAsk deny-backstop steps, found ${dontask_n}" >&2
    exit 1
  }
  if grep -q 'bypassPermissions' "$workflow" && grep -q 'claude_args:.*bypassPermissions' "$workflow"; then
    echo "selftest: an agent step still uses bypassPermissions" >&2
    exit 1
  fi
  printf '%s\n' "$deliver_run" | grep 'reap_agent_orphans' >/dev/null || {
    echo "selftest: the bundle step does not reap detached agent processes" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep 'now" != "$captured"' >/dev/null || {
    echo "selftest: the bundle step does not re-check the bundle after the reap" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep 'reap_should_kill' >/dev/null || {
    echo "selftest: the bundle step does not classify orphans" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep 'run-\*\.scope' >/dev/null || {
    echo "selftest: the bundle reaper does not catch systemd-run scopes" >&2
    exit 1
  }
  reap_n="$(grep -c 'reap_should_kill()' "$workflow" || true)"
  [ "$reap_n" -eq 1 ] || {
    echo "selftest: expected the reaper predicate in the bundle step, found ${reap_n}" >&2
    exit 1
  }
  reap_a="$(awk '
    /reap_should_kill\(\) \{/ { c++; if (c==1) p=1 }
    p { print }
    p && /^          \}$/ { exit }
  ' "$workflow")"
  (
    eval "$reap_a"
    export GITHUB_WORKSPACE=/work RUNNER_TEMP=/tmp/rt
    expect_kill() {
      if ! reap_should_kill "$@"; then
        echo "selftest: reap_should_kill kept a process it must kill: $*" >&2
        exit 1
      fi
    }
    expect_keep() {
      if reap_should_kill "$@"; then
        echo "selftest: reap_should_kill killed a process it must keep: $*" >&2
        exit 1
      fi
    }
    expect_kill 50 1 sleep /work/x sleep 9 "" 99 1
    expect_keep 50 1 Runner.Worker /work/x runner 9 "" 99 1
    expect_kill 70 400 bash /work/x bash 70 "" 99 1
    expect_keep 99 400 bash /work/x bash 99 "" 99 1
    expect_kill 80 200 sleep /work/x sleep 10 "0::/system.slice/run-u123.scope" 99 1
    expect_keep 2 0 systemd /work/x systemd 2 "0::/system.slice/run-u123.scope" 99 1
    expect_keep 80 200 sleep /home/elsewhere sleep 10 "" 99 1
    expect_kill 55 1 sleep / "design-run.bundle" 3 "" 99 1
    expect_keep 1 1 bash /work/x bash 1 "" 99 1
  )
  grep -q '  triage:' "$workflow" || {
    echo "selftest: provider-triage is not a separate job" >&2
    exit 1
  }
  if grep -q 'Restore provider-triage from the pinned commit' "$workflow"; then
    echo "selftest: provider-triage is still restored inside the agent job" >&2
    exit 1
  fi
  grep -q 'ref: \${{ needs.run.outputs.start_sha }}' "$workflow" || {
    echo "selftest: the triage job does not check out START_SHA" >&2
    exit 1
  }
  grep -q 'PYTHONSAFEPATH: "1"' "$workflow" || {
    echo "selftest: provider-triage does not set PYTHONSAFEPATH" >&2
    exit 1
  }
  grep -q 'steps.verify_triage.outcome == '"'"'success'"'"'' "$workflow" || {
    echo "selftest: provider-triage does not wait for the fresh checkout" >&2
    exit 1
  }
  grep -q '/usr/bin/python3 -m model_registry classify' "${repo_root}/.github/actions/provider-triage/action.yml" || {
    echo "selftest: provider-triage does not pin /usr/bin/python3" >&2
    exit 1
  }
  if grep -q 'PR the delivery step verified' "$skill"; then
    echo "selftest: SKILL.md still subscribes to a PR the deliver job has not opened" >&2
    exit 1
  fi
  printf '%s\n' "$deliver_run" | grep 'GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_OBJECT_DIRECTORY' >/dev/null || {
    echo "selftest: deliver step does not drop alternate object dirs" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep 'GIT_CONFIG_PARAMETERS' >/dev/null || {
    echo "selftest: deliver step does not drop GIT_CONFIG_PARAMETERS" >&2
    exit 1
  }
  # #923: settle restore must pin --no-replace-objects + hooksPath and use
  # mktemp→mv (never redirect onto a fixed path that may be a symlink).
  grep -E 'git --no-replace-objects -c core\.hooksPath=/dev/null( -c core\.(fsmonitor=false|sshCommand=))* show "\$START_SHA:scripts/routine-lock-cleanup\.sh"' "$workflow" >/dev/null || {
    echo "selftest: lock-cleanup restore is missing --no-replace-objects and hooksPath" >&2
    exit 1
  }
  grep 'mktemp "${RUNNER_TEMP}/routine-lock-cleanup-blob.XXXXXX"' "$workflow" >/dev/null || {
    echo "selftest: lock-cleanup restore is missing mktemp→mv (#923)" >&2
    exit 1
  }
  grep 'lock-cleanup restore did not leave a regular file' "$workflow" >/dev/null || {
    echo "selftest: lock-cleanup restore dropped the regular-file refusal (#923)" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep 'RUNNER_TEMP' >/dev/null || {
    echo "selftest: deliver step does not stage the script in RUNNER_TEMP" >&2
    exit 1
  }
  printf '%s\n' "$deliver_run" | grep 'refusing to restore design-run-deliver' >/dev/null || {
    echo "selftest: deliver step does not refuse a symlink restore" >&2
    exit 1
  }
  if printf '%s\n' "$deliver_run" | grep './scripts/design-run-deliver.sh' >/dev/null; then
    echo "selftest: deliver step still executes the worktree script" >&2
    exit 1
  fi

  # backlog-burn wiring (issue #863, the #859/#861 pattern; path policy
  # tightened in #869). The burn's agent steps must never see the PAT,
  # the PAT lives only in the deliver workflow's push step, and the
  # bundle handoff carries --routine backlog-burn so the shared
  # protected-prefix policy (.github/.claude/scripts/tools) is explicit.
  burn="${repo_root}/.github/workflows/backlog-burn.yml"
  [ -f "$burn" ] || { echo "selftest: backlog-burn.yml is missing" >&2; exit 1; }
  burn_run="$(awk '
    /^      - name: Bundle the ship commits/ { in_step = 1 }
    in_step && /^        run: \|/ { printing = 1; next }
    in_step && printing && /^      - name:/ { exit }
    printing { print }
  ' "$burn")"
  [ -n "$burn_run" ] || { echo "selftest: could not extract the burn bundle run block" >&2; exit 1; }
  printf '%s\n' "$burn_run" | grep '/usr/bin/git --no-replace-objects -c core.hooksPath=/dev/null -c core.fsmonitor=false -c core.sshCommand= show "$START_SHA:scripts/design-run-deliver.sh"' >/dev/null || {
    echo "selftest: burn bundle step does not git-show the pinned script" >&2
    exit 1
  }
  printf '%s\n' "$burn_run" | grep 'DELIVER_SHA256' >/dev/null || {
    echo "selftest: burn bundle step does not check the pre-agent sha256" >&2
    exit 1
  }
  printf '%s\n' "$burn_run" | grep 'objects/info/alternates' >/dev/null || {
    echo "selftest: burn bundle step does not refuse object alternates" >&2
    exit 1
  }
  printf '%s\n' "$burn_run" | grep -- '--routine backlog-burn --write-bundle "${RUNNER_TEMP}/backlog-burn.bundle"' >/dev/null || {
    echo "selftest: burn bundle step does not write the backlog-burn bundle" >&2
    exit 1
  }
  printf '%s\n' "$burn_run" | grep 'refusing to restore design-run-deliver' >/dev/null || {
    echo "selftest: burn bundle step does not refuse a symlink restore" >&2
    exit 1
  }
  printf '%s\n' "$burn_run" | grep './scripts/design-run-deliver.sh' >/dev/null && {
    echo "selftest: burn bundle step still executes the worktree script" >&2
    exit 1
  }
  printf '%s\n' "$burn_run" | grep 'reap_agent_orphans' >/dev/null || {
    echo "selftest: burn bundle step does not reap detached agent processes" >&2
    exit 1
  }
  printf '%s\n' "$burn_run" | grep 'now" != "$captured"' >/dev/null || {
    echo "selftest: burn bundle step does not re-check the bundle after the reap" >&2
    exit 1
  }
  grep -q 'deliver_sha256=' "$burn" || {
    echo "selftest: the burn pre-agent pin does not record deliver_sha256" >&2
    exit 1
  }
  grep -q 'DELIVER_WORKTREE: \${{ github.workspace }}' "$burn" || {
    echo "selftest: burn bundle step does not pin DELIVER_WORKTREE to the checkout" >&2
    exit 1
  }
  grep -q 'shell: /usr/bin/bash --noprofile --norc' "$burn" || {
    echo "selftest: burn trusted steps do not pin an absolute shell" >&2
    exit 1
  }
  grep -q 'actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9' "$burn" || {
    echo "selftest: the burn artifacts are not uploaded from the pinned v7 action" >&2
    exit 1
  }
  if grep -q 'actions/upload-artifact@v7' "$burn" || grep 'actions/checkout@v7' "$burn" >/dev/null || grep -q 'actions/setup-python@v7' "$burn"; then
    echo "selftest: backlog-burn.yml still uses a floating v7 action tag" >&2
    exit 1
  fi
  grep -q 'retention-days: 1' "$burn" || {
    echo "selftest: the burn artifacts have no short retention" >&2
    exit 1
  }
  grep -q 'name: backlog-burn-lock' "$burn" || {
    echo "selftest: the burn job does not publish the SHIP-LOCK context" >&2
    exit 1
  }
  grep -q 'name: backlog-burn-bundle' "$burn" || {
    echo "selftest: the burn job does not upload the ship bundle" >&2
    exit 1
  }
  grep -q 'name: backlog-burn-meta' "$burn" || {
    echo "selftest: the burn job does not upload delivery metadata" >&2
    exit 1
  }
  # AC4: the arming variable, the cadence and the workflow name (the
  # deliver workflow_run trigger keys on it) are untouched.
  grep -q "^name: Backlog burn (scheduled /ship-issue)$" "$burn" || {
    echo "selftest: the burn workflow name changed" >&2
    exit 1
  }
  grep -q -e "- cron: '17 \* \* \* \*'" "$burn" || {
    echo "selftest: the burn cadence changed" >&2
    exit 1
  }
  grep -q "vars.BACKLOG_BURN_ENABLED == 'true'" "$burn" || {
    echo "selftest: the burn arming gate changed" >&2
    exit 1
  }
  if grep -q 'secrets.GH_TOKEN' "$burn" || grep 'HAS_GH_TOKEN' "$burn" >/dev/null; then
    echo "selftest: the burn workflow still references the push PAT" >&2
    exit 1
  fi
  if grep -q 'github_token: \${{ secrets.GH_TOKEN' "$burn"; then
    echo "selftest: a burn agent step still receives the push PAT" >&2
    exit 1
  fi
  if grep -q 'name: Note a checkless draft PR' "$burn"; then
    echo "selftest: the checkless-PR notice step is still present" >&2
    exit 1
  fi
  burn_token_n="$(grep -c 'github_token: \${{ github.token }}' "$burn" || true)"
  [ "$burn_token_n" -eq 5 ] || {
    echo "selftest: expected 5 burn agent github.token wires, found ${burn_token_n}" >&2
    exit 1
  }
  burn_dontask_n="$(grep -c -- '--permission-mode dontAsk --settings .claude/backlog-burn-settings.json' "$burn" || true)"
  [ "$burn_dontask_n" -eq 5 ] || {
    echo "selftest: expected 5 burn dontAsk deny-backstop steps, found ${burn_dontask_n}" >&2
    exit 1
  }
  if grep -q 'claude_args:.*bypassPermissions' "$burn"; then
    echo "selftest: a burn agent step still uses bypassPermissions" >&2
    exit 1
  fi
  burn_scrub_n="$(grep -c 'CLAUDE_CODE_SUBPROCESS_ENV_SCRUB: "1"' "$burn" || true)"
  [ "$burn_scrub_n" -eq 5 ] || {
    echo "selftest: expected 5 burn subprocess env scrubs, found ${burn_scrub_n}" >&2
    exit 1
  }
  if grep -q 'CLAUDE_CODE_SUBPROCESS_ENV_SCRUB: "0"' "$burn"; then
    echo "selftest: backlog-burn must not set SCRUB=0 (issue #875 / Cipher #876)" >&2
    exit 1
  fi
  if grep -Eiq 'sysctl -w kernel\.apparmor_restrict_unprivileged_userns=0|echo 0 \| sudo tee /proc/sys/kernel/apparmor_restrict_unprivileged_userns' "$burn"; then
    echo "selftest: backlog-burn must not clear apparmor_restrict_unprivileged_userns (Cipher #876)" >&2
    exit 1
  fi
  if grep -Eiq 'curl .*install\.sh(\s|\|)|install\.sh \| bash|bootstrap\.sh' "$burn"; then
    echo "selftest: backlog-burn must not curl|bash install.sh (Cipher #876)" >&2
    exit 1
  fi
  burn_install_line="$(grep -n 'name: Install preflight toolchain before disabling sudo' "$burn" | head -1 | cut -d: -f1)"
  burn_sudo_line="$(grep -n 'name: Disable sudo before the agent' "$burn" | head -1 | cut -d: -f1)"
  burn_smoke_line="$(grep -n 'name: Smoke-test Claude SCRUB=1 sandbox as the agent user' "$burn" | head -1 | cut -d: -f1)"
  burn_verify1_line="$(grep -n 'name: Verify Claude Code pin (before link 1)' "$burn" | head -1 | cut -d: -f1)"
  burn_agent_line="$(grep -n 'name: Ship via Z.AI (GLM, chain link 1)' "$burn" | head -1 | cut -d: -f1)"
  [ -n "$burn_install_line" ] && [ -n "$burn_sudo_line" ] && [ -n "$burn_smoke_line" ] \
    && [ -n "$burn_verify1_line" ] && [ -n "$burn_agent_line" ] \
    && [ "$burn_install_line" -lt "$burn_sudo_line" ] \
    && [ "$burn_sudo_line" -lt "$burn_smoke_line" ] \
    && [ "$burn_smoke_line" -lt "$burn_verify1_line" ] \
    && [ "$burn_verify1_line" -lt "$burn_agent_line" ] || {
    echo "selftest: burn preflight → disable-sudo → scrub smoke → verify → agent (Cipher #876)" >&2
    exit 1
  }
  burn_pip_line="$(grep -n 'name: Install preflight Python tools after disabling sudo' "$burn" | head -1 | cut -d: -f1)"
  # apt (needs root) before disable-sudo; pip (no root) after it; then the agent.
  # A pip install that drifts back before disable-sudo reopens Cipher #868 LOW.
  [ -n "$burn_install_line" ] && [ -n "$burn_sudo_line" ] && [ -n "$burn_pip_line" ] \
    && [ -n "$burn_agent_line" ] \
    && [ "$burn_install_line" -lt "$burn_sudo_line" ] \
    && [ "$burn_sudo_line" -lt "$burn_pip_line" ] \
    && [ "$burn_pip_line" -lt "$burn_agent_line" ] || {
    echo "selftest: apt preflight must precede disable-sudo, which must precede pip, which must precede the burn agent" >&2
    exit 1
  }
  burn_printcheck_pip_line="$(grep -n 'pip install .*tools/printcheck' "$burn" | head -1 | cut -d: -f1)"
  burn_stylelift_pip_line="$(grep -n 'pip install .*tools/stylelift' "$burn" | head -1 | cut -d: -f1)"
  [ -n "$burn_printcheck_pip_line" ] && [ -n "$burn_stylelift_pip_line" ] \
    && [ "$burn_printcheck_pip_line" -gt "$burn_sudo_line" ] \
    && [ "$burn_stylelift_pip_line" -gt "$burn_sudo_line" ] || {
    echo "selftest: burn pip installs of printcheck/stylelift must run after disable-sudo" >&2
    exit 1
  }
  # Hashed lockfile install (Cipher HOLD on #878): fail-closed PyPI pins.
  grep -q -- '--require-hashes' "$burn" || {
    echo "selftest: burn preflight_pip must pip install --require-hashes" >&2
    exit 1
  }
  grep -q 'backlog-burn-preflight-requirements.txt' "$burn" || {
    echo "selftest: burn preflight_pip must install from backlog-burn-preflight-requirements.txt" >&2
    exit 1
  }
  [ -f "${repo_root}/.github/backlog-burn-preflight-requirements.txt" ] || {
    echo "selftest: .github/backlog-burn-preflight-requirements.txt is missing" >&2
    exit 1
  }
  grep -qE '^[^#].*--hash=sha256:' \
    "${repo_root}/.github/backlog-burn-preflight-requirements.txt" || {
    echo "selftest: backlog-burn-preflight-requirements.txt has no sha256 hashes" >&2
    exit 1
  }
  # Local tools must be --no-deps --no-build-isolation so they cannot resolve
  # unpinned PyPI deps (including build backends via PEP 517 isolation).
  grep -q 'pip install --no-deps --no-build-isolation -e .*tools/printcheck' "$burn" || {
    echo "selftest: burn must pip install --no-deps --no-build-isolation -e tools/printcheck" >&2
    exit 1
  }
  grep -q 'pip install --no-deps --no-build-isolation -e .*tools/stylelift' "$burn" || {
    echo "selftest: burn must pip install --no-deps --no-build-isolation -e tools/stylelift" >&2
    exit 1
  }
  if grep -qE 'pip install .*printcheck\[test\]|pip install .*stylelift\[test\]' "$burn"; then
    echo "selftest: burn must not pip install printcheck/stylelift[test] (unpinned extras)" >&2
    exit 1
  fi
  grep -q -- '--only-binary :all:' "$burn" || {
    echo "selftest: burn preflight_pip must pip install --only-binary :all:" >&2
    exit 1
  }
  # tools/backlog-burn is stdlib-only: run via PYTHONPATH, never pip install
  # before disable-sudo (Cipher HOLD on #878 — unhashed setuptools via -e).
  # Skip full-line comments so a "# No pip install …" note is not a hit.
  burn_bb_pip_line="$(
    awk -v sudo="$burn_sudo_line" '
      /^[[:space:]]*#/ { next }
      /pip install .*tools\/backlog-burn/ && NR <= sudo { print NR; exit }
    ' "$burn"
  )"
  if [ -n "$burn_bb_pip_line" ]; then
    echo "selftest: burn must not pip install tools/backlog-burn before disable-sudo (line ${burn_bb_pip_line})" >&2
    exit 1
  fi
  grep -q 'PYTHONPATH: tools/backlog-burn/src' "$burn" || {
    echo "selftest: burn must set PYTHONPATH=tools/backlog-burn/src for the selector" >&2
    exit 1
  }
  grep -q 'python3 -m backlog_burn.cli' "$burn" || {
    echo "selftest: burn must invoke backlog_burn via python3 -m backlog_burn.cli" >&2
    exit 1
  }
  if grep -vE '^[[:space:]]*#' "$burn" | grep -E '(^|[[:space:]])backlog-burn (config|run|select|gather)' >/dev/null; then
    echo "selftest: burn still calls the backlog-burn console script (needs install)" >&2
    exit 1
  fi
  burn_pip_gate_n="$(grep -c 'steps.preflight_pip.outcome == '\''success'\''' "$burn" || true)"
  burn_sudo_gate_n="$(grep -c 'steps.disable_sudo.outcome == '\''success'\''' "$burn" || true)"
  # disable_sudo gates preflight_pip itself plus every later verify/keyed step.
  # Those later steps must also require preflight_pip (pip_gates == sudo_gates - 1).
  # Today that is the 5 keyed ship links; when #876 adds verify_* steps they
  # must take the same preflight_pip conjunct or this equality fails.
  [ "$burn_sudo_gate_n" -ge 6 ] || {
    echo "selftest: expected at least 6 burn steps gated on disable_sudo (pip + ships), found ${burn_sudo_gate_n}" >&2
    exit 1
  }
  [ "$burn_pip_gate_n" -eq $((burn_sudo_gate_n - 1)) ] || {
    echo "selftest: every disable_sudo-gated step except preflight_pip must also gate on preflight_pip (pip=${burn_pip_gate_n} sudo=${burn_sudo_gate_n})" >&2
    exit 1
  }
  [ "$burn_pip_gate_n" -ge 5 ] || {
    echo "selftest: expected at least 5 burn steps gated on preflight_pip (keyed ships), found ${burn_pip_gate_n}" >&2
    exit 1
  }
  # apt line may wrap after prusa-slicer; require both halves.
  grep -q 'openscad xvfb imagemagick prusa-slicer' "$burn" \
    &&   grep -q 'ffmpeg gifsicle jq bubblewrap apparmor-profiles' "$burn" \
    && grep -q 'ripgrep' "$burn" || {
    echo "selftest: the burn preflight install does not apt-get toolchain + bubblewrap + apparmor-profiles + ripgrep" >&2
    exit 1
  }
  grep -q 'setup-bwrap-apparmor.sh' "$burn" || {
    echo "selftest: burn missing setup-bwrap-apparmor.sh" >&2
    exit 1
  }
  grep -q 'install-claude-code-pin.sh' "$burn" || {
    echo "selftest: burn missing install-claude-code-pin.sh" >&2
    exit 1
  }
  grep -q 'smoke-claude-scrub-sandbox.sh' "$burn" || {
    echo "selftest: burn missing smoke-claude-scrub-sandbox.sh" >&2
    exit 1
  }
  grep -q 'verify-claude-code-pin.sh' "$burn" || {
    echo "selftest: burn missing verify-claude-code-pin.sh" >&2
    exit 1
  }
  burn_path_pin_n="$(grep -c 'path_to_claude_code_executable: \${{ steps.preflight.outputs.claude_bin }}' "$burn" || true)"
  [ "$burn_path_pin_n" -eq 5 ] || {
    echo "selftest: expected 5 burn path_to_claude_code_executable pins, found ${burn_path_pin_n}" >&2
    exit 1
  }
  for gate in "steps.preflight.outcome == 'success'" "steps.disable_sudo.outcome == 'success'" \
    "steps.scrub_smoke.outcome == 'success'"; do
    gate_n="$(grep -c "$gate" "$burn" || true)"
    [ "$gate_n" -ge 5 ] || {
      echo "selftest: burn expected >=5 gates on ${gate}, found ${gate_n}" >&2
      exit 1
    }
  done
  burn_verify_gate_n="$(grep -c "steps.verify_claude_[1-5].outcome == 'success'" "$burn" || true)"
  [ "$burn_verify_gate_n" -eq 5 ] || {
    echo "selftest: expected 5 burn agent steps gated on verify_claude_N, found ${burn_verify_gate_n}" >&2
    exit 1
  }
  burn_verify_step_n="$(grep -c 'name: Verify Claude Code pin (before link' "$burn" || true)"
  [ "$burn_verify_step_n" -eq 5 ] || {
    echo "selftest: expected 5 burn per-link verify steps, found ${burn_verify_step_n}" >&2
    exit 1
  }
  claude_ver_file="${repo_root}/.github/claude-code-version"
  [ -f "$claude_ver_file" ] || {
    echo "selftest: .github/claude-code-version is missing" >&2
    exit 1
  }
  claude_ver="$(awk '/^version:/{print $2; exit}' "$claude_ver_file")"
  claude_sha="$(awk '/^linux-x64-sha256:/{print $2; exit}' "$claude_ver_file")"
  claude_fpr="$(awk '/^gpg-fingerprint:/{print $2; exit}' "$claude_ver_file")"
  [[ "$claude_ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    echo "selftest: .github/claude-code-version has no exact version: pin" >&2
    exit 1
  }
  [ "$claude_sha" = "bc1aad9982c7b59c7d889ff92595d61cf46e0a6eae074cb551d932a989bcd222" ] || {
    echo "selftest: committed linux-x64-sha256 is not the Cipher-pinned 2.1.301 digest" >&2
    exit 1
  }
  [ "$claude_fpr" = "31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE" ] || {
    echo "selftest: committed gpg-fingerprint is not the Anthropic Claude Code signing key" >&2
    exit 1
  }
  srt_pin="${repo_root}/.github/sandbox-runtime-version"
  [ -f "$srt_pin" ] || {
    echo "selftest: .github/sandbox-runtime-version is missing" >&2
    exit 1
  }
  srt_ver="$(awk '/^version:/{print $2; exit}' "$srt_pin")"
  srt_integrity="$(awk '/^dist-integrity:/{print $2; exit}' "$srt_pin")"
  [ "$srt_ver" = "0.0.80" ] || {
    echo "selftest: sandbox-runtime version pin is not 0.0.80 (got ${srt_ver:-empty})" >&2
    exit 1
  }
  [ "$srt_integrity" = "sha512-WG4P8faU/JDH90I8NLUBPmg7e72zhanlW3AVCD0OF06JCtId9IDFewFgv4YRvHLcnn//h1r6a1AMosBsMLpxnA==" ] || {
    echo "selftest: sandbox-runtime dist-integrity is not the committed 0.0.80 pin" >&2
    exit 1
  }
  for script in install-claude-code-pin.sh install-sandbox-runtime-pin.sh \
    verify-claude-code-pin.sh verify-sandbox-runtime-pin.sh \
    setup-bwrap-apparmor.sh smoke-claude-scrub-sandbox.sh; do
    [ -x "${repo_root}/scripts/${script}" ] || {
      echo "selftest: scripts/${script} missing or not executable" >&2
      exit 1
    }
  done
  grep -q 'verify-sandbox-runtime-pin.sh' "$burn" || {
    echo "selftest: burn missing verify-sandbox-runtime-pin.sh" >&2
    exit 1
  }
  grep -q 'verify-sandbox-runtime-pin.sh' "$workflow" || {
    echo "selftest: design-run missing verify-sandbox-runtime-pin.sh" >&2
    exit 1
  }
  # Preflight/scrub/verify failure must score walk_outcome as failure (not
  # not-run), or settle leaves the SHIP-LOCK starving the claimed issue.
  # verify_claude_N is required: a pin-verify fail skips every ship and would
  # otherwise take the all-skipped not-run branch (Bugbot on #876).
  for wf in "$burn" "$workflow"; do
    grep -q "steps.preflight.outcome == 'failure'" "$wf" || {
      echo "selftest: $(basename "$wf") walk_outcome does not treat preflight failure as failure" >&2
      exit 1
    }
    grep -q "steps.scrub_smoke.outcome == 'failure'" "$wf" || {
      echo "selftest: $(basename "$wf") walk_outcome does not treat scrub_smoke failure as failure" >&2
      exit 1
    }
    for n in 1 2 3 4 5; do
      grep -q "steps.verify_claude_${n}.outcome == 'failure'" "$wf" || {
        echo "selftest: $(basename "$wf") walk_outcome does not treat verify_claude_${n} failure as failure" >&2
        exit 1
      }
    done
    # The failure clause must appear on every walk_outcome twin (job output +
    # metadata + red-gate env), not only once in a comment.
    verify_fail_n="$(grep -c "steps.verify_claude_1.outcome == 'failure'" "$wf" || true)"
    [ "$verify_fail_n" -ge 3 ] || {
      echo "selftest: $(basename "$wf") expected >=3 walk_outcome twins scoring verify_claude_1 failure, found ${verify_fail_n}" >&2
      exit 1
    }
  done
  grep -q '\.local/bin/srt' "${repo_root}/scripts/install-sandbox-runtime-pin.sh" || {
    echo "selftest: install-sandbox-runtime-pin.sh does not strip ~/.local/bin/srt" >&2
    exit 1
  }
  grep -q '\.local/bin' "${repo_root}/scripts/verify-sandbox-runtime-pin.sh" || {
    echo "selftest: verify-sandbox-runtime-pin.sh does not strip ~/.local/bin shadows" >&2
    exit 1
  }
  for tool in srt bwrap socat rg; do
    grep -q "$tool" "${repo_root}/scripts/verify-sandbox-runtime-pin.sh" || {
      echo "selftest: verify-sandbox-runtime-pin.sh does not pin ${tool}" >&2
      exit 1
    }
  done
  grep -q 'assert_resolved bwrap /usr/bin/bwrap' \
    "${repo_root}/scripts/verify-sandbox-runtime-pin.sh" || {
    echo "selftest: verify-sandbox-runtime-pin.sh does not require /usr/bin/bwrap" >&2
    exit 1
  }
  # Cipher MED-2: verify scripts must check the real inherited PATH (never
  # re-export PATH=/usr/bin:/bin before that check — GITHUB_PATH prepends
  # ahead of step env PATH and a re-set would hide a planted fake bwrap).
  for vscript in verify-sandbox-runtime-pin.sh verify-claude-code-pin.sh; do
    vpath="${repo_root}/scripts/${vscript}"
    grep -Fq 'inherited PATH must be exactly /usr/bin:/bin' "$vpath" || {
      echo "selftest: ${vscript} does not refuse a polluted inherited PATH" >&2
      exit 1
    }
    # The PATH check must appear before any `export PATH=` (if any).
    check_line="$(grep -n 'inherited PATH must be exactly /usr/bin:/bin' "$vpath" | head -1 | cut -d: -f1)"
    export_line="$(grep -n 'export PATH=' "$vpath" | head -1 | cut -d: -f1 || true)"
    if [ -n "${export_line:-}" ] && [ -n "${check_line:-}" ] \
      && [ "$export_line" -le "$check_line" ]; then
      echo "selftest: ${vscript} re-exports PATH before the inherited-PATH check (Cipher MED-2)" >&2
      exit 1
    fi
  done
  # Absolute bwrap/socat/rg pins: Claude managed-settings (preflight) + srt smoke.
  grep -Fq '"bwrapPath": "/usr/bin/bwrap"' \
    "${repo_root}/scripts/install-claude-code-pin.sh" || {
    echo "selftest: install-claude-code-pin.sh does not write managed bwrapPath" >&2
    exit 1
  }
  grep -Fq '"socatPath": "/usr/bin/socat"' \
    "${repo_root}/scripts/install-claude-code-pin.sh" || {
    echo "selftest: install-claude-code-pin.sh does not write managed socatPath" >&2
    exit 1
  }
  grep -Fq '"command": "/usr/bin/rg"' \
    "${repo_root}/scripts/install-claude-code-pin.sh" || {
    echo "selftest: install-claude-code-pin.sh does not write managed ripgrep path" >&2
    exit 1
  }
  grep -Fq 'managed_dir="/etc/claude-code"' \
    "${repo_root}/scripts/install-claude-code-pin.sh" || {
    echo "selftest: install-claude-code-pin.sh does not target /etc/claude-code" >&2
    exit 1
  }
  grep -Fq 'managed-settings.json' \
    "${repo_root}/scripts/install-claude-code-pin.sh" || {
    echo "selftest: install-claude-code-pin.sh does not write managed-settings.json" >&2
    exit 1
  }
  grep -Fq 'managed="/etc/claude-code/managed-settings.json"' \
    "${repo_root}/scripts/verify-claude-code-pin.sh" || {
    echo "selftest: verify-claude-code-pin.sh does not require managed-settings path pins" >&2
    exit 1
  }
  grep -Fq '"bwrapPath": "/usr/bin/bwrap"' \
    "${repo_root}/scripts/smoke-claude-scrub-sandbox.sh" || {
    echo "selftest: smoke-claude-scrub-sandbox.sh srt settings lack absolute bwrapPath" >&2
    exit 1
  }
  grep -Fq '"socatPath": "/usr/bin/socat"' \
    "${repo_root}/scripts/smoke-claude-scrub-sandbox.sh" || {
    echo "selftest: smoke-claude-scrub-sandbox.sh srt settings lack absolute socatPath" >&2
    exit 1
  }
  grep -Fq '"command": "/usr/bin/rg"' \
    "${repo_root}/scripts/smoke-claude-scrub-sandbox.sh" || {
    echo "selftest: smoke-claude-scrub-sandbox.sh lacks absolute rg path" >&2
    exit 1
  }
  # Cipher MED-1: verify_claude_N restores verify-*.sh from START_SHA into
  # RUNNER_TEMP and invokes via /usr/bin/bash (not the agent-writable tree
  # shebang).
  for wf in "$burn" "$workflow"; do
    restore_n="$(grep -c 'restore_verify verify-claude-code-pin.sh' "$wf" || true)"
    [ "$restore_n" = "5" ] || {
      echo "selftest: $(basename "$wf") expected 5 START_SHA restores of verify-claude-code-pin.sh, found ${restore_n}" >&2
      exit 1
    }
    restore_srt_n="$(grep -c 'restore_verify verify-sandbox-runtime-pin.sh' "$wf" || true)"
    [ "$restore_srt_n" = "5" ] || {
      echo "selftest: $(basename "$wf") expected 5 START_SHA restores of verify-sandbox-runtime-pin.sh, found ${restore_srt_n}" >&2
      exit 1
    }
    bash_inv_n="$(grep -c '/usr/bin/bash "${RUNNER_TEMP}/verify-claude-code-pin.sh"' "$wf" || true)"
    [ "$bash_inv_n" = "5" ] || {
      echo "selftest: $(basename "$wf") expected 5 /usr/bin/bash invokes of restored verify-claude-code-pin.sh, found ${bash_inv_n}" >&2
      exit 1
    }
    grep -F 'show "$START_SHA:scripts/${name}"' "$wf" >/dev/null || {
      echo "selftest: $(basename "$wf") verify restore does not git-show from START_SHA" >&2
      exit 1
    }
    # Must not still invoke the workspace verify scripts directly in verify_claude_N.
    if grep -E '^\s+"\$\{GITHUB_WORKSPACE\}/scripts/verify-(claude-code|sandbox-runtime)-pin\.sh"' "$wf" >/dev/null; then
      echo "selftest: $(basename "$wf") still invokes workspace verify-*.sh directly (Cipher MED-1)" >&2
      exit 1
    fi
    start_sha_env_n="$(grep -c 'START_SHA: \${{ steps.start_ref.outputs.sha }}' "$wf" || true)"
    # start_ref START_SHA appears on verify (5) plus other trusted steps; require
    # at least the five verify steps carry it (grep counts all occurrences).
    [ "$start_sha_env_n" -ge 5 ] || {
      echo "selftest: $(basename "$wf") expected >=5 START_SHA env pins from start_ref, found ${start_sha_env_n}" >&2
      exit 1
    }
  done
  for wf in "$burn" "$workflow"; do
    grep -q 'PATH: /opt/sandbox-runtime/bin:/usr/bin:/bin:/home/runner/.local/bin' "$wf" || {
      echo "selftest: $(basename "$wf") agent steps lack /opt+/usr/bin-before-~/.local/bin PATH" >&2
      exit 1
    }
    # Every SCRUB agent PATH block must blank NODE_OPTIONS/LD_PRELOAD/…
    # at process start (GITHUB_ENV plant from a prior continue-on-error link).
    python3 - "$wf" <<'PY' || exit 1
import sys
path = sys.argv[1]
lines = open(path).read().splitlines()
needle = "PATH: /opt/sandbox-runtime/bin:/usr/bin:/bin:/home/runner/.local/bin"
need = ("LD_PRELOAD: \"\"", "LD_LIBRARY_PATH: \"\"", "LD_AUDIT: \"\"",
        "BASH_ENV: \"\"", "ENV: \"\"", "NODE_OPTIONS: \"\"", "NODE_PATH: \"\"",
        "HTTP_PROXY: \"\"", "HTTPS_PROXY: \"\"", "ALL_PROXY: \"\"",
        "NODE_TLS_REJECT_UNAUTHORIZED: \"\"", "NODE_EXTRA_CA_CERTS: \"\"",
        "SSLKEYLOGFILE: \"\"", "HOME: /home/runner",
        "CLAUDE_CONFIG_DIR: /home/runner/.claude",
        "XDG_CONFIG_HOME: /home/runner/.config")
hits = 0
for i, line in enumerate(lines):
    if needle not in line:
        continue
    # 36 lines covers PATH + comments + LD/NODE/proxy/TLS pins (+ Anthropic
    # BASE_URL pin on the tail links). Keep this ahead of the pin list length.
    window = "\n".join(lines[i:i+44])
    missing = [n for n in need if n not in window]
    if missing:
        print(f"selftest: {path} SCRUB PATH at line {i+1} missing process-start pins: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    hits += 1
if hits != 5:
    print(f"selftest: {path} expected 5 SCRUB agent PATH blocks with hijack pins, found {hits}", file=sys.stderr)
    sys.exit(1)
# Anthropic tail (links 4–5): pin native BASE_URL + blank AUTH_TOKEN so a
# prior GLM GITHUB_ENV plant cannot redirect the Anthropic API key.
native = sum(1 for line in lines
             if line.strip() == 'ANTHROPIC_BASE_URL: https://api.anthropic.com')
blank_auth = sum(1 for line in lines if line.strip() == 'ANTHROPIC_AUTH_TOKEN: ""')
if native != 2:
    print(f"selftest: {path} expected 2 Anthropic-tail native ANTHROPIC_BASE_URL pins, found {native}", file=sys.stderr)
    sys.exit(1)
if blank_auth != 2:
    print(f"selftest: {path} expected 2 Anthropic-tail ANTHROPIC_AUTH_TOKEN blanks, found {blank_auth}", file=sys.stderr)
    sys.exit(1)
PY
  done
  # Wrapper is built with absolute /opt node copy + cli.js (never env node,
  # never /usr/local/bin/node — that path is world-writable on GHA).
  grep -Fq 'exec ${pinned_node} ${cli_js}' \
    "${repo_root}/scripts/install-sandbox-runtime-pin.sh" || {
    echo "selftest: install-sandbox-runtime-pin.sh does not emit absolute-node wrapper" >&2
    exit 1
  }
  grep -Fq 'pinned_node="${INSTALL_ROOT}/bin/node"' \
    "${repo_root}/scripts/install-sandbox-runtime-pin.sh" || {
    echo "selftest: install-sandbox-runtime-pin.sh does not copy node under /opt" >&2
    exit 1
  }
  grep -Fq 'pinned_node="/opt/sandbox-runtime/bin/node"' \
    "${repo_root}/scripts/verify-sandbox-runtime-pin.sh" || {
    echo "selftest: verify-sandbox-runtime-pin.sh does not require /opt node pin" >&2
    exit 1
  }
  grep -Eiq 'env[[:space:]]+node' "${repo_root}/scripts/verify-sandbox-runtime-pin.sh" || {
    echo "selftest: verify-sandbox-runtime-pin.sh does not refuse env node" >&2
    exit 1
  }
  grep -q 'install-sandbox-runtime-pin.sh' "$burn" || {
    echo "selftest: burn missing install-sandbox-runtime-pin.sh" >&2
    exit 1
  }
  grep -q 'install-sandbox-runtime-pin.sh' "$workflow" || {
    echo "selftest: design-run missing install-sandbox-runtime-pin.sh" >&2
    exit 1
  }
  # Actual install lines only — comments may mention the forbidden form.
  if grep -E '^[[:space:]]*(sudo[[:space:]]+)?npm install -g.*@anthropic-ai/sandbox-runtime' \
       "$burn" "$workflow" >/dev/null; then
    echo "selftest: ship workflows still bare-npm-install sandbox-runtime (Cipher #876)" >&2
    exit 1
  fi
  canary="${repo_root}/.github/workflows/claude-sandbox-canary.yml"
  [ -f "$canary" ] || {
    echo "selftest: claude-sandbox-canary.yml is missing" >&2
    exit 1
  }
  grep -q 'permissions:' "$canary" && grep -A2 '^permissions:' "$canary" | grep -q 'contents: read' || {
    echo "selftest: canary must set permissions contents: read" >&2
    exit 1
  }
  if grep -E '\$\{\{[[:space:]]*secrets\.|ANTHROPIC_API_KEY: \$\{|ZAI_KEY: \$\{|GH_TOKEN: \$\{|REGEN_TOKEN: \$\{' \
       "$canary" >/dev/null; then
    echo "selftest: canary must not reference provider/PAT secrets" >&2
    exit 1
  fi
  grep -q 'install-sandbox-runtime-pin.sh' "$canary" || {
    echo "selftest: canary missing install-sandbox-runtime-pin.sh" >&2
    exit 1
  }
  grep -q 'smoke-claude-scrub-sandbox.sh' "$canary" || {
    echo "selftest: canary missing smoke-claude-scrub-sandbox.sh" >&2
    exit 1
  }
  grep -q 'setup-bwrap-apparmor.sh' "$canary" || {
    echo "selftest: canary missing setup-bwrap-apparmor.sh" >&2
    exit 1
  }
  grep -q 'ripgrep' "$canary" || {
    echo "selftest: canary preflight does not apt-get ripgrep (srt dependency)" >&2
    exit 1
  }
  if grep -Eiq 'sysctl -w kernel\.apparmor_restrict_unprivileged_userns=0|echo 0 \| sudo tee /proc/sys/kernel/apparmor_restrict_unprivileged_userns' "$canary"; then
    echo "selftest: canary must not clear apparmor_restrict_unprivileged_userns" >&2
    exit 1
  fi
  grep -q 'dist-integrity' "${repo_root}/scripts/install-sandbox-runtime-pin.sh" || {
    echo "selftest: install-sandbox-runtime-pin.sh does not check dist-integrity" >&2
    exit 1
  }
  grep -q -- 'npm ci' "${repo_root}/scripts/install-sandbox-runtime-pin.sh" || {
    echo "selftest: install-sandbox-runtime-pin.sh does not use npm ci" >&2
    exit 1
  }
  grep -q -- '--ignore-scripts' "${repo_root}/scripts/install-sandbox-runtime-pin.sh" || {
    echo "selftest: install-sandbox-runtime-pin.sh does not use --ignore-scripts" >&2
    exit 1
  }
  srt_pkg="${repo_root}/.github/sandbox-runtime/package.json"
  srt_lock="${repo_root}/.github/sandbox-runtime/package-lock.json"
  [ -f "$srt_pkg" ] || {
    echo "selftest: .github/sandbox-runtime/package.json is missing" >&2
    exit 1
  }
  [ -f "$srt_lock" ] || {
    echo "selftest: .github/sandbox-runtime/package-lock.json is missing" >&2
    exit 1
  }
  if ! python3 - "$srt_pkg" "$srt_lock" "$srt_ver" "$srt_integrity" <<'PY'
import json, sys
pkg_path, lock_path, want_ver, want_integrity = sys.argv[1:5]
pkg = json.load(open(pkg_path))
lock = json.load(open(lock_path))
dep = (pkg.get("dependencies") or {}).get("@anthropic-ai/sandbox-runtime", "")
if dep != want_ver:
    print(f"package.json dep {dep!r} != pin {want_ver!r}", file=sys.stderr)
    sys.exit(1)
if lock.get("lockfileVersion") != 3:
    print(f"lockfileVersion {lock.get('lockfileVersion')!r} != 3", file=sys.stderr)
    sys.exit(1)
entry = (lock.get("packages") or {}).get("node_modules/@anthropic-ai/sandbox-runtime") or {}
if entry.get("version") != want_ver or entry.get("integrity") != want_integrity:
    print("lockfile entry mismatches pin", file=sys.stderr)
    sys.exit(1)
missing = [
    name for name, meta in (lock.get("packages") or {}).items()
    if name.startswith("node_modules/") and not (meta or {}).get("integrity")
]
if missing:
    print("lock packages missing integrity:", missing, file=sys.stderr)
    sys.exit(1)
PY
  then
    echo "selftest: sandbox-runtime package/lock disagree with pin" >&2
    exit 1
  fi
  for wf in "$burn" "$workflow" "$canary"; do
    # The ship/canary jobs that call setup-bwrap-apparmor must pin 24.04.
    if ! awk '
      BEGIN { runs=0; hit=0; ok=0 }
      /runs-on:[[:space:]]*ubuntu-24\.04/ { runs=1 }
      /runs-on:[[:space:]]*ubuntu-latest/ { runs=0 }
      /setup-bwrap-apparmor\.sh/ { hit=1; if (runs==1) ok=1 }
      END { exit (hit && ok) ? 0 : 1 }
    ' "$wf"; then
      echo "selftest: $(basename "$wf") must pin runs-on: ubuntu-24.04 for AppArmor bwrap (got ubuntu-latest or missing)" >&2
      exit 1
    fi
  done
  grep -q 'sudo -n true' "$burn" || {
    echo "selftest: the burn sudo disable step does not prove sudo is gone" >&2
    exit 1
  }
  grep -q -- '--slurp' "$burn" || {
    echo "selftest: the burn label strip does not merge paginated event pages" >&2
    exit 1
  }
  grep -q 'AGENT_WINDOW_END' "$burn" || {
    echo "selftest: the burn label strip does not bound the agent window" >&2
    exit 1
  }
  grep -q 'agent window end missing — using settle start' "$burn" || {
    echo "selftest: the burn label strip does not fall back when agent_window_end is empty" >&2
    exit 1
  }
  burn_perms="$(awk '/^  burn:/{p=1} p && /^  [A-Za-z]/ && !/^  burn:/{exit} p' "$burn")"
  case "$burn_perms" in
    *"pull-requests: read"*) ;;
    *) echo "selftest: the burn job does not set pull-requests: read" >&2; exit 1 ;;
  esac
  case "$burn_perms" in
    *"pull-requests: write"*)
      echo "selftest: the burn job still grants pull-requests: write" >&2
      exit 1 ;;
  esac
  if awk '
    /^permissions:/ { p = 1; next }
    p && /^[^ ]/ { exit }
    p && /^  actions:/ { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$burn"; then
    echo "selftest: burn workflow permissions still grant actions" >&2
    exit 1
  fi
  burn_settings="${repo_root}/.claude/backlog-burn-settings.json"
  [ -f "$burn_settings" ] || { echo "selftest: backlog-burn settings are missing" >&2; exit 1; }
  for rule in 'Bash(git push:*)' 'Bash(git push*)' 'Bash(gh pr create:*)' 'Bash(gh pr create*)' \
    'Bash(gh issue create*autonomy-ok*)' 'Bash(gh issue create*design-brief*)' \
    'Bash(gh pr create*autonomy-ok*)' 'Bash(gh pr create*design-brief*)' \
    'Bash(gh issue edit*autonomy-ok*)' 'Bash(gh issue edit*design-brief*)' \
    'Bash(gh api*autonomy-ok*)' 'Bash(gh api*design-brief*)' \
    'Bash(curl*autonomy-ok*)' 'Bash(curl*design-brief*)'; do
    grep -qF "\"${rule}\"" "$burn_settings" || {
      echo "selftest: backlog-burn settings missing deny ${rule}" >&2
      exit 1
    }
  done
  grep -q 'name: Strip bot-added opt-in labels' "$burn" || {
    echo "selftest: burn bot-added opt-in labels are not stripped" >&2
    exit 1
  }
  grep -q 'github-actions\[bot\]' "$burn" || {
    echo "selftest: the burn label strip does not key on the bot actor" >&2
    exit 1
  }
  grep -q 'needs-decision is never removed' "$burn" || {
    echo "selftest: the burn label strip does not leave needs-decision alone" >&2
    exit 1
  }
  grep -q '  settle:' "$burn" || {
    echo "selftest: burn label strip and lock cleanup are not in a fresh settle job" >&2
    exit 1
  }
  # Settle START_SHA case must accept a real 40-char commit (Bugbot on #863:
  # 41 hex classes rejected every SHA and lock cleanup never ran).
  settle_job="$(awk '/^  settle:/{p=1;print;next} p && /^  [A-Za-z]/{exit} p' "$burn")"
  # SIGPIPE-safe under pipefail (no `grep | head -1`).
  settle_sha_arm="$(grep -E '\[0-9a-f\]\[0-9a-f\]' <<<"$settle_job" || true)"
  settle_sha_arm="${settle_sha_arm%%$'\n'*}"
  [ -n "$settle_sha_arm" ] || {
    echo "selftest: settle job has no START_SHA hex case arm" >&2
    exit 1
  }
  settle_sha_n="$(printf '%s' "$settle_sha_arm" | grep -oE '\[0-9a-f\]' | wc -l | tr -d ' ')"
  [ "$settle_sha_n" = "40" ] || {
    echo "selftest: settle START_SHA case has ${settle_sha_n} hex classes, want 40" >&2
    exit 1
  }
  burn_outcome_n="$(grep -c 'AGENT_OUTCOME: ${{ needs.burn.outputs.walk_outcome }}' "$burn" || true)"
  [ "$burn_outcome_n" -eq 2 ] || {
    echo "selftest: expected 2 identical burn AGENT_OUTCOME reads, found ${burn_outcome_n}" >&2
    exit 1
  }
  burn_pending_n="$(grep -c "needs.burn.outputs.bundle_pending != 'true'" "$burn" || true)"
  [ "$burn_pending_n" -eq 3 ] || {
    echo "selftest: expected the settle lock cleanup, red gate, and triage gated on bundle_pending, found ${burn_pending_n}" >&2
    exit 1
  }
  # #923: burn settle restore — same mktemp→mv + pinned git show as design-run.
  grep -E 'git --no-replace-objects -c core\.hooksPath=/dev/null( -c core\.(fsmonitor=false|sshCommand=))* show "\$START_SHA:scripts/routine-lock-cleanup\.sh"' "$burn" >/dev/null || {
    echo "selftest: burn lock-cleanup restore is missing --no-replace-objects and hooksPath" >&2
    exit 1
  }
  grep 'mktemp "${RUNNER_TEMP}/routine-lock-cleanup-blob.XXXXXX"' "$burn" >/dev/null || {
    echo "selftest: burn lock-cleanup restore is missing mktemp→mv (#923)" >&2
    exit 1
  }
  grep 'Prove lock-cleanup restore leaves a regular file' "$burn" >/dev/null || {
    echo "selftest: burn is missing the early lock-cleanup restore preflight (#923)" >&2
    exit 1
  }
  burn_routine_n="$(grep -v '^[[:space:]]*#' "$burn" | grep -c -- '--routine backlog-burn' || true)"
  [ "$burn_routine_n" -eq 2 ] || {
    echo "selftest: expected the burn bundle step and settle lock cleanup on --routine backlog-burn, found ${burn_routine_n}" >&2
    exit 1
  }
  burn_reap_n="$(grep -c 'reap_should_kill()' "$burn" || true)"
  [ "$burn_reap_n" -eq 1 ] || {
    echo "selftest: expected the reaper predicate in the burn bundle step, found ${burn_reap_n}" >&2
    exit 1
  }
  burn_reap_a="$(awk '
    /reap_should_kill\(\) \{/ { c++; if (c==1) p=1 }
    p { print }
    p && /^          \}$/ { exit }
  ' "$burn")"
  (
    eval "$burn_reap_a"
    export GITHUB_WORKSPACE=/work RUNNER_TEMP=/tmp/rt
    if reap_should_kill 55 1 sleep / "backlog-burn.bundle" 3 "" 99 1; then :; else
      echo "selftest: burn reap_should_kill kept a process mentioning the burn bundle" >&2
      exit 1
    fi
    if reap_should_kill 55 1 sleep / "design-run.bundle" 3 "" 99 1; then
      echo "selftest: burn reap_should_kill killed a process outside the burn" >&2
      exit 1
    fi
  )
  grep -q '  triage:' "$burn" || {
    echo "selftest: burn provider-triage is not a separate job" >&2
    exit 1
  }
  grep -q 'ref: \${{ needs.burn.outputs.start_sha }}' "$burn" || {
    echo "selftest: the burn triage job does not check out START_SHA" >&2
    exit 1
  }
  grep -q 'steps.verify_triage.outcome == '"'"'success'"'"'' "$burn" || {
    echo "selftest: burn provider-triage does not wait for the fresh checkout" >&2
    exit 1
  }
  burn_triage_job="$(awk '
    /^  triage:/ { printing = 1 }
    printing && /^  [A-Za-z]/ && !/^  triage:/ { exit }
    printing { print }
  ' "$burn")"
  printf '%s\n' "$burn_triage_job" | grep 'uses: \./\.github/actions/provider-triage' >/dev/null || {
    echo "selftest: the burn triage job does not run provider-triage" >&2
    exit 1
  }
  if printf '%s\n' "$burn_perms" | grep 'provider-triage' >/dev/null; then
    echo "selftest: provider-triage still runs inside the burn agent job" >&2
    exit 1
  fi
  grep -q 'PYTHONSAFEPATH: "1"' "$burn" || {
    echo "selftest: burn provider-triage does not set PYTHONSAFEPATH" >&2
    exit 1
  }
  grep -q 'vars.AI_ANDON_CORD' "$burn" || {
    echo "selftest: the burn jobs lost the andon cord leg" >&2
    exit 1
  }

  burn_deliver="${repo_root}/.github/workflows/backlog-burn-deliver.yml"
  [ -f "$burn_deliver" ] || { echo "selftest: backlog-burn-deliver.yml is missing" >&2; exit 1; }
  grep -q 'workflow_run:' "$burn_deliver" || {
    echo "selftest: burn delivery is not a workflow_run workflow" >&2
    exit 1
  }
  grep -q 'workflows: \["Backlog burn (scheduled /ship-issue)"\]' "$burn_deliver" || {
    echo "selftest: burn delivery workflow_run does not name the burn workflow" >&2
    exit 1
  }
  grep -q 'actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131' "$burn_deliver" || {
    echo "selftest: the burn deliver workflow does not download the bundle from the pinned v7 action" >&2
    exit 1
  }
  if grep -q 'actions/download-artifact@v7' "$burn_deliver" || grep 'actions/checkout@v7' "$burn_deliver" >/dev/null; then
    echo "selftest: backlog-burn-deliver.yml still uses a floating v7 action tag" >&2
    exit 1
  fi
  grep -q '\$GITHUB_WORKSPACE/scripts/design-run-deliver.sh' "$burn_deliver" || {
    echo "selftest: the burn deliver workflow does not run the checkout script" >&2
    exit 1
  }
  if grep -q 'anthropics/claude-code-action' "$burn_deliver"; then
    echo "selftest: the burn deliver workflow runs agent code" >&2
    exit 1
  fi
  grep -q '"Pick one issue and run /ship-issue"' "$burn_deliver" || {
    echo "selftest: burn delivery does not filter the triggering run's job" >&2
    exit 1
  }
  grep -q 'name: backlog-burn-lock' "$burn_deliver" || {
    echo "selftest: burn delivery does not download the SHIP-LOCK context" >&2
    exit 1
  }
  grep -q 'name: backlog-burn-meta' "$burn_deliver" || {
    echo "selftest: burn delivery does not download the metadata" >&2
    exit 1
  }
  grep -q 'name: backlog-burn-bundle' "$burn_deliver" || {
    echo "selftest: burn delivery does not download the bundle" >&2
    exit 1
  }
  grep -q -- '--bundle "${RUNNER_TEMP}/backlog-burn-bundle/backlog-burn.bundle"' "$burn_deliver" || {
    echo "selftest: burn delivery does not verify the burn bundle path" >&2
    exit 1
  }
  burn_pat_n="$(grep -c 'GH_TOKEN: \${{ secrets.GH_TOKEN }}' "$burn_deliver" || true)"
  [ "$burn_pat_n" -eq 1 ] || {
    echo "selftest: the burn push PAT must appear on exactly one deliver step, found ${burn_pat_n}" >&2
    exit 1
  }
  if grep -q 'github_token: \${{ secrets.GH_TOKEN' "$burn_deliver"; then
    echo "selftest: a burn deliver step wires the PAT as an agent token" >&2
    exit 1
  fi
  burn_deliver_routine_n="$(grep -v '^[[:space:]]*#' "$burn_deliver" | grep -c -- '--routine backlog-burn' || true)"
  [ "$burn_deliver_routine_n" -eq 2 ] || {
    echo "selftest: expected the burn deliver push and lock cleanup on --routine backlog-burn, found ${burn_deliver_routine_n}" >&2
    exit 1
  }
  grep -q 'head_branch == github.event.repository.default_branch' "$burn_deliver" || {
    echo "selftest: burn deliver job does not require the triggering head branch" >&2
    exit 1
  }
  grep -q 'metadata issue' "$burn_deliver" || {
    echo "selftest: burn deliver does not require the metadata issue to match the pre-agent lock" >&2
    exit 1
  }
  grep -q 'Upload the delivery metadata' "$burn_deliver" || {
    echo "selftest: burn deliver does not require the trusted metadata upload step" >&2
    exit 1
  }
  burn_pin_gates="$(grep -c "steps.pin.outcome == 'success'" "$burn_deliver" || true)"
  [ "$burn_pin_gates" -eq 3 ] || {
    echo "selftest: burn download, deliver, and the red step must be gated on the pin, and lock cleanup must not be (found ${burn_pin_gates})" >&2
    exit 1
  }
  if awk '
    /name: Release the SHIP-LOCK after delivery/ { found = 1; n = 0 }
    found { n++; if ($0 ~ /steps.pin.outcome/) bad = 1 }
    found && n > 12 { exit }
    END { exit bad ? 1 : 0 }
  ' "$burn_deliver"; then
    :
  else
    echo "selftest: burn lock cleanup is still gated on the delivery pin" >&2
    exit 1
  fi
  if grep -q 'git fetch' "$burn_deliver"; then
    echo "selftest: burn delivery fetches a commit by id" >&2
    exit 1
  fi
  if grep -q 'ref: ${{ steps.parsed.outputs.start_sha }}' "$burn_deliver"; then
    echo "selftest: burn checkout still uses the artifact start_sha" >&2
    exit 1
  fi
  grep -q 'show "$WORKFLOW_HEAD_SHA:scripts/routine-lock-cleanup.sh"' "$burn_deliver" || {
    echo "selftest: burn lock cleanup does not read the script from the triggering head" >&2
    exit 1
  }
  grep -q '^  actions: read$' "$burn_deliver" || {
    echo "selftest: burn deliver workflow does not grant actions: read" >&2
    exit 1
  }
  if awk '
    /^permissions:/ { p = 1; next }
    p && /^[^ ]/ { exit }
    p && /^  actions: write/ { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$burn_deliver"; then
    echo "selftest: burn deliver workflow grants actions: write" >&2
    exit 1
  fi
  grep -q "always() && (steps.lock_parsed.outcome == 'success' || steps.parsed.outcome == 'success')" "$burn_deliver" || {
    echo "selftest: burn deliver checkout is skipped when an earlier step failed" >&2
    exit 1
  }
  ship_skill="${repo_root}/.claude/skills/ship-issue/SKILL.md"
  grep -q 'Do not `git push`' "$ship_skill" || {
    echo "selftest: ship-issue SKILL.md does not forbid git push in unattended mode" >&2
    exit 1
  }
  grep -q 'do not `gh pr create`' "$ship_skill" || {
    echo "selftest: ship-issue SKILL.md does not forbid gh pr create in unattended mode" >&2
    exit 1
  }
  grep -q 'does not exist yet' "$ship_skill" || {
    echo "selftest: ship-issue SKILL.md does not say the deliver-job PR does not exist yet" >&2
    exit 1
  }

  # --routine behavior. A scripts/ change is forbidden for BOTH routines
  # (issue #869 — backlog-burn shares design-run's protected prefixes); an
  # unknown routine is a usage error, never a silent default. A benign
  # docs/ change still delivers under backlog-burn.
  local rsrc rfile rstart
  rsrc="${tmp}/rsrc"
  rfile="${tmp}/backlog-burn.bundle"
  mkdir -p "$rsrc/scripts" "$rsrc/docs"
  git_cmd -C "$rsrc" init -b main >/dev/null
  printf 'seed\n' > "$rsrc/docs/seed.md"
  git_cmd -C "$rsrc" -c user.email=t@example.com -c user.name=t add -- docs/seed.md
  git_cmd -C "$rsrc" -c user.email=t@example.com -c user.name=t commit -m start >/dev/null
  rstart="$(git_cmd -C "$rsrc" rev-parse HEAD)"
  git_cmd -C "$rsrc" checkout -b claude/issue-869-burn-paths >/dev/null 2>&1
  printf 'fix\n' > "$rsrc/scripts/fix.sh"
  git_cmd -C "$rsrc" -c user.email=t@example.com -c user.name=t add -- scripts/fix.sh
  git_cmd -C "$rsrc" -c user.email=t@example.com -c user.name=t commit -m fix >/dev/null
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$rsrc" \
    "$SELF" --repo acme/print-bench --issue 869 --base "$rstart" \
    --base-branch main --run-url https://example.test/run/1 \
    --write-bundle "$rfile" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 1 ] || { echo "selftest: design-run accepted a scripts/ commit (exit ${rc})" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep 'touches scripts/fix.sh' >/dev/null || {
    echo "selftest: design-run did not report the scripts/ refusal" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  [ ! -e "$rfile" ] || { echo "selftest: design-run wrote a bundle for a forbidden range" >&2; exit 1; }
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$rsrc" \
    "$SELF" --repo acme/print-bench --issue 869 --base "$rstart" \
    --base-branch main --run-url https://example.test/run/1 \
    --routine backlog-burn --write-bundle "$rfile" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 1 ] || {
    echo "selftest: backlog-burn accepted a scripts/ commit (exit ${rc})" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'touches scripts/fix.sh' >/dev/null || {
    echo "selftest: backlog-burn did not report the scripts/ refusal" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  [ ! -e "$rfile" ] || { echo "selftest: backlog-burn wrote a bundle for a forbidden scripts/ range" >&2; exit 1; }
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$rsrc" \
    "$SELF" --repo acme/print-bench --issue 869 --base "$rstart" \
    --base-branch main --run-url https://example.test/run/1 \
    --routine bogus --write-bundle "$rfile" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 2 ] || { echo "selftest: an unknown routine exited ${rc}, expected 2" >&2; exit 1; }
  printf '%s\n' "$stderr" | grep 'unknown routine: bogus' >/dev/null || {
    echo "selftest: an unknown routine did not report the refusal" >&2
    exit 1
  }

  # backlog-burn refuses .github/**, **/.claude/**, scripts/** and tools/**
  # together (closes #869 / #879): for each root prefix, add / modify /
  # delete / rename into / rename out of / symlink into — while a benign
  # docs/ change still delivers. Nested **/.claude/** and pathspec-magic
  # symlink names are covered below. The normalizer (case / ../ /
  # backslash / absolute symlink target / gitlink) is shared with
  # design-run.
  local gsrc gfile gstart prefix
  gsrc="${tmp}/gsrc"
  gfile="${tmp}/protected-forbid.bundle"
  greject() {  # $1 label, $2 expected stderr needle
    local label="$1" needle="$2"
    rm -f "$gfile"
    set +e
    stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
      DELIVER_WORKTREE="$gsrc" \
      "$SELF" --repo acme/print-bench --issue 869 --base "$gstart" \
      --base-branch main --run-url https://example.test/run/1 \
      --routine backlog-burn --write-bundle "$gfile" 2>&1 >/dev/null)"
    rc=$?
    set -e
    [ "$rc" -eq 1 ] || {
      echo "selftest: backlog-burn accepted protected ${label} (exit ${rc})" >&2
      printf '%s\n' "$stderr" >&2
      exit 1
    }
    printf '%s\n' "$stderr" | grep "$needle" >/dev/null || {
      echo "selftest: backlog-burn protected ${label} did not report the refusal" >&2
      printf '%s\n' "$stderr" >&2
      exit 1
    }
    [ ! -e "$gfile" ] || {
      echo "selftest: backlog-burn wrote a bundle for protected ${label}" >&2
      exit 1
    }
  }

  rm -rf "$gsrc"
  mkdir -p "$gsrc/.github/workflows" "$gsrc/.claude/hooks" \
    "$gsrc/scripts" "$gsrc/tools" "$gsrc/docs" "$gsrc/safe"
  git_cmd -C "$gsrc" init -b main >/dev/null
  printf 'name: keep\non: push\njobs: {}\n' > "$gsrc/.github/workflows/keep.yml"
  printf 'keep\n' > "$gsrc/.claude/hooks/keep.sh"
  printf 'keep\n' > "$gsrc/scripts/keep.sh"
  printf 'keep\n' > "$gsrc/tools/keep.py"
  printf 'seed\n' > "$gsrc/docs/seed.md"
  printf 'park\n' > "$gsrc/safe/parked.txt"
  # Seed root agent-instruction files at gstart so symlink-into cases only
  # change docs/hook (otherwise the range also touches CLAUDE.md itself).
  printf 'seed\n' > "$gsrc/CLAUDE.md"
  printf 'seed\n' > "$gsrc/AGENTS.md"
  printf '{}\n' > "$gsrc/.mcp.json"
  git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
    .github/workflows/keep.yml .claude/hooks/keep.sh scripts/keep.sh \
    tools/keep.py docs/seed.md safe/parked.txt \
    CLAUDE.md AGENTS.md .mcp.json
  git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m start >/dev/null
  gstart="$(git_cmd -C "$gsrc" rev-parse HEAD)"
  git_cmd -C "$gsrc" checkout -b claude/issue-869-protected-forbid >/dev/null 2>&1

  for prefix in .github .claude scripts tools; do
    case "$prefix" in
      .github) mkdir -p "$gsrc/.github/workflows" ;;
      .claude) mkdir -p "$gsrc/.claude/hooks" ;;
      scripts|tools) mkdir -p "$gsrc/$prefix" ;;
    esac

    # Add
    case "$prefix" in
      .github)
        printf 'name: evil\non: push\njobs: {}\n' > "$gsrc/.github/workflows/evil.yml"
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
          .github/workflows/evil.yml
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "add ${prefix}" >/dev/null
        greject "${prefix}/add" 'touches .github/workflows/evil.yml'
        ;;
      .claude)
        printf 'evil\n' > "$gsrc/.claude/hooks/evil.sh"
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
          .claude/hooks/evil.sh
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "add ${prefix}" >/dev/null
        greject "${prefix}/add" 'touches .claude/hooks/evil.sh'
        ;;
      scripts)
        printf 'evil\n' > "$gsrc/scripts/evil.sh"
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- scripts/evil.sh
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "add ${prefix}" >/dev/null
        greject "${prefix}/add" 'touches scripts/evil.sh'
        ;;
      tools)
        printf 'evil\n' > "$gsrc/tools/evil.py"
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- tools/evil.py
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "add ${prefix}" >/dev/null
        greject "${prefix}/add" 'touches tools/evil.py'
        ;;
    esac
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Modify
    case "$prefix" in
      .github)
        printf 'name: keep\non: push\njobs: {x: {runs-on: ubuntu-latest, steps: []}}\n' \
          > "$gsrc/.github/workflows/keep.yml"
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
          .github/workflows/keep.yml
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "mod ${prefix}" >/dev/null
        greject "${prefix}/modify" 'touches .github/workflows/keep.yml'
        ;;
      .claude)
        printf 'changed\n' > "$gsrc/.claude/hooks/keep.sh"
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
          .claude/hooks/keep.sh
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "mod ${prefix}" >/dev/null
        greject "${prefix}/modify" 'touches .claude/hooks/keep.sh'
        ;;
      scripts)
        printf 'changed\n' > "$gsrc/scripts/keep.sh"
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- scripts/keep.sh
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "mod ${prefix}" >/dev/null
        greject "${prefix}/modify" 'touches scripts/keep.sh'
        ;;
      tools)
        printf 'changed\n' > "$gsrc/tools/keep.py"
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- tools/keep.py
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "mod ${prefix}" >/dev/null
        greject "${prefix}/modify" 'touches tools/keep.py'
        ;;
    esac
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Delete
    case "$prefix" in
      .github)
        git_cmd -C "$gsrc" rm -q -- .github/workflows/keep.yml
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "del ${prefix}" >/dev/null
        greject "${prefix}/delete" 'touches .github/workflows/keep.yml'
        ;;
      .claude)
        git_cmd -C "$gsrc" rm -q -- .claude/hooks/keep.sh
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "del ${prefix}" >/dev/null
        greject "${prefix}/delete" 'touches .claude/hooks/keep.sh'
        ;;
      scripts)
        git_cmd -C "$gsrc" rm -q -- scripts/keep.sh
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "del ${prefix}" >/dev/null
        greject "${prefix}/delete" 'touches scripts/keep.sh'
        ;;
      tools)
        git_cmd -C "$gsrc" rm -q -- tools/keep.py
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "del ${prefix}" >/dev/null
        greject "${prefix}/delete" 'touches tools/keep.py'
        ;;
    esac
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Rename into protected prefix (from safe/)
    case "$prefix" in
      .github)
        git_cmd -C "$gsrc" mv -- safe/parked.txt .github/workflows/moved.yml
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "ren-in ${prefix}" >/dev/null
        greject "${prefix}/rename-into" '\.github/workflows/moved\.yml'
        ;;
      .claude)
        git_cmd -C "$gsrc" mv -- safe/parked.txt .claude/hooks/moved.sh
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "ren-in ${prefix}" >/dev/null
        greject "${prefix}/rename-into" '\.claude/hooks/moved\.sh'
        ;;
      scripts)
        git_cmd -C "$gsrc" mv -- safe/parked.txt scripts/moved.sh
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "ren-in ${prefix}" >/dev/null
        greject "${prefix}/rename-into" 'scripts/moved\.sh'
        ;;
      tools)
        git_cmd -C "$gsrc" mv -- safe/parked.txt tools/moved.py
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "ren-in ${prefix}" >/dev/null
        greject "${prefix}/rename-into" 'tools/moved\.py'
        ;;
    esac
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Rename out of protected prefix (into docs/)
    case "$prefix" in
      .github)
        git_cmd -C "$gsrc" mv -- .github/workflows/keep.yml docs/exfiltrated.yml
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "ren-out ${prefix}" >/dev/null
        greject "${prefix}/rename-out" '\.github/workflows/keep\.yml'
        ;;
      .claude)
        git_cmd -C "$gsrc" mv -- .claude/hooks/keep.sh docs/exfiltrated.sh
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "ren-out ${prefix}" >/dev/null
        greject "${prefix}/rename-out" '\.claude/hooks/keep\.sh'
        ;;
      scripts)
        git_cmd -C "$gsrc" mv -- scripts/keep.sh docs/exfiltrated.sh
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "ren-out ${prefix}" >/dev/null
        greject "${prefix}/rename-out" 'scripts/keep\.sh'
        ;;
      tools)
        git_cmd -C "$gsrc" mv -- tools/keep.py docs/exfiltrated.py
        git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "ren-out ${prefix}" >/dev/null
        greject "${prefix}/rename-out" 'tools/keep\.py'
        ;;
    esac
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Symlink into protected prefix (path itself under docs/)
    case "$prefix" in
      .github)
        ln -s '../.github/workflows/keep.yml' "$gsrc/docs/hook"
        ;;
      .claude)
        ln -s '../.claude/hooks/keep.sh' "$gsrc/docs/hook"
        ;;
      scripts)
        ln -s '../scripts/keep.sh' "$gsrc/docs/hook"
        ;;
      tools)
        ln -s '../tools/keep.py' "$gsrc/docs/hook"
        ;;
    esac
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- docs/hook
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m "symlink ${prefix}" >/dev/null
    greject "${prefix}/symlink" 'points under a protected prefix'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null
  done

  # Case-folded .GitHub/ path — normalizer lowercases before the match.
  mkdir -p "$gsrc/.GitHub/workflows"
  printf 'name: case\non: push\njobs: {}\n' > "$gsrc/.GitHub/workflows/case.yml"
  git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
    .GitHub/workflows/case.yml
  git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m 'case fold' >/dev/null
  greject 'case-fold' 'touches'
  git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

  # Absolute symlink target fails closed.
  ln -s '/etc/passwd' "$gsrc/docs/abs"
  git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- docs/abs
  git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m 'abs symlink' >/dev/null
  greject 'abs-symlink' 'points under a protected prefix'
  git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

  # Gitlink (mode 160000) under a protected prefix — refused by path and
  # by the explicit gitlink check.
  blob_sha="$(git_cmd -C "$gsrc" rev-parse "HEAD:docs/seed.md")"
  git_cmd -C "$gsrc" update-index --add --cacheinfo "160000,${blob_sha},scripts/submod"
  git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m 'gitlink' >/dev/null
  greject gitlink 'touches scripts/submod'
  git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

  # Backslash in a path — normalize fails closed (single `\`, not `\\`).
  mkdir -p "$gsrc/docs"
  printf 'x\n' > "${gsrc}/docs/foo\\bar"
  git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- "docs/foo\\bar"
  git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m 'backslash path' >/dev/null
  # Needle is a BRE: `\\` matches one literal backslash (`\b` would be a word boundary).
  greject backslash 'touches docs/foo\\bar'
  git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

  # Root agent-instruction files (CLAUDE.md, AGENTS.md, .mcp.json) —
  # add / modify / rename into / symlink into — refused for both routines
  # (issue #869). Names are case-folded by the normalizer.
  local rootfile routine
  reject_rootfile() {  # $1 routine, $2 label, $3 needle
    local routine="$1" label="$2" needle="$3"
    rm -f "$gfile"
    set +e
    stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
      DELIVER_WORKTREE="$gsrc" \
      "$SELF" --repo acme/print-bench --issue 869 --base "$gstart" \
      --base-branch main --run-url https://example.test/run/1 \
      --routine "$routine" --write-bundle "$gfile" 2>&1 >/dev/null)"
    rc=$?
    set -e
    [ "$rc" -eq 1 ] || {
      echo "selftest: ${routine} accepted protected ${label} (exit ${rc})" >&2
      printf '%s\n' "$stderr" >&2
      exit 1
    }
    printf '%s\n' "$stderr" | grep "$needle" >/dev/null || {
      echo "selftest: ${routine} protected ${label} did not report the refusal" >&2
      printf '%s\n' "$stderr" >&2
      exit 1
    }
    [ ! -e "$gfile" ] || {
      echo "selftest: ${routine} wrote a bundle for protected ${label}" >&2
      exit 1
    }
  }
  for routine in backlog-burn design-run; do
    for rootfile in CLAUDE.md AGENTS.md .mcp.json; do
      # Add — delete the seeded file then recreate so the tip introduces
      # the path as an addition relative to a parent that lacked it; the
      # range still refuses on the protected path either way.
      git_cmd -C "$gsrc" rm -q -- "$rootfile"
      git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
        commit -m "drop ${rootfile}" >/dev/null
      printf 'evil\n' > "$gsrc/$rootfile"
      git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- "$rootfile"
      git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
        commit -m "add ${rootfile}" >/dev/null
      reject_rootfile "$routine" "${rootfile}/add" "touches ${rootfile}"
      git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

      # Modify (files already seeded at gstart)
      printf 'changed\n' > "$gsrc/$rootfile"
      git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- "$rootfile"
      git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
        commit -m "mod ${rootfile}" >/dev/null
      reject_rootfile "$routine" "${rootfile}/modify" "touches ${rootfile}"
      git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

      # Rename into (replace the seeded file from safe/)
      git_cmd -C "$gsrc" rm -q -- "$rootfile"
      git_cmd -C "$gsrc" mv -- safe/parked.txt "$rootfile"
      git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
        commit -m "ren-in ${rootfile}" >/dev/null
      reject_rootfile "$routine" "${rootfile}/rename-into" "touches ${rootfile}"
      git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

      # Symlink into (path under docs/ pointing at the seeded root file)
      ln -s "../${rootfile}" "$gsrc/docs/hook"
      git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- docs/hook
      git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
        commit -m "symlink ${rootfile}" >/dev/null
      reject_rootfile "$routine" "${rootfile}/symlink" 'points under a protected prefix'
      git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null
    done
  done

  # Nested agent-instruction paths at ANY depth (issue #869 Cipher MEDIUM):
  # docs/CLAUDE.md, designs/<name>/{CLAUDE,AGENTS}.md, lib/.mcp.json,
  # nested .cursor/rules/, nested .cursorrules, case variant, plus
  # rename-into and symlink-into (path matches or target is protected).
  reject_nested() {  # $1 routine, $2 label, $3 needle
    reject_rootfile "$1" "$2" "$3"
  }
  for routine in backlog-burn design-run; do
    # docs/CLAUDE.md — add
    mkdir -p "$gsrc/docs"
    printf 'evil\n' > "$gsrc/docs/CLAUDE.md"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- docs/CLAUDE.md
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'add docs/CLAUDE.md' >/dev/null
    reject_nested "$routine" 'docs/CLAUDE.md/add' 'touches docs/CLAUDE.md'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # designs/<name>/CLAUDE.md — add (alone; multi-path commits report one)
    mkdir -p "$gsrc/designs/gadget"
    printf 'evil\n' > "$gsrc/designs/gadget/CLAUDE.md"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
      designs/gadget/CLAUDE.md
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'add designs/gadget/CLAUDE.md' >/dev/null
    reject_nested "$routine" 'designs/gadget/CLAUDE.md/add' 'touches designs/gadget/CLAUDE.md'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # designs/<name>/AGENTS.md — add
    mkdir -p "$gsrc/designs/gadget"
    printf 'evil\n' > "$gsrc/designs/gadget/AGENTS.md"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
      designs/gadget/AGENTS.md
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'add designs/gadget/AGENTS.md' >/dev/null
    reject_nested "$routine" 'designs/gadget/AGENTS.md/add' 'touches designs/gadget/AGENTS.md'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # lib/.mcp.json — add (design-run otherwise allows single-file lib/)
    mkdir -p "$gsrc/lib"
    printf '{}\n' > "$gsrc/lib/.mcp.json"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- lib/.mcp.json
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'add lib/.mcp.json' >/dev/null
    reject_nested "$routine" 'lib/.mcp.json/add' 'touches lib/\.mcp\.json'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Nested .cursor/rules/x.mdc — add
    mkdir -p "$gsrc/a/b/.cursor/rules"
    printf 'rule\n' > "$gsrc/a/b/.cursor/rules/x.mdc"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
      a/b/.cursor/rules/x.mdc
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'add nested .cursor rules' >/dev/null
    reject_nested "$routine" 'nested-.cursor/add' 'touches a/b/\.cursor/rules/x\.mdc'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Nested .cursorrules — add
    mkdir -p "$gsrc/docs/deep"
    printf 'rules\n' > "$gsrc/docs/deep/.cursorrules"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
      docs/deep/.cursorrules
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'add nested .cursorrules' >/dev/null
    reject_nested "$routine" 'nested-.cursorrules/add' 'touches docs/deep/\.cursorrules'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Case variant docs/claude.MD — normalizer folds case
    mkdir -p "$gsrc/docs"
    printf 'evil\n' > "$gsrc/docs/claude.MD"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- docs/claude.MD
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'add docs/claude.MD' >/dev/null
    reject_nested "$routine" 'docs/claude.MD/case' 'touches'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # CLAUDE.local.md nested — add
    mkdir -p "$gsrc/docs"
    printf 'evil\n' > "$gsrc/docs/CLAUDE.local.md"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
      docs/CLAUDE.local.md
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'add docs/CLAUDE.local.md' >/dev/null
    reject_nested "$routine" 'docs/CLAUDE.local.md/add' 'touches docs/CLAUDE\.local\.md'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Rename into nested protected path
    mkdir -p "$gsrc/docs"
    git_cmd -C "$gsrc" mv -- safe/parked.txt docs/CLAUDE.md
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'rename into docs/CLAUDE.md' >/dev/null
    reject_nested "$routine" 'docs/CLAUDE.md/rename-into' 'touches docs/CLAUDE.md'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Symlink whose path matches a protected name (docs/CLAUDE.md -> seed.md)
    mkdir -p "$gsrc/docs"
    ln -s 'seed.md' "$gsrc/docs/CLAUDE.md"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- docs/CLAUDE.md
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'symlink path docs/CLAUDE.md' >/dev/null
    reject_nested "$routine" 'docs/CLAUDE.md/symlink-path' 'touches docs/CLAUDE.md'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Symlink whose target is a nested protected path (seed target at tip
    # first, then reset base past the seed so the range only adds the link).
    mkdir -p "$gsrc/docs"
    printf 'seed\n' > "$gsrc/docs/CLAUDE.md"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- docs/CLAUDE.md
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'seed docs/CLAUDE.md for symlink target' >/dev/null
    local nested_base
    nested_base="$(git_cmd -C "$gsrc" rev-parse HEAD)"
    ln -s 'CLAUDE.md' "$gsrc/docs/hook"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- docs/hook
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'symlink target docs/CLAUDE.md' >/dev/null
    # Temporarily point reject at nested_base..HEAD (only the symlink).
    rm -f "$gfile"
    set +e
    stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
      DELIVER_WORKTREE="$gsrc" \
      "$SELF" --repo acme/print-bench --issue 869 --base "$nested_base" \
      --base-branch main --run-url https://example.test/run/1 \
      --routine "$routine" --write-bundle "$gfile" 2>&1 >/dev/null)"
    rc=$?
    set -e
    [ "$rc" -eq 1 ] || {
      echo "selftest: ${routine} accepted docs/hook->CLAUDE.md (exit ${rc})" >&2
      printf '%s\n' "$stderr" >&2
      exit 1
    }
    printf '%s\n' "$stderr" | grep 'points under a protected prefix' >/dev/null || {
      echo "selftest: ${routine} docs/hook->CLAUDE.md did not report symlink refusal" >&2
      printf '%s\n' "$stderr" >&2
      exit 1
    }
    [ ! -e "$gfile" ] || {
      echo "selftest: ${routine} wrote a bundle for docs/hook->CLAUDE.md" >&2
      exit 1
    }
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Delete nested protected path
    mkdir -p "$gsrc/docs"
    printf 'seed\n' > "$gsrc/docs/CLAUDE.md"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- docs/CLAUDE.md
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'seed docs/CLAUDE.md for delete' >/dev/null
    git_cmd -C "$gsrc" rm -q -- docs/CLAUDE.md
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'delete docs/CLAUDE.md' >/dev/null
    reject_nested "$routine" 'docs/CLAUDE.md/delete' 'touches docs/CLAUDE.md'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Nested **/.claude/** at any depth (issue #879) — add + case variant.
    mkdir -p "$gsrc/docs/.claude/skills/x"
    printf 'evil\n' > "$gsrc/docs/.claude/skills/x/SKILL.md"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
      docs/.claude/skills/x/SKILL.md
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'add nested .claude skill' >/dev/null
    reject_nested "$routine" 'nested-.claude/add' \
      'touches docs/\.claude/skills/x/SKILL\.md'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    mkdir -p "$gsrc/docs/.CLAUDE/skills/x"
    printf 'evil\n' > "$gsrc/docs/.CLAUDE/skills/x/SKILL.md"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
      docs/.CLAUDE/skills/x/SKILL.md
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'add nested .CLAUDE case' >/dev/null
    reject_nested "$routine" 'nested-.CLAUDE/case' 'touches'
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

    # Pathspec-magic symlink name (issue #879): without GIT_LITERAL_PATHSPECS
    # ls-tree treats `:^y` as exclude magic, returns empty, and the check
    # used to pass. Literal lookup must see the symlink and refuse the
    # protected target.
    mkdir -p "$gsrc/.claude"
    printf 'seed\n' > "$gsrc/.claude/x"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- .claude/x
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'seed .claude/x for pathspec-magic symlink' >/dev/null
    local magic_base
    magic_base="$(git_cmd -C "$gsrc" rev-parse HEAD)"
    ln -s '.claude/x' "$gsrc/:^y"
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- ':^y'
    git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
      commit -m 'pathspec-magic symlink' >/dev/null
    rm -f "$gfile"
    set +e
    stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
      DELIVER_WORKTREE="$gsrc" \
      "$SELF" --repo acme/print-bench --issue 869 --base "$magic_base" \
      --base-branch main --run-url https://example.test/run/1 \
      --routine "$routine" --write-bundle "$gfile" 2>&1 >/dev/null)"
    rc=$?
    set -e
    [ "$rc" -eq 1 ] || {
      echo "selftest: ${routine} accepted pathspec-magic symlink :^y (exit ${rc})" >&2
      printf '%s\n' "$stderr" >&2
      exit 1
    }
    printf '%s\n' "$stderr" | grep 'points under a protected prefix' >/dev/null || {
      echo "selftest: ${routine} pathspec-magic :^y did not report symlink refusal" >&2
      printf '%s\n' "$stderr" >&2
      exit 1
    }
    [ ! -e "$gfile" ] || {
      echo "selftest: ${routine} wrote a bundle for pathspec-magic :^y" >&2
      exit 1
    }
    git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null
  done

  # ls-tree failure fails closed (issue #879): a wrapper GIT_BIN that
  # exits 128 on ls-tree must refuse a otherwise-benign docs/ delivery.
  cat > "${tmp}/bin/git-fail-lstree" <<'EOF'
#!/bin/sh
real=/usr/bin/git
skip=
for arg in "$@"; do
  if [ -n "$skip" ]; then
    skip=
    continue
  fi
  case "$arg" in
    -C|-c|--git-dir|--work-tree) skip=1; continue ;;
    --no-replace-objects|-* ) continue ;;
    ls-tree)
      echo "planted ls-tree failure" >&2
      exit 128
      ;;
    *) break ;;
  esac
done
exec "$real" "$@"
EOF
  chmod +x "${tmp}/bin/git-fail-lstree"
  printf 'ok\n' > "$gsrc/docs/lstree-fail.md"
  git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- \
    docs/lstree-fail.md
  git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t \
    commit -m 'docs for ls-tree fail-closed' >/dev/null
  rm -f "$gfile"
  set +e
  stderr="$(env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_BIN="${tmp}/bin/git-fail-lstree" \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$gsrc" \
    "$SELF" --repo acme/print-bench --issue 869 --base "$gstart" \
    --base-branch main --run-url https://example.test/run/1 \
    --routine backlog-burn --write-bundle "$gfile" 2>&1 >/dev/null)"
  rc=$?
  set -e
  [ "$rc" -eq 1 ] || {
    echo "selftest: ls-tree failure did not fail closed (exit ${rc})" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  printf '%s\n' "$stderr" | grep 'ls-tree failed for' >/dev/null || {
    echo "selftest: ls-tree failure did not report the refusal" >&2
    printf '%s\n' "$stderr" >&2
    exit 1
  }
  [ ! -e "$gfile" ] || {
    echo "selftest: ls-tree failure wrote a bundle" >&2
    exit 1
  }
  git_cmd -C "$gsrc" reset --hard "$gstart" >/dev/null

  # Benign docs/ change still passes for backlog-burn.
  printf 'ok\n' > "$gsrc/docs/ok.md"
  git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t add -- docs/ok.md
  git_cmd -C "$gsrc" -c user.email=t@example.com -c user.name=t commit -m 'docs ok' >/dev/null
  rm -f "$gfile"
  set +e
  env GH_BIN="${tmp}/bin/gh" GH_TOKEN=test-token \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    DELIVER_WORKTREE="$gsrc" \
    "$SELF" --repo acme/print-bench --issue 869 --base "$gstart" \
    --base-branch main --run-url https://example.test/run/1 \
    --routine backlog-burn --write-bundle "$gfile" >/dev/null
  rc=$?
  set -e
  [ "$rc" -eq 0 ] && [ -f "$gfile" ] || {
    echo "selftest: backlog-burn refused a benign docs/ commit (exit ${rc})" >&2
    exit 1
  }

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
      export GITHUB_WORKSPACE="$dir"
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

  echo "design-run-deliver selftest: ok"
}

REPO="" ISSUE="" BASE="" BASE_BRANCH="" RUN_URL="" PUSH_URL="" BRANCH="" ASKPASS=""
BUNDLE="" BUNDLE_SHA256="" WRITE_BUNDLE="" WRITE_INTENTS="" APPLY_INTENTS="" DELIVER_REF="HEAD"

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
    --routine) ROUTINE="${2:-}"; shift 2 ;;
    --write-intents) WRITE_INTENTS="${2:-}"; shift 2 ;;
    --apply-intents) APPLY_INTENTS="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) usage "unknown argument: $1" ;;
  esac
done

[ -n "$REPO" ] && [ -n "$ISSUE" ] && [ -n "$BASE" ] && [ -n "$BASE_BRANCH" ] && [ -n "$RUN_URL" ] \
  || usage "missing required argument"
if [ -n "$WRITE_BUNDLE" ] && [ -n "$BUNDLE" ]; then
  usage "pass only one of --bundle and --write-bundle"
fi
if [ -n "$WRITE_INTENTS" ] && [ -z "$WRITE_BUNDLE" ]; then
  usage "--write-intents rides the bundle step (pass --write-bundle too)"
fi
if [ -n "$APPLY_INTENTS" ] && { [ -n "$WRITE_BUNDLE" ] || [ -n "$WRITE_INTENTS" ] || [ -n "$BUNDLE" ]; }; then
  usage "pass only one of --apply-intents and the write/bundle modes"
fi
if [ -n "$BUNDLE" ] && [ -z "$BUNDLE_SHA256" ]; then
  usage "--bundle requires --bundle-sha256"
fi
[ -z "$PUSH_URL" ] && PUSH_URL="https://github.com/${REPO}.git"

# Per-routine wording, applied after parsing so every reader below resolves
# it at call time (issue #863). design-run keeps the pre-flag literals
# byte-for-byte; an unknown routine is a usage error, never a silent
# fallback — a typo'd routine must not ship design-run's narrow path policy
# under backlog-burn's name or vice versa.
case "$ROUTINE" in
  design-run)
    DELIVERED_LINE='🚢 design-run delivered — branch and draft PR verified'
    COMMIT_SUBJECT="Design for #${ISSUE}"
    PR_TITLE_FALLBACK="Design for #${ISSUE}"
    ;;
  backlog-burn)
    DELIVERED_LINE='🚢 backlog-burn delivered — branch and draft PR verified'
    COMMIT_SUBJECT="Ship #${ISSUE}"
    PR_TITLE_FALLBACK="Ship #${ISSUE}"
    ;;
  *) usage "unknown routine: ${ROUTINE}" ;;
esac

run_live
