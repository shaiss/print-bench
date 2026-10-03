#!/usr/bin/env bash
# Deterministic fuse check (designs/<name>/ci.fusecheck): the runner gate.sh
# calls, plus the shell-level selftest that proves the seam it owns.
#
#   ./scripts/fusecheck-check.sh <name> <src.scad> <manifest> [<stl>...]
#                                  # run one design's fusecheck manifest
#                                  # (gate.sh sources this file and calls
#                                  # fusecheck_gate with exactly these
#                                  # arguments — one parser, no copy)
#   ./scripts/fusecheck-check.sh --selftest
#                                  # prove the seam on the fixtures under
#                                  # scripts/fusecheck-fixtures/: render them,
#                                  # anchor their body counts with fusecheck
#                                  # itself, then drive the real runner over
#                                  # committed manifests whose expected
#                                  # verdicts cover the whole `assert` bound
#                                  # grammar — legacy `<min>`, two-sided
#                                  # `<min> <max>`, `=N` — plus the malformed
#                                  # line and the exit-4 hard-fail path, every
#                                  # negative row asserted to fire. Run by
#                                  # scripts/check.sh (issue #627).
#
# A print-in-place mechanism that welds shut still exports watertight and —
# for a living hinge — as ONE connected body, so printcheck cannot see it; and
# a hand-written interference fitcheck only sees the pose its author
# intersects, which can be the wrong one (the first sweetheart-hamster shipped
# a fitcheck that tested the CLOSED pose while CI sliced the FLAT pose, and
# missed a 1378-facet weld at the hinge). fusecheck answers the un-mis-aimable
# question on the SLICED STL, never a -D pose: remove the declared
# thin-flexure zone(s) and count the separable bodies that remain — a living
# hinge that joins the halves only through its flexure splits into 2, a
# large-area weld stays 1. Manifest lines (coordinates in printcheck's rested
# frame — lowest point at z=0):
#   flexure X0,Y0,Z0:X1,Y1,Z1     global, repeatable — faces whose centroid is
#                                 inside are dropped before counting
#   assert  <stl-basename> <min> [<max>]
#                                 that sliced STL, minus the flexure zones,
#                                 must split into >= <min> bodies — and, when
#                                 <max> is given, <= <max> (issue #612 part 2;
#                                 the sugar `assert <stl> =N` means min=max=N)
#   control <part>         <max>  MANDATORY negative control: the KNOWN-FUSED
#                                 pose (-D part="<part>", a real dispatch
#                                 branch), same flexure zones, must stay <=<max>
# A detected fuse (assert bodies < min) is a STRONG WARN, not a hard fail — the
# reviewers (Jane/Drik) must consciously sign it off. An EXTRA body (assert
# bodies > max) is the opposite defect and a hard FAIL: a freed counter island
# (a stencil "0" whose tether never printed) or a dropped part is not
# something a reviewer waves through. The bound's semantics live in
# `fusecheck --bound` (tools/printcheck, pytest-pinned), so the gate and a
# hand run cannot drift; this file only tokenises the line and words the
# verdict. A broken check is a hard FAIL: no assert or no control (issue #37
# — a check that cannot fail is worthless), a malformed line (a max below its
# min included), a control part with no dispatch branch, an assert STL the
# gate never rendered (a fuse check on an unsliced part proves nothing), or a
# control that no longer fuses (an over-large flexure AABB that would mask a
# real fuse also splits the fused control, and is caught here).
#
# WHY EXTRACTED: the read `assert <stl> <min> [<max>]` / `=N` tokenisation and
# the exit-3 (too few → WARN) / exit-4 (too many → FAIL) mapping used to live
# inline in gate.sh, where no test could reach it — every pytest and CI gate
# stayed green while the seam itself regressed. It now lives here as
# fusecheck_gate, which gate.sh SOURCES (the lineage.sh pattern — sourced, not
# re-implemented) and calls once per design; the selftest drives the same
# function over the fixtures, so a parser regression fails here first. The
# only line of the original block that changed is the first: the manifest
# path, hardcoded `designs/${name}/ci.fusecheck`, became the third parameter
# so the fixtures can hand their own manifests to the same parser.
#
# Failure is communicated by setting the CALLER's `fail` flag to 1 — the same
# global gate.sh aggregates — never by a return code; a function whose caller
# must also remember `|| fail=1` is a second way to forget the failure.
# fusecheck_gate therefore always returns 0 and `set -e` callers may call it
# bare.
#
# Output is the house style gate-summary.py and tools/telemetry already read:
# `ok    fusecheck <name>: …` / `warn  fusecheck <name>: …` /
# `FAIL  fusecheck <name>: …` — byte-identical to the lines the inline block
# used to emit.

