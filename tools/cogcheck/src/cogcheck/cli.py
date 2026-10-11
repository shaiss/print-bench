"""Command line: measure one manifest, report, and exit by verdict.

Exit codes carry the verdict so gate wiring never parses prose:

- 0 — STABLE (verdict produced, object stands)
- 3 — TIP-RISK (verdict produced, advisory in the gate)
- 1 — broken input (unreadable STL, malformed manifest, unmeasurable mesh)
- 2 — usage

In human mode the report's final stdout line is always
``VERDICT: <STABLE|TIP-RISK> — …``, the one machine-greppable line
scripts/cog-check.sh re-emits as the gate's ``ok``/``warn`` row. ``--json``
emits only the CheckResult JSON document (no trailing VERDICT line) so
consumers can ``json.loads`` stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cogcheck.conf import ManifestError, parse_file
from cogcheck.verdict import STABLE, AssemblyError, assemble

EXIT_BROKEN = 1
EXIT_TIP_RISK = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cogcheck",
        description="CoG / tip-over stability check: mesh-derived centre of "
        "gravity against a manifest's densities, point masses, transforms "
        "and margin.",
    )
    parser.add_argument("manifest", help="path to a designs/<name>/ci.cog manifest")
    parser.add_argument(
        "--stl-dir",
        default="build",
        help="directory the manifest's part STL basenames resolve against "
        "(default: build — where gate.sh exports them)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the full result as JSON instead of the human report",
    )
    args = parser.parse_args(argv)

    try:
        manifest = parse_file(args.manifest)
    except ManifestError as e:
        print(f"cogcheck: error: {e}", file=sys.stderr)
        return EXIT_BROKEN
    try:
        result = assemble(manifest, stl_dir=args.stl_dir)
    except AssemblyError as e:
        print(f"cogcheck: error: {e}", file=sys.stderr)
        return EXIT_BROKEN

    if args.json:
        print(
            json.dumps(
                {
                    "manifest": args.manifest,
                    "verdict": result.verdict,
                    "detail": result.detail,
                    "cog": list(result.cog),
                    "total_mass_g": result.total_mass_g,
                    "ground_z": result.ground_z,
                    "footprint": [list(p) for p in result.footprint],
                    "footprint_area_mm2": result.footprint_area_mm2,
                    "footprint_degenerate": result.footprint_degenerate,
                    "margin": result.margin,
                    "margin_left": result.margin_left,
                    "parts": [
                        {
                            "stl": p.stl,
                            "volume_mm3": p.volume_mm3,
                            "mass_g": p.mass_g,
                            "cog": list(p.cog),
                            "contact_points": p.contact_points,
                        }
                        for p in result.parts
                    ],
                    "point_masses": [
                        {"label": label, "grams": grams, "at": list(at)}
                        for label, grams, at in result.point_masses
                    ],
                },
                indent=2,
            )
        )
        return 0 if result.verdict == STABLE else EXIT_TIP_RISK

    print(f"cogcheck — {args.manifest}")
    print(
        f"  parts: {len(result.parts)} printed, "
        f"{len(result.point_masses)} non-printed mass(es)"
    )
    for p in result.parts:
        print(
            f"  {p.stl}: {p.mass_g:.1f} g  V={p.volume_mm3:.0f} mm³  "
            f"cog=({p.cog[0]:.2f}, {p.cog[1]:.2f}, {p.cog[2]:.2f})"
        )
    for label, grams, at in result.point_masses:
        print(
            f"  {label}: {grams:.1f} g at "
            f"({at[0]:.2f}, {at[1]:.2f}, {at[2]:.2f})"
        )
    print(
        f"  assembled: {result.total_mass_g:.1f} g  "
        f"CoG=({result.cog[0]:.2f}, {result.cog[1]:.2f}, {result.cog[2]:.2f}) mm"
    )
    print(
        f"  ground z={result.ground_z:.2f}  footprint: "
        f"{len(result.footprint)}-vertex hull, {result.footprint_area_mm2:.1f} mm²"
    )
    if result.footprint_degenerate:
        print("  footprint: DEGENERATE (line/point contact)")
    print(
        f"  CoG projection ({result.cog[0]:.2f}, {result.cog[1]:.2f}): "
        f"signed margin {result.margin_left:.2f} mm "
        f"(required {result.margin:.2f} mm)"
    )
    print(f"VERDICT: {result.verdict} — {result.detail}")
    return 0 if result.verdict == STABLE else EXIT_TIP_RISK


if __name__ == "__main__":
    sys.exit(main())
