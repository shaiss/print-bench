#!/usr/bin/env bash
# gh-project.sh — emit repeatable `gh` recipes that provision this repo's
# GitHub Projects (v2) boards from a committed spec.
#
# TWO BOARDS, one emitter (pass `--board <name>` before the subcommand;
# default `autonomy`):
#   * autonomy — the roadmap board (issue #148): the autonomy loop's backlog,
#     with a human-owned Stage and Story points. docs/roadmap-board.md.
#   * growth   — the Lark approval board (docs/growth.md): where each queued
#     Twitter/X post sits, so a human can see and approve them. Its Stage is a
#     pure LENS the growth-board-sync workflow derives from each queue issue's
#     state + labels + markers (growth.board.stage_of), so it has no Story
#     points and its Stage is always set, never set-if-new.
#
# WHY a recipe you run, not an API call the automation makes: this session's
# tooling cannot create or populate a Projects v2 board (the board/field/item
# API is GraphQL-only and unavailable here), and a Project is settings-shaped
# anyway. So each board's schema lives HERE as the committed source of truth,
# and `setup` prints the exact, idempotent `gh` commands that create it —
# reviewable before you run it, and repeatable in the future. Populating a board
# (adding issues, setting fields) is done by a sync workflow; see
# docs/roadmap-board.md (autonomy) and docs/growth.md (growth).
#
# Usage:
#   scripts/gh-project.sh [--board <name>] setup         # print the idempotent board-provisioning recipe
#   scripts/gh-project.sh [--board <name>] setup | bash  # run it (needs gh >= 2.30 + jq + the `project` scope)
#   scripts/gh-project.sh [--board <name>] add-item <issue-or-pr-url> [--stage <name> | --stage-if-new <name>] [--points <n>]
#                                       # print an idempotent recipe that adds ONE issue/PR to the
#                                       # board and sets its Stage / Story points; pipe to bash to run.
#                                       # --stage always sets the Stage; --stage-if-new sets it only when
#                                       # the item is first added (so a re-add never clobbers a human's move)
#   scripts/gh-project.sh --selftest    # prove the emitted recipes are valid, well-formed bash (run by check.sh)
#
# AUTH: `gh project` requires the `project` token scope, which login does NOT
# grant by default and which a `contents:write` fine-grained PAT (e.g.
# REGEN_TOKEN) does NOT include; the Actions GITHUB_TOKEN cannot touch Projects
# v2 at all. When run as a human with a stored gh login, the recipe grants the
# scope for you (`gh auth refresh -s project`) only if it is missing, reading
# from /dev/tty so the interactive flow works even under `setup | bash`. For the
# automation slice, add the Projects (read/write) permission to the token — see
# docs/roadmap-board.md.
set -euo pipefail

SELF="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)/$(basename "$0")"

die() { echo "gh-project: $*" >&2; exit 1; }

# ---- the board specs: the committed source of truth ------------------------
# Change a spec to reshape its board; the emitted recipe is idempotent, so
# re-running it reconciles the live board to the spec. `select_board` sets the
# active spec into these globals; the emitters read them. Both boards live under
# the same owner (a user, not an org).
PROJECT_OWNER="shaiss"
DEFAULT_BOARD="autonomy"

# The active spec, filled by select_board. STAGE_FIELD is a distinct
# SINGLE_SELECT because GitHub gives every board a built-in "Status"
# (Todo/In Progress/Done) the CLI cannot reshape, so we add "Stage" and group
# the board by it in the UI (view config is UI-only). Options are ordered; names
# only (the CLI can't set colours). POINTS_FIELD is a NUMBER field, or empty for
# a board that does not estimate.
PROJECT_TITLE=""
STAGE_FIELD=""
STAGE_OPTIONS=""
POINTS_FIELD=""

select_board() {  # $1 = board name; sets the spec globals (and BOARD) or dies
  BOARD="$1"
  case "$1" in
    autonomy)
      PROJECT_TITLE="print-bench autonomy"
      STAGE_FIELD="Stage"
      STAGE_OPTIONS="Backlog,Ready,In progress,In review,Done"
      # Story points, Fibonacci 1/2/3/5/8 by convention: a chunked one-PR
      # sub-issue is 1-3; a bigger estimate is a hint it should be re-chunked.
      POINTS_FIELD="Story points"
      ;;
    growth)
      PROJECT_TITLE="print-bench growth"
      STAGE_FIELD="Stage"
      # The Lark approval pipeline. Kept in lockstep with
      # growth.board.BOARD_STAGE_OPTIONS (tools/growth) — a drift test in
      # tools/growth/tests/test_board.py reads this line and fails if the two
      # disagree, so the provisioning recipe and the stage policy name the same
      # stages. A queued post moves Queued -> Drafted (Lark's dry-run) ->
      # Approved (a human's approved-to-post label) -> Posted; Parked is
      # needs-decision, Attention is a live claim that never closed.
      STAGE_OPTIONS="Queued,Drafted,Approved,Posted,Parked,Attention"
      # Growth posts are not estimated: no Story points field.
      POINTS_FIELD=""
      ;;
    *)
      die "unknown board '$1' (known: autonomy, growth)"
      ;;
  esac
}

