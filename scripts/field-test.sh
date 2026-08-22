#!/usr/bin/env bash
# Append a FIELD-TEST entry to a design's NOTES.md (issue #101). This is the
# formatting-and-file half of the "Log a print result" GitHub Action
# (.github/workflows/log-print-result.yml) — kept in a script, not buried in
# workflow YAML, so it is testable: `--selftest` is run by scripts/check.sh.
#
# Usage:
#   scripts/field-test.sh --design <name> --printer <p> --result <r> \
#       [--printed-from <version>] [--settings <s>] [--deviations <d>] \
#       [--carry <c>] [--parts <what>] [--date <YYYY-MM-DD>]
#   scripts/field-test.sh --selftest
#
# --printed-from anchors the print to the design version/commit it came from
# (e.g. "v0.2"), so a result is traceable to the exact geometry that produced
# it — the design→print→iterate lineage.
#
# Required: --design, --printer, --result. The design must exist
# (designs/<name>/<name>.scad). The "## Field test log" section is created at
# the end of NOTES.md when absent; entries append to the end, so keep that
# section last (see templates/FIELD-TEST.md and docs/print-feedback.md).
#
# --notes-file <path> overrides the resolved NOTES.md (used by --selftest);
# with it, --design is not required and no design lookup happens.
set -euo pipefail

# Absolute path to this script, captured before the cd below so --selftest can
# re-invoke the real CLI end-to-end.
SELF="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)/$(basename "$0")"
cd "$(dirname "$0")/.."

die() { echo "field-test: $*" >&2; exit 1; }

# Guard a value-taking option: called as `need_val "$@"` from inside the parse
# loop, it fails cleanly when a flag is the final argv token with no value,
# rather than expanding an unset $2 into a raw "unbound variable" under set -u.
need_val() { [ "$#" -ge 2 ] || die "$1 requires a value"; }

# One entry block on stdout. Unset optional fields render as an em dash (or
# "none" for carry-forward) so the shape is always complete.
format_entry() {  # date printer printed_from parts settings result deviations carry
  printf '### %s — %s\n' "$1" "$2"
  printf -- '- **Printed from:** %s\n' "${3:-—}"
  printf -- '- **Part(s):** %s\n' "${4:-—}"
  printf -- '- **Slicer settings:** %s\n' "${5:-—}"
  printf -- '- **Result:** %s\n' "$6"
  printf -- '- **Measured deviations:** %s\n' "${7:-—}"
  printf -- '- **Carry forward:** %s\n' "${8:-none}"
}

# Append an entry to a NOTES.md. When the "## Field test log" section is absent,
# create it at the end of the file. When it already exists, insert the entry at
# the END of that section — immediately before the next level-2 heading, or at
# EOF if the section is last — so an entry is never misfiled outside the section
# when the log is not the last thing in the file (Copilot review on #110). The
# convention still asks for the section to be kept last; this just stops the
# tool from placing an entry in the wrong place when it is not.
append_entry() {  # notes date printer printed_from parts settings result deviations carry
  local notes="$1"; shift
  [ -f "$notes" ] || die "no such NOTES.md: $notes"
  local entry; entry="$(format_entry "$@")"

  # Anchored match, the same predicate the awk below uses: a heading that only
  # CONTAINS "## Field test log" (e.g. "## Field test log notes") must not count
  # as the section here, or we would skip creating it and then fail to insert —
  # a silent no-op (CodeRabbit/Qodo review on #110).
  if ! grep -qE '^## Field test log[[:space:]]*$' "$notes"; then
    {
      printf '\n## Field test log\n\n'
      printf '_Real prints of this design, newest at the bottom. See '
      printf 'templates/FIELD-TEST.md and docs/print-feedback.md._\n'
      printf '\n%s\n' "$entry"
    } >> "$notes"
    return
  fi

  # Insert into the existing section. A level-3 "### " entry header never
  # matches "^## ", so only a real level-2 heading after the log ends it.
  local tmp; tmp="$(mktemp)"
  awk -v entry="$entry" '
    /^## Field test log[[:space:]]*$/ { print; in_sec=1; next }
    in_sec && /^## / && !inserted { printf "\n%s\n\n", entry; inserted=1; in_sec=0 }
    { print }
    END { if (in_sec && !inserted) printf "\n%s\n", entry }
  ' "$notes" > "$tmp"
  mv "$tmp" "$notes"
}

