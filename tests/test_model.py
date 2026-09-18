"""Integration tests: the real model under model/ must be clean and published."""

from __future__ import annotations

from pathlib import Path

from tools.diagram import DOC_PATH as ARCHITECTURE_PATH, render_architecture
from tools.model import REPO_ROOT, load_model
from tools.rules import check_model
from tools.traceability import REPORT_PATH, render_report


def test_repository_model_has_no_errors():
    model = load_model(REPO_ROOT)
    findings = [finding for finding in check_model(model, REPO_ROOT) if finding.severity == "error"]
    assert findings == []


def test_every_requirement_has_a_source_and_a_verification():
    model = load_model(REPO_ROOT)
    for uid, requirement in model.requirements.items():
        assert requirement.ref.strip(), f"{uid} has no source"
        assert model.verifications_of(uid), f"{uid} has no verification case"


def test_every_verification_case_has_an_evidence_record():
    model = load_model(REPO_ROOT)
    for uid in model.verifications:
        assert model.evidence_of(uid) is not None, f"{uid} has no evidence record"


def test_traceability_matrix_is_up_to_date():
    model = load_model(REPO_ROOT)
    current = (REPO_ROOT / REPORT_PATH).read_text(encoding="utf-8")
    assert current == render_report(model), (
        "docs/traceability.md is out of date: run python -m tools.traceability report"
    )


def test_report_lists_every_requirement():
    model = load_model(REPO_ROOT)
    report = render_report(model)
    for uid, requirement in model.requirements.items():
        assert uid in report
        assert requirement.header in report


def test_architecture_document_is_up_to_date():
    model = load_model(REPO_ROOT)
    current = (REPO_ROOT / ARCHITECTURE_PATH).read_text(encoding="utf-8")
    assert current == render_architecture(model), (
        "docs/architecture.md is out of date: run python -m tools.diagram"
    )


def test_architecture_document_lists_every_element():
    model = load_model(REPO_ROOT)
    document = render_architecture(model)
    for external in model.externals:
        assert external in document, external
    for component in model.components:
        assert component.id in document
        assert component.name in document
    for interface in model.interfaces:
        assert interface.name in document
    for function in model.functions:
        assert function.id in document


def test_model_paths_exist():
    for relative in (
        "model/requirements",
        "model/verification",
        "model/architecture/architecture.yaml",
        "model/interfaces/icd_payload.yaml",
        "model/interfaces/icd_platform.yaml",
        "model/evidence.yaml",
        "model/assumptions.yaml",
    ):
        assert (Path(REPO_ROOT) / relative).exists(), relative
