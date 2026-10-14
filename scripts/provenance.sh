#!/usr/bin/env bash
# provenance.sh — the repo-script face of the provenance harvester
# (tools/provenance, docs/provenance.md): the keyless, deterministic harvester
# that freezes who/how evidence onto the add-only `provenance` data branch and
# derives per-design views onto `provenance-site`.
#
#   scripts/provenance.sh --selftest
#     The offline negative-control suite (python3 -m provenance selftest): the
#     add-only guard (D / M outside state.json / 0-byte blob / guard-file
#     change), tip continuity (foreign / deleted / bootstrap / declared),
#     recover refusing an undeclared sha, the membership-rule and trust-rule
#     negatives. No network, no GitHub token, a throwaway temp repo. Run by
#     scripts/check.sh.
#
#   scripts/provenance.sh <subcommand> [args…]
#     Passes through to `python3 -m provenance` with the PYTHONPATH the
#     workflow uses (tools/provenance/src + tools/model-registry/src).
#
# SCAFFOLD STATE: the package's modules are interface skeletons until the
# P0/P1 builders land them (WORKPLAN, builder H6 owns this script). Until
# then --selftest reports the scaffold and exits 0 so check.sh stays green;
# H6 replaces the scaffold branch below with the real call and wires this
# script into scripts/check.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONPATH="$PWD/tools/provenance/src:$PWD/tools/model-registry/src${PYTHONPATH:+:$PYTHONPATH}"

case "${1:-}" in
  --selftest)
    echo "ok    provenance --selftest: scaffold (builder H6 wires python3 -m provenance selftest)"
    exit 0 ;;
  ""|-h|--help)
    sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
    exit 0 ;;
  -*)
    echo "provenance.sh: unknown option $1" >&2
    exit 2 ;;
  *)
    exec python3 -m provenance "$@" ;;
esac
