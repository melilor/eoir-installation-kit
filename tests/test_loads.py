"""Load path and strength checks, one test per rule, plus the repository model.

The model this tool consumes is spread over four files (the strength model, the
layout, the mass model and the two interface control files) and it reads the
clearance analysis as well, so the tests copy the repository model into a
temporary directory and change one declaration at a time. That way every test
exercises the real interactions instead of a hand-built stub.
"""

from __future__ import annotations

import shutil
from copy import deepcopy
from pathlib import Path

import yaml

from tools.loads import (
    build_resonance,
    check_loads,
    closed_form_reaction,
    compute_reactions,
    generated_files,
    load_loads_model,
)
from tools.model import REPO_ROOT

FILES = (
    "model/loads.yaml",
    "model/layout.yaml",
    "model/mass.yaml",
    "model/interfaces/icd_platform.yaml",
    "model/interfaces/icd_payload.yaml",
)


def copy_model(tmp_path: Path) -> Path:
    """A writable copy of the repository model, file by file."""
    for relative in FILES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / relative, target)
    return tmp_path


def edit(tmp_path: Path, relative: str, mutate) -> None:
    path = tmp_path / relative
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def failed(tmp_path: Path, mutate) -> set[str]:
    root = copy_model(tmp_path)
    mutate(root)
    findings, _ = check_loads(load_loads_model(root), root)
    return {finding.check for finding in findings if finding.status == "FAIL"}


# --------------------------------------------------------------------------- #
# One test per rule
# --------------------------------------------------------------------------- #


def test_the_base_model_passes_every_check(tmp_path):
    assert failed(tmp_path, lambda root: None) == set()


def test_a_reaction_above_the_hard_point_capability_is_a_failure(tmp_path):
    def mutate(root):
        edit(
            root,
            "model/interfaces/icd_platform.yaml",
            lambda platform: platform["attachment_provisions"]["load_capability_kn"].update(
                {"per_point_ultimate": 0.5}
            ),
        )

    assert failed(tmp_path, mutate) == {"LOADS-HARD-POINT"}


def test_a_case_without_its_factor_of_safety_is_a_failure(tmp_path):
    def mutate(root):
        edit(
            root,
            "model/loads.yaml",
            lambda loads: loads["declared_rules"].update({"factor_of_safety": 1.0}),
        )

    # Only the limit cases carry a required factor of safety.
    assert failed(tmp_path, mutate) == {"LOADS-FACTOR-OF-SAFETY"}
    root = copy_model(tmp_path / "check")
    edit(
        root,
        "model/loads.yaml",
        lambda loads: loads["declared_rules"].update({"factor_of_safety": 1.0}),
    )
    findings, detail = check_loads(load_loads_model(root), root)
    failing = {finding.subject for finding in findings if finding.status == "FAIL"}
    assert failing == {"LC-MAN-UP", "LC-MAN-DOWN"}
    assert detail["cases"]["LC-EML-FWD"]["factor"] == 1.0


def test_a_thinner_fitting_is_a_failure_at_the_critical_section(tmp_path):
    def mutate(root):
        edit(
            root,
            "model/loads.yaml",
            lambda loads: loads["sections"]["fitting"].update({"thickness_mm": 0.5}),
        )

    assert "LOADS-FITTING-NET-SECTION" in failed(tmp_path, mutate)


def test_a_bearing_allowable_below_the_bearing_stress_is_a_failure(tmp_path):
    def mutate(root):
        # A bearing rule of 1 % of Fty is 2.6 MPa; the worst case carries 4.8 MPa.
        edit(
            root,
            "model/loads.yaml",
            lambda loads: loads["declared_rules"].update({"bearing_allowable_ratio": 0.01}),
        )

    assert failed(tmp_path, mutate) == {"LOADS-BEARING"}


def test_a_fastener_too_small_for_the_shear_is_a_failure(tmp_path):
    def mutate(root):
        def shrink(loads):
            for material in loads["materials"]:
                if material["id"] == "MAT-02":
                    material["thread_stress_area_mm2"] = 0.5

        edit(root, "model/loads.yaml", shrink)

    assert "LOADS-BOLT" in failed(tmp_path, mutate)


def test_a_stiffer_frame_raises_the_frequency_estimate(tmp_path):
    root = copy_model(tmp_path)
    model = load_loads_model(root)
    baseline = build_resonance(model)

    def thicken(loads):
        loads["sections"]["frame_rail"].update({"height_mm": 80, "width_mm": 80})

    edit(root, "model/loads.yaml", thicken)
    stiffer = build_resonance(load_loads_model(root))

    assert stiffer.estimate_low_hz > baseline.estimate_low_hz
    assert stiffer.estimate_high_hz > baseline.estimate_high_hz
    # The interval never spans the factor of four of the two idealisations, because
    # the fitting brackets sit in series with the rails.
    for resonance in (baseline, stiffer):
        assert 1.0 < resonance.estimate_high_hz / resonance.estimate_low_hz < 4.0


