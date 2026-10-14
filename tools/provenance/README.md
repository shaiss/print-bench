# provenance — the keyless who/how harvester

The who/how record every design page's "How it was made" section will read
(P3, not built yet) — who filed the brief, which routine and model built it,
every review round and which sign-offs are trustworthy, when it merged and
deployed — is produced by this tool. It runs in
`.github/workflows/provenance.yml` with no secret but `GITHUB_TOKEN` and no
LLM anywhere, freezes structured facts once after a settle window, and writes
them to two data refs. The design of record is
[docs/provenance.md](../../docs/provenance.md); the closed machine-readable
contract both Python and Node validate against is
[site/lib/provenance-contract.json](../../site/lib/provenance-contract.json);
the policy is [.github/provenance.conf](../../.github/provenance.conf).

| Ref | Kind | What |
|---|---|---|
| `provenance` | evidence, linear, add-only | run receipts (complete Actions jobs responses — GitHub deletes runs after 90 days), digested API payloads per frozen PR / brief / release, the ingested #843 snapshot (read from main, pinned by its manifest digest), `state.json` |
| `provenance-site` | derived, one squashed commit | `records/`, `views/<design>.json`, `site/bundle.json` — recomputed from (evidence tip, main sha, extractor version) |

Prose is never stored: every comment, issue, review and commit-message body
is replaced at capture by a digest (`digest.py`) carrying only marker lines,
the trust suffix, triage verdict cells, a classified lead line and a few
validated fields.

## CLI

```bash
export PYTHONPATH=tools/provenance/src:tools/model-registry/src

python3 -m provenance harvest --out-dir .provenance [--since 2026-07-31] \
    [--until …] [--pr 636,371] [--receipts-only] [--max-requests N] [--dry-run] \
    [--scheduled] [--bootstrap]                           # ingests the #843 snapshot on its first run
python3 -m provenance refreeze --pr 636 --out-dir .provenance
python3 -m provenance publish --out-dir .provenance      # push what plan.json says, then checkpoints
python3 -m provenance recover --confirm-sha <sha40>      # break-glass: the newest checkpoint only
python3 -m provenance gate --scheduled                   # the workflow's gate job
python3 -m provenance check --dir <tree> --kind evidence # validate a checked-out data-ref tree
python3 -m provenance selftest                           # offline negative controls
```

`harvest`, `refreeze` and `recover` only PLAN: they build the new commits
locally, write `plan.json` and the intent files, and stop. The workflow
uploads the intent artifacts (`intent-<ref>-<sha40>`), runs `publish`, and
then uploads the checkpoints (`tip-<ref>-<sha40>`) naming the verified tips —
tip continuity anchors on the newest checkpoint (docs/provenance.md §Tip
continuity). There is no ingest mode: `harvest` ingests the snapshot from the
default-branch checkout when `state.json` has not recorded it.

## Module map

See the docstring of `src/provenance/__init__.py` for the module → role →
owner table. `canonical`, `digest`, `steps`, `rawdoc` and `protocols` are
implemented in full (every fixture's bytes depend on them), as is the pure
tip-continuity rule `gitstore.continuity_verdict` with its shared case table
`tests/fixtures/continuity_cases.json` (Reeve's detector passes the same
table); the rest are interface skeletons with complete docstrings until the
P0/P1 builders land them.

## Tests

```bash
python3 -m pytest tools/provenance -q
```

`tests/test_purity.py` holds the boundaries from day one: network only in
`github.py`, subprocess only in `gitstore.py`, the clock only in `cli.py` /
`github.py`, no randomness, no HTTP write verb but the one read-only GraphQL
query. Fixtures under `tests/fixtures/` are produced by
`tests/dev/build_fixtures.py` from an uncommitted GET-only capture (bodies
included) and contain no prose (`tests/test_fixtures.py` checks); the
audit's golden timelines and membership labels are read in place from
`audits/provenance-2026-10/fixtures/`.

Stdlib-only, like `tools/andon` and `tools/reeve`: the workflow runs it from
the checkout on the system Python with no pip step.
