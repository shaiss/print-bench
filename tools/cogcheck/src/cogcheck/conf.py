"""Parse ``designs/<name>/ci.cog`` — the manifest the check is keyed on.

House ``key: value`` conf, one declaration per line, ``#`` starts a comment.
The manifest carries exactly what an exported STL cannot infer about the
assembled object:

- per-part material density (g/cm³) — PLA, resin, steel-stalk-filled …
  differ by an order of magnitude, and a wrong density is a silently wrong
  verdict, so it is REQUIRED per part with no default;
- the non-printed masses (a brass stalk, ballast fill, a PCB) as labelled
  point masses with their positions;
- the transforms placing each printed part into the ASSEMBLED STANDING frame
  — the orientation the finished object stands in, which for anything but a
  one-part design is not the orientation any single STL prints in;
- the tunable stability margin (mm) the CoG's ground projection must clear
  the support footprint's boundary by (default 0: inside is enough).

Everything fails loudly with the file and line: a manifest that half-parses
is a stability verdict built on numbers nobody can audit, and half the lines
in a stability manifest exist precisely because nobody can eyeball them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

Vec3 = tuple[float, float, float]


class ManifestError(Exception):
    """The manifest is malformed; str(e) carries file, line and reason."""

    def __init__(self, message: str, path: str = "<manifest>", lineno: int = 0):
        where = f"{path}:{lineno}: " if lineno else f"{path}: "
        super().__init__(f"{where}{message}")
        self.path = path
        self.lineno = lineno


@dataclass(frozen=True)
class PartSpec:
    """One printed part: the STL's basename under the stl dir, its material
    density, and its placement in the assembled standing frame."""

    stl: str
    density: float  # g/cm³
    translate: Vec3 = (0.0, 0.0, 0.0)
    rotate: Vec3 = (0.0, 0.0, 0.0)  # degrees, OpenSCAD rotate([x, y, z])


@dataclass(frozen=True)
class MassSpec:
    """One non-printed point mass at a known position — the brass stalk,
    ballast fill or PCB an STL cannot see."""

    label: str
    grams: float
    at: Vec3


@dataclass(frozen=True)
class Manifest:
    margin: float = 0.0
    parts: tuple[PartSpec, ...] = ()
    masses: tuple[MassSpec, ...] = ()


def parse(text: str, path: str = "<manifest>") -> Manifest:
    """Parse manifest text. Raises ManifestError on any malformed line,
    duplicate declaration, unknown key, or a manifest with no printed parts
    (nothing would contribute contact geometry, so there is nothing to
    judge)."""
    margin: float | None = None
    parts: list[PartSpec] = []
    masses: list[MassSpec] = []
    seen_stls: set[str] = set()
    seen_labels: set[str] = set()

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise ManifestError(
                f"not a 'key: value' line — expected margin | part | mass", path, lineno
            )
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "margin":
            if margin is not None:
                raise ManifestError("margin declared twice", path, lineno)
            margin = _number(value, "margin", path, lineno)
            if margin < 0:
                raise ManifestError(
                    f"margin must be >= 0 mm, got {value}", path, lineno
                )
        elif key == "part":
            parts.append(_parse_part(value, path, lineno, seen_stls))
        elif key == "mass":
            masses.append(_parse_mass(value, path, lineno, seen_labels))
        else:
            raise ManifestError(
                f"unknown key '{key}' — use margin | part | mass", path, lineno
            )

    if not parts:
        raise ManifestError(
            "manifest declares no 'part:' — without a printed part there is "
            "no contact geometry and no mass to place; nothing to judge",
            path,
        )
    return Manifest(
        margin=margin if margin is not None else 0.0,
        parts=tuple(parts),
        masses=tuple(masses),
    )


def parse_file(path: str | Path) -> Manifest:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        raise ManifestError(f"cannot read manifest: {e}") from e
    return parse(text, str(p))


def _parse_part(value: str, path: str, lineno: int, seen: set[str]) -> PartSpec:
    """`part: <stl-basename> | density: <g/cm3> | translate: x,y,z | rotate: rx,ry,z`"""
    fields = _split_fields(value, path, lineno)
    if not fields or not fields[0][1]:
        raise ManifestError(
            "part line needs the STL basename before the '|' fields "
            "(e.g. 'part: mydesign-base.stl | density: 1.24')",
            path,
            lineno,
        )
    stl = _require_stl_basename(fields[0][1], path, lineno)
    density: float | None = None
    translate: Vec3 = (0.0, 0.0, 0.0)
    rotate: Vec3 = (0.0, 0.0, 0.0)
    seen_fields: set[str] = set()
    for name, val, has_colon in fields[1:]:
        if not has_colon:
            raise ManifestError(
                f"field '{name}' needs a value — 'name: value'", path, lineno
            )
        if name in seen_fields:
            raise ManifestError(
                f"part field '{name}' declared twice", path, lineno
            )
        seen_fields.add(name)
        if name == "density":
            density = _number(val, "density", path, lineno)
            if density <= 0:
                raise ManifestError(
                    f"density must be > 0 g/cm³, got {val}", path, lineno
                )
        elif name == "translate":
            translate = _vec3(val, "translate", path, lineno)
        elif name == "rotate":
            rotate = _vec3(val, "rotate", path, lineno)
        else:
            raise ManifestError(
                f"unknown part field '{name}' — use density | translate | rotate",
                path,
                lineno,
            )
    if density is None:
        raise ManifestError(
            "part declares no density — material density is required per part "
            "(no default: a wrong density is a silently wrong verdict)",
            path,
            lineno,
        )
    if stl in seen:
        raise ManifestError(f"part '{stl}' declared twice", path, lineno)
    seen.add(stl)
    return PartSpec(stl=stl, density=density, translate=translate, rotate=rotate)


def _parse_mass(value: str, path: str, lineno: int, seen: set[str]) -> MassSpec:
    """`mass: <label> | grams: <g> | at: x,y,z`"""
    fields = _split_fields(value, path, lineno)
    if not fields or not fields[0][1]:
        raise ManifestError(
            "mass line needs a label before the '|' fields "
            "(e.g. 'mass: stalk | grams: 42 | at: 0,0,43')",
            path,
            lineno,
        )
    label = fields[0][1]
    grams: float | None = None
    at: Vec3 | None = None
    seen_fields: set[str] = set()
    for name, val, has_colon in fields[1:]:
        if not has_colon:
            raise ManifestError(
                f"field '{name}' needs a value — 'name: value'", path, lineno
            )
        if name in seen_fields:
            raise ManifestError(
                f"mass field '{name}' declared twice", path, lineno
            )
        seen_fields.add(name)
        if name == "grams":
            grams = _number(val, "grams", path, lineno)
            if grams <= 0:
                raise ManifestError(f"grams must be > 0, got {val}", path, lineno)
        elif name == "at":
            at = _vec3(val, "at", path, lineno)
        else:
            raise ManifestError(
                f"unknown mass field '{name}' — use grams | at", path, lineno
            )
    if grams is None or at is None:
        missing = "grams" if grams is None else "at"
        raise ManifestError(
            f"mass '{label}' declares no {missing} — a point mass needs both "
            "its weight and its position",
            path,
            lineno,
        )
    if label in seen:
        raise ManifestError(f"mass '{label}' declared twice", path, lineno)
    seen.add(label)
    return MassSpec(label=label, grams=grams, at=at)


def _require_stl_basename(stl: str, path: str, lineno: int) -> str:
    """A part STL must be a single basename resolved under --stl-dir.

    Reject path separators and ``.`` / ``..`` so a manifest cannot escape the
    stl directory (``part: ../../etc/passwd`` would otherwise join onto
    ``stl_dir`` and open arbitrary files the process can read).
    """
    if (
        not stl
        or stl in {".", ".."}
        or "/" in stl
        or "\\" in stl
        or stl != Path(stl).name
    ):
        raise ManifestError(
            f"part STL must be a single basename (no '/', '\\\\', or '..'), "
            f"got {stl!r}",
            path,
            lineno,
        )
    return stl


def _split_fields(value: str, path: str, lineno: int) -> list[tuple[str, str, bool]]:
    """Split 'a.stl | density: 1.24 | …' into (name, value, had-colon)
    triples. The head field (before the first '|') carries no colon."""
    out: list[tuple[str, str, bool]] = []
    for chunk in value.split("|"):
        chunk = chunk.strip()
        if not chunk:
            raise ManifestError("empty '|' field", path, lineno)
        if ":" in chunk:
            name, val = chunk.split(":", 1)
            out.append((name.strip(), val.strip(), True))
        else:
            out.append((chunk, chunk, False))
    return out


def _number(text: str, what: str, path: str, lineno: int) -> float:
    try:
        value = float(text)
    except ValueError as e:
        raise ManifestError(f"{what} must be a number, got {text!r}", path, lineno) from e
    if not math.isfinite(value):
        raise ManifestError(
            f"{what} must be finite, got {text!r}", path, lineno
        )
    return value


def _vec3(text: str, what: str, path: str, lineno: int) -> Vec3:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 3:
        raise ManifestError(
            f"{what} must be 'x,y,z' (three numbers), got {text!r}", path, lineno
        )
    try:
        values = tuple(float(p) for p in parts)
    except ValueError as e:
        raise ManifestError(
            f"{what} must be 'x,y,z' (three numbers), got {text!r}", path, lineno
        ) from e
    if not all(math.isfinite(v) for v in values):
        raise ManifestError(
            f"{what} must be finite 'x,y,z', got {text!r}", path, lineno
        )
    x, y, z = values
    return (x, y, z)
