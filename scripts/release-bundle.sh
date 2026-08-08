#!/usr/bin/env bash
# Build a versioned, self-describing release bundle for a design: the gated
# printable STL(s) + a manifest.json (design, version, per-part SHA-256
# checksums and byte sizes, and the machine-readable print settings lifted
# from the README) + a zip, under build/release/<design>-<version>/.
#
# This is the BUILD half of issue #102 (versioned releases & download UX): the
# release workflow (.github/workflows/release.yml) runs gate.sh first so only
# gated geometry ever ships, then this to assemble what gets attached to the
# tagged GitHub Release. The SITE half — site.sh consuming the manifest to
# render per-part download links on product pages — is the deferred follow-up.
#
#   ./scripts/release-bundle.sh <name> [--version <v>]   # one design
#   ./scripts/release-bundle.sh --all   [--version <v>]  # every active design
#   ./scripts/release-bundle.sh --selftest               # offline mechanism test
#
# Parts mirror gate.sh exactly: the ci.parts entries (rendered via
# -D part="..."), or the default render when a design ships no ci.parts, plus
# the <name>-coupon when a coupon wrapper exists. An STL already in build/
# (gate.sh's output) is reused as-is; a missing one is rendered here through
# $OPENSCAD_BIN, so the script is self-contained locally and cheap in CI.
#
# Archive freeze (CLAUDE.md): a design carrying designs/<name>/ARCHIVED is
# frozen at v0.1 and is never re-rendered, so it is skipped with a notice — it
# keeps whatever release it already has.
#
# Overridable for the selftest (and only for it): RELEASE_BUNDLE_DESIGNS_DIR
# points the part enumeration at a fixture tree, RELEASE_BUNDLE_BUILD_DIR moves
# both the STL inputs and the release output out of the real build/. Default
# behavior — designs/ and build/ — is unchanged when neither is set.
set -euo pipefail

# Absolute path to this script, captured before the cd so --selftest can
# re-invoke against fixture trees from any CWD (mirrors readme-gate.sh).
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"

cd "$(dirname "$0")/.."
# lib/ resolves `use <printability.scad>`; the repo root resolves
# `include <styles/<name>/style.scad>` — same as gate.sh, for the render
# fallback below.
export OPENSCADPATH="$PWD/lib:$PWD"

# OPENSCAD_BIN selects the binary (e.g. openscad-nightly); OPENSCAD_ARGS passes
# extra flags (e.g. --backend=manifold). Both default to the stable invocation,
# exactly as gate.sh / check.sh do.
OPENSCAD_BIN="${OPENSCAD_BIN:-openscad}"
read -ra OSC_ARGS <<<"${OPENSCAD_ARGS:-}"

DESIGNS="${RELEASE_BUNDLE_DESIGNS_DIR:-designs}"
BUILD="${RELEASE_BUNDLE_BUILD_DIR:-build}"

usage() {
  sed -n '2,20p' "$SELF" | sed 's/^# \{0,1\}//'
}

render_part() {   # render_part <name> <part-or-empty> <out-stl>
  local name="$1" part="$2" out="$3"
  local src="${DESIGNS}/${name}/${name}.scad"
  local dargs=()
  [[ -n "$part" ]] && dargs=(-D "part=\"${part}\"")
  echo "== ${name}$([[ -n "$part" ]] && echo " (part=${part})"): render =="
  xvfb-run -a "$OPENSCAD_BIN" ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
    ${dargs[@]+"${dargs[@]}"} -o "$out" "$src"
}

render_coupon() { # render_coupon <name> <out-stl>
  local name="$1" out="$2"
  echo "== ${name} (coupon): render =="
  xvfb-run -a "$OPENSCAD_BIN" ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
    -o "$out" "${DESIGNS}/${name}/${name}-coupon.scad"
}

