# Frozen preview cameras — descriptions

One line per `cameras.conf` entry: what the shot exists to show and what a
reviewer should check in it. Cameras are **fixed** now that each has been
reviewed — a new region gets a new `cameras.conf` line, never a reframed
existing one.

| Shot | What it shows / what to check |
|---|---|
| `contact-sheet` | The 4-view default render (iso / top / front / bottom-iso) of the printable `cap` part, exactly what CI slices. The bottom-iso quadrant is the one to read for print pose: sector tips as bed contact, the corrugated ceiling printing supportless. |
| `hero` | Keeper-side face at 62° — the face the user sees mounted. Three grip bosses in a 120° triangular layout at radius 20: the tight probe pair aft, the gland forward. Slot cuts through each boss wall, 0.8 mm lead-in chamfers at the mouths, flat rim. (Preview-mode colors interior faces green through the sector windows; the CGAL render is watertight, one body.) |
| `print-pose` | The part rotated 235° — the underside as it actually prints, port face down on the three sector tips. Shows the concentric V-groove ceiling relief: ~12–15 fine rings like a vinyl record from the rim inward, interrupted by the three bore mouths. No supports, no danglers, no flat ceiling. |
| `pair` | The cap mated to a pink tube stub (the `pair` part) — the whole point of the coupling. Check: cap sits flush and centered on the tube's collar, the Ø94.9 port flange steps over the Ø84.8 tube, bosses up, clean bayonet engagement with no collision. |
| `cutaway` | Full-render (`render` opt) half-section through the mid-plane — the interior structure. Check: the grip bores are open through-tunnels from mouth to ceiling with no stray solids, boss walls uniform, section faces clean. (The 1.2 mm grooves are below pixel resolution at this zoom — read the corrugation in `print-pose`.) |
