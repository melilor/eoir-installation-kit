"""Electrical checks, one test per rule, plus the repository model."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

from tools.model import REPO_ROOT
from tools.power import (
    EVIDENCE_DIR,
    check_power,
    generated_files,
    load_power_model,
)


def base_power() -> dict:
    return {
        "revision": "T",
        "date": "2026-01-01",
        "declared_rules": {
            "copper_resistivity_ohm_mm2_per_m": 0.0175,
            "conductor_ampacity_a_per_mm2": 8.0,
            "continuous_voltage_drop_pct": 2.0,
            "peak_voltage_drop_pct": 4.0,
            "breaker_margin_factor": 1.25,
        },
        "harnesses": [
            {
                "id": "HR-01",
                "component": "CMP-04",
                "description": "Power harness",
                "conductor_cross_section_mm2": 2.5,
                "installed_length_m": 2.4,
            }
        ],
        "protection": {
            "component": "CMP-06",
            "device": "Circuit breaker",
            "rating_a": 20,
            "trip_curve": "not available",
        },
        "open_items": ["Inrush against the breaker rating needs the trip curve."],
    }


def base_platform() -> dict:
    return {
        "electrical": {
            "bus_voltage_vdc": 28,
            "bus_capacity_w": 3000,
            "existing_continuous_load_w": 2100,
        }
    }


def base_payload() -> dict:
    return {"power": {"voltage_vdc": 28, "continuous_w": 150, "peak_w": 400, "inrush_a": 25}}


def write_model(tmp_path: Path, power: dict, platform: dict, payload: dict) -> Path:
    (tmp_path / "model" / "interfaces").mkdir(parents=True, exist_ok=True)
    (tmp_path / "model" / "power.yaml").write_text(yaml.safe_dump(power), encoding="utf-8")
    (tmp_path / "model" / "interfaces" / "icd_platform.yaml").write_text(
        yaml.safe_dump(platform), encoding="utf-8"
    )
    (tmp_path / "model" / "interfaces" / "icd_payload.yaml").write_text(
        yaml.safe_dump(payload), encoding="utf-8"
    )
    return tmp_path


def failed(tmp_path: Path, mutate) -> set[str]:
    power = deepcopy(base_power())
    platform = deepcopy(base_platform())
    payload = deepcopy(base_payload())
    mutate(power, platform, payload)
    root = write_model(tmp_path, power, platform, payload)
    findings, _ = check_power(load_power_model(root))
    return {finding.check for finding in findings if finding.status == "FAIL"}


def test_the_base_model_passes_every_check(tmp_path):
    assert failed(tmp_path, lambda power, platform, payload: None) == set()


def test_voltage_drop_over_the_continuous_limit_is_a_failure(tmp_path):
    def mutate(power, platform, payload):
        # 0.3 % of 28 V is 0.084 V; the continuous drop is 0.180 V, the peak drop 0.480 V
        # against a 4 % limit, so only the continuous case fails.
        power["declared_rules"]["continuous_voltage_drop_pct"] = 0.3

    assert failed(tmp_path, mutate) == {"POWER-CONTINUOUS"}


def test_voltage_drop_over_the_peak_limit_is_a_failure(tmp_path):
    def mutate(power, platform, payload):
        # 1.5 % of 28 V is 0.42 V; the peak drop is 0.480 V and the continuous drop 0.180 V
        # against a 2 % limit, so only the peak case fails.
        power["declared_rules"]["peak_voltage_drop_pct"] = 1.5

    assert failed(tmp_path, mutate) == {"POWER-PEAK"}


def test_conductor_too_small_for_the_current_is_a_failure(tmp_path):
    def mutate(power, platform, payload):
        power["harnesses"][0]["conductor_cross_section_mm2"] = 0.5

    assert "POWER-AMPACITY" in failed(tmp_path, mutate)


def test_breaker_below_the_required_rating_is_a_failure(tmp_path):
    def mutate(power, platform, payload):
        power["protection"]["rating_a"] = 10

    assert failed(tmp_path, mutate) == {"POWER-BREAKER"}


def test_bus_overload_is_a_failure(tmp_path):
    def mutate(power, platform, payload):
        platform["electrical"]["existing_continuous_load_w"] = 2950

    assert failed(tmp_path, mutate) == {"POWER-BUS"}


def test_currents_follow_the_declared_demand(tmp_path):
    root = write_model(tmp_path, base_power(), base_platform(), base_payload())
    _, circuits = check_power(load_power_model(root))
    circuit = circuits[0]
    assert circuit.continuous_current_a == 150 / 28
    assert circuit.peak_current_a == 400 / 28
    assert circuit.ampacity_a == 2.5 * 8.0


# --------------------------------------------------------------------------- #
# The repository model and its evidence
# --------------------------------------------------------------------------- #


def test_repository_power_analysis_has_no_failed_check():
    model = load_power_model(REPO_ROOT)
    findings, _ = check_power(model)
    failures = [finding for finding in findings if finding.status == "FAIL"]
    assert failures == [], [finding.message for finding in failures]


def test_repository_power_evidence_is_up_to_date():
    model = load_power_model(REPO_ROOT)
    findings, circuits = check_power(model)
    for name, content in generated_files(model, findings, circuits).items():
        path = Path(REPO_ROOT) / EVIDENCE_DIR / name
        assert path.exists(), f"{name} is missing"
        assert path.read_text(encoding="utf-8") == content, f"{name} is out of date"


def test_open_items_are_reported_in_the_evidence():
    model = load_power_model(REPO_ROOT)
    findings, circuits = check_power(model)
    checks = generated_files(model, findings, circuits)["checks.json"]
    assert "inrush" in checks.lower()
