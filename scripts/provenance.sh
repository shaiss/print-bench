#!/usr/bin/env bash
# provenance.sh — the repo-script face of the provenance harvester
# (tools/provenance, docs/provenance.md): the keyless, deterministic harvester
# that freezes who/how evidence onto the add-only `provenance` data branch and
# derives per-design views onto `provenance-site`.
#
#   scripts/provenance.sh --selftest
#     The offline negative-control suite (python3 -m provenance selftest): the
#     add-only guard (D / M outside state.json / 0-byte blob / guard-file
#     change), every row of the tip-continuity table (ok / foreign / rollback /
#     deleted / unanchored / bootstrap), a rejected push refused, no token in a
#     failing push's error, the membership-rule and trust-rule negatives. No
#     network, no GitHub token, a throwaway temp repo. One `selftest ok|FAIL
#     <label>` line per case; exits non-zero when any case failed or a module
#     could not supply its cases (a missing case is a FAIL, never a skip). Run
#     by scripts/check.sh.
#
#   scripts/provenance.sh <subcommand> [args…]
#     Passes through to `python3 -m provenance` with the PYTHONPATH the
#     workflow uses (tools/provenance/src + tools/model-registry/src).
#
# Stdlib only — no pip step: the package runs from the checkout on the system
# Python, exactly as .github/workflows/provenance.yml runs it.
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONPATH="$PWD/tools/provenance/src:$PWD/tools/model-registry/src${PYTHONPATH:+:$PYTHONPATH}"

case "${1:-}" in
  --selftest)
    exec python3 -m provenance selftest ;;
  ""|-h|--help)
    sed -n '2,23p' "$0" | sed 's/^# \{0,1\}//'
    exit 0 ;;
  -*)
    echo "provenance.sh: unknown option $1" >&2
    exit 2 ;;
  *)
    exec python3 -m provenance "$@" ;;
esac
