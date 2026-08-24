# nuggs — product charter

## The product, in one paragraph

**N.U.G.G.S. is a tube system, and the thing it ships is a standard.** The
standard is one **genderless quarter-turn port** around an 80 mm bore:
every module carries the same port at every end, so any module mates with
any other, either way round, and any module leaves the middle of a run in
one twist. Today the system ships one run — the **Bin Bridge**, two
bulkheads and a straight joining two enclosures through their walls, for
someone with a Bambu-class printer, a spool of natural PETG, and an adult
Syrian whose factory cage tubes are too narrow for a pouch-full animal.
The one thing the system must do well is **be a bore an adult Syrian can
traverse safely and an owner can open in one action**, at every module
anyone ever adds to it. It competes with a hole saw and a length of
drainpipe — so if it is not safer, cleanable, and openable, it has no
reason to exist.

**What "system" costs, stated up front.** The moment a second module
exists, the non-negotiables below stop being properties of one part and
become properties of *what a user assembles*, which no `assert` can see.
That is why the rules are written as rules a **module** inherits, and why
the ones that can only be broken by assembly (N2, N3) are carried on the
part and on the product page as well as in the model.

The customer is the **owner**, but the user is the **animal**, and the
animal cannot report a defect. That asymmetry is why the non-negotiables
below are asserts rather than guidance.

Enforced by `/pm nuggs`. Engineering log: `NOTES.md`. Product page:
`README.md`. Sourced research: [`docs/nuggs-research.md`](../../docs/nuggs-research.md)
— **read §11 (re-verification, 2026-08-03) before quoting any welfare
figure in this file.** Design request: #34.

## Non-negotiables