# Emit the provisioning recipe from the spec above. Deterministic and
# side-effect-free: it only prints. The spec values are substituted into a
# header (unquoted heredoc); the body is literal (quoted heredoc) and reads them
# as its own runtime variables, so the recipe is the single source and this
# emitter needs no `gh` itself.
emit_recipe() {
  cat <<EOF
#!/usr/bin/env bash
# Provision the "$PROJECT_TITLE" GitHub Project (v2). Idempotent — re-run to
# reconcile. GENERATED by scripts/gh-project.sh: edit the board spec there, not
# this output. Needs gh >= 2.30 and jq.
set -euo pipefail

OWNER="$PROJECT_OWNER"
TITLE="$PROJECT_TITLE"
STAGE_FIELD="$STAGE_FIELD"
STAGE_OPTIONS="$STAGE_OPTIONS"
POINTS_FIELD="$POINTS_FIELD"
EOF
  # Part A — steps 0-1 and the field_absent helper (every board has these).
  cat <<'EOF'

# 0. `gh project` needs the `project` scope (not granted at login; not covered
#    by a contents:write PAT). Four cases, in order:
#      * an env-var token (CI/automation): `gh auth refresh` ERRORS on a
#        GH_TOKEN/GITHUB_TOKEN ("environment variable is being used for
#        authentication") and would abort under `set -e`, so we skip it — the
#        scope must already be on that token;
#      * a stored login that already has the scope: nothing to do;
#      * a stored login missing the scope, with a terminal: grant it once,
#        interactively, reading /dev/tty so `setup | bash` (which owns bash's
#        stdin) can still prompt;
#      * missing the scope with no terminal: print how to grant it and stop.
if [ -n "${GH_TOKEN:-}" ] || [ -n "${GITHUB_TOKEN:-}" ]; then
  echo "auth: using a token from the environment — ensure it carries the 'project' scope" >&2
elif gh auth status 2>&1 | grep -q "'project'"; then
  echo "auth: your gh login already carries the 'project' scope" >&2
elif [ -e /dev/tty ]; then
  # Grant the scope once, interactively. `setup | bash` pipes THIS recipe into
  # bash's stdin, so `gh auth refresh` (an interactive OAuth device flow) has no
  # terminal to prompt on and errors with "--hostname required when not running
  # interactively". Point it at the controlling terminal so the documented
  # `… | bash` invocation still works.
  echo "auth: granting gh the 'project' scope (interactive) …" >&2
  gh auth refresh -s project < /dev/tty
else
  echo "auth: gh is missing the 'project' scope and no terminal is available to" >&2
  echo "      grant it. Run this once in your shell, then re-run the recipe:" >&2
  echo "        gh auth refresh -s project" >&2
  exit 1
fi

# 1. Board — create only if one with this title does not already exist.
NUM=$(gh project list --owner "$OWNER" -L 200 --format json \
  --jq ".projects[] | select(.title==\"$TITLE\") | .number")
if [ -z "$NUM" ]; then
  gh project create --owner "$OWNER" --title "$TITLE" --format json >/dev/null
  NUM=$(gh project list --owner "$OWNER" -L 200 --format json \
    --jq ".projects[] | select(.title==\"$TITLE\") | .number")
fi
[ -n "$NUM" ] || { echo "could not resolve project number for '$TITLE'" >&2; exit 1; }
echo "project #$NUM  ($TITLE)"

# A field is absent when nothing in the field list has its name (empty result).
field_absent() {  # $1 = field name
  [ -z "$(gh project field-list "$NUM" --owner "$OWNER" -L 200 --format json \
    --jq ".fields[] | select(.name==\"$1\") | .name")" ]
}
EOF

  # Part B — the "Story points" (NUMBER) field, emitted ONLY for a board whose
  # spec carries one. A board without points (growth) gets no Story-points bash
  # in its recipe at all, rather than a runtime-inert guarded block.
  if [ -n "$POINTS_FIELD" ]; then
    cat <<'EOF'

# 2. "Story points" (NUMBER) — create if absent.
if field_absent "$POINTS_FIELD"; then
  gh project field-create "$NUM" --owner "$OWNER" --name "$POINTS_FIELD" --data-type NUMBER
  echo "created field: $POINTS_FIELD (NUMBER)"
else
  echo "field exists: $POINTS_FIELD"
fi
EOF
  fi

  # Part C — the "Stage" (SINGLE_SELECT) field (every board has one).
  cat <<'EOF'

# 3. "Stage" (SINGLE_SELECT) with our pipeline options — create if absent.
#    The built-in "Status" field is left untouched (the CLI can't reshape it);
#    group the board's Board view by "Stage" in the UI.
if field_absent "$STAGE_FIELD"; then
  gh project field-create "$NUM" --owner "$OWNER" --name "$STAGE_FIELD" \
    --data-type SINGLE_SELECT --single-select-options "$STAGE_OPTIONS"
  echo "created field: $STAGE_FIELD (SINGLE_SELECT: $STAGE_OPTIONS)"
else
  echo "field exists: $STAGE_FIELD"
fi
EOF

  # The closing add-item hint, matched to the board (points for autonomy, the
  # first Stage option as the entry stage for a lens board like growth).
  if [ -n "$POINTS_FIELD" ]; then
    cat <<EOF
echo "done. add issues to the board with:"
echo "  scripts/gh-project.sh add-item https://github.com/$PROJECT_OWNER/print-bench/issues/<N> --stage ${STAGE_OPTIONS%%,*} --points <n> | bash"
EOF
  else
    cat <<EOF
echo "done. add issues to the board with:"
echo "  scripts/gh-project.sh --board $BOARD add-item https://github.com/$PROJECT_OWNER/print-bench/issues/<N> --stage ${STAGE_OPTIONS%%,*} | bash"
EOF
  fi
}

# Emit an idempotent recipe that adds ONE issue/PR to the board and (optionally)
# sets its Stage and Story points. Same emit-only design as emit_recipe: it only
# prints, so it needs no `gh` and is testable. Args: url, stage (may be ""),
# points (may be ""), stage_if_new ("1" = set the stage only when the item is
# newly created, "0" = always set it). The caller validates them (add_item_cli)
# before they are substituted here.
emit_add_item() {
  local url="$1" stage="$2" points="$3" stage_if_new="${4:-0}"
  cat <<EOF
#!/usr/bin/env bash
# Add $url to the "$PROJECT_TITLE" board and set its fields. Idempotent — re-run
# to reconcile. GENERATED by scripts/gh-project.sh. Needs gh + jq.
set -euo pipefail

OWNER="$PROJECT_OWNER"
TITLE="$PROJECT_TITLE"
URL="$url"
STAGE="$stage"
POINTS="$points"
STAGE_IF_NEW="$stage_if_new"
STAGE_FIELD="$STAGE_FIELD"
POINTS_FIELD="$POINTS_FIELD"
EOF
  cat <<'EOF'

# Same env-var-token guard as the provisioning recipe (don't abort under set -e).
if [ -n "${GH_TOKEN:-}" ] || [ -n "${GITHUB_TOKEN:-}" ]; then
  echo "auth: using a token from the environment — ensure it carries the 'project' scope" >&2
elif gh auth status 2>&1 | grep -q "'project'"; then
  echo "auth: your gh login already carries the 'project' scope" >&2
elif [ -e /dev/tty ]; then
  # Grant the scope once, interactively. `setup | bash` pipes THIS recipe into
  # bash's stdin, so `gh auth refresh` (an interactive OAuth device flow) has no
  # terminal to prompt on and errors with "--hostname required when not running
  # interactively". Point it at the controlling terminal so the documented
  # `… | bash` invocation still works.
  echo "auth: granting gh the 'project' scope (interactive) …" >&2
  gh auth refresh -s project < /dev/tty
else
  echo "auth: gh is missing the 'project' scope and no terminal is available to" >&2
  echo "      grant it. Run this once in your shell, then re-run the recipe:" >&2
  echo "        gh auth refresh -s project" >&2
  exit 1
fi

# The board must already exist — run `scripts/gh-project.sh setup | bash` first.
NUM=$(gh project list --owner "$OWNER" -L 200 --format json \
  --jq ".projects[] | select(.title==\"$TITLE\") | .number")
[ -n "$NUM" ] || { echo "board '$TITLE' not found — run: scripts/gh-project.sh setup | bash" >&2; exit 1; }
PID=$(gh project list --owner "$OWNER" -L 200 --format json \
  --jq ".projects[] | select(.title==\"$TITLE\") | .id")

# Idempotent add: reuse the existing board item if this URL is already on the
# board, otherwise add it. (item-add on an already-added URL can duplicate, so
# we look it up first.)
ITEM=$(gh project item-list "$NUM" --owner "$OWNER" -L 500 --format json \
  --jq ".items[] | select(.content.url==\"$URL\") | .id")
if [ -z "$ITEM" ]; then
  ITEM=$(gh project item-add "$NUM" --owner "$OWNER" --url "$URL" --format json --jq '.id')
  CREATED=1
else
  CREATED=0
fi
[ -n "$ITEM" ] || { echo "could not add or find a board item for $URL" >&2; exit 1; }
echo "item $ITEM  ($URL)"

# Stage (single-select). With STAGE_IF_NEW=1 the stage is applied ONLY when we
# just created the board item, so a re-add — or an out-of-order opened/labeled
# run — can never clobber a Stage a human moved the card to; the initial Stage is
# bound to item creation, not to which event won the race. With STAGE_IF_NEW=0
# (an explicit --stage) it is always applied.
if [ -n "$STAGE" ] && { [ "$STAGE_IF_NEW" != "1" ] || [ "$CREATED" = "1" ]; }; then
  SF=$(gh project field-list "$NUM" --owner "$OWNER" -L 200 --format json \
    --jq ".fields[] | select(.name==\"$STAGE_FIELD\") | .id")
  OPT=$(gh project field-list "$NUM" --owner "$OWNER" -L 200 --format json \
    --jq ".fields[] | select(.name==\"$STAGE_FIELD\") | .options[] | select(.name==\"$STAGE\") | .id")
  [ -n "$OPT" ] || { echo "stage '$STAGE' is not an option of '$STAGE_FIELD'" >&2; exit 1; }
  gh project item-edit --id "$ITEM" --project-id "$PID" --field-id "$SF" --single-select-option-id "$OPT"
  echo "set $STAGE_FIELD = $STAGE"
elif [ -n "$STAGE" ]; then
  echo "item already on the board; leaving $STAGE_FIELD unchanged (--stage-if-new)"
fi

# Story points (number).
if [ -n "$POINTS" ]; then
  PF=$(gh project field-list "$NUM" --owner "$OWNER" -L 200 --format json \
    --jq ".fields[] | select(.name==\"$POINTS_FIELD\") | .id")
  gh project item-edit --id "$ITEM" --project-id "$PID" --field-id "$PF" --number "$POINTS"
  echo "set $POINTS_FIELD = $POINTS"
fi
EOF
}

# Parse + VALIDATE the add-item args, then emit the recipe. Validation matters
# because the values are substituted into the emitted recipe: the URL must be a
# real github issue/PR URL, the stage must be one the board actually has, and
# points must be numeric.
add_item_cli() {
  local url="" stage="" points="" stage_if_new="0"
  while [ $# -gt 0 ]; do
    case "$1" in
      --stage)
        [ -z "$stage" ] || die "add-item: use only one of --stage / --stage-if-new"
        [ $# -ge 2 ] || die "--stage requires a value"; stage="$2"; stage_if_new="0"; shift 2 ;;
      --stage-if-new)
        [ -z "$stage" ] || die "add-item: use only one of --stage / --stage-if-new"
        [ $# -ge 2 ] || die "--stage-if-new requires a value"; stage="$2"; stage_if_new="1"; shift 2 ;;
      --points) [ $# -ge 2 ] || die "--points requires a value"; points="$2"; shift 2 ;;
      --*)      die "add-item: unknown flag '$1'" ;;
      *)        [ -z "$url" ] || die "add-item: unexpected extra argument '$1'"; url="$1"; shift ;;
    esac
  done
  [ -n "$url" ] || die "add-item: an issue/PR URL is required"
  case "$url" in
    https://github.com/*/*/issues/[0-9]*|https://github.com/*/*/pull/[0-9]*) ;;
    *) die "add-item: '$url' is not a github issue/PR URL" ;;
  esac
  if [ -n "$stage" ]; then
    case ",$STAGE_OPTIONS," in
      *",$stage,"*) ;;
      *) die "add-item: stage '$stage' is not one of: $STAGE_OPTIONS" ;;
    esac
  fi
  if [ -n "$points" ]; then
    [ -n "$POINTS_FIELD" ] || die "add-item: board '$BOARD' has no Story points field; --points is not allowed"
    case "$points" in ''|*[!0-9]*) die "add-item: --points must be a non-negative integer" ;; esac
  fi
  emit_add_item "$url" "$stage" "$points" "$stage_if_new"
}

