"""Layout checks and the exported evidence.

One test per check, each built by breaking exactly one thing in a small synthetic
layout, plus integration tests on the repository layout and its evidence files.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from tools.layout import (
    EVIDENCE_DIR,
    check_layout,
    generated_files,
    load_layout,
    render_dxf,
)
from tools.model import REPO_ROOT

ICD = {"payload": {"mass_kg": 45, "power": {"voltage_vdc": 28}}}


def base_layout() -> dict:
    """A small layout that passes every check."""
    return {
        "revision": "T",
        "date": "2026-01-01",
        "units": "mm",
        "declared_rules": {
            "edge_distance_factor": 2.0,
            "hole_pitch_factor": 3.0,
            "connector_access_radius": 60,
            "inspection_access_radius": 80,
            "harness_clearance": 50,
            "clamp_spacing_max": 200,
            "bend_radius_factor": 5.0,
        },
        "side_view": {
            "platform_skin_y": 0,
            "frame_members": [
                {"id": "SM-01", "name": "Forward structure", "rect": [-520, -260, -380, -40]}
            ],
            "payload_envelope": {"id": "PE-01", "rect": [-190, -480, 190, -40]},
            "removal_corridor": {"id": "RC-01", "rect": [-260, -980, 260, -500]},
        },
        "bottom_view": {
            "payload_footprint": {"id": "PF-01", "rect": [-190, -230, 190, 230]},
            "frame_members": [
                {"id": "BL-01", "name": "Rail", "rect": [-510, 130, 510, 170]},
                {"id": "BM-01", "name": "Beam", "rect": [-30, -170, 30, 170]},
            ],
            "fittings": [{"id": "FT-01", "rect": [-510, -210, -390, -90]}],
            "fasteners": [
                {
                    "id": "F-01",
                    "fitting": "FT-01",
                    "position": [-480, -180],
                    "diameter": 8,
                    "locking_devices": 2,
                },
                {
                    "id": "F-02",
                    "fitting": "FT-01",
                    "position": [-420, -120],
                    "diameter": 8,
                    "locking_devices": 2,
                },
            ],
            "connectors": [
                {"id": "CN-01", "name": "Power connector", "position": [0, 250], "access_radius": 60}
            ],
            "inspection_zones": [{"id": "IZ-01", "fitting": "FT-01", "rect": [-540, -240, -360, -60]}],
            "hot_zones": [{"id": "HZ-01", "name": "Exhaust", "rect": [230, -60, 300, 90]}],
            "moving_parts": [{"id": "MP-01", "name": "Linkage", "rect": [-300, -80, -230, 90]}],
            "harnesses": [
                {
                    "id": "HR-01",
                    "name": "Power harness",
                    "cable_od": 14,
                    "bend_radius": 80,
                    "path": [[-450, -150], [-450, 150], [-30, 150], [-30, 250], [0, 250]],
                    "clamps": [
                        [-450, -50],
                        [-450, 100],
                        [-350, 150],
                        [-200, 150],
                        [-50, 150],
                    ],
                }
            ],
        },
        "interface_refs": [
            {
                "label": "Payload mass",
                "icd": "model/interfaces/icd.yaml",
                "path": "payload.mass_kg",
                "expect": 45,
            }
        ],
    }


def write_layout(tmp_path: Path, data: dict) -> Path:
    (tmp_path / "model" / "interfaces").mkdir(parents=True, exist_ok=True)
    (tmp_path / "model" / "layout.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    (tmp_path / "model" / "interfaces" / "icd.yaml").write_text(
        yaml.safe_dump(ICD), encoding="utf-8"
    )
    return tmp_path


def findings_for(tmp_path: Path, mutate) -> list:
    data = base_layout()
    mutate(data)
    root = write_layout(tmp_path, data)
    return check_layout(load_layout(root), root)


def failed_checks(findings) -> set[str]:
    return {finding.check for finding in findings if finding.status == "FAIL"}


def test_the_base_layout_passes_every_check(tmp_path):
    findings = findings_for(tmp_path, lambda data: None)
    assert failed_checks(findings) == set()
    assert len(findings) > 20


def test_removal_corridor_obstructed_is_a_failure(tmp_path):
    def mutate(data):
        data["side_view"]["frame_members"].append(
            {"id": "SM-09", "name": "Belly mast", "rect": [-100, -620, 100, -560]}
        )

    assert failed_checks(findings_for(tmp_path, mutate)) == {"REMOVAL-CORRIDOR"}


def test_connector_access_blocked_is_a_failure(tmp_path):
    def mutate(data):
        data["bottom_view"]["frame_members"].append(
            {"id": "BM-09", "name": "Bracket", "rect": [-70, 210, 70, 260]}
        )

    assert failed_checks(findings_for(tmp_path, mutate)) == {"CONNECTOR-ACCESS"}


def test_small_edge_distance_is_a_failure(tmp_path):
    def mutate(data):
        data["bottom_view"]["fasteners"][0]["position"] = [-396, -180]

    assert failed_checks(findings_for(tmp_path, mutate)) == {"FITTING-EDGE-DISTANCE"}


def test_unknown_fitting_is_a_failure(tmp_path):
    def mutate(data):
        data["bottom_view"]["fasteners"][0]["fitting"] = "FT-99"

    assert "FITTING-EDGE-DISTANCE" in failed_checks(findings_for(tmp_path, mutate))


def test_hole_pitch_too_small_is_a_failure(tmp_path):
    def mutate(data):
        data["bottom_view"]["fasteners"][1]["position"] = [-470, -170]

    assert "HOLE-PITCH" in failed_checks(findings_for(tmp_path, mutate))


def test_fastener_with_one_locking_device_is_a_failure(tmp_path):
    def mutate(data):
        data["bottom_view"]["fasteners"][0]["locking_devices"] = 1

    assert failed_checks(findings_for(tmp_path, mutate)) == {"FASTENER-LOCKING"}


def test_inspection_zone_over_the_payload_is_a_failure(tmp_path):
    def mutate(data):
        data["bottom_view"]["inspection_zones"][0]["rect"] = [-200, -240, -100, -150]

    assert failed_checks(findings_for(tmp_path, mutate)) == {"INSPECTION-ACCESS"}


def test_diagonal_harness_segment_is_a_failure(tmp_path):
    def mutate(data):
        data["bottom_view"]["harnesses"][0]["path"] = [[-450, -150], [-30, 250]]

    assert "HARNESS-ORTHOGONAL" in failed_checks(findings_for(tmp_path, mutate))


def test_bend_radius_below_the_rule_is_a_failure(tmp_path):
    def mutate(data):
        data["bottom_view"]["harnesses"][0]["bend_radius"] = 40

    assert failed_checks(findings_for(tmp_path, mutate)) == {"BEND-RADIUS"}


def test_clamp_off_the_path_is_a_failure(tmp_path):
    def mutate(data):
        data["bottom_view"]["harnesses"][0]["clamps"][0] = [-450, -400]

    assert "CLAMP-ON-PATH" in failed_checks(findings_for(tmp_path, mutate))


def test_clamp_spacing_beyond_the_rule_is_a_failure(tmp_path):
    def mutate(data):
        data["bottom_view"]["harnesses"][0]["clamps"] = [[-450, -50]]

    assert "CLAMP-SPACING" in failed_checks(findings_for(tmp_path, mutate))


def test_harness_too_close_to_a_hot_zone_is_a_failure(tmp_path):
    def mutate(data):
        data["bottom_view"]["hot_zones"][0]["rect"] = [-300, 130, -200, 170]

    assert failed_checks(findings_for(tmp_path, mutate)) == {"HARNESS-CLEARANCE"}


def test_interface_value_mismatch_is_a_failure(tmp_path):
    def mutate(data):
        data["interface_refs"][0]["expect"] = 40

    assert failed_checks(findings_for(tmp_path, mutate)) == {"ICD-CONSISTENCY"}


def test_missing_interface_path_is_a_failure(tmp_path):
    def mutate(data):
        data["interface_refs"][0]["path"] = "payload.unknown"

    assert failed_checks(findings_for(tmp_path, mutate)) == {"ICD-CONSISTENCY"}


def test_missing_interface_file_is_a_failure(tmp_path):
    def mutate(data):
        data["interface_refs"][0]["icd"] = "model/interfaces/missing.yaml"

    assert failed_checks(findings_for(tmp_path, mutate)) == {"ICD-CONSISTENCY"}


# --------------------------------------------------------------------------- #
# The repository layout and its evidence
# --------------------------------------------------------------------------- #


def test_repository_layout_has_no_failed_check():
    layout = load_layout(REPO_ROOT)
    failed = [finding for finding in check_layout(layout, REPO_ROOT) if finding.status == "FAIL"]
    assert failed == [], [finding.message for finding in failed]


def test_repository_layout_evidence_is_up_to_date():
    layout = load_layout(REPO_ROOT)
    files = generated_files(layout, check_layout(layout, REPO_ROOT))
    for name, content in files.items():
        path = Path(REPO_ROOT) / EVIDENCE_DIR / name
        assert path.exists(), f"{name} is missing"
        assert path.read_text(encoding="utf-8") == content, f"{name} is out of date"


def count_dxf_entities(text: str) -> dict[str, int]:
    counters = {"LINE": 0, "CIRCLE": 0, "TEXT": 0}
    tokens = [line.strip() for line in text.splitlines()]
    for index, token in enumerate(tokens[:-1]):
        if token == "0" and tokens[index + 1] in counters:
            counters[tokens[index + 1]] += 1
    return counters


def test_dxf_export_round_trips_with_the_expected_entity_counts():
    layout = load_layout(REPO_ROOT)
    counts = count_dxf_entities(render_dxf(layout))
    rectangles = (
        2  # payload envelope and removal corridor in the side view
        + len(layout.side_frame)
        + 1  # payload footprint
        + len(layout.bottom_frame)
        + len(layout.fittings)
        + len(layout.inspection_zones)
        + len(layout.hot_zones)
        + len(layout.moving_parts)
    )
    circles = len(layout.fasteners) + len(layout.connectors)
    lines = rectangles * 4 + sum(len(harness.segments) for harness in layout.harnesses)
    assert counts["LINE"] == lines
    assert counts["CIRCLE"] == circles
    assert counts["TEXT"] == 2


def test_svg_contains_a_shape_for_every_rectangle_and_hole():
    layout = load_layout(REPO_ROOT)
    svg = generated_files(layout, check_layout(layout, REPO_ROOT))["layout.svg"]
    rectangles = (
        2
        + len(layout.side_frame)
        + 1
        + len(layout.bottom_frame)
        + len(layout.fittings)
        + len(layout.inspection_zones)
        + len(layout.hot_zones)
        + len(layout.moving_parts)
    )
    assert svg.count("<rect") >= rectangles
    assert svg.count("<circle") >= len(layout.fasteners) + len(layout.connectors)
    assert svg.count("<polyline") == len(layout.harnesses)


def test_check_result_is_deterministic(tmp_path):
    root = write_layout(tmp_path, base_layout())
    layout = load_layout(root)
    first = generated_files(layout, check_layout(layout, root))
    second = generated_files(layout, check_layout(layout, root))
    assert first == second