def test_less_clearance_than_the_deflection_needs_is_a_failure(tmp_path):
    def mutate(root):
        # The tightest direction reaches 30 mm, so a requirement of 29.5 mm
        # leaves 0.5 mm against the 2.18 mm the kit moves under limit load.
        edit(
            root,
            "model/layout.yaml",
            lambda layout: layout["declared_rules"].update({"minimum_clearance_mm": 29.5}),
        )

    assert failed(tmp_path, mutate) == {"LOADS-DEFLECTION"}


def test_an_inverted_rotor_speed_range_is_a_failure(tmp_path):
    def mutate(root):
        edit(
            root,
            "model/interfaces/icd_platform.yaml",
            lambda platform: platform["structural_environment"].update(
                {"tail_rotor_rpm": {"lower": 3000, "upper": 2000}}
            ),
        )

    assert failed(tmp_path, mutate) == {"LOADS-RESONANCE-CRITERION"}


def test_a_harmonic_order_below_one_is_a_failure(tmp_path):
    def mutate(root):
        edit(
            root,
            "model/loads.yaml",
            lambda loads: loads["declared_rules"]["excitation_harmonics"].update({"main": [0]}),
        )

    assert failed(tmp_path, mutate) == {"LOADS-RESONANCE-CRITERION"}


# --------------------------------------------------------------------------- #
# The arithmetic
# --------------------------------------------------------------------------- #


def test_a_vertical_case_divides_equally_and_makes_no_couple(tmp_path):
    model = load_loads_model(copy_model(tmp_path))
    case = next(case for case in model.load_cases() if case.id == "LC-MAN-UP")
    reactions = compute_reactions(model, case)
    force = model.load_mass_kg * 3.5 * 1.5 * 9.80665

    assert len(reactions) == 4
    for reaction in reactions:
        assert reaction.force == (0.0, 0.0, force / 4)
        assert reaction.added_z == 0.0
    assert {round(reaction.magnitude, 6) for reaction in reactions} == {round(force / 4, 6)}


def test_a_horizontal_case_pitches_the_reaction_between_the_pairs(tmp_path):
    model = load_loads_model(copy_model(tmp_path))
    case = next(case for case in model.load_cases() if case.id == "LC-EML-FWD")
    reactions = compute_reactions(model, case)
    force = model.load_mass_kg * 4.0 * 9.80665
    couple = force * model.moment_arm_mm / (2 * model.spacing_mm[0])

    for reaction in reactions:
        # A forward inertia force acting below the attachment plane pushes the
        # forward fittings into the platform and pulls the aft ones off it.
        expected = -couple if reaction.x > 0 else couple
        assert abs(reaction.added_z - expected) < 1e-9
        assert abs(reaction.shear - force / 4) < 1e-9


def test_the_closed_form_and_the_general_solution_agree_on_the_components(tmp_path):
    model = load_loads_model(copy_model(tmp_path))
    for case in model.load_cases():
        reaction = max(compute_reactions(model, case), key=lambda item: item.magnitude)
        hand = closed_form_reaction(model, case)
        direct = (reaction.force[0], reaction.force[1], reaction.force[2] - reaction.added_z)
        assert abs(hand["direct"] - sum(component**2 for component in direct) ** 0.5) < 1e-9
        assert abs(hand["couple"] - abs(reaction.added_z)) < 1e-9


# --------------------------------------------------------------------------- #
# The repository model and its evidence
# --------------------------------------------------------------------------- #


def test_the_repository_model_passes_every_check():
    model = load_loads_model()
    findings, _ = check_loads(model)
    assert [finding.as_dict() for finding in findings if finding.status == "FAIL"] == []


def test_the_committed_evidence_matches_the_model():
    model = load_loads_model()
    findings, detail = check_loads(model)
    files = generated_files(model, findings, detail)
    for name, content in files.items():
        committed = (REPO_ROOT / "evidence" / "loads" / name).read_text(encoding="utf-8")
        assert committed == content


def test_the_repository_resonance_separation_is_not_demonstrated():
    resonance = build_resonance(load_loads_model())
    assert resonance.separation_demonstrated is False
    assert resonance.windows
    assert min(
        abs(resonance.estimate_low_hz - band.lower_hz)
        + abs(resonance.estimate_high_hz - band.upper_hz)
        for band in resonance.bands
    ) < 100