selftest() {
  local out
  out="$(emit_recipe)"
  [ -n "$out" ] || die "selftest: emitted an empty recipe"
  # The generated recipe must be valid, runnable bash (syntax-only check).
  bash -n <(printf '%s\n' "$out") || die "selftest: emitted recipe is not valid bash"
  # Spec substitution reached the recipe.
  grep -qF 'TITLE="print-bench autonomy"' <<<"$out" || die "selftest: project title not substituted"
  grep -qF 'OWNER="shaiss"' <<<"$out"               || die "selftest: owner not substituted"
  # The three provisioning steps are present with the verified gh syntax.
  grep -qF 'gh project create --owner "$OWNER" --title "$TITLE"' <<<"$out" \
    || die "selftest: board-create command missing"
  grep -qFe '--data-type NUMBER' <<<"$out"        || die "selftest: Story points NUMBER field missing"
  grep -qFe '--data-type SINGLE_SELECT' <<<"$out" || die "selftest: Stage single-select field missing"
  grep -qF 'Backlog,Ready,In progress,In review,Done' <<<"$out" \
    || die "selftest: stage options missing"
  grep -qF 'gh auth refresh -s project' <<<"$out" || die "selftest: project-scope refresh missing"
  # The refresh must be guarded so an env-var token (CI/automation) doesn't abort
  # the recipe under set -e (Vercel agent review on #164).
  grep -qF 'GH_TOKEN:-' <<<"$out" || die "selftest: env-token auth guard missing"
  # Idempotency guards are present (create-if-absent, not unconditional create).
  grep -qF 'if [ -z "$NUM" ]' <<<"$out" || die "selftest: board create is not guarded (not idempotent)"
  grep -qF 'field_absent' <<<"$out"     || die "selftest: field creates are not guarded (not idempotent)"
  # Negative control: a spec with an empty title must NOT emit a valid create —
  # proves the assertions above are actually checking substituted content.
  local saved="$PROJECT_TITLE" bad
  PROJECT_TITLE=""
  bad="$(emit_recipe)"
  PROJECT_TITLE="$saved"
  if grep -qF 'TITLE="print-bench autonomy"' <<<"$bad"; then
    die "selftest: title substitution is not spec-driven (negative control failed)"
  fi

  # ---- add-item: emit a valid, spec-driven, idempotent recipe --------------
  local add
  add="$("$SELF" add-item "https://github.com/shaiss/print-bench/issues/148" --stage Backlog --points 3)"
  bash -n <(printf '%s\n' "$add") || die "selftest: add-item recipe is not valid bash"
  grep -qF 'URL="https://github.com/shaiss/print-bench/issues/148"' <<<"$add" || die "selftest: add-item url not substituted"
  grep -qF 'STAGE="Backlog"' <<<"$add" || die "selftest: add-item stage not substituted"
  grep -qF 'POINTS="3"' <<<"$add"      || die "selftest: add-item points not substituted"
  grep -qF 'gh project item-add' <<<"$add"    || die "selftest: add-item item-add missing"
  grep -qF 'select(.content.url==' <<<"$add"  || die "selftest: add-item idempotent url lookup missing"
  grep -qFe '--single-select-option-id' <<<"$add" || die "selftest: add-item stage set missing"
  grep -qFe '--number "$POINTS"' <<<"$add"        || die "selftest: add-item points set missing"
  grep -qF 'STAGE_IF_NEW="0"' <<<"$add"           || die "selftest: --stage should emit STAGE_IF_NEW=0"
  # --stage-if-new: the stage is applied only when the item is newly created, so
  # the recipe carries STAGE_IF_NEW="1" and gates the set on $CREATED (the
  # opened/labeled race CodeRabbit flagged on #167).
  local addnew
  addnew="$("$SELF" add-item "https://github.com/shaiss/print-bench/issues/148" --stage-if-new Backlog)"
  bash -n <(printf '%s\n' "$addnew") || die "selftest: --stage-if-new recipe is not valid bash"
  grep -qF 'STAGE_IF_NEW="1"' <<<"$addnew"  || die "selftest: --stage-if-new flag not emitted"
  grep -qF '"$CREATED" = "1"' <<<"$addnew"  || die "selftest: --stage-if-new does not gate the set on item creation"
  # Negative controls (validation via the real CLI): a bad URL, an unknown stage,
  # non-numeric points, and both stage flags at once must each be refused.
  "$SELF" add-item "not-a-url" >/dev/null 2>&1 \
    && die "selftest: add-item accepted a non-URL" || true
  "$SELF" add-item "https://github.com/shaiss/print-bench/issues/1" --stage Nope >/dev/null 2>&1 \
    && die "selftest: add-item accepted an unknown stage" || true
  "$SELF" add-item "https://github.com/shaiss/print-bench/issues/1" --points x >/dev/null 2>&1 \
    && die "selftest: add-item accepted non-numeric points" || true
  "$SELF" add-item "https://github.com/shaiss/print-bench/issues/1" --stage Backlog --stage-if-new Ready >/dev/null 2>&1 \
    && die "selftest: add-item accepted both --stage and --stage-if-new" || true

  # ---- the growth board (a second spec through the same emitter) ------------
  # Provisioning recipe for --board growth: valid bash, its own title + stages,
  # and NO Story points field (the growth board does not estimate).
  select_board growth
  local grec
  grec="$(emit_recipe)"
  select_board autonomy
  bash -n <(printf '%s\n' "$grec") || die "selftest: growth setup recipe is not valid bash"
  grep -qF 'TITLE="print-bench growth"' <<<"$grec"       || die "selftest: growth board title not substituted"
  grep -qF 'Queued,Drafted,Approved,Posted,Parked,Attention' <<<"$grec" \
    || die "selftest: growth stage options missing"
  grep -qFe '--data-type NUMBER' <<<"$grec" \
    && die "selftest: growth board must not emit a Story points NUMBER field" || true
  grep -qFe '--data-type SINGLE_SELECT' <<<"$grec" || die "selftest: growth Stage single-select field missing"
  # add-item on the growth board: a growth Stage is accepted and substituted.
  local gadd
  gadd="$("$SELF" --board growth add-item "https://github.com/shaiss/print-bench/issues/1" --stage Approved)"
  bash -n <(printf '%s\n' "$gadd") || die "selftest: growth add-item recipe is not valid bash"
  grep -qF 'TITLE="print-bench growth"' <<<"$gadd" || die "selftest: growth add-item title not substituted"
  grep -qF 'STAGE="Approved"' <<<"$gadd"           || die "selftest: growth add-item stage not substituted"
  # Negative controls: an autonomy stage is not a growth stage; --points is
  # refused on a board with no points field; an unknown board is refused.
  "$SELF" --board growth add-item "https://github.com/shaiss/print-bench/issues/1" --stage Backlog >/dev/null 2>&1 \
    && die "selftest: growth add-item accepted a non-growth stage" || true
  "$SELF" --board growth add-item "https://github.com/shaiss/print-bench/issues/1" --stage Queued --points 3 >/dev/null 2>&1 \
    && die "selftest: growth add-item accepted --points on a board with no Story points field" || true
  "$SELF" --board nope setup >/dev/null 2>&1 \
    && die "selftest: accepted an unknown board name" || true

  echo "ok    gh-project.sh selftest passed"
}

# Parse the optional leading `--board <name>` global flag, then select the board
# spec so every subcommand (and the selftest) reads the right one. Callers that
# pass no --board get the default (autonomy), so existing invocations —
# roadmap-sync.yml's `add-item …` — are unchanged.
BOARD="$DEFAULT_BOARD"
if [ "${1:-}" = "--board" ]; then
  [ $# -ge 2 ] || die "--board requires a value"
  BOARD="$2"; shift 2
fi
select_board "$BOARD"

case "${1:-}" in
  setup)         emit_recipe ;;
  add-item)      shift; add_item_cli "$@" ;;
  # The whole suite starts from the autonomy board (its first assertions are the
  # autonomy recipe), then switches to growth itself — so reset here in case a
  # caller passed `--board growth --selftest`, which would otherwise fail those
  # opening assertions before reaching the growth checks.
  --selftest)    select_board autonomy; selftest ;;
  -h|--help|"")  grep '^#' "$SELF" | sed 's/^# \{0,1\}//' ;;
  *)             die "unknown argument: '$1' (try: [--board <name>] setup | add-item | --selftest | --help)" ;;
esac