# The runner. Callers must have `fail` defined (gate.sh does; the executed
# modes below set it) and, for a manifest with a `control` line,
# lineage_render_binstl on scope — source scripts/lineage.sh first, as gate.sh
# and the executed modes below do.
fusecheck_gate() {
  local name="$1" src="$2" fusef="$3"
  shift 3
  local stls=("$@")
  if [[ -f "$fusef" ]]; then
    local uline ukey uarg1 uarg2 urest
    local fz_args=() n_assert=0 n_control=0
    # First pass: collect the global flexure zones (an assert may precede the
    # flexure line that applies to it, so the zones must be gathered up front).
    while IFS= read -r uline || [[ -n "$uline" ]]; do
      uline="${uline%%#*}"
      ukey="" uarg1="" urest=""
      read -r ukey uarg1 urest <<<"$uline" || true
      [[ -z "$ukey" ]] && continue
      if [[ "$ukey" == "flexure" ]]; then
        if [[ -z "$uarg1" || -n "$urest" ]]; then
          echo "FAIL  fusecheck ${name}: malformed flexure line \"${uline}\" — expected 'flexure x0,y0,z0:x1,y1,z1'"
          fail=1
          continue
        fi
        fz_args+=("--ignore-aabb=${uarg1}")
      fi
    done < "$fusef"
    # Second pass: run the asserts and controls, applying the collected zones.
    while IFS= read -r uline || [[ -n "$uline" ]]; do
      uline="${uline%%#*}"
      ukey="" uarg1="" uarg2="" urest=""
      read -r ukey uarg1 uarg2 urest <<<"$uline" || true
      [[ -z "$ukey" ]] && continue
      case "$ukey" in
        flexure) : ;;   # gathered in the first pass
        assert)
          # Tokenise the bound: `<min>` (the legacy one-sided floor), `<min>
          # <max>` (two-sided) or `=N` (min = max = N). ubound is the spec
          # handed to `fusecheck --bound`; ulo/uhi/ubtext only word the lines.
          local ubound="" ulo="" uhi="" ubtext=""
          if [[ -n "$uarg1" && -n "$uarg2" ]]; then
            if [[ -z "$urest" && "$uarg2" =~ ^=([0-9]+)$ ]]; then
              ubound="$uarg2"; ulo="${BASH_REMATCH[1]}"; uhi="$ulo"; ubtext="= ${ulo}"
            elif [[ -z "$urest" && "$uarg2" =~ ^[0-9]+$ ]]; then
              ubound="$uarg2"; ulo="$uarg2"; ubtext=">= ${ulo}"
            elif [[ "$uarg2" =~ ^[0-9]+$ && "$urest" =~ ^[0-9]+$ \
                    && "$urest" -ge "$uarg2" ]]; then
              ubound="${uarg2}:${urest}"; ulo="$uarg2"; uhi="$urest"; ubtext="${ulo}..${uhi}"
            fi
          fi
          if [[ -z "$ubound" ]]; then
            echo "FAIL  fusecheck ${name}: malformed assert line \"${uline}\" — expected 'assert <stl-basename> <min_bodies> [<max_bodies>]' (max >= min) or 'assert <stl-basename> =N'"
            fail=1
            continue
          fi
          n_assert=$((n_assert + 1))
          local astl="build/${uarg1}" matched=0 s
          for s in ${stls[@]+"${stls[@]}"}; do
            if [[ "$s" == "$astl" ]]; then matched=1; break; fi
          done
          if [[ "$matched" -eq 0 ]]; then
            echo "FAIL  fusecheck ${name}: assert names ${uarg1}, which the gate never rendered — a fuse check on an unsliced STL proves nothing"
            fail=1
            continue
          fi
          # fusecheck prints the count and carries the verdict in its exit
          # code: 0 within the bound, 3 below min (the fuse), 4 above max (an
          # extra body), anything else a measurement error.
          local ubodies urc=0
          ubodies="$(python3 -m printcheck.fusecheck "$astl" --bound "$ubound" \
                     ${fz_args[@]+"${fz_args[@]}"})" || urc=$?
          case "$urc" in
            0)
              if [[ -z "$uhi" ]]; then
                # One-sided: the line every existing manifest already emits.
                echo "ok    fusecheck ${name}: ${uarg1} splits into ${ubodies} bodies (>= ${ulo}) once the flexure is removed — the mechanism separates"
              else
                echo "ok    fusecheck ${name}: ${uarg1} splits into ${ubodies} bodies (${ubtext}) once the flexure is removed — the mechanism separates and nothing came loose"
              fi ;;
            3)
              echo "warn  fusecheck ${name}: ${uarg1} splits into only ${ubodies} body/bodies (< ${ulo}) once the flexure is removed — likely FUSED; reviewer signoff required" ;;
            4)
              echo "FAIL  fusecheck ${name}: ${uarg1} splits into ${ubodies} bodies (> ${uhi}; bound ${ubtext}) once the flexure is removed — extra body = freed island / dropped part; a body nothing holds is a defect, not a signoff"
              fail=1 ;;
            *)
              echo "FAIL  fusecheck ${name}: fusecheck failed on ${astl}"
              fail=1 ;;
          esac ;;
        control)
          if [[ -z "$uarg1" || -z "$uarg2" || -n "$urest" \
                || ! "$uarg2" =~ ^[0-9]+$ ]]; then
            echo "FAIL  fusecheck ${name}: malformed control line \"${uline}\" — expected 'control <part> <max_bodies>'"
            fail=1
            continue
          fi
          # The part must be a real DISPATCH selector, not merely a quoted
          # string somewhere in the file — a part with no branch renders empty,
          # counts 0 bodies, and would satisfy any <max> vacuously.
          if ! [[ "$uarg1" =~ ^[A-Za-z0-9_-]+$ ]] \
             || ! grep -Eq "part[[:space:]]*==[[:space:]]*\"${uarg1}\"" "$src"; then
            echo "FAIL  fusecheck ${name}: no 'part == \"${uarg1}\"' dispatch branch in ${src} — a control with no branch renders empty and can never fuse"
            fail=1
            continue
          fi
          n_control=$((n_control + 1))
          local cstl="build/${name}-${uarg1}.stl"
          echo "== ${name} (fusecheck control=${uarg1}): render =="
          if ! lineage_render_binstl "$src" "$cstl" -D "part=\"${uarg1}\""; then
            echo "FAIL  fusecheck ${name}: control ${uarg1} render failed"
            fail=1
            continue
          fi
          local cbodies
          if ! cbodies="$(python3 -m printcheck.fusecheck "$cstl" \
                          ${fz_args[@]+"${fz_args[@]}"})"; then
            echo "FAIL  fusecheck ${name}: fusecheck failed on control ${cstl}"
            fail=1
            continue
          fi
          if [[ "$cbodies" -le "$uarg2" ]]; then
            echo "ok    fusecheck ${name}: control ${uarg1} stays ${cbodies} body/bodies (<= ${uarg2}) — the known-fused pose still reads fused, so the check can fire"
          else
            echo "FAIL  fusecheck ${name}: control ${uarg1} split into ${cbodies} bodies (> ${uarg2}) — the negative control no longer fuses (flexure AABB too large?); the fuse check is unfalsifiable"
            fail=1
          fi ;;
        *)
          echo "FAIL  fusecheck ${name}: unknown key \"${ukey}\" in \"${uline}\" — use flexure | assert | control"
          fail=1 ;;
      esac
    done < "$fusef"
    if [[ "$n_assert" -eq 0 ]]; then
      echo "FAIL  fusecheck ${name}: ci.fusecheck names no 'assert' — a manifest that never checks a sliced part proves nothing about the fit it exists to gate"
      fail=1
    fi
    if [[ "$n_control" -eq 0 ]]; then
      echo "FAIL  fusecheck ${name}: ci.fusecheck carries no 'control' negative case — without a known-fused pose the fuse check is unfalsifiable"
      fail=1
    fi
  fi
  return 0
}

