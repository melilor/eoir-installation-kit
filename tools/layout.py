"""Generate and check the installation layout.

The layout is a two-view 2D envelope model declared in ``model/layout.yaml``:
rectangles, circles and orthogonal harness paths, in millimetres. It is not a 3D
CAD model, and the hole is declared rather than hidden.

This module produces, from that single definition:

* ``evidence/layout/checks.json`` — the result of every geometric and data check
* ``evidence/layout/report.md`` — the same results, readable
* ``evidence/layout/layout.svg`` — the two views as a figure
* ``evidence/layout/layout.dxf`` — a neutral R12 ASCII export of the two views

``python -m tools.layout`` writes them; ``python -m tools.layout --check`` fails
when a committed file differs from what the model produces, which is how CI
keeps the published evidence from drifting.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from math import hypot
from pathlib import Path
from typing import Any

import yaml

from .analysis import Finding, findings_table, make_finding, sort_findings, summarise
from .model import REPO_ROOT

LAYOUT_PATH = Path("model/layout.yaml")
EVIDENCE_DIR = Path("evidence/layout")
GENERATED_FILES = ("checks.json", "report.md", "layout.svg", "layout.dxf")

#: The two views are placed side by side in the DXF export.
DXF_VIEW_OFFSET_X = 1200.0
#: SVG pixels per millimetre.
SVG_SCALE = 0.4


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Rect:
    """An axis-aligned rectangle, in millimetres."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def centre(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    @property
    def corners(self) -> tuple[tuple[float, float], ...]:
        return ((self.x0, self.y0), (self.x1, self.y0), (self.x1, self.y1), (self.x0, self.y1))

    def contains(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def intersects(self, other: "Rect") -> bool:
        return not (
            self.x1 <= other.x0 or other.x1 <= self.x0 or self.y1 <= other.y0 or other.y1 <= self.y0
        )

    def distance_to_point(self, x: float, y: float) -> float:
        dx = max(self.x0 - x, x - self.x1, 0.0)
        dy = max(self.y0 - y, y - self.y1, 0.0)
        return hypot(dx, dy)

    def distance_to_rect(self, other: "Rect") -> float:
        """Distance to another rectangle, zero when they touch or overlap."""
        if self.intersects(other):
            return 0.0
        gap_x = max(other.x0 - self.x1, self.x0 - other.x1, 0.0)
        gap_y = max(other.y0 - self.y1, self.y0 - other.y1, 0.0)
        return hypot(gap_x, gap_y)


@dataclass(frozen=True)
class NamedRect:
    id: str
    name: str
    rect: Rect


@dataclass(frozen=True)
class Fastener:
    id: str
    fitting: str
    x: float
    y: float
    diameter: float
    locking_devices: int


@dataclass(frozen=True)
class Connector:
    id: str
    name: str
    x: float
    y: float
    access_radius: float


@dataclass(frozen=True)
class InspectionZone:
    id: str
    fitting: str
    rect: Rect


@dataclass(frozen=True)
class Harness:
    id: str
    name: str
    cable_od: float
    bend_radius: float
    path: tuple[tuple[float, float], ...]
    clamps: tuple[tuple[float, float], ...]

    @property
    def segments(self) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
        return tuple(zip(self.path, self.path[1:]))


@dataclass(frozen=True)
class InterfaceRef:
    label: str
    icd: str
    path: str
    expect: Any


@dataclass(frozen=True)
class FieldOfView:
    """The swept sector of the rotating head in the side view."""

    gimbal_x: float
    gimbal_y: float
    head_radius: float
    ray_step_deg: float


@dataclass(frozen=True)
class Layout:
    revision: str
    units: str
    rules: dict[str, float]
    side_frame: tuple[NamedRect, ...]
    payload_envelope: NamedRect
    removal_corridor: NamedRect
    footprint: NamedRect
    bottom_frame: tuple[NamedRect, ...]
    fittings: tuple[NamedRect, ...]
    fasteners: tuple[Fastener, ...]
    connectors: tuple[Connector, ...]
    inspection_zones: tuple[InspectionZone, ...]
    hot_zones: tuple[NamedRect, ...]
    moving_parts: tuple[NamedRect, ...]
    harnesses: tuple[Harness, ...]
    interface_refs: tuple[InterfaceRef, ...]
    field_of_view: FieldOfView | None = None
    platform_skin_y: float = 0.0


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def _rect(values: list[float]) -> Rect:
    x0, y0, x1, y1 = (float(value) for value in values)
    return Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _named(entry: dict[str, Any]) -> NamedRect:
    return NamedRect(entry["id"], entry.get("name", ""), _rect(entry["rect"]))


def load_layout(root: Path | None = None) -> Layout:
    """Load ``model/layout.yaml`` into typed structures."""
    base = Path(root) if root else REPO_ROOT
    raw = yaml.safe_load((base / LAYOUT_PATH).read_text(encoding="utf-8"))
    side = raw["side_view"]
    bottom = raw["bottom_view"]
    fov_raw = side.get("field_of_view")
    field_of_view = (
        FieldOfView(
            gimbal_x=float(fov_raw["gimbal_centre"][0]),
            gimbal_y=float(fov_raw["gimbal_centre"][1]),
            head_radius=float(fov_raw["head_radius_mm"]),
            ray_step_deg=float(fov_raw["ray_step_deg"]),
        )
        if fov_raw
        else None
    )
    return Layout(
        revision=raw["revision"],
        units=raw["units"],
        rules={key: float(value) for key, value in raw["declared_rules"].items()},
        side_frame=tuple(_named(entry) for entry in side["frame_members"]),
        payload_envelope=_named(side["payload_envelope"]),
        removal_corridor=_named(side["removal_corridor"]),
        footprint=_named(bottom["payload_footprint"]),
        bottom_frame=tuple(_named(entry) for entry in bottom["frame_members"]),
        fittings=tuple(_named(entry) for entry in bottom["fittings"]),
        fasteners=tuple(
            Fastener(
                id=entry["id"],
                fitting=entry["fitting"],
                x=float(entry["position"][0]),
                y=float(entry["position"][1]),
                diameter=float(entry["diameter"]),
                locking_devices=int(entry["locking_devices"]),
            )
            for entry in bottom["fasteners"]
        ),
        connectors=tuple(
            Connector(
                id=entry["id"],
                name=entry.get("name", ""),
                x=float(entry["position"][0]),
                y=float(entry["position"][1]),
                access_radius=float(entry["access_radius"]),
            )
            for entry in bottom["connectors"]
        ),
        inspection_zones=tuple(
            InspectionZone(entry["id"], entry["fitting"], _rect(entry["rect"]))
            for entry in bottom["inspection_zones"]
        ),
        hot_zones=tuple(_named(entry) for entry in bottom["hot_zones"]),
        moving_parts=tuple(_named(entry) for entry in bottom["moving_parts"]),
        harnesses=tuple(
            Harness(
                id=entry["id"],
                name=entry.get("name", ""),
                cable_od=float(entry["cable_od"]),
                bend_radius=float(entry["bend_radius"]),
                path=tuple((float(x), float(y)) for x, y in entry["path"]),
                clamps=tuple((float(x), float(y)) for x, y in entry["clamps"]),
            )
            for entry in bottom["harnesses"]
        ),
        interface_refs=tuple(
            InterfaceRef(entry["label"], entry["icd"], entry["path"], entry["expect"])
            for entry in raw["interface_refs"]
        ),
        field_of_view=field_of_view,
        platform_skin_y=float(side.get("platform_skin_y", 0.0)),
    )


# --------------------------------------------------------------------------- #
# Geometry helpers for the harness checks
# --------------------------------------------------------------------------- #


def segment_rect_distance(
    a: tuple[float, float], b: tuple[float, float], rect: Rect
) -> float:
    """Distance between an axis-aligned segment and an axis-aligned rectangle.

    Exact for the axis-aligned geometry declared in the layout: the gaps on the
    two axes are independent, and the distance is their hypotenuse.
    """
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((a[1], b[1]))
    gap_x = max(rect.x0 - x1, x0 - rect.x1, 0.0)
    gap_y = max(rect.y0 - y1, y0 - rect.y1, 0.0)
    return hypot(gap_x, gap_y)


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


def _distance_along_path(point: tuple[float, float], path: tuple[tuple[float, float], ...]) -> float:
    """Distance from the start of the path to the projection of a point on it."""
    best_distance = float("inf")
    best_along = 0.0
    travelled = 0.0
    for a, b in zip(path, path[1:]):
        length = hypot(b[0] - a[0], b[1] - a[1])
        dx, dy = b[0] - a[0], b[1] - a[1]
        if length == 0:
            continue
        t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (length * length)))
        projected = (a[0] + t * dx, a[1] + t * dy)
        distance = hypot(point[0] - projected[0], point[1] - projected[1])
        if distance < best_distance:
            best_distance = distance
            best_along = travelled + t * length
        travelled += length
    return best_along