May not be weakened to make engineering easier. **Every module in the
system inherits all of them** — a new module family is not a new charter.

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | No passage narrower than the bore floor, anywhere — including the bulkhead throat, any bend's inscribed circle, and the neck of any module in any family | **70 mm** | Deutscher Tierschutzbund, pouch-full **entrance** minimum (⚠️ an entrance-opening rule applied to a bore, and secondary-summary — see research §11.8) | A better-sourced figure for a *pouch-full* Syrian appears. Not for print convenience, ever. **Not reopened by the 40–50 mm wild-burrow tunnel figure** — soil is grippable, self-ventilating and escapable by digging; PETG is none of those |
| N2 ⚠️ **scope PROVISIONAL** | **No RUN of continuously enclosed bore exceeds 2 × body length.** The *number* is not in doubt; what is provisional is whether the source scopes it per tube or per system — marked LOW confidence in research §11.6 and listed as publication-blocking in Open decisions below. Until the DTSchB PDF is read, treat branched and looping layouts as OUT of scope and the Bin Bridge (one run, both ends open) as the only configuration this rule has been checked against. If the source turns out to be per-system, N2 reverts to a total and this line is the record of that risk being known in advance. A *run* is the maximal chain of enclosed bore between two **breaks**. A break is: an **open module** (longitudinal window ≥ 180°), a **port discharging into a ventilated enclosure**, or a **turnaround node** of clear internal width ≥ body length **that is itself open to ventilated space** (width alone is not a break — a sealed wide chamber is a dead volume, and N3 forbids it). **A bend is not a break. A junction at bore diameter is not a break. A coupling is not a break. A top hatch resets RETRIEVAL, not REVERSING.** | **360 mm** per run at `body_len_mm = 180`; **min(2 × body_len_mm, 300)** if the run is not hand-releasable — not "drops to 300", which is only a drop above body_len_mm = 150 | Deutscher Tierschutzbund position paper *Tierschutzwidriges Zubehör* — **not TVT Merkblatt 62**; see research §11.2. One limb of a conjunctive test (length **and** ventilation **and** instructions), stated per tube | The owner measures a longer animal — the assert scales, the rule does not. Or someone opens the DTSchB PDF and finds it is per-*system*, in which case the per-run scope is retracted and N2 reverts to a total |
| N3 | No dead-air volume and no dead end. Every run is open at both ends — into a ventilated enclosure, an open module, or a turnaround node the animal can leave by turning around | 0 closed volumes | TVT MB 62 (condensation, ventilation) — the qualitative objection set, which is what MB 62 actually documents | **Reworked 2026-08-03:** this used to be satisfied by *banning branches*. It is now satisfied by **topology** — a branch is legal when every terminus is a node or an enclosure. A branch that ends in a bore-diameter stub is still forbidden |
| N4 | No vertical runs; maximum incline | **15°** | Fall risk — Syrians climb well but have almost no depth perception | Never for v1; a future ramp module with treads would need its own evidence |
| N5 | The entire enclosed length of any run opens by hand, tool-free, in one action | 1 action | A wedged or pouch-impacted animal cannot reverse | Never. Glued or screwed assembly does not satisfy this — and a run that fails it drops to N2's 300 mm limit rather than being allowed |
| N6 | Nothing protrudes into the bore, and no chew-initiation geometry the animal can reach — **at a joint as well as within a module** | — | Ingested fragments; claw and pouch snag | Never |
| N7 | Hand wash only, ≤ 50 °C; never a dishwasher | 50 °C | PLA Tg 57–70 °C, PETG 80–85 °C, dry cycle 70 °C+ | Never — a deformed tube is a *narrowed* tube, so the material failure mode is the injury failure mode |
| N8 | No interoperability with any commercial tube system, and no reducers in either direction | Kaytee 57.15 mm is 18.4 % under N1 | Adapting down imports the exact defect the product exists to fix | Never |
| N9 | Never drill tempered glass | — | Detolf and most tank panels shatter | A no-drill rim saddle (B3) serves glass instead |
| **N10** | **One interlock standard, shared by every module.** Every port face in the system is the same genderless port at the same revision. No second joint, no family-specific variant, no adapter between two NUGGS joints | 1 standard | A second joint means two tolerance knobs, two coupons and two failure modes — and it silently partitions the kit into families that cannot mate. The genderless port is the thesis; two of them is not a system | Never, within a revision. A breaking change bumps the port revision, and the revision is on the part so a printed module can be identified years later |
| **N11** | **An open module's floor is the bore arc.** A module opened by a longitudinal window keeps its round section; it is a tube with a window, never a flat-floored trough | 0.000 mm step at the joint | A flat floor tangent to an 80 mm bore's invert stands **6.93 mm** proud of a round mate at the paw-span edge (22.5 mm lateral) — a full-height vertical rim across the transition plane, which is N6's toe-stub. A chord floor gives an 8.78 mm centreline pit instead. The arc floor is the only section with zero step, because both modules' bores are the same cylinder | Never while N6 stands. The 45° per-module bend ceiling that follows from bore-axis-vertical printing is **accepted**, not a reason to reopen this |

**N1 and N5 are the product.** If a module cannot hold both, it should not
ship at all — that is a finding for the human, not a trade to make. **N10
is what makes it a system**: a module that mates with nothing is a
different product wearing this one's name.

## What N2 actually protects, and why the number means something

Worth stating once, because the number is inherited and the *reason* is
not, and because every reviewer will ask why 360 mm and not 250 or 900:

> Because the animal **cannot turn around** in an 80 mm bore — a hairpin
> needs roughly two body widths plus bend allowance, ~110 mm at a ~45 mm
> body width — it leaves by whichever end is nearer. Worst-case
> **unassisted reverse travel is half the run.** A run capped at 360 mm
> bounds it at 180 mm: exactly one body length.

That derivation is **engineering judgement**. No literature measures how
far a hamster will reverse, or the width it needs to fold in. The 2×
multiplier is (probably) sourced; what the multiplier *means* here is not.
Any module or product-page claim that presents the reversing argument as
literature is a charter violation, not a wording preference.

## Out of scope

**Never.** Any reducer to commercial bore. Any vertical riser. Any
dead-end cap. Any run over 2 × body length between breaks. Any second
interlock standard (N10). Any flat-floored open module (N11). Any
tempered-glass drilling variant. Any in-cage configuration — the enclosure
minimum is 100 × 50 cm and an in-cage L-run eats about a quarter of it, so
a tunnel that consumes floor or substrate is a net welfare loss
(Hauzenberger, Gebhardt-Henrich & Steiger 2006 puts substrate depth, not
tunnels, at the centre of hamster welfare, and recommends at least 40 cm
of it).

