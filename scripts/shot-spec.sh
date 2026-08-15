#!/usr/bin/env bash
# Author a design's product-shot manifests from a PM's art-direction brief,
# without hand-writing the syntax. This is the mechanics half of the
# /art-direction skill: the PM (via the skill) picks a named *view* and a
# named *color*; this script owns the camera math, the hex, the freeze rule,
# and the exact README embed — so a creative request never turns into a
# pipe-delimited line typed by hand.
#
#   ./scripts/shot-spec.sh views                       # named framing presets
#   ./scripts/shot-spec.sh palette                     # named filament colors
#   ./scripts/shot-spec.sh add <design> <shot> [opts]  # -> shots.conf (tier 1)
#   ./scripts/shot-spec.sh still <design> <still> --prompt '...' [--seed <shot>]  # -> product-still.conf (tier 1.5)
#   ./scripts/shot-spec.sh lifestyle <design> <shot> --scene '...' [--seed <ref>] # -> lifestyle.conf (tier 2)
#   ./scripts/shot-spec.sh motion <design> <shot> --motion '...' [--seed <ref>]   # -> motion.conf (tier 2 clip)
#   ./scripts/shot-spec.sh embed <design> <shot> [--lifestyle|--still|--motion]   # README block
#   ./scripts/shot-spec.sh check <design>              # validate manifests
#   ./scripts/shot-spec.sh --selftest
#
# The tiers form one image-to-image SEED chain — a bare-part product still (tier
# 1.5) seeds a lifestyle scene (tier 2), which seeds a motion clip — so `--seed`
# names the committed previews/<ref>.png each stage starts from. A still seeds
# only a geometry-true tier-1 render (angle = which render it seeds); a scene
# may seed a tier-1 render or a product still; a clip may seed any of them.
#
# What it deliberately does NOT do: touch README.md, or render anything. The
# skill places the embed with framing judgment, and CI renders the PNGs
# (scripts/product-shot.sh for tier 1, the lifestyle workflow for tier 2). The
# division of labor mirrors product-shots/SKILL.md: you own the manifest and the
# embed; CI owns the pixels.
#
# Standards this enforces so the PM never has to remember them:
#   * Freeze policy — `add`/`lifestyle` REFUSE to touch an existing entry of the
#     same name (shots are fixed across review rounds; add a new one, never move
#     one). See CLAUDE.md "Frozen preview cameras".
#   * Tier-1 shape — a studio shot is geometry-true and its scene is fixed, so
#     the only creative levers are pose (a -D define), color, finish, framing.
#     Scenery/staging lives in tier 2, which is why `lifestyle` is a separate
#     verb and emits the disclosure readme-gate requirement 9 demands.
#   * Well-formedness — finish in the known set, color a known name or #rrggbb,
#     camera a numeric rotz,elev,zoom, size a sane WxH. `check` re-runs all of
#     these on the committed manifests before CI ever spins up a renderer.
set -euo pipefail

cd "$(dirname "$0")/.."

# The design tree to operate on. Overridable so --selftest can point every
# subcommand at a throwaway fixture tree without touching the real designs/
# (mirrors readme-gate.sh's READMEGATE_DESIGNS_DIR). Defaults to designs/.
ROOT="${SHOTSPEC_DESIGNS_DIR:-designs}"

# ---- vocabularies -----------------------------------------------------------
# Named framing presets: rotz,elev,zoom (the tuple scripts/product-shot.sh and
# tools/photoshot/photoshot.py consume). rotz/elev orbit the grounded model in
# degrees; zoom scales an automatic bounding-box fit (1.0 = snug, <1 pulls back,
# >1 crops in), so a preset means the same framing on any design's size. These
# are the product-photography angles product-shots/SKILL.md recommends, named so
# a brief can say "top" instead of "0,80,0.95".
VIEWS=(
  "hero:35,18,0.90"          # the lead three-quarter product shot
  "hero-tall:35,14,0.92"     # same, framed for a tall part (e.g. an instrument)
  "three-quarter:28,24,0.85" # higher three-quarter, more of the top face
  "front:0,8,0.90"           # straight-on elevation
  "top:0,80,0.95"            # near top-down, for grids/trays/flat parts
  "low:40,6,0.92"            # dramatic low angle, hero of a tall silhouette
  "detail:45,20,1.25"        # crop in on one feature
)

# Named filament colors -> #rrggbb (product-shot.sh wants the hex WITHOUT '#',
# which this script strips when it writes the manifest line). Plausible, varied
# filament tones so pages across the repo don't all look alike; pass a raw
# #rrggbb to --color for anything not here.
PALETTE=(
  "charcoal:3a3f4a" "graphite:4a4f57" "slate:5b6b7a" "black:222831"
  "ivory:e8e2d0" "sand:c9b48a"
  "orange:e8734a" "amber:d98a3d" "crimson:b5384a" "rust:9c5a3c"
  "forest:3a6b46" "sage:8a9a5b" "teal:2a8a8a"
  "sky:4a7fb5" "navy:2f3f66" "plum:6a4a9a"
)

FINISHES="satin gloss matte"

# largest sensible per-side pixel dimension. The real ceiling is the byte
# budget (scripts/preview-budget.sh, enforced at render and by readme-gate), but
# that can't be known before the render exists; this catches the fat-finger
# 12800x9600 that would blow it, while leaving normal 1100..1600 sizes alone.
MAX_DIM=2400

die() { echo "error: $*" >&2; exit 1; }

# kebab-case, the repo convention for design and shot names. Same shape
# product-shot.sh's <shot> and lifestyle-shot.sh validate against.
is_kebab() { [[ "$1" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; }

# A seed reference is the basename of a committed preview (previews/<ref>.png).
# An AI-prefixed seed (lifestyle-* scene, product-still-* still) is a repaint,
# not a geometry-true render — the tiers that must stay mesh-pinned refuse one.
is_ai_prefix() { case "$1" in lifestyle-*|product-still-*) return 0 ;; *) return 1 ;; esac; }

