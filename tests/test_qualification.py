"""Qualification plan checks: one test per rule, plus the repository plan.

The plan consumes the whole model — the requirements it has to cover, the
components it has to place in a zone, the compliance register it has to be part
of — so the tests copy ``model/`` into a temporary directory and break one
declaration at a time.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from tools.model import REPO_ROOT
from tools.qualification import (
    check_qualification,
    cited_sections,
    generated_files,
    load_qualification_model,
)

MODEL_DIR = REPO_ROOT / "model"
PLAN = Path("docs/qualification-plan.md")


def copy_model(tmp_path: Path) -> Path:
    """The model, plus the generated plan the register points at."""
    shutil.copytree(MODEL_DIR, tmp_path / "model")
    plan = tmp_path / PLAN
    plan.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / PLAN, plan)
    return tmp_path


def edit(root: Path, relative: str, mutate) -> None:
    path = root / relative
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def section(document: dict, number: str) -> dict:
    return next(entry for entry in document["sections"] if str(entry["section"]) == number)


def failed(tmp_path: Path, mutate) -> set[str]:
    root = copy_model(tmp_path / "failed")
    mutate(root)
    findings, _ = check_qualification(load_qualification_model(root), root)
    return {finding.check for finding in findings if finding.status == "FAIL"}


def failing_subjects(tmp_path: Path, mutate) -> set[str]:
    root = copy_model(tmp_path / "subjects")
    mutate(root)
    findings, _ = check_qualification(load_qualification_model(root), root)
    return {finding.subject for finding in findings if finding.status == "FAIL"}


# --------------------------------------------------------------------------- #
# One test per rule
# --------------------------------------------------------------------------- #


def test_the_base_plan_passes_every_check(tmp_path):
    assert failed(tmp_path, lambda root: None) == set()


def test_a_cited_section_missing_from_the_plan_is_a_failure(tmp_path):
    def mutate(root):
        edit(
            root,
            "model/qualification.yaml",
            lambda plan: plan["sections"].remove(section(plan, "16")),
        )

    assert failed(tmp_path, mutate) == {"QUAL-SECTION-COVERAGE"}


def test_an_entry_without_a_basis_is_a_failure(tmp_path):
    def mutate(root):
        def blank(plan):
            section(plan, "16")["basis"] = ""

        edit(root, "model/qualification.yaml", blank)

    assert failed(tmp_path, mutate) == {"QUAL-SECTION"}
    assert failing_subjects(tmp_path, mutate) == {"16"}


def test_an_entry_without_a_category_or_an_open_item_is_a_failure(tmp_path):
    def mutate(root):
        def blank(plan):
            for selection in section(plan, "20")["zones"]:
                selection["category"] = None
                selection["open_on"] = None

        edit(root, "model/qualification.yaml", blank)

    assert failed(tmp_path, mutate) == {"QUAL-SECTION"}
    assert failing_subjects(tmp_path, mutate) == {"20"}


def test_a_test_entry_without_an_article_is_a_failure(tmp_path):
    def mutate(root):
        def blank(plan):
            section(plan, "22")["article"] = None

        edit(root, "model/qualification.yaml", blank)

    assert failing_subjects(tmp_path, mutate) == {"22"}


def test_a_planned_entry_without_a_limitation_is_a_failure(tmp_path):
    def mutate(root):
        def blank(plan):
            entry = section(plan, "24")
            entry["status"] = "PLANNED"
            entry["limitation"] = None

        edit(root, "model/qualification.yaml", blank)

    assert failing_subjects(tmp_path, mutate) == {"24"}


def test_an_open_entry_without_an_open_item_is_a_failure(tmp_path):
    def mutate(root):
        def blank(plan):
            entry = section(plan, "15")
            entry["open_on"] = None
            for selection in entry["zones"]:
                selection["open_on"] = None

        edit(root, "model/qualification.yaml", blank)

    assert failing_subjects(tmp_path, mutate) == {"15"}


def test_an_unknown_method_is_a_failure(tmp_path):
    def mutate(root):
        def blank(plan):
            section(plan, "19")["method"] = "MAYBE"

        edit(root, "model/qualification.yaml", blank)

    assert failing_subjects(tmp_path, mutate) == {"19"}


def test_an_unknown_status_is_a_failure(tmp_path):
    def mutate(root):
        def blank(plan):
            section(plan, "19")["status"] = "PROBABLY"

        edit(root, "model/qualification.yaml", blank)

    assert failing_subjects(tmp_path, mutate) == {"19"}


def test_a_component_without_a_zone_is_a_failure(tmp_path):
    def mutate(root):
        def drop(plan):
            plan["components"] = [
                entry for entry in plan["components"] if entry["component"] != "CMP-07"
            ]

        edit(root, "model/qualification.yaml", drop)

    assert failed(tmp_path, mutate) == {"QUAL-COMPONENT-ZONE"}
    assert failing_subjects(tmp_path, mutate) == {"CMP-07"}


def test_an_entry_pointing_at_an_unknown_zone_is_a_failure(tmp_path):
    def mutate(root):
        def rename(plan):
            section(plan, "10")["zones"][0]["id"] = "Z-99"

        edit(root, "model/qualification.yaml", rename)

    assert failing_subjects(tmp_path, mutate) == {"10"}


def test_a_zone_with_no_applicable_section_is_a_failure(tmp_path):
    def mutate(root):
        def blank(plan):
            plan["zones"][0]["qualification_required"] = True
            for entry in plan["sections"]:
                for selection in entry["zones"]:
                    if selection["id"] == "Z-01":
                        selection["category"] = "not-applicable"
                        selection["open_on"] = None

        edit(root, "model/qualification.yaml", blank)

    assert failed(tmp_path, mutate) == {"QUAL-ZONE-COVERAGE"}
    assert failing_subjects(tmp_path, mutate) == {"Z-01"}


def test_a_zone_that_needs_no_qualification_needs_a_reason(tmp_path):
    def mutate(root):
        def blank(plan):
            zone = next(entry for entry in plan["zones"] if entry["id"] == "Z-03")
            zone["reason"] = ""

        edit(root, "model/qualification.yaml", blank)

    assert failing_subjects(tmp_path, mutate) == {"Z-03"}


def test_a_protection_mean_without_a_state_is_a_failure(tmp_path):
    def mutate(root):
        def blank(plan):
            plan["protection_preservation"][0]["status"] = "MAYBE"

        edit(root, "model/qualification.yaml", blank)

    assert failed(tmp_path, mutate) == {"QUAL-PROTECTION"}
    assert failing_subjects(tmp_path, mutate) == {"PP-01"}


def test_an_open_protection_mean_without_an_open_item_is_a_failure(tmp_path):
    def mutate(root):
        def blank(plan):
            plan["protection_preservation"][3]["open_on"] = None

        edit(root, "model/qualification.yaml", blank)

    assert failing_subjects(tmp_path, mutate) == {"PP-04"}


def test_a_functional_test_without_an_article_is_a_failure(tmp_path):
    def mutate(root):
        def blank(plan):
            plan["functional_tests"][0]["article"] = ""

        edit(root, "model/qualification.yaml", blank)

    assert failed(tmp_path, mutate) == {"QUAL-FUNCTIONAL-TEST"}


def test_the_register_pointing_elsewhere_is_a_failure(tmp_path):
    def mutate(root):
        def blank(register):
            for document in register["documents"]:
                if document["id"] == "TP-001":
                    document["path"] = "docs/somewhere-else.md"

        edit(root, "model/compliance.yaml", blank)

    assert failed(tmp_path, mutate) == {"QUAL-DOCUMENT"}


# --------------------------------------------------------------------------- #
# The arithmetic
# --------------------------------------------------------------------------- #


def test_every_cited_section_is_found_in_the_requirements():
    cited = cited_sections()
    assert set(cited) == {4, 6, 8, 11, 12, 13, 14, 16, 20, 21}
    assert cited[21] == "SYS014"
    assert cited[11] == "SYS033"


def test_the_repository_plan_passes_every_check():
    model = load_qualification_model()
    findings, _ = check_qualification(model)
    assert [finding.as_dict() for finding in findings if finding.status == "FAIL"] == []


def test_the_committed_plan_and_evidence_match_the_model():
    model = load_qualification_model()
    findings, detail = check_qualification(model)
    for name, content in generated_files(model, findings, detail).items():
        assert (REPO_ROOT / name).read_text(encoding="utf-8") == content


def test_no_category_is_claimed_without_a_declared_basis():
    """A category either has a basis in the model or it is not written down."""
    model = load_qualification_model()
    for entry in model.sections:
        for selection in entry.zones:
            if selection.category in (None, "not-applicable"):
                continue
            assert entry.basis.strip(), f"section {entry.section} claims {selection.category}"
            assert any(
                selection.category.split()[0] in " ".join(reference["statement"].split())
                for reference in model.references
            ) or selection.category in ("R or U", "D", "T", "Z"), (
                f"section {entry.section} claims {selection.category} with no public statement behind it"
            )


def test_what_needs_an_article_is_declared_as_a_limitation():
    model = load_qualification_model()
    planned = [entry for entry in model.sections if entry.status == "PLANNED"]
    assert planned
    for entry in planned:
        assert entry.article and entry.limitation, f"section {entry.section}"
    for test in model.functional_tests:
        assert test.limitation
