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
#   explode: <mm>
#
#   title         optional display title for ASSEMBLY.md (defaults to the
#                 design name verbatim).
#   part          a printed part: the module call that produces its geometry,
#                 a quantity, and a human description. These are the design's
#                 own part modules, defined in designs/<name>/<name>.scad.
#   vitamin       a bought-in part (screw, bearing, insert, magnet …): the
#                 NopSCADlib module call (e.g. screw(M3_cap_screw,16)) that
#                 draws it and self-registers on the BOM, a quantity, and a
#                 human description.
#   step          one line of step-by-step assembly text; multiple step: lines
#                 become an ordered list in ASSEMBLY.md.
#   explode       optional per-step separation distance (mm) between stacked
#                 parts in the exploded view; a non-negative integer. Tune it
#                 to the part size — a ~250 mm part reads well around 150, a
#                 ~20 mm part around 15. Defaults to 30 when absent; the old
#                 hardcoded value was far too small for large parts.
#
# NopSCADlib is pulled in ONLY when the manifest declares at least one
# vitamin: — a vitamin's geometry comes from NopSCADlib. A parts-only
# manifest renders with pure first-party OpenSCAD (parts stacked by a plain
# translate), so a vitamin-free design does NOT become a GPL-3.0 combined
# work and needs no license disclosure. Declaring a vitamin: is the opt-in
# into NopSCADlib at the design layer (see docs/licensing.md).
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
  ASSEMBLY_USES_NOPSCADLIB=0
  local parts=() vitamins=() raw_explode="" has_explode=0

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"                           # strip comments
    [[ "$line" =~ [^[:space:]] ]] || continue    # skip blanks
    local key val
    key="$(trim "${line%%:*}")"
    val="$(trim "${line#*:}")"
    case "$key" in
      title)   ASSEMBLY_TITLE="$val" ;;
      step)    ASSEMBLY_STEPS+=("$val") ;;
      explode) raw_explode="$val"; has_explode=1 ;;
      part|vitamin)
        # split val on '|' into call | qty | description
        local call qty desc
        IFS='|' read -r call qty desc <<<"$val"
        call="$(trim "$call")"; qty="$(trim "$qty")"; desc="$(trim "$desc")"
        # Reject malformed lines: every part/vitamin needs all three fields.
        [[ -n "$call" && -n "$qty" && -n "$desc" ]] \
          || die "malformed ${key}: line (need 'call | qty | description'): $line"
        if [[ "$key" == part ]]; then
          parts+=("$call|$qty|$desc")
        else
          vitamins+=("$call|$qty|$desc")
        fi
        ;;
    esac
  done <"$conf"

  [[ -n "$ASSEMBLY_TITLE" ]] || ASSEMBLY_TITLE="$design"

  # A manifest that declares nothing to render is a mistake, not an empty view.
  (( ${#parts[@]} + ${#vitamins[@]} > 0 )) \
    || die "assembly.conf for '$design' declares no part: or vitamin: entries"

  # Per-step separation (mm) for the exploded view. Default is deliberately
  # larger than the old hardcoded 20mm, which vanished against a large part;
  # a design tunes it to its own scale with `explode:`.
  # Default applies only when explode: is absent — a declared-but-empty value
  # is an error, not a silent fallback. Normalise with 10# so a leading zero
  # (e.g. 08) is base-10, not an invalid octal that would abort under set -e.
  local step=30
  if (( has_explode )); then
    [[ "$raw_explode" =~ ^[0-9]+$ ]] \
      || die "explode: must be a non-negative integer (mm), got: '$raw_explode'"
    step=$((10#$raw_explode))
  fi

  # ── Emit the SCAD ──
  # The design's own parts are modules in designs/<name>/<name>.scad, which we
  # `use` so the calls resolve (path mirrors ROOT — overridable via
  # ASSEMBLY_DESIGNS_DIR for the selftest; OPENSCADPATH includes the repo root).
  #
  # NopSCADlib is included ONLY when the manifest declares a vitamin: whose
  # geometry it supplies. A parts-only manifest stays pure first-party OpenSCAD
  # — parts stacked by a plain translate — so a vitamin-free design does not
  # become a GPL-3.0 combined work (see docs/licensing.md). Declaring a vitamin
  # is the design-layer opt-in into NopSCADlib.
  {
    echo "use <${ROOT}/${design}/${design}.scad>"
    if (( ${#vitamins[@]} )); then
      ASSEMBLY_USES_NOPSCADLIB=1
      # Vitamins need NopSCADlib; wrap in assembly() for BOM hierarchy and use
      # explode() so $explode (set by the render pass) displaces each item.
      echo 'include <NopSCADlib/core.scad>'
      echo 'module __assembly_root() assembly("main") {'
      local idx=0 call qty desc
      for entry in "${parts[@]}"; do
        IFS='|' read -r call qty desc <<<"$entry"
        echo "  explode($((idx * step))) translate([0,0,$((idx*5))]) $call;"
        idx=$((idx + 1))
      done
      for entry in "${vitamins[@]}"; do
        IFS='|' read -r call qty desc <<<"$entry"
        echo "  explode($((idx * step))) translate([100,$((idx*5)),0]) $call;"
        idx=$((idx + 1))
      done
      echo '}'
      echo '__assembly_root();'
    else
      # Parts only: no NopSCADlib, no assembly()/explode() — stack the parts
      # along Z by `step` mm each so the exploded view separates them.
      local idx=0 call qty desc
      for entry in "${parts[@]}"; do
        IFS='|' read -r call qty desc <<<"$entry"
        echo "translate([0,0,$((idx * step))]) $call;"
        idx=$((idx + 1))
      done
    fi
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
  # Capture the log and fail on non-zero exit or on an ERROR line (OpenSCAD can
  # exit 0 while reporting CGAL/geometry errors — product-shot.sh's pattern).
  echo "  render: exploded.png"
  local rc=0 log
  log="$(xvfb-run -a "$OPENSCAD_BIN" \
    ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
    -D'$explode=1' \
    -o "$outdir/exploded.png" "$scad" 2>&1)" || rc=$?
  if (( rc != 0 )); then
    echo "error: exploded-view render failed (exit $rc)" >&2
    sed 's/^/      /' <<<"$log" | tail -20 >&2
    rm -f "$scad"; return 1
  fi
  if grep -qE '^ERROR' <<<"$log"; then
    echo "error: exploded-view render emitted ERROR" >&2
    grep '^ERROR' <<<"$log" | sed 's/^/      /' >&2
    rm -f "$scad"; return 1
  fi

  # Pass 2 — BOM collection ($bom=2 emits vitamin echo lines). Only meaningful
  # when NopSCADlib is in play (vitamins declared); a parts-only design has no
  # NopSCADlib BOM to collect, and the table is re-read from the manifest
  # regardless, so skip the extra render entirely.
  local bom_out="build/.assembly-${design}.bom"
  if (( ASSEMBLY_USES_NOPSCADLIB )); then
    echo "  collect: BOM"
    rc=0
    log="$(xvfb-run -a "$OPENSCAD_BIN" \
      ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
      -D'$bom=2' \
      -o /dev/null --export-format echo "$scad" 2>&1)" || rc=$?
    printf '%s' "$log" >"$bom_out"
    if (( rc != 0 )); then
      echo "error: BOM collection failed (exit $rc)" >&2
      sed 's/^/      /' <<<"$log" | tail -20 >&2
      rm -f "$scad" "$bom_out"; return 1
    fi
  fi

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
  local needles=("include <NopSCADlib/core.scad>" "widget_body()" "widget_lid()" "screw(M3_cap_screw,16)" "insert(F1BM3)" 'assembly("main")' "explode(")
  for needle in "${needles[@]}"; do
    if ! grep -qF "$needle" "$test_scad"; then
      echo "SELFTEST FAIL: generated SCAD missing '$needle'"; sed 's/^/    /' "$test_scad"; pass=0
    fi
  done
  if [[ "$pass" == "1" ]]; then
    echo "selftest ok    [parse] (parts, vitamins, NopSCADlib, assembly() and explode() emitted)"
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

  # Test 7 — malformed part/vitamin line (missing fields) is rejected.
  mkdir -p "$root/bad"
  printf 'part: only_call()\n' > "$root/bad/assembly.conf"
  : > "$root/bad/bad.scad"
  out="$( ROOT="$root" generate_scad "bad" "$tmp/bad.scad" 2>&1 )" || true
  if ! grep -qF "malformed" <<<"$out"; then
    echo "SELFTEST FAIL: malformed part line should be rejected"; sed 's/^/    /' <<<"$out"; pass=0
  else
    echo "selftest ok    [malformed] (missing fields rejected)"
  fi

  # Test 8 — no-arg sweep over a tree with no manifests is a clean no-op.
  local empty_root; empty_root="$(mktemp -d)"
  out="$( ASSEMBLY_DESIGNS_DIR="$empty_root" "$SELF" 2>&1 )" || true
  if ! grep -qF "no designs with assembly.conf found" <<<"$out"; then
    echo "SELFTEST FAIL: no-arg sweep with no manifests should report cleanly"; sed 's/^/    /' <<<"$out"; pass=0
  else
    echo "selftest ok    [no-arg-noop] (no manifests → clean no-op)"
  fi
  rm -rf "$empty_root"

  # Test 9 — a parts-only manifest stays NopSCADlib-free (no GPL combination
  # for a vitamin-free design) and applies the explode: step.
  mkdir -p "$root/pure"
  cat > "$root/pure/assembly.conf" <<'CONF'
explode: 150
part: base()  | 1 | base
part: cover() | 1 | cover
CONF
  : > "$root/pure/pure.scad"
  ASSEMBLY_USES_NOPSCADLIB=x
  ROOT="$root" generate_scad "pure" "$tmp/pure.scad"
  if grep -qF 'NopSCADlib' "$tmp/pure.scad"; then
    echo "SELFTEST FAIL: [pure] parts-only manifest pulled in NopSCADlib"; sed 's/^/    /' "$tmp/pure.scad"; pass=0
  elif grep -qF 'assembly(' "$tmp/pure.scad"; then
    echo "SELFTEST FAIL: [pure] parts-only manifest emitted an assembly() wrapper"; pass=0
  elif ! grep -qF 'translate([0,0,150]) cover();' "$tmp/pure.scad"; then
    echo "SELFTEST FAIL: [pure] explode: step not applied (want 'translate([0,0,150]) cover();')"; sed 's/^/    /' "$tmp/pure.scad"; pass=0
  elif [[ "$ASSEMBLY_USES_NOPSCADLIB" != "0" ]]; then
    echo "SELFTEST FAIL: [pure] ASSEMBLY_USES_NOPSCADLIB should be 0 for a parts-only manifest, got '$ASSEMBLY_USES_NOPSCADLIB'"; pass=0
  else
    echo "selftest ok    [pure] (parts-only → no NopSCADlib, explode: step applied)"
  fi

  # Test 10 — a manifest that declares nothing to render is rejected.
  mkdir -p "$root/empty"
  printf 'title: nothing here\n' > "$root/empty/assembly.conf"
  : > "$root/empty/empty.scad"
  out="$( ROOT="$root" generate_scad "empty" "$tmp/empty.scad" 2>&1 )" || true
  if ! grep -qF "declares no part" <<<"$out"; then
    echo "SELFTEST FAIL: [empty] manifest with no parts/vitamins should be rejected"; sed 's/^/    /' <<<"$out"; pass=0
  else
    echo "selftest ok    [empty] (manifest with no parts/vitamins rejected)"
  fi

  # Test 11 — a non-integer explode: value is rejected.
  mkdir -p "$root/badexplode"
  printf 'explode: lots\npart: p() | 1 | p\n' > "$root/badexplode/assembly.conf"
  : > "$root/badexplode/badexplode.scad"
  out="$( ROOT="$root" generate_scad "badexplode" "$tmp/be.scad" 2>&1 )" || true
  if ! grep -qF "explode: must be" <<<"$out"; then
    echo "SELFTEST FAIL: [bad-explode] non-integer explode: should be rejected"; sed 's/^/    /' <<<"$out"; pass=0
  else
    echo "selftest ok    [bad-explode] (non-integer explode: rejected)"
  fi

  # Test 12 — a declared-but-empty explode: is an error, not a silent default.
  mkdir -p "$root/emptyexplode"
  printf 'explode:\npart: p() | 1 | p\n' > "$root/emptyexplode/assembly.conf"
  : > "$root/emptyexplode/emptyexplode.scad"
  out="$( ROOT="$root" generate_scad "emptyexplode" "$tmp/ee.scad" 2>&1 )" || true
  if ! grep -qF "explode: must be" <<<"$out"; then
    echo "SELFTEST FAIL: [empty-explode] a declared-but-empty explode: should be rejected, not defaulted"; sed 's/^/    /' <<<"$out"; pass=0
  else
    echo "selftest ok    [empty-explode] (declared-but-empty explode: rejected)"
  fi

  # Test 13 — a leading-zero explode: is read base-10 (not octal), so it does
  # not abort arithmetic under set -e; 010 must mean 10mm, not 8.
  mkdir -p "$root/leadzero"
  cat > "$root/leadzero/assembly.conf" <<'CONF'
explode: 010
part: base()  | 1 | base
part: cover() | 1 | cover
CONF
  : > "$root/leadzero/leadzero.scad"
  ROOT="$root" generate_scad "leadzero" "$tmp/lz.scad"
  if ! grep -qF 'translate([0,0,10]) cover();' "$tmp/lz.scad"; then
    echo "SELFTEST FAIL: [leading-zero] explode: 010 should be base-10 (want 'translate([0,0,10]) cover();')"; sed 's/^/    /' "$tmp/lz.scad"; pass=0
  else
    echo "selftest ok    [leading-zero] (explode: 010 read base-10, no octal abort)"
  fi

  if (( pass )); then
    echo "ok    assembly.sh --selftest: manifest parsing and generator contract hold"
    return 0
  fi
  echo "FAIL  assembly.sh --selftest"
  return 1
}

# ── Sweep: regenerate every design with an assembly.conf ──
assembly_all() {
  local found=0
  for conf in "$ROOT"/*/assembly.conf; do
    [[ -f "$conf" ]] || continue
    found=1
    assembly_one "$(basename "$(dirname "$conf")")"
  done
  if [[ "$found" -eq 0 ]]; then
    echo "no designs with assembly.conf found under $ROOT/"
  fi
}

# ── Dispatch ──
case "${1:-}" in
  --selftest) run_selftest ;;
  -h|--help)
    sed -n '2,42p' "$SELF" | sed 's/^# \{0,1\}//'
    ;;
  "")
    # No arg = sweep every design with an assembly.conf (regen-family contract).
    # A tree with no manifests is a clean no-op, not an error.
    assembly_all
    ;;
  -*)
    die "unknown option '$1' — try: $0 --help"
    ;;
  *)
    assembly_one "$1"
    ;;
esac
