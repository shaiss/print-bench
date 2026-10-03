"""Spec → four standalone SVG sheets.

The emitter owns the look and the sheet furniture; the spec owns what is
drawn and where. Every sheet is built the same way, from the same palette:

    ground (sheet colour + 20/100 px grids)
    header (heading, subtitle ending ``· SHEET n / 4``, the amber rule)
    the spec's primitive rows for this sheet, in file order
    the note box, if the spec gives one
    the bill of parts (exploded sheet)
    the title block

Each drawn unit is wrapped in ``<g class="cp-<kind>" data-src="L<line>">`` so
the checker (:mod:`concept_preview.check`) can name the spec line behind any
finding. The emitter does no auto-layout of the drawing: a primitive lands
exactly where its row says, and furniture text that would overflow its box is
a spec error, not a reflow.

Output is deterministic — the same spec emits the same bytes — so committed
sheets can be verified fresh by re-emitting and comparing.
"""

from __future__ import annotations

from . import palette as P
from . import primitives as prim
from .geom import esc, fmt, text_width
from .spec import Row, Spec, SpecError

FILENAMES = {kind: f"concept-{kind}.svg" for kind in P.SHEETS}


def _primitive(spec: Spec, row: Row) -> prim.Fragment:
    f = row.fields
    try:
        if row.kind == "hatch":
            if "at" in f:
                (x, y), (w, h) = f["at"], f["size"]
                return prim.hatched_rect(x, y, w, h)
            (cx, cy) = f["center"]
            return prim.hatched_ring(cx, cy, f["r"], f.get("ri", 0.0))
        if row.kind == "shank":
            (x, y), (w, h) = f["at"], f["size"]
            return prim.threaded_shank(x, y, w, h, f.get("pitch", 12.0), ident=f"thr-L{row.line}")
        if row.kind == "hex":
            (x, y), (w, h) = f["at"], f["size"]
            return prim.hex_head(x, y, w, h, f.get("chamfer"), f.get("ends", "both"), f.get("grip", 0))
        if row.kind == "dim":
            return prim.dimension_line(f["from"], f["to"], f["text"], f.get("ext", ()), f.get("flip", False))
        if row.kind == "balloon":
            (cx, cy) = f["at"]
            return prim.balloon(cx, cy, f["n"], f.get("to"))
        if row.kind == "leader":
            (x, y) = f["at"]
            return prim.leader(x, y, f["to"], f["text"], f.get("sub"), f.get("anchor"), f.get("tone", "label"))
    except ValueError as e:
        raise SpecError(spec.path, row.line, f"{row.kind}: {e}") from None
    raise AssertionError(f"no emitter for {row.kind}")  # pragma: no cover — schema bug


def _text(cls: str, x: float, y: float, size: float, text: str, anchor: str = "start") -> str:
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return (f'<text class="{cls}" x="{fmt(x)}" y="{fmt(y)}" font-size="{fmt(size)}"{a}>'
            f"{esc(text)}</text>")


def _fits(spec: Spec, line: int, what: str, text: str, size: float, cls: str, room: float) -> None:
    need = text_width(text, size, cls)
    if need > room:
        raise SpecError(spec.path, line,
                        f"{what} {text!r} is {fmt(need)} px wide; it has {fmt(room)} px "
                        f"(shorten it — the emitter does not wrap)")


def _group(kind: str, line: int, body: str) -> str:
    return f'<g class="cp-{kind}" data-src="L{line}">{body}</g>'


def _header(spec: Spec, kind: str, n: int, w: int) -> str:
    decl = spec.sheets[kind]
    subtitle = f"{decl.subtitle}{P.SHEET_SEPARATOR}SHEET {n} / {len(P.SHEETS)}"
    _fits(spec, decl.line, "sheet heading", decl.heading, P.SIZE_HEAD, "t-h",
          w - 2 * P.SHEET_MARGIN)
    _fits(spec, decl.line, "sheet subtitle", subtitle, P.SIZE_SUBTITLE, "t-sub",
          w - P.SHEET_MARGIN - P.SUBTITLE_X)
    body = (_text("t-h", P.SHEET_MARGIN, P.HEAD_BASELINE, P.SIZE_HEAD, decl.heading)
            + _text("t-sub", P.SUBTITLE_X, P.SUBTITLE_BASELINE, P.SIZE_SUBTITLE, subtitle)
            + f'<line class="rule" x1="{P.SHEET_MARGIN}" y1="{P.RULE_Y}" '
            f'x2="{w - P.SHEET_MARGIN}" y2="{P.RULE_Y}"/>')
    return _group("header", decl.line, body)


def _title_block_origin(w: int, h: int) -> tuple[float, float]:
    return (w - P.TB_MARGIN_RIGHT - P.TB_W, h - P.TB_MARGIN_BOTTOM - P.TB_H)


