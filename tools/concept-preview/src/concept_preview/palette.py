"""The drafting system, defined once: every colour, line weight, text style,
fill pattern, marker and sheet-furniture measurement a concept sheet uses.

Provenance. These tokens are lifted from the approved pre-roll elevator
concept canvas (issue #471's design session; the canvas is
https://claude.ai/code/artifact/b3e488f9-be4b-4bb9-a8c3-b8bc56c484d3, cited
from designs/preroll-elevator/NOTES.md). That canvas was four hand-authored
sheets that each restated the same stylesheet; here the stylesheet exists in
exactly one place, and every sheet the emitter writes embeds the identical
bytes from :func:`stylesheet` and :func:`defs` — so two sheets cannot drift
apart, which is the property issue #472 asks for ("defined once and reused
by all sheets").

One deliberate departure from the reference: it loaded Oswald and IBM Plex
Mono from Google Fonts. A served sheet here must carry NO external reference
(the product site's no-CDN rule, issue #474), so the font stacks name those
faces first — used when installed locally — and fall back through local
families to the generic ``sans-serif`` / ``monospace``. Nothing is fetched.

The label-collision check measures text with a deterministic monospace model
(:data:`MONO_ADVANCE`): every monospace face in the fallback stack advances
0.6 em per glyph (IBM Plex Mono, DejaVu Sans Mono, Menlo, Courier), which is
what makes a label's footprint computable without a renderer. The headline
face is proportional, so it is measured with the conservative
:data:`HEAD_ADVANCE` — wide enough for a generic sans fallback, since the
condensed face may not be installed.
"""

from __future__ import annotations

# ── Colour tokens ─────────────────────────────────────────────────────────
GROUND = "#0e2740"          # the deep-blue sheet
INK = "#d6e8f7"             # primary line work (.ln, .metal stroke, .t-lbl)
INK_HEAD = "#eaf3fb"        # sheet heading (.t-h)
INK_SUB = "#9db8d1"         # secondary text (.t-sub)
INK_TB = "#b9d2e8"          # title-block text (.t-tb)
LINE2 = "#7fa8c9"           # secondary line work (.ln2: face edges, ticks)
AMBER = "#f4b24a"           # accents: leaders, dimensions, the title rule
AMBER_HI = "#ffc866"        # motion highlight
CENTRE = "#6f9ac0"          # centre lines (.cl)
HATCH = "#4f7aa0"           # section hatching
THREAD = "#89b0d0"          # thread profile lines
FRAME = "#3d6284"           # title-block / note frame
GRID_MINOR = "rgba(127,168,201,0.07)"   # 20 px grid
GRID_MAJOR = "rgba(127,168,201,0.13)"   # 100 px grid
METAL_FILL = "rgba(214,232,247,0.05)"   # faint body fill
FRAME_FILL = "rgba(255,255,255,0.03)"   # title-block / note fill

# ── Fonts (local stacks only — no web-font fetch, see module docstring) ───
FONT_HEAD = ("Oswald,'Arial Narrow','Roboto Condensed','Helvetica Neue',"
             "Arial,sans-serif")
FONT_MONO = ("'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,"
             "'DejaVu Sans Mono','Liberation Mono',monospace")

# ── Text metric model (the collision check's ruler) ───────────────────────
MONO_ADVANCE = 0.6    # em per glyph, every monospace face in FONT_MONO
HEAD_ADVANCE = 0.72   # em per glyph, conservative for a generic sans fallback
ASCENT = 0.8          # em above the baseline
DESCENT = 0.2         # em below the baseline

# Text classes: (font, weight, letter-spacing px, fill, advance em/glyph).
TEXT_CLASSES = {
    "t-h":   (FONT_HEAD, "600", 2, INK_HEAD, HEAD_ADVANCE),
    "t-sub": (FONT_MONO, "400", 1, INK_SUB, MONO_ADVANCE),
    "t-lbl": (FONT_MONO, "400", 0, INK, MONO_ADVANCE),
    "t-amb": (FONT_MONO, "400", 0, AMBER, MONO_ADVANCE),
    "t-tb":  (FONT_MONO, "400", 1, INK_TB, MONO_ADVANCE),
}

# Line/shape classes, as CSS declarations. The reference's names, kept so a
# reader who knows the canvas reads the emitted source the same way.
SHAPE_CLASSES = {
    "ln":       f"fill:none;stroke:{INK};stroke-width:1.6",
    "ln2":      f"fill:none;stroke:{LINE2};stroke-width:1",
    "metal":    f"fill:{METAL_FILL};stroke:{INK};stroke-width:1.6",
    "cut":      f"fill:url(#hatch);stroke:{INK};stroke-width:1.5",
    "cut-ring": "fill:none;stroke:url(#hatch)",
    "amb":      f"fill:none;stroke:{AMBER};stroke-width:1.8",
    "ambd":     f"fill:none;stroke:{AMBER};stroke-width:1.2;stroke-dasharray:6 4",
    "lead":     f"fill:none;stroke:{AMBER};stroke-width:1;opacity:.9",
    "dimln":    f"fill:none;stroke:{AMBER};stroke-width:1",
    "cl":       (f"fill:none;stroke:{CENTRE};stroke-width:.9;"
                 "stroke-dasharray:8 3 1 3;opacity:.65"),
    "tb":       f"fill:{FRAME_FILL};stroke:{FRAME};stroke-width:1",
    "bal":      f"fill:{GROUND};stroke:{AMBER};stroke-width:1.4",
    "rule":     f"fill:none;stroke:{AMBER};stroke-width:2",
    "rule-thin": f"fill:none;stroke:{AMBER};stroke-width:1.4",
}