# Emit the manifest.json into <outdir> and the zip alongside it. Python does
# the checksum, print-settings parse and zip so string escaping and hashing are
# not hand-rolled in bash. Reads the part list (label<TAB>filename) from the
# file named in argv, not stdin (stdin is the program heredoc).
write_manifest_and_zip() {   # <name> <version> <outdir> <readme> <partsfile> <zip>
  python3 - "$@" <<'PY'
import hashlib, json, os, re, sys, zipfile

name, version, outdir, readme, partsfile, zippath = sys.argv[1:7]

def parse_print_settings(path):
    settings = {}
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return settings
    in_sec = False
    cur = None
    for ln in lines:
        if re.match(r"^##\s+print settings\s*$", ln.strip(), re.I):
            in_sec, cur = True, None
            continue
        if in_sec and re.match(r"^##\s", ln):        # next section ends it
            break
        if not in_sec:
            continue
        m = re.match(r"^\s*[-*]\s+\*\*(.+?):\*\*\s*(.*)$", ln)
        if m:
            key = re.sub(r"[^a-z0-9]+", "_", m.group(1).strip().lower()).strip("_")
            settings[key] = m.group(2).strip()
            cur = key
        elif cur and ln.strip() and not re.match(r"^\s*([-*]|#)", ln):
            settings[cur] = (settings[cur] + " " + ln.strip()).strip()  # wrapped line
        elif not ln.strip():
            cur = None                                # blank line ends a bullet
    return settings

parts = []
with open(partsfile, encoding="utf-8") as fh:
    for line in fh:
        line = line.rstrip("\n")
        if not line:
            continue
        label, fname = line.split("\t", 1)
        blob = open(os.path.join(outdir, fname), "rb").read()
        parts.append({
            "part": label,
            "file": fname,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "size": len(blob),
        })

manifest = {
    "design": name,
    "version": version,
    "generated_by": "scripts/release-bundle.sh",
    "part_count": len(parts),
    "parts": parts,
    "print_settings": parse_print_settings(readme),
}

with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, ensure_ascii=False)
    fh.write("\n")

with zipfile.ZipFile(zippath, "w", zipfile.ZIP_DEFLATED) as z:
    for fn in sorted(os.listdir(outdir)):
        z.write(os.path.join(outdir, fn), arcname=f"{name}-{version}/{fn}")
PY
}

bundle_one() {    # bundle_one <name> <version>
  local name="$1" version="$2"
  local ddir="${DESIGNS}/${name}"
  local src="${ddir}/${name}.scad"
  if [[ ! -f "$src" ]]; then
    echo "skip ${name}: ${src} not found"
    return 0
  fi
  if [[ -f "${ddir}/ARCHIVED" ]]; then
    echo "::notice::skip ${name}: archived at $(head -1 "${ddir}/ARCHIVED") — frozen, keeps its last release, not re-rendered"
    return 0
  fi

  local outdir="${BUILD}/release/${name}-${version}"
  rm -rf "$outdir"
  mkdir -p "$outdir"

  # Enumerate the gated parts the same way gate.sh does.
  local labels=() dvals=() files=()
  if [[ -f "${ddir}/ci.parts" ]]; then
    local p
    while read -r p || [[ -n "$p" ]]; do
      [[ -z "$p" || "$p" == \#* ]] && continue
      labels+=("$p"); dvals+=("part:$p"); files+=("${name}-${p}.stl")
    done < "${ddir}/ci.parts"
  else
    labels+=("$name"); dvals+=("default"); files+=("${name}.stl")
  fi
  if [[ -f "${ddir}/${name}-coupon.scad" ]]; then
    labels+=("coupon"); dvals+=("coupon"); files+=("${name}-coupon.stl")
  fi

  local partsfile
  partsfile="$(mktemp)"
  local i
  for i in "${!labels[@]}"; do
    local label="${labels[$i]}" dval="${dvals[$i]}" fname="${files[$i]}"
    local buildstl="${BUILD}/${fname}" outstl="${outdir}/${fname}"
    if [[ ! -f "$buildstl" ]]; then
      # Not gated into build/ yet (local standalone run): render it here,
      # identically to gate.sh, so the script is self-contained.
      case "$dval" in
        coupon)  render_coupon "$name" "$buildstl" ;;
        default) render_part "$name" "" "$buildstl" ;;
        part:*)  render_part "$name" "${dval#part:}" "$buildstl" ;;
      esac
    fi
    cp "$buildstl" "$outstl"
    printf '%s\t%s\n' "$label" "$fname" >> "$partsfile"
  done

  local zip="${BUILD}/release/${name}-${version}.zip"
  local mcopy="${BUILD}/release/${name}-${version}.manifest.json"
  write_manifest_and_zip "$name" "$version" "$outdir" "${ddir}/README.md" "$partsfile" "$zip"
  cp "${outdir}/manifest.json" "$mcopy"
  rm -f "$partsfile"
  echo "ok    ${name}: bundled ${#labels[@]} part(s) at ${version} -> ${zip}"
}

