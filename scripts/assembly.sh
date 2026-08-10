#!/usr/bin/env bash
# Generate assembly instructions (exploded view + BOM) from a per-design manifest.
#
# Usage:
#   ./scripts/assembly.sh            # regenerate every design with an assembly.conf
#   ./scripts/assembly.sh <name>     # regenerate one design (must have assembly.conf)
#   ./scripts/assembly.sh --selftest # manifest-parser + generator contract test
#
# A design opts in with designs/<name>/assembly.conf, in the house key: value
# conf style used by team.conf / derives.conf / shots.conf. Each key may repeat
# to declare multiple items:
#
#   title: <one-line assembly title>
#   part: <openscad-module-call> | <qty> | <description>
#   vitamin: <openscad-module-call> | <qty> | <description>
#   step: <step text — the order of step: lines is the assembly order>
#
#   title         optional display title for ASSEMBLY.md (defaults to the
#                 design name, title-cased)
#   part          a printed part: the module call that produces its geometry
#                 (called with $bom=1 so it self-registers), a quantity, and a
#                 human description. These are the design's own parts.
#   vitamin       a bought-in part (screw, bearing, insert, magnet …): the
#                 NopSCADlib module call (e.g. screw(M3_cap_screw,16)) that
#                 draws it and self-registers on the BOM, a quantity, and a
#                 human description.
#   step          one line of step-by-step assembly text; multiple step: lines
#                 become an ordered list in ASSEMBLY.md.
#
# Lines starting with # are comments; blank lines are ignored.
# The manifest is FIXED across review rounds — add a new entry rather than
# moving or reordering one, so a diff stays legible (same rule as shots.conf).
#
# The generator writes two artifacts:
#   designs/<name>/previews/exploded.png  — an exploded-view render
#   designs/<name>/ASSEMBLY.md            — the bill of materials + step text
#
# Requires: openscad (via $OPENSCAD_BIN), xvfb-run (headless display).
# The generated exploded view is committed by CI's regen job (#157 wires that);
# this script only produces it locally.

set -euo pipefail

cd "$(dirname "$0")/.."
export OPENSCADPATH="$PWD/lib:$PWD"

OPENSCAD_BIN="${OPENSCAD_BIN:-openscad}"
read -ra OSC_ARGS <<<"${OPENSCAD_ARGS:-}"

# Overridable root so --selftest can target a throwaway fixture tree.
ROOT="${ASSEMBLY_DESIGNS_DIR:-designs}"

SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  printf '%s' "${s%"${s##*[![:space:]]}"}"
}

die() { echo "error: $*" >&2; exit 1; }

# ── Parse a manifest into a temporary SCAD file + capture the fields we need ──
# Emits a self-contained .scad that includes NopSCADlib, instantiates each
# declared part/vitamin inside an assembly() block with explode() offsets, and
# relies on $bom/$explode (set by the render passes below) to drive BOM output
# and the exploded displacement.
#
# Globals set for the caller:  ASSEMBLY_TITLE, ASSEMBLY_STEPS[]
# Args: <design-name> <output-scad-path>
generate_scad() {
  local design="$1" out_scad="$2"
  local conf="$ROOT/$design/assembly.conf"
  ASSEMBLY_TITLE=""
  ASSEMBLY_STEPS=()
  local parts=() vitamins=()

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"                           # strip comments
    [[ "$line" =~ [^[:space:]] ]] || continue    # skip blanks
    local key val
    key="$(trim "${line%%:*}")"
    val="$(trim "${line#*:}")"
    case "$key" in
      title) ASSEMBLY_TITLE="$val" ;;
      step)  ASSEMBLY_STEPS+=("$val") ;;
      part|vitamin)
        # split val on '|' into call | qty | description
        local call qty desc
        IFS='|' read -r call qty desc <<<"$val"
        call="$(trim "$call")"; qty="$(trim "$qty")"; desc="$(trim "$desc")"
        if [[ "$key" == part ]]; then
          parts+=("$call|$qty|$desc")
        else
          vitamins+=("$call|$qty|$desc")
        fi
        ;;
    esac
  done <"$conf"

  [[ -n "$ASSEMBLY_TITLE" ]] || ASSEMBLY_TITLE="$design"

  # ── Emit the SCAD ──
  # The design's own parts are expected to be modules in designs/<name>/<name>.scad.
  # We include that file so the part module calls resolve. Vitamins come from
  # NopSCADlib's core.scad (screws, nuts, washers, bearings). Each item sits
  # inside assembly("…") for BOM hierarchy, with explode() offsets stacking
  # along Z so the exploded view separates them.
  {
    echo 'include <NopSCADlib/core.scad>'
    # Include the design so its part modules resolve; tolerate a missing file
    # (the selftest fixture may not ship one).
    echo "use <designs/${design}/${design}.scad>"
    echo 'module __assembly_root() assembly("main") {'
    local idx=0
    for entry in "${parts[@]}"; do
      local call qty desc
      IFS='|' read -r call qty desc <<<"$entry"
      # Stack parts along Z; each offset by idx*20mm in the exploded view.
      echo "  explode($((idx * 20))) translate([0,0,$((idx*5))]) $call;"
      idx=$((idx + 1))
    done
    for entry in "${vitamins[@]}"; do
      local call qty desc
      IFS='|' read -r call qty desc <<<"$entry"
      echo "  explode($((idx * 20))) translate([100,$((idx*5)),0]) $call;"
      idx=$((idx + 1))
    done
    echo '}'
    echo '__assembly_root();'
  } >"$out_scad"
}

