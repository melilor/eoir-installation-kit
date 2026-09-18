"""The technical report and the review: one test per review question.

The review reads the whole package — the model, the evidence files, the documents
that quote numbers and the tickets that are still open — so the tests copy those
trees into a temporary directory and break one thing at a time.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
import yaml

from tools.model import REPO_ROOT
from tools.report import (
    check_review,
    count_tests,
    evidence_summary,
    generated_files,
    load_report_model,
    open_items,
    resolve_highlight,
)

TREES = ("model", "docs", "evidence", "tests", ".scratch")


def copy_package(tmp_path: Path, name: str = "copy") -> Path:
    root = tmp_path / name
    for tree in TREES:
        shutil.copytree(REPO_ROOT / tree, root / tree)
    # The documents that quote numbers live at the top level, not in a tree.
    shutil.copy(REPO_ROOT / "README.md", root / "README.md")
    return root


def edit(root: Path, relative: str, mutate) -> None:
    path = root / relative
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def failed(tmp_path: Path, mutate, name: str | None = None) -> set[str]:
    root = copy_package(tmp_path, name or unique("failed"))
    mutate(root)
    findings, _ = check_review(load_report_model(root), root)
    return {finding.check for finding in findings if finding.status == "FAIL"}


def failing_subjects(tmp_path: Path, mutate, name: str | None = None) -> set[str]:
    root = copy_package(tmp_path, name or unique("subjects"))
    mutate(root)
    findings, _ = check_review(load_report_model(root), root)
    return {finding.subject for finding in findings if finding.status == "FAIL"}


def unique(prefix: str) -> str:
    """A fresh directory name, because a test may run the review more than once."""
    global _RUNS
    _RUNS += 1
    return f"{prefix}-{_RUNS}"


_RUNS = 0


# --------------------------------------------------------------------------- #
# One test per review question
# --------------------------------------------------------------------------- #


def test_the_base_package_passes_the_review(tmp_path):
    assert failed(tmp_path, lambda root: None) == set()


def test_an_analysis_without_an_evidence_file_is_a_failure(tmp_path):
    def mutate(root):
        (root / "evidence" / "qualification" / "checks.json").unlink()

    # Removing an evidence file also removes the number the documents quote from it,
    # so the documented number cannot be confirmed any more: both checks speak.
    assert "REVIEW-EVIDENCE" in failed(tmp_path, mutate)
    assert "qualification" in failing_subjects(tmp_path, mutate)
    assert "README.md:qualification_checks" in failing_subjects(tmp_path, mutate)


def test_a_missing_artifact_is_a_failure(tmp_path):
    def mutate(root):
        (root / "evidence" / "loads" / "checks.json").unlink()

    assert "REVIEW-ARTIFACTS" in failed(tmp_path, mutate)


def test_an_empty_artifact_is_a_failure(tmp_path):
    def mutate(root):
        # The declared artifact of a passed case is the machine-readable file.
        (root / "evidence" / "mass" / "checks.json").write_text("   ", encoding="utf-8")

    assert "REVIEW-ARTIFACTS" in failed(tmp_path, mutate)
    assert "REVIEW-EVIDENCE" in failed(tmp_path, mutate)


def test_a_warned_case_is_a_failure(tmp_path):
    def mutate(root):
        def promote(register):
            for record in register["cases"]:
                if record["verification"] == "VER003":
                    record["status"] = "WARN"

        edit(root, "model/evidence.yaml", promote)

    # The warning also changes the counts the documents quote, which is the point
    # of checking them: a status change moves a number in a README.
    assert "REVIEW-NO-WARN" in failed(tmp_path, mutate)


def test_a_future_case_without_its_ticket_is_a_failure(tmp_path):
    def mutate(root):
        def repoint(register):
            for record in register["cases"]:
                if record["verification"] == "VER017":
                    record["plan"] = "issues/99-a-ticket-that-does-not-exist"

        edit(root, "model/evidence.yaml", repoint)

    assert failed(tmp_path, mutate) == {"REVIEW-FUTURE-TICKET"}


def test_a_limitation_without_a_class_is_a_failure(tmp_path):
    def mutate(root):
        def drop(report):
            report["limitations"] = [
                entry for entry in report["limitations"] if entry["id"] != "VER011"
            ]

        edit(root, "model/report.yaml", drop)

    assert failed(tmp_path, mutate) == {"REVIEW-LIMITATION-CLASS"}
    assert failing_subjects(tmp_path, mutate) == {"model"}


def test_a_classification_that_names_nothing_is_a_failure(tmp_path):
    def mutate(root):
        def add(report):
            report["limitations"].append(
                {"id": "VER999", "class": "INPUT", "closes_with": "nothing, it does not exist"}
            )

        edit(root, "model/report.yaml", add)

    assert failed(tmp_path, mutate) == {"REVIEW-LIMITATION-CLASS"}
    assert failing_subjects(tmp_path, mutate) == {"register"}


def test_a_documented_number_that_does_not_match_is_a_failure(tmp_path):
    def mutate(root):
        path = root / "README.md"
        text = path.read_text(encoding="utf-8")
        found = re.search(r"(\d+)\s+tests:", text)
        assert found
        path.write_text(
            text.replace(found.group(0), f"{int(found.group(1)) + 7} tests:"), encoding="utf-8"
        )

    assert failed(tmp_path, mutate) == {"REVIEW-DOCUMENTED-NUMBER"}
    assert "README.md:tests" in failing_subjects(tmp_path, mutate)


def test_a_number_that_disappeared_from_a_document_is_a_failure(tmp_path):
    def mutate(root):
        path = root / "docs" / "overview.md"
        text = path.read_text(encoding="utf-8")
        found = re.search(r"\| Tests \| \*\*\d+\*\*, green \|", text)
        assert found
        path.write_text(text.replace(found.group(0), "| Tests | green |"), encoding="utf-8")

    assert failed(tmp_path, mutate) == {"REVIEW-DOCUMENTED-NUMBER"}


def test_a_review_that_does_not_declare_itself_is_a_failure(tmp_path):
    def mutate(root):
        def blank(report):
            report["review"]["performed_by"] = ""

        edit(root, "model/report.yaml", blank)

    assert failed(tmp_path, mutate) == {"REVIEW-DECLARED"}


def test_an_independent_claim_without_a_limitation_is_a_failure(tmp_path):
    def mutate(root):
        def claim(report):
            report["review"]["independent"] = True

        edit(root, "model/report.yaml", claim)

    # An independent review does not need to say what independence costs, and the
    # register then carries a classification for a limitation that no longer exists.
    assert failed(tmp_path, mutate) == {"REVIEW-LIMITATION-CLASS"}


# --------------------------------------------------------------------------- #
# The computed facts
# --------------------------------------------------------------------------- #


def test_every_highlight_resolves_against_the_repository_evidence():
    model = load_report_model()
    assert len(model.highlights) >= 10
    for entry in model.highlights:
        payload = evidence_summary(REPO_ROOT, entry["analysis"])
        assert payload is not None, entry["analysis"]
        value = resolve_highlight(payload, entry["path"])
        assert value is not None, f"{entry['analysis']}:{entry['path']} resolved to nothing"


def test_the_test_count_counts_every_test_module():
    counted = count_tests(REPO_ROOT)
    modules = len(list((REPO_ROOT / "tests").glob("test_*.py")))
    assert counted > modules, "every module has more than one test"
    assert counted > 150


def test_every_open_item_has_an_identifier():
    ids = open_items(REPO_ROOT)
    assert len(ids) == len(set(ids))
    assert ids, "the analyses record open items"


def test_the_review_classifies_every_limitation_of_the_model():
    model = load_report_model()
    findings, detail = check_review(model)
    classes = {entry.id for entry in model.limitations}
    assert "REVIEW" in classes
    assert all(entry.kind in {"INPUT", "METHOD", "ARTICLE", "AUTHORITY", "INDEPENDENCE"} for entry in model.limitations)
    assert len(model.limitations) >= 30
    assert [finding.as_dict() for finding in findings if finding.status == "FAIL"] == []


def test_the_committed_report_and_review_evidence_match_the_model():
    model = load_report_model()
    findings, detail = check_review(model)
    for name, content in generated_files(model, findings, detail, REPO_ROOT).items():
        assert (REPO_ROOT / name).read_text(encoding="utf-8") == content