**No longer out of scope, as of 2026-08-03.** Branches, loops and open
modules. They were excluded by a rule that summed the whole system into
one length budget; under the per-run rule they are legal **iff** every run
between breaks is short and every branch point that claims to reset the
count is a real node. This is not a licence — it is a topology
requirement, and it is the one the wild burrow satisfies (short galleries
punctuated by 10–20 cm chambers, Gattermann 2001).

**Deferred.** Everything in the backlog below. The default answer to
"could we also…" is "yes, as a backlog item".

## v1 — definition of done

Gate-green is necessary and **not** sufficient. v1 is done when:

- [x] `gate.sh --slice nuggs` exits 0 across all four parts
- [x] Every welfare assert fires when deliberately violated *(and as of
      2026-08-03 the fast `check.sh` pass fails on one too, not just the gate;
      it used to print `ok` for a design 20 mm under the bore floor)*
- [x] **Two identical ports mate, twist shut, and GEOMETRICALLY retain** —
      measured by `lib/nuggs-coupling-mates.conf`: 0 facets of interference
      seated at the insertion clocking and at BOTH locked clockings, 47.8 mm³
      of trapped material on pull-off when locked, over 28.1 mm² of bearing
      area *(round 2; both-directions coverage added round 6)*
- [ ] **The joint resists a stated axial LOAD** — not the same item, and
      splitting them is the point (PR #78 review). Everything above is a
      boolean intersection: it proves the two solids cannot occupy the
      pull-off position, which is a statement about *geometry*, not about
      what PETG does at a given force. Bearing area is not strength — layer
      adhesion, print orientation and `port_tol` all move the real number and
      none of them appear in a mesh. This item needs a printed pair, a
      defined load or torque criterion, and a measurement
- [x] **The joint's clearance does not depend on the caller's `$fn`** — the
      standard is one standard or it is not a standard. Pinned inside the
      port and gated: the insertion case passes at mate-check's hardcoded
      `$fn = 96`, and the port measures identically at caller `$fn` of 16,
      48, 96 and 128 (NOTES.md round 5)
- [ ] Minimum internal diameter ≥ 70 mm measured on every exported STL
- [ ] The coupon has been **physically printed** and the joint exercised
- [ ] README leads with the PLOS One position and the **corrected** DTSchB
      attribution, plus the honest bill and the honest confidence ladder
- [ ] The emergency opening action is stated in one sentence

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| ~~B0~~ | ~~Make the coupling work~~ | **Done in geometry, round 2.** Nests, twists both ways, **geometrically** retains over 28.1 mm² of bearing area. Not a load test — see the v1 axial-load item, which is deliberately still open | — |
| ~~B1~~ | ~~Bed contact on the straight~~ | **Done, round 3.** lug_deg 30->40: contact 396->528 mm2, coverage 52->69%, printcheck warning cleared, joint unchanged | +4 g |
| **B1a** | **Print the coupon and tune `port_tol`** | Now top. The joint is proven in geometry, not in plastic. Until a printed pair twists at a sane torque, every fit number here is a guess — and it is also the only way to know whether bed contact is really solved | ~90 g, 7 h |
| **B1d** | **Make the port a shared library with a gated fit** | Promoted 2026-08-03 by N10. A standard that lives inside one design's `.scad` is not a standard: a second consumer inherits it by copy, and nothing in this repo gates a *fit*. Includes pinning the port's own tessellation, since the joint's clearance currently varies with the caller's `$fn` | Re-gates every design (a `lib/` path sets `infra=true`) |
| B1b | Degenerate zero-volume shells | argus-diff reports 12 bodies of 0.0 mm3 on the straight under CI's manifold backend; CGAL shows 4-6 zero-area triangles at r=ro and r=o_in. Pre-existing, zero material, harmless to slicing — but it makes every geometric diff noisy, which costs a reviewer attention on the diffs that matter. **New evidence (2026-08-03):** removing `nuggs_port()` from `bulkhead_in` took that part from 84/100 with degenerate faces to **100/100 with none**, which localises the slivers to `nuggs_port()` rather than to the tube or flange | Needs openscad-nightly locally first |
| **B1c** | **A docs-vs-model consistency check** | Five of this design's defects have now been a doc claiming something the model does not do, and four were caught by a human rather than a check. **A sixth is now on the record and it was a *citation*, not a dimension** (the TVT attribution). The two that *stopped* recurring — the mate-test clockings and `port_tol` — were fixed by making the check read the value back out of the geometry | Needs a convention that does not exist yet — same blocker as gating the mate test |
| B2 | Elbow-45 | First thing everyone asks for, and two of them make any turn 0–90°. **45° is a ceiling, not a preference**: bore-axis-vertical printing caps a module's axis change at 45° (max \|n_z\| = sin(tilt); sin 45° = printcheck's threshold exactly) | Must assert the inscribed circle ≥ 70 mm (N1). **And its product page must say a bend is not a break (N2)** — this is the module most likely to be misread as one |
| B4 | Turnaround node (was "turnaround chamber") | **Promoted above B3 on 2026-08-03.** Under N2 this is no longer just a branch prerequisite — it is the *only* thing besides an open end and an open module that resets a run, so it is what makes any layout larger than one straight legal | Must assert clear internal width ≥ `body_len_mm`, and ramp its floor to the bore invert (N6/N11). First part enclosing volume, so first needing vents |
| B3 | Rim saddle | The only route for glass enclosures (N9), and no-drill lowers the entry cost more than any other item | Needs an internal ramp ≤ 15° (N4) |
| B4a | **Open-module family** (window ≥ 180°, arc floor) | New, 2026-08-03. An open module is a **break** (N2) and a mass saving; it is also the honest answer to the ventilation limb of N2's source. This is where `nuggs-yard`'s work is rebuilt onto the standard — its own PR, not this one | Every family that claims the port owes the gate a conformance case |
| B5 | Wye-45 | Branch. **No longer "may be non-compliant"** — under the per-run rule it is compliant iff every leg is short and every terminus is a node or an enclosure. Needs B4 first | A wye at bore diameter is not a break; the part must not be documented as one |
| B6 | Bulkhead variants (thick plywood, thin PP) | Widens the enclosures served | Small |
| B7 | Elbow-90 | **Now impossible as one part.** Bore-axis-vertical printing caps a module at 45° of axis change, so a 90° turn is two B2s. Kept in the list only so the answer is recorded rather than re-litigated | — |
| B8 | Factory-port blank | Caps a commercial cage's stock port so the owner can cut a proper one. **Replaces** any notion of a reducer (N8) | Small |
| B9 | Drainpipe adapter | 3 in sch40 ID is 77.3 mm — above N1 but below our 80 mm, so it *necks* the animal. Document as a neck, never sell as an upgrade | |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| **Is the 2× body-length rule per tube or per system?** | **Blocks publishing N2's relaxation.** This is the hinge of the whole re-charter and it rests on plural German in a search summary (research §11.6, LOW confidence) | Per tube → per run. If the PDF says otherwise, N2 reverts to a total and the branch/loop scope closes again |
| Head-and-body length of the actual animal | **Blocks N2's real value** | `body_len_mm = 180` (Merck upper figure) |
| Shoulder width, hip width, head width with both pouches loaded | Not blocking, but it is the **only** unsourced input in the design — nobody publishes it. It is also what the ~45 mm body width behind the 110 mm hairpin figure is guessed from | 80 mm is generous. This is an assumption, not a derivation |
| Which two enclosures, and their wall thickness (calipers) | Blocks the bulkhead's real dimensioning | Plastic bin, 1.5–20 mm range supported |
| Bedding depth in each, and the level difference | Blocks mounting height guidance | 25–30 cm substrate; ≤ 41.4 mm level difference on a 160 mm straight |
| Does the owner have an 89 mm hole saw? | **Blocks buildability** — no hole saw, no v1 | Assumed yes; it is a stocked size but not in a 13-piece set |
| PETG or PLA? | Not blocking; changes `port_tol` and how loud N7 gets | PETG |
| Licence | Blocks first STL release — and now blocks more, since N10 means the port spec is meant to be quoted by third parties | Permissive, no NC clause |
| Is the hamster actually called Nugget? | Cosmetic | Fallback: *Nocturnal Underground Genderless Gallery Standard* |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-02 | Short bridge between two enclosures, not a tube system | TVT's 2 × body-length limit makes a sprawling run non-compliant; PLOS One rates the category unsuitable, so the design answers each cited defect or omits the part. **⚠️ Superseded 2026-08-03 — and its premise was wrong twice over: the limit is DTSchB's, not TVT's, and it reads per tube, not per system** |
| 2026-08-02 | Bore 80 mm, floor 70 mm as an assert | Commercial ~57 mm is 18.4 % under the floor; the animal cannot report a too-narrow bore, so it cannot be a tunable minimum |
| 2026-08-02 | Genderless coupling | One tolerance knob, one coupon, zero coupler parts — and it is what makes N5 (one-action opening) physically true |
| 2026-08-02 | No vent slots in v1 | N3 means nothing encloses air, so there is nothing to vent; this also removed the indexing problem that broke earlier connector proposals |
| 2026-08-02 | Ship the first round with the coupling documented as broken | A green gate plus an honest NOTES.md beats a design that looks finished; the three defects were measured, not suspected |
| 2026-08-02 | Rib is a narrow tab (`rib_deg = 12`), not the full sector width | The entry slot must admit the rib axially, so a full-width rib leaves nothing to twist under. This is what made round 1 retain nothing |
| 2026-08-02 | Circumferential run spans the full sector, so the joint locks in either twist direction | Handedness is a thing to get wrong for no benefit, especially one-handed during an emergency (N5) |
| 2026-08-02 | Every sector is one swept polygon, never a union of two arcs | Two arcs sharing an exact radius leave a coincident cylindrical surface and CGAL returns a non-watertight mesh |
| 2026-08-03 | lug_deg 30 -> 40 to fix bed contact, not the coupling | The part stands on its sector tips, so sector width IS first-layer area. 16 degrees were sitting unused under the asserted ceiling. Mate test identical at 30/40/44, so the joint is unaffected |
| 2026-08-03 | 40 not 44, though 44 anchors more | 44 leaves 2 deg of headroom on lug_deg + twist_deg <= pitch/2; 40 leaves 6, so twist_deg can grow to 20 if the printed coupon says the twist is too short. The unmeasured fit gets the margin |
| 2026-08-03 | No sacrificial first-layer tie ring yet | It would make one continuous ring, but a part that must be removed is an N6 chew-edge risk if forgotten. Not worth that trade before a real print says the six islands are insufficient |
| 2026-08-03 | `port_tol` stays ONE knob, in millimetres; the bayonet's angles are derived from it per radius | It was being spent as both mm and degrees, realising 0.2317 mm/side instead of 0.300 and making circumferential clearance scale with `bore_d` — so "one tolerance knob, one coupon" was a claim, not an implementation. Adding a second `port_tol_deg` parameter would have made the claim false by construction, which is the thing being fixed (#56/1) |
| 2026-08-03 | **Removed the coupling port from `bulkhead_in`** | 14 150 mm³ of sector tips, groove mouths and proud rib tabs sat 13 mm inside the enclosure at bedding height (N6), and another 2 869 mm³ stood 6 mm proud of the flange's own clamping face so the inner flange could not seat flat on the wall. Nothing mates with it: the straight couples to `bulkhead_out`, `assembled()` never instantiates this part, and the README has always described it as flange + spigot. The only thing it could serve is an in-enclosure module, which is Never scope. printcheck 84 → **100/100**, 56.7 → 38.1 g (#56/3) |
| 2026-08-03 | **N6 stands as written — no restatement needed** | #56 asked whether N6 had to be softened because the reference part failed it. It doesn't: the part was wrong, not the rule. Any future in-enclosure module is a change to the **Out of scope → Never** line first, and only then a question about N6 |
| 2026-08-03 | `NUGGS_REV` is engraved, never proud, and only on faces that look at the room | It was declared and used nowhere while NOTES.md claimed the length limit was embossed on the part. A raised character is the chew-initiation edge N6 forbids, so the mark is recessed 0.6 mm; `bulkhead_in` stays unmarked because every face it has is inside the enclosure or buried in the wall hole (#56/4) |
| 2026-08-03 | "One straight per run" is carried on the part and in the README, not only in NOTES.md | It is the only protection against exceeding N2 by assembly, and OpenSCAD cannot assert what a human bolts together. Two straights *will* mate and feel right — that is what genderless costs (#56/4, #56/5) |
| **2026-08-03** | **RE-CHARTER: nuggs is a SYSTEM whose standard is the port.** "It is not a tube *system*" is struck from this charter, from README.md and from NOTES.md's goal | The framing existed to satisfy a length rule that (a) is attributed to the wrong organisation and (b) reads per tube, not per system (research §11.2, §11.4). With the rule correctly scoped, the thing that was forbidden — more than one module in a layout — is legal under a topology requirement instead of a prohibition. **N10 is added** so "system" means one standard rather than a family of near-misses |
| **2026-08-03** | **N2 is re-scoped from a total-system sum to a PER-RUN limit, and re-attributed to DTSchB** | The number does not move (2 × body length). Three things change: it is measured per run rather than summed over the system; it names the **Deutscher Tierschutzbund** position paper *Tierschutzwidriges Zubehör* rather than TVT Merkblatt 62, which was never the source of any length limit any search returned; and it comes with a **definition of what resets it**. The v1 Bin Bridge passes under both rules — this was not done to rescue a failing design. (This entry first cited 238 mm, then 230; the measured figure is **246 mm**, once the four bulkhead flange plates are counted. All three pass 360, which is why none of the errors surfaced — see NOTES 6.4/6.5) |
| **2026-08-03** | **A bend, a junction at bore diameter, a coupling and a top hatch do NOT break a run** | This correction matters more than the number. In an 80 mm bore the animal cannot rotate, so a bend turns the *tube*, not the *animal*; a wye at bore diameter is a branching one-way bore that multiplies the ways to be trapped; a coupling is a joint. A top hatch resets **retrieval**, which is a different constraint with a different resetter — collapsing the two is the trap. Only a widening ≥ body length, an open end, or a ≥ 180° window resets the reversing count |
| **2026-08-03** | **N3 survives, but is now satisfied by topology rather than by banning branches** | The old N3 forbade branches because a branch terminus is a dead end. Under N2's node definition a branch is legal when every terminus is a node or a ventilated enclosure — which is also the wild-burrow topology (Gattermann 2001). A stub at bore diameter is still forbidden, and that is the actual rule |
| **2026-08-03** | **N1 (70 mm) is NOT reopened** | Reviewed against the new evidence and left as a hard assert. The failure mode is silent — grit in a full pouch lacerates the mucosa, leading to impaction and abscess with no visible symptom until surgery — so it cannot be a user judgement. Two honest qualifications are recorded rather than suppressed: the DTSchB 7 cm figure is an *entrance-opening* minimum applied to a bore, and wild burrow tunnels are 40–50 mm. Neither changes the assert |
| **2026-08-03** | **N11: an open module is a tube with a window, never a flat-floored trough** | Forced by N6 and by arithmetic, not by taste. Against a round mate, a flat floor tangent to the invert stands 6.93 mm proud at the paw-span edge (22.5 mm lateral) — a full-height vertical rim across the joint, i.e. a toe-stub; a chord floor gives an 8.78 mm centreline pit that also collects bedding and urine. Only the arc floor gives a 0.000 mm step, because both modules' bores are the same cylinder. The 45° per-module bend ceiling that follows from bore-axis-vertical printing is **accepted as the price** |
| **2026-08-03** | **The reversing derivation is labelled ENGINEERING JUDGEMENT wherever it appears** | The 2× multiplier is (probably) sourced; "an animal should not have to reverse more than its own body length" is not, and neither is the ~110 mm hairpin width it depends on. No literature measures either. A number that has been given a meaning is more useful than an inherited one — but presenting the meaning as literature is exactly the citation defect this round exists to fix |
| **2026-08-03** | **The nuggs-yard rebuild is a later PR** | Its gendered lap-skirt joint is superseded by N10, and its open modules must be rebuilt on the port with an arc floor (N11) — including the loss of its one-part 90° plan curve, which the 45° ceiling makes impossible. That is real geometry work with its own gate run, and folding it into the re-charter would make the charter change unreviewable |
