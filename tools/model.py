"""Load the installation kit model.

The model has four parts:

* ``model/requirements`` and ``model/verification``: Doorstop documents holding
  the system requirements (``SYS``) and the verification cases (``VER``, linked
  to their parent requirements through Doorstop links).
* ``model/architecture/architecture.yaml``: functions, components, interfaces
  and the external systems at the boundary.
* ``model/evidence.yaml``: one evidence record per verification case (method,
  status, artifact, plan).
* ``model/assumptions.yaml``: the declared assumptions and interface data that
  requirements point at with ``ASM A-00x``.

Doorstop is used for the requirement hierarchy and the requirement-to-
verification links. Two of its checks are filtered out on purpose:

* ``external reference not found`` -- the ``ref`` field carries a *citation*
  string (``STD ...`` or ``ASM A-00x``), not a file path or URL. Citations are
  checked by :mod:`tools.rules`.
* ``duplicate level`` -- the requirements documents are flat lists, so every
  item sits at level 1.

Everything else Doorstop reports (missing text, broken links, ...) is kept.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml
from doorstop.core.builder import build

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Doorstop issue fragments that are accepted by design (see module docstring).
ACCEPTED_DOORSTOP_ISSUES = (
    "external reference not found",
    "duplicate level",
)


@dataclass(frozen=True)
class Requirement:
    """A system requirement or a verification case."""

    uid: str
    header: str
    text: str
    ref: str
    active: bool
    links: tuple[str, ...] = ()
    document: str = ""


@dataclass(frozen=True)
class ArchitectureElement:
    """A function, a component or an interface of the installation kit."""

    id: str
    name: str
    requirements: tuple[str, ...] = ()
    realizes: tuple[str, ...] = ()
    source: str = ""
    target: str = ""


@dataclass(frozen=True)
class Evidence:
    """The state of one verification case."""

    verification: str
    method: str
    status: str
    artifact: str | None = None
    plan: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class Assumption:
    """A declared assumption or interface datum."""

    id: str
    title: str
    statement: str
    status: str
    data_file: str | None = None


@dataclass(frozen=True)
class Document:
    """A document that will show compliance with the requirements it covers."""

    id: str
    title: str
    type: str
    status: str
    covers: tuple[str, ...] = ()
    path: str | None = None
    plan: str | None = None


@dataclass(frozen=True)
class ComponentMass:
    """The declared mass of one architecture component."""

    id: str
    mass_kg: float
    source: str = ""


@dataclass(frozen=True)
class ClassificationCriterion:
    """One appreciable-effect criterion of the change classification."""

    criterion: str
    effect: str
    rationale: str


@dataclass(frozen=True)
class ChangeClassification:
    """The change classification of the installation (EASA Part 21 Subpart D)."""

    status: str
    proposed: str
    basis: str
    approval_route: str
    privileges: str
    criteria: tuple[ClassificationCriterion, ...] = ()
    open_items: tuple[str, ...] = ()


@dataclass(frozen=True)
class Model:
    """The whole model, loaded and ready to be checked."""

    requirements: dict[str, Requirement]
    verifications: dict[str, Requirement]
    functions: tuple[ArchitectureElement, ...]
    components: tuple[ArchitectureElement, ...]
    interfaces: tuple[ArchitectureElement, ...]
    externals: tuple[str, ...]
    evidence: dict[str, Evidence]
    assumptions: dict[str, Assumption]
    doorstop_issues: tuple[str, ...] = ()
    documents: tuple[Document, ...] = ()
    classification: ChangeClassification | None = None
    masses: dict[str, ComponentMass] = field(default_factory=dict)

    def verifications_of(self, requirement_uid: str) -> tuple[Requirement, ...]:
        """Return the verification cases linked to a requirement."""
        return tuple(
            case
            for case in self.verifications.values()
            if requirement_uid in case.links
        )

    def elements_of(self, requirement_uid: str) -> tuple[ArchitectureElement, ...]:
        """Return the functions, components and interfaces owning a requirement."""
        return tuple(
            element
            for element in self.functions + self.components + self.interfaces
            if requirement_uid in element.requirements
        )

    def evidence_of(self, verification_uid: str) -> Evidence | None:
        """Return the evidence record of a verification case."""
        return self.evidence.get(verification_uid)


def _requirement_from_item(item: Any) -> Requirement:
    links: Iterable[Any] = item.links or ()
    return Requirement(
        uid=str(item.uid),
        header=item.header or "",
        text=item.text or "",
        ref=item.ref or "",
        active=bool(item.active),
        links=tuple(str(link) for link in links),
        document=str(item.document.prefix) if item.document else "",
    )


def _load_doorstop(root: Path) -> tuple[dict[str, Requirement], dict[str, Requirement], list[str]]:
    tree = build(root=str(root))
    requirements: dict[str, Requirement] = {}
    verifications: dict[str, Requirement] = {}
    for document in tree.documents:
        for item in document.items:
            requirement = _requirement_from_item(item)
            if requirement.document == "SYS":
                requirements[requirement.uid] = requirement
            else:
                verifications[requirement.uid] = requirement
    issues = []
    for issue in tree.get_issues():
        message = f"{type(issue).__name__}: {issue}"
        if any(accepted in message for accepted in ACCEPTED_DOORSTOP_ISSUES):
            continue
        issues.append(message)
    return requirements, verifications, issues


def _elements(raw: Iterable[dict[str, Any]], key: str = "requirements") -> tuple[ArchitectureElement, ...]:
    return tuple(
        ArchitectureElement(
            id=entry["id"],
            name=entry.get("name", ""),
            requirements=tuple(entry.get(key, ())),
            realizes=tuple(entry.get("realizes", ())),
            source=entry.get("from", ""),
            target=entry.get("to", ""),
        )
        for entry in raw
    )


def _load_compliance(
    base: Path,
) -> tuple[tuple[Document, ...], ChangeClassification | None]:
    path = base / "model/compliance.yaml"
    if not path.exists():
        return (), None
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    documents = tuple(
        Document(
            id=entry["id"],
            title=entry.get("title", ""),
            type=entry.get("type", ""),
            status=entry.get("status", ""),
            covers=tuple(entry.get("covers", ())),
            path=entry.get("path"),
            plan=entry.get("plan"),
        )
        for entry in raw.get("documents", ())
    )
    classification_raw = raw.get("change_classification")
    classification = None
    if classification_raw:
        classification = ChangeClassification(
            status=classification_raw.get("status", ""),
            proposed=classification_raw.get("proposed", ""),
            basis=classification_raw.get("basis", "").strip(),
            approval_route=classification_raw.get("approval_route", "").strip(),
            privileges=classification_raw.get("privileges", "").strip(),
            criteria=tuple(
                ClassificationCriterion(
                    criterion=entry["criterion"],
                    effect=entry["effect"],
                    rationale=entry["rationale"].strip(),
                )
                for entry in classification_raw.get("criteria", ())
            ),
            open_items=tuple(classification_raw.get("open_items", ())),
        )
    return documents, classification


def _load_masses(base: Path) -> dict[str, ComponentMass]:
    path = base / "model/mass.yaml"
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        entry["id"]: ComponentMass(
            id=entry["id"],
            mass_kg=float(entry["mass_kg"]),
            source=entry.get("source", ""),
        )
        for entry in raw.get("components", ())
    }


def load_model(root: Path | None = None) -> Model:
    """Load the model from ``root`` (the repository by default)."""
    base = Path(root) if root else REPO_ROOT
    requirements, verifications, doorstop_issues = _load_doorstop(base)
    documents, classification = _load_compliance(base)
    masses = _load_masses(base)

    architecture = yaml.safe_load((base / "model/architecture/architecture.yaml").read_text(encoding="utf-8"))
    evidence_raw = yaml.safe_load((base / "model/evidence.yaml").read_text(encoding="utf-8"))
    assumptions_raw = yaml.safe_load((base / "model/assumptions.yaml").read_text(encoding="utf-8"))

    evidence = {
        record["verification"]: Evidence(
            verification=record["verification"],
            method=record.get("method", ""),
            status=record.get("status", ""),
            artifact=record.get("artifact"),
            plan=record.get("plan"),
            note=record.get("note"),
        )
        for record in evidence_raw["cases"]
    }
    assumptions = {
        record["id"]: Assumption(
            id=record["id"],
            title=record.get("title", ""),
            statement=record.get("statement", "").strip(),
            status=record.get("status", ""),
            data_file=record.get("data_file"),
        )
        for record in assumptions_raw
    }

    return Model(
        requirements=requirements,
        verifications=verifications,
        functions=_elements(architecture["functions"]),
        components=_elements(architecture["components"]),
        interfaces=_elements(architecture["interfaces"]),
        externals=tuple(entry["id"] for entry in architecture.get("externals", ())),
        evidence=evidence,
        assumptions=assumptions,
        doorstop_issues=tuple(doorstop_issues),
        documents=documents,
        classification=classification,
        masses=masses,
    )