# Parse a seedable manifest line "<name> | [seed=<ref> |] <prompt>" into the
# globals PSL_name / PSL_seed / PSL_prompt (PSL_seed empty when there is no
# seed= field). Sets globals rather than echoing joined fields on purpose: an
# empty middle field collapses under `read`'s IFS-whitespace handling, so a
# seedless line would misparse its prompt as the seed. Mirrors the seed parsing
# in lifestyle-shot.sh / lifestyle-clip.sh — only a middle field that literally
# starts with 'seed=' is a seed, so a '|' inside a prompt still parses.
# Bash-3.2-safe (no namerefs).
PSL_name=""; PSL_seed=""; PSL_prompt=""; PSL_has_seed=0
parse_seedable_line() {  # <line>  -> sets PSL_name / PSL_seed / PSL_prompt / PSL_has_seed
  local line="$1" rest rtrim
  PSL_name="${line%%|*}"; PSL_name="${PSL_name//[[:space:]]/}"
  rest="${line#*|}"
  rtrim="${rest#"${rest%%[![:space:]]*}"}"; rtrim="${rtrim%"${rtrim##*[![:space:]]}"}"
  PSL_seed=""
  # PSL_has_seed flags that a middle field starting with 'seed=' is PRESENT, so a
  # validator can tell a genuine no-seed line from a malformed one: an empty
  # value ("seed= | prompt") or a bare "seed=ref" with no trailing "| prompt"
  # (which lands whole in PSL_prompt) must be rejected, not silently accepted.
  [[ "$rtrim" == seed=* ]] && PSL_has_seed=1 || PSL_has_seed=0
  if [[ "$rtrim" == seed=* && "$rest" == *"|"* ]]; then
    PSL_seed="${rest%%|*}"; PSL_seed="${PSL_seed//[[:space:]]/}"; PSL_seed="${PSL_seed#seed=}"
    PSL_prompt="${rest#*|}"; PSL_prompt="${PSL_prompt#"${PSL_prompt%%[![:space:]]*}"}"; PSL_prompt="${PSL_prompt%"${PSL_prompt##*[![:space:]]}"}"
  else
    PSL_prompt="$rtrim"
  fi
}

# Validate the parsed seed field for a tier. <loc> is "conf:n" for messages;
# <tier> is lifestyle|still|motion and governs the allowed seed prefixes. Sets
# `bad=1` (dynamic scope from cmd_check) on any problem. Catches the malformed
# forms the generators reject at runtime — empty 'seed=' and 'seed=' with no
# prompt — so `shot-spec check` fails BEFORE a paid CI generation does.
check_seed_field() {  # <loc> <tier>
  local loc="$1" tier="$2"
  [[ "$PSL_has_seed" == 1 ]] || return 0
  if [[ "$PSL_prompt" == seed=* ]]; then
    echo "  FAIL $loc — 'seed=' without a following '| <prompt>'"; bad=1; return 0
  fi
  if [[ -z "$PSL_seed" ]]; then
    echo "  FAIL $loc — empty 'seed=' (give a ref or drop the field)"; bad=1; return 0
  fi
  is_kebab "$PSL_seed" || { echo "  FAIL $loc — seed '$PSL_seed' not kebab-case"; bad=1; return 0; }
  case "$tier" in
    still)
      if is_ai_prefix "$PSL_seed"; then
        echo "  FAIL $loc — seed '$PSL_seed' is an AI image; a product still must seed from a geometry-true tier-1 render"; bad=1
      fi ;;
    lifestyle)
      case "$PSL_seed" in
        lifestyle-*) echo "  FAIL $loc — seed '$PSL_seed' is a lifestyle-* scene; seed from a geometry-true render or a product-still-* still"; bad=1 ;;
      esac ;;
    motion) : ;;   # a clip may seed from any kebab ref (incl. an AI still)
  esac
}

# Every subcommand interpolates <design> into paths ("$ROOT/$design/..."), so a
# name like "../scripts" would escape the design tree. Pin it to kebab-case
# BEFORE any path is built — the same guard lifestyle-shot.sh applies for the
# same reason. Call this first in every verb that takes a design.
require_design() {
  is_kebab "$1" || die "design name '$1' must be kebab-case ([a-z0-9-]) — no path separators"
}

lookup() {  # lookup <name> <"name:value"...> ; echoes value or empty
  # Takes the table's "key:value" entries as arguments rather than by nameref
  # (bash 4.3's `local -n`), so this script stays Bash 3.2-compatible and
  # doesn't raise check.sh's interpreter floor — call as `lookup x "${TBL[@]}"`.
  local want="$1"; shift
  local kv
  for kv in "$@"; do
    [[ "${kv%%:*}" == "$want" ]] && { printf '%s' "${kv#*:}"; return 0; }
  done
  return 1
}

resolve_color() {  # name or #rrggbb / rrggbb -> rrggbb (no '#'), or die
  local c="$1" hex
  if hex="$(lookup "$c" "${PALETTE[@]}")"; then printf '%s' "$hex"; return; fi
  c="${c#\#}"
  [[ "$c" =~ ^[0-9a-fA-F]{6}$ ]] || die "unknown color '$1' — see 'palette', or pass a #rrggbb"
  printf '%s' "$c"
}

resolve_view() {  # view name -> rotz,elev,zoom, or die
  local cam
  cam="$(lookup "$1" "${VIEWS[@]}")" || die "unknown view '$1' — see 'views', or pass --camera rotz,elev,zoom"
  printf '%s' "$cam"
}