# Validate a design name (path safety) and that it exists.
validate_design() {  # name
  [[ "$1" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "invalid design name: '$1'"
  [ -f "designs/$1/$1.scad" ] || die "no such design: designs/$1/$1.scad"
}

selftest() {
  local tmp notes rc out headers entries
  tmp="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap "rm -rf '$tmp'" RETURN
  notes="$tmp/NOTES.md"
  printf '# demo\n\n## Goal\nx\n' > "$notes"

  # 1. First entry creates the section and lands the fields.
  "$SELF" --notes-file "$notes" --printer "Bambu A1" \
    --result "slot fit snug" --deviations "slot 0.15 mm tight" \
    --printed-from v0.2 --date 2026-01-02 >/dev/null || die "selftest: first append failed"
  grep -qF '## Field test log' "$notes" || die "selftest: section not created"
  grep -qF '### 2026-01-02 — Bambu A1' "$notes" || die "selftest: entry header missing"
  grep -qF 'slot 0.15 mm tight' "$notes" || die "selftest: deviations not written"
  grep -qF '**Printed from:** v0.2' "$notes" || die "selftest: printed-from not written"

  # 2. Second entry reuses the one section and adds a second entry.
  "$SELF" --notes-file "$notes" --printer "Prusa MK4" \
    --result "loose" --date 2026-01-03 >/dev/null || die "selftest: second append failed"
  headers="$(grep -cF '## Field test log' "$notes")"
  [ "$headers" = 1 ] || die "selftest: expected exactly one section header, got $headers"
  entries="$(grep -cE '^### ' "$notes")"
  [ "$entries" = 2 ] || die "selftest: expected two entries, got $entries"

  # 3. Missing required field is refused.
  rc=0; out="$("$SELF" --notes-file "$notes" --printer p 2>&1)" || rc=$?
  [ "$rc" -ne 0 ] || die "selftest: missing --result was accepted"
  grep -qi 'result' <<<"$out" || die "selftest: missing-result message unclear: $out"

  # 4. An invalid design name is refused (path safety).
  rc=0; "$SELF" --design "../etc" --printer p --result r >/dev/null 2>&1 || rc=$?
  [ "$rc" -ne 0 ] || die "selftest: invalid design name was accepted"

  # 5. A nonexistent design is refused.
  rc=0; "$SELF" --design no-such-design-xyz --printer p --result r >/dev/null 2>&1 || rc=$?
  [ "$rc" -ne 0 ] || die "selftest: nonexistent design was accepted"

  # 6. When the log is NOT the last section, the entry lands INSIDE it (before
  #    the following heading), not at EOF (Copilot review on #110).
  printf '# d\n\n## Field test log\n\n_intro_\n\n### 2026-01-01 — old\n\n## Later section\n\ntail\n' > "$notes"
  "$SELF" --notes-file "$notes" --printer "Ender 3" --result "ok" --date 2026-02-02 >/dev/null \
    || die "selftest: append into a non-last section failed"
  awk '/^### 2026-02-02 — Ender 3/{seen=1} /^## Later section/{if(!seen) exit 1}' "$notes" \
    || die "selftest: entry was placed after a later section instead of inside the log"
  grep -qF 'tail' "$notes" || die "selftest: content after the section was lost"

  # 7. A heading that only CONTAINS "## Field test log" (trailing text) is not
  #    the section: a proper section is created and the entry is not lost — the
  #    existence grep and the insertion awk must agree (review on #110).
  printf '# d\n\n## Field test log notes\n\nunrelated\n' > "$notes"
  "$SELF" --notes-file "$notes" --printer "X1C" --result "ok" --date 2026-04-04 >/dev/null \
    || die "selftest: append against a look-alike heading failed"
  grep -qF '### 2026-04-04 — X1C' "$notes" || die "selftest: entry lost against a look-alike heading"
  grep -qE '^## Field test log[[:space:]]*$' "$notes" || die "selftest: exact section not created"

  # 8. A value-taking flag with no value fails cleanly, not with a raw bash
  #    "unbound variable" under set -u (review on #110).
  rc=0; out="$("$SELF" --notes-file "$notes" --printer 2>&1)" || rc=$?
  [ "$rc" -ne 0 ] || die "selftest: --printer with no value was accepted"
  grep -qi 'requires a value' <<<"$out" || die "selftest: missing-value message unclear: $out"

  echo "ok    field-test.sh selftest passed"
}

# --- argument parsing -------------------------------------------------------
design="" printer="" result="" settings="" deviations="" carry="" parts=""
printed_from="" date="" notes_override=""
while [ $# -gt 0 ]; do
  case "$1" in
    --selftest)    selftest; exit 0 ;;
    --design)      need_val "$@"; design="$2"; shift 2 ;;
    --printer)     need_val "$@"; printer="$2"; shift 2 ;;
    --printed-from) need_val "$@"; printed_from="$2"; shift 2 ;;
    --result)      need_val "$@"; result="$2"; shift 2 ;;
    --settings)    need_val "$@"; settings="$2"; shift 2 ;;
    --deviations)  need_val "$@"; deviations="$2"; shift 2 ;;
    --carry)       need_val "$@"; carry="$2"; shift 2 ;;
    --parts)       need_val "$@"; parts="$2"; shift 2 ;;
    --date)        need_val "$@"; date="$2"; shift 2 ;;
    --notes-file)  need_val "$@"; notes_override="$2"; shift 2 ;;
    -h|--help)     grep '^#' "$SELF" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)             die "unknown argument: $1" ;;
  esac
done

[ -n "$printer" ] || die "--printer is required"
[ -n "$result" ]  || die "--result is required"
[ -n "$date" ]    || date="$(date -u +%F)"

if [ -n "$notes_override" ]; then
  notes="$notes_override"
else
  [ -n "$design" ] || die "--design is required"
  validate_design "$design"
  notes="designs/$design/NOTES.md"
fi

append_entry "$notes" "$date" "$printer" "$printed_from" "$parts" "$settings" \
  "$result" "$deviations" "$carry"
echo "field-test: appended a ${date} entry to $notes"
