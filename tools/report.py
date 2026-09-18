"""The technical report and the review of the package.

The report is generated from ``model/report.yaml`` — the narrative, the limitations
register with the class of every limitation, the review criteria and the highlights —
and from the evidence files under ``evidence/``. No figure is typed into the report:
the numbers come from the artifacts, so a table cannot drift from what the analysis
produced.

The review is what this module checks, and it is mechanical on purpose: every
question is answered against the requirement and evidence model rather than against
the prose of the report.

* ``REVIEW-EVIDENCE``       — every analysis the report quotes has an evidence file
                              that exists and reports no failure;
* ``REVIEW-ARTIFACTS``      — every verification case with a passed or limited status
                              has an artifact that exists and is not empty;
* ``REVIEW-NO-WARN``        — no case carries the warning status;
* ``REVIEW-FUTURE-TICKET``  — every case still to come points at a ticket file that
                              exists, one finding per case;
* ``REVIEW-LIMITATION-CLASS`` — every limitation of the model is classified, and every
                              classification names a real limitation;
* ``REVIEW-DOCUMENTED-NUMBER`` — every number the repository documents quote matches
                              the model or the evidence;
* ``REVIEW-DECLARED``       — the review declares what it is, who ran it, that it is
                              not independent and what that costs.

The independence of a review is not something a tool can have. The study has one
author, so the report says so and the register records it.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from .analysis import Finding, findings_table, make_finding, sort_findings, summarise
from .model import REPO_ROOT, load_model
from .rules import check_model

REPORT_PATH = Path("model/report.yaml")
DOCUMENT_PATH = Path("docs/report.md")
EVIDENCE_DIR = Path("evidence/review")
GENERATED_FILES = ("checks.json", "report.md")
ISSUE_DIR = Path(".scratch/eoir-installation-kit/issues")
ANALYSES = ("layout", "mass", "clearance", "power", "loads", "qualification")


@dataclass(frozen=True)
class NumberClaim:
    file: str
    pattern: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class Limitation:
    id: str
    kind: str
    closes_with: str


@dataclass(frozen=True)
class ReportModel:
    revision: str
    title: str
    subtitle: str
    abstract: str
    chapters: tuple[dict, ...]
    review: dict
    claims: tuple[NumberClaim, ...]
    limitations: tuple[Limitation, ...]
    highlights: tuple[dict, ...]

    def class_of(self, limitation_id: str) -> Limitation | None:
        return next((item for item in self.limitations if item.id == limitation_id), None)


def load_report_model(root: Path | None = None) -> ReportModel:
    base = Path(root) if root else REPO_ROOT
    raw = yaml.safe_load((base / REPORT_PATH).read_text(encoding="utf-8"))
    claims = []
    for entry in raw["documented_numbers"]:
        value = entry["value"]
        sources = tuple(value) if isinstance(value, list) else (str(value),)
        claims.append(NumberClaim(file=entry["file"], pattern=entry["pattern"], sources=sources))
    return ReportModel(
        revision=raw["revision"],
        title=raw["title"],
        subtitle=raw["subtitle"],
        abstract=raw["abstract"],
        chapters=tuple(raw["chapters"]),
        review=raw["review"],
        claims=tuple(claims),
        limitations=tuple(
            Limitation(id=entry["id"], kind=entry["class"], closes_with=entry["closes_with"])
            for entry in raw["limitations"]
        ),
        highlights=tuple(raw["highlights"]),
    )


# --------------------------------------------------------------------------- #
# Computed facts
# --------------------------------------------------------------------------- #


def evidence_summary(root: Path, analysis: str) -> dict | None:
    """The evidence file of an analysis, or None when it is missing or unreadable."""
    path = root / "evidence" / analysis / "checks.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def count_tests(root: Path) -> int:
    """Test functions pytest collects: one per def, none parameterised."""
    total = 0
    for path in sorted((root / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        total += sum(
            1
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        )
    return total


def open_items(root: Path) -> tuple[str, ...]:
    """Every open item the analyses recorded, with its identifier."""
    ids: list[str] = []
    for name in ("power", "loads", "qualification"):
        path = root / "model" / f"{name}.yaml"
        if not path.exists():
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        for entry in raw.get("open_items", []):
            if isinstance(entry, dict) and entry.get("id"):
                ids.append(entry["id"])
    return tuple(ids)


def governed_finding(payload: dict) -> dict:
    """The finding that comes closest to its limit, relative to the limit."""
    findings = payload.get("findings", [])
    if not findings:
        return {}

    def closeness(finding: dict) -> float:
        limit = abs(finding.get("limit") or 0.0)
        return abs(finding.get("margin", 0.0)) / limit if limit else abs(finding.get("margin", 0.0))

    return min(findings, key=closeness)


def resolve_highlight(payload: dict, path: str):
    """Read a dotted path inside an evidence file, with an optional list index."""
    value = payload
    for part in path.split("."):
        match = re.match(r"^([^\[]+)\[(\d+)\]$", part)
        if match:
            value = value[match.group(1)][int(match.group(2))]
        else:
            value = value[part]
    return value


def facts(root: Path) -> dict:
    """Everything the review and the report need, computed once."""
    model = load_model(root)
    validation = check_model(model, root)
    per_analysis = {name: evidence_summary(root, name) for name in ANALYSES}
    statuses = {uid: record.status for uid, record in model.evidence.items()}
    computed: dict[str, object] = {
        "requirements": len(model.requirements),
        "components": len(model.components),
        "verification_cases": len(model.verifications),
        "assumptions": len(model.assumptions),
        "documents": len(model.documents),
        "tests": count_tests(root),
        "pass_cases": sum(1 for status in statuses.values() if status == "PASS"),
        "limitation_cases": sum(1 for status in statuses.values() if status == "LIMITATION"),
        "future_cases": sum(1 for status in statuses.values() if status == "FUTURE"),
        "validator_errors": sum(1 for finding in validation if finding.severity == "error"),
        "validator_warnings": sum(1 for finding in validation if finding.severity == "warning"),
    }
    for name, payload in per_analysis.items():
        checks = (payload or {}).get("summary", {}).get("checks")
        if checks is not None:
            computed[f"{name}_checks"] = checks
    return computed


# --------------------------------------------------------------------------- #
# The review
# --------------------------------------------------------------------------- #


def check_review(report: ReportModel, root: Path | None = None) -> tuple[list[Finding], dict]:
    """Run the review and return its findings and the computed facts."""
    base = Path(root) if root else REPO_ROOT
    model = load_model(base)
    statuses = {uid: record.status for uid, record in model.evidence.items()}
    computed = facts(base)
    per_analysis = {name: evidence_summary(base, name) for name in ANALYSES}
    findings: list[Finding] = []

    for name in ANALYSES:
        payload = per_analysis[name]
        if payload is None:
            findings.append(
                make_finding(
                    "REVIEW-EVIDENCE",
                    name,
                    False,
                    -1.0,
                    0.0,
                    f"evidence/{name}/checks.json does not exist: the report cannot quote an "
                    "analysis that left no artifact",
                )
            )
            continue
        failed = payload["summary"]["failed"]
        findings.append(
            make_finding(
                "REVIEW-EVIDENCE",
                name,
                failed == 0,
                float(payload["summary"]["checks"] - failed),
                float(payload["summary"]["checks"]),
                f"evidence/{name}/checks.json: {payload['summary']['checks']} checks, "
                f"{failed} failed",
                mode="min",
            )
        )

    missing = []
    for uid, status in sorted(statuses.items()):
        if status not in ("PASS", "LIMITATION"):
            continue
        artifact = model.evidence[uid].artifact
        path = base / artifact if artifact else None
        if path is None or not path.exists() or not path.read_text(encoding="utf-8").strip():
            missing.append(uid)
    findings.append(
        make_finding(
            "REVIEW-ARTIFACTS",
            "passed-and-limited",
            not missing,
            float(len(statuses) - len(missing)),
            float(len(statuses)),
            "every case with a passed or limited status names an artifact that exists and is "
            "not empty"
            if not missing
            else f"cases whose artifact is missing or empty: {', '.join(missing)}",
            mode="min",
        )
    )

    warned = sorted(uid for uid, status in statuses.items() if status == "WARN")
    findings.append(
        make_finding(
            "REVIEW-NO-WARN",
            "register",
            not warned,
            float(len(warned)),
            0.0,
            "no case carries the warning status"
            if not warned
            else f"cases carrying the warning status: {', '.join(warned)}",
            mode="max",
        )
    )

    for uid in sorted(statuses):
        if statuses[uid] != "FUTURE":
            continue
        plan = (model.evidence[uid].plan or "").strip()
        ticket = base / ISSUE_DIR / f"{plan.rsplit('/', 1)[-1]}.md"
        findings.append(
            make_finding(
                "REVIEW-FUTURE-TICKET",
                uid,
                bool(plan) and ticket.exists(),
                float(ticket.exists()),
                1.0,
                f"{uid}: plan {plan or '(none)'}"
                + ("" if ticket.exists() else " names a ticket file that does not exist"),
            )
        )

    declared_here = {"REVIEW"} if not report.review.get("independent") else set()
    known = sorted(set(statuses) | set(model.assumptions) | set(open_items(base)) | declared_here)
    limitations = [uid for uid in known if _is_limitation(model, statuses, uid)]
    unclassified = [uid for uid in limitations if report.class_of(uid) is None]
    findings.append(
        make_finding(
            "REVIEW-LIMITATION-CLASS",
            "model",
            not unclassified,
            float(len(limitations) - len(unclassified)),
            float(len(limitations)),
            f"{len(limitations)} limitations in the model, all classified"
            if not unclassified
            else f"limitations with no class in {REPORT_PATH}: {', '.join(unclassified)}",
            mode="min",
        )
    )
    stale = [
        entry.id
        for entry in report.limitations
        if entry.id not in known or not _is_limitation(model, statuses, entry.id)
    ]
    findings.append(
        make_finding(
            "REVIEW-LIMITATION-CLASS",
            "register",
            not stale,
            float(len(report.limitations) - len(stale)),
            float(len(report.limitations)),
            f"{len(report.limitations)} classifications, every one naming a real limitation"
            if not stale
            else f"classifications that name nothing: {', '.join(stale)}",
            mode="min",
        )
    )

    for claim in report.claims:
        path = base / claim.file
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        match = re.search(claim.pattern, text) if text else None
        if match is None:
            findings.append(
                make_finding(
                    "REVIEW-DOCUMENTED-NUMBER",
                    f"{claim.file}:{claim.pattern}",
                    False,
                    -1.0,
                    0.0,
                    f"{claim.file}: the pattern {claim.pattern!r} does not appear any more, so "
                    "the number it carried is no longer checked",
                )
            )
            continue
        found = match.groups()
        expected = tuple(computed.get(source, -1) for source in claim.sources)
        values = tuple(int(value) for value in found)
        ok = values == expected
        findings.append(
            make_finding(
                "REVIEW-DOCUMENTED-NUMBER",
                f"{claim.file}:{'+'.join(claim.sources)}",
                ok,
                float(values[0]),
                float(expected[0]),
                f"{claim.file}: says {values} where the model and the evidence say {expected}"
                if not ok
                else f"{claim.file}: {values} agrees with {'+'.join(claim.sources)}",
                mode="min",
            )
        )

    declared = report.review
    ok = (
        bool(declared.get("kind"))
        and bool(declared.get("performed_by"))
        and bool(declared.get("criteria"))
        and (declared.get("independent") is True or bool((declared.get("limitation") or "").strip()))
    )
    findings.append(
        make_finding(
            "REVIEW-DECLARED",
            "review",
            ok,
            float(ok),
            1.0,
            f"the review declares itself {declared.get('kind')}, run by "
            f"{declared.get('performed_by')}, independent: {declared.get('independent')}"
            + (
                ""
                if declared.get("independent")
                else ", and states what that costs"
            ),
        )
    )

    highlights = []
    for entry in report.highlights:
        payload = per_analysis.get(entry["analysis"]) or {}
        try:
            value = resolve_highlight(payload, entry["path"])
        except (KeyError, IndexError, TypeError):
            value = None
        highlights.append(
            {
                "analysis": entry["analysis"],
                "label": entry["label"],
                "path": entry["path"],
                "value": round(value, 3) if isinstance(value, float) else value,
                "unit": entry.get("unit", ""),
                "against": entry.get("against", ""),
            }
        )

    detail = {
        "facts": computed,
        "highlights": highlights,
        "analyses": {
            name: {
                "summary": (payload or {}).get("summary"),
                "governing": governed_finding(payload or {}),
            }
            for name, payload in per_analysis.items()
        },
        "limitations": [
            {"id": entry.id, "class": entry.kind, "closes_with": entry.closes_with}
            for entry in report.limitations
        ],
        "evidence_state": statuses,
    }
    return sort_findings(findings), detail


def _is_limitation(model, statuses: dict[str, str], uid: str) -> bool:
    """A limitation is an open assumption, a limited case or an open item."""
    if uid in statuses:
        return statuses[uid] == "LIMITATION"
    if uid in model.assumptions:
        return model.assumptions[uid].status == "OPEN"
    return uid == "REVIEW" or uid.startswith(("OI-", "QI-"))


# --------------------------------------------------------------------------- #
# The report
# --------------------------------------------------------------------------- #


def render_report(model: ReportModel, detail: dict, root: Path | None = None) -> str:
    """Render the technical report."""
    base = Path(root) if root else REPO_ROOT
    document = load_model(base)
    statuses = {uid: record.status for uid, record in document.evidence.items()}
    facts_by_name = detail["facts"]
    lines = [
        "<!-- Generated by tools/report.py — do not edit by hand. -->",
        "<!-- Run: python -m tools.report -->",
        "",
        f"# {model.title}",
        "",
        f"**{model.subtitle}**",
        "",
        f"Revision {model.revision}. "
        f"{facts_by_name['requirements']} requirements, "
        f"{facts_by_name['verification_cases']} verification cases, "
        f"{facts_by_name['components']} components, "
        f"{facts_by_name['assumptions']} declared assumptions, "
        f"{facts_by_name['documents']} compliance documents, "
        f"{facts_by_name['tests']} tests.",
        "",
        " ".join(model.abstract.split()),
        "",
        "## Contents",
        "",
    ]
    for chapter in model.chapters:
        lines.append(f"- {chapter['id']} {chapter['title']}")
    lines += ["- Annex: where the rest of the package is"]
    lines.append("")

    for chapter in model.chapters:
        lines += [f"## {chapter['id']} — {chapter['title']}", ""]
        for paragraph in chapter["paragraphs"]:
            lines += [" ".join(paragraph.split()), ""]
        if chapter["id"] == "R-05":
            lines += render_results(detail)
        if chapter["id"] == "R-06":
            lines += render_verification(document, statuses)
        if chapter["id"] == "R-07":
            lines += render_assumptions(document)
        if chapter["id"] == "R-08":
            lines += render_limitations(document, model, statuses, detail)
        if chapter["id"] == "R-09":
            lines += render_compliance(document)
        if chapter["id"] == "R-10":
            lines += render_review(model, detail)

    lines += [
        "## Annex",
        "",
        "- `docs/traceability.md` — the matrix: requirement, allocation, verification case, "
        "evidence state.",
        "- `docs/compliance-matrix.md` — the requirements against the compliance documents.",
        "- `docs/architecture.md` — the functions, components and interfaces, with the allocation.",
        "- `docs/qualification-plan.md` — the environmental qualification plan.",
        "- `evidence/` — every artifact the report quotes, generated by the tool named in each "
        "file header.",
        "",
    ]
    return "\n".join(lines)


def render_results(detail: dict) -> list[str]:
    lines = [
        "### The numbers a reader should see first",
        "",
        "| Number | Value | Against | Read from |",
        "| --- | --- | --- | --- |",
    ]
    for entry in detail.get("highlights", []):
        value = entry["value"]
        shown = "missing" if value is None else f"{value} {entry['unit']}".strip()
        lines.append(
            f"| {entry['label']} | {shown} | {entry['against']} | "
            f"`evidence/{entry['analysis']}/checks.json` → `{entry['path']}` |"
        )
    lines += [
        "",
        "### The finding that comes closest to its limit, per analysis",
        "",
        "| Analysis | Checks | Failed | Closest to its limit | Value | Limit | Margin | Artifact |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, payload in detail["analyses"].items():
        summary = payload.get("summary") or {}
        governing = payload.get("governing") or {}
        lines.append(
            f"| {name} | {summary.get('checks', '—')} | {summary.get('failed', '—')} | "
            f"{governing.get('check', '—')} on {governing.get('subject', '—')} | "
            f"{governing.get('value', '—')} | {governing.get('limit', '—')} | "
            f"{governing.get('margin', '—')} | `evidence/{name}/checks.json` |"
        )
    lines += [
        "",
        "Every number in that table is read from the artifact in the last column, which is "
        "generated by the tool of the same name in `tools/`. The full finding sets, with one row "
        "per check, are in `evidence/<analysis>/report.md`.",
        "",
    ]
    return lines


def render_verification(document, statuses: dict[str, str]) -> list[str]:
    lines = [
        "| Case | Method | Status | Artifact or plan |",
        "| --- | --- | --- | --- |",
    ]
    for uid in sorted(statuses):
        record = document.evidence[uid]
        pointer = record.artifact if record.artifact else f"plan: {record.plan or '—'}"
        lines.append(f"| {uid} | {record.method} | {record.status} | `{pointer}` |")
    lines += [
        "",
        f"{sum(1 for status in statuses.values() if status == 'PASS')} cases are closed with "
        f"evidence, {sum(1 for status in statuses.values() if status == 'LIMITATION')} are "
        f"limited and {sum(1 for status in statuses.values() if status == 'FUTURE')} are still "
        "to come. The note of each case, in `model/evidence.yaml`, says what the evidence does "
        "not cover.",
        "",
    ]
    return lines


def render_assumptions(document) -> list[str]:
    lines = [
        "| Assumption | Statement | Status | Data file |",
        "| --- | --- | --- | --- |",
    ]
    for uid in sorted(document.assumptions):
        assumption = document.assumptions[uid]
        statement = " ".join(assumption.statement.split())
        lines.append(
            f"| {uid} | {statement[:160]}{'…' if len(statement) > 160 else ''} | "
            f"{assumption.status} | `{assumption.data_file or '—'}` |"
        )
    lines.append("")
    return lines


def render_limitations(document, model: ReportModel, statuses: dict[str, str], detail: dict) -> list[str]:
    lines = [
        "| Limitation | Class | What it is | What closes it |",
        "| --- | --- | --- | --- |",
    ]
    limitations = {entry["id"]: entry for entry in detail["limitations"]}
    for uid in sorted(limitations):
        entry = limitations[uid]
        if uid in statuses:
            what = " ".join((document.evidence[uid].note or "").split())
            subject = f"{uid} ({statuses[uid].lower()} case)"
        elif uid in document.assumptions:
            assumption = document.assumptions[uid]
            what = f"{assumption.title}: {' '.join(assumption.statement.split())}"
            subject = f"{uid} (open assumption)"
        else:
            what = "an open item of an analysis, recorded in the model file that holds it"
            subject = f"{uid} (open item)"
        lines.append(
            f"| {subject} | {entry['class']} | {what[:220]}{'…' if len(what) > 220 else ''} | "
            f"{entry['closes_with']} |"
        )
    lines += [
        "",
        "Classes: **INPUT** — a declared input is missing or unconfirmed; **METHOD** — the "
        "method used cannot show it; **ARTICLE** — it needs a physical article; **AUTHORITY** — "
        "it needs the platform, the installer or the competent authority; **INDEPENDENCE** — the "
        "limitation of the review itself.",
        "",
    ]
    return lines


def render_compliance(document) -> list[str]:
    lines = [
        "| Document | Type | State | Requirements covered |",
        "| --- | --- | --- | --- |",
    ]
    for entry in document.documents:
        lines.append(
            f"| {entry.id} {entry.title} | {entry.type} | {entry.status} | "
            f"{len(entry.covers)} |"
        )
    lines += [
        "",
        "The coverage is exact: every requirement is covered by exactly one document, and the "
        "model validator refuses the repository otherwise. The classification of the change, the "
        "approval route and the privileges are in `model/compliance.yaml`.",
        "",
    ]
    return lines


def render_review(model: ReportModel, detail: dict) -> list[str]:
    lines = [
        f"Kind: **{model.review['kind']}**. Run by: {model.review['performed_by']}. "
        f"Independent: **{'yes' if model.review['independent'] else 'no'}**.",
        "",
        "What the review asks:",
        "",
    ]
    lines += [f"- {criterion}" for criterion in model.review["criteria"]]
    lines += [
        "",
        "What it found: nothing that is not already in the limitation register, and the register "
        "is checked against the model in both directions, so a limitation cannot be dropped from "
        "it and a classification cannot survive the limitation it described.",
        "",
    ]
    if not model.review["independent"]:
        lines += ["What it cannot do:", "", " ".join(model.review["limitation"].split()), ""]
    return lines


def render_review_report(model: ReportModel, findings: list[Finding], detail: dict) -> str:
    summary = summarise(findings)
    lines = [
        "<!-- Generated by tools/report.py — do not edit by hand. -->",
        "<!-- Run: python -m tools.report -->",
        "",
        "# Review of the package",
        "",
        f"Revision {model.revision}. {summary['checks']} checks, {summary['passed']} passed, "
        f"{summary['failed']} failed.",
        "",
        "The review runs against the model and the evidence, not against the report: the numbers "
        "the documents quote are checked against what the model and the artifacts say, the "
        "limitations are checked in both directions, and the cases that need a ticket are checked "
        "against the tickets on disk.",
        "",
        "## Checks",
        "",
    ]
    lines += findings_table(findings)
    lines += [
        "",
        "## The state the review saw",
        "",
        "| Fact | Value |",
        "| --- | --- |",
    ]
    for key, value in detail["facts"].items():
        lines.append(f"| {key} | {value} |")
    lines += [
        "",
        "## What the review does not do",
        "",
        "It is not independent: the study has one author, and a program that reads the same files "
        "the author wrote is not a second engineer. It checks consistency, coverage and honesty "
        "of the register, not engineering judgement. The classes of limitation it records are the "
        "work programme: what a platform has to supply, what a campaign has to measure, and what "
        "the closed-form analyses cannot replace.",
        "",
    ]
    return "\n".join(lines)


def generated_files(model: ReportModel, findings: list[Finding], detail: dict, root: Path) -> dict[str, str]:
    """Return the content of every generated file, the report included."""
    return {
        DOCUMENT_PATH.as_posix(): render_report(model, detail, root),
        f"{EVIDENCE_DIR}/checks.json": json.dumps(
            {
                "revision": model.revision,
                "review": {
                    "kind": model.review["kind"],
                    "performed_by": model.review["performed_by"],
                    "independent": model.review["independent"],
                    "criteria": model.review["criteria"],
                },
                "limitations": detail["limitations"],
                "facts": detail["facts"],
                "summary": summarise(findings),
                "findings": [finding.as_dict() for finding in findings],
            },
            indent=2,
        )
        + "\n",
        f"{EVIDENCE_DIR}/report.md": render_review_report(model, findings, detail),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.report", description=__doc__)
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root (default: the repo)")
    parser.add_argument("--check", action="store_true", help="fail if the report or the evidence is out of date")
    args = parser.parse_args(argv)

    root = Path(args.root)
    model = load_report_model(root)
    findings, detail = check_review(model, root)
    files = generated_files(model, findings, detail, root)
    failed = [finding for finding in findings if finding.status == "FAIL"]

    if args.check:
        stale = []
        for name, content in files.items():
            path = root / name
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != content:
                stale.append(name)
        if stale:
            print(f"stale report or review evidence: {', '.join(stale)} — run python -m tools.report")
            return 1
        print(f"report and review are up to date ({len(findings)} checks, {len(failed)} failed)")
        return 1 if failed else 0

    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(
        f"wrote {DOCUMENT_PATH} and {EVIDENCE_DIR}: {len(findings)} checks, "
        f"{len(findings) - len(failed)} passed, {len(failed)} failed"
    )
    for finding in failed:
        print(f"  FAIL {finding.check}: {finding.message}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