def path_length(path: tuple[tuple[float, float], ...]) -> float:
    return sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))


def _resolve_path(document: Any, dotted: str) -> Any:
    node = document
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            raise KeyError(dotted)
        node = node[key]
    return node


# --------------------------------------------------------------------------- #
# Checks — one function per rule, each returning Finding objects
# --------------------------------------------------------------------------- #


def check_removal_corridor(layout: Layout) -> list[Finding]:
    """No side-view frame member may obstruct the payload removal corridor."""
    findings = []
    for member in layout.side_frame:
        intersects = member.rect.intersects(layout.removal_corridor.rect)
        findings.append(
            make_finding(
                "REMOVAL-CORRIDOR",
                member.id,
                not intersects,
                layout.removal_corridor.rect.distance_to_point(*member.rect.centre),
                0.0,
                f"{member.name} does not obstruct {layout.removal_corridor.id}"
                if not intersects
                else f"{member.name} obstructs {layout.removal_corridor.id}",
            )
        )
    return findings


def check_connector_access(layout: Layout) -> list[Finding]:
    """Each payload connector needs a free access cylinder."""
    findings = []
    for connector in layout.connectors:
        limit = float(layout.rules["connector_access_radius"])
        for member in layout.bottom_frame:
            distance = member.rect.distance_to_point(connector.x, connector.y)
            findings.append(
                make_finding(
                    "CONNECTOR-ACCESS",
                    f"{connector.id}/{member.id}",
                    distance >= limit,
                    distance,
                    limit,
                    f"{connector.name} access radius {connector.access_radius:g} mm "
                    f"to {member.name}: {distance:.1f} mm (need {limit:g} mm)",
                )
            )
    return findings


