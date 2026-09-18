"""Field of view and clearance analysis.

The rotating head of the payload sweeps a sector around its gimbal axis. This tool
builds that sector from the declared geometry (``model/layout.yaml``) and the
declared elevation range (``model/interfaces/icd_payload.yaml``), samples it with
one ray per ``ray_step_deg``, and checks every ray against the declared platform
geometry in the side view:

* ``FOV-OBSTRUCTION`` — no ray hits a structural member (SYS008);
* ``FOV-SKIN`` — no ray reaches the platform skin;
* ``FOV-CLEARANCE`` — the minimum distance from the swept sector to the structure
  is at least the declared clearance (SYS009).

The sector exists only with the payload installed: with the payload removed there
is nothing to sweep, and that configuration is covered by the removal-corridor
check in ``tools/layout.py``. The report lists the clearance direction by
direction and flags the directions whose margin is inside twice the limit, so a
tight direction is reported instead of averaged away.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from math import cos, hypot, radians, sin
from pathlib import Path

import yaml

from .analysis import Finding, findings_table, make_finding, summarise
from .layout import LAYOUT_PATH, NamedRect, load_layout
from .model import REPO_ROOT

PAYLOAD_ICD = Path("model/interfaces/icd_payload.yaml")
EVIDENCE_DIR = Path("evidence/clearance")
GENERATED_FILES = ("checks.json", "report.md", "sweep.svg")

#: Step of the direction table in the report.
REPORT_STEP_DEG = 10.0


@dataclass(frozen=True)
class Ray:
    """One sampled direction of the swept sector."""

    elevation_deg: float
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass(frozen=True)
class RayResult:
    """What one ray found."""

    ray: Ray
    blocked_by: str | None
    clearance: float
    nearest: str
    below_skin: float


def load_elevation_range(root: Path | None = None) -> tuple[float, float]:
    """Read the declared elevation range from the payload interface data."""
    base = Path(root) if root else REPO_ROOT
    payload = yaml.safe_load((base / PAYLOAD_ICD).read_text(encoding="utf-8"))
    elevation = payload["field_of_view_deg"]["elevation"]
    return float(elevation["lower"]), float(elevation["upper"])


def build_sector(
    gimbal: tuple[float, float],
    radius: float,
    lower_deg: float,
    upper_deg: float,
    step_deg: float,
) -> tuple[Ray, ...]:
    """Sample the swept sector with one ray per step."""
    if step_deg <= 0:
        raise ValueError("ray_step_deg must be positive")
    rays = []
    steps = int(round((upper_deg - lower_deg) / step_deg))
    for index in range(steps + 1):
        elevation = lower_deg + index * step_deg
        angle = radians(elevation)
        end = (gimbal[0] + radius * cos(angle), gimbal[1] + radius * sin(angle))
        rays.append(Ray(elevation_deg=elevation, start=gimbal, end=end))
    return tuple(rays)


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #


def _orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> bool:
    d1 = _orientation(p3, p4, p1)
    d2 = _orientation(p3, p4, p2)
    d3 = _orientation(p1, p2, p3)
    d4 = _orientation(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _distance_point_to_segment(
    point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    px, py = point
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_squared))
    return hypot(px - (ax + t * dx), py - (ay + t * dy))


def _segment_segment_distance(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> float:
    return min(
        _distance_point_to_segment(c, a, b),
        _distance_point_to_segment(d, a, b),
        _distance_point_to_segment(a, c, d),
        _distance_point_to_segment(b, c, d),
    )


def segment_intersects_rect(
    a: tuple[float, float], b: tuple[float, float], rect: NamedRect
) -> bool:
    """True when the segment touches the rectangle."""
    if rect.rect.contains(*a) or rect.rect.contains(*b):
        return True
    corners = rect.rect.corners
    for index in range(4):
        if _segments_intersect(a, b, corners[index], corners[(index + 1) % 4]):
            return True
    return False


def segment_rect_distance(
    a: tuple[float, float], b: tuple[float, float], rect: NamedRect
) -> float:
    """Distance between the segment and the rectangle, zero when they touch."""
    if segment_intersects_rect(a, b, rect):
        return 0.0
    corners = rect.rect.corners
    best = min(_distance_point_to_segment(corner, a, b) for corner in corners)
    for index in range(4):
        best = min(
            best,
            _segment_segment_distance(a, b, corners[index], corners[(index + 1) % 4]),
        )
    return best


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #


def evaluate_rays(
    rays: tuple[Ray, ...], obstacles: tuple[NamedRect, ...], skin_y: float
) -> list[RayResult]:
    """Evaluate every ray against the structure and the platform skin."""
    results = []
    for ray in rays:
        blocked_by = None
        nearest = "—"
        clearance = float("inf")
        for obstacle in obstacles:
            if blocked_by is None and segment_intersects_rect(ray.start, ray.end, obstacle):
                blocked_by = obstacle.id
            distance = segment_rect_distance(ray.start, ray.end, obstacle)
            if distance < clearance:
                clearance = distance
                nearest = obstacle.id
        below_skin = skin_y - max(ray.start[1], ray.end[1])
        if below_skin < clearance:
            clearance = max(below_skin, 0.0)
            nearest = "PLATFORM-SKIN"
        if blocked_by is None and below_skin <= 0:
            blocked_by = "PLATFORM-SKIN"
        results.append(
            RayResult(
                ray=ray,
                blocked_by=blocked_by,
                clearance=clearance,
                nearest=nearest,
                below_skin=below_skin,
            )
        )
    return results


def check_clearance(
    root: Path | None = None,
) -> tuple[list[Finding], list[RayResult], float, float]:
    """Run the field of view checks and return the findings and the ray results."""
    base = Path(root) if root else REPO_ROOT
    layout = load_layout(base)
    if layout.field_of_view is None:
        raise ValueError(f"{LAYOUT_PATH} declares no field_of_view geometry")
    fov = layout.field_of_view
    lower, upper = load_elevation_range(base)
    rays = build_sector(
        gimbal=(fov.gimbal_x, fov.gimbal_y),
        radius=fov.head_radius,
        lower_deg=lower,
        upper_deg=upper,
        step_deg=fov.ray_step_deg,
    )
    results = evaluate_rays(rays, layout.side_frame, layout.platform_skin_y)

    limit = float(layout.rules["minimum_clearance_mm"])
    blocked = [result for result in results if result.blocked_by]
    tightest = min(results, key=lambda result: result.clearance)
    highest = max(result.ray.end[1] for result in results)
    below_skin = layout.platform_skin_y - highest

    findings = [
        make_finding(
            "FOV-OBSTRUCTION",
            "payload-installed",
            not blocked,
            float(len(blocked)),
            0.0,
            f"{len(blocked)} of {len(results)} rays obstructed"
            + (
                f", first at {blocked[0].ray.elevation_deg:+.1f} deg by {blocked[0].blocked_by}"
                if blocked
                else f"; swept sector from {lower:g} to {upper:g} deg is clear"
            ),
            mode="max",
        ),
        make_finding(
            "FOV-SKIN",
            "payload-installed",
            below_skin >= limit,
            below_skin,
            limit,
            f"highest ray reaches y = {highest:.1f} mm, {below_skin:.1f} mm below the skin "
            f"(clearance {limit:g} mm)",
        ),
        make_finding(
            "FOV-CLEARANCE",
            "payload-installed",
            tightest.clearance >= limit,
            tightest.clearance,
            limit,
            f"tightest direction {tightest.ray.elevation_deg:+.1f} deg, "
            f"nearest element {tightest.nearest}: {tightest.clearance:.1f} mm "
            f"(clearance {limit:g} mm)",
        ),
    ]
    return findings, results, lower, upper


def marginal_directions(results: list[RayResult], limit: float) -> list[RayResult]:
    """Directions whose margin is inside twice the limit."""
    threshold = 2 * limit
    return [
        result
        for result in sorted(results, key=lambda item: item.clearance)
        if result.clearance < threshold
    ]


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def render_checks(
    findings: list[Finding],
    results: list[RayResult],
    lower: float,
    upper: float,
    limit: float,
) -> str:
    """Render the machine-readable result."""
    payload = {
        "configuration": "payload-installed",
        "elevation_deg": {"lower": lower, "upper": upper},
        "rays": len(results),
        "clearance_limit_mm": limit,
        "minimum_clearance_mm": round(min(result.clearance for result in results), 3),
        "highest_ray_y_mm": round(max(result.ray.end[1] for result in results), 3),
        "obstructed_rays": sum(1 for result in results if result.blocked_by),
        "marginal_directions": [
            {
                "elevation_deg": result.ray.elevation_deg,
                "clearance_mm": round(result.clearance, 3),
                "nearest": result.nearest,
            }
            for result in marginal_directions(results, limit)
        ],
        "summary": summarise(findings),
        "findings": [finding.as_dict() for finding in findings],
    }
    return json.dumps(payload, indent=2) + "\n"


def render_report(
    findings: list[Finding],
    results: list[RayResult],
    lower: float,
    upper: float,
    limit: float,
) -> str:
    """Render the readable report with the direction table."""
    summary = summarise(findings)
    lines = [
        "<!-- Generated by tools/clearance.py — do not edit by hand. -->",
        "<!-- Run: python -m tools.clearance -->",
        "",
        "# Field of view and clearance",
        "",
        f"Configuration: payload installed. Swept sector from {lower:g} to {upper:g} deg of "
        f"elevation, {len(results)} sampled rays, clearance requirement {limit:g} mm "
        "(SYS009).",
        "",
        f"{summary['checks']} checks, {summary['passed']} passed, {summary['failed']} failed.",
        "",
        "## Checks",
        "",
        *findings_table(findings),
        "",
        "## Clearance by direction",
        "",
        "| Elevation (deg) | Nearest element | Clearance (mm) | Obstructed |",
        "| --- | --- | --- | --- |",
    ]
    step = REPORT_STEP_DEG
    milestones = [result for result in results if abs(result.ray.elevation_deg % step) < 1e-9]
    for result in milestones:
        lines.append(
            f"| {result.ray.elevation_deg:+.0f} | {result.nearest} | "
            f"{result.clearance:.1f} | {result.blocked_by or '—'} |"
        )
    lines.append("")
    marginal = marginal_directions(results, limit)
    lines.append("## Marginal directions")
    lines.append("")
    if marginal:
        lines.append(f"Directions with a margin inside twice the limit ({2 * limit:g} mm):")
        lines.append("")
        lines.append("| Elevation (deg) | Nearest element | Clearance (mm) |")
        lines.append("| --- | --- | --- |")
        for result in marginal:
            lines.append(
                f"| {result.ray.elevation_deg:+.1f} | {result.nearest} | {result.clearance:.1f} |"
            )
    else:
        lines.append(
            f"None: every direction keeps more than twice the limit ({2 * limit:g} mm) of "
            "clearance."
        )
    lines.append("")
    lines.append(
        "The sector exists only with the payload installed; the removed configuration is "
        "covered by the removal-corridor check in the layout evidence. The platform skin is "
        "treated as the boundary of the platform body in the side view."
    )
    lines.append("")
    return "\n".join(lines)


def render_svg(
    results: list[RayResult],
    obstacles: tuple[NamedRect, ...],
    payload_envelope: NamedRect,
    removal_corridor: NamedRect,
    gimbal: tuple[float, float],
    radius: float,
    limit: float,
) -> str:
    """Render the swept sector and the rays over the side view."""

    def to_px(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        return (40 + (x + 560) * 0.4, 40 + (0 - y) * 0.4)

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 500" width="520" height="500">',
        "  <style>",
        "    rect.frame { fill: #dde3ee; stroke: #33415c; stroke-width: 1; }",
        "    rect.payload { fill: #ffe8cc; stroke: #a15c00; stroke-width: 1; }",
        "    rect.corridor { fill: none; stroke: #2f7d32; stroke-width: 1; stroke-dasharray: 6 4; }",
        "    line.ray { stroke: #1565c0; stroke-width: 1; }",
        "    line.ray.blocked { stroke: #c62828; stroke-width: 1.5; }",
        "    line.ray.tight { stroke: #ef6c00; stroke-width: 1.5; }",
        "    circle { fill: #33415c; }",
        "    text { font: 10px sans-serif; fill: #223; }",
        "  </style>",
        '  <text x="40" y="24">Swept sector, side view (mm)</text>',
    ]

    def rect_svg(rect: NamedRect, css: str) -> str:
        x, y = to_px((rect.rect.x0, rect.rect.y1))
        return (
            f'  <rect class="{css}" x="{x:.1f}" y="{y:.1f}" '
            f'width="{(rect.rect.x1 - rect.rect.x0) * 0.4:.1f}" '
            f'height="{(rect.rect.y1 - rect.rect.y0) * 0.4:.1f}" />'
        )

    lines.append(rect_svg(payload_envelope, "payload"))
    lines.append(rect_svg(removal_corridor, "corridor"))
    for obstacle in obstacles:
        lines.append(rect_svg(obstacle, "frame"))
    for result in results:
        start = to_px(result.ray.start)
        end = to_px(result.ray.end)
        css = "ray"
        if result.blocked_by:
            css += " blocked"
        elif result.clearance < 2 * limit:
            css += " tight"
        lines.append(
            f'  <line class="{css}" x1="{start[0]:.1f}" y1="{start[1]:.1f}" '
            f'x2="{end[0]:.1f}" y2="{end[1]:.1f}" />'
        )
    centre = to_px(gimbal)
    lines.append(f'  <circle cx="{centre[0]:.1f}" cy="{centre[1]:.1f}" r="3" />')
    lines.append(
        f'  <text x="{centre[0] + 8:.1f}" y="{centre[1] - 6:.1f}">gimbal axis, '
        f"head radius {radius:g} mm</text>"
    )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def generated_files(root: Path | None = None) -> dict[str, str]:
    """Return the content of every generated evidence file."""
    base = Path(root) if root else REPO_ROOT
    findings, results, lower, upper = check_clearance(base)
    layout = load_layout(base)
    limit = float(layout.rules["minimum_clearance_mm"])
    fov = layout.field_of_view
    assert fov is not None
    return {
        "checks.json": render_checks(findings, results, lower, upper, limit),
        "report.md": render_report(findings, results, lower, upper, limit),
        "sweep.svg": render_svg(
            results,
            layout.side_frame,
            layout.payload_envelope,
            layout.removal_corridor,
            (fov.gimbal_x, fov.gimbal_y),
            fov.head_radius,
            limit,
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.clearance", description=__doc__)
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root (default: the repo)")
    parser.add_argument("--check", action="store_true", help="fail if the evidence is out of date")
    args = parser.parse_args(argv)

    root = Path(args.root)
    findings, _, _, _ = check_clearance(root)
    files = generated_files(root)
    failed = [finding for finding in findings if finding.status == "FAIL"]

    if args.check:
        stale = []
        for name, content in files.items():
            path = root / EVIDENCE_DIR / name
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != content:
                stale.append(name)
        if stale:
            print(f"stale clearance evidence: {', '.join(stale)} — run python -m tools.clearance")
            return 1
        print(f"clearance evidence is up to date ({len(findings)} checks, {len(failed)} failed)")
        return 1 if failed else 0

    target = root / EVIDENCE_DIR
    target.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (target / name).write_text(content, encoding="utf-8")
    print(
        f"wrote {EVIDENCE_DIR}: {len(findings)} checks, "
        f"{len(findings) - len(failed)} passed, {len(failed)} failed"
    )
    for finding in failed:
        print(f"  FAIL {finding.check}: {finding.message}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
