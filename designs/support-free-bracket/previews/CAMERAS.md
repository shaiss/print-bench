# Frozen preview shots — support-free-bracket

Rendered by `./scripts/render.sh support-free-bracket --previews` from
`cameras.conf` beside this file. Cameras are **fixed** now that they are
reviewed: a new region gets a new `cameras.conf` line, never a moved one, so
before/after comparisons across review rounds stay aligned.

| Shot | What it shows |
|---|---|
| `contact-sheet` | The as-printed 4-view (iso / top / front / bottom-iso) — the exact pose CI slices. |
| `iso` | The whole bracket in its print orientation: plate standing at the back, arm flat on the bed, vault brace rising between them. |
| `bottom-iso` | The support-free **proof shot**, from underneath: the vault ceiling sloping over the open cavity, the teardrop roofs, and no flat downward-facing ceiling anywhere. |
| `front-bores` | Head-on at the plate face: both M5 teardrop bores with their pointed roofs up (the flip of issue #398 verified visually). |
| `side-vault` | Side elevation: the 42° vault line running from plate to arm — the triangle that replaces a support-needing flat ceiling. |