def check_fitting_edge_distance(layout: Layout) -> list[Finding]:
    """Each fastener hole needs an edge distance of at least 2 diameters."""
    findings = []
    factor = float(layout.rules["edge_distance_factor"])
    fittings = {fitting.id: fitting for fitting in layout.fittings}
    for fastener in layout.fasteners:
        fitting = fittings.get(fastener.fitting)
        if fitting is None:
            findings.append(
                make_finding(
                    "FITTING-EDGE-DISTANCE",
                    fastener.id,
                    False,
                    -1.0,
                    factor * fastener.diameter,
                    f"fastener {fastener.id} references unknown fitting {fastener.fitting}",
                )
            )
            continue
        limit = factor * fastener.diameter
        edges = (
            fastener.x - fitting.rect.x0,
            fitting.rect.x1 - fastener.x,
            fastener.y - fitting.rect.y0,
            fitting.rect.y1 - fastener.y,
        )
        smallest = min(edges)
        findings.append(
            make_finding(
                "FITTING-EDGE-DISTANCE",
                f"{fastener.id}/{fitting.id}",
                smallest >= limit,
                smallest,
                limit,
                f"smallest edge distance of {fastener.id} in {fitting.id}: {smallest:.1f} mm "
                f"(need {limit:g} mm)",
            )
        )
    return findings


def check_hole_pitch(layout: Layout) -> list[Finding]:
    """Fasteners on the same fitting are at least three diameters apart."""
    findings = []
    factor = float(layout.rules["hole_pitch_factor"])
    by_fitting: dict[str, list[Fastener]] = {}
    for fastener in layout.fasteners:
        by_fitting.setdefault(fastener.fitting, []).append(fastener)
    for fitting_id, fasteners in sorted(by_fitting.items()):
        for index, first in enumerate(fasteners):
            for second in fasteners[index + 1 :]:
                distance = hypot(first.x - second.x, first.y - second.y)
                limit = factor * max(first.diameter, second.diameter)
                findings.append(
                    make_finding(
                        "HOLE-PITCH",
                        f"{fitting_id}:{first.id}-{second.id}",
                        distance >= limit,
                        distance,
                        limit,
                        f"pitch between {first.id} and {second.id}: {distance:.1f} mm "
                        f"(need {limit:g} mm)",
                    )
                )
    return findings


