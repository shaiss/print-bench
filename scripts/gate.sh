#!/usr/bin/env bash
# Render each design's printable STL(s) and gate them with printcheck
# (tools/printcheck — pip install -e tools/printcheck).
#   ./scripts/gate.sh                  # gate all designs under designs/
#   ./scripts/gate.sh <name>...        # gate one or more designs
#   ./scripts/gate.sh --slice [<name>...] # additionally test-slice each gated
#                                      # STL with PrusaSlicer (ground truth:
#                                      # slicing errors fail the gate; slicer
#                                      # warnings and print time are surfaced)
#
# Per-design config, all optional:
#   designs/<name>/ci.parts        one `part` value per line; each renders as
#                                  build/<name>-<part>.stl via -D part="..."
#                                  (without it, <name>.scad renders as-is —
#                                  use it when the default render is an
#                                  assembled preview, not the printable part)
#   designs/<name>/printcheck.args extra printcheck flags, e.g.
#                                  --build-volume 256x256x256 for designs
#                                  that target a larger printer
#   designs/<name>/<name>-coupon.scad  "print this first" coupon wrapper;
#                                  rendered as build/<name>-coupon.stl and
#                                  gated like any other part
#   designs/<name>/ci.fitchecks    boolean fit checks between the design's
#                                  parts: `<part> empty` must render zero
#                                  facets, `<part> interferes` is the
#                                  mandatory negative control that must not
#                                  (proves the check can fail). Never
#                                  printchecked or sliced
#   designs/<name>/derives.conf    lineage of a derivative design: the
#                                  parent(s) it includes, the parent parts it
#                                  claims to replace, and any diamond-ok:
#                                  assertions (format: tools/lineage). Its
#                                  presence turns on derivative_gate below,
#                                  which proves each claimed override actually
#                                  changed the mesh and each base-safety claim
#                                  is true
set -euo pipefail

SLICE=0
names=()
for arg in "$@"; do
  case "$arg" in
    --slice) SLICE=1 ;;
    -*) echo "error: unknown flag $arg" >&2; exit 2 ;;
    *) names+=("$arg") ;;
  esac
done
if [[ "$SLICE" == 1 ]]; then
  command -v prusa-slicer >/dev/null || {
    echo "error: --slice needs prusa-slicer on PATH" >&2; exit 2; }
fi

cd "$(dirname "$0")/.."
mkdir -p build
# lib/ resolves `use <printability.scad>`; the repo root resolves
# `include <styles/<name>/style.scad>` (see scripts/style-lift.sh).
export OPENSCADPATH="$PWD/lib:$PWD"

# OPENSCAD_BIN selects the binary (e.g. openscad-nightly); OPENSCAD_ARGS
# passes extra flags (e.g. --backend=manifold — nightly-only, 2021.01 has
# no --backend). Both default to the stable invocation.
OPENSCAD_BIN="${OPENSCAD_BIN:-openscad}"
read -ra OSC_ARGS <<<"${OPENSCAD_ARGS:-}"

# Sourced, not re-implemented: lineage_render_binstl / lineage_mesh_hash /
# lineage_facet_count are the same functions `./scripts/lineage.sh selftest`
# exercises against known-good and known-broken fixtures, which is the only
# reason to believe derivative_gate below can still fire.
# shellcheck source=scripts/lineage.sh
source scripts/lineage.sh

fail=0

slice_one() {
  local stl="$1"
  local gcode="${stl%.stl}.gcode"
  echo "== test-slice ${stl} =="
  local out
  # --filament-density: without it PrusaSlicer emits "total filament used
  # [g] = 0.00" — the grams line the summary parses would silently read zero
  # for every part. 1.24 g/cm³ is PLA; the summary labels the assumption.
  if ! out=$(prusa-slicer --export-gcode -o "$gcode" \
      --layer-height 0.2 --nozzle-diameter 0.4 --filament-diameter 1.75 \
      --filament-density 1.24 \
      "$stl" 2>&1); then
    tail -20 <<<"$out"
    echo "FAIL  ${stl}: slicing failed"
    fail=1
    return 0
  fi
  grep -i "warning" <<<"$out" | sed 's/^/      /' || true
  grep -m1 "estimated printing time" "$gcode" | sed 's/^; */      /' || true
  grep -m1 "^; total filament used \[g\]" "$gcode" | sed 's/^; */      /' || true
}

