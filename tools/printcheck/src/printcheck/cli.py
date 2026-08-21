"""Command-line interface: printcheck MODEL.stl [options]."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from .analyzer import analyze, load_mesh
from .checks import Config
from .report import Report, Severity

# Single source of truth for user-tunable defaults: the Config dataclass.
_D = Config()
_D_BUILD_VOLUME = "x".join(f"{v:g}" for v in _D.build_volume_mm)


def _positive_mm(value: str) -> float:
    """argparse type: a finite, strictly positive number."""
    f = float(value)
    if not math.isfinite(f) or f <= 0:
        raise argparse.ArgumentTypeError(
            f"{value!r} must be a positive number")
    return f


def _angle_deg(value: str) -> float:
    """argparse type: an angle strictly between 0 and 90 degrees."""
    f = float(value)
    if not math.isfinite(f) or not 0 < f < 90:
        raise argparse.ArgumentTypeError(
            f"{value!r} must be an angle between 0 and 90 degrees")
    return f


def build_parser() -> argparse.ArgumentParser:
    """Build the printcheck argument parser."""
    p = argparse.ArgumentParser(
        prog="printcheck",
        description="Analyze an STL (or OBJ/3MF/PLY) for FDM printability.",
    )
    p.add_argument("model", nargs="+", help="mesh file(s) to analyze")
    p.add_argument("--json", action="store_true",
                   help="emit the report as JSON instead of text")
    p.add_argument("--nozzle", type=_positive_mm, default=_D.nozzle_mm,
                   help=f"nozzle diameter in mm (default {_D.nozzle_mm})")
    p.add_argument("--layer-height", type=_positive_mm,
                   default=_D.layer_height_mm,
                   help=f"layer height in mm (default {_D.layer_height_mm})")
    p.add_argument("--min-wall", type=_positive_mm, default=None,
                   help="minimum wall thickness in mm (default 2x nozzle)")
    p.add_argument("--overhang-angle", type=_angle_deg,
                   default=_D.overhang_deg,
                   help="support threshold in degrees from vertical "
                        f"(default {_D.overhang_deg:g})")
    p.add_argument("--bridge-max", type=_positive_mm, default=_D.bridge_max_mm,
                   help="widest unsupported span treated as a self-supporting "
                        f"bridge, in mm (default {_D.bridge_max_mm:g}); "
                        "narrower downward regions are not counted as overhang")
    p.add_argument("--build-volume", type=str, default=_D_BUILD_VOLUME,
                   help=f"printer build volume as XxYxZ in mm "
                        f"(default {_D_BUILD_VOLUME})")
    p.add_argument("--no-orientation", action="store_true",
                   help="skip the orientation suggestion pass")
    p.add_argument("--ai", action="store_true",
                   help="append an AI-written summary of the heuristic "
                        "findings (needs ANTHROPIC_API_KEY)")
    p.add_argument("--fail-under", type=int, default=None, metavar="SCORE",
                   help="exit non-zero if the score is below SCORE "
                        "(for CI pipelines)")
    p.add_argument("--repair", action="store_true",
                   help="on integrity failures, boolean-union the shells "
                        "with manifold3d and write <model>.repaired.stl; "
                        "the exit code still reflects the original mesh")
    return p


def _bodies_overlap(mesh) -> bool:
    """True when any two connected components have intersecting AABBs.

    Cheap proxy separating "shells concatenated instead of unioned"
    (overlapping boxes) from an intentional plate of parts (disjoint).
    """
    import numpy as np
    bodies = mesh.split(only_watertight=False)
    boxes = [b.bounds for b in bodies]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            lo = np.maximum(boxes[i][0], boxes[j][0])
            hi = np.minimum(boxes[i][1], boxes[j][1])
            if bool(np.all(lo < hi)):
                return True
    return False


def _try_repair(path: str, report: Report) -> None:
    """Attempt a manifold3d union repair of `path`, write .repaired.stl.

    Triggers on non-INFO integrity findings, or on a multi-body mesh
    whose bodies overlap (closed shells exported without a union pass
    are watertight, so they only ever raise INFO). A disjoint plate of
    parts is left alone: unioning it would weld the plate.
    """
    from .repair import repair
    broken = any(f.check == "integrity" and f.severity is not Severity.INFO
                 for f in report.findings)
    try:
        mesh = load_mesh(path)
        if not broken:
            if report.mesh_summary["bodies"] < 2 or not _bodies_overlap(mesh):
                return
        result = repair(mesh)
    except Exception as e:
        print(f"  repair: failed to process {path}: {e}", file=sys.stderr)
        return
    if result.mesh is None:
        print(f"  repair: {result.note}")
        return
    out = str(Path(path).with_suffix(".repaired.stl"))
    result.mesh.export(out)
    print(f"  repair: {result.note}")
    print(f"  repair: wrote {out} (verify with printcheck before trusting; "
          "the gate still judges the original)")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the process exit code (0 ok, 1 gate
    failure, 2 usage/load error)."""
    args = build_parser().parse_args(argv)
    try:
        bv = tuple(float(x) for x in args.build_volume.lower().split("x"))
        assert len(bv) == 3
    except (ValueError, AssertionError):
        print(f"error: bad --build-volume {args.build_volume!r}, "
              "expected e.g. 250x210x220", file=sys.stderr)
        return 2

    cfg = Config(
        nozzle_mm=args.nozzle,
        layer_height_mm=args.layer_height,
        min_wall_mm=args.min_wall if args.min_wall else args.nozzle * 2,
        overhang_deg=args.overhang_angle,
        bridge_max_mm=args.bridge_max,
        build_volume_mm=bv,
    )

    worst_exit = 0
    for path in args.model:
        try:
            report = analyze(path, cfg, orientation=not args.no_orientation)
        except Exception as e:
            print(f"error: {path}: {e}", file=sys.stderr)
            worst_exit = max(worst_exit, 2)
            continue

        if args.ai:
            from .ai import summarize
            try:
                report.ai_summary = summarize(report)
            except RuntimeError as e:
                print(f"warning: AI summary skipped: {e}", file=sys.stderr)

        print(report.to_json() if args.json else report.to_text())

        if args.repair:
            _try_repair(path, report)

        if len(args.model) > 1 and not args.json:
            print()

        if args.fail_under is not None and report.score < args.fail_under:
            worst_exit = max(worst_exit, 1)
        elif report.verdict == "NOT PRINTABLE AS-IS":
            worst_exit = max(worst_exit, 1)
    return worst_exit


if __name__ == "__main__":
    raise SystemExit(main())
