# backlog-groomer

The deterministic backlog-health report behind the scheduled **Backlog
groomer** workflow (`.github/workflows/backlog-groomer.yml`, issue #244),
with the optional fast-model **narrative layer** of #248 on top.

The autonomy routines — backlog burn (#95), design run (#96), the chunker —
all feed one issue queue; this tool tends it. It owns only a *report*: every
finding is a recomputable fact about timestamps, labels, and links (no LLM
in any finding), and the routine is **advisory-only** — the tool performs
GET-only reads of GitHub, and the workflow's single GitHub write is
upserting one sticky report issue. Nothing else is labeled, closed, or
commented on. The narrative layer (below) is the one model call, it only
*phrases* the deterministic findings, and it defaults **off**.

## The detectors

Each is a pure function of the snapshot, provable to fire and to stay
silent (`tests/test_detectors.py` keeps a positive case and a negative
control per detector — delete a detector's condition and one half fails):

1. **stale** — open issue with no update in > `staleness_days`.
2. **armed-stuck** — `autonomy-ok`, quiet for > `armed_stuck_days`, with no
   open PR closing it (nine GitHub keywords, number compared as an int so
   `fixes #24` never half-matches #244): the burn is disarmed, failing, or
   stuck on it. `updatedAt` is the label-age proxy (labeling bumps it), so
   a month-old issue armed today reads as fresh; like `unchunked-oversized`
   it errs quiet — activity resets the clock.
3. **unsized-armed** — `autonomy-ok` without a `points-<n>` label, which the
   roadmap board (#148) needs.
4. **decision-resolved-parked** — `needs-decision` plus a
   `decision-approved`/`decision-rejected` verdict (#161): the human
   answered and nobody resumed.
5. **unchunked-oversized** — `declined-too-big` quiet for >
   `oversized_stuck_days` (`updatedAt` is the proxy; it errs quiet).
6. **dup-candidates** — open-issue pairs with title-token Jaccard ≥
   `dup_threshold`, capped at `max_dup_pairs` **with the cap disclosed**
   ("showing N of M") — no silent truncation.
7. **epic-complete** — every native sub-issue closed; closing stays the
   human's call, the groomer only surfaces it.

A detector whose input is absent from the snapshot renders **"not
evaluated"** with the reason, never silently empty — an empty section must
mean "checked, clean".

## The narrative layer (#248, optional, default off)

A 3–5 sentence *"this week's focus"* paragraph at the top of the report,
written by a fast model over the **rendered report and nothing else**. The
division of labor is #244's locked design: substance stays deterministic —
the narrative may only summarize/prioritize findings the detectors already
surfaced, and a narrative claim with no corresponding finding is a bug.
This is the cheap-to-be-wrong tier (the product-scout's #229 reasoning):
a clumsy summary costs nothing because the facts are all still there,
deterministic, below it — which is also why there is no fallback chain, a
failed call simply produces no narrative.

How each property is held:

- **Phrasing-only by construction.** The model's sole input is the
  rendered report body; the system prompt forbids inventing any number,
  issue, label, or title not literally in it. `generate()` has no
  snapshot parameter at all — there is no code path that could hand the
  model the raw data.
- **Byte-identical deterministic sections.** The narrative is emitted
  between HTML-comment markers immediately below the report's upsert
  marker and above `## Summary`; `strip_narrative()` removes exactly that
  span, and the tests hold `strip(insert(report)) == report` for the
  golden fixture — whatever the model wrote.
- **Fail-soft.** No key, a transport error, an empty or over-cap answer →
  no narrative, `::notice::`, exit 0, the deterministic report posts
  unchanged. The layer can never take the report down with it.
- **Model from the #206 registry.** `backlog-groomer narrative` resolves
  its model from `.github/models/registry.conf`'s `groomer-narrative`
  chain (first link — cheapest capable), so swapping the model is a
  registry edit, not a code edit. The provider's key is read from the
  env var named by the registry (`ZAI_KEY` / `ANTHROPIC_API_KEY`).
- **Arming.** Three keys must agree before any provider key is touched:
  the groomer's own two (conf `enabled` + repo variable) **and**
  `narrative: true` in the conf **and** the provider's secret present.
  Every other combination is a `::notice::` skip with the report
  unaffected.

```bash
# offline: the whole pipeline (placement, markers, disclosure), no key
backlog-groomer narrative --report report.md --mock
# live: conf-gated, registry-resolved, fail-soft
ZAI_KEY=… backlog-groomer narrative --report report.md --conf .github/backlog-groomer.conf
```

The one POST in the package is `_post_message`, the model-API seam in
`narrative.py` — confined there by a test (AST-checked: the verb lives in
the seam function and nowhere else), while `github.py` stays GET-only and
the workflow's upsert stays the sole GitHub write.

## Usage

```bash
pip install -e 'tools/backlog-groomer[test]'

backlog-groomer report --input snapshot.json --out report.md   # pure render
backlog-groomer gather --repo owner/name > snapshot.json       # GET-only live read
backlog-groomer run --repo owner/name --conf .github/backlog-groomer.conf --out report.md
backlog-groomer narrative --report report.md [--mock]          # the #248 layer
backlog-groomer config --get staleness_days --path .github/backlog-groomer.conf
backlog-groomer armed --variable "$BACKLOG_GROOMER_ENABLED" --conf-enabled true
```

The report's first line is the upsert marker
(`<!-- backlog-groomer-report -->`); the workflow finds the one report issue
it owns by that marker plus the `groomer-report` label, creates it once, and
edits it forever after. An all-clean report still posts — "grooming ran,
nothing found" is a real answer, and the sticky issue's edit history is the
proof of life.

## Config: where the on/off and the thresholds live

```text
enabled: true
cadence: 41 5 * * *
narrative: false
provider: zai
staleness_days: 14
armed_stuck_days: 7
oversized_stuck_days: 7
dup_threshold: 0.6
max_dup_pairs: 10
```

Strict on purpose: unknown keys, duplicates, and malformed values raise
with `path:lineno`; an absent `enabled` reads as **off**, and so does an
absent `narrative`. `narrative: true` requires a `provider:` (one of
`zai`, `anthropic` — the providers with a reviewed workflow ship step);
the parser rejects the combination that would leave the step guessing.
Arming is two keys — the conf's `enabled` **and** the
`BACKLOG_GROOMER_ENABLED` repo variable must both be `true`
(`backlog-groomer armed` is the tested decision) — so a clone or fork can
never silently arm the routine. This is the groomer's own parser, not a
reuse of `tools/backlog-burn`'s: that parser's key set is closed by
design, and widening it per-tool would couple the routines' policies; the
*format contract* is identical.

## Layout

- `src/backlog_groomer/detectors.py` — the pure detector core (this is the
  policy; everything else is plumbing).
- `src/backlog_groomer/report.py` — deterministic markdown renderer; the
  golden test pins its bytes.
- `src/backlog_groomer/config.py` — the strict conf parser and the
  two-key `armed()` decision.
- `src/backlog_groomer/github.py` — the single-seam, GET-only live read
  (`_get` is monkeypatched in tests; a fail-loud page cap raises rather
  than truncating a snapshot).
- `src/backlog_groomer/narrative.py` — the optional #248 layer: the
  model-API seam (`_post_message`, the package's only POST), the
  marker-bounded splice, `strip_narrative`, and the #206 registry
  resolution.
- `src/backlog_groomer/cli.py` — `report` / `gather` / `run` / `narrative`
  / `config` / `armed`; the workflow stays glue with no policy of its own.

Stdlib-only: the scheduled job runs on the system Python right after
checkout, and a third-party import would put a pip resolve in front of the
reporting step — the same rule `tools/lineage` and `tools/backlog-burn`
keep.

## Tests

```bash
pip install -e 'tools/backlog-groomer[test]'
python -m pytest tools/backlog-groomer/tests -q
```

Alongside the per-detector pairs: a golden-file test (same fixture snapshot
in → byte-identical report out, twice), the full 2×2 arming matrix, the
fail-loud parser rejections, an AST test that the pure modules import
nothing network-capable, and a write-verb confinement check — no
POST/PATCH/PUT/DELETE anywhere except `narrative.py`'s single model-API
seam (AST-checked, so prose doesn't trip it and a smuggled verb can't hide).
`tests/test_narrative.py` owns the layer's own contracts: the
`strip(insert(report)) == report` byte-identity, the fail-soft matrix, the
seam's inputs (the rendered report and nothing else), and the registry
resolution.
