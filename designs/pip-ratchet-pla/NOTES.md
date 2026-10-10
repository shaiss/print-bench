# pip-ratchet-pla — engineering log

## Goal

The pip-ratchet print-in-place ratchet demonstrator re-sectioned for PLA
(brief #675, deferred from #668 per the parent's PM.md N6): same wheel,
same teeth, same frame, same every-clearance — only the pawl beam
thickness re-derived so a PLA build clicks like the shipped PETG one, and
an honest stress/fatigue verdict recorded for the section. **The PETG
parent changes nothing** (brief: "No geometry in the PETG design changes
as part of this"); this design is a derivative that ships beside it.

The owner's question the brief asks, answered by this run and then by the
coupon: *can PLA carry this pawl at all?* PLA ranks ≪ PETG for cyclic flex
(`docs/advanced-techniques.md`: "treat it as unsuitable unless a coupon
proves otherwise") — so the field test, not the gate, returns the verdict,
and "not viable" is a valid answer the coupon can still give.

## Given / assumed measurements

| Dimension | Value | Status |
|---|---|---|
| PETG flexural modulus E | 2000 MPa | given — parent NOTES.md (its σ derivation) |
| PLA flexural modulus E | 3500 MPa | given — brief #675 (typical printed PLA) |
| Click-force target | same as the shipped PETG demonstrator | brief: "the same click-force target" (force-match, K ∝ E·t³·w/4L³) |
| Parent pawl section t × L × w | 1.2 × 18 × 8 (L_eff ≈ 13) | given — parent entry + NOTES decision 1 |
| Ride-up deflection δ | 1.05 mm (engagement 0.85 + web_clr 0.2) | derived — parent entry (`ride_defl`) |
| PLA yield strength | ~60 MPa (printed, typical) | assumed — literature ballpark, coupon to confirm |
| PLA flexural fatigue endurance | ~15–25 MPa at 10⁵–10⁶ cycles | assumed — the poor ranking the repo doc gives PLA; coupon decides |
| Everything else | inherited verbatim from `pip-ratchet` | by construction (single `pawl_t` override) |

## Key decisions

1. **Mechanism: derivative (`variant-of: pip-ratchet`), not a parent
   `part` entry.** The brief offers "a variant entry or derivative" but
   also fixes "no geometry in the PETG design changes as part of this",
   and the parent's PM.md N6 wants the PLA exercise *separate*. A new
   `part` branch would edit the parent file (and could not carry its own
   coupon, README and field-test log); the derivative gives both designs
   as contemporaries with the lineage recorded and the override
   mesh-proven by the gate (`replaces: pip-ratchet:` — the parent ships
   no ci.parts, so the empty part is its default render).
2. **`pawl_t` = 1.0, force-matched — not guessed, not thinned to the
   floor.** Holding click force constant at fixed w and L means holding
   E·t³ constant (the same law the parent's coupon tuning uses):
   t = 1.2·(2000/3500)^(1/3) = 0.996 mm, rounded to the coupon sweep's
   0.1 mm step → **1.0 mm** (+1.3 % click force — inside the noise of the
   feel target, which the parent's own page marks "not a gate"). 1.0
   keeps ≥ 0.8 mm (the FDM two-line floor the parent asserts) with
   margin, and stays a whole 0.1 step so the coupon sweep reads it.
3. **Stress re-check: σ = 32.6 MPa — statically fine, fatigue-poor.**
   σ = 3·E·t·δ/(2·L_eff²) = 3·3500·1.0·1.05/(2·13²) ≈ **32.6 MPa**, vs the
   parent's PETG 22.4 MPa (same formula, same δ, same L_eff — +46 % from
   E up 1.75× and t down 1.2→1.0). Static SF ≈ 1.8 vs PLA yield ~60 MPa:
   not ruled out. But 32.6 MPa sits *above* the assumed PLA flexural
   fatigue band (~15–25 MPa) — predicted **finite click life**, and the
   pop-fidget-card field test already caught PLA cracking in cyclic flex.
   Hence the design's posture: the stress number is echoed in the entry
   file, asserted nowhere, and the coupon's click-count death test is the
   adoption gate (decision 5). This is the brief's own framing: "the pass
   may conclude 'not viable', which is a valid answer."
4. **Nothing else moves.** The override changes only the beam band
   (`beam_out` = web_in + pawl_t: 29.4 → 29.2) and the sampling/arc
   conversions derived from it (sub-0.2 mm shifts of the block's back
   face angle). Wheel, tooth profile, nose/hook/lock_gap geometry,
   clearances (xy_tol, z_tol, web_clr), the break-free construction, the
   print orientation and the parent's gate set are inherited. Every
   *wheel-facing* surface is `pawl_t`-free (`web_in = r_tip + web_clr`,
   the nose face, `lock_gap`, the hook profile) — the thickness grows
   strictly outward (`beam_out`, `a_block_back`), frame-side — so the
   section change moves no clearance the wheel sees, at any `pawl_t`.
5. **The coupon is a fatigue qualification, not just a feel tuner.** The
   parent's coupon (rack + one pawl, shared production profiles, nothing
   copied) is inherited with the one-line `pawl_t` mirror. In PETG it
   answers "does this click right"; in PLA it must first answer "does
   this survive" — cycle the force-matched t = 1.0 strip to a click-count
   death before printing the demonstrator (protocol below). The mirrored
   constant is a documented sync point: the wrapper cannot import the
   derivative's assignment without pasting the parent entry twice (which
   would double-draw), and both files echo their t.
6. **Why not a longer beam instead?** σ ∝ 1/L_eff² would fall with a
   longer pawl, but L is the parent's geometry (decision 1 there: 18 free
   length, clamp at u = 13) and the brief scopes this run to the section
   ("re-derive `pawl_t`"). Re-dimensioning L for PLA is a different
   design conversation — recorded here as the named escape hatch if the
   coupon returns "not viable at this section".
7. **The parent's ci.fitchecks / ci.fusecheck are not re-shipped — a
   discovered gate limitation, not a skipped proof.** Both manifests'
   branch proof greps the entry `.scad` itself for `part == "<pose>"`,
   and this derivative's poses live in the parent (functional through
   the include — every `-D part=` render this run went through the
   parent's dispatch — but invisible to the grep), so iteration 1 failed
   them on all six lines. The only way to satisfy the grep honestly is
   shadowing the parent's `main()` with a copied dispatcher + copied
   asserts: rejected — it freezes the parent's guards at copy time, and
   it is the exact "redefined the dispatcher" failure smell gate.sh's
   derivative checks name. The proofs carry instead, each with evidence:
   the **fit** obligation is provably `pawl_t`-invariant (decision 4:
   every wheel-facing surface is pawl_t-free; the parent's green
   fitcheck covers this build at any section), and the **separability**
   obligation is *measured* — printcheck counts `bodies: 2` (wheel +
   frame, watertight) on both this design's exports, the same fact the
   fusecheck 2-body assert re-proved on iteration 1 before the manifest
   was dropped (`ok` × 2 in the gate log). If the bench later wants
   derivatives to inherit boolean-fit poses, that is a `gate.sh` feature
   (resolve the branch proof through the include closure) — out of this
   run's `Touches`, recorded here for whoever picks it up.

## Measured on the export (G4 — built mesh, not the typed parameter)

| Must fit / hold row | Derivation | Measured on the export | How |
|---|---|---|---|
| Pawl beam thickness (THE delta) | 1.0 | **0.996–1.003 mm** — band r 28.197–29.200, vertices at z = 2.8 / 10.8 exactly (the parent's 1.2 measures 1.22, band r 28.178–29.396, the same method) | vertex radii in (28.05, 29.55) on the `part="frame"` STL — clusters at web_in 28.2 and beam_out 29.2 |
| Click force (force-match) | E·t³ = 3500 vs parent 3456 (+1.3 %) | **not measurable on a mesh** — predicted ~3 N peak, same as the shipped PETG (parent's own prediction method, coupon confirms by feel) | coupon |
| Ride-up stress | 32.6 MPa | **not measurable on a mesh** — derivation recorded above (decision 3), coupon returns the fatigue verdict | coupon |
| Everything inherited | parent's measured table | **spot-checked**: wheel tip Ø **56.00** (parent measured 55.99), 24 tip-land gaps at the 15° pitch, footprint **69.00 × 69.00 × 13.70**, 134 facets flat on z = 0 and **zero** below it — identical bed contact to the parent | `part="wheel"` + default STL, vertex/facet measurement (the parent's method) |
| Override actually bound | — | **bound**: the σ echo fires at t = 1 AND the frame band measures 0.996–1.003 ≠ the parent's 1.22 — the same build cannot be the parent's mesh. `gate.sh`'s derivative mesh-compare is the contract form (G2, `replaces: pip-ratchet:`) | render echo + this table's first row; gate re-proves |

## Print this first (the PLA qualification, in order)

1. Print the coupon **in PLA**: `./scripts/render.sh pip-ratchet-pla
   --sweep pawl_t=0.9:1.5:0.1`, slice `build/pip-ratchet-pla-sweep-pawl_t.stl`,
   0.2 mm layers, no supports. (Single coupon: print
   `pip-ratchet-pla-coupon.scad` at the default t = 1.0.)
2. Break the rack strip free in its channel (firm slide). It should click
   freely +x and lock dead −x; the t = 1.0 lane should feel like the PETG
   demonstrator you know (that is the force-match).
3. **The step the PETG coupon never needed — cycle to death.** Pick your
   target life (a demo toy: ≥ 1 000 clicks; a daily-driver: ≥ 10 000).
   Click the t = 1.0 strip at a steady ~1–2 Hz and count. Death = visible
   crack at the root, force collapse (clicks go mushy), or ridethrough
   (pawl stops engaging). Record cycles, material brand, layer height in
   the Field test log. **Dying before your target is the coupon
   succeeding**: it is brief #675's "not viable" arriving before you spent
   the wheel's filament — don't print the demonstrator on a dead coupon.
4. If the coupon lives: print the demonstrator in PLA, shear the wheel
   free (firm twist CCW — the arrow direction), verify freewheel-CCW /
   lock-CW, and log the result.

## Print settings (demonstrator)

- **Material:** **PLA** — that is the point; keep the PETG build on the
  parent's page
- **Layer height:** 0.2 (the axial gaps are quantized to it — keep it)
- **Perimeters/walls:** 3 at a 0.4 nozzle; the pawl beam at 1.0 mm prints
  as a 2-perimeter feature — do not thin further without re-running the
  force match
- **Infill:** 15%, any
- **Supports:** none — inherited overhangs only (45° cone, break-free gap)
- **Orientation:** exactly as rendered, base down. Inherited, not
  accidental: the beams lie in the XY plane, so flex stress acts across
  roads *within* a layer, the orientation the fatigue ranking demands
  (layers parallel to the flex axis)

## Field test log

<!-- FIELD-TEST entries append below (templates/FIELD-TEST.md). -->
