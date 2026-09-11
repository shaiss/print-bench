#!/usr/bin/env bash
# Kinematics verification gate (issue #607): SWEPT fitchecks. A design authors
# boolean parts exactly like ci.fitchecks (a `part` dispatch branch whose mesh
# is the interference, the engagement, or a probe), and this gate renders each
# one at every step of a parameter sweep — or at every declared landing stop —
# and counts facets. Two design questions become gateable this way:
#
#   ROTATIONAL MESH   a gear pair rendered at N phases across one mesh cycle
#                     must show zero interference (gearA ∩ gearB empty) AND
#                     never separate (gearA grown by a small clearance ∩ gearB
#                     non-empty) at EVERY phase. A pair that clears at phase 0
#                     and jams at phase 3/8 is a pair that jams.
#   INDEX / LANDING   at each declared stop the presenting face is the declared
#                     shape and within tolerance of reader-upright (posed shell
#                     ∩ the complement of a tolerance wedge → empty) and its
#                     numeral is not rolled or mirrored (posed numeral cutter ∩
#                     an upright template → non-empty).
#
#   ./scripts/kinematics-check.sh <src.scad> <manifest> [<label>]
#                                  # run one manifest; gate.sh calls this for
#                                  # designs/<name>/<name>.scad + ci.kinematics
#   ./scripts/kinematics-check.sh --selftest
#                                  # prove the gate on the fixtures under
#                                  # scripts/kinematics-fixtures/: every
#                                  # positive row passes, every negative
#                                  # control fires. Run by scripts/check.sh.
#
# Manifest (designs/<name>/ci.kinematics), one directive per line, `#` comments:
#
#   steps <n>                   sweep resolution for later sweep-mode checks
#                               (default 12, 2..64) — budget lives here: every
#                               `empty`/`nonempty` line costs <n> CGAL renders
#   sweep <param>               enter SWEEP mode: <param> is -D'd over [0,1)
#                               as k/<n>, k = 0..<n>-1 (1 is never rendered —
#                               a cycle-periodic parameter repeats 0 there)
#   stops <param> <v1,v2,...>   enter STOPS mode: later checks evaluate at
#                               exactly these <param> values instead
#   empty <part>                must render 0 facets at EVERY step/stop
#   nonempty <part>             must render >0 facets at EVERY step/stop
#   empty-control <part>        MUST show >0 facets at SOME step/stop (a pair
#                               that jams, a face that mis-lands) — mandatory
#                               whenever an `empty` check exists, else FAIL:
#                               the empty checks are unfalsifiable
#   nonempty-control <part>     MUST show 0 facets at SOME step/stop (a pair
#                               that gaps out, a mirrored numeral) — mandatory
#                               whenever a `nonempty` check exists
#
# Every check evaluates in whichever mode (sweep or stops, with the current
# `steps`) was declared most recently above it; a check before any `sweep` or
# `stops` line is malformed. The swept/stepped parameter must be a plain
# top-level variable of the entry .scad (the -D override replaces its
# assignment, exactly like `part`), and the gate CHECKS that it is — an
# assignment `<param> = …` at the start of a line of the entry file itself,
# comments stripped — because a -D of a name the source never assigns binds
# nothing and OpenSCAD says nothing: the geometry sits at one pose and every
# check holds at every value (`sweep kin_phse` is a green gate over one
# frame). Never sweep `$t` — top-level assignments evaluate before a -D'd
# special variable lands (see animations.conf). A `stops` list is capped at
# KIN_MAX_STEPS values, the same cap `steps` carries: the render budget is
# bounded either way. A manifest is validated whole — syntax, the parameter,
# dispatch branches, the mandatory controls — BEFORE the first render, so a
# typo never burns render minutes and a structurally unfalsifiable manifest
# fails without measuring anything. The renders then fail fast: an `empty`
# check stops at the first step that shows facets, a control stops at the
# first step that satisfies it (usually the first — a control is cheap by
# construction).
#
# Facets, not exit codes, and the same helpers as gate.sh's fitcheck block and
# mate-check.sh: lineage_render_binstl turns OpenSCAD's "Current top level
# object is empty" exit 1 into the success it is here, and lineage_facet_count
# reads the binary STL (absent file = 0). A part whose name has no
# `part == "<part>"` dispatch branch in the source renders empty and would
# pass `empty` forever — the typo IS a pass — so the branch is required, the
# way ci.fitchecks requires it. The source is grepped with its `//` and
# `/* */` comments stripped (kin_strip_comments), so a branch that exists only
# in the header prose, or a part name quoted in a comment, cannot satisfy it;
# the same stripped text is what the parameter check above reads.
#
# WRONG-GEOMETRY WARNINGS fail the check. lineage_render_binstl returns
# success on a render whose only complaint is a WARNING, and on the
# cleanly-empty path it prints nothing at all — so a checked part whose
# module is misspelled, or whose include is missing, renders EMPTY and passes
# `empty` with a mesh that is not the design's. This gate asks the helper for
# the full render log (LINEAGE_RENDER_LOG, its optional out-parameter) and
# fails a check whose log carries a `WARNING: Ignoring unknown …` (module,
# function, variable) or `WARNING: Can't open …` (include file, `use` library)
# line: the class scripts/check.sh's FATAL_WARN names as "silently produced
# the WRONG SHAPE", plus the two siblings only an instantiating render can
# reach. Every other WARNING (2-manifold, deprecation) stays advisory, exactly
# as in check.sh. gate.sh's fitcheck block and mate-check.sh render through
# the same helper and do not check this today — the same exposure, noted
# here so the two rules can be aligned rather than discovered.
#
# Output is the house style gate-summary.py and tools/telemetry already read:
# `ok    kinematics <label>: …` / `FAIL  kinematics <label>: …` (no summary
# shape claims these, exactly like fitcheck lines), a wrong-geometry warning
# is `FAIL  kinematics <label>: <part> render emitted a wrong-geometry
# warning: <first warning line>`, and a render failure is reported as
# `FAIL  <label> (kinematics <part> at <param>=<v>): render failed` — the
# `FAIL  <design> (part=<part>): render failed` shape gate.sh uses for a
# part render, which the summary's "failed before printcheck ran" list
# (regex `FAIL\s+(.+: (?:render failed|\S+ not found))$`, the same one in
# tools/telemetry) collects: the `: ` must sit right before `render failed`.
set -euo pipefail