valid_camera() {  # rotz,elev,zoom, each a finite number
  local r e z rest
  IFS=',' read -r r e z rest <<<"$1"
  [[ -z "$rest" && -n "$r" && -n "$e" && -n "$z" ]] || return 1
  local n
  for n in "$r" "$e" "$z"; do
    [[ "$n" =~ ^-?[0-9]+(\.[0-9]+)?$ ]] || return 1
  done
  # zoom scales a fit; zero or negative is meaningless.
  awk -v z="$z" 'BEGIN{exit !(z>0)}'
}

valid_size() {  # WxH, both positive ints within a sane ceiling
  local w h rest
  # normalize only the separator (accept 1280X960) — ${1//X/x} is a plain
  # pattern substitution (Bash 3.2-safe), unlike ${1,,} case conversion.
  IFS='x' read -r w h rest <<<"${1//X/x}"
  [[ -z "$rest" && "$w" =~ ^[0-9]+$ && "$h" =~ ^[0-9]+$ ]] || return 1
  (( w >= 4 && h >= 4 && w <= MAX_DIM && h <= MAX_DIM ))
}

# ---- subcommands ------------------------------------------------------------
cmd_views() {
  echo "Named framing presets (rotz,elev,zoom):"
  local kv
  for kv in "${VIEWS[@]}"; do printf '  %-14s %s\n' "${kv%%:*}" "${kv#*:}"; done
  echo "Pass --camera rotz,elev,zoom for a custom angle."
}

cmd_palette() {
  echo "Named filament colors (#rrggbb):"
  local kv
  for kv in "${PALETTE[@]}"; do printf '  %-10s #%s\n' "${kv%%:*}" "${kv#*:}"; done
  echo "Pass --color '#rrggbb' for a custom color."
}

# Print the tier-1 README embed for a shot. Alt text names finish, color AND
# material (e.g. "in satin forest PLA") — the descriptive form every existing
# product-shot alt in the repo follows, so the tool's default output matches the
# convention rather than emitting an alt a reviewer has to flag. The skill still
# refines wording; readme-gate only checks the embed is present.
embed_tier1() {  # <design> <shot> <color-name-or-hex> <finish> <material>
  printf '![Product shot: %s in %s %s %s](previews/%s.png)\n' \
    "$1" "$4" "$3" "$5" "$2"
}

# Print the canonical tier-2 disclosure block VERBATIM — the exact structure
# readme-gate requirement 9 keys on (an "AI-styled scene" alt label plus a
# "geometry is approximate" caption in the paragraph directly below). Copying it
# from here is what keeps a lifestyle shot from ever landing undisclosed.
embed_lifestyle() {  # <design> <shot>
  printf '![AI-styled scene: %s staged in a real-world setting](previews/lifestyle-%s.png)\n\n' \
    "$1" "$2"
  printf '*AI-generated impression for general illustration only — geometry is '
  printf 'approximate and may not exactly match the printed part; see the studio '
  printf 'render above and the STL for the true shape.*\n'
}

# Tier-1.5 product-still disclosure — the SAME canonical tokens ("AI-styled
# scene" alt, "geometry is approximate" caption) lifestyle-shot.sh --kind
# product-still emits, so the PM's pasted embed matches the generator's exactly.
embed_still() {  # <design> <still>
  printf '![AI-styled scene: %s bare-part product still](previews/product-still-%s.png)\n\n' \
    "$1" "$2"
  printf '*AI-generated impression for general illustration only — geometry is '
  printf 'approximate and may not exactly match the printed part; see the studio '
  printf 'render above and the STL for the true shape.*\n'
}

# Tier-2 motion-clip disclosure — same canonical tokens, plus the honest note
# that the MOTION itself is illustrative (the model can invent movement the
# print can't perform; the deterministic turntable stays the motion-true GIF).
embed_motion() {  # <design> <shot>
  printf '![AI-styled scene: %s shown in motion](previews/lifestyle-%s.gif)\n\n' \
    "$1" "$2"
  printf '*AI-generated impression for general illustration only — geometry is '
  printf 'approximate and the motion is illustrative; see the deterministic '
  printf 'turntable and the STL for the true shape and behavior.*\n'
}

# Does a manifest already carry an entry named <shot>? (first pipe field,
# comments/blank ignored). This is the freeze guard.
manifest_has() {  # <conf> <shot>
  local conf="$1" want="$2" line name
  [[ -f "$conf" ]] || return 1
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"
    [[ "$line" =~ [^[:space:]] ]] || continue
    IFS='|' read -r name _ <<<"$line"
    name="${name//[[:space:]]/}"
    [[ "$name" == "$want" ]] && return 0
  done <"$conf"
  return 1
}