def check_fastener_locking(layout: Layout) -> list[Finding]:
    """Each removable fastener carries two independent locking devices."""
    return [
        make_finding(
            "FASTENER-LOCKING",
            fastener.id,
            fastener.locking_devices >= 2,
            float(fastener.locking_devices),
            2.0,
            f"{fastener.id}: {fastener.locking_devices} locking devices (need 2)",
        )
        for fastener in layout.fasteners
    ]


def check_inspection_access(layout: Layout) -> list[Finding]:
    """Inspection zones stay clear of the payload footprint."""
    return [
        make_finding(
            "INSPECTION-ACCESS",
            zone.id,
            not zone.rect.intersects(layout.footprint.rect),
            zone.rect.distance_to_rect(layout.footprint.rect),
            0.0,
            f"{zone.id} is clear of {layout.footprint.id}"
            if not zone.rect.intersects(layout.footprint.rect)
            else f"{zone.id} overlaps {layout.footprint.id}",
        )
        for zone in layout.inspection_zones
    ]


def check_harness_orthogonal(layout: Layout) -> list[Finding]:
    """Harness paths are orthogonal: one coordinate changes per segment."""
    findings = []
    for harness in layout.harnesses:
        for index, (a, b) in enumerate(harness.segments, start=1):
            orthogonal = a[0] == b[0] or a[1] == b[1]
            findings.append(
                make_finding(
                    "HARNESS-ORTHOGONAL",
                    f"{harness.id}:seg{index}",
                    orthogonal,
                    1.0 if orthogonal else 0.0,
                    1.0,
                    f"{harness.id} segment {index} is "
                    + ("orthogonal" if orthogonal else "not orthogonal"),
                )
            )
    return findings


def check_bend_radius(layout: Layout) -> list[Finding]:
    """Declared bend radius is at least five cable diameters."""
    findings = []
    factor = float(layout.rules["bend_radius_factor"])
    for harness in layout.harnesses:
        limit = factor * harness.cable_od
        findings.append(
            make_finding(
                "BEND-RADIUS",
                harness.id,
                harness.bend_radius >= limit,
                harness.bend_radius,
                limit,
                f"{harness.name} bend radius {harness.bend_radius:g} mm "
                f"(need {limit:g} mm for {harness.cable_od:g} mm cable)",
            )
        )
    return findings


def check_clamp_on_path(layout: Layout) -> list[Finding]:
    """Every clamp sits on its harness path."""
    findings = []
    limit = 1.0
    for harness in layout.harnesses:
        for index, clamp in enumerate(harness.clamps, start=1):
            distance = min(
                _distance_point_to_segment(clamp, a, b) for a, b in harness.segments
            )
            findings.append(
                make_finding(
                    "CLAMP-ON-PATH",
                    f"{harness.id}:clamp{index}",
                    distance <= limit,
                    distance,
                    limit,
                    f"clamp {index} of {harness.id} is {distance:.1f} mm from the path "
                    f"(limit {limit:g} mm)",
                    mode="max",
                )
            )
    return findings


def check_clamp_spacing(layout: Layout) -> list[Finding]:
    """Distance between consecutive clamps, including the path ends."""
    findings = []
    limit = float(layout.rules["clamp_spacing_max"])
    for harness in layout.harnesses:
        positions = [0.0]
        positions += [_distance_along_path(clamp, harness.path) for clamp in harness.clamps]
        positions.append(path_length(harness.path))
        positions.sort()
        for index, (first, second) in enumerate(zip(positions, positions[1:]), start=1):
            gap = second - first
            findings.append(
                make_finding(
                    "CLAMP-SPACING",
                    f"{harness.id}:gap{index}",
                    gap <= limit,
                    gap,
                    limit,
                    f"{harness.id} gap {index} between clamps: {gap:.1f} mm (limit {limit:g} mm)",
                    mode="max",
                )
            )
    return findings


