# brief-sources

The deterministic half of the **spike-to-brief converter** (#245, child A —
issue #438). The #245 thesis is that the substance of a new design brief is
human-vetted research already committed under `docs/`, and a model should
only *reshape* it. This package makes the **which recommendation** half of
that reshaping pure and provable: it turns the markers in committed research
docs into an ordered list of decided design-brief candidates and applies the
guard rails #245 locks — committed sources only, dedup against what is
already open or already built, at most one candidate per firing, provenance
per number — as code with tests, not as a prompt.

The mold is `tools/backlog-groomer` / `tools/reeve`: pure functions of
committed files, its own pytest suite, no pip at runtime, no LLM, no
network. Stronger than either sibling: there is not even an advisory GitHub
read here — **zero HTTP calls and zero write verbs anywhere in the package**
(a test scans the AST of every module for both). It reads `<root>/docs/*.md`
and lists `<root>/designs/`, and prints.

The model-driven half (child B, #439: the skill that reshapes a candidate
into a filed brief) and the cadence half (child C, #440: workflow, conf,
registry chain, arming variable) build on this tool and are not part of it.

## The marker convention

A committed research doc marks a **decided** recommendation — a demonstrator
a human decision already names (#204's catalog, seeded below), or a spike
conclusion marked build-it — with one HTML comment:

```markdown
<!-- brief-candidate: <slug> | <title> | source=<doc>#<anchor> | status=<status> ref=<n> -->
```

| Field | Meaning |
|---|---|
| `slug` | kebab-case `[a-z0-9][a-z0-9-]*` — the candidate's addressable name |
| `title` | the subject's title (no `\|`; the field separator) |
| `source=<doc>#<anchor>` | provenance: the marker's **own** doc path from the repo root, plus the GitHub section anchor that holds the substance — the per-number provenance #245 requires |
| `status=decided` | a decision exists; not yet filed as a brief |
| `status=briefed ref=<n>` | already filed as design-brief issue `#n` — never selects again |
| `ref=<n>` | only valid with `status=briefed` |

Rules the parser enforces (fail-loud, naming `file:line` — a silently
skipped marker is a decided recommendation nobody acts on):

- The marker **records a decision that doc already made**; the convention
  never invents candidates. Seeding a marker where no decision exists is out
  of bounds (see `docs/metamaterials-4d.md`'s #201 go/no-go, deliberately
  unmarked).
- `source=` must name the doc the marker physically sits in — a marker
  copy-pasted between docs still claiming the other doc's section is bad
  provenance and raises.
- Unknown fields, duplicate fields, non-kebab slugs, `ref` without
  `briefed`, `briefed` without `ref` — all raise.
- Markers inside fenced code blocks or inline code spans are **skipped**:
  those are places a doc *displays* the convention (like this README would
  be, if it lived under `docs/`), not decisions. Non-marker comments and
  prose never parse as anything.

The one deliberate non-check: the anchor is **recorded, not validated**.
Re-deriving GitHub's anchor slug in this package would add a second
implementation of GitHub's algorithm that can drift against the real one;
the anchor is provenance for a human to click, and a wrong anchor is a
review problem, not a selection hazard.

### The seed

`docs/advanced-techniques.md` carries nine markers — the #204 catalog
demonstrators, each anchored to the section that documents the technique the
design demonstrates, all `status=briefed` against #385–#393. They make the
tree itself a **live negative control**: `select` over this repo with the
real open-brief list must print `NONE`, and the test suite asserts it.

## The guard rails

`select` applies, in order, and prints exactly ONE candidate with its
provenance — or the single word `NONE`:

1. **`status=briefed` never selects** — already filed, never re-file.
2. **Duplicate slugs collapse** to the first occurrence — whatever its
   status, so a `briefed` first occurrence suppresses a later `decided`
   duplicate of the same slug.
3. **A matching open brief drops the candidate.**
4. **A matching existing `designs/<name>/` drops the candidate.**

Rail 3 sees only *open* briefs: a brief **closed as declined** matches
nothing here, so a declined subject can be re-proposed. That is a deliberate
gap, not an oversight — a re-filed declined brief is a *visible* duplicate a
human closes in seconds, the cheap failure — but the reshaper that consumes
these candidates (#439) should carry the same knowledge so it does not keep
surfacing a subject a human has already turned down.

Ordering is oldest-undone-first, defined as `extract`'s scan order: sorted
doc path, then marker order within a doc. That is a deliberate definition —
commit timestamps are not stable across clones, and a selector whose order
differed between two byte-identical trees would be nondeterministic in
exactly the wrong place.

Matching is **conservative: when in doubt, drop**. A dropped candidate
costs a human one look at a `NONE`; a wrongly-selected candidate re-files a
brief that already exists — the failure this tool exists to prevent. Three
independent tests, any one matching drops: normalized substring (the common
live shape — a brief titled `<slug> — …`), full slug-token containment
(catches reworded titles), and token-overlap Jaccard ≥ 0.5 over the
candidate's slug+title against the subject. House title vocabulary
("Tier", "reference", "design", "Domain", …) is stopworded first, so
sharing it is *proven different*, not doubt — otherwise the second design
in a technique family could never be filed.

## CLI

```bash
pip install -e 'tools/brief-sources[test]'

# Every candidate under a root, oldest-undone-first (--json for machines)
python -m brief_sources extract --root .

# The one candidate worth filing (or NONE) against the live open-brief list
gh issue list --state open --label design-brief --json number,title \
  --jq '.[] | "\(.number) \(.title)"' \
  | python -m brief_sources select --root . --open-briefs -
```

`--open-briefs` takes a path or `-` (stdin), one `<number> <title>` per
line (spaces, tabs or `|` after the number; a tab ends the title, so `gh
issue list`'s default table pipes cleanly). It is **required on purpose**:
dedup is the reason this tool exists, and a `select` that silently assumed
an empty backlog would re-file everything the rail was meant to catch. An
empty file is the honest way to say "nothing is open".

Exit codes: `0` success (including the `NONE` verdict — that is an answer,
not an error); `2` a wrong invocation, a malformed marker, or a malformed
brief list.

## Tests

`pytest tools/brief-sources/tests` — a positive AND a negative control per
rule (the repo standing rule: a guard never exercised can be weakened while
every other check stays green), plus:

- **fixture isolation** — a `--root` fixture never sees or leaks the real
  tree, including when invoked from the repo's own cwd;
- **the live negative control** — over this repo, the nine seeded
  demonstrators are all `status=briefed` with their refs, and `select` with
  the nine real brief titles prints `NONE`. The control pins *presence and
  status*, not a count of nine: a tenth briefed marker is the tool working,
  not a regression. A future `status=decided` marker legitimately breaks
  the NONE assertions — landing one means updating the live control in the
  same change, which is the control doing its job;
- **the safety scan** — no module imports anything network-capable, no
  `open()` in a write mode, no filesystem-write method call, and no HTTP
  write verb as a string constant, anywhere in the package (AST-scanned, so
  docstring prose never trips it and code always does).

## Layout

- `src/brief_sources/markers.py` — the marker grammar and `extract`
- `src/brief_sources/select.py` — the guard rails and `parse_briefs`
- `src/brief_sources/cli.py` — `extract` / `select` commands
- `tests/` — the suite described above
