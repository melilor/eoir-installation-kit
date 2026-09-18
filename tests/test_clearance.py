"""Field of view and clearance checks, and the exported evidence."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from test_layout import base_layout, write_layout

from tools.clearance import (
    EVIDENCE_DIR,
    build_sector,
    check_clearance,
    generated_files,
    marginal_directions,
)
from tools.model import REPO_ROOT


def fov_layout() -> dict:
    """The layout of the layout tests, with a swept sector declared."""
    data = deepcopy(base_layout())
    data["declared_rules"]["minimum_clearance_mm"] = 25
    data["side_view"]["field_of_view"] = {
        "gimbal_centre": [0, -420],
        "head_radius_mm": 190,
        "ray_step_deg": 0.5,
    }
    return data


def write_fov_layout(tmp_path: Path, mutate=None) -> Path:
    data = fov_layout()
    if mutate is not None:
        mutate(data)
    root = write_layout(tmp_path, data)
    payload = {
        "mass_and_inertia": {"mass_kg": 45, "cg_envelope_mm": {"x": 150}},
        "power": {"voltage_vdc": 28},
        "field_of_view_deg": {"azimuth": "continuous", "elevation": {"lower": -120, "upper": 30}},
    }
    (root / "model" / "interfaces" / "icd_payload.yaml").write_text(
        yaml.safe_dump(payload), encoding="utf-8"
    )
    return root


def failed_checks(root: Path) -> set[str]:
    findings, _, _, _ = check_clearance(root)
    return {finding.check for finding in findings if finding.status == "FAIL"}


def test_the_base_sector_passes_every_check(tmp_path):
    root = write_fov_layout(tmp_path)
    assert failed_checks(root) == set()


def test_sector_has_one_ray_per_step():
    rays = build_sector((0, 0), 100, -120, 30, 0.5)
    assert len(rays) == 301
    assert rays[0].elevation_deg == -120
    assert rays[-1].elevation_deg == 30
    assert rays[0].end[0] == pytest.approx(100 * -0.5, abs=1e-6)


def test_ray_step_must_be_positive():
    with pytest.raises(ValueError):
        build_sector((0, 0), 100, -120, 30, 0)


def test_obstacle_inside_the_sector_is_an_obstruction(tmp_path):
    def mutate(data):
        data["side_view"]["frame_members"].append(
            {"id": "SM-09", "name": "Mast", "rect": [-100, -490, 100, -430]}
        )

    assert "FOV-OBSTRUCTION" in failed_checks(write_fov_layout(tmp_path, mutate))


def test_obstacle_close_to_the_sector_fails_the_clearance(tmp_path):
    def mutate(data):
        # 250 mm from the gimbal axis on the horizontal direction: the sector
        # reaches 190 mm, so the clearance is 60 mm minus the 25 mm rule.
        data["side_view"]["frame_members"].append(
            {"id": "SM-09", "name": "Step", "rect": [205, -450, 245, -390]}
        )

    assert "FOV-CLEARANCE" in failed_checks(write_fov_layout(tmp_path, mutate))


def test_sector_reaching_the_skin_is_a_failure(tmp_path):
    def mutate(data):
        data["side_view"]["frame_members"] = []
        data["side_view"]["field_of_view"]["head_radius_mm"] = 900

    assert "FOV-SKIN" in failed_checks(write_fov_layout(tmp_path, mutate))


def test_marginal_directions_are_reported(tmp_path):
    def mutate(data):
        data["side_view"]["frame_members"].append(
            {"id": "SM-09", "name": "Step", "rect": [220, -450, 260, -390]}
        )

    root = write_fov_layout(tmp_path, mutate)
    findings, results, _, _ = check_clearance(root)
    limit = 25.0
    assert findings  # the checks ran
    marginal = marginal_directions(results, limit)
    assert marginal, "a direction at 30 mm must be reported as marginal"
    assert marginal[0].clearance == pytest.approx(30.0, abs=0.5)


def test_every_ray_has_the_head_radius():
    rays = build_sector((10, -20), 190, -120, 30, 1.0)
    for ray in rays:
        distance = ((ray.end[0] - 10) ** 2 + (ray.end[1] + 20) ** 2) ** 0.5
        assert distance == pytest.approx(190.0)


# --------------------------------------------------------------------------- #
# The repository layout and its evidence
# --------------------------------------------------------------------------- #


def test_repository_clearance_analysis_has_no_failed_check():
    findings, _, _, _ = check_clearance(REPO_ROOT)
    failures = [finding for finding in findings if finding.status == "FAIL"]
    assert failures == [], [finding.message for finding in failures]


def test_repository_clearance_evidence_is_up_to_date():
    for name, content in generated_files(REPO_ROOT).items():
        path = Path(REPO_ROOT) / EVIDENCE_DIR / name
        assert path.exists(), f"{name} is missing"
        assert path.read_text(encoding="utf-8") == content, f"{name} is out of date"
