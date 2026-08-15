# backlog-groomer

The deterministic backlog-health report behind the scheduled **Backlog
groomer** workflow (`.github/workflows/backlog-groomer.yml`, issue #244).
The autonomy routines — backlog burn (#95), design run (#96), the chunker —
all feed one issue queue; this tool tends it. It owns only a *report*: every
finding is a recomputable fact about timestamps, labels, and links (no LLM
anywhere), and the routine is **advisory-only** — the tool performs GET-only
reads, and the workflow's single write is upserting one sticky report issue.
Nothing else is labeled, closed, or commented on.

## The detectors

Each is a pure function of the snapshot, provable to fire and to stay
silent (`tests/test_detectors.py` keeps a positive case and a negative
control per detector — delete a detector's condition and one half fails):

1. **stale** — open issue with no update in > `staleness_days`.
2. **armed-stuck** — `autonomy-ok` older than `armed_stuck_days` with no
   open PR closing it (nine GitHub keywords, number compared as an int so
   `fixes #24` never half-matches #244): the burn is disarmed, failing, or
   perpetually re-declining it.
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

## Usage

```bash
pip install -e 'tools/backlog-groomer[test]'

backlog-groomer report --input snapshot.json --out report.md   # pure render
backlog-groomer gather --repo owner/name > snapshot.json       # GET-only live read
backlog-groomer run --repo owner/name --conf .github/backlog-groomer.conf --out report.md
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

```
enabled: true
cadence: 41 5 * * *
staleness_days: 14
armed_stuck_days: 7
oversized_stuck_days: 7
dup_threshold: 0.6
max_dup_pairs: 10
```

Strict on purpose: unknown keys, duplicates, and malformed values raise
with `path:lineno`; an absent `enabled` reads as **off**. Arming is two
keys — the conf's `enabled` **and** the `BACKLOG_GROOMER_ENABLED` repo
variable must both be `true` (`backlog-groomer armed` is the tested
decision) — so a clone or fork can never silently arm the routine. This is
the groomer's own parser, not a reuse of `tools/backlog-burn`'s: that
parser's key set is closed by design, and widening it per-tool would couple
the routines' policies; the *format contract* is identical.

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
- `src/backlog_groomer/cli.py` — `report` / `gather` / `run` / `config` /
  `armed`; the workflow stays glue with no policy of its own.

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
nothing network-capable, and a word-bounded scan that no HTTP write verb
appears anywhere in the package.