cmd_add() {
  local design="${1:-}" shot="${2:-}"; shift $(( $# >= 2 ? 2 : $# ))
  [[ -n "$design" && -n "$shot" ]] || die "usage: add <design> <shot> [--view N|--camera R,E,Z] [--color C] [--finish F] [--pose 'def'] [--size WxH] [--dry-run]"
  local view="hero" camera="" color="orange" finish="satin" pose="" size="1280x960" material="PLA" dry=0
  while (( $# )); do
    case "$1" in
      --view)     view="${2:?}"; shift 2;;
      --camera)   camera="${2:?}"; shift 2;;
      --color)    color="${2:?}"; shift 2;;
      --finish)   finish="${2:?}"; shift 2;;
      --pose)     pose="${2:?}"; shift 2;;
      --size)     size="${2:?}"; shift 2;;
      --material) material="${2:?}"; shift 2;;
      --dry-run)  dry=1; shift;;
      *) die "unknown option '$1' to add";;
    esac
  done
  # Material is descriptive alt text only (not a manifest field); keep it to one
  # line so the printed embed stays a single markdown image.
  [[ "$material" != *$'\n'* ]] || die "material must be a single line"

  require_design "$design"
  [[ -d "$ROOT/$design" ]] || die "no $ROOT/$design"
  is_kebab "$shot" || die "shot name '$shot' must be kebab-case ([a-z0-9-])"
  [[ " $FINISHES " == *" $finish "* ]] || die "unknown finish '$finish' — one of: $FINISHES"
  valid_size "$size" || die "bad size '$size' — want WxH (each 4..$MAX_DIM px)"

  local hex; hex="$(resolve_color "$color")"
  [[ -z "$camera" ]] && camera="$(resolve_view "$view")"
  valid_camera "$camera" || die "bad camera '$camera' — want rotz,elev,zoom (zoom>0)"

  # The pose is a raw -D payload passed to OpenSCAD (e.g. part="assembled"), and
  # it becomes the manifest's last field. Reject the characters that would
  # produce a line product-shot.sh misparses rather than emit one: a space
  # splits it into two defines the single-field grammar can't hold; a '|' is the
  # field separator; a '#' is stripped as a comment (inline in shots.conf); a
  # newline breaks the one-line grammar entirely. Multiple defines are legal in
  # the file — hand-edit for that and re-run `check`.
  if [[ -n "$pose" ]]; then
    case "$pose" in
      *" "*)   die "pose '$pose' has a space — one define per shot here (e.g. part=\"assembled\"); hand-edit shots.conf for multiple" ;;
      *"|"*)   die "pose '$pose' contains '|' — that is the manifest field separator" ;;
      *"#"*)   die "pose '$pose' contains '#' — product-shot.sh strips it as a comment" ;;
      *$'\n'*) die "pose must be a single line" ;;
    esac
  fi

  local conf="$ROOT/$design/shots.conf"
  if manifest_has "$conf" "$shot"; then
    die "shots.conf already has an entry '$shot' — shots are frozen across review rounds; pick a new name instead of moving it (CLAUDE.md: Frozen preview cameras)"
  fi

  local line="$shot | $hex | $finish | $camera | $size"
  [[ -n "$pose" ]] && line="$line | $pose"

  if (( dry )); then
    echo "# would append to $conf:"
    echo "$line"
  else
    if [[ ! -f "$conf" ]]; then
      echo "# Studio product shots for the product page (scripts/product-shot.sh)." >"$conf"
      echo "# name | color | finish | camera(rotz,elev,zoom) | size | defines" >>"$conf"
    fi
    printf '%s\n' "$line" >>"$conf"
    echo "wrote entry '$shot' to $conf"
  fi
  echo
  echo "Embed this near the top of $ROOT/$design/README.md (above the contact sheet):"
  embed_tier1 "$design" "$shot" "$color" "$finish" "$material"
}

cmd_lifestyle() {
  local design="${1:-}" shot="${2:-}"; shift $(( $# >= 2 ? 2 : $# ))
  [[ -n "$design" && -n "$shot" ]] || die "usage: lifestyle <design> <shot> --scene '...' [--seed <ref>] [--dry-run]"
  local scene="" seed="" dry=0
  while (( $# )); do
    case "$1" in
      --scene)   scene="${2:?}"; shift 2;;
      --seed)    seed="${2:?}"; shift 2;;
      --dry-run) dry=1; shift;;
      *) die "unknown option '$1' to lifestyle";;
    esac
  done
  require_design "$design"
  [[ -d "$ROOT/$design" ]] || die "no $ROOT/$design"
  is_kebab "$shot" || die "shot name '$shot' must be kebab-case ([a-z0-9-])"
  [[ -n "$scene" ]] || die "a lifestyle shot needs --scene '<describe the setting>' (image-to-image seeded from a real render: describe the SCENE, not fake geometry)"
  # A '#' in the scene would be read as a comment by lifestyle-shot.sh's
  # full-line rule only at line start, but the manifest is '<shot> | <prompt>'
  # and a literal newline can't live in one line — reject it early with a clear
  # message rather than writing a broken second line.
  [[ "$scene" != *$'\n'* ]] || die "scene must be a single line"
  # A lifestyle scene seeds from a geometry-true tier-1 render OR a tier-1.5
  # product still — but never another lifestyle-* scene (a repaint of a repaint,
  # nothing anchoring the shape). Same rule lifestyle-shot.sh enforces.
  if [[ -n "$seed" ]]; then
    is_kebab "$seed" || die "seed '$seed' must be kebab-case ([a-z0-9-])"
    case "$seed" in
      lifestyle-*) die "seed '$seed' is a lifestyle-* scene — a lifestyle scene seeds from a geometry-true render or a product-still-* still, not another scene" ;;
    esac
  fi

  local conf="$ROOT/$design/lifestyle.conf"
  if manifest_has "$conf" "$shot"; then
    die "lifestyle.conf already has an entry '$shot' — add a new scene name instead of moving one"
  fi

  local line="$shot | $scene"
  [[ -n "$seed" ]] && line="$shot | seed=$seed | $scene"
  if (( dry )); then
    echo "# would append to $conf:"
    echo "$line"
  else
    if [[ ! -f "$conf" ]]; then
      cat >"$conf" <<'HDR'
# Tier-2 AI lifestyle-shot prompts (scripts/lifestyle-shot.sh) — one
# '<shot> | <prompt>' or '<shot> | seed=<ref> | <prompt>' per line. COSMETIC,
# but image-to-image seeded from a committed geometry-true render (or a
# product still), so the shape is pinned; readme-gate forces the disclosure.
HDR
    fi
    printf '%s\n' "$line" >>"$conf"
    echo "wrote scene '$shot' to $conf"
  fi
  echo
  echo "Embed this in $ROOT/$design/README.md, directly below the tier-1 hero (VERBATIM — the disclosure is gated):"
  embed_lifestyle "$design" "$shot"
}

