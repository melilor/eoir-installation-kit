"""Mass and balance checks, one test per rule, plus the repository model."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

from tools.mass import (
    EVIDENCE_DIR,
    check_mass,
    generated_files,
    load_mass_model,
)
from tools.model import REPO_ROOT


def base_platform() -> dict:
    return {
        "mass_and_inertia": {
            "mtow_kg": 2250,
            "empty_mass_kg": 1350,
            "empty_cg_mm_aft_of_datum": 3020,
            "cg_range_mm_aft_of_datum": {"forward": 2900, "aft": 3150},
        }
    }


def base_payload() -> dict:
    return {
        "mass_and_inertia": {
            "mass_kg": 45,
            "cg_offset_mm": {"x": 0},
            "cg_envelope_mm": {"x": 150},
        }
    }


def base_mass() -> dict:
    return {
        "revision": "T",
        "date": "2026-01-01",
        "units": "kg",
        "declared_rules": {"kit_mass_target_kg": 15.0, "component_mass_tolerance_pct": 5.0},
        "installation": {
            "kit_station_mm_aft_of_datum": 2350,
            "payload_station_mm_aft_of_datum": 2350,
        },
        "components": [
            {"id": "CMP-01", "mass_kg": 8.0, "source": "DECLARED"},
            {"id": "CMP-02", "mass_kg": 5.6, "source": "DECLARED"},
        ],
        "configurations": [
            {
                "id": "CFG-01",
                "description": "Forward CG limit",
                "payload": "installed",
                "payload_cg_offset_mm": -150,
                "kit_mass_factor": 1.05,
            },
            {
                "id": "CFG-02",
                "description": "Nominal",
                "payload": "installed",
                "payload_cg_offset_mm": 0,
                "kit_mass_factor": 1.0,
            },
            {
                "id": "CFG-03",
                "description": "Payload removed",
                "payload": "removed",
                "payload_cg_offset_mm": 0,
                "kit_mass_factor": 1.0,
            },
        ],
    }


def write_model(tmp_path: Path, mass: dict, platform: dict, payload: dict) -> Path:
    (tmp_path / "model" / "interfaces").mkdir(parents=True, exist_ok=True)
    (tmp_path / "model" / "mass.yaml").write_text(yaml.safe_dump(mass), encoding="utf-8")
    (tmp_path / "model" / "interfaces" / "icd_platform.yaml").write_text(
        yaml.safe_dump(platform), encoding="utf-8"
    )
    (tmp_path / "model" / "interfaces" / "icd_payload.yaml").write_text(
        yaml.safe_dump(payload), encoding="utf-8"
    )
    return tmp_path


def findings_for(tmp_path: Path, mutate) -> list:
    mass = deepcopy(base_mass())
    platform = deepcopy(base_platform())
    payload = deepcopy(base_payload())
    mutate(mass, platform, payload)
    root = write_model(tmp_path, mass, platform, payload)
    findings, _ = check_mass(load_mass_model(root))
    return findings


def failed(findings) -> set[str]:
    return {finding.check for finding in findings if finding.status == "FAIL"}


def test_the_base_model_passes_every_check(tmp_path):
    findings = findings_for(tmp_path, lambda mass, platform, payload: None)
    assert failed(findings) == set()


def test_kit_mass_above_the_target_is_a_failure(tmp_path):
    def mutate(mass, platform, payload):
        mass["declared_rules"]["kit_mass_target_kg"] = 10.0

    assert failed(findings_for(tmp_path, mutate)) == {"MASS-KIT"}


def test_payload_cg_beyond_the_envelope_is_a_failure(tmp_path):
    def mutate(mass, platform, payload):
        payload["mass_and_inertia"]["cg_envelope_mm"]["x"] = 100

    assert failed(findings_for(tmp_path, mutate)) == {"MASS-PAYLOAD"}


def test_cg_forward_of_the_certified_range_is_a_failure(tmp_path):
    def mutate(mass, platform, payload):
        platform["mass_and_inertia"]["empty_cg_mm_aft_of_datum"] = 2900
        mass["installation"]["kit_station_mm_aft_of_datum"] = 1000
        mass["installation"]["payload_station_mm_aft_of_datum"] = 1000

    assert failed(findings_for(tmp_path, mutate)) == {"MASS-BALANCE"}


def test_total_mass_above_mtow_is_a_failure(tmp_path):
    def mutate(mass, platform, payload):
        platform["mass_and_inertia"]["mtow_kg"] = 1400

    assert failed(findings_for(tmp_path, mutate)) == {"MASS-MTOW"}


def test_balancing_accounts_for_the_payload_offset(tmp_path):
    findings = findings_for(tmp_path, lambda mass, platform, payload: None)
    balances = check_mass(load_mass_model(write_model(
        tmp_path, base_mass(), base_platform(), base_payload()
    )))[1]
    forward = next(balance for balance in balances if balance.configuration.id == "CFG-01")
    nominal = next(balance for balance in balances if balance.configuration.id == "CFG-02")
    assert forward.cg_mm < nominal.cg_mm  # a forward payload CG moves the platform CG forward
    assert findings  # the checks ran


# --------------------------------------------------------------------------- #
# The repository model and its evidence
# --------------------------------------------------------------------------- #


def test_repository_mass_analysis_has_no_failed_check():
    findings, _ = check_mass(load_mass_model(REPO_ROOT))
    failures = [finding for finding in findings if finding.status == "FAIL"]
    assert failures == [], [finding.message for finding in failures]


def test_repository_mass_evidence_is_up_to_date():
    model = load_mass_model(REPO_ROOT)
    findings, balances = check_mass(model)
    for name, content in generated_files(model, findings, balances).items():
        path = Path(REPO_ROOT) / EVIDENCE_DIR / name
        assert path.exists(), f"{name} is missing"
        assert path.read_text(encoding="utf-8") == content, f"{name} is out of date"


def test_kit_mass_is_the_sum_of_the_component_masses():
    model = load_mass_model(REPO_ROOT)
    assert model.kit_mass_kg == sum(component.mass_kg for component in model.components)
