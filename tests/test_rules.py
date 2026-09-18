"""Unit tests for the validation rules: one failing model per rule."""

from __future__ import annotations

from tools.model import ArchitectureElement, Assumption, Evidence, Requirement
from tools.rules import check_model

from conftest import build_model


def rules(model, root=None):
    return {finding.rule for finding in check_model(model, root)}


def test_valid_model_has_no_findings(model):
    assert check_model(model) == []


def test_doorstop_issues_are_errors():
    model = build_model(doorstop_issues=("DoorstopError: SYS001: broken",))
    assert "DOORSTOP" in rules(model)


def test_requirement_without_source_is_an_error():
    broken = Requirement(uid="SYS001", header="h", text="t", ref="", active=True, document="SYS")
    model = build_model(requirements={"SYS001": broken})
    assert "REQ-SOURCE" in rules(model)


def test_requirement_with_unknown_assumption_is_an_error():
    broken = Requirement(
        uid="SYS001", header="h", text="t", ref="ASM A-999", active=True, document="SYS"
    )
    model = build_model(requirements={"SYS001": broken})
    assert "REQ-SOURCE" in rules(model)


def test_requirement_with_free_text_citation_is_an_error():
    broken = Requirement(
        uid="SYS001", header="h", text="t", ref="see the manual", active=True, document="SYS"
    )
    model = build_model(requirements={"SYS001": broken})
    assert "REQ-SOURCE" in rules(model)


def test_requirement_without_architecture_allocation_is_an_error():
    other = ArchitectureElement(id="CMP-01", name="Frame", requirements=(), realizes=("FCT-01",))
    model = build_model(components=(other,))
    assert "ARCH-REQ" in rules(model) and "ARCH-ALLOC" in rules(model)


def test_component_with_unknown_requirement_is_an_error():
    other = ArchitectureElement(
        id="CMP-01", name="Frame", requirements=("SYS404",), realizes=("FCT-01",)
    )
    model = build_model(components=(other,))
    assert "ARCH-REQ" in rules(model)


def test_function_without_component_is_an_error():
    other = ArchitectureElement(
        id="CMP-01", name="Frame", requirements=("SYS001",), realizes=()
    )
    model = build_model(components=(other,))
    assert "ARCH-REALIZES" in rules(model)


def test_interface_with_unknown_endpoint_is_an_error():
    broken = ArchitectureElement(
        id="IF-01", name="Attachment", requirements=("SYS001",), source="CMP-01", target="EXT-GHOST"
    )
    model = build_model(interfaces=(broken,))
    assert "ARCH-IFACE" in rules(model)


def test_requirement_without_verification_is_an_error():
    model = build_model(verifications={}, evidence={})
    assert "VER-COVER" in rules(model)


def test_verification_without_evidence_record_is_an_error():
    model = build_model(evidence={})
    assert "VER-EVIDENCE" in rules(model)


def test_evidence_for_unknown_verification_is_an_error():
    model = build_model(
        evidence={
            "VER001": Evidence(verification="VER001", method="test", status="FUTURE", plan="x"),
            "VER999": Evidence(verification="VER999", method="test", status="FUTURE", plan="x"),
        }
    )
    assert "VER-EVIDENCE" in rules(model)


def test_pass_without_artifact_is_an_error(tmp_path):
    record = Evidence(verification="VER001", method="test", status="PASS")
    model = build_model(evidence={"VER001": record})
    assert "EVIDENCE-ARTIFACT" in rules(model, tmp_path)


def test_pass_with_missing_artifact_is_an_error(tmp_path):
    record = Evidence(
        verification="VER001", method="test", status="PASS", artifact="evidence/missing.md"
    )
    model = build_model(evidence={"VER001": record})
    assert "EVIDENCE-ARTIFACT" in rules(model, tmp_path)


def test_pass_with_existing_artifact_is_accepted(tmp_path):
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "report.md").write_text("result", encoding="utf-8")
    record = Evidence(
        verification="VER001", method="test", status="PASS", artifact="evidence/report.md"
    )
    model = build_model(evidence={"VER001": record})
    assert check_model(model, tmp_path) == []


def test_future_without_plan_is_an_error():
    record = Evidence(verification="VER001", method="test", status="FUTURE")
    model = build_model(evidence={"VER001": record})
    assert "EVIDENCE-PLAN" in rules(model)


def test_limitation_without_note_is_an_error():
    record = Evidence(verification="VER001", method="test", status="LIMITATION")
    model = build_model(evidence={"VER001": record})
    assert "EVIDENCE-NOTE" in rules(model)


def test_unknown_method_and_status_are_errors():
    bad_method = Evidence(verification="VER001", method="vibes", status="FUTURE", plan="x")
    assert "EVIDENCE-METHOD" in rules(build_model(evidence={"VER001": bad_method}))
    bad_status = Evidence(verification="VER001", method="test", status="MAYBE", plan="x")
    assert "EVIDENCE-STATUS" in rules(build_model(evidence={"VER001": bad_status}))


def test_unknown_assumption_status_is_an_error():
    assumption = Assumption(id="A-001", title="t", statement="s", status="PROBABLY")
    model = build_model(assumptions={"A-001": assumption})
    assert "ASM-STATUS" in rules(model)


def test_assumption_with_missing_data_file_is_an_error(tmp_path):
    assumption = Assumption(
        id="A-001", title="t", statement="s", status="OPEN", data_file="model/icd.yaml"
    )
    model = build_model(assumptions={"A-001": assumption})
    assert "ASM-FILE" in rules(model, tmp_path)


def test_assumption_with_existing_data_file_is_accepted(tmp_path):
    (tmp_path / "model").mkdir()
    (tmp_path / "model" / "icd.yaml").write_text("x: 1", encoding="utf-8")
    assumption = Assumption(
        id="A-001", title="t", statement="s", status="OPEN", data_file="model/icd.yaml"
    )
    model = build_model(assumptions={"A-001": assumption})
    assert check_model(model, tmp_path) == []


def test_evidence_against_an_open_assumption_is_a_warning(tmp_path):
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "report.md").write_text("result", encoding="utf-8")
    requirement = Requirement(
        uid="SYS001",
        header="h",
        text="t",
        ref="ASM A-001",
        active=True,
        document="SYS",
    )
    assumption = Assumption(id="A-001", title="t", statement="s", status="OPEN")
    record = Evidence(
        verification="VER001", method="test", status="PASS", artifact="evidence/report.md"
    )
    model = build_model(
        requirements={"SYS001": requirement},
        assumptions={"A-001": assumption},
        evidence={"VER001": record},
    )
    findings = check_model(model, tmp_path)
    assert [finding.rule for finding in findings] == ["ASM-OPEN"]
    assert findings[0].severity == "warning"


def test_duplicate_identifier_is_an_error():
    duplicate = ArchitectureElement(
        id="CMP-01", name="Other frame", requirements=("SYS001",), realizes=("FCT-01",)
    )
    model = build_model(components=(duplicate, duplicate))
    assert "ID-DUPLICATE" in rules(model)
