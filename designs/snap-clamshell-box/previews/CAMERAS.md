# Frozen preview cameras — snap-clamshell-box

- `contact-sheet` — the standard 4-view sheet (iso / top / front / bottom-iso)
  of the flat print pose. Owned here so `--previews` (and CI's regen) re-render
  it whenever the geometry moves — it can never go stale again (issue #265,
  the #69 hole).
- `closed-latched` — the closed box (`demo_fold=180`) from a front-right
  three-quarter, chosen so the latch fix reads at a glance: the windowed strip
  standing `latch_clr` proud of the lid wall, the buttress step below it, and
  the tab visible inside the window. Replaces a hand-committed straight-on
  elevation no manifest produced (issue #265); the framing is deliberately new —
  the old head-on view could not show the standoff, which is the feature the
  fix added. Camera frozen 2026-08-16 (PR #268, round 1).