# ── Generate artifacts for one design ──
assembly_one() {
  local design="$1"
  local conf="$ROOT/$design/assembly.conf"
  local outdir="$ROOT/$design/previews"

  [[ -f "$conf" ]] || { echo "error: $conf not found" >&2; return 1; }
  mkdir -p "$outdir" build

  local scad="build/.assembly-${design}.scad"
  generate_scad "$design" "$scad"

  # Pass 1 — exploded-view render ($explode=1 displaces parts via explode()).
  echo "  render: exploded.png"
  xvfb-run -a "$OPENSCAD_BIN" \
    ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
    -D'$explode=1' \
    -o "$outdir/exploded.png" "$scad" 2>&1 | grep -iE "error|warning" || true

  # Pass 2 — BOM collection ($bom=2 emits vitamin/part echo lines).
  echo "  collect: BOM"
  local bom_out="build/.assembly-${design}.bom"
  xvfb-run -a "$OPENSCAD_BIN" \
    ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
    -D'$bom=2' \
    -o /dev/null --export-format echo "$scad" >"$bom_out" 2>&1 || true

  # ── Write ASSEMBLY.md ──
  local md="$ROOT/$design/ASSEMBLY.md"
  {
    echo "# ${ASSEMBLY_TITLE} — assembly"
    echo
    echo "![Exploded view](previews/exploded.png)"
    echo
    echo "## Bill of materials"
    echo
    # Re-read the manifest for the BOM table — the echo pass may not be
    # available on all setups, so the manifest itself is the source of truth.
    echo "| Part | Qty | Description |"
    echo "|---|---|---|"
    while IFS= read -r line || [[ -n "$line" ]]; do
      line="${line%%#*}"
      [[ "$line" =~ [^[:space:]] ]] || continue
      local key val
      key="$(trim "${line%%:*}")"
      val="$(trim "${line#*:}")"
      case "$key" in
        part|vitamin)
          local call qty desc
          IFS='|' read -r call qty desc <<<"$val"
          call="$(trim "$call")"; qty="$(trim "$qty")"; desc="$(trim "$desc")"
          echo "| \`${call}\` | ${qty} | ${desc} |"
          ;;
      esac
    done <"$conf"
    echo
    if ((${#ASSEMBLY_STEPS[@]})); then
      echo "## Assembly steps"
      echo
      local i=1
      for step in "${ASSEMBLY_STEPS[@]}"; do
        echo "${i}. ${step}"
        i=$((i + 1))
      done
      echo
    fi
  } >"$md"
  echo "  wrote: ASSEMBLY.md"

  rm -f "$scad" "$bom_out"
}

# ── Selftest ──
# Proves the manifest parser and the generator's contract without needing a
# real design or a render: a throwaway fixture design with a minimal
# assembly.conf is parsed, and the script's no-conf error behavior is verified.
# Renders nothing (mirrors shot-spec.sh / field-test.sh — fast, no openscad).
run_selftest() {
  local tmp; tmp="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap "rm -rf '$tmp'" RETURN
  local pass=1
  local root="$tmp/designs"

  # Fixture: a minimal design with an assembly.conf.
  mkdir -p "$root/widget"
  cat > "$root/widget/assembly.conf" <<'CONF'
# Assembly manifest for widget (scripts/assembly.sh selftest fixture).
title: Widget assembly
part: widget_body() | 1 | the main body
part: widget_lid() | 1 | the press-fit lid
vitamin: screw(M3_cap_screw,16) | 4 | M3 cap screw x16mm
vitamin: insert(F1BM3) | 4 | heatset insert M3
step: Press the four heatset inserts into the body's insert bosses.
step: Place the lid over the body, aligning the screw holes.
step: Drive the four M3 cap screws through the lid into the inserts.
CONF
  # A minimal design .scad so the use<> would resolve (the parser references it).
  cat > "$root/widget/widget.scad" <<'SCAD'
module widget_body() cube([20,20,5]);
module widget_lid() cube([20,20,2]);
SCAD

  # Test 1 — manifest parser: generate_scad emits all declared items.
  # generate_scad is a function in this script's scope, so we call it directly.
  local test_scad="$tmp/parse-test.scad"
  ASSEMBLY_TITLE="" ASSEMBLY_STEPS=()
  ROOT="$root" generate_scad "widget" "$test_scad"
  local needles=("widget_body()" "widget_lid()" "screw(M3_cap_screw,16)" "insert(F1BM3)" 'assembly("main")' "explode(")
  for needle in "${needles[@]}"; do
    if ! grep -qF "$needle" "$test_scad"; then
      echo "SELFTEST FAIL: generated SCAD missing '$needle'"; sed 's/^/    /' "$test_scad"; pass=0
    fi
  done
  if [[ "$pass" == "1" ]]; then
    echo "selftest ok    [parse] (all parts, vitamins, assembly() and explode() emitted)"
  fi

  # Test 2 — ASSEMBLY_STEPS captured in the right order (order matters: the
  # manifest's step: sequence is the assembly order).
  if [[ "${ASSEMBLY_STEPS[0]}" != *"Press the four heatset inserts"* ]]; then
    echo "SELFTEST FAIL: first step is '${ASSEMBLY_STEPS[0]:-<empty>}', expected the inserts step"
    pass=0
  elif [[ "${ASSEMBLY_STEPS[2]}" != *"Drive the four M3 cap screws"* ]]; then
    echo "SELFTEST FAIL: third step is '${ASSEMBLY_STEPS[2]:-<empty>}', expected the screws step"
    pass=0
  else
    echo "selftest ok    [steps] (ordered step list captured correctly)"
  fi

  # Test 3 — title from the manifest is captured.
  if [[ "$ASSEMBLY_TITLE" != "Widget assembly" ]]; then
    echo "SELFTEST FAIL: title is '$ASSEMBLY_TITLE', expected 'Widget assembly'"; pass=0
  else
    echo "selftest ok    [title] (manifest title captured)"
  fi

  # Test 4 — title defaults to design name when title: is absent.
  mkdir -p "$root/notitle"
  printf 'part: foo() | 1 | bar\n' > "$root/notitle/assembly.conf"
  : > "$root/notitle/notitle.scad"
  ASSEMBLY_TITLE=""
  ROOT="$root" generate_scad "notitle" "$tmp/nt.scad"
  if [[ "$ASSEMBLY_TITLE" != "notitle" ]]; then
    echo "SELFTEST FAIL: title should default to 'notitle', got '$ASSEMBLY_TITLE'"; pass=0
  else
    echo "selftest ok    [default-title] (title defaults to design name when absent)"
  fi

  # Test 5 — a named design with no assembly.conf errors cleanly (rc 1).
  mkdir -p "$root/bare"
  : > "$root/bare/bare.scad"
  local out rc=0
  out="$( ASSEMBLY_DESIGNS_DIR="$root" "$SELF" bare 2>&1 )" || rc=$?
  if [[ "$rc" != "1" ]]; then
    echo "SELFTEST FAIL: [bare design] expected rc 1 (no assembly.conf) got $rc"; sed 's/^/    /' <<<"$out"; pass=0
  elif ! grep -qF "not found" <<<"$out"; then
    echo "SELFTEST FAIL: [bare design] expected 'not found' in output"; sed 's/^/    /' <<<"$out"; pass=0
  else
    echo "selftest ok    [bare design] (no assembly.conf → clean error)"
  fi

  # Test 6 — comments and blank lines are stripped (a line that is only a
  # comment must not be parsed as a key).
  mkdir -p "$root/comments"
  cat > "$root/comments/assembly.conf" <<'CONF'
# This is a comment line
   # indented comment

part: real_part() | 1 | real
#vitamin: commented_out() | 1 | should not appear
CONF
  : > "$root/comments/comments.scad"
  ASSEMBLY_TITLE="" ASSEMBLY_STEPS=()
  ROOT="$root" generate_scad "comments" "$tmp/cmt.scad"
  if grep -qF "commented_out" "$tmp/cmt.scad"; then
    echo "SELFTEST FAIL: commented-out vitamin leaked into generated SCAD"; pass=0
  elif ! grep -qF "real_part()" "$tmp/cmt.scad"; then
    echo "SELFTEST FAIL: real part missing from generated SCAD"; pass=0
  else
    echo "selftest ok    [comments] (comment lines and indented comments stripped)"
  fi

  if (( pass )); then
    echo "ok    assembly.sh --selftest: manifest parsing and generator contract hold"
    return 0
  fi
  echo "FAIL  assembly.sh --selftest"
  return 1
}

# ── Dispatch ──
case "${1:-}" in
  --selftest) run_selftest ;;
  ""|-h|--help)
    sed -n '2,42p' "$SELF" | sed 's/^# \{0,1\}//'
    ;;
  -*)
    die "unknown option '$1' — try: $0 --help"
    ;;
  *)
    assembly_one "$1"
    ;;
esac