cd "$(dirname "$0")/.."
export OPENSCADPATH="$PWD/lib:$PWD"

# lineage_render_binstl (empty-vs-broken) and lineage_facet_count. Sourcing is
# safe: everything above lineage.sh's bottom guard is a definition.
# shellcheck source=scripts/lineage.sh
source ./scripts/lineage.sh

KIN_DEFAULT_STEPS=12
KIN_MAX_STEPS=64
KIN_OUT="build/.kinematics"
# The render-log lines that mean the mesh is not the design's (see the
# header): check.sh's FATAL_WARN class, widened to the two siblings a real
# render can also hit ("unknown variable", "Can't open library").
KIN_WRONG_GEOMETRY_WARN="^WARNING: (Ignoring unknown|Can't open)"

trim() { local s="$1"; s="${s#"${s%%[![:space:]]*}"}"; printf '%s' "${s%"${s##*[![:space:]]}"}"; }

# The source with every `//` and `/* */` comment removed, line structure
# kept, so a grep for a dispatch branch or a top-level assignment can only
# match code. POSIX awk, one pass: a `/*` opens a block that swallows text
# (across lines) up to the next `*/`; a `//` outside a block drops the rest
# of its line. A `//` inside a string literal is cut too (an http:// in an
# echo) — the check gets stricter on that line, never looser, the safe
# direction for a gate.
kin_strip_comments() {
  awk '
    {
      line = $0; out = ""
      while (length(line) > 0) {
        if (inblk) {
          i = index(line, "*/")
          if (i == 0) { line = ""; break }
          line = substr(line, i + 2); inblk = 0
        } else {
          b = index(line, "/*"); l = index(line, "//")
          if (b == 0 && l == 0) { out = out line; line = ""; break }
          if (l > 0 && (b == 0 || l < b)) { out = out substr(line, 1, l - 1); line = ""; break }
          out = out substr(line, 1, b - 1); line = substr(line, b + 2); inblk = 1
        }
      }
      print out
    }' "$1"
}

# Does the comment-stripped source ($1) assign <name> ($2) at the start of a
# line — `name = …`, not `name == …`? That is the top-level assignment a -D
# replaces; anything else (an include's variable, a module parameter, a typo)
# leaves the -D binding nothing.
kin_declares_var() {
  grep -Eq "^[[:space:]]*${2}[[:space:]]*=([^=]|$)" <<<"$1"
}

# Run one manifest against one source. Prints the ok/FAIL lines, returns 0
# when every check and control behaved as declared, 1 otherwise. Globals are
# not touched — the selftest runs this in a subshell per row.
kin_run() {
  local src="$1" manifest="$2"
  local label="${3:-$(basename "$manifest")}"
  local fail=0

  if [[ ! -f "$src" ]]; then
    echo "FAIL  kinematics ${label}: source ${src} not found"
    return 1
  fi
  if [[ ! -f "$manifest" ]]; then
    echo "FAIL  kinematics ${label}: manifest ${manifest} not found"
    return 1
  fi
  # Every grep against the source below reads this, never the raw file.
  local stripped
  stripped="$(kin_strip_comments "$src")"

  # ---- pass 1: parse + validate the whole manifest before any render ----
  # Each accepted check becomes one record "verb|part|mode|param|values"
  # where values is a space-separated list of -D values.
  local checks=()
  local mode="" param="" values="" steps="$KIN_DEFAULT_STEPS"
  local n_empty=0 n_nonempty=0 n_ectl=0 n_nctl=0
  local line verb a b rest
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="$(trim "${line%%#*}")"
    [[ -z "$line" ]] && continue
    verb="" a="" b="" rest=""
    read -r verb a b rest <<<"$line" || true
    case "$verb" in
      steps)
        if [[ -z "$a" || -n "$b" || ! "$a" =~ ^[0-9]+$ \
              || "$a" -lt 2 || "$a" -gt "$KIN_MAX_STEPS" ]]; then
          echo "FAIL  kinematics ${label}: malformed line \"${line}\" — expected 'steps <n>' with 2 <= n <= ${KIN_MAX_STEPS}"
          fail=1
          continue
        fi
        steps="$a" ;;
      sweep)
        if [[ -z "$a" || -n "$b" || ! "$a" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
          echo "FAIL  kinematics ${label}: malformed line \"${line}\" — expected 'sweep <param>'"
          fail=1
          continue
        fi
        # The name must be an assignment the -D can replace: a -D of a name
        # the source never assigns binds nothing, silently, and every check
        # then holds at every value over one unmoving pose. The mode is still
        # entered so the checks below are validated in this same pass.
        if ! kin_declares_var "$stripped" "$a"; then
          echo "FAIL  kinematics ${label}: sweep parameter \"${a}\" is not a top-level variable of ${src} — a -D of a name the source never assigns binds nothing, so the geometry would sit at one pose and every check would pass vacuously"
          fail=1
        fi
        mode="sweep" param="$a" values="" ;;
      stops)
        if [[ -z "$a" || -z "$b" || -n "$rest" || ! "$a" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
          echo "FAIL  kinematics ${label}: malformed line \"${line}\" — expected 'stops <param> <v1,v2,...>'"
          fail=1
          continue
        fi
        local v ok=1 vals="" vals_arr
        IFS=',' read -ra vals_arr <<<"$b"
        # The same cap as `steps`: the render budget of a manifest is bounded
        # per check either way, and an unbounded list is a typo'd paste.
        if (( ${#vals_arr[@]} > KIN_MAX_STEPS )); then
          echo "FAIL  kinematics ${label}: malformed line \"${line}\" — stops carries ${#vals_arr[@]} values, at most ${KIN_MAX_STEPS} allowed (KIN_MAX_STEPS, the same cap as 'steps')"
          fail=1
          continue
        fi
        for v in "${vals_arr[@]}"; do
          if [[ ! "$v" =~ ^-?[0-9]+(\.[0-9]+)?$ ]]; then ok=0; break; fi
          vals+="${vals:+ }${v}"
        done
        if [[ "$ok" -eq 0 || -z "$vals" ]]; then
          echo "FAIL  kinematics ${label}: malformed line \"${line}\" — stops values must be comma-separated numbers"
          fail=1
          continue
        fi
        # Same rule and same reason as `sweep` above.
        if ! kin_declares_var "$stripped" "$a"; then
          echo "FAIL  kinematics ${label}: stops parameter \"${a}\" is not a top-level variable of ${src} — a -D of a name the source never assigns binds nothing, so the geometry would sit at one pose and every check would pass vacuously"
          fail=1
        fi
        mode="stops" param="$a" values="$vals" ;;
      empty|nonempty|empty-control|nonempty-control)
        if [[ -z "$a" || -n "$b" ]]; then
          echo "FAIL  kinematics ${label}: malformed line \"${line}\" — expected '${verb} <part>'"
          fail=1
          continue
        fi
        if [[ -z "$mode" ]]; then
          echo "FAIL  kinematics ${label}: '${verb} ${a}' has no sweep or stops declared before it — nothing says what to evaluate it over"
          fail=1
          continue
        fi
        # A real DISPATCH selector in the source, as ci.fitchecks demands: a
        # part with no branch renders empty and passes `empty` vacuously.
        # Grepped with comments stripped, so a branch that exists only in
        # the header prose cannot satisfy it.
        if ! [[ "$a" =~ ^[A-Za-z0-9_-]+$ ]] \
           || ! grep -Eq "part[[:space:]]*==[[:space:]]*\"${a}\"" <<<"$stripped"; then
          echo "FAIL  kinematics ${label}: no 'part == \"${a}\"' dispatch branch in ${src} — a part with no branch renders empty and passes vacuously"
          fail=1
          continue
        fi
        local vlist="$values"
        if [[ "$mode" == "sweep" ]]; then
          local k
          vlist=""
          for ((k = 0; k < steps; k++)); do vlist+="${vlist:+ }${k}/${steps}"; done
        fi
        case "$verb" in
          empty) n_empty=$((n_empty + 1)) ;;
          nonempty) n_nonempty=$((n_nonempty + 1)) ;;
          empty-control) n_ectl=$((n_ectl + 1)) ;;
          nonempty-control) n_nctl=$((n_nctl + 1)) ;;
        esac
        checks+=("${verb}|${a}|${mode}|${param}|${vlist}") ;;
      *)
        echo "FAIL  kinematics ${label}: unknown directive \"${verb}\" in \"${line}\" — use steps | sweep | stops | empty | nonempty | empty-control | nonempty-control"
        fail=1 ;;
    esac
  done < "$manifest"

  # Both directions are load-bearing (issue #37, the fitcheck rule): a check
  # with no control is one that cannot fail, and controls alone check nothing.
  if (( n_empty + n_nonempty == 0 )); then
    echo "FAIL  kinematics ${label}: manifest carries no 'empty' or 'nonempty' check — a manifest of controls alone proves nothing about the mechanism it exists to gate"
    fail=1
  fi
  if (( n_empty > 0 && n_ectl == 0 )); then
    echo "FAIL  kinematics ${label}: manifest carries 'empty' checks but no 'empty-control' — without a pose that must interfere they are unfalsifiable"
    fail=1
  fi
  if (( n_nonempty > 0 && n_nctl == 0 )); then
    echo "FAIL  kinematics ${label}: manifest carries 'nonempty' checks but no 'nonempty-control' — without a pose that must gap out they are unfalsifiable"
    fail=1
  fi
  if (( fail )); then
    echo "FAIL  kinematics ${label}: manifest rejected before rendering — fix the lines above"
    return 1
  fi

  # ---- pass 2: render and count ----
  mkdir -p "$KIN_OUT"
  local rec vpart vmode vparam vlist renders=0
  local -a vals
  for rec in "${checks[@]}"; do
    IFS='|' read -r verb vpart vmode vparam vlist <<<"$rec"
    read -ra vals <<<"$vlist"
    local total="${#vals[@]}" unit="steps" i v facets stl logf warn verdict=""
    [[ "$vmode" == "stops" ]] && unit="stops"
    stl="${KIN_OUT}/${label}-${vpart}.stl"
    logf="${KIN_OUT}/${label}-${vpart}.log"
    for ((i = 0; i < total; i++)); do
      v="${vals[$i]}"
      renders=$((renders + 1))
      # LINEAGE_RENDER_LOG is the helper's optional out-parameter: OpenSCAD's
      # full output lands in $logf on every path, so the WARNING test below
      # sees the cleanly-empty render the helper reports as a silent success.
      if ! LINEAGE_RENDER_LOG="$logf" lineage_render_binstl "$src" "$stl" -D "part=\"${vpart}\"" -D "${vparam}=${v}"; then
        echo "FAIL  ${label} (kinematics ${vpart} at ${vparam}=${v}): render failed"
        echo "      (${unit%s} $((i + 1))/${total})"
        verdict="render-failed"
        break
      fi
      warn="$(grep -E -m1 "$KIN_WRONG_GEOMETRY_WARN" "$logf" || true)"
      if [[ -n "$warn" ]]; then
        echo "FAIL  kinematics ${label}: ${vpart} render emitted a wrong-geometry warning: ${warn}"
        echo "      (${vparam}=${v}, ${unit%s} $((i + 1))/${total}) — the mesh it left behind is not the design's, so it is not measured"
        verdict="wrong-geometry"
        break
      fi
      facets="$(lineage_facet_count "$stl")" || facets=unreadable
      if [[ "$facets" == unreadable ]]; then
        echo "FAIL  kinematics ${label}: ${vpart} at ${vparam}=${v} did not parse as a binary STL — a harness/render fault, not a measurement"
        verdict="unreadable"
        break
      fi
      case "$verb" in
        empty)
          if [[ "$facets" -ne 0 ]]; then
            echo "FAIL  kinematics ${label}: ${vpart} produced ${facets} facets at ${vparam}=${v} (${unit%s} $((i + 1))/${total}) — expected empty at every ${unit%s}"
            verdict="failed"
            break
          fi ;;
        nonempty)
          if [[ "$facets" -eq 0 ]]; then
            echo "FAIL  kinematics ${label}: ${vpart} came out empty at ${vparam}=${v} (${unit%s} $((i + 1))/${total}) — expected non-empty at every ${unit%s}"
            verdict="failed"
            break
          fi ;;
        empty-control)
          if [[ "$facets" -ne 0 ]]; then
            echo "ok    kinematics ${label}: empty-control ${vpart} shows ${facets} facets at ${vparam}=${v} — the empty checks can fail"
            verdict="fired"
            break
          fi ;;
        nonempty-control)
          if [[ "$facets" -eq 0 ]]; then
            echo "ok    kinematics ${label}: nonempty-control ${vpart} comes out empty at ${vparam}=${v} — the non-empty checks can fail"
            verdict="fired"
            break
          fi ;;
      esac
    done
    case "${verb}:${verdict}" in
      empty:)
        echo "ok    kinematics ${label}: ${vpart} is empty at all ${total} ${unit} of ${vparam}" ;;
      nonempty:)
        echo "ok    kinematics ${label}: ${vpart} is non-empty at all ${total} ${unit} of ${vparam}" ;;
      empty-control:)
        echo "FAIL  kinematics ${label}: empty-control ${vpart} stayed empty at all ${total} ${unit} of ${vparam} — the empty checks are unfalsifiable"
        fail=1 ;;
      nonempty-control:)
        echo "FAIL  kinematics ${label}: nonempty-control ${vpart} stayed non-empty at all ${total} ${unit} of ${vparam} — the non-empty checks are unfalsifiable"
        fail=1 ;;
      *:fired) : ;;
      *) fail=1 ;;
    esac
  done

  if (( fail == 0 )); then
    echo "ok    kinematics ${label}: $((n_empty + n_nonempty)) check(s) and $((n_ectl + n_nctl)) control(s) behave as declared over ${renders} render(s)"
  fi
  return "$fail"
}

