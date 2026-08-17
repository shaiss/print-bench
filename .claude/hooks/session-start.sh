#!/bin/bash
# SessionStart hook: install the OpenSCAD toolchain in Claude Code on the web.
# The repo needs: openscad (renderer), xvfb (headless display), imagemagick
# (montage, for multi-view preview sheets), prusa-slicer + printcheck (so
# ./scripts/gate.sh --slice — the exact gate CI runs — works locally before
# a push), plus ffmpeg + gifsicle (the clip pipeline behind
# scripts/lifestyle-clip.sh; gifsicle also closes the local/CI GIF-size
# asymmetry — animate.sh only shrinks when it is present, and CI always has
# it). Idempotent — exits fast when everything is already present
# (e.g. cached container state).
#
# bpy (Blender as a Python module, behind ./scripts/product-shot.sh) is NOT
# installed by default any more. CI's `regen` job renders and commits the
# product shots now, so a session no longer needs a ~1 GB wheel to produce a
# deliverable — it needed one to produce an artifact CI could have made.
# Pass --with-bpy (or set INSTALL_BPY=1) when you want to preview a shot
# locally before pushing; nothing in the repo's gates requires it. On a local
# machine that means `--force --with-bpy`: without --force the guard below
# exits before installing anything, so --with-bpy on its own is a no-op there.
set -euo pipefail

WITH_BPY="${INSTALL_BPY:-0}"
FORCED=0
for arg in "$@"; do
  case "$arg" in
    # --force: install even outside Claude Code on the web (manual
    # invocation); without it the hook is a silent no-op on local machines.
    --force)    FORCED=1 ;;
    --with-bpy) WITH_BPY=1 ;;
  esac
done
if [ "$FORCED" != 1 ] && [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# find_spec rather than `import bpy`: importing Blender costs seconds and
# hundreds of MB, and this guard runs on every session start.
has_bpy() {
  python3 -c 'import importlib.util,sys; sys.exit(0 if importlib.util.find_spec("bpy") else 1)' \
    >/dev/null 2>&1
}

if command -v openscad >/dev/null 2>&1 \
  && command -v xvfb-run >/dev/null 2>&1 \
  && command -v montage >/dev/null 2>&1 \
  && command -v ffmpeg >/dev/null 2>&1 \
  && command -v gifsicle >/dev/null 2>&1 \
  && { [ "$WITH_BPY" != 1 ] || has_bpy; } \
  && command -v prusa-slicer >/dev/null 2>&1 \
  && command -v printcheck >/dev/null 2>&1 \
  && command -v stylelift >/dev/null 2>&1 \
  && command -v pytest >/dev/null 2>&1; then
  echo "OpenSCAD toolchain already installed"
  exit 0
fi

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
fi

export DEBIAN_FRONTEND=noninteractive
# Package indexes in the base image can be stale (404s on install); refresh
# first and tolerate unrelated repo failures (e.g. blocked PPAs).
$SUDO apt-get update -qq 2>/dev/null || true
$SUDO apt-get install -y -qq openscad xvfb imagemagick prusa-slicer ffmpeg gifsicle jq

# Blender ships on PyPI as `bpy`, a self-contained Python module — no apt
# package, no X display. Pinned to the 4.5 LTS series: product shots are
# byte-reproducible across point releases within a series, but not necessarily
# across them, and the committed PNGs are diffed. Wheels are built per Python
# minor version, so this needs the interpreter Blender 4.5 targets (3.11).
#
# `python3 -m pip`, never bare `pip`: they are not always the same interpreter
# (here python3 is /usr/local/bin/python3 while pip is /usr/bin/pip), and bpy is
# a compiled extension. Installing with one interpreter and importing with
# another gives a "successful" install that cannot be imported. The check below
# is the same python3 that scripts/product-shot.sh runs, so a mismatch fails
# here rather than mid-render.
if [ "$WITH_BPY" = 1 ] && ! has_bpy; then
  python3 -m pip install -q 'bpy~=4.5.0'
  if ! python3 -c 'import bpy' >/dev/null 2>&1; then
    echo "error: bpy installed but will not import under $(python3 -V 2>&1)." >&2
    echo "       bpy 4.5 ships wheels for Python 3.11 only." >&2
    exit 1
  fi
fi

# [test] extra brings pytest, so /preflight can run the unit tests locally
# exactly as CI does
if ! command -v printcheck >/dev/null 2>&1 || ! command -v pytest >/dev/null 2>&1; then
  pip install -q -e "$REPO_DIR/tools/printcheck[test]"
fi
# stylelift backs scripts/style-lift.sh and the style gate; same mesh stack
if ! command -v stylelift >/dev/null 2>&1; then
  pip install -q -e "$REPO_DIR/tools/stylelift[test]"
fi

echo "Installed: $(openscad --version 2>&1); prusa-slicer + printcheck + stylelift ready"
