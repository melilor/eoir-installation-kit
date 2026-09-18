"""Environmental qualification plan.

Reads ``model/qualification.yaml`` — the installation zones, the DO-160G sections
that apply to them, the category of each or the reason it is still open, the
method and the test article — and writes two things: the plan itself in
``docs/qualification-plan.md``, which is the compliance document TP-001, and the
check result in ``evidence/qualification/``.

The checks are the acceptance criteria of the requirement they close:

* ``QUAL-SECTION-COVERAGE`` — every DO-160G section a requirement cites appears in
                              the plan (SYS014, SYS016, SYS033, SYS034, SYS035);
* ``QUAL-SECTION``          — each entry is complete: a declared zone, a basis, a
                              category or an explicit open, a method, an article
                              where a test is needed, and a limitation where the
                              work is pending (SYS014);
* ``QUAL-COMPONENT-ZONE``   — every component is qualified in a declared zone, or
                              declared as not installed (SYS014);
* ``QUAL-ZONE-COVERAGE``    — every declared zone is reached by at least one
                              section, and every zone an entry names exists;
* ``QUAL-PROTECTION``       — every protection means names what it serves, its
                              state against the platform protection plan and what
                              cannot be checked (SYS017, SYS035);
* ``QUAL-DOCUMENT``         — the plan is the document TP-001 of the compliance
                              register, and the register points at this file.

A category is never invented here: where the declared inputs and the public
statements about the standard do not fix it, the entry says what it depends on
and who closes it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from .analysis import Finding, findings_table, make_finding, sort_findings, summarise
from .model import REPO_ROOT, load_model

QUALIFICATION_PATH = Path("model/qualification.yaml")
PLAN_PATH = Path("docs/qualification-plan.md")
EVIDENCE_DIR = Path("evidence/qualification")
GENERATED_FILES = ("checks.json", "report.md")
METHODS = ("TEST", "ANALYSIS", "INSPECTION", "REVIEW")
STATUSES = ("ASSESSED", "PLANNED", "OPEN")
SECTION_REFERENCE = re.compile(r"DO-160G Section (\d+)")

# Everything an entry has to declare to be complete. The number of conditions is
# the limit of the QUAL-SECTION finding, so a missing one is visible as a number
# and named in the message.
ENTRY_CONDITIONS = (
    "a declared zone",
    "a basis",
    "a category or an explicit open item",
    "a method from the declared set",
    "a status from the declared set",
    "an article where a test is required",
    "a limitation where the work is planned",
    "an open item where the selection is open",
)


@dataclass(frozen=True)
class ZoneSelection:
    """What one section declares for one installation zone."""

    zone: str
    category: str | None
    open_on: str | None


@dataclass(frozen=True)
class SectionEntry:
    section: str
    title: str
    requirement: str
    zones: tuple[ZoneSelection, ...]
    basis: str
    method: str
    article: str | None
    status: str
    limitation: str | None = None
    open_on: str | None = None
    closing_action: str | None = None

    @property
    def number(self) -> int:
        return int(self.section.split(".")[0])

    @property
    def categories(self) -> dict[str, str | None]:
        return {selection.zone: selection.category for selection in self.zones}


@dataclass(frozen=True)
class ProtectionMean:
    id: str
    mean: str
    serves: tuple[str, ...]
    section: str
    against_plan: str
    status: str
    limitation: str | None = None
    open_on: str | None = None


@dataclass(frozen=True)
class FunctionalTest:
    id: str
    title: str
    requirement: str
    zones: tuple[str, ...]
    basis: str
    method: str
    article: str
    status: str
    limitation: str | None = None


@dataclass(frozen=True)
class QualificationModel:
    revision: str
    standard: str
    sections_in_standard: int
    closing_authority: str
    references: tuple[dict, ...]
    zones: tuple[dict, ...]
    components: tuple[dict, ...]
    sections: tuple[SectionEntry, ...]
    functional_tests: tuple[FunctionalTest, ...]
    protection: tuple[ProtectionMean, ...]
    open_items: tuple[dict, ...]

    @property
    def zone_ids(self) -> tuple[str, ...]:
        return tuple(zone["id"] for zone in self.zones)

    def zone(self, zone_id: str) -> dict:
        return next(zone for zone in self.zones if zone["id"] == zone_id)

    @property
    def applicable(self) -> tuple[SectionEntry, ...]:
        return tuple(
            entry
            for entry in self.sections
            if any(selection.category != "not-applicable" for selection in entry.zones)
        )


def load_qualification_model(root: Path | None = None) -> QualificationModel:
    """Load the qualification model."""
    base = Path(root) if root else REPO_ROOT
    raw = yaml.safe_load((base / QUALIFICATION_PATH).read_text(encoding="utf-8"))
    return QualificationModel(
        revision=raw["revision"],
        standard=raw["standard"],
        sections_in_standard=int(raw["sections_in_standard"]),
        closing_authority=raw["closing_authority"],
        references=tuple(raw["declared_rules"]["public_references"]),
        zones=tuple(raw["zones"]),
        components=tuple(raw["components"]),
        sections=tuple(
            SectionEntry(
                section=str(entry["section"]),
                title=entry["title"],
                requirement=entry["requirement"],
                zones=tuple(
                    ZoneSelection(
                        zone=selection["id"],
                        category=selection.get("category"),
                        open_on=selection.get("open_on"),
                    )
                    for selection in entry["zones"]
                ),
                basis=entry.get("basis", ""),
                method=entry.get("method", ""),
                article=entry.get("article"),
                status=entry.get("status", ""),
                limitation=entry.get("limitation"),
                open_on=entry.get("open_on"),
                closing_action=entry.get("closing_action"),
            )
            for entry in raw["sections"]
        ),
        functional_tests=tuple(
            FunctionalTest(
                id=entry["id"],
                title=entry["title"],
                requirement=entry["requirement"],
                zones=tuple(entry["zones"]),
                basis=entry.get("basis", ""),
                method=entry.get("method", ""),
                article=entry.get("article", ""),
                status=entry.get("status", ""),
                limitation=entry.get("limitation"),
            )
            for entry in raw.get("functional_tests", [])
        ),
        protection=tuple(
            ProtectionMean(
                id=entry["id"],
                mean=entry["mean"],
                serves=tuple(entry["serves"]),
                section=str(entry["section"]),
                against_plan=entry["against_plan"],
                status=entry.get("status", ""),
                limitation=entry.get("limitation"),
                open_on=entry.get("open_on"),
            )
            for entry in raw["protection_preservation"]
        ),
        open_items=tuple(raw["open_items"]),
    )


def cited_sections(root: Path | None = None) -> dict[int, tuple[str, ...]]:
    """The DO-160G sections the requirements cite, with every requirement that cites them.

    The requirements are walked in identifier order, not in the order Doorstop happens
    to read the directory in: that order differs between file systems, and a report
    that changes with it would fail its own freshness check on another machine.
    """
    model = load_model(root)
    cited: dict[int, list[str]] = {}
    for uid in sorted(model.requirements):
        requirement = model.requirements[uid]
        if not requirement.active:
            continue
        for number in SECTION_REFERENCE.findall(requirement.ref or ""):
            uids = cited.setdefault(int(number), [])
            if uid not in uids:
                uids.append(uid)
    return {number: tuple(uids) for number, uids in cited.items()}


def entry_gaps(entry: SectionEntry, zone_ids: tuple[str, ...]) -> list[str]:
    """What an entry does not declare, one line per missing condition."""
    gaps: list[str] = []
    if not entry.zones or any(selection.zone not in zone_ids for selection in entry.zones):
        gaps.append("a declared zone")
    if not entry.basis.strip():
        gaps.append("a basis")
    for selection in entry.zones:
        if selection.category != "not-applicable" and not selection.category and not (
            (selection.open_on or "").strip()
        ):
            gaps.append("a category or an explicit open item")
    if entry.method not in METHODS:
        gaps.append("a method from the declared set")
    if entry.status not in STATUSES:
        gaps.append("a status from the declared set")
    if entry.method == "TEST" and not (entry.article or "").strip():
        gaps.append("an article where a test is required")
    if entry.status == "PLANNED" and not (entry.limitation or "").strip():
        gaps.append("a limitation where the work is planned")
    if entry.status == "OPEN" and not (
        (entry.open_on or "").strip()
        or any((selection.open_on or "").strip() for selection in entry.zones)
    ):
        gaps.append("an open item where the selection is open")
    return gaps


def check_qualification(
    model: QualificationModel, root: Path | None = None
) -> tuple[list[Finding], dict]:
    """Run the plan checks and return the findings and the computed summary."""
    base = Path(root) if root else REPO_ROOT
    findings: list[Finding] = []
    zone_ids = model.zone_ids
    cited = cited_sections(base)
    planned = {entry.number for entry in model.sections}

    missing = {number: uids for number, uids in cited.items() if number not in planned}
    findings.append(
        make_finding(
            "QUAL-SECTION-COVERAGE",
            "requirements",
            not missing,
            float(len(cited) - len(missing)),
            float(len(cited)),
            f"{len(cited) - len(missing)} of the {len(cited)} DO-160G sections the requirements cite "
            + (
                "appear in the plan"
                if not missing
                else "; missing "
                + ", ".join(
                    f"{number} (cited by {', '.join(uids)})" for number, uids in sorted(missing.items())
                )
            ),
            mode="min",
        )
    )

    for entry in model.sections:
        gaps = entry_gaps(entry, zone_ids)
        findings.append(
            make_finding(
                "QUAL-SECTION",
                entry.section,
                not gaps,
                float(len(ENTRY_CONDITIONS) - len(gaps)),
                float(len(ENTRY_CONDITIONS)),
                f"section {entry.section} {entry.title}: "
                + (
                    "complete, state " + entry.status
                    if not gaps
                    else "missing " + ", ".join(gaps)
                ),
                mode="min",
            )
        )

    for entry in model.functional_tests:
        ok = (
            entry.method in METHODS
            and entry.status in STATUSES
            and bool(entry.article.strip())
            and bool(entry.basis.strip())
            and all(zone in zone_ids for zone in entry.zones)
        )
        findings.append(
            make_finding(
                "QUAL-FUNCTIONAL-TEST",
                entry.id,
                ok,
                float(ok),
                1.0,
                f"{entry.id} {entry.title}: "
                + ("declared with a method, an article and its zones" if ok else "incomplete"),
            )
        )

    components = load_model(base).components
    declared = {entry["component"]: entry["zones"] for entry in model.components}
    for component in components:
        zones = declared.get(component.id)
        ok = bool(zones) and all(zone in zone_ids for zone in zones)
        findings.append(
            make_finding(
                "QUAL-COMPONENT-ZONE",
                component.id,
                ok,
                float(len(zones or [])),
                1.0,
                f"{component.id} {component.name}: "
                + (
                    "in " + ", ".join(zones or [])
                    if ok
                    else "no declared installation zone"
                ),
                mode="min",
            )
        )

    for zone in model.zones:
        reached = [
            entry
            for entry in model.sections
            if zone["id"] in entry.categories
            and entry.categories[zone["id"]] != "not-applicable"
        ]
        required = bool(zone.get("qualification_required", True))
        reason = " ".join((zone.get("reason") or "").split())
        ok = bool(reached) if required else bool(reason)
        findings.append(
            make_finding(
                "QUAL-ZONE-COVERAGE",
                zone["id"],
                ok,
                float(len(reached) if required else len(reason)),
                1.0,
                f"{zone['id']} {zone['name']}: "
                + (
                    f"{len(reached)} applicable sections assessed against it"
                    if required
                    else f"no qualification required — {reason}"
                    if reason
                    else "declares no reason why it needs no qualification"
                ),
                mode="min",
            )
        )

    for mean in model.protection:
        ok = (
            bool(mean.mean.strip())
            and bool(mean.serves)
            and bool(mean.against_plan.strip())
            and mean.status in STATUSES
            and (mean.status != "OPEN" or bool((mean.open_on or "").strip()))
            and (mean.status != "PLANNED" or bool((mean.limitation or "").strip()))
        )
        findings.append(
            make_finding(
                "QUAL-PROTECTION",
                mean.id,
                ok,
                float(ok),
                1.0,
                f"{mean.id} section {mean.section}: serves {', '.join(mean.serves)}, state "
                f"{mean.status}, checked against {mean.against_plan}",
            )
        )

    register = {document.id: document for document in load_model(base).documents}
    document = register.get("TP-001")
    found = base / PLAN_PATH
    ok = (
        document is not None
        and (document.path or "").replace("\\", "/") == PLAN_PATH.as_posix()
        and found.exists()
    )
    if document is None:
        message = "TP-001 is not in the compliance register"
    elif (document.path or "").replace("\\", "/") != PLAN_PATH.as_posix():
        message = (
            f"TP-001 declares path {document.path!r}, not {PLAN_PATH.as_posix()!r}"
        )
    elif not found.exists():
        message = f"TP-001 points at {PLAN_PATH}, which does not exist"
    else:
        message = (
            f"TP-001 is the plan at {PLAN_PATH.as_posix()}, state {document.status}"
        )
    findings.append(
        make_finding(
            "QUAL-DOCUMENT",
            "TP-001",
            ok,
            float(ok),
            1.0,
            message,
        )
    )

    by_status: dict[str, int] = {}
    for entry in model.sections:
        by_status[entry.status] = by_status.get(entry.status, 0) + 1

    detail = {
        "zones": [
            {
                "id": zone["id"],
                "name": zone["name"],
                "components": [entry["component"] for entry in model.components if zone["id"] in entry["zones"]],
            }
            for zone in model.zones
        ],
        "sections": [
            {
                "section": entry.section,
                "title": entry.title,
                "requirement": entry.requirement,
                "categories": entry.categories,
                "method": entry.method,
                "article": entry.article,
                "status": entry.status,
                "limitation": entry.limitation,
                "open_on": entry.open_on,
            }
            for entry in model.sections
        ],
        "cited_by_requirements": {
            str(number): list(uids) for number, uids in sorted(cited.items())
        },
        "status_counts": by_status,
        "methods": {
            method: sum(1 for entry in model.sections if entry.method == method)
            for method in METHODS
        },
        "open_categories": sum(
            1
            for entry in model.sections
            for selection in entry.zones
            if selection.category != "not-applicable"
            and not selection.category
            and (selection.open_on or "").strip()
        ),
        "selected_categories": sum(
            1
            for entry in model.sections
            for selection in entry.zones
            if selection.category not in (None, "not-applicable")
        ),
    }
    return sort_findings(findings), detail


# --------------------------------------------------------------------------- #
# The plan document
# --------------------------------------------------------------------------- #


def render_plan(model: QualificationModel, detail: dict) -> str:
    """Render the qualification plan, which is the document TP-001."""
    lines = [
        "<!-- Generated by tools/qualification.py — do not edit by hand. -->",
        "<!-- Run: python -m tools.qualification -->",
        "",
        "# Environmental qualification plan",
        "",
        "| | |",
        "| --- | --- |",
        "| Document | TP-001 of the compliance register |",
        f"| Standard | {model.standard} |",
        f"| Revision | {model.revision} |",
        "| Installation | EO/IR installation kit on a CS-27 class platform |",
        "",
        "## Purpose and scope",
        "",
        "This plan states which sections and categories of the standard the installation has to be",
        "qualified to, in which installation zone, by which method and on which article. It covers",
        "the kit and the payload interface: the payload is qualified by its supplier, and this plan",
        "covers what the installation does to it.",
        "",
        "Two things are deliberately not done here. First, a category is not invented: the standard",
        "is not part of this repository, so a category is written down only where a declared input of",
        "the study and a public statement about the standard fix it, and every other entry names what",
        "the category depends on. Second, no compliance is claimed: the plan says what will show it,",
        "and the states below are what the study can reach without an article.",
        "",
        "## What the plan rests on",
        "",
        "| Statement used to select sections and categories | Source |",
        "| --- | --- |",
    ]
    for reference in model.references:
        statement = " ".join(reference["statement"].split())
        lines.append(f"| {statement} | {reference['source']} |")
    lines += [
        "",
        "The category of a section encodes the installation zone, and the zone definition belongs to",
        "the platform. The closing authority is therefore joint:",
        "",
        f"> {model.closing_authority}",
        "",
        "## Installation zones",
        "",
        "| Zone | Where | Exposure | Source of the definition | Components |",
        "| --- | --- | --- | --- | --- |",
    ]
    for zone in detail["zones"]:
        raw = model.zone(zone["id"])
        exposure = " ".join(raw["exposure"].split())
        lines.append(
            f"| {zone['id']} | {zone['name']} | {exposure} | {raw['source']} | "
            f"{', '.join(zone['components'])} |"
        )
    lines += [
        "",
        "## Applicability matrix",
        "",
        f"{len(model.sections)} entries: {detail['status_counts'].get('ASSESSED', 0)} assessed now, "
        f"{detail['status_counts'].get('PLANNED', 0)} planned on an article, "
        f"{detail['status_counts'].get('OPEN', 0)} open on a platform input. "
        f"{detail['selected_categories']} zone selections carry a category "
        f"({detail['open_categories']} are open on a named input).",
        "",
        "| Section | Title | Requirement | "
        + " | ".join(zone["id"] for zone in detail["zones"])
        + " | Method | Status |",
        "| --- | --- | --- | " + " | ".join("---" for _ in detail["zones"]) + " | --- | --- |",
    ]
    for entry in detail["sections"]:
        cells = []
        for zone in detail["zones"]:
            if zone["id"] not in entry["categories"]:
                cells.append("—")
            else:
                category = entry["categories"][zone["id"]]
                cells.append(category if category else "open")
        lines.append(
            f"| {entry['section']} | {entry['title']} | {entry['requirement']} | "
            + " | ".join(cells)
            + f" | {entry['method']} | {entry['status']} |"
        )
    lines += [
        "",
        "`not-applicable` means the section does not reach the zone; `open` means the category",
        "cannot be fixed with the declared inputs; `—` means the zone is not in the entry.",
        "",
        "## Why each selection is what it is",
        "",
    ]
    for raw in model.sections:
        lines.append(f"### Section {raw.section} — {raw.title}")
        lines.append("")
        lines.append(" ".join(raw.basis.split()))
        lines.append("")
        for selection in raw.zones:
            if selection.category == "not-applicable":
                lines.append(f"- **{selection.zone}**: the section does not apply.")
            elif selection.category:
                lines.append(
                    f"- **{selection.zone}**: category {selection.category}"
                    + (f" — {selection.open_on} still open." if selection.open_on else ".")
                )
            else:
                lines.append(f"- **{selection.zone}**: category open on {selection.open_on}.")
        lines.append("")
        lines.append(
            f"Method: {raw.method}" + (f" on {raw.article}" if raw.article else "")
            + f". State: {raw.status}."
        )
        if raw.limitation:
            lines.append("")
            lines.append(f"Limitation: {' '.join(raw.limitation.split())}")
        if raw.closing_action:
            lines.append("")
            lines.append(f"Closing action: {' '.join(raw.closing_action.split())}")
        lines.append("")

    lines += [
        "## Functional performance",
        "",
        "| Test | Requirement | What it shows | Method | Article | State |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for test in model.functional_tests:
        lines.append(
            f"| {test.id} {test.title} | {test.requirement} | {' '.join(test.basis.split())} | "
            f"{test.method} | {test.article} | {test.status} |"
        )
    lines += [
        "",
        "## Methods: what is analysis and what needs an article",
        "",
        "| Method | Entries | What it means here |",
        "| --- | --- | --- |",
        f"| TEST | {detail['methods']['TEST']} | Runs on the first article. The study has no article, so these entries are planned, not passed. |",
        f"| ANALYSIS | {detail['methods']['ANALYSIS']} | Carried by an analysis committed in this repository, named in the entry. |",
        f"| INSPECTION | {detail['methods']['INSPECTION']} | Carried by inspecting the declared design, which is in the model. |",
        f"| REVIEW | {detail['methods']['REVIEW']} | A review against a platform document, listed in the entry. |",
        "",
        "The campaign order follows the published practice that the potentially destructive tests run",
        "last: functional performance, then temperature, altitude, humidity, vibration, the electrical",
        "and EMC sections, then waterproofness, fluids, sand and dust, salt fog, and finally the",
        "sections that can destroy the article — lightning direct effects and any crash safety item.",
        "",
        "## Protection preservation",
        "",
        "| Means | Serves | Section | Checked against | State | What cannot be checked |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for mean in model.protection:
        cannot = mean.limitation or mean.open_on or "—"
        lines.append(
            f"| {mean.mean} | {', '.join(mean.serves)} | {mean.section} | {mean.against_plan} | "
            f"{mean.status} | {' '.join(cannot.split())} |"
        )
    lines += [
        "",
        "## Open items",
        "",
    ]
    for item in model.open_items:
        lines.append(f"- **{item['id']} — {item['title']}** {' '.join(item['detail'].split())}")
    lines += [
        "",
        "## What this plan does not do",
        "",
        "- It does not claim compliance with any category: every category either rests on a declared",
        "  input and a public statement about the standard, or is open on a named input.",
        "- It does not reproduce the standard. The clause numbers, the curves and the levels have to",
        "  be taken from RTCA DO-160G by whoever executes the campaign.",
        "- It does not replace the structural, electrical and thermal analyses: the tests confirm",
        "  their assumptions, they do not substitute for them.",
        "",
    ]
    return "\n".join(lines)


def render_report(model: QualificationModel, findings: list[Finding], detail: dict) -> str:
    """Render the readable check report."""
    summary = summarise(findings)
    lines = [
        "<!-- Generated by tools/qualification.py — do not edit by hand. -->",
        "<!-- Run: python -m tools.qualification -->",
        "",
        "# Qualification plan checks",
        "",
        f"Revision {model.revision}, {model.standard}. {summary['checks']} checks, "
        f"{summary['passed']} passed, {summary['failed']} failed.",
        "",
        "The plan itself is `docs/qualification-plan.md` (document TP-001). This report is the",
        "machine check that the plan is complete and that it does not claim more than it can.",
        "",
        "## Summary",
        "",
        f"- {len(model.sections)} section entries over {len(model.zones)} zones: "
        + ", ".join(f"{count} {status}" for status, count in sorted(detail["status_counts"].items()))
        + f"; {len(model.functional_tests)} functional test",
        f"- {detail['selected_categories']} zone selections carry a category, "
        f"{detail['open_categories']} are open on a named input",
        f"- Sections the requirements cite: "
        + ", ".join(
            f"{number} ({', '.join(uids)})"
            for number, uids in detail["cited_by_requirements"].items()
        ),
        "",
        "## Checks",
        "",
    ]
    lines += findings_table(findings)
    lines += [
        "",
        "## Entries",
        "",
        "| Section | Title | Category by zone | Method | State | Open on |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in detail["sections"]:
        categories = ", ".join(
            f"{zone}: {category or 'open'}" for zone, category in entry["categories"].items()
        )
        lines.append(
            f"| {entry['section']} | {entry['title']} | {categories} | {entry['method']} | "
            f"{entry['status']} | {' '.join((entry['open_on'] or '—').split())} |"
        )
    lines += [
        "",
        "## What the evidence does not cover",
        "",
        "- No category is asserted from the standard: the entries that carry one rest on a declared",
        "  input and a public statement, and the rest are open.",
        "- No test result exists. Every `PLANNED` entry needs the first article, and the entries that",
        "  need an article carry the limitation that says so.",
        "- The platform inputs the plan waits for — the compartment map, the HIRF and lightning",
        "  environment, the radio compatibility limits, the fluid list — are listed as open items,",
        "  not assumed.",
        "",
    ]
    return "\n".join(lines)


def generated_files(
    model: QualificationModel, findings: list[Finding], detail: dict
) -> dict[str, str]:
    """Return the content of every generated file, the plan included."""
    return {
        PLAN_PATH.as_posix(): render_plan(model, detail),
        f"{EVIDENCE_DIR}/checks.json": json.dumps(
            {
                "revision": model.revision,
                "standard": model.standard,
                "sections_in_standard": model.sections_in_standard,
                "closing_authority": model.closing_authority,
                **detail,
                "protection": [
                    {
                        "id": mean.id,
                        "serves": list(mean.serves),
                        "section": mean.section,
                        "status": mean.status,
                    }
                    for mean in model.protection
                ],
                "open_items": [item["id"] for item in model.open_items],
                "summary": summarise(findings),
                "findings": [finding.as_dict() for finding in findings],
            },
            indent=2,
        )
        + "\n",
        f"{EVIDENCE_DIR}/report.md": render_report(model, findings, detail),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.qualification", description=__doc__)
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root (default: the repo)")
    parser.add_argument("--check", action="store_true", help="fail if the plan or the evidence is out of date")
    args = parser.parse_args(argv)

    root = Path(args.root)
    model = load_qualification_model(root)
    findings, detail = check_qualification(model, root)
    files = generated_files(model, findings, detail)
    failed = [finding for finding in findings if finding.status == "FAIL"]

    if args.check:
        stale = []
        for name, content in files.items():
            path = root / name
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != content:
                stale.append(name)
        if stale:
            print(
                f"stale qualification output: {', '.join(stale)} — run python -m tools.qualification"
            )
            return 1
        print(f"qualification plan and evidence are up to date ({len(findings)} checks, {len(failed)} failed)")
        return 1 if failed else 0

    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(
        f"wrote {PLAN_PATH} and {EVIDENCE_DIR}: {len(findings)} checks, "
        f"{len(findings) - len(failed)} passed, {len(failed)} failed"
    )
    for finding in failed:
        print(f"  FAIL {finding.check}: {finding.message}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