# Prove the gate on its own fixtures: every positive row must pass with the
# expected ok lines, every negative row must FAIL with the specific line its
# control exists to produce. A gate that has never fired looks exactly like
# one that cannot, and each of these rows is one failure mode it must see.
# Fixture manifests are named <fixture>.<case>.kinematics and run against
# scripts/kinematics-fixtures/<fixture>.scad.
kin_selftest() {
  local fx="scripts/kinematics-fixtures"
  local rc=0
  # Row: manifest | pass|fail | expected output substrings, ';;'-separated.
  local rows=(
    # -- the rotational-mesh gate on a BOSL2 spur pair, one full mesh cycle --
    "gears.kinematics|pass|mesh-clear is empty at all 8 steps of kin_phase;;mesh-engaged is non-empty at all 8 steps of kin_phase;;empty-control mesh-jam shows;;nonempty-control mesh-gap comes out empty;;2 check(s) and 2 control(s) behave as declared"
    "gears.neg-jam-as-empty.kinematics|fail|mesh-jam produced"
    "gears.neg-gap-as-nonempty.kinematics|fail|mesh-gap came out empty"
    # -- the landing-pose gate on the pentagon shell, five stops --
    "landing.kinematics|pass|landing-flat is empty at all 5 stops of stop;;landing-flat-in-tol is empty at all 5 stops of stop;;landing-glyph is non-empty at all 5 stops of stop;;landing-glyph-cover is empty at all 5 stops of stop;;empty-control landing-flat-rolled shows;;empty-control landing-glyph-cover-mirrored shows;;nonempty-control landing-glyph-mirrored comes out empty;;nonempty-control landing-glyph-rolled comes out empty;;4 check(s) and 4 control(s) behave as declared"
    "landing.neg-rolled-as-flat.kinematics|fail|landing-flat-rolled produced"
    "landing.neg-mirrored-as-upright.kinematics|fail|landing-glyph-mirrored came out empty"
    "landing.neg-cover-mirrored-as-empty.kinematics|fail|landing-glyph-cover-mirrored produced"
    # -- controls that cannot fire --
    "landing.neg-dead-empty-control.kinematics|fail|empty-control landing-flat stayed empty at all 2 stops"
    "landing.neg-dead-nonempty-control.kinematics|fail|nonempty-control landing-glyph stayed non-empty at all 2 stops"
    # -- structural refusals, all before any render --
    "landing.neg-unfalsifiable-empty.kinematics|fail|no 'empty-control'"
    "landing.neg-unfalsifiable-nonempty.kinematics|fail|no 'nonempty-control'"
    "landing.neg-no-check.kinematics|fail|no 'empty' or 'nonempty' check"
    "landing.neg-no-dispatch.kinematics|fail|no 'part == \"landing-nope\"' dispatch branch"
    "broken.neg-comment-dispatch.kinematics|fail|no 'part == \"broken-in-line-comment\"' dispatch branch;;no 'part == \"broken-in-block-comment\"' dispatch branch"
    "landing.neg-bad-param.kinematics|fail|sweep parameter \"sotp\" is not a top-level variable of;;stops parameter \"sto\" is not a top-level variable of"
    "landing.neg-too-many-stops.kinematics|fail|stops carries 65 values, at most 64 allowed"
    "landing.neg-check-before-sweep.kinematics|fail|has no sweep or stops declared before it"
    "landing.neg-malformed.kinematics|fail|expected 'steps <n>';;expected 'sweep <param>';;stops values must be comma-separated numbers;;expected 'empty <part>';;unknown directive \"frobnicate\""
    # -- render faults the gate must report, never measure --
    "broken.neg-render-failed.kinematics|fail|(kinematics broken-assert at stop=0): render failed"
    "broken.neg-wrong-geometry.kinematics|fail|broken-unknown-module render emitted a wrong-geometry warning: WARNING: Ignoring unknown module 'no_such_module'"
  )
  local row mf expect subs label src out st sub missing
  for row in "${rows[@]}"; do
    IFS='|' read -r mf expect subs <<<"$row"
    label="${mf%.kinematics}"
    src="${fx}/${mf%%.*}.scad"
    if [[ ! -f "$src" || ! -f "${fx}/${mf}" ]]; then
      echo "FAIL  selftest: fixture ${src} or ${fx}/${mf} is missing"
      rc=1
      continue
    fi
    st=0
    out="$(kin_run "$src" "${fx}/${mf}" "$label" 2>&1)" || st=$?
    missing=""
    while IFS= read -r sub || [[ -n "$sub" ]]; do
      [[ -z "$sub" ]] && continue
      grep -qF -- "$sub" <<<"$out" || missing+="${missing:+, }\"${sub}\""
    done <<<"${subs//;;/$'\n'}"
    if [[ "$expect" == pass && "$st" -eq 0 && -z "$missing" ]]; then
      echo "ok    selftest: ${label} passes with every expected line"
    elif [[ "$expect" == fail && "$st" -ne 0 && -z "$missing" ]]; then
      echo "ok    selftest: ${label} fires — ${subs%%;;*}"
    else
      echo "FAIL  selftest: ${label} expected ${expect} (got exit ${st})${missing:+, missing ${missing}}"
      sed 's/^/      /' <<<"$out"
      rc=1
    fi
  done
  if (( rc == 0 )); then
    echo "ok    selftest: ${#rows[@]} kinematics rows behave as declared — the gate passes what it must and fires on every control"
  fi
  return "$rc"
}

case "${1:-}" in
  --selftest)
    [[ $# -eq 1 ]] || { echo "error: --selftest takes no arguments" >&2; exit 2; }
    rc=0
    kin_selftest || rc=$?
    exit "$rc" ;;
  -h|--help|"")
    sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
    exit 2 ;;
  -*)
    echo "error: unknown flag $1" >&2; exit 2 ;;
  *)
    [[ $# -ge 2 && $# -le 3 ]] || { echo "usage: $0 <src.scad> <manifest> [<label>]  |  --selftest" >&2; exit 2; }
    rc=0
    kin_run "$1" "$2" "${3:-}" || rc=$?
    exit "$rc" ;;
esac
