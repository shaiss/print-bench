---
name: spike-converter
description: The model half of the spike-to-brief converter — takes ONE decided research recommendation (chosen deterministically by the #438 brief-sources extractor, never by the model) and reshapes it into a design-brief issue matching templates/design-brief.md. Extraction and reformatting, not invention. Advisory-only and dry-run-first; attended use only. Invoke as /spike-converter (issue #439, #245 child B).
---

# Spike converter

The model-driven half of the spike-to-brief converter (#245 child B, issue
#439). The #245 thesis: the *substance* of a new design brief is human-vetted
research already committed under `docs/`, so a model should only **reshape**
it — never originate it. The deterministic half (`tools/brief-sources`,
#438) decides **which** recommendation, with tests; this skill does the
**reshape**, and its discipline is the mirror of the extractor's: every number
in the brief you emit is either quoted from the source doc with its citation,
or explicitly marked as an assumption / parked in Open questions. Nothing in
between. A number you cannot source is not yours to invent.

This skill is the *transcriber* lane of the generative front — where
`/product-scout` (Remy) originates proposals from catalog signals, the
converter transcribes a decision a research doc already records. That is why
it has no `people/` identity: it has no taste to exercise. It proposes a
`design-brief` issue and stops; the human curates what actually gets designed
(`#245`: the converter proposes, the human curates).

**Attended-only** as shipped. The cadence, arming variable, model chain and
deny backstop are the workflow child (#440), not this skill — nothing here
assumes a scheduler exists.

## Run this — the exact procedure (do every step)

You have exactly three read surfaces and one write surface:

- **Selection and GitHub reads** go through the wrapper
  `.claude/skills/spike-converter/converter-helper.sh` (`select-candidate` /
  `list-briefs` / `read-thread`). Run it as a **single bare command** — nothing
  else on the line: no `;`, `&&`, `||`, `|`, no `$(...)`. The wrapper is the
  only place the #438 extractor is invoked from, so you never run `python3`
  yourself.
- **The source doc** is read with Read/Grep/Glob — the repo's own files, never
  the open web. If the source section does not carry a number you want, that is
  the answer: it goes to Open questions or becomes a stated assumption.
- **Filing** (when the human says go) goes through the reused scout MCP tool
  **`mcp__scout__file_design_brief`** — the same stdio server `/product-scout`
  launches (`.claude/skills/product-scout/scout-mcp.json`). Do NOT copy that
  server into this skill and do NOT route a brief body through a shell command:
  one filing surface, one audit.

Every run, in order:

1. **Select first — and only via the wrapper.** Bare command:
   `.claude/skills/spike-converter/converter-helper.sh select-candidate`
   It prints exactly ONE candidate with provenance (`slug` / `title` /
   `source` / `status`), or the single word `NONE`.
   - **`NONE` means stop and say so** — quote the wrapper's output and end the
     run. Do not look for a candidate yourself, do not "help" by scanning
     `docs/` for unmarked ideas (that is `/product-scout`'s or a human's lane,
     per the #245 lane table), do not retry with a different `--root` to get a
     different answer. A `NONE` is the extractor doing its job.
   - A candidate means the guard rails already ran: committed source only,
     deduped against open briefs and existing `designs/`. **You never pick
     between candidates** — the extractor already picked, oldest-undone-first.
2. **Read the source section named by `source=`** (format `docs/<doc>#<anchor>`)
   with Read/Grep/Glob. The anchor is a GitHub section anchor; if it does not
   resolve exactly, read the whole doc and locate the section by its heading —
   the marker's `slug`/`title` say what you are looking for. Read enough of the
   surrounding doc to know what the section claims and what it does not.
3. **Check the declined lane.** The extractor's dedup sees only *open* briefs —
   a brief a human closed as declined matches nothing, so a turned-down subject
   can re-select (a deliberate, documented gap in #438: a visible duplicate is
   the cheap failure). Before composing, if the source doc references a prior
   brief for this subject, or a sibling marker carries `ref=<n>`, read it:
   `.claude/skills/spike-converter/converter-helper.sh read-thread <n>`
   If that thread shows the subject was **declined**, stop and say so — surface
   it to the human (they may want to drop or amend the marker); do not re-file
   what was turned down.
4. **Compose the brief — dry-run is the default.** Emit the brief as markdown
   (§3) and show it to the human. **Filing nothing is the default state**: the
   acceptance of this skill is verifiable without filing, and a human should
   see the reshape before it becomes an issue. Only when the human says file:
   call `mcp__scout__file_design_brief` with `title` and `body` as plain
   arguments (the body is full markdown — tables, pipes, newlines are fine in
   a JSON tool argument; that is exactly why the surface is an MCP tool and
   not a shell flag). If the tool is not available in this session (it loads
   when the session is started with `--mcp-config
   .claude/skills/product-scout/scout-mcp.json`), say so, leave the printed
   brief with the human, and stop — never invent a second filing path.
5. **Read the filed issue back** once as a stranger design session (§6). One
   candidate, one brief, one issue per run — the extractor's one-per-firing
   rule, kept.

## 1. The lane — what converts and what does not

| Situation | Who |
|---|---|
| A decided marker (`status=decided`) selects | **this skill** reshapes it |
| An idea with no marker, no decision behind it | `/product-scout` or a human — never this skill |
| A spike conclusion marked build-it | the human marks it (`status=decided`), then this skill |
| A subject already open as a brief | nobody — the extractor already dropped it |
| A subject a human declined | stop at step 3 and say so |

The boundary is the marker: an HTML comment a human decision put there. This
skill never adds, edits or removes markers — seeding one is a human act (the
convention "records a decision that doc already made", #438's README), and a
converter that could mint its own inputs would be `/product-scout` with worse
oversight.

## 2. Provenance is the deliverable

The candidate's `source=` is not decoration; it is the authority the whole
brief rests on. Every measurement, constraint, and physical claim in the brief
carries a citation of the form `docs/<doc>#<anchor>` (the section, per the
candidate provenance — a claim the doc supports only in another section cites
that section instead, and says so). Specifically:

- **Must fit / hold** rows are **given** only when the source doc states the
  number — cite it. Otherwise the row is **assumed** with a stated basis, or
  the dimension moves to **Open questions**. A bare number of unknown
  provenance is the failure mode this skill exists to prevent.
- Claims about what the technique *does* (physics, behavior, limits) quote the
  doc's own wording closely enough that a reader can check it against the
  cited section. Where the doc hedges ("may", "in principle"), the brief
  hedges identically — the converter does not upgrade a hedge to a promise.
- What the doc cannot supply — printer specifics, a style choice, a fit target
  the research never measured — becomes an **explicit stated assumption** in
  Assumptions & defaults, or an **Open question**. Mark blocking questions as
  blocking; a session must know what it can proceed without.

## 3. The brief format — exact, not similar

The body matches `templates/design-brief.md` **section for section and heading
for heading** — the same shape `/intake` files and the `Design brief` issue
form collect, so a design session picks it up cold. The headings, in order:

```
## What it is
## Must fit / hold
## Printer & material
## Style
## First-pass part breakdown
## Assumptions & defaults
## Open questions
```

No extra sections, no renamed ones, no omitted empty ones (an empty **Open
questions** is a checkable claim that a session can start from this brief
alone — include it as a real empty section only if it is true). The Must-fit
table keeps the template's four columns: Dimension | Value (mm) | Given /
assumed | Source. `Value (mm)` is a units commitment: a non-mm measurement
says its unit in the cell.

The title is `Design brief: <short subject>` — the filing tool requires the
`Design brief:` prefix, so compose it that way from the start. The label
(`design-brief`) is applied by the tool, not by you; it is the only label this
skill's output ever carries.

## 4. The boundary (advisory-only, non-negotiable)

- **Proposes only.** Its entire write surface is filing one `design-brief`
  issue — never `autonomy-ok` or any routing label, never a comment on another
  issue, never a push, never a merge. Arming, chunking and parking are
  decisions this skill does not get to make.
- **Never invents substance.** A reshaped brief whose numbers all trace to the
  cited section, or are marked as assumptions — anything else is a bug in the
  run, not a creative liberty.
- **Never picks.** Candidate choice is the extractor's, deterministically. A
  run that scans `docs/` itself has already failed step 1.
- **One per run.** The extractor emits one candidate per firing; the converter
  files at most one brief per run. If the human wants the next candidate, that
  is the next run.

## 5. Dry-run mode (the default, and how to verify)

A dry-run is steps 1–4 with no filing: select (live, or against a fixture for
testing), read, compose, print. It is the default because it is the mode a
human can check — and the mode this skill's acceptance is written in. To
exercise selection against a fixture instead of the live backlog:

```bash
# a fixture root with docs/<doc>.md carrying one status=decided marker, and an
# open-briefs file (empty = a genuinely empty backlog; "<n> <title>" lines
# otherwise). --root defaults to this repo; pass the fixture root:
.claude/skills/spike-converter/converter-helper.sh select-candidate \
  --root <fixture-root> --open-briefs <briefs-file>
```

Against the live repo the same verb with no flags is the real check: today
every seeded marker is `status=briefed`, so it prints `NONE` — the dedup
negative control, live. A `NONE` there is correct behavior, not a failure to
work around.

## 6. Done means

Read the brief back once as a stranger design session:

- every **Must fit / hold** row is given-with-citation or assumed-with-a-stated-
  basis — no bare numbers;
- the section headings diff clean against `templates/design-brief.md`;
- every physical claim traces to the cited section, hedged where the doc
  hedges;
- **Style** holds a decision (`none` is a decision);
- **Open questions** lists everything the source could not supply, each marked
  blocking or not — or is a true empty;
- it is the **candidate the extractor picked**, not a subject you preferred;
- if filed: it carries the `design-brief` label, the `Design brief:` title,
  and nothing else.

If any section would make a design session ask the filer a question that Open
questions does not already contain, the brief is not done — fix it before
filing, or park the question there and say so.