# ── Type sizes (px) ───────────────────────────────────────────────────────
SIZE_HEAD = 27
SIZE_SUBTITLE = 12
SIZE_LABEL = 13       # leader label (.t-lbl)
SIZE_LABEL_SUB = 11   # leader second line (.t-sub)
SIZE_CALLOUT = 12     # amber leader callout (.t-amb), e.g. a diameter
SIZE_DIM = 13         # dimension text
SIZE_BALLOON = 11     # balloon number
SIZE_NOTE = 11        # note head + lines
SIZE_TB_TITLE = 12    # title-block first line
SIZE_TB = 10.5        # title-block second/third lines
SIZE_BOM_HEAD = 13
SIZE_BOM = 11.5

# ── Primitive measurements ────────────────────────────────────────────────
BALLOON_R = 10
LEADER_GAP = 6        # text edge → leader start
LABEL_SUB_DY = 16     # leader main line → second line baseline
DIM_EXT_OVERSHOOT = 8  # extension line runs past the dimension line by this
DIM_TEXT_GAP = 10     # dimension line → nearest glyph edge
GRIP_PITCH = 8        # knurl tick spacing on a hex head

# ── Sheet furniture (all sheets share these, so they all read alike) ──────
SHEET_MARGIN = 44             # heading / rule inset
HEAD_BASELINE = 60
SUBTITLE_X = 46
SUBTITLE_BASELINE = 86
RULE_Y = 99
HEADER_BOTTOM = 104           # the header band reserved for the emitter
TB_W = 236
TB_H = 72
TB_MARGIN_RIGHT = 28
TB_MARGIN_BOTTOM = 32
TB_DIVIDER_DY = 30
TB_PAD_X = 12
NOTE_X = 28
NOTE_GAP = 30                 # note box → title block
NOTE_LINE_DY = 18
NOTE_MAX_LINES = 4
BOM_W = 372
BOM_COLS = {"no": 4, "part": 38, "qty": 256, "print": 292}
BOM_ROW_DY = 26
# One space each side: SVG collapses runs of whitespace when it renders (the
# reference's "   ·   " drew as " · "), and the width ruler should measure
# what is drawn.
SHEET_SEPARATOR = " · "

# The four canonical sheets, in sheet-number order, with the reference
# canvas's artboard size and wording as defaults.
SHEETS = ("exterior", "cutaway", "section", "exploded")
SHEET_DEFAULTS = {
    #            (w,   h),   heading (None → the spec title), subtitle, caption
    "exterior": ((620, 940), None, "EXTERIOR ELEVATION", "EXTERIOR — ELEVATION"),
    "cutaway":  ((900, 940), "HOW IT WORKS", "LONGITUDINAL HALF-SECTION",
                 "MECHANISM — HALF SECTION"),
    "section":  ((680, 760), "SECTION A–A", "TOP SECTION — LAYOUT",
                 "TOP SECTION A–A"),
    "exploded": ((780, 1040), "EXPLODED VIEW & PARTS",
                 "ASSEMBLY ORDER, TOP DOWN", "EXPLODED · BOM"),
}
SHEET_MIN = 320
SHEET_MAX = 2400


def stylesheet() -> str:
    """The one <style> body every sheet embeds, byte-identical across sheets."""
    rules = [f"svg{{background:{GROUND}}}"]
    for cls, (font, weight, spacing, fill, _adv) in TEXT_CLASSES.items():
        decl = f"font-family:{font};font-weight:{weight};fill:{fill}"
        if spacing:
            decl += f";letter-spacing:{spacing}px"
        rules.append(f".{cls}{{{decl}}}")
    for cls, decl in SHAPE_CLASSES.items():
        rules.append(f".{cls}{{{decl}}}")
    return "\n".join(rules)


def defs() -> str:
    """The shared <defs> body: grids, the section hatch, and the markers.
    Per-shank thread patterns live with their shank (their period is the
    shank's own), never here."""
    return "\n".join([
        '<pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">'
        f'<path d="M20 0H0V20" fill="none" stroke="{GRID_MINOR}" stroke-width="1"/></pattern>',
        '<pattern id="grid5" width="100" height="100" patternUnits="userSpaceOnUse">'
        f'<path d="M100 0H0V100" fill="none" stroke="{GRID_MAJOR}" stroke-width="1"/></pattern>',
        '<pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)">'
        f'<line x1="0" y1="0" x2="0" y2="7" stroke="{HATCH}" stroke-width="1"/></pattern>',
        # auto-start-reverse: the start arrow points out at its extension
        # line, as the end arrow does at its own.
        '<marker id="dim" markerWidth="12" markerHeight="12" refX="9" refY="6" '
        'orient="auto-start-reverse">'
        f'<path d="M2 2L9 6L2 10" fill="none" stroke="{AMBER}" stroke-width="1.3"/></marker>',
        '<marker id="dot" markerWidth="9" markerHeight="9" refX="4.5" refY="4.5">'
        f'<circle cx="4.5" cy="4.5" r="2.3" fill="{AMBER}"/></marker>',
    ])


def advance(cls: str) -> tuple[float, float]:
    """(em-per-glyph, letter-spacing px) for a text class — the ruler."""
    try:
        _font, _weight, spacing, _fill, adv = TEXT_CLASSES[cls]
    except KeyError:
        raise KeyError(f"unknown text class {cls!r}") from None
    return adv, float(spacing)