def check_harness_clearance(layout: Layout) -> list[Finding]:
    """Harnesses stay clear of hot zones and moving parts."""
    findings = []
    limit = float(layout.rules["harness_clearance"])
    obstacles = layout.hot_zones + layout.moving_parts
    for harness in layout.harnesses:
        for index, (a, b) in enumerate(harness.segments, start=1):
            for obstacle in obstacles:
                distance = segment_rect_distance(a, b, obstacle.rect)
                findings.append(
                    make_finding(
                        "HARNESS-CLEARANCE",
                        f"{harness.id}:seg{index}/{obstacle.id}",
                        distance >= limit,
                        distance,
                        limit,
                        f"{harness.name} segment {index} to {obstacle.name}: {distance:.1f} mm "
                        f"(need {limit:g} mm)",
                    )
                )
    return findings


def check_icd_consistency(layout: Layout, root: Path) -> list[Finding]:
    """Values declared in the layout agree with the interface control data."""
    findings = []
    for reference in layout.interface_refs:
        icd_path = root / reference.icd
        if not icd_path.exists():
            findings.append(
                make_finding(
                    "ICD-CONSISTENCY",
                    reference.label,
                    False,
                    -1.0,
                    0.0,
                    f"{reference.icd} does not exist",
                )
            )
            continue
        document = yaml.safe_load(icd_path.read_text(encoding="utf-8"))
        try:
            actual = _resolve_path(document, reference.path)
        except KeyError:
            findings.append(
                make_finding(
                    "ICD-CONSISTENCY",
                    reference.label,
                    False,
                    -1.0,
                    0.0,
                    f"{reference.path} not found in {reference.icd}",
                )
            )
            continue
        findings.append(
            make_finding(
                "ICD-CONSISTENCY",
                reference.label,
                actual == reference.expect,
                1.0 if actual == reference.expect else 0.0,
                1.0,
                f"{reference.label}: {reference.icd}#{reference.path} = {actual!r}, "
                f"declared {reference.expect!r}",
            )
        )
    return findings


def check_layout(layout: Layout, root: Path | None = None) -> list[Finding]:
    """Run every layout check and return the findings, failures first."""
    base = Path(root) if root else REPO_ROOT
    findings: list[Finding] = []
    findings += check_removal_corridor(layout)
    findings += check_connector_access(layout)
    findings += check_fitting_edge_distance(layout)
    findings += check_hole_pitch(layout)
    findings += check_fastener_locking(layout)
    findings += check_inspection_access(layout)
    findings += check_harness_orthogonal(layout)
    findings += check_bend_radius(layout)
    findings += check_clamp_on_path(layout)
    findings += check_clamp_spacing(layout)
    findings += check_harness_clearance(layout)
    findings += check_icd_consistency(layout, base)
    return sort_findings(findings)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def render_checks(layout: Layout, findings: list[Finding]) -> str:
    """Render the machine-readable check result."""
    payload = {
        "revision": layout.revision,
        "units": layout.units,
        "declared_rules": layout.rules,
        "summary": summarise(findings),
        "findings": [finding.as_dict() for finding in findings],
    }
    return json.dumps(payload, indent=2) + "\n"


def render_report(layout: Layout, findings: list[Finding]) -> str:
    """Render the check result as a readable report."""
    passed = sum(1 for finding in findings if finding.status == "PASS")
    failed = len(findings) - passed
    lines = [
        "<!-- Generated by tools/layout.py — do not edit by hand. -->",
        "<!-- Run: python -m tools.layout -->",
        "",
        "# Layout checks",
        "",
        f"Revision {layout.revision}, units {layout.units}. "
        f"{len(findings)} checks, {passed} passed, {failed} failed.",
        "",
        *findings_table(findings),
        "",
    ]
    lines.append("## Declared rules")
    lines.append("")
    lines.append("| Rule | Value |")
    lines.append("| --- | --- |")
    for name, value in sorted(layout.rules.items()):
        lines.append(f"| {name} | {value:g} |")
    lines.append("")
    lines.append(
        "The layout is a two-view 2D envelope model: rectangles, circles and orthogonal "
        "harness paths. Three-dimensional interference checking and the strength analysis are "
        "separate work, tracked by their own tickets."
    )
    lines.append("")
    return "\n".join(lines)