# Derivative designs (those shipping a derives.conf) get two extra proofs.
# Both exist because OpenSCAD's override mechanism — `include <parent.scad>`,
# then redefine a module so the parent's own call sites route to your version —
# reports NOTHING when it fails to bind. Misspell the module you meant to
# replace and you get exit 0, no WARNING, no ERROR, and a watertight STL that
# printcheck scores 100/100: the parent's part, shipped under the derivative's
# name. The only difference between "override took" and "override was a typo"
# is the mesh itself, so the mesh is what gets compared.
#
# Every line printed here is machine-read by scripts/gate-summary.py into the
# sticky PR comment: keep the "<status>  derivative <name>: <kind> <subject> —
# <detail>" shape, and keep ` — ` out of <detail>, since that is the separator.
# Continuation lines are indented, which is what keeps the parser off them.
derivative_gate() {
  local name="$1"
  [[ -f "designs/${name}/derives.conf" ]] || return 0

  # A lineage check that quietly no-ops is the same failure class this gate was
  # built to catch, so an unrunnable CLI fails the design instead of skipping it.
  if [[ ! -x scripts/lineage.sh ]]; then
    echo "FAIL  derivative ${name}: derives.conf — scripts/lineage.sh is not executable, so no lineage claim can be checked"
    fail=1
    return 0
  fi

  echo "== ${name}: derivative checks =="
  # Its own directory rather than reusing build/<name>-<part>.stl: those are
  # written in whatever format the .stl extension implied, and a hash
  # comparison means nothing unless both sides came out of the same exporter.
  local outdir="build/.lineage"
  mkdir -p "$outdir"

  # claims counts what derives.conf actually asked to be proven and read_ok
  # records whether we managed to ask. Together they separate "this derivative
  # asserts nothing" — worth saying out loud, since a reader seeing a
  # derives.conf reasonably assumes the gate is holding it to something — from
  # "the assertions could not be read", which is a failure.
  local claims=0 read_ok=1

  local replaces parent part label slug dstl pstl dhash phash dfacets pfacets
  local dargs=()
  if ! replaces=$(./scripts/lineage.sh replaces "$name"); then
    echo "FAIL  derivative ${name}: derives.conf — reading its replaces: entries failed, see the lineage output above"
    read_ok=0
    fail=1
  else
    while IFS=$'\t' read -r parent part; do
      [[ -n "$parent" ]] || continue
      claims=$((claims + 1))
      label="${parent}:${part}"
      # An empty part means the parent's default render — no -D part= at all.
      if [[ -n "$part" ]]; then
        dargs=(-D "part=\"${part}\"")
        slug="$part"
      else
        dargs=()
        slug="default"
      fi
      if [[ ! -f "designs/${parent}/${parent}.scad" ]]; then
        echo "FAIL  derivative ${name}: override ${label} — designs/${parent}/${parent}.scad is missing, so there is no baseline to compare against"
        fail=1
        continue
      fi
      dstl="${outdir}/${name}--${slug}.stl"
      pstl="${outdir}/${parent}--${slug}.stl"
      if ! lineage_render_binstl "designs/${name}/${name}.scad" "$dstl" \
          ${dargs[@]+"${dargs[@]}"}; then
        echo "FAIL  derivative ${name}: override ${label} — the derivative's own render did not complete"
        fail=1
        continue
      fi
      if ! lineage_render_binstl "designs/${parent}/${parent}.scad" "$pstl" \
          ${dargs[@]+"${dargs[@]}"}; then
        echo "FAIL  derivative ${name}: override ${label} — the parent's render did not complete"
        fail=1
        continue
      fi
      # Tested rather than assigned bare. `x=$(cmd)` adopts cmd's status, and
      # under `set -e` a nonzero one aborts the whole run — which would let a
      # single unreadable export take down the gate for every design after it,
      # exactly the aggregate-and-continue discipline gate_one is built on.
      # lineage_mesh_hash exits nonzero only when a file exists but will not
      # parse as a binary STL; a missing file is the empty mesh and succeeds.
      if ! dhash=$(lineage_mesh_hash "$dstl"); then
        echo "FAIL  derivative ${name}: override ${label} — the derivative's export could not be read back, so the claim cannot be settled"
        fail=1
        continue
      fi
      if ! phash=$(lineage_mesh_hash "$pstl"); then
        echo "FAIL  derivative ${name}: override ${label} — the parent's export could not be read back, so the claim cannot be settled"
        fail=1
        continue
      fi
      dfacets=$(lineage_facet_count "$dstl") || dfacets="?"
      pfacets=$(lineage_facet_count "$pstl") || pfacets="?"
      # Emptiness is judged BEFORE difference, and is its own failure.
      #
      # An empty render hashes to a sentinel, and a sentinel is trivially
      # unequal to any real mesh — so folding this into the "differs" branch
      # would report `ok ... mesh differs from the parent (12 → 0 facets)` for a
      # derivative that produced no geometry whatsoever for the part it claims
      # to replace. Nothing else would catch it either: these exports live in
      # build/.lineage and are never printchecked, so an empty part ships behind
      # a green gate whose message asserts the opposite. A render that emitted
      # nothing is not evidence that a redefinition bound; it is evidence that
      # the derivative's dispatcher no longer handles this part, or that the
      # override replaced it with nothing.
      if [[ "$dfacets" == 0 ]]; then
        echo "FAIL  derivative ${name}: override ${label} — the derivative renders no geometry at all for a part it claims to replace"
        printf '      %s\n' \
          "The parent renders ${pfacets} facets here and the derivative renders none," \
          "which is not an override taking effect — it is the part going missing." \
          "Usually the derivative redefined the part's module with an empty body, or" \
          "redefined the dispatcher so this part value no longer reaches any geometry." \
          "If the part genuinely should not exist in this design, drop it from" \
          "replaces: rather than shipping an empty STL under its name."
        fail=1
      elif [[ "$dhash" == "$phash" ]]; then
        echo "FAIL  derivative ${name}: override ${label} — the override did not take, the mesh is identical to the parent's"
        printf '      %s\n' \
          "Both sides hash to ${dhash}." \
          "That is what a redefinition binding nothing looks like from the outside:" \
          "OpenSCAD never mentions an override that matched no existing name, so the" \
          "part renders, slices and scores exactly as the parent's does." \
          "Check the module or variable designs/${name}/${name}.scad redefines against" \
          "the spelling in designs/${parent}/${parent}.scad, check the include line" \
          "actually names ${parent}, and check the redefinition sits after that include."
        fail=1
      else
        echo "ok    derivative ${name}: override ${label} — mesh differs from the parent (${pfacets} → ${dfacets} facets)"
      fi
    done <<<"$replaces"
  fi

  # diamond-ok: is a claim, not a fact. `include` is not guarded, so a diamond
  # evaluates the shared ancestor twice and unions its top-level geometry in
  # twice — cleanly, watertight, invisible to printcheck. The claim is only
  # true if the ancestor's entry point emits no geometry at all, and that is
  # cheap to check, so it gets checked rather than believed.
  local required ancestor astl facets
  if ! required=$(./scripts/lineage.sh base-safe-required "$name"); then
    echo "FAIL  derivative ${name}: derives.conf — reading its diamond-ok: entries failed, see the lineage output above"
    read_ok=0
    fail=1
  else
    while read -r ancestor; do
      [[ -n "$ancestor" ]] || continue
      claims=$((claims + 1))
      if [[ ! -f "designs/${ancestor}/${ancestor}.scad" ]]; then
        echo "FAIL  derivative ${name}: base-safe ${ancestor} — designs/${ancestor}/${ancestor}.scad is missing, so the claim cannot be proven"
        fail=1
        continue
      fi
      # Every configuration the ancestor can ship in, not just the default
      # render. A `part`-dispatching entry point — which is the multi-part
      # convention this repo recommends — emits nothing at all under its
      # default `part` value and geometry under the others, so proving only
      # the default proves nothing: the diamond still doubles whatever
      # `-D part=...` draws. Measured: an ancestor whose top level is
      # `if (part=="tray") tray();` passes a default-only proof while a
      # diamond over it echo-counts its top level firing twice under
      # `-D part="tray"`.
      local cfgs=("") cfg cfgargs cfglabel bad=0
      if [[ -f "designs/${ancestor}/ci.parts" ]]; then
        while read -r cfg || [[ -n "$cfg" ]]; do
          [[ -z "$cfg" || "$cfg" == \#* ]] && continue
          cfgs+=("$cfg")
        done < "designs/${ancestor}/ci.parts"
      fi
      for cfg in "${cfgs[@]}"; do
        cfgargs=()
        cfglabel="default render"
        if [[ -n "$cfg" ]]; then
          cfgargs=(-D "part=\"${cfg}\"")
          cfglabel="part=${cfg}"
        fi
        astl="${outdir}/${ancestor}--base-safe-${cfg:-default}.stl"
        if ! lineage_render_binstl "designs/${ancestor}/${ancestor}.scad" "$astl" \
            ${cfgargs[@]+"${cfgargs[@]}"}; then
          echo "FAIL  derivative ${name}: base-safe ${ancestor} — its ${cfglabel} did not render, so the claim cannot be proven"
          fail=1
          bad=1
          continue
        fi
        if ! facets=$(lineage_facet_count "$astl"); then
          echo "FAIL  derivative ${name}: base-safe ${ancestor} — its ${cfglabel} could not be read back, so the claim cannot be proven"
          fail=1
          bad=1
          continue
        fi
        [[ "$facets" == 0 ]] && continue
        bad=1
        fail=1
        echo "FAIL  derivative ${name}: base-safe ${ancestor} — its ${cfglabel} emits ${facets} facets, so the diamond-ok claim is false"
        printf '      %s\n' \
          "Anything ${ancestor}'s top level draws lands in this design twice, and the" \
          "duplicate unions cleanly enough that no downstream check can see it." \
          "Split designs/${ancestor}/${ancestor}.scad into a geometry-free module" \
          "library plus a thin dispatcher that calls it, then re-assert diamond-ok." \
          "Guarding the top-level geometry behind a part value is not enough: the" \
          "diamond doubles whatever that value renders, and this proof checks them all."
      done
      if [[ "$bad" == 0 ]]; then
        echo "ok    derivative ${name}: base-safe ${ancestor} — emits no geometry in any of its ${#cfgs[@]} configuration(s)"
      fi
    done <<<"$required"
  fi

  if (( read_ok && claims == 0 )); then
    echo "ok    derivative ${name}: derives.conf — records lineage only, with no replaces: or diamond-ok: entries for the gate to prove"
  fi
}

# Failures inside gate_one set fail=1 and keep going (matching how the
# printcheck step already aggregates) so one broken design never hides the
# results of the designs after it — gate_one always returns 0.
gate_one() {
  local name="$1"
  # Wall time for the whole of gate_one — render, printcheck, slice and the
  # derivative checks. The line shape is machine-read by scripts/telemetry.sh
  # (capture); gate-summary.py's patterns cannot match it, so the sticky PR
  # comment is unaffected. Keep the "time  <name>: gated in <N>s" shape.
  local gate_t0="$SECONDS"
  local src="designs/${name}/${name}.scad"
  if [[ ! -f "$src" ]]; then
    echo "FAIL  ${name}: ${src} not found"
    fail=1
    return 0
  fi

  local stls=()
  if [[ -f "designs/${name}/ci.parts" ]]; then
    local part
    # `|| [[ -n "$part" ]]`: without it a ci.parts whose last line has no
    # trailing newline loses that part from the gate entirely.
    while read -r part || [[ -n "$part" ]]; do
      [[ -z "$part" || "$part" == \#* ]] && continue
      local stl="build/${name}-${part}.stl"
      echo "== ${name} (part=${part}): render =="
      if ! xvfb-run -a "$OPENSCAD_BIN" ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
          -o "$stl" -D "part=\"${part}\"" "$src"; then
        echo "FAIL  ${name} (part=${part}): render failed"
        fail=1
        continue
      fi
      stls+=("$stl")
    done < "designs/${name}/ci.parts"
  else
    echo "== ${name}: render =="
    # No early return on failure. Returning here skipped derivative_gate at the
    # end of this function, so a derivative whose default render broke produced
    # no derivative section at all — and "no section" is exactly what a
    # derivative with nothing to prove also looks like, in the log and in the
    # PR comment. The run is red either way, but the reader cannot tell which
    # of the two happened, which is the ambiguity this whole gate exists to
    # remove. (The ci.parts branch above already `continue`s for this reason.)
    if ! xvfb-run -a "$OPENSCAD_BIN" ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
        -o "build/${name}.stl" "$src"; then
      echo "FAIL  ${name}: render failed"
      fail=1
    else
      stls+=("build/${name}.stl")
    fi
  fi

  # "Print this first" coupon wrapper (repo convention, see CLAUDE.md): a
  # ≤10-line include-and-override wrapper on the production modules. It is
  # the first STL a user prints, so it gets the same printcheck + test-slice
  # treatment as the parts it stands in for.
  local coupon="designs/${name}/${name}-coupon.scad"
  if [[ -f "$coupon" ]]; then
    local coupon_stl="build/${name}-coupon.stl"
    echo "== ${name} (coupon): render =="
    if ! xvfb-run -a "$OPENSCAD_BIN" ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
        -o "$coupon_stl" "$coupon"; then
      echo "FAIL  ${name} (coupon): render failed"
      fail=1
    else
      stls+=("$coupon_stl")
    fi
  fi

  # Boolean fit checks (designs/<name>/ci.fitchecks): each line names a part
  # value that renders a boolean between the design's other parts, plus the
  # verdict its mesh must deliver — `empty` (zero facets: the parts clear) or
  # `interferes` (a deliberately broken pose that must produce facets). The
  # pair is mandatory: an empty render alone is a check that cannot fail
  # (designs/nuggs round 6.1 — the Nef crash made every "empty difference"
  # proof vacuous), so a manifest with no `interferes` control fails. These
  # parts are never printchecked or sliced: empty IS their success state.
  local fchecks="designs/${name}/ci.fitchecks"
  if [[ -f "$fchecks" ]]; then
    local fline fpart fexpect frest ffacets fstl n_controls=0 n_empty=0
    while IFS= read -r fline || [[ -n "$fline" ]]; do
      fline="${fline%%#*}"
      fpart="" fexpect="" frest=""
      read -r fpart fexpect frest <<<"$fline" || true
      [[ -z "$fpart" ]] && continue
      # Exactly two fields: a stray third word means the line is not saying
      # what its author thought, and a half-parsed check is worse than none.
      if [[ -z "$fexpect" || -n "$frest" ]]; then
        echo "FAIL  fitcheck ${name}: malformed line \"${fline}\" — expected exactly '<part> empty|interferes'"
        fail=1
        continue
      fi
      # The part must be a real DISPATCH selector in the entry .scad, not
      # merely a quoted string anywhere in it ("deepskyblue" is a quoted
      # string): a part value with no dispatch branch renders as nothing,
      # which `empty` would wave through forever — the typo IS a pass.
      if ! [[ "$fpart" =~ ^[A-Za-z0-9_-]+$ ]] \
         || ! grep -Eq "part[[:space:]]*==[[:space:]]*\"${fpart}\"" "$src"; then
        echo "FAIL  fitcheck ${name}: no 'part == \"${fpart}\"' dispatch branch in ${src} — a part with no branch renders empty and passes vacuously"
        fail=1
        continue
      fi
      fstl="build/${name}-${fpart}.stl"
      echo "== ${name} (fitcheck=${fpart}, expect ${fexpect}): render =="
      # lineage_render_binstl: binary STL (what lineage_facet_count parses),
      # clears stale output, and treats a cleanly-empty render as success
      # with no file — which facet-counts as 0. A real error still fails.
      if ! lineage_render_binstl "$src" "$fstl" -D "part=\"${fpart}\""; then
        echo "FAIL  ${name}: fitcheck ${fpart} render failed"
        fail=1
        continue
      fi
      ffacets="$(lineage_facet_count "$fstl")"
      case "$fexpect" in
        empty)
          n_empty=$((n_empty + 1))
          if [[ "$ffacets" -eq 0 ]]; then
            echo "ok    fitcheck ${name}: ${fpart} is empty — the parts clear"
          else
            echo "FAIL  fitcheck ${name}: ${fpart} produced ${ffacets} facets of interference"
            fail=1
          fi ;;
        interferes)
          n_controls=$((n_controls + 1))
          if [[ "$ffacets" -gt 0 ]]; then
            echo "ok    fitcheck ${name}: ${fpart} interferes as expected (${ffacets} facets) — the check can fail"
          else
            echo "FAIL  fitcheck ${name}: negative control ${fpart} came out empty — the fitcheck can no longer fail"
            fail=1
          fi ;;
        *)
          echo "FAIL  fitcheck ${name}: unknown expectation \"${fexpect}\" for ${fpart} (use empty | interferes)"
          fail=1 ;;
      esac
    done < "$fchecks"
    if [[ "$n_controls" -eq 0 ]]; then
      echo "FAIL  fitcheck ${name}: ci.fitchecks carries no \"interferes\" negative control — without one the empty checks are unfalsifiable"
      fail=1
    fi
    if [[ "$n_empty" -eq 0 ]]; then
      echo "FAIL  fitcheck ${name}: ci.fitchecks carries no \"empty\" check — a manifest of controls alone proves nothing about the fit it exists to gate"
      fail=1
    fi
  fi

  local args=()
  if [[ -f "designs/${name}/printcheck.args" ]]; then
    # Word-splitting the flag file is intended; `|| true` keeps set -e from
    # aborting on a comment-only file.
    # shellcheck disable=SC2207
    args=($(grep -vE '^(#|$)' "designs/${name}/printcheck.args" || true))
  fi
  local stl
  for stl in ${stls[@]+"${stls[@]}"}; do
    echo "== ${name}: printcheck ${stl} =="
    if ! printcheck "$stl" ${args[@]+"${args[@]}"}; then
      fail=1
    fi
    if [[ "$SLICE" == 1 ]]; then
      slice_one "$stl"
    fi
  done

  # Deterministic fuse check (designs/<name>/ci.fusecheck). A print-in-place
  # mechanism that welds shut still exports watertight and — for a living hinge —
  # as ONE connected body, so printcheck cannot see it; and a hand-written
  # interference fitcheck only sees the pose its author intersects, which can be
  # the wrong one (the first sweetheart-hamster shipped a fitcheck that tested
  # the CLOSED pose while CI sliced the FLAT pose, and missed a 1378-facet weld
  # at the hinge). fusecheck answers the un-mis-aimable question on the SLICED
  # STL, never a -D pose: remove the declared thin-flexure zone(s) and count the
  # separable bodies that remain — a living hinge that joins the halves only
  # through its flexure splits into 2, a large-area weld stays 1. Manifest lines
  # (coordinates in printcheck's rested frame — lowest point at z=0):
  #   flexure X0,Y0,Z0:X1,Y1,Z1     global, repeatable — faces whose centroid is
  #                                 inside are dropped before counting
  #   assert  <stl-basename> <min>  that sliced STL, minus the flexure zones,
  #                                 must split into >= <min> bodies
  #   control <part>         <max>  MANDATORY negative control: the KNOWN-FUSED
  #                                 pose (-D part="<part>", a real dispatch
  #                                 branch), same flexure zones, must stay <=<max>
  # A detected fuse (assert bodies < min) is a STRONG WARN, not a hard fail — the
  # reviewers (Jane/Drik) must consciously sign it off. A broken check is a hard
  # FAIL: no assert or no control (issue #37 — a check that cannot fail is
  # worthless), a malformed line, a control part with no dispatch branch, an
  # assert STL the gate never rendered (a fuse check on an unsliced part proves
  # nothing), or a control that no longer fuses (an over-large flexure AABB that
  # would mask a real fuse also splits the fused control, and is caught here).
  local fusef="designs/${name}/ci.fusecheck"
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
          if [[ -z "$uarg1" || -z "$uarg2" || -n "$urest" \
                || ! "$uarg2" =~ ^[0-9]+$ ]]; then
            echo "FAIL  fusecheck ${name}: malformed assert line \"${uline}\" — expected 'assert <stl-basename> <min_bodies>'"
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
          local ubodies
          if ! ubodies="$(python3 -m printcheck.fusecheck "$astl" \
                          ${fz_args[@]+"${fz_args[@]}"})"; then
            echo "FAIL  fusecheck ${name}: fusecheck failed on ${astl}"
            fail=1
            continue
          fi
          if [[ "$ubodies" -ge "$uarg2" ]]; then
            echo "ok    fusecheck ${name}: ${uarg1} splits into ${ubodies} bodies (>= ${uarg2}) once the flexure is removed — the mechanism separates"
          else
            echo "warn  fusecheck ${name}: ${uarg1} splits into only ${ubodies} body/bodies (< ${uarg2}) once the flexure is removed — likely FUSED; reviewer signoff required"
          fi ;;
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

  # Last, so the printcheck rows above stay one contiguous block in the log
  # and in the summary table. A no-op for every design without a derives.conf.
  derivative_gate "$name"

  echo "time  ${name}: gated in $((SECONDS - gate_t0))s"
}

if [[ ${#names[@]} -ge 1 ]]; then
  for name in "${names[@]}"; do
    gate_one "$name"
  done
else
  found=0
  archived=0
  for dir in designs/*/; do
    [[ -d "$dir" ]] || continue
    name="$(basename "$dir")"
    [[ -f "designs/${name}/${name}.scad" ]] || continue
    # A design frozen at v0.1 (designs/<name>/ARCHIVED) is retired from the
    # full-catalog gate — this no-args path is what CI runs on a main push
    # and on any infra change (gate_designs=ALL), so skipping here is what
    # stops a frozen design from spending render/slice cycles forever.
    # A caller that NAMES an archived design still gates it (the branch
    # above never reaches this loop). That is the revival path, and CI only
    # ever names an archived design when the PR edited its own files: the
    # `changes` classifier drops an archived design that was pulled in only
    # by blast radius or a shared style, so an indirect touch never lands here.
    if [[ -f "designs/${name}/ARCHIVED" ]]; then
      echo "skip ${name}: archived at $(head -1 "designs/${name}/ARCHIVED") — frozen, not gated in full-catalog runs"
      archived=$((archived + 1))
      continue
    fi
    found=1
    gate_one "$name"
  done
  if [[ "$found" -eq 0 ]]; then
    # Distinguish an empty tree from one where every design is archived, so a
    # green no-op reads honestly instead of looking like nothing exists.
    if [[ "$archived" -gt 0 ]]; then
      echo "no designs gated: all ${archived} design(s) under designs/ are archived at v0.1"
    else
      echo "no designs found under designs/"
    fi
  fi
fi

exit "$fail"
