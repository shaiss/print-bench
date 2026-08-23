#!/usr/bin/env bash
# plate.sh — build the multi-object 3MF "print plate" deliverable for a
# multi-part design, and gate that it imports as N separate objects.
#
# The problem this exists for (field test, issue: multi-part fuse): a design
# whose parts print SEPARATELY (a wall boss + a screw-on collar) has no single
# sliceable file. STL carries no object separation, so the assembled/default
# render slices as ONE fused body — the user prints a welded lump. 3MF *does*
# carry multiple objects; PrusaSlicer's `--merge` packs N part STLs into one
# 3MF as N distinct objects a slicer imports as N parts. That multi-object 3MF
# is the printable deliverable; the assembled render stays a preview.
#
#   ./scripts/plate.sh <name>...        build build/<name>-plate.3mf for each
#   ./scripts/plate.sh --check <name>   build it and ASSERT object count == the
#                                       number of parts declared in ci.plate
#   ./scripts/plate.sh --selftest       prove the object counter discriminates
#                                       (separate parts -> N, a fused body -> 1)
#
# A multi-part design declares its plate in designs/<name>/ci.plate: one
# printable production part per line (each a value from ci.parts). Coupons,
# fit-proofs and the assembled preview are NOT plate parts. The plate is
# exactly those parts, merged as distinct objects.
#
# Reuses build/<name>-<part>.stl when present (gate.sh renders them first, so
# the gate adds a merge, not a re-render); renders any missing part on demand.
set -euo pipefail

MODE="build"   # build | check | selftest
names=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) MODE="check" ;;
    --selftest) MODE="selftest" ;;
    --) shift; break ;;
    -*) echo "plate.sh: unknown flag $1" >&2; exit 2 ;;
    *) names+=("$1") ;;
  esac
  shift
done
names+=("$@")

command -v prusa-slicer >/dev/null || {
  echo "error: plate.sh needs prusa-slicer on PATH (the --merge --export-3mf path)" >&2
  exit 2; }

export OPENSCADPATH="${OPENSCADPATH:-$PWD/lib:$PWD}"
OPENSCAD_BIN="${OPENSCAD_BIN:-openscad}"
# Word-splitting OPENSCAD_ARGS into an array is intended (same as gate.sh).
# shellcheck disable=SC2206
OSC_ARGS=(${OPENSCAD_ARGS:-})

# Count <object type="model"> entries in a 3MF (its 3D/3dmodel.model part).
# A 3MF built with `--merge` from N input files carries N such objects; a
# single fused body carries 1. This is the measurement the gate rests on.
plate_object_count() {
  python3 - "$1" <<'PY'
import sys, zipfile, re
try:
    with zipfile.ZipFile(sys.argv[1]) as z:
        xml = z.read("3D/3dmodel.model").decode("utf-8", "replace")
except Exception as e:
    print(f"ERR {e}", file=sys.stderr); sys.exit(3)
# <object ... type="model" ...> — the printable objects. A 3MF may also carry
# non-model objects (supports, modifiers); type="model" is the part count.
print(len(re.findall(r'<object\b[^>]*\btype="model"', xml)))
PY
}

# Build build/<name>-plate.3mf from the parts named in designs/<name>/ci.plate.
# Echoes the number of plate parts on success. Renders any missing part STL.
build_plate() {
  local name="$1"
  local manifest="designs/${name}/ci.plate"
  local src="designs/${name}/${name}.scad"
  [[ -f "$manifest" ]] || { echo "plate ${name}: no ci.plate manifest — nothing to build" >&2; return 4; }
  [[ -f "$src" ]] || { echo "plate ${name}: ${src} not found" >&2; return 4; }

  local parts=() part stls=()
  while read -r part || [[ -n "$part" ]]; do
    part="${part%%#*}"; part="${part//[[:space:]]/}"
    [[ -z "$part" ]] && continue
    parts+=("$part")
  done < "$manifest"

  if [[ "${#parts[@]}" -lt 2 ]]; then
    echo "FAIL  plate ${name}: ci.plate lists ${#parts[@]} part(s) — a plate is 2+ separately-printed parts as distinct objects (a single part needs no plate)" >&2
    return 5
  fi

  mkdir -p build
  for part in "${parts[@]}"; do
    local stl="build/${name}-${part}.stl"
    if [[ ! -f "$stl" ]]; then
      echo "== plate ${name} (part=${part}): render ==" >&2
      if ! xvfb-run -a "$OPENSCAD_BIN" ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
          -o "$stl" -D "part=\"${part}\"" "$src" >&2; then
        echo "FAIL  plate ${name}: part '${part}' failed to render" >&2
        return 5
      fi
    fi
    stls+=("$stl")
  done

  local out="build/${name}-plate.3mf"
  # --merge is MANDATORY: without it prusa-slicer exports each input to the
  # same path in turn, the last overwriting the rest (one object, not N).
  if ! prusa-slicer --merge --export-3mf --output "$out" "${stls[@]}" >&2; then
    echo "FAIL  plate ${name}: prusa-slicer --merge --export-3mf failed" >&2
    return 5
  fi
  echo "${#parts[@]}"
}