# --- selftest: prove the mechanism offline, no render, no network, no release.
# Points the enumeration at a fixture designs/ tree and pre-seeds fixture STLs
# into a fixture build/ so no OpenSCAD runs, then asserts: the manifest names
# every part, each recorded sha256 recomputes over the bundled STL, the print
# settings are lifted from the fixture README, the zip is produced, and an
# ARCHIVED fixture is skipped (never bundled). This is the half the real tree
# cannot cover — designs/ ships no release bundle, so without it the whole
# builder could be weakened and every gate stays green.
run_selftest() {
  local tmp
  tmp="$(mktemp -d)"
  # shellcheck disable=SC2064  # expand $tmp now, when the trap is installed
  trap "rm -rf '$tmp'" RETURN
  local d="$tmp/designs" b="$tmp/build"
  mkdir -p "$d/gizmo" "$d/frozen" "$b"

  # Fixture design with a ci.parts (two parts) and a canonical Print settings
  # section, plus pre-seeded "gated" STLs so no render happens.
  printf 'base\nlid\n' > "$d/gizmo/ci.parts"
  : > "$d/gizmo/gizmo.scad"
  {
    printf '# gizmo\n\nA throwaway fixture for the release-bundle selftest.\n\n'
    printf '## Print settings\n\n'
    printf -- '- **Material:** PLA or PETG\n'
    printf -- '- **Layer height:** 0.2 mm (fixture value that wraps\n'
    printf '  onto a second line)\n'
    printf -- '- **Supports:** none needed\n'
    printf -- '- **Orientation:** flat face down as modeled\n\n'
    printf '## Parameters\n\n- `wall` — wall thickness (mm)\n'
  } > "$d/gizmo/README.md"
  printf 'solid base\nendsolid base\n' > "$b/gizmo-base.stl"
  printf 'solid lid xyz\nendsolid lid\n' > "$b/gizmo-lid.stl"

  # Archived fixture: must be skipped, never bundled.
  printf 'v0.1\nfrozen fixture\n' > "$d/frozen/ARCHIVED"
  : > "$d/frozen/frozen.scad"
  printf '# frozen\n\nArchived fixture.\n\n## Print settings\n\n- **Supports:** none\n\n## Parameters\n\n- none\n' \
    > "$d/frozen/README.md"

  local pass=1
  fail_msg() { echo "SELFTEST FAIL  $1"; pass=0; }

  RELEASE_BUNDLE_DESIGNS_DIR="$d" RELEASE_BUNDLE_BUILD_DIR="$b" \
    bash "$SELF" gizmo --version v9.9 >/dev/null

  local outdir="$b/release/gizmo-v9.9" mf="$b/release/gizmo-v9.9/manifest.json"
  [[ -f "$mf" ]] || fail_msg "no manifest at $mf"
  [[ -f "$b/release/gizmo-v9.9.zip" ]] || fail_msg "no zip produced"
  [[ -f "$b/release/gizmo-v9.9.manifest.json" ]] || fail_msg "no standalone manifest copy"

  if [[ -f "$mf" ]]; then
    # Every recorded checksum must recompute over the bundled STL, and the
    # fields must be exactly what was asked for — verified, not asserted.
    python3 - "$mf" "$outdir" <<'PY' || fail_msg "manifest content checks failed"
import hashlib, json, sys
mf, outdir = sys.argv[1], sys.argv[2]
m = json.load(open(mf))
ok = True
def bad(msg):
    global ok; ok = False; print("    " + msg)
if m.get("design") != "gizmo": bad(f'design={m.get("design")!r} != gizmo')
if m.get("version") != "v9.9": bad(f'version={m.get("version")!r} != v9.9')
if m.get("part_count") != 2: bad(f'part_count={m.get("part_count")!r} != 2')
labels = sorted(p["part"] for p in m["parts"])
if labels != ["base", "lid"]: bad(f'parts={labels} != [base, lid]')
import os
for p in m["parts"]:
    blob = open(os.path.join(outdir, p["file"]), "rb").read()
    if hashlib.sha256(blob).hexdigest() != p["sha256"]:
        bad(f'{p["file"]}: sha256 does not match the bundled bytes')
    if p["size"] != len(blob):
        bad(f'{p["file"]}: size {p["size"]} != {len(blob)}')
ps = m.get("print_settings", {})
if ps.get("material") != "PLA or PETG": bad(f'material={ps.get("material")!r}')
if ps.get("supports") != "none needed": bad(f'supports={ps.get("supports")!r}')
if ps.get("orientation") != "flat face down as modeled": bad(f'orientation={ps.get("orientation")!r}')
# the wrapped bullet must be folded into one value
if ps.get("layer_height") != "0.2 mm (fixture value that wraps onto a second line)":
    bad(f'layer_height not folded: {ps.get("layer_height")!r}')
sys.exit(0 if ok else 1)
PY
  fi

  # Archive freeze: bundling an archived design writes nothing and skips.
  local out
  out="$(RELEASE_BUNDLE_DESIGNS_DIR="$d" RELEASE_BUNDLE_BUILD_DIR="$b" \
    bash "$SELF" frozen --version v9.9 2>&1)"
  if [[ -e "$b/release/frozen-v9.9" || -e "$b/release/frozen-v9.9.zip" ]]; then
    fail_msg "archived design 'frozen' was bundled despite the freeze"
  fi
  grep -q "archived" <<<"$out" || fail_msg "archived skip printed no notice: $out"

  if [[ "$pass" == 1 ]]; then
    echo "ok    release-bundle --selftest: manifest, checksums, print settings, zip and archive-skip all hold"
    return 0
  fi
  echo "FAIL  release-bundle --selftest: a mechanism check did not hold"
  return 1
}

# --- argument handling
VERSION="v0.1"
ALL=0
names=()
if [[ "${1:-}" == "--selftest" ]]; then
  run_selftest
  exit $?
fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    --all) ALL=1 ;;
    --version) shift; VERSION="${1:?--version needs a value}" ;;
    --version=*) VERSION="${1#--version=}" ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "error: unknown flag $1" >&2; exit 2 ;;
    *) names+=("$1") ;;
  esac
  shift
done

mkdir -p "${BUILD}/release"

if [[ "$ALL" == 1 ]]; then
  if [[ ${#names[@]} -gt 0 ]]; then
    echo "error: --all takes no design names" >&2; exit 2
  fi
  shopt -s nullglob
  for dir in "${DESIGNS}"/*/; do
    n="$(basename "$dir")"
    [[ -f "${DESIGNS}/${n}/${n}.scad" ]] || continue
    bundle_one "$n" "$VERSION"
  done
elif [[ ${#names[@]} -ge 1 ]]; then
  for n in "${names[@]}"; do
    bundle_one "$n" "$VERSION"
  done
else
  echo "error: name a design, or pass --all (see --help)" >&2
  exit 2
fi
