# Adoption studies: measuring a tool against the bench

**Status: in use.** An *adoption study* is print-bench's neutral, repeatable
way to answer one question about any outside tool — a vendor product, an
OpenSCAD library, a slicer, a CI service — **without** deciding to adopt it in
the same breath. It measures the tool against the quality machinery the bench
already runs, and states plainly where the tool is **redundant**, where it is
**additive**, and **where integration would make sense**, plus the questions
that must be answered first.

The point is that the study is *neutral* and *repeatable*: the same tool
studied twice, by different hands, lands on the same verdict, because the
baseline it is held against is the bench's own gates — not taste, not a sales
deck. Filing a study is a request to **evaluate**, never to integrate; no
adoption decision is implied or made by opening one.

> This is process, not policy. `docs/licensing.md` (issue #160) governs what a
> tool's license *lets* the bench do; a study *reports* against that boundary
> and everything else the bench measures, and hands the reading to a human.

## How to submit one

Open an **Adoption study** issue from the chooser
(`.github/ISSUE_TEMPLATE/adoption-study.yml`). The form auto-labels the issue
`adoption-study` and titles it `Adoption study: <product>`; its fields mirror
the canonical format in `templates/adoption-study.md` heading-for-heading (the
two are kept identical the same way the design-brief form mirrors
`templates/design-brief.md`). Fill it as a neutral dossier:

- every **capability claim carries evidence** — a link, a doc reference, a demo.
  A claim with nothing in the evidence column is an *assumption* and belongs
  under *Assumptions & claims to verify*, never stated as fact.
- **license reach is first-class.** Name the exact terms (BSD-2-Clause vs.
  GPL-3.0 is a different tool for print-bench, not a nuance) — the study is read
  against the boundary `docs/licensing.md` draws.
- the **integration surface** frames where the tool would plug in (a `lib/`
  module, a `scripts/` tool, a `styles/` pack, one design, the autonomy loop) —
  it scopes the evaluation, it does not commit to it.

## How it is assessed

The study is measured against the bench's **deterministic baseline** — the
machinery that already decides whether a design is good. A capability the tool
offers is only *additive* if the baseline does not already cover it:

| The baseline a study is measured against | What it already proves |
|---|---|
| Deterministic gates — printcheck (0–100) + a PrusaSlicer test-slice (`gate.sh --slice`) | A part is watertight, printable, and actually slices |
| Compulsory must-fail negative controls — `mate-check.sh`, `guard-check.sh`, `lineage.sh selftest` | Each check can still *fail*: a fit that stopped assembling, a guard that stopped refusing, a derivative override that stopped taking |
| Telemetry (issue #93) — `telemetry/log.ndjson`, one record per default-branch gate run | A time-series of scores, gate wall-time, and budget headroom — the bench measuring itself |
| The model/provider registry (issue #206) + smoke (issue #298) | Which models run and that each is *callable* with a real 1-token request — proof of servability, **not** of being better |

Every study lands as a **split verdict**, in three parts, always all three:

- **Redundant** — the capabilities the baseline above already covers. A tool
  that only restates what `gate.sh`, the negative controls, telemetry, or the
  registry already do adds nothing, however polished; naming that plainly is
  half the value of a neutral study.
- **Additive** — the capabilities the baseline genuinely does not have, stated
  against evidence. This is the only column that can justify integration.
- **Where integration makes sense** — *if* anything is additive, the narrowest
  surface that would carry it (one design's opt-in, a single `scripts/` tool, a
  `lib/` helper), and the cost of that seam — including the license reach, which
  under N2 can rule a tool out for shared core no matter how additive it is.

Two disciplines keep the verdict honest:

1. **Qualifying questions, not conclusions.** A study that cannot yet decide a
   column records the *questions that would decide it* — measurable, answerable
   ones — rather than guessing. An empty *Open questions* section is itself a
   claim: it says the study is ready to be read as-is.
2. **Git stays the source of truth; the study is advisory.** A study is a
   reading a human acts on. It **never gates a merge**, never arms autonomy, and
   never changes a committed decision on its own — the reproducible source of
   truth stays the repo's config and gates (N4). A study can *recommend* raising
   a tool; the raising is a separate, human, reviewed act.

## Disposition: the taxonomy and the lifecycle

A study, once read, gets a **disposition** — a non-routing advisory label that
records the reading. The two labels are deliberately advisory: they surface a
verdict to a human; they route no autonomy routine (unlike `autonomy-ok`,
`design-brief`, `declined-too-big`, or `needs-decision`).

```text
study filed                    study read                       (optional) acted on
───────────                    ──────────                       ───────────────────
+label adoption-study   ──►    +label disposition:worth-raising ──►  a human raises a
(the issue form does this)     | disposition:declined                design brief / issue,
AWAITING a disposition         the split verdict is recorded         or does nothing —
(no disposition:* label)       on the thread                         the study just closes
```

- An open `adoption-study` issue **with no `disposition:*` label** is **awaiting
  a disposition** — nobody has read it to a verdict yet.
- Adding **`disposition:worth-raising`** records that the study found something
  additive worth a human's attention; **`disposition:declined`** records that it
  did not (redundant, or ruled out on license or fit). Both are terminal
  readings, not routing signals — acting on a `worth-raising` verdict is a
  separate human step, and a study can be closed either way.

## Reeve is the deterministic keeper

A study is only useful if the ones that need a human's eye actually reach one.
That is **Reeve's** job — the platform PM (`PM.md`, issue #272) — and it does it
deterministically, with no model in the loop. Reeve's existing GET-only issue
gather reads the open `adoption-study` issues, and its single sticky
*bench-health* report surfaces two lists to the lead:

- studies **awaiting a disposition** — filed but not yet read to a verdict; and
- studies marked **`disposition:worth-raising` but still open** — a verdict the
  human agreed with but nobody has acted on.

Reeve holds **no secret**, writes **nothing but that one report issue**, and
**never gates a merge** — the same advisory-only shape as its other detectors.
It is the keeper of *what reaches the lead*, not an approver of anything: it
makes an unread or unacted study impossible to lose in the backlog, and stops
there.

## Worked example

[Issue #332, *Adoption study: LangSmith*](https://github.com/shaiss/print-bench/issues/332),
is the first real study — opened and closed as a spike. Its split verdict:
LangSmith's run-tracing capability is genuinely **additive** over the bench's
telemetry (per-run LLM traces the `log.ndjson` gate-run series does not
capture), so the disposition is **worth raising for that capability only**; its
evaluation is **declined for geometry** on principle, because the bench's
geometry quality is proven by deterministic gates and negative controls, not by
an observability vendor. The study recommends; it adopts nothing.

## The agentic assessor is a proposal, not a build

Today the assessment is **human-run**: a person reads the filed study against
the baseline and writes the split verdict. An **agentic assessor** that
auto-produces the study from the filed issue is a *proposed* follow-up, designed
but deliberately **not built here**, because auto-drafting a disposition from
untrusted issue text crosses the bench's "agentic writer over untrusted issue
text" boundary — the same line the labeler and product scout sit behind. The
full design (the one narrow intake surface, the deny-backstop, the two-key
arming, and the one boundary it may never cross) is in
[`docs/adoption-study-assessor-proposal.md`](adoption-study-assessor-proposal.md).

## References

- `templates/adoption-study.md` — the canonical study format.
- `.github/ISSUE_TEMPLATE/adoption-study.yml` — the intake form.
- `docs/licensing.md` — the GPL/BSD boundary a study reads against (issue #160).
- `PM.md` — Reeve's charter; the bench-health report is Reeve's surface.
- `docs/adoption-study-assessor-proposal.md` — the proposed agentic assessor.
- Issue [#332](https://github.com/shaiss/print-bench/issues/332) — the worked example.
