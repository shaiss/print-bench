"""The ``preview-spec.conf`` parser: the house ``key: value`` / pipe-row
format, fail-loud, every error naming its line.

A spec is what a model (or a person) composes; the emitter owns the look.
The spec therefore carries only *what* and *where* — never a colour, a line
weight or a font — and the parser refuses anything it does not recognise
rather than skip it: a silently dropped row is a part missing from the
sheet that every check would then pass.

Grammar (``#`` lines and blank lines are ignored)::

    title: PRE-ROLL ELEVATOR            # header keys: title (required),
    rev: A                              #   rev, scale, units
    sheet: <sheet> | k=v | ...          # one per canonical sheet, all four
    part: n=<no> | name=<text> | ...    # the bill of parts (exploded sheet)
    note: <sheet> | head=<text> | line=<text> | ...
    <primitive>: <sheet> | k=v | ...    # hatch shank hex dim balloon leader

``<sheet>`` is one of ``exterior cutaway section exploded``. Coordinates
are sheet pixels, origin top-left, ``x,y``; sizes are ``WxH``. Rows draw in
file order, so a later row paints over an earlier one.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import palette as P
from .primitives import HEX_ENDS, LEADER_ANCHORS, LEADER_TONES


class SpecError(Exception):
    """A spec the tool refuses. ``line`` is 1-based; 0 means the file as a
    whole (a required row that is absent has no line to point at)."""

    def __init__(self, path: str, line: int, message: str):
        self.path, self.line, self.message = path, line, message
        where = f"{path}:{line}" if line else path
        super().__init__(f"{where}: {message}")


@dataclass(frozen=True)
class F:
    """One field of a row: its value type, whether it is required, whether
    it may repeat, and a one-line meaning for the vocabulary listing."""
    type: str
    required: bool = False
    multi: bool = False
    help: str = ""


HEADER = {
    "title": F("text", True, help="the design's name — sheet headings and every title block"),
    "rev": F("text", help="revision letter in the title block (default A)"),
    "scale": F("text", help="scale note in the title block (default NTS)"),
    "units": F("text", help="units note in the title block (default mm)"),
}
HEADER_DEFAULTS = {"rev": "A", "scale": "NTS", "units": "mm"}

SHEET_FIELDS = {
    "size": F("size", help="artboard WxH px (default per sheet)"),
    "heading": F("text", help="the big heading (default per sheet; exterior uses the title)"),
    "subtitle": F("text", help="the line under the heading; ' · SHEET n / 4' is appended"),
    "caption": F("text", help="title-block second line"),
    "bom": F("point", help="exploded sheet only, required there: the bill-of-parts table's top-left"),
}
PART_FIELDS = {
    "n": F("token", True, help="part number (1-3 chars) — what a balloon names"),
    "name": F("text", True, help="part name in the bill of parts"),
    "qty": F("text", help="quantity (default 1)"),
    "print": F("text", help="print orientation note (optional)"),
}
NOTE_FIELDS = {
    "head": F("text", True, help="the note's amber heading"),
    "line": F("text", multi=True, help="a body line (repeatable, up to 4)"),
}

PRIMITIVES = {
    "hatch": {
        "at": F("point", help="rect form: top-left"),
        "size": F("size", help="rect form: WxH"),
        "center": F("point", help="ring form: centre"),
        "r": F("num", help="ring form: outer radius"),
        "ri": F("num", help="ring form: bore radius (0 or absent = solid disc)"),
    },
    "shank": {
        "at": F("point", True, help="top-left of the shank"),
        "size": F("size", True, help="WxH"),
        "pitch": F("num", help="thread pitch px, 6-30 (default 12)"),
    },
    "hex": {
        "at": F("point", True, help="top-left of the head/nut"),
        "size": F("size", True, help="WxH (across corners x height)"),
        "chamfer": F("num", help="45° chamfer px (default min(W/8, H/4, 12))"),
        "ends": F("enum:" + "|".join(HEX_ENDS), help="which ends are chamfered (default both)"),
        "grip": F("int", help="knurl ticks per side (default 0)"),
    },
    "dim": {
        "from": F("point", True, help="one end of the dimension line"),
        "to": F("point", True, help="the other end (axis-aligned with from)"),
        "text": F("text", True, help="the value, e.g. ≈ 130"),
        "ext": F("nums", help="feature coordinate(s) the extension lines start from"),
        "flip": F("bool", help="text on the other side of the line"),
    },
    "balloon": {
        "at": F("point", True, help="balloon centre"),
        "n": F("token", True, help="the part number — must be a declared part"),
        "to": F("point", help="leader target on the part (optional)"),
    },
    "leader": {
        "at": F("point", True, help="label baseline anchor point"),
        "to": F("point", True, help="the feature the dot lands on"),
        "text": F("text", True, help="the label"),
        "sub": F("text", help="a second, quieter line under the label"),
        "anchor": F("enum:" + "|".join(LEADER_ANCHORS),
                    help="text anchor (default: end if the target is right, else start)"),
        "tone": F("enum:" + "|".join(LEADER_TONES), help="label (default) or amber callout"),
    },
}

ROW_KINDS = ("sheet", "part", "note", *PRIMITIVES)


@dataclass
class Row:
    kind: str
    sheet: str
    fields: dict
    line: int


@dataclass
class SheetDecl:
    kind: str
    line: int
    size: tuple[int, int]
    heading: str
    subtitle: str
    caption: str
    bom: tuple[float, float] | None


@dataclass
class Part:
    n: str
    name: str
    qty: str
    print: str
    line: int


@dataclass
class Note:
    sheet: str
    head: str
    lines: list[str]
    line: int


@dataclass
class Spec:
    path: str
    title: str
    rev: str
    scale: str
    units: str
    sheets: dict = field(default_factory=dict)   # kind -> SheetDecl
    parts: list = field(default_factory=list)    # [Part]
    notes: dict = field(default_factory=dict)    # sheet -> Note
    rows: list = field(default_factory=list)     # [Row] primitives, file order

    def rows_for(self, sheet: str) -> list:
        return [r for r in self.rows if r.sheet == sheet]


_TOKEN = re.compile(r"^[0-9A-Za-z*]{1,3}$")
_NUM = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
_POINT = re.compile(rf"^\s*({_NUM})\s*,\s*({_NUM})\s*$")
_SIZE = re.compile(rf"^\s*({_NUM})\s*[xX]\s*({_NUM})\s*$")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def _value(path: str, ln: int, kind: str, key: str, ftype: str, raw: str):
    where = f"{kind} {key}="
    raw = raw.strip()
    if ftype == "text":
        if not raw:
            raise SpecError(path, ln, f"{where} is empty")
        if _CTRL.search(raw):
            raise SpecError(path, ln, f"{where} carries a control character")
        return raw
    if ftype == "token":
        if not _TOKEN.match(raw):
            raise SpecError(path, ln, f"{where}{raw!r} must be 1-3 of [0-9A-Za-z*]")
        return raw
    if ftype == "point":
        m = _POINT.match(raw)
        if not m:
            raise SpecError(path, ln, f"{where}{raw!r} is not an x,y point")
        return (float(m.group(1)), float(m.group(2)))
    if ftype == "size":
        m = _SIZE.match(raw)
        if not m:
            raise SpecError(path, ln, f"{where}{raw!r} is not a WxH size")
        w, h = float(m.group(1)), float(m.group(2))
        if w <= 0 or h <= 0:
            raise SpecError(path, ln, f"{where}{raw!r} must be positive")
        return (w, h)
    if ftype == "num":
        if not re.fullmatch(_NUM, raw):
            raise SpecError(path, ln, f"{where}{raw!r} is not a number")
        return float(raw)
    if ftype == "nums":
        parts = [p.strip() for p in raw.split(",")]
        if not 1 <= len(parts) <= 2 or not all(re.fullmatch(_NUM, p) for p in parts):
            raise SpecError(path, ln, f"{where}{raw!r} must be one number or two, comma-separated")
        return tuple(float(p) for p in parts)
    if ftype == "int":
        if not re.fullmatch(r"\d+", raw):
            raise SpecError(path, ln, f"{where}{raw!r} is not a whole number")
        return int(raw)
    if ftype == "bool":
        if raw.lower() in ("yes", "true"):
            return True
        if raw.lower() in ("no", "false"):
            return False
        raise SpecError(path, ln, f"{where}{raw!r} must be yes or no")
    if ftype.startswith("enum:"):
        choices = ftype[5:].split("|")
        if raw not in choices:
            raise SpecError(path, ln, f"{where}{raw!r} must be one of {', '.join(choices)}")
        return raw
    raise AssertionError(f"unknown field type {ftype}")  # pragma: no cover — schema bug


def _fields(path: str, ln: int, kind: str, schema: dict, raw_fields: list[str]) -> dict:
    out: dict = {}
    for raw in raw_fields:
        if not raw:
            raise SpecError(path, ln, f"{kind}: empty field (two '|' in a row, or a trailing '|')")
        if "=" not in raw:
            raise SpecError(path, ln, f"{kind}: field {raw!r} is not key=value")
        key, val = raw.split("=", 1)
        key = key.strip()
        if key not in schema:
            known = " ".join(schema)
            raise SpecError(path, ln, f"{kind}: unknown field {key!r} (known: {known})")
        f = schema[key]
        value = _value(path, ln, kind, key, f.type, val)
        if f.multi:
            out.setdefault(key, []).append(value)
        elif key in out:
            raise SpecError(path, ln, f"{kind}: field {key!r} given twice")
        else:
            out[key] = value
    for key, f in schema.items():
        if f.required and key not in out:
            raise SpecError(path, ln, f"{kind}: missing required field {key}=")
    for key, value in out.items():
        if isinstance(value, float) and not math.isfinite(value):
            raise SpecError(path, ln, f"{kind}: {key}= is not finite")
    return out


def _sheet_name(path: str, ln: int, kind: str, raw: str) -> str:
    if "=" in raw:
        raise SpecError(path, ln, f"{kind}: first field must be the sheet name "
                        f"({' '.join(P.SHEETS)}), got {raw!r}")
    if raw not in P.SHEETS:
        raise SpecError(path, ln, f"{kind}: unknown sheet {raw!r} (sheets: {' '.join(P.SHEETS)})")
    return raw


def parse(text: str, path: str = "<spec>") -> Spec:
    header: dict = {}
    sheets: dict = {}
    parts: list = []
    notes: dict = {}
    rows: list = []
    for ln, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in s:
            raise SpecError(path, ln, f"expected 'key: value', got {s!r}")
        key, rest = s.split(":", 1)
        key, rest = key.strip(), rest.strip()
        if not rest:
            raise SpecError(path, ln, f"{key}: has no value")
        if key in HEADER:
            if key in header:
                raise SpecError(path, ln, f"{key}: given twice")
            header[key] = (_value(path, ln, key, "", HEADER[key].type, rest), ln)
            continue
        if key not in ROW_KINDS:
            known = " ".join(list(HEADER) + list(ROW_KINDS))
            if re.fullmatch(r"[a-z][a-z0-9_-]*", key):
                raise SpecError(path, ln, f"unknown key or primitive {key!r} (known: {known})")
            raise SpecError(path, ln, f"expected 'key: value', got {s!r}")
        fields = [f.strip() for f in rest.split("|")]
        if key == "part":
            f = _fields(path, ln, key, PART_FIELDS, fields)
            parts.append(Part(f["n"], f["name"], f.get("qty", "1"), f.get("print", ""), ln))
            continue
        sheet = _sheet_name(path, ln, key, fields[0])
        if key == "sheet":
            if sheet in sheets:
                raise SpecError(path, ln, f"sheet: {sheet!r} declared twice (first at line {sheets[sheet].line})")
            f = _fields(path, ln, key, SHEET_FIELDS, fields[1:])
            sheets[sheet] = _sheet_decl(path, ln, sheet, f)
        elif key == "note":
            if sheet in notes:
                raise SpecError(path, ln, f"note: sheet {sheet!r} already has a note (line {notes[sheet].line})")
            f = _fields(path, ln, key, NOTE_FIELDS, fields[1:])
            lines = f.get("line", [])
            if len(lines) > P.NOTE_MAX_LINES:
                raise SpecError(path, ln, f"note: {len(lines)} lines (at most {P.NOTE_MAX_LINES})")
            notes[sheet] = Note(sheet, f["head"], lines, ln)
        else:
            f = _fields(path, ln, key, PRIMITIVES[key], fields[1:])
            if key == "hatch":
                _hatch_form(path, ln, f)
            rows.append(Row(key, sheet, f, ln))

    if "title" not in header:
        raise SpecError(path, 0, "no 'title:' line (the design's name is required)")
    for kind in P.SHEETS:
        if kind not in sheets:
            raise SpecError(path, 0, f"no 'sheet: {kind}' row — every spec declares all four "
                            f"canonical sheets ({' '.join(P.SHEETS)})")
    # Defaults that read the title resolve once the whole header is known.
    title = header["title"][0]
    for decl in sheets.values():
        if decl.heading == "":
            decl.heading = title
    _cross_checks(path, sheets, parts, rows)
    get = lambda k: header[k][0] if k in header else HEADER_DEFAULTS[k]  # noqa: E731
    return Spec(path, title, get("rev"), get("scale"), get("units"),
                sheets, parts, notes, rows)


def _sheet_decl(path: str, ln: int, kind: str, f: dict) -> SheetDecl:
    (dw, dh), heading, subtitle, caption = P.SHEET_DEFAULTS[kind]
    w, h = f.get("size", (dw, dh))
    if w != int(w) or h != int(h):
        raise SpecError(path, ln, "sheet: size= must be whole pixels")
    if not (P.SHEET_MIN <= w <= P.SHEET_MAX and P.SHEET_MIN <= h <= P.SHEET_MAX):
        raise SpecError(path, ln, f"sheet: size= must be {P.SHEET_MIN}..{P.SHEET_MAX} px each way")
    if "bom" in f and kind != "exploded":
        raise SpecError(path, ln, "sheet: bom= belongs on the exploded sheet only")
    if kind == "exploded" and "bom" not in f:
        raise SpecError(path, ln, "sheet: the exploded sheet needs bom=x,y (where the bill of parts sits)")
    return SheetDecl(kind, ln, (int(w), int(h)),
                     f.get("heading", heading or ""),  # "" → the title, resolved in parse()
                     f.get("subtitle", subtitle), f.get("caption", caption), f.get("bom"))


def _hatch_form(path: str, ln: int, f: dict) -> None:
    rect = {"at", "size"} & f.keys()
    ring = {"center", "r", "ri"} & f.keys()
    if rect and ring:
        raise SpecError(path, ln, "hatch: give either at=+size= (rect) or center=+r= (ring), not both")
    if rect and rect != {"at", "size"}:
        raise SpecError(path, ln, "hatch: the rect form needs both at= and size=")
    if ring and not {"center", "r"} <= ring:
        raise SpecError(path, ln, "hatch: the ring form needs center= and r=")
    if not rect and not ring:
        raise SpecError(path, ln, "hatch: needs at=+size= (rect) or center=+r= (ring)")


def _cross_checks(path: str, sheets: dict, parts: list, rows: list) -> None:
    seen: dict = {}
    for p in parts:
        if p.n in seen:
            raise SpecError(path, p.line, f"part: n={p.n} declared twice (first at line {seen[p.n]})")
        seen[p.n] = p.line
    if not parts:
        raise SpecError(path, sheets["exploded"].line,
                        "no 'part:' rows — the exploded sheet's bill of parts needs at least one")
    for r in rows:
        if r.kind == "balloon" and r.fields["n"] not in seen:
            raise SpecError(path, r.line, f"balloon: n={r.fields['n']} names no declared part "
                            f"(parts: {' '.join(seen)})")


def load(path: Path) -> Spec:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise SpecError(str(path), 0, f"not UTF-8 text ({e.reason})") from None
    return parse(text, str(path))


def vocabulary() -> str:
    """The spec vocabulary, rendered from the schema tables above — the
    listing cannot drift from what the parser accepts."""
    out = ["# preview-spec.conf vocabulary (generated from concept_preview.spec)", "",
           "Header keys (key: value):"]
    for k, f in HEADER.items():
        out.append(f"  {k:<8} {'required' if f.required else 'optional'}  {f.help}")
    out += ["", f"Sheets (all four required, one row each): {' '.join(P.SHEETS)}"]
    blocks = [("sheet: <sheet> | k=v | ...", SHEET_FIELDS), ("part: k=v | ...", PART_FIELDS),
              ("note: <sheet> | k=v | ...", NOTE_FIELDS)]
    blocks += [(f"{k}: <sheet> | k=v | ...", v) for k, v in PRIMITIVES.items()]
    for head, schema in blocks:
        out += ["", head]
        for k, f in schema.items():
            req = "required" if f.required else ("repeatable" if f.multi else "optional")
            out.append(f"  {k + '=':<9} {f.type:<26} {req:<10} {f.help}")
    out += ["", "Points are x,y and sizes WxH in sheet pixels (origin top-left);",
            "rows draw in file order. hatch takes at=+size= (rect) or center=+r=[+ri=] (ring)."]
    return "\n".join(out) + "\n"