# The selftest (scripts/fusecheck-check.sh --selftest, run by check.sh).
# Renders the fixture design's two poses, re-measures their body counts with
# fusecheck itself (AC1 — the manifests' expectations are anchored to measured
# geometry, not to what the harness reports), then drives the REAL runner over
# each committed fixture manifest and asserts every expected verdict fires —
# ok rows, the WARN row, the hard-FAIL row, the malformed rows — and that the
# run-level fail flag lands where the contract says (WARN never fails the run;
# exit 4 never escapes as a WARN).
fusecheck_selftest() {
  local fxdir="scripts/fusecheck-fixtures"
  local fxscad="${fxdir}/fixtures.scad"
  local label="fusecheck-fixtures"
  local scratch="build/.fusecheck-selftest"
  # The assert lines name build/-relative basenames, so the fixture renders
  # land in build/ under the label (the same build/ the gate renders into).
  local sep="build/${label}-separable.stl"
  local fus="build/${label}-fused.stl"
  local stls=("$sep" "$fus")
  mkdir -p "$scratch"

  if ! python3 -c 'import printcheck' 2>/dev/null; then
    echo "FAIL  fusecheck selftest: printcheck not importable — pip install -e tools/printcheck (the gate's fusecheck pass needs it too; CI installs it in every job that runs check.sh)" >&2
    return 1
  fi

  echo "== fusecheck selftest: render fixtures =="
  local p stl
  for p in separable fused; do
    stl="build/${label}-${p}.stl"
    if ! lineage_render_binstl "$fxscad" "$stl" -D "part=\"${p}\""; then
      echo "FAIL  fusecheck selftest: fixture render failed: ${p}"
      return 1
    fi
  done

  # AC1: measure, don't assume. If these numbers move, the manifests below
  # are lying — fix the fixtures or the manifests, never the expectation.
  local nsep nfus
  nsep="$(python3 -m printcheck.fusecheck "$sep")" || {
    echo "FAIL  fusecheck selftest: fusecheck could not count ${sep}"
    return 1
  }
  nfus="$(python3 -m printcheck.fusecheck "$fus")" || {
    echo "FAIL  fusecheck selftest: fusecheck could not count ${fus}"
    return 1
  }
  if [[ "$nsep" != "2" || "$nfus" != "1" ]]; then
    echo "FAIL  fusecheck selftest: measured body counts are separable=${nsep} (manifests expect 2), fused=${nfus} (manifests expect 1) — the fixture geometry drifted from its manifests"
    return 1
  fi
  echo "ok    fusecheck selftest: measured bodies — separable=${nsep}, fused=${nfus}"

  # Drive one fixture manifest through the REAL runner. No subshell: the
  # output goes to a file and the fail flag is read after the call returns.
  local mf out ffail
  run_fx() {
    mf="$1"
    out="${scratch}/$(basename "$mf").log"
    fail=0
    fusecheck_gate "$label" "$fxscad" "$mf" "${stls[@]}" > "$out" 2>&1
    ffail="$fail"
  }
  # Expectation helpers — the negative controls of this selftest: a missing
  # verdict line is exactly the silent green issue #627 files, so each miss
  # dumps the whole log and fails the run.
  local missed=0
  expect() {   # expect <what> <grep -E pattern>
    if ! grep -Eq "$2" "$out"; then
      echo "FAIL  fusecheck selftest [$(basename "$mf")]: expected ${1} — no line matches: ${2}"
      sed 's/^/      | /' "$out"
      missed=1
    fi
  }
  refuse() {   # refuse <what> <grep -E pattern>
    if grep -Eq "$2" "$out"; then
      echo "FAIL  fusecheck selftest [$(basename "$mf")]: did not expect ${1} — a line matches: ${2}"
      sed 's/^/      | /' "$out"
      missed=1
    fi
  }
  expect_flag() {   # expect_flag <expected 0|1>
    if [[ "$ffail" != "$1" ]]; then
      echo "FAIL  fusecheck selftest [$(basename "$mf")]: expected run fail flag=${1}, got ${ffail}"
      missed=1
    fi
  }

  # --- legacy one-sided floor (AC2 pass side) + the =N sugar (AC4) --------
  run_fx "${fxdir}/pass-legacy.fusecheck"
  expect "the legacy one-sided row to pass" \
    '^ok    fusecheck .*separable\.stl splits into 2 bodies \(>= 2\)'
  expect "the =N exact row to pass" \
    '^ok    fusecheck .*separable\.stl splits into 2 bodies \(= 2\)'
  refuse "any WARN (nothing fused here)" '^warn  fusecheck'
  refuse "any FAIL" '^FAIL'
  expect_flag 0

  # --- legacy floor on the FUSED part: WARN, run continues (AC2 WARN side,
  # and AC6 direction 1 — exit 3 is never a hard FAIL) ---------------------
  run_fx "${fxdir}/warn-legacy.fusecheck"
  expect "the too-few row to WARN" \
    '^warn  fusecheck .*fused\.stl splits into only 1 body/bodies \(< 2\)'
  refuse "any FAIL (exit 3 must never hard-fail)" '^FAIL'
  expect_flag 0

  # --- two-sided MIN MAX, count inside the bound (AC3 pass side) ----------
  run_fx "${fxdir}/pass-twosided.fusecheck"
  expect "the two-sided row to pass inside the bound" \
    '^ok    fusecheck .*separable\.stl splits into 2 bodies \(2\.\.2\)'
  refuse "any WARN" '^warn  fusecheck'
  refuse "any FAIL" '^FAIL'
  expect_flag 0

  # --- count ABOVE the two-sided max: hard FAIL, never a WARN (AC3 FAIL
  # side, the issue's exit-4 path, and AC6 direction 2) --------------------
  run_fx "${fxdir}/fail-abovemax.fusecheck"
  expect "the too-many row to hard-FAIL" \
    '^FAIL  fusecheck .*separable\.stl splits into 2 bodies \(> 1; bound 1\.\.1\)'
  refuse "any WARN (exit 4 must never downgrade)" '^warn  fusecheck'
  expect_flag 1

  # --- malformed bounds: the LINE fails the parse (AC5) --------------------
  run_fx "${fxdir}/fail-malformed.fusecheck"
  expect "the max-below-min line to FAIL the parse" \
    '^FAIL  fusecheck .*malformed assert line .*separable\.stl 2 1'
  expect "the non-numeric line to FAIL the parse" \
    '^FAIL  fusecheck .*malformed assert line .*separable\.stl 2 x'
  expect_flag 1

  if [[ "$missed" -ne 0 ]]; then
    echo "FAIL  fusecheck selftest: ${missed} expectation(s) missed — see the dumped logs above"
    return 1
  fi
  echo "ok    fusecheck selftest: every bound-grammar row and negative control fired"
  return 0
}