cmd_still() {
  local design="${1:-}" still="${2:-}"; shift $(( $# >= 2 ? 2 : $# ))
  [[ -n "$design" && -n "$still" ]] || die "usage: still <design> <still> --prompt '...' [--seed <tier-1-shot>] [--dry-run]"
  local seed="" prompt="" dry=0
  while (( $# )); do
    case "$1" in
      --seed)    seed="${2:?}"; shift 2;;
      --prompt)  prompt="${2:?}"; shift 2;;
      --dry-run) dry=1; shift;;
      *) die "unknown option '$1' to still";;
    esac
  done
  require_design "$design"
  [[ -d "$ROOT/$design" ]] || die "no $ROOT/$design"
  is_kebab "$still" || die "still name '$still' must be kebab-case ([a-z0-9-])"
  [[ -n "$prompt" ]] || die "a product still needs --prompt '<describe the BARE part, no scene>'"
  [[ "$prompt" != *$'\n'* ]] || die "prompt must be a single line"
  # Angle-by-seed: an image-to-image still has no camera of its own — its angle
  # comes from the tier-1 render it seeds, which is why there is no --view/--camera
  # here. Default the seed to the still's own name; it must be a geometry-true
  # render (a shots.conf shot), never an AI image, so the shape stays mesh-pinned.
  [[ -n "$seed" ]] || seed="$still"
  is_kebab "$seed" || die "seed '$seed' must be kebab-case ([a-z0-9-])"
  ! is_ai_prefix "$seed" || die "seed '$seed' is an AI image — a product still must seed from a geometry-true tier-1 render (a shots.conf shot) so its shape stays pinned to the real mesh"

  local conf="$ROOT/$design/product-still.conf"
  if manifest_has "$conf" "$still"; then
    die "product-still.conf already has an entry '$still' — stills are frozen across review rounds; pick a new name instead of moving it (CLAUDE.md: Frozen preview cameras)"
  fi

  local line="$still | seed=$seed | $prompt"
  if (( dry )); then
    echo "# would append to $conf:"
    echo "$line"
  else
    if [[ ! -f "$conf" ]]; then
      cat >"$conf" <<'HDR'
# Tier-1.5 AI product stills (scripts/lifestyle-shot.sh --kind product-still)
# — the BARE part, no scene, image-to-image seeded from a geometry-true
# tier-1 render. One '<still> | seed=<ref> | <prompt>' per line; readme-gate
# forces the AI disclosure on the committed previews/product-still-<still>.png.
HDR
    fi
    printf '%s\n' "$line" >>"$conf"
    echo "wrote still '$still' to $conf"
  fi
  echo
  echo "Embed this in $ROOT/$design/README.md (VERBATIM — the disclosure is gated):"
  embed_still "$design" "$still"
}

cmd_motion() {
  local design="${1:-}" shot="${2:-}"; shift $(( $# >= 2 ? 2 : $# ))
  [[ -n "$design" && -n "$shot" ]] || die "usage: motion <design> <shot> --motion '...' [--seed <ref>] [--dry-run]"
  local motion="" seed="" dry=0
  while (( $# )); do
    case "$1" in
      --motion)  motion="${2:?}"; shift 2;;
      --seed)    seed="${2:?}"; shift 2;;
      --dry-run) dry=1; shift;;
      *) die "unknown option '$1' to motion";;
    esac
  done
  require_design "$design"
  [[ -d "$ROOT/$design" ]] || die "no $ROOT/$design"
  is_kebab "$shot" || die "shot name '$shot' must be kebab-case ([a-z0-9-])"
  [[ -n "$motion" ]] || die "a motion clip needs --motion '<describe the motion>' (image-to-video; the motion is illustrative)"
  [[ "$motion" != *$'\n'* ]] || die "motion prompt must be a single line"
  # A clip MAY seed from an AI image — animating a lifestyle scene or a product
  # still is exactly the still->clip hop — so only kebab is required here.
  if [[ -n "$seed" ]]; then
    is_kebab "$seed" || die "seed '$seed' must be kebab-case ([a-z0-9-])"
  fi

  local conf="$ROOT/$design/motion.conf"
  if manifest_has "$conf" "$shot"; then
    die "motion.conf already has an entry '$shot' — add a new clip name instead of moving one"
  fi

  local line="$shot | $motion"
  [[ -n "$seed" ]] && line="$shot | seed=$seed | $motion"
  if (( dry )); then
    echo "# would append to $conf:"
    echo "$line"
  else
    if [[ ! -f "$conf" ]]; then
      cat >"$conf" <<'HDR'
# Tier-2 AI motion-clip prompts (scripts/lifestyle-clip.sh) — one
# '<shot> | <prompt>' or '<shot> | seed=<ref> | <prompt>' per line. COSMETIC
# image-to-video seeded from a committed still; the motion is illustrative.
# readme-gate forces the disclosure on previews/lifestyle-<shot>.gif.
HDR
    fi
    printf '%s\n' "$line" >>"$conf"
    echo "wrote clip '$shot' to $conf"
  fi
  echo
  echo "Embed this in $ROOT/$design/README.md (VERBATIM — the disclosure is gated):"
  embed_motion "$design" "$shot"
}