# build_plate + assert object count == part count. The whole gate.
check_plate() {
  local name="$1" n
  if ! n="$(build_plate "$name")"; then
    return 1
  fi
  local out="build/${name}-plate.3mf" got
  got="$(plate_object_count "$out")" || { echo "FAIL  plate ${name}: could not read ${out}"; return 1; }
  if [[ "$got" != "$n" ]]; then
    echo "FAIL  plate ${name}: ${out} imports as ${got} object(s), but ci.plate declares ${n} part(s) — the deliverable is not separable into its parts"
    return 1
  fi
  echo "ok    plate ${name}: build/${name}-plate.3mf — ${got} separate objects (== ${n} declared parts)"
  return 0
}

# Prove the object counter can both PASS (N separate parts -> N objects) and
# FAIL (a fused body -> 1 object, i.e. fewer than the parts it should hold).
# Without the failing half the check is worthless (issue #37).
selftest() {
  local t; t="$(mktemp -d)"; trap 'rm -rf "$t"' RETURN
  # two disjoint unit cubes, each its own STL
  printf 'cube(10);' > "$t/a.scad"
  printf 'cube(10);' > "$t/b.scad"
  # one STL containing BOTH cubes as one exported body (the fuse: a single
  # file, so a slicer sees one object no matter that the cubes are disjoint)
  printf 'cube(10); translate([20,0,0]) cube(10);' > "$t/fused.scad"
  for f in a b fused; do
    xvfb-run -a "$OPENSCAD_BIN" ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} -o "$t/$f.stl" "$t/$f.scad" >/dev/null 2>&1 \
      || { echo "SELFTEST FAIL  render $f"; return 1; }
  done
  local pass=1
  prusa-slicer --merge --export-3mf --output "$t/sep.3mf" "$t/a.stl" "$t/b.stl" >/dev/null 2>&1 \
    || { echo "SELFTEST FAIL  merge two parts"; return 1; }
  local sep; sep="$(plate_object_count "$t/sep.3mf")"
  [[ "$sep" == 2 ]] || { echo "SELFTEST FAIL  two separate part STLs merged to ${sep} object(s), expected 2"; pass=0; }
  # the fused single STL -> exactly 1 object: this is the case that must be
  # DETECTABLE as < N, or a fused deliverable would sail through the gate.
  prusa-slicer --merge --export-3mf --output "$t/fused.3mf" "$t/fused.stl" >/dev/null 2>&1 \
    || { echo "SELFTEST FAIL  export fused body"; return 1; }
  local fused; fused="$(plate_object_count "$t/fused.3mf")"
  [[ "$fused" == 1 ]] || { echo "SELFTEST FAIL  a fused single body read as ${fused} object(s), expected 1 — the counter cannot flag a fused deliverable"; pass=0; }
  if [[ "$pass" == 1 ]]; then
    echo "plate.sh selftest OK — separate parts -> 2 objects, a fused body -> 1 (the fuse is detectable as < N)"
    return 0
  fi
  return 1
}

if [[ "$MODE" != "selftest" && "${#names[@]}" -lt 1 ]]; then
  echo "usage: plate.sh [--check|--selftest] <name>..." >&2; exit 2
fi

case "$MODE" in
  selftest) selftest ;;
  check)
    rc=0
    # ${names[@]+...} guard: expanding an empty array under `set -u` aborts on
    # the bash 3.2 floor the repo targets (same pattern as gate.sh).
    for name in ${names[@]+"${names[@]}"}; do check_plate "$name" || rc=1; done
    exit "$rc" ;;
  build)
    rc=0
    for name in ${names[@]+"${names[@]}"}; do
      if n="$(build_plate "$name")"; then
        echo "built build/${name}-plate.3mf (${n} parts as separate objects)"
      else rc=1; fi
    done
    exit "$rc" ;;
esac