# Sourced vs executed: gate.sh wants definitions only — it owns OPENSCADPATH,
# lineage_render_binstl (via scripts/lineage.sh, sourced first) and the fail
# flag. The executed modes set those up themselves.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  set -euo pipefail
  cd "$(dirname "$0")/.."
  # lib/ resolves `use <printability.scad>`; the repo root resolves
  # `include <styles/<name>/style.scad>` — the same export gate.sh makes.
  export OPENSCADPATH="$PWD/lib:$PWD"
  # lineage_render_binstl (the control render: binary STL, empty-is-success,
  # warnings surfaced), the same helper gate.sh sources.
  # shellcheck source=scripts/lineage.sh
  source scripts/lineage.sh

  usage() {
    echo "usage: scripts/fusecheck-check.sh <name> <src.scad> <manifest> [<stl>...]" >&2
    echo "       scripts/fusecheck-check.sh --selftest" >&2
  }

  case "${1:-}" in
    --selftest)
      shift
      fusecheck_selftest
      ;;
    -h|--help)
      usage
      ;;
    "")
      usage
      exit 2
      ;;
    *)
      # One manifest, the same arguments gate.sh passes. fusecheck_gate
      # reports through the fail flag and always returns 0.
      fail=0
      fusecheck_gate "$@"
      [[ "$fail" -eq 0 ]]
      ;;
  esac
fi