cmd_embed() {
  local design="${1:-}" shot="${2:-}"; shift $(( $# >= 2 ? 2 : $# ))
  [[ -n "$design" && -n "$shot" ]] || die "usage: embed <design> <shot> [--lifestyle|--still|--motion]"
  require_design "$design"
  is_kebab "$shot" || die "shot name '$shot' must be kebab-case ([a-z0-9-])"
  if [[ "${1:-}" == "--lifestyle" ]]; then
    embed_lifestyle "$design" "$shot"
  elif [[ "${1:-}" == "--still" ]]; then
    embed_still "$design" "$shot"
  elif [[ "${1:-}" == "--motion" ]]; then
    embed_motion "$design" "$shot"
  else
    # Recover the color/finish from the manifest so the alt text is accurate.
    local conf="$ROOT/$design/shots.conf" line name color finish
    local col="a printed part" fin=""
    if [[ -f "$conf" ]]; then
      while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%%#*}"; [[ "$line" =~ [^[:space:]] ]] || continue
        IFS='|' read -r name color finish _ <<<"$line"
        name="${name//[[:space:]]/}"
        [[ "$name" == "$shot" ]] || continue
        col="#${color//[[:space:]]/}"; fin="${finish//[[:space:]]/}"
        break
      done <"$conf"
    fi
    # material isn't stored in the manifest; default to the repo's usual PLA.
    embed_tier1 "$design" "$shot" "$col" "$fin" "PLA"
  fi
}

# Validate a design's manifests against the standards BEFORE CI renders. This is
# the complement to readme-gate (which is presence-only, and runs post-render):
# it catches a malformed line while it is still cheap to fix, and it is what the
# --selftest exercises.
check_shots() {  # <conf> ; sets rc via `bad`
  local conf="$1" line name color finish camera size extra
  [[ -f "$conf" ]] || return 0
  local n=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    n=$((n+1))
    line="${line%%#*}"; [[ "$line" =~ [^[:space:]] ]] || continue
    # `_` absorbs the optional 6th (defines) field — not validated here,
    # product-shot.sh owns -D parsing — while `extra` catches a 7th field and
    # beyond. product-shot.sh reads exactly six fields, so a stray '|' after
    # defines would be folded into the defines value and emitted as a malformed
    # -D; reject it here rather than let `check` pass a line the render fails on.
    IFS='|' read -r name color finish camera size _ extra <<<"$line"
    name="${name//[[:space:]]/}"; color="${color//[[:space:]]/}"
    finish="${finish//[[:space:]]/}"; camera="${camera//[[:space:]]/}"
    size="${size//[[:space:]]/}"
    if [[ -z "$name" || -z "$color" || -z "$finish" || -z "$camera" || -z "$size" ]]; then
      echo "  FAIL $conf:$n — need 'name | color | finish | camera | size [| defines]'"; bad=1; continue
    fi
    if [[ -n "${extra//[[:space:]]/}" ]]; then
      echo "  FAIL $conf:$n — too many fields (a '|' after defines; product-shot.sh reads six)"; bad=1; continue
    fi
    is_kebab "$name"                || { echo "  FAIL $conf:$n — shot name '$name' not kebab-case"; bad=1; }
    [[ "$color" =~ ^[0-9a-fA-F]{6}$ ]] || { echo "  FAIL $conf:$n — color '$color' is not rrggbb (no '#')"; bad=1; }
    [[ " $FINISHES " == *" $finish "* ]] || { echo "  FAIL $conf:$n — finish '$finish' not one of: $FINISHES"; bad=1; }
    valid_camera "$camera"          || { echo "  FAIL $conf:$n — camera '$camera' not rotz,elev,zoom (zoom>0)"; bad=1; }
    valid_size "$size"              || { echo "  FAIL $conf:$n — size '$size' not a sane WxH"; bad=1; }
  done <"$conf"
}

check_lifestyle() {  # <conf>
  local conf="$1" line name seed prompt
  [[ -f "$conf" ]] || return 0
  local n=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    n=$((n+1))
    # Full-line comments only (a '#' can be scene content), matching
    # lifestyle-shot.sh.
    local trimmed="${line#"${line%%[![:space:]]*}"}"
    [[ -z "$trimmed" || "$trimmed" == '#'* ]] && continue
    [[ "$line" == *"|"* ]] || { echo "  FAIL $conf:$n — want '<shot> | <prompt>' or '<shot> | seed=<ref> | <prompt>'"; bad=1; continue; }
    parse_seedable_line "$line"; name="$PSL_name"; prompt="$PSL_prompt"
    is_kebab "$name" || { echo "  FAIL $conf:$n — scene name '$name' not kebab-case"; bad=1; }
    check_seed_field "$conf:$n" lifestyle
    [[ -n "$prompt" ]] || { echo "  FAIL $conf:$n — empty scene prompt"; bad=1; }
  done <"$conf"
}

check_stills() {  # <conf>
  local conf="$1" line name seed prompt
  [[ -f "$conf" ]] || return 0
  local n=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    n=$((n+1))
    local trimmed="${line#"${line%%[![:space:]]*}"}"
    [[ -z "$trimmed" || "$trimmed" == '#'* ]] && continue
    [[ "$line" == *"|"* ]] || { echo "  FAIL $conf:$n — want '<still> | seed=<ref> | <prompt>'"; bad=1; continue; }
    parse_seedable_line "$line"; name="$PSL_name"; prompt="$PSL_prompt"
    is_kebab "$name" || { echo "  FAIL $conf:$n — still name '$name' not kebab-case"; bad=1; }
    check_seed_field "$conf:$n" still
    [[ -n "$prompt" ]] || { echo "  FAIL $conf:$n — empty still prompt"; bad=1; }
  done <"$conf"
}

check_motion() {  # <conf>
  local conf="$1" line name seed prompt
  [[ -f "$conf" ]] || return 0
  local n=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    n=$((n+1))
    local trimmed="${line#"${line%%[![:space:]]*}"}"
    [[ -z "$trimmed" || "$trimmed" == '#'* ]] && continue
    [[ "$line" == *"|"* ]] || { echo "  FAIL $conf:$n — want '<shot> | <prompt>' or '<shot> | seed=<ref> | <prompt>'"; bad=1; continue; }
    parse_seedable_line "$line"; name="$PSL_name"; prompt="$PSL_prompt"
    is_kebab "$name" || { echo "  FAIL $conf:$n — clip name '$name' not kebab-case"; bad=1; }
    check_seed_field "$conf:$n" motion
    [[ -n "$prompt" ]] || { echo "  FAIL $conf:$n — empty motion prompt"; bad=1; }
  done <"$conf"
}

cmd_check() {
  local design="${1:-}"
  [[ -n "$design" ]] || die "usage: check <design>"
  require_design "$design"
  [[ -d "$ROOT/$design" ]] || die "no $ROOT/$design"
  local bad=0
  check_shots "$ROOT/$design/shots.conf"
  check_stills "$ROOT/$design/product-still.conf"
  check_lifestyle "$ROOT/$design/lifestyle.conf"
  check_motion "$ROOT/$design/motion.conf"
  if (( bad )); then
    echo "FAIL  $design: manifest problems above"
    return 1
  fi
  echo "ok    $design: shot manifests well-formed"
}

# ---- selftest ---------------------------------------------------------------
# Prove every validation and the freeze guard still fire. The repo's rule (see
# guard-check.sh, mate-check.sh, readme-gate --selftest): a check that guards
# something ships a firing negative test, because a weakened guard leaves every
# other check green. Wired into scripts/check.sh.
run_selftest() {
  local tmp; tmp="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap "rm -rf '$tmp'" RETURN
  local pass=1
  local root="$tmp/designs"
  mkdir -p "$root/gadget"

  # Every subcommand reads its design tree from SHOTSPEC_DESIGNS_DIR, so point it
  # at the fixture and the file-writing verbs land in $tmp, never the real tree.
  _run() {  # _run <expect-rc> <needle-or-empty> -- <args...>
    local want="$1" needle="$2"; shift 2; [[ "$1" == "--" ]] && shift
    local out rc=0
    out="$( SHOTSPEC_DESIGNS_DIR="$root" "$SELF" "$@" 2>&1 )" || rc=$?
    if [[ "$rc" != "$want" ]]; then
      echo "SELFTEST FAIL: [$*] expected rc $want got $rc"; sed 's/^/    /' <<<"$out"; pass=0; return
    fi
    if [[ -n "$needle" ]] && ! grep -qF "$needle" <<<"$out"; then
      echo "SELFTEST FAIL: [$*] output missing '$needle'"; sed 's/^/    /' <<<"$out"; pass=0; return
    fi
    echo "selftest ok    [$*] ${needle:+($needle)}"
  }

  # vocab commands work
  _run 0 "hero"   -- views
  _run 0 "forest" -- palette

  # add: happy path writes a valid line
  _run 0 "wrote entry" -- add gadget product-hero --view hero --color forest --finish satin --pose 'part="assembled"'
  if ! grep -qE '^product-hero \| 3a6b46 \| satin \| 35,18,0.90 \| 1280x960 \| part="assembled"$' "$tmp/designs/gadget/shots.conf"; then
    echo "SELFTEST FAIL: add did not write the expected manifest line"; sed 's/^/    /' "$tmp/designs/gadget/shots.conf"; pass=0
  else echo "selftest ok    add wrote the expected line"; fi

  # freeze: re-adding the same name refuses
  _run 1 "already has an entry" -- add gadget product-hero --view top --color amber
  # bad finish / view / color / size all refuse
  _run 1 "unknown finish" -- add gadget b --finish shiny
  _run 1 "unknown view"   -- add gadget b --view sideways
  _run 1 "unknown color"  -- add gadget b --color mauve
  _run 1 "bad size"       -- add gadget b --size 99999x10
  # pose rejects every char that would corrupt the manifest line
  _run 1 "has a space"    -- add gadget b --pose 'part="a" show="b"'
  _run 1 "field separator" -- add gadget b --pose 'part="a"|x'
  _run 1 "as a comment"    -- add gadget b --pose 'part="a"#x'
  # custom camera + hex color accepted
  _run 0 "wrote entry" -- add gadget top-down --camera 0,80,0.95 --color '#123456'

  # design-name traversal is refused by every verb before a path is built
  _run 1 "must be kebab-case" -- add ../scripts evil --view hero
  _run 1 "must be kebab-case" -- lifestyle ../scripts evil --scene "x"
  _run 1 "must be kebab-case" -- embed ../scripts evil
  _run 1 "must be kebab-case" -- check ../scripts

  # lifestyle: happy path + disclosure emitted + freeze + empty-scene refusal
  _run 0 "geometry is approximate" -- lifestyle gadget product-hero --scene "on a workbench under warm light"
  _run 1 "already has an entry"    -- lifestyle gadget product-hero --scene "again"
  _run 1 "needs --scene"           -- lifestyle gadget nostory

  # still (tier 1.5): happy path writes a seed= line + disclosure, then freeze,
  # missing-prompt, and the AI-seed refusal (a still stays geometry-pinned).
  _run 0 "geometry is approximate" -- still gadget hero-iso --seed product-hero --prompt "the bare part on a seamless white sweep"
  if ! grep -qE '^hero-iso \| seed=product-hero \| the bare part on a seamless white sweep$' "$tmp/designs/gadget/product-still.conf"; then
    echo "SELFTEST FAIL: still did not write the expected line"; sed 's/^/    /' "$tmp/designs/gadget/product-still.conf"; pass=0
  else echo "selftest ok    still wrote the expected line"; fi
  _run 1 "already has an entry"            -- still gadget hero-iso --seed product-hero --prompt "again"
  _run 1 "needs --prompt"                  -- still gadget nostory --seed product-hero
  _run 1 "must seed from a geometry-true"  -- still gadget badseed --seed lifestyle-x --prompt "x"
  _run 1 "must seed from a geometry-true"  -- still gadget badseed2 --seed product-still-x --prompt "x"
  # still defaults --seed to the still's own name when omitted
  _run 0 "wrote still" -- still gadget front --prompt "the bare part head-on, plain background"
  if ! grep -qE '^front \| seed=front \| the bare part head-on, plain background$' "$tmp/designs/gadget/product-still.conf"; then
    echo "SELFTEST FAIL: still default-seed line wrong"; sed 's/^/    /' "$tmp/designs/gadget/product-still.conf"; pass=0
  else echo "selftest ok    still defaulted seed to its own name"; fi

  # lifestyle --seed: emits a seed= line + rejects a lifestyle-* seed (a scene
  # may seed a product still, never another scene).
  _run 0 "geometry is approximate" -- lifestyle gadget on-desk --seed product-still-hero --scene "on a desk beside a laptop"
  if ! grep -qE '^on-desk \| seed=product-still-hero \| on a desk beside a laptop$' "$tmp/designs/gadget/lifestyle.conf"; then
    echo "SELFTEST FAIL: lifestyle --seed did not write the seed= line"; sed 's/^/    /' "$tmp/designs/gadget/lifestyle.conf"; pass=0
  else echo "selftest ok    lifestyle wrote the seed= line"; fi
  _run 1 "is a lifestyle-* scene" -- lifestyle gadget badscene --seed lifestyle-x --scene "x"

  # motion (tier 2 clip): happy path — an AI still IS a legal seed here — plus
  # freeze and missing-motion.
  _run 0 "geometry is approximate" -- motion gadget clip --seed lifestyle-on-desk --motion "a slow steady orbit"
  if ! grep -qE '^clip \| seed=lifestyle-on-desk \| a slow steady orbit$' "$tmp/designs/gadget/motion.conf"; then
    echo "SELFTEST FAIL: motion did not write the expected line"; sed 's/^/    /' "$tmp/designs/gadget/motion.conf"; pass=0
  else echo "selftest ok    motion wrote the expected line"; fi
  _run 1 "already has an entry" -- motion gadget clip --motion "again"
  _run 1 "needs --motion"       -- motion gadget nostory2 --seed lifestyle-on-desk

  # traversal guard on the new verbs
  _run 1 "must be kebab-case" -- still  ../scripts evil --prompt "x"
  _run 1 "must be kebab-case" -- motion ../scripts evil --motion "x"

  # check: passes on the good tree (now also covering product-still/motion/seeded-lifestyle)
  _run 0 "well-formed" -- check gadget

  # check: fails on a hand-corrupted line (bad finish, bad camera)
  printf 'busted | 3a6b46 | neon | 35,x,0.9 | 1280x960\n' >>"$tmp/designs/gadget/shots.conf"
  _run 1 "FAIL" -- check gadget

  # check: a valid 6-field line (with defines) passes, but a 7th field is
  # rejected — product-shot.sh reads exactly six fields.
  mkdir -p "$root/widget"
  printf 'hero | 3a6b46 | satin | 35,18,0.9 | 1280x960 | part="a"\n' >"$root/widget/shots.conf"
  _run 0 "well-formed" -- check widget
  printf 'hero | 3a6b46 | satin | 35,18,0.9 | 1280x960 | part="a" | oops\n' >"$root/widget/shots.conf"
  _run 1 "too many fields" -- check widget

  # check: the seed-aware validators fire on corrupt manifests (a fresh fixture
  # so it can't be masked by widget's already-corrupt shots.conf).
  mkdir -p "$root/still-check"
  # a product still seeding from an AI image -> rejected
  printf 'bad | seed=product-still-x | a bare part\n' >"$root/still-check/product-still.conf"
  _run 1 "geometry-true tier-1 render" -- check still-check
  # a lifestyle scene seeding from another scene -> rejected
  printf 'good | seed=product-hero | a bare part\n' >"$root/still-check/product-still.conf"
  printf 'bad | seed=lifestyle-x | a scene\n' >"$root/still-check/lifestyle.conf"
  _run 1 "is a lifestyle-* scene" -- check still-check
  # a motion clip with a non-kebab seed -> rejected
  rm -f "$root/still-check/lifestyle.conf"
  printf 'clip | seed=Bad_Seed | a motion\n' >"$root/still-check/motion.conf"
  _run 1 "seed 'Bad_Seed' not kebab-case" -- check still-check
  # a motion clip seeding from an AI still is FINE (the still->clip hop) -> passes
  printf 'clip | seed=lifestyle-x | a motion\n' >"$root/still-check/motion.conf"
  _run 0 "well-formed" -- check still-check

  # malformed seed= forms are rejected before a paid CI generation (matching the
  # generators' runtime guards): an empty 'seed=' value, and a 'seed=ref' with no
  # trailing '| <prompt>'. One per tier so each validator's check_seed_field fires.
  rm -f "$root/still-check/motion.conf"
  printf 'hero | seed= | a bare part\n' >"$root/still-check/product-still.conf"
  _run 1 "empty 'seed='" -- check still-check
  printf 'hero | seed=product-hero\n' >"$root/still-check/product-still.conf"
  _run 1 "without a following" -- check still-check
  printf 'good | seed=product-hero | a bare part\n' >"$root/still-check/product-still.conf"
  printf 'scene | seed= | a scene\n' >"$root/still-check/lifestyle.conf"
  _run 1 "empty 'seed='" -- check still-check
  printf 'scene | seed=product-hero\n' >"$root/still-check/lifestyle.conf"
  _run 1 "without a following" -- check still-check
  rm -f "$root/still-check/lifestyle.conf"
  printf 'clip | seed= | a motion\n' >"$root/still-check/motion.conf"
  _run 1 "empty 'seed='" -- check still-check

  if (( pass )); then echo "ok    shot-spec --selftest: every validator and the freeze guard fire"; return 0; fi
  echo "FAIL  shot-spec --selftest"; return 1
}

# Absolute path to self so --selftest can invoke subcommands from the fixture CWD.
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"

case "${1:-}" in
  views)      shift; cmd_views "$@";;
  palette)    shift; cmd_palette "$@";;
  add)        shift; cmd_add "$@";;
  still)      shift; cmd_still "$@";;
  lifestyle)  shift; cmd_lifestyle "$@";;
  motion)     shift; cmd_motion "$@";;
  embed)      shift; cmd_embed "$@";;
  check)      shift; cmd_check "$@";;
  --selftest) run_selftest;;
  ""|-h|--help)
    sed -n '2,48p' "$SELF" | sed 's/^# \{0,1\}//'
    ;;
  *) die "unknown command '$1' — try: views, palette, add, still, lifestyle, motion, embed, check, --selftest";;
esac