def _title_block(spec: Spec, kind: str, w: int, h: int) -> str:
    decl = spec.sheets[kind]
    x, y = _title_block_origin(w, h)
    meta = f"SCALE {spec.scale} · {spec.units} · REV {spec.rev}"
    room = P.TB_W - 2 * P.TB_PAD_X
    _fits(spec, decl.line, "title-block title", spec.title, P.SIZE_TB_TITLE, "t-tb", room)
    _fits(spec, decl.line, "title-block caption", decl.caption, P.SIZE_TB, "t-tb", room)
    _fits(spec, decl.line, "title-block scale line", meta, P.SIZE_TB, "t-tb", room)
    tx = x + P.TB_PAD_X
    body = (f'<rect class="tb" x="{fmt(x)}" y="{fmt(y)}" width="{P.TB_W}" height="{P.TB_H}"/>'
            f'<line class="ln2" x1="{fmt(x)}" y1="{fmt(y + P.TB_DIVIDER_DY)}" '
            f'x2="{fmt(x + P.TB_W)}" y2="{fmt(y + P.TB_DIVIDER_DY)}"/>'
            + _text("t-tb", tx, y + 21, P.SIZE_TB_TITLE, spec.title)
            + _text("t-tb", tx, y + 48, P.SIZE_TB, decl.caption)
            + _text("t-tb", tx, y + 64, P.SIZE_TB, meta))
    return _group("titleblock", decl.line, body)


def _note(spec: Spec, kind: str, w: int, h: int) -> str:
    note = spec.notes.get(kind)
    if note is None:
        return ""
    tb_x, tb_y = _title_block_origin(w, h)
    width = tb_x - P.NOTE_GAP - P.NOTE_X
    if width < 120:
        raise SpecError(spec.path, note.line,
                        f"note: the {kind} sheet is too narrow for a note beside the title block")
    height = 22 + P.NOTE_LINE_DY * len(note.lines) + 14
    top = tb_y + P.TB_H - height
    room = width - 2 * P.TB_PAD_X
    _fits(spec, note.line, "note head", note.head, P.SIZE_NOTE, "t-amb", room)
    tx = P.NOTE_X + P.TB_PAD_X
    body = [f'<rect class="tb" x="{P.NOTE_X}" y="{fmt(top)}" width="{fmt(width)}" height="{fmt(height)}"/>',
            _text("t-amb", tx, top + 22, P.SIZE_NOTE, note.head)]
    for i, line in enumerate(note.lines, 1):
        _fits(spec, note.line, "note line", line, P.SIZE_NOTE, "t-lbl", room)
        body.append(_text("t-lbl", tx, top + 22 + P.NOTE_LINE_DY * i, P.SIZE_NOTE, line))
    return _group("note", note.line, "".join(body))


def _bom(spec: Spec, kind: str) -> str:
    decl = spec.sheets[kind]
    if decl.bom is None:
        return ""
    bx, by = decl.bom
    c = P.BOM_COLS
    rule = (lambda y, cls: f'<line class="{cls}" x1="{fmt(bx)}" y1="{fmt(y)}" '
            f'x2="{fmt(bx + P.BOM_W)}" y2="{fmt(y)}"/>')
    body = [_text("t-amb", bx, by, P.SIZE_BOM_HEAD, "BILL OF PARTS"), rule(by + 12, "rule-thin")]
    for col, head in (("no", "NO"), ("part", "PART"), ("qty", "QTY"), ("print", "PRINT")):
        body.append(_text("t-sub", bx + c[col], by + 34, P.SIZE_BOM, head))
    body.append(rule(by + 42, "ln2"))
    y = by + 64
    for part in spec.parts:
        _fits(spec, part.line, "part name", part.name, P.SIZE_BOM, "t-lbl", c["qty"] - c["part"] - 8)
        _fits(spec, part.line, "part qty", part.qty, P.SIZE_BOM, "t-lbl", c["print"] - c["qty"] - 6)
        _fits(spec, part.line, "part print note", part.print, P.SIZE_BOM, "t-sub", P.BOM_W - c["print"])
        body.append(_text("t-amb", bx + c["no"], y, P.SIZE_BOM, part.n))
        body.append(_text("t-lbl", bx + c["part"], y, P.SIZE_BOM, part.name))
        body.append(_text("t-lbl", bx + c["qty"], y, P.SIZE_BOM, part.qty))
        if part.print:
            body.append(_text("t-sub", bx + c["print"], y, P.SIZE_BOM, part.print))
        y += P.BOM_ROW_DY
    body.append(rule(y - P.BOM_ROW_DY + 14, "ln2"))
    return _group("bom", decl.line, "".join(body))


def render_sheet(spec: Spec, kind: str) -> str:
    n = P.SHEETS.index(kind) + 1
    w, h = spec.sheets[kind].size
    decl = spec.sheets[kind]
    name = spec.title if decl.heading == spec.title else f"{spec.title} — {decl.heading}"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'viewBox="0 0 {w} {h}" data-sheet="{kind}">',
           f"<title>{esc(name)} (sheet {n} of {len(P.SHEETS)})</title>",
           f"<style>\n{P.stylesheet()}\n</style>",
           f"<defs>\n{P.defs()}\n</defs>",
           _group("ground", decl.line,
                  f'<rect x="0" y="0" width="{w}" height="{h}" fill="{P.GROUND}"/>'
                  f'<rect x="0" y="0" width="{w}" height="{h}" fill="url(#grid)"/>'
                  f'<rect x="0" y="0" width="{w}" height="{h}" fill="url(#grid5)"/>'),
           _header(spec, kind, n, w)]
    for row in spec.rows_for(kind):
        out.append(_group(row.kind, row.line, _primitive(spec, row).svg))
    out += [_note(spec, kind, w, h), _bom(spec, kind), _title_block(spec, kind, w, h)]
    return "\n".join(part for part in out if part) + "\n</svg>\n"


def render_all(spec: Spec) -> dict[str, str]:
    """All four sheets, keyed by output filename, in sheet order."""
    return {FILENAMES[kind]: render_sheet(spec, kind) for kind in P.SHEETS}