def _svg_rect(rect: Rect, to_px, css_class: str) -> str:
    x, y = to_px((rect.x0, rect.y1))
    width = (rect.x1 - rect.x0) * SVG_SCALE
    height = (rect.y1 - rect.y0) * SVG_SCALE
    return f'  <rect class="{css_class}" x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" />'


def render_svg(layout: Layout) -> str:
    """Render the two views as an SVG figure."""

    def side_px(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        return (40 + (x + 560) * SVG_SCALE, 40 + (0 - y) * SVG_SCALE)

    def bottom_px(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        return (40 + (x + 560) * SVG_SCALE, 500 + (300 - y) * SVG_SCALE)

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 760" width="520" height="760">',
        "  <style>",
        "    rect.frame { fill: #dde3ee; stroke: #33415c; stroke-width: 1; }",
        "    rect.payload { fill: #ffe8cc; stroke: #a15c00; stroke-width: 1; }",
        "    rect.corridor { fill: none; stroke: #2f7d32; stroke-width: 1; stroke-dasharray: 6 4; }",
        "    rect, circle { vector-effect: non-scaling-stroke; }",
        "    rect.zone { fill: #e8f5e9; stroke: #2f7d32; stroke-width: 1; }",
        "    rect.hot { fill: #ffe0e0; stroke: #a11212; stroke-width: 1; }",
        "    rect.moving { fill: #ede7f6; stroke: #5e35b1; stroke-width: 1; }",
        "    rect.fitting { fill: #fff3c4; stroke: #8d6e00; stroke-width: 1; }",
        "    polyline { fill: none; stroke: #1565c0; stroke-width: 2; }",
        "    circle { fill: none; stroke: #1565c0; stroke-width: 1; }",
        "    circle.access { stroke: #0d47a1; stroke-dasharray: 4 3; }",
        "    circle.hole { fill: #33415c; stroke: none; }",
        "    text { font: 10px sans-serif; fill: #223; }",
        "  </style>",
        '  <text x="40" y="24">Side view (mm, y up)</text>',
    ]
    lines.append(_svg_rect(layout.payload_envelope.rect, side_px, "payload"))
    lines.append(_svg_rect(layout.removal_corridor.rect, side_px, "corridor"))
    for member in layout.side_frame:
        lines.append(_svg_rect(member.rect, side_px, "frame"))
    lines.append(_svg_rect(layout.footprint.rect, bottom_px, "payload"))
    for member in layout.bottom_frame:
        lines.append(_svg_rect(member.rect, bottom_px, "frame"))
    for zone in layout.inspection_zones:
        lines.append(_svg_rect(zone.rect, bottom_px, "zone"))
    for obstacle in layout.hot_zones:
        lines.append(_svg_rect(obstacle.rect, bottom_px, "hot"))
    for obstacle in layout.moving_parts:
        lines.append(_svg_rect(obstacle.rect, bottom_px, "moving"))
    for fitting in layout.fittings:
        lines.append(_svg_rect(fitting.rect, bottom_px, "fitting"))
    for fastener in layout.fasteners:
        x, y = bottom_px((fastener.x, fastener.y))
        lines.append(f'  <circle class="hole" cx="{x:.1f}" cy="{y:.1f}" r="{fastener.diameter * SVG_SCALE:.1f}" />')
    for connector in layout.connectors:
        x, y = bottom_px((connector.x, connector.y))
        radius = connector.access_radius * SVG_SCALE
        lines.append(f'  <circle class="access" cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" />')
    for harness in layout.harnesses:
        points = " ".join(f"{x:.1f},{y:.1f}" for x, y in (bottom_px(point) for point in harness.path))
        lines.append(f'  <polyline points="{points}" />')
        for clamp in harness.clamps:
            x, y = bottom_px(clamp)
            lines.append(f'  <rect x="{x - 2:.1f}" y="{y - 2:.1f}" width="4" height="4" fill="#1565c0" />')
    lines.append('  <text x="40" y="484">Bottom view (mm, x forward, y right)</text>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _dxf_rect(rect: Rect, layer: str, offset_x: float = 0.0) -> list[str]:
    entities: list[str] = []
    corners = rect.corners
    for index in range(4):
        a = corners[index]
        b = corners[(index + 1) % 4]
        entities += [
            "0", "LINE", "8", layer,
            "10", f"{a[0] + offset_x:.3f}", "20", f"{a[1]:.3f}", "30", "0.0",
            "11", f"{b[0] + offset_x:.3f}", "21", f"{b[1]:.3f}", "31", "0.0",
        ]
    return entities


def _dxf_circle(cx: float, cy: float, radius: float, layer: str, offset_x: float = 0.0) -> list[str]:
    return [
        "0", "CIRCLE", "8", layer,
        "10", f"{cx + offset_x:.3f}", "20", f"{cy:.3f}", "30", "0.0",
        "40", f"{radius:.3f}",
    ]


def _dxf_text(x: float, y: float, text: str, layer: str = "TEXT", offset_x: float = 0.0) -> list[str]:
    return [
        "0", "TEXT", "8", layer,
        "10", f"{x + offset_x:.3f}", "20", f"{y:.3f}", "30", "0.0",
        "40", "25.0", "1", text,
    ]


def render_dxf(layout: Layout) -> str:
    """Render the two views as a minimal DXF R12 ASCII file.

    The side view sits at x = 0, the bottom view is translated by
    ``DXF_VIEW_OFFSET_X`` so the two do not overlap.
    """
    entities: list[str] = []
    entities += _dxf_text(-520, 60, "SIDE VIEW")
    entities += _dxf_rect(layout.payload_envelope.rect, "PAYLOAD")
    entities += _dxf_rect(layout.removal_corridor.rect, "ZONE")
    for member in layout.side_frame:
        entities += _dxf_rect(member.rect, "FRAME")

    offset = DXF_VIEW_OFFSET_X
    entities += _dxf_text(-520, 320, "BOTTOM VIEW", offset_x=offset)
    entities += _dxf_rect(layout.footprint.rect, "PAYLOAD", offset)
    for member in layout.bottom_frame:
        entities += _dxf_rect(member.rect, "FRAME", offset)
    for fitting in layout.fittings:
        entities += _dxf_rect(fitting.rect, "FITTING", offset)
    for zone in layout.inspection_zones:
        entities += _dxf_rect(zone.rect, "ZONE", offset)
    for obstacle in layout.hot_zones + layout.moving_parts:
        entities += _dxf_rect(obstacle.rect, "ZONE", offset)
    for fastener in layout.fasteners:
        entities += _dxf_circle(fastener.x, fastener.y, fastener.diameter / 2, "FASTENER", offset)
    for connector in layout.connectors:
        entities += _dxf_circle(connector.x, connector.y, connector.access_radius, "ZONE", offset)
    for harness in layout.harnesses:
        for a, b in harness.segments:
            entities += [
                "0", "LINE", "8", "HARNESS",
                "10", f"{a[0] + offset:.3f}", "20", f"{a[1]:.3f}", "30", "0.0",
                "11", f"{b[0] + offset:.3f}", "21", f"{b[1]:.3f}", "31", "0.0",
            ]

    lines = ["0", "SECTION", "2", "ENTITIES", *entities, "0", "ENDSEC", "0", "EOF"]
    return "\n".join(lines) + "\n"


def generated_files(layout: Layout, findings: list[Finding]) -> dict[str, str]:
    """Return the content of every generated evidence file."""
    return {
        "checks.json": render_checks(layout, findings),
        "report.md": render_report(layout, findings),
        "layout.svg": render_svg(layout),
        "layout.dxf": render_dxf(layout),
    }


# --------------------------------------------------------------------------- #
# Command line
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.layout", description=__doc__)
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root (default: the repo)")
    parser.add_argument("--check", action="store_true", help="fail if the evidence is out of date")
    args = parser.parse_args(argv)

    root = Path(args.root)
    layout = load_layout(root)
    findings = check_layout(layout, root)
    files = generated_files(layout, findings)
    failed = [finding for finding in findings if finding.status == "FAIL"]

    if args.check:
        stale = []
        for name, content in files.items():
            path = root / EVIDENCE_DIR / name
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != content:
                stale.append(name)
        if stale:
            print(f"stale layout evidence: {', '.join(stale)} — run python -m tools.layout")
            return 1
        print(f"layout evidence is up to date ({len(findings)} checks, {len(failed)} failed)")
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
