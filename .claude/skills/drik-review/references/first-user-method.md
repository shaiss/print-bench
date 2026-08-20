# Drik's field guide — first-user method reference

The method and homework Drik reviews with. Cite these as lived use ("my
keys will eat that tab"), never as an audit of anyone else's numbers.

## Deriving the first user

Answer in one sentence each, at the top of the review:

1. **Who prints-and-uses this first?** Not "makers" — a person with a
   situation (the board-gamer mid-match, the cook with wet hands, the
   commuter with keys and a coin in one pocket).
2. **What is one real session of use?** A concrete script with a beginning
   and end: setup → the repeated action → teardown. The repeated action is
   where the design lives or dies.

If the design dir/PM.md names a customer, start there; if it doesn't,
derive one and say you did.

## Session-of-use frequency method

Walk the session and count each mechanism's exercises per session, then
per week of ownership. Rank features by that count — the top of the list
is the hot path, whatever the backlog calls it. The output is a sentence
like: "every shot opens a door → 16 slide/lift/re-lock cycles per match →
the 'polish' detent is gameplay-critical." Frequency math is Drik math:
it supports *your* re-ranking, it never re-checks the designer's geometry.

Ownership cycles compound: a daily-carry fidget at ~100 cycles/day sees
~36k/year. Anything unmeasured on that path ("paper value, untested") is a
promotion candidate: the field test stops being polish.

## Real-object homework (measure the payload, not the pocket of air)

Before judging "it fits X", look up or recall what X actually measures.
Frequent flyers:

| Object | Real dimensions |
|---|---|
| Credit/ID card | 85.6 × 54.0 × 0.76 mm |
| AA / AAA battery | Ø14.5 × 50.5 / Ø10.5 × 44.5 mm |
| CR2032 coin cell | Ø20 × 3.2 mm |
| US quarter / Euro 2€ | Ø24.26 × 1.75 / Ø25.75 × 2.20 mm |
| Standard split ring 25 mm | wire Ø1.0–1.4 mm |
| USB-C plug overmold | ~12.4 × 6.5 mm, bodies vary to 18 × 8 |
| SD / microSD card | 32 × 24 × 2.1 / 15 × 11 × 1.0 mm |
| Pen/pencil | Ø7–12 mm |
| Standard poker card deck | 63 × 88 mm, ~15–18 mm boxed |
| Hex keys/bits (1/4" hex) | 6.35 mm across flats |

Anything not on the list: state the dimension you assumed and where it
came from. An unstated payload assumption is itself a finding.

## Handling & feel heuristics

- **Weight**: PLA ≈ 1.24 g/cm³, PETG ≈ 1.27 — at typical 15 % infill a
  part weighs roughly 40–60 % of solid. A "substantial" feel needs mass;
  a big light part feels cheap. CI's filament grams are the real number.
- **Edges**: any edge a thumb or palm lives on wants a chamfer/round;
  as-printed square edges on show surfaces feel and look raw.
- **Sound**: loose fits rattle, and rattle reads as broken (or, in a
  hidden-information game, as *information* — see the leak audit).
- **Pocketability**: > ~45 mm diameter or > ~8 mm thick stops being a
  pocket coin and becomes a desk object; > ~90 mm stops being EDC at all.
  Name which artifact it actually is.
- **Layer direction vs load**: printed layers shear apart under bending
  across the Z seam — a thin tab loaded across layers (keyring torque,
  clip flex) is the classic week-two failure. Ask where this part's load
  crosses layers.
- **Keys-and-bag survival**: engraved detail shallower than ~0.4 mm
  polishes away in a pocket with keys; proud fine detail chips.

## Failure-cost framing

Always in user terms, priced with CI's own numbers: the print time and
filament grams of the part that dies, plus the moment it dies in
("mid-dinner, sixteen welded doors over $60 of omakase"). Then judge the insurance: does
a coupon exist, does it exercise the *same* risky joint, and is its cost a
fraction of the part it protects? "23 minutes of insurance against a
49-minute brick" is the shape of a good answer.

## Information-leak audit checklist

State the concealment contract first (what is this design supposed to
hide, if anything?). Then sweep:

- **Sightlines**: clearance gaps, shadow gaps, translucent walls at
  typical filament thickness (< ~1.2 mm PLA glows through backlight).
- **Sound**: does a loaded state rattle/thud differently from empty when
  bumped? (A detent or preload that kills rattle also kills the tell.)
- **Weight/balance**: can a hand feel which side/cell is loaded?
- **Touch**: temperature, flex, or texture differences between states.
- **History**: wear patterns, scuffs, or marks that reveal usage or
  configuration the design means to conceal.

Stateless designs (both faces public, nothing concealed): say once that
the leak surface is empty and move on — an honest non-finding beats a
padded one.

## Product-page honesty checklist (customer's read, not doc audit)

- Does the page tell me what I'm actually getting (true size class,
  weight, part count, assembly required)?
- Would I succeed printing it from the page alone (settings, print-first
  coupon, warnings that matter)?
- Are safety/care caveats (food contact, heat, load limits) present —
  and still present this round?
- Do the images sell what ships? (AI disclosure rules live in SKILL.md §4.)
- Is any claim untestable or untested-but-stated-as-fact? Quote it.
