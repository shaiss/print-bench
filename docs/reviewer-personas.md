# Reviewer personas: one lens, one reference pack, PM-gated tags

The recast is [PR #322](https://github.com/shaiss/print-bench/pull/322) (tracked
as issue #324 for this doc). This is the pattern for adding another one.

A reviewer persona is a **laser-focused human-like AI reviewer** with exactly one
job: to contribute the judgment a particular kind of stakeholder would produce —
judgment no gate, no slicer check, and no other persona can emit. Jane speaks for
the person running the printer; Drik speaks for the person who will live with the
printed part. Each is a skill (`.claude/skills/<name>-review/`), a registered team
member (`people/<handle>.md`), and a job in the auto-review pipeline, and each
produces **tagged feedback the design's PM triages** — never a merge verdict.

The shape exists so the owner can add more of them later without redesigning the
loop each time. This doc is that redesign, written down once.

## The test: new persona, or lens inside an existing one?

The default answer is **no**. A persona is a recurring cost — another model run
on every review round, another skill to keep honest, another voice in the PM's
triage. It is justified only when all three hold:

1. **A stakeholder no existing persona speaks for.** Not a new *topic* — a new
   *person*. Ask who this persona is in the room as. Jane is the person at the
   printer tonight; Drik is the first customer. If your candidate is "the same
   person Jane already is, but looking at assembly," that is a section in Jane's
   checklist, not a new Jane.
2. **Expertise that arrives as knowledge, not just attention.** The lens must
   carry a *reference pack* — facts of the trade the persona reviews against
   (Jane's extrusion-width arithmetic, Drik's real-object measurements). If you
   cannot fill a `references/*.md` with domain knowledge the persona needs in
   hand, the lens is a checklist item, and checklists belong inside an existing
   persona's method.
3. **Findings the current loop would otherwise miss.** Name three findings this
   persona would have produced on recent designs that no gate, Jane, Drik, or
   the PM produced. If you cannot, the loop is not missing the lens.

The examples from the recast, each of which passes: an **assembly/maintenance
reviewer** (the person who will service the part — a different stakeholder from
both the printer-operator and the first customer, with torque/tolerance/wear
knowledge of its own), an **accessibility reviewer** (the person with restricted
dexterity, sight, or reach using the part), and a **cost/material-efficiency
reviewer** (the person paying for filament and print hours across a fleet, not
one print).

What does **not** justify a persona: a subject area ("a docs reviewer," "a
security reviewer" for a repo with no security surface), a severity level ("a
strict reviewer" — severity is the PM's triage, not a persona), or a reformatting
of what CI already proves. If the lens's whole output would be numbers,
comparisons, or pass/fail calls, it is a gate — write it in `scripts/`, not as a
persona.

One lens means one lens. A persona that grows a second lens ("Drik, but also
checking the print settings") has become two people in one coat; split the new
lens out by this same test, or file it back where it belongs.

## Division of labor is the spine

**CI checks the numbers. The persona contributes only the judgment its lens
produces.** This is the one rule every persona contract states before anything
else, and the recast exists to enforce it:

- **Never re-derive a number a gate covers, never re-run a gate to confirm its
  posted output, never report that a designer's claim "checks out."** The
  printcheck/slice sticky comment is ground truth; consume it, don't audit it.
- **Arithmetic in exactly one place: in support of a new finding of the
  persona's own.** "0.5 mm strokes on a 0.42 mm line width is one wobbly wall"
  is Jane math — it powers *her* finding. Recomputing the designer's clearance
  stack to confirm it is not.
- **Read docs as their user, not their auditor.** Internal-notes drift is
  `scripts/docs-check.sh`'s and reviewers-of-record's business. A persona reads
  the pages a real stakeholder would read (the product page, the usage notes)
  and reports whether *that person* would succeed.

A persona whose review is mostly confirmation has failed at its job even when
every observation is accurate. At least one finding per review should be
something no gate or slicer check could produce; if the pass genuinely surfaced
none, say that plainly rather than padding.

## The bundled reference pack

Each persona ships its domain knowledge with it, in
`.claude/skills/<name>-review/references/*.md`. The skill's §0 loads the pack
*before* reviewing — the persona arrives knowing its trade, the same way Jane
arrives knowing what 0.5 mm strokes do on a 0.4 nozzle. The exemplars:

- `.claude/skills/jane-review/references/print-experience.md` — extrusion-width
  arithmetic, stock-profile behavior, first-layer facts, the clearance feel
  ladder.
- `.claude/skills/drik-review/references/first-user-method.md` — deriving the
  first user, scripting a session of use, the real-object homework habit, the
  leak-audit checklist.

The pack is the persona's *own* knowledge, cited as experience ("on a 0.4 that's
one wobbly wall"), never as an audit of anyone else's numbers — the division of
labor applies inside the pack too. One focused file beats several thin ones;
split only when a file serves two different moments in the method.

## PM-gated tags

Every finding carries an **evidence tag** from a vocabulary the persona defines
in its own contract, and the design's PM (`/pm <name>`, skill §8, run by the
`pm-triage` job) rules on each one: **act-now / queue / decline**.

- Jane: `[saw-it]` (visible in a preview, the diff, or a CI report) /
  `[bench-sense]` (experience judgment the PM should weigh).
- Drik: `[used-it]` (visible) / `[customer-sense]` (experience judgment) /
  `[hunch]` (worth checking, unproven — never drives a change alone).

A new persona defines its own vocabulary on the same axis — at least one
**evidence** tag (a claim checkable against something committed) and one or more
**judgment** tags (experience the PM weighs), each defined in the persona's
contract in a line a PM can triage against. The PM's skepticism calibration
extends to it mechanically: an evidence tag is challenged only with evidence; a
judgment tag is weighed against the charter and its cost; a hunch-tier tag never
drives a change by itself. Without the tags the PM has nothing calibrated to
rule on, and without the PM the tags are decoration — the pair is the mechanism.

## Registration checklist

Every artifact a new persona needs, in the order to land them. The drift-guard
pin (step 5) must land in the **same PR** as the ship job (step 4): the guard
checks only the jobs the tuple names, so a job shipped unpinned is a job whose
chain wiring nothing verifies — it must never exist in that state.

| # | Artifact | What it is |
|---|---|---|
| 1 | `.claude/skills/<name>-review/SKILL.md` | The persona's contract: who it is, its one lens, the division-of-labor section first, its §0 load list, its method, its output contract with the tag vocabulary and the attribution footer, and a portability note saying which specifics are the example vs. the contract. |
| 2 | `.claude/skills/<name>-review/references/*.md` | The bundled knowledge pack the skill's §0 loads before reviewing (see above). Ship at least one file; more only when the method has genuinely different moments. |
| 3 | `people/<handle>.md` | The team-registry entry: a `---`-fenced header with `name`/`kind: agent`/`role`/`initials`, **`shared: true`** (review specialists are registry-wide, never in a design's `team.conf` core), and **`mandate: .claude/skills/<name>-review/SKILL.md`** — the header points at the charter and never restates it. An unresolvable mandate path fails `./scripts/site.sh`. |
| 4 | A ship-job block in `.github/workflows/auto-review.yml` | The job that runs the persona on each new review round: `needs: design-changes`, gated on `designs_changed`/`is_new_round`, then **one ship step per link of the registry `review` chain** (`needs.design-changes.outputs.model1..modelN`), each `continue-on-error` and gated on the previous not succeeding, a missing-key notice step, and a final gate step failing only when every configured provider failed. Copy the `jane-review` job's shape wholesale — including its provider-fallback rationale comment — and change only the persona name and prompt. Slot→provider wiring stays literal (the Actions constraint): slots 1–3 Z.AI via `secrets.ZAI_KEY`, slots 4–6 Anthropic via `secrets.ANTHROPIC_API_KEY`, pinned to the registry by the guard. Add the job to the `needs:` of `pm-triage` and `design-coach`, and extend their skip conditions (the `result == 'success'` clauses listing which reviewers completed) so the verdict and the coach see its feedback and a failed persona job doesn't cancel them. |
| 5 | The `REVIEWER_JOBS` addition in `tools/model-registry/tests/test_workflow_drift.py` | The drift-guard pin: add the job id to the `REVIEWER_JOBS` tuple so the test asserts the job exists, has exactly one ship step per chain link, and sources the right `model{k}` slot per step. The check is one-directional — it iterates the tuple, not the workflow — so the tuple entry is what brings a job under guard; a reviewer job added without it is simply never checked, and the guard can't notice. |
| 6 | A CLAUDE.md bullet in the Review skills section | One line in the voice of the existing Jane/Drik bullets: the lens, the stakeholder, the trust-in-CI boundary, the tags, and that findings are PM-triaged feedback. Not optional bookkeeping: `scripts/docs-check.sh` check 2 fails if a skill exists that CLAUDE.md doesn't mention, and CLAUDE.md is what a session actually loads — an undocumented persona is a persona nobody invokes. |

Steps 1–2 are the persona; 3–5 wire it into the loop; 6 tells humans (and
sessions) it exists. A PR adding a persona should be reviewable as: the contract
(read this closely), the pack (is this real knowledge?), and the wiring (a diff
that copies `jane-review`'s shape).

## Anti-goals

Three failure modes the recast explicitly closed. A new persona that drifts into
any of them has broken the loop it joined, however good its findings:

- **No verified-math sections.** A review section that confirms the designer's
  numbers is not content — it is auditing someone else's work, which is CI's
  job, done worse. Every persona's output contract states this.
- **No doc-drift auditing.** Personas read committed docs as a user would, not
  as an auditor checking them against the tree — that mechanical freshness
  checking belongs to `scripts/docs-check.sh`, `scripts/readme-gate.sh`, and
  friends, which do it deterministically.
- **No merge-gating by reviewers.** Reviewer output is **feedback into the
  design loop**; the design's PM rules on it (act-now / queue / decline), and
  the human's merge decision stays the human's. No persona job blocks a merge,
  and no persona posts a verdict that reads like one.

The same three apply to the PM itself: the triage is a gate on *what the next
iteration acts on*, never on the merge, and the PM does not re-derive numbers
either — CI checked the numbers, the reviewers felt the part, the PM rules on
scope and value.
