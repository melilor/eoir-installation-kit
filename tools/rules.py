"""Validation rules for the model.

Every rule returns a :class:`Finding` with a stable identifier, so a failure in
CI points at one line of this file. The rules are the contract of the model:

* no requirement without a source;
* no requirement without an architecture allocation;
* no requirement without a verification case;
* no verification case without an evidence record;
* no evidence claim without the artifact it points at;
* no declared assumption silently promoted to a verified statement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .model import ArchitectureElement, Model, REPO_ROOT

#: Allowed methods for a verification case.
METHODS = frozenset({"analysis", "simulation", "test", "inspection", "demonstration", "review"})

#: Allowed states of a verification case.
EVIDENCE_STATUSES = frozenset({"PASS", "WARN", "FAIL", "LIMITATION", "BLOCKED", "FUTURE"})

#: States that must point at an artifact that exists in the repository.
STATUS_REQUIRING_ARTIFACT = frozenset({"PASS", "WARN"})

#: States that must carry a note explaining the gap.
STATUS_REQUIRING_NOTE = frozenset({"FAIL", "LIMITATION", "BLOCKED"})

#: Allowed states of a declared assumption.
ASSUMPTION_STATUSES = frozenset({"OPEN", "CLOSED", "REJECTED"})

#: Allowed states of a compliance document.
DOCUMENT_STATUSES = frozenset({"PLANNED", "DRAFT", "OUTLINE", "GENERATED", "ISSUED"})

#: Allowed types of a compliance document.
DOCUMENT_TYPES = frozenset({"drawing", "analysis", "test", "ica", "checklist", "manual"})

#: Allowed sources of a declared component mass.
MASS_SOURCES = frozenset({"DECLARED", "DERIVED"})

#: Allowed states, outcomes and criterion effects of the change classification.
CLASSIFICATION_STATUSES = frozenset({"OPEN", "CLOSED"})
CLASSIFICATION_OUTCOMES = frozenset({"MINOR", "MAJOR"})
CRITERION_EFFECTS = frozenset({"YES", "NO", "OPEN"})

#: A citation is ``STD <reference>`` or ``ASM <assumption id>``; several
#: citations can be chained with a semicolon.
CITATION = re.compile(r"^(STD|ASM)\s+(.+)$")


@dataclass(frozen=True)
class Finding:
    """One result of the validation."""

    rule: str
    severity: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.severity.upper():7} {self.rule}: {self.message}"


def _error(rule: str, message: str) -> Finding:
    return Finding(rule, "error", message)


def _warning(rule: str, message: str) -> Finding:
    return Finding(rule, "warning", message)


def citations(ref: str) -> list[tuple[str, str]]:
    """Split a cite string into ``(kind, value)`` pairs."""
    pairs: list[tuple[str, str]] = []
    for raw in ref.split(";"):
        piece = raw.strip()
        if not piece:
            continue
        match = CITATION.match(piece)
        if match:
            pairs.append((match.group(1), match.group(2).strip()))
        else:
            pairs.append(("UNKNOWN", piece))
    return pairs


def check_model(model: Model, root: Path | None = None) -> list[Finding]:
    """Run every rule and return the findings, errors first."""
    base = Path(root) if root else REPO_ROOT
    findings: list[Finding] = []

    findings += _check_doorstop(model)
    findings += _check_citations(model)
    findings += _check_architecture(model)
    findings += _check_verification(model, base)
    findings += _check_assumptions(model, base)
    findings += _check_compliance(model, base)
    findings += _check_masses(model)
    findings += _check_classification(model)
    findings += _check_identifiers(model)

    return sorted(findings, key=lambda finding: (finding.severity != "error", finding.rule))


def _check_doorstop(model: Model) -> list[Finding]:
    return [_error("DOORSTOP", issue) for issue in model.doorstop_issues]


def _check_citations(model: Model) -> list[Finding]:
    findings: list[Finding] = []
    for requirement in model.requirements.values():
        if not requirement.active:
            continue
        if not requirement.text.strip():
            findings.append(_error("REQ-TEXT", f"{requirement.uid}: requirement text is empty"))
        if not requirement.ref.strip():
            findings.append(_error("REQ-SOURCE", f"{requirement.uid}: no source (ref is empty)"))
            continue
        for kind, value in citations(requirement.ref):
            if kind == "UNKNOWN":
                findings.append(
                    _error("REQ-SOURCE", f"{requirement.uid}: citation '{value}' is neither STD nor ASM")
                )
            elif kind == "ASM" and value not in model.assumptions:
                findings.append(
                    _error("REQ-SOURCE", f"{requirement.uid}: unknown assumption '{value}'")
                )
    return findings


def _check_architecture(model: Model) -> list[Finding]:
    findings: list[Finding] = []
    known_requirements = set(model.requirements)
    elements = model.functions + model.components + model.interfaces

    for element in model.functions + model.components + model.interfaces:
        if not element.requirements:
            findings.append(_error("ARCH-REQ", f"{element.id}: no requirement allocated"))
        for uid in element.requirements:
            if uid not in known_requirements:
                findings.append(_error("ARCH-REQ", f"{element.id}: unknown requirement '{uid}'"))

    for requirement in model.requirements.values():
        if not requirement.active:
            continue
        if not any(requirement.uid in component.requirements for component in model.components):
            findings.append(
                _error("ARCH-ALLOC", f"{requirement.uid}: not allocated to any component")
            )

    realized = {function_id for component in model.components for function_id in component.realizes}
    for function in model.functions:
        if function.id not in realized:
            findings.append(
                _error("ARCH-REALIZES", f"{function.id}: no component realises this function")
            )
    known_functions = {function.id for function in model.functions}
    for component in model.components:
        if not component.realizes:
            findings.append(_error("ARCH-REALIZES", f"{component.id}: realises no function"))
        for function_id in component.realizes:
            if function_id not in known_functions:
                findings.append(
                    _error("ARCH-REALIZES", f"{component.id}: unknown function '{function_id}'")
                )

    known_components = {component.id for component in model.components}
    endpoints = known_components | set(model.externals)
    for interface in model.interfaces:
        for role, endpoint in (("from", interface.source), ("to", interface.target)):
            if endpoint not in endpoints:
                findings.append(
                    _error("ARCH-IFACE", f"{interface.id}: {role} endpoint '{endpoint}' is unknown")
                )
        if interface.source and interface.source == interface.target:
            findings.append(_error("ARCH-IFACE", f"{interface.id}: both endpoints are the same"))

    return findings


def _check_verification(model: Model, root: Path) -> list[Finding]:
    findings: list[Finding] = []

    for requirement in model.requirements.values():
        if not requirement.active:
            continue
        if not model.verifications_of(requirement.uid):
            findings.append(_error("VER-COVER", f"{requirement.uid}: no verification case"))

    for case in model.verifications.values():
        if not case.links:
            findings.append(_error("VER-LINK", f"{case.uid}: links no requirement"))
        for uid in case.links:
            if uid not in model.requirements:
                findings.append(_error("VER-LINK", f"{case.uid}: unknown requirement '{uid}'"))
        record = model.evidence_of(case.uid)
        if record is None:
            findings.append(_error("VER-EVIDENCE", f"{case.uid}: no evidence record"))
            continue
        findings += _check_evidence_record(record, root)

    for uid in model.evidence:
        if uid not in model.verifications:
            findings.append(_error("VER-EVIDENCE", f"{uid}: evidence record for an unknown case"))

    return findings


def _check_evidence_record(record, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    if record.method not in METHODS:
        findings.append(_error("EVIDENCE-METHOD", f"{record.verification}: unknown method '{record.method}'"))
    if record.status not in EVIDENCE_STATUSES:
        findings.append(_error("EVIDENCE-STATUS", f"{record.verification}: unknown status '{record.status}'"))
        return findings
    if record.status in STATUS_REQUIRING_ARTIFACT:
        if not record.artifact:
            findings.append(
                _error("EVIDENCE-ARTIFACT", f"{record.verification}: status {record.status} without an artifact")
            )
        elif not (root / record.artifact).exists():
            findings.append(
                _error("EVIDENCE-ARTIFACT", f"{record.verification}: artifact '{record.artifact}' does not exist")
            )
    if record.status == "FUTURE" and not (record.plan or "").strip():
        findings.append(_error("EVIDENCE-PLAN", f"{record.verification}: status FUTURE without a plan"))
    if record.status in STATUS_REQUIRING_NOTE and not (record.note or "").strip():
        findings.append(_error("EVIDENCE-NOTE", f"{record.verification}: status {record.status} without a note"))
    return findings


def _check_assumptions(model: Model, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for assumption in model.assumptions.values():
        if assumption.status not in ASSUMPTION_STATUSES:
            findings.append(
                _error("ASM-STATUS", f"{assumption.id}: unknown status '{assumption.status}'")
            )
        if not assumption.statement.strip():
            findings.append(_error("ASM-TEXT", f"{assumption.id}: empty statement"))
        if assumption.data_file and not (root / assumption.data_file).exists():
            findings.append(
                _error(
                    "ASM-FILE",
                    f"{assumption.id}: declared data file '{assumption.data_file}' does not exist",
                )
            )

    for requirement in model.requirements.values():
        if not requirement.active:
            continue
        cases = model.verifications_of(requirement.uid)
        if not cases:
            continue
        statuses = {model.evidence_of(case.uid).status for case in cases if model.evidence_of(case.uid)}
        if not statuses & STATUS_REQUIRING_ARTIFACT:
            continue
        for kind, value in citations(requirement.ref):
            if kind == "ASM" and model.assumptions.get(value, None) and model.assumptions[value].status == "OPEN":
                findings.append(
                    _warning(
                        "ASM-OPEN",
                        f"{requirement.uid}: verified against the open assumption {value}",
                    )
                )
    return findings


def _check_compliance(model: Model, root: Path) -> list[Finding]:
    """Every requirement is covered by exactly one document, and the register is sound."""
    findings: list[Finding] = []
    known = set(model.requirements)
    coverage: dict[str, list[str]] = {}

    for document in model.documents:
        if document.status not in DOCUMENT_STATUSES:
            findings.append(
                _error("COMPLIANCE-REF", f"{document.id}: unknown status '{document.status}'")
            )
        if document.type not in DOCUMENT_TYPES:
            findings.append(_error("COMPLIANCE-REF", f"{document.id}: unknown type '{document.type}'"))
        if not document.covers:
            findings.append(_error("COMPLIANCE-REF", f"{document.id}: covers no requirement"))
        for uid in document.covers:
            if uid not in known:
                findings.append(
                    _error("COMPLIANCE-REF", f"{document.id}: unknown requirement '{uid}'")
                )
            coverage.setdefault(uid, []).append(document.id)
        if document.path and not (root / document.path).exists():
            findings.append(
                _error(
                    "COMPLIANCE-FILE",
                    f"{document.id}: declared document '{document.path}' does not exist",
                )
            )

    document_ids = [document.id for document in model.documents]
    for document_id in sorted({value for value in document_ids if document_ids.count(value) > 1}):
        findings.append(_error("COMPLIANCE-REF", f"{document_id}: duplicate document id"))

    for requirement in model.requirements.values():
        if not requirement.active:
            continue
        owners = coverage.get(requirement.uid, [])
        if not owners:
            findings.append(
                _error("COMPLIANCE-COVERAGE", f"{requirement.uid}: no compliance document")
            )
        elif len(owners) > 1:
            findings.append(
                _error(
                    "COMPLIANCE-COVERAGE",
                    f"{requirement.uid}: covered by {', '.join(sorted(owners))}",
                )
            )
    return findings


def _check_masses(model: Model) -> list[Finding]:
    """Every component has exactly one declared mass, and the mass is positive."""
    findings: list[Finding] = []
    known = {component.id for component in model.components}
    for component in model.components:
        mass = model.masses.get(component.id)
        if mass is None:
            findings.append(
                _error("MASS-COVERAGE", f"{component.id}: no declared mass")
            )
            continue
        if mass.mass_kg <= 0:
            findings.append(
                _error("MASS-COVERAGE", f"{component.id}: mass {mass.mass_kg:g} kg is not positive")
            )
        if mass.source not in MASS_SOURCES:
            findings.append(
                _error("MASS-COVERAGE", f"{component.id}: unknown source '{mass.source}'")
            )
    for component_id in model.masses:
        if component_id not in known:
            findings.append(
                _error("MASS-COVERAGE", f"{component_id}: mass for an unknown component")
            )
    return findings


def _check_classification(model: Model) -> list[Finding]:
    """The change classification is complete enough to be argued."""
    classification = model.classification
    if classification is None:
        return [_error("CLASSIFICATION", "no change classification recorded")]
    findings: list[Finding] = []
    if classification.status not in CLASSIFICATION_STATUSES:
        findings.append(
            _error("CLASSIFICATION", f"unknown status '{classification.status}'")
        )
    if classification.proposed not in CLASSIFICATION_OUTCOMES:
        findings.append(
            _error("CLASSIFICATION", f"unknown proposed outcome '{classification.proposed}'")
        )
    if not classification.criteria:
        findings.append(_error("CLASSIFICATION", "no criterion assessed"))
    for criterion in classification.criteria:
        if criterion.effect not in CRITERION_EFFECTS:
            findings.append(
                _error(
                    "CLASSIFICATION",
                    f"{criterion.criterion}: unknown effect '{criterion.effect}'",
                )
            )
        if not criterion.rationale.strip():
            findings.append(
                _error("CLASSIFICATION", f"{criterion.criterion}: no rationale")
            )
    if classification.proposed == "MAJOR" and not classification.approval_route.strip():
        findings.append(_error("CLASSIFICATION", "major change without an approval route"))
    return findings


def _check_identifiers(model: Model) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[str, str] = {}
    groups = (
        ("function", model.functions),
        ("component", model.components),
        ("interface", model.interfaces),
    )
    for kind, elements in groups:
        for element in elements:
            owner = seen.get(element.id)
            if owner is not None:
                findings.append(
                    _error("ID-DUPLICATE", f"{element.id}: used by {owner} and {kind}")
                )
            else:
                seen[element.id] = kind
    for uid in model.requirements:
        if uid in seen:
            findings.append(_error("ID-DUPLICATE", f"{uid}: used by a requirement and a {seen[uid]}"))
        seen[uid] = "requirement"
    for uid in model.verifications:
        if uid in seen:
            findings.append(_error("ID-DUPLICATE", f"{uid}: used by {seen[uid]} and a verification case"))
        seen[uid] = "verification"
    for aid in model.assumptions:
        if aid in seen:
            findings.append(_error("ID-DUPLICATE", f"{aid}: used by {seen[aid]} and an assumption"))
        seen[aid] = "assumption"
    return findings
