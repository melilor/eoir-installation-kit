"""Command line behaviour, as CI and the reader will use it."""

from __future__ import annotations

from tools.clearance import main as clearance_main
from tools.compliance import main as compliance_main
from tools.diagram import main as diagram_main
from tools.mass import main as mass_main
from tools.traceability import main


def test_check_passes_on_the_repository_model(capsys):
    assert main(["check"]) == 0
    output = capsys.readouterr().out
    assert "0 errors" in output


def test_warnings_do_not_fail_the_gate(capsys):
    assert main(["check"]) == 0
    output = capsys.readouterr().out
    assert "ASM-OPEN" in output
    assert "warning" in output


def test_report_check_passes_when_the_matrix_is_current(capsys):
    assert main(["report", "--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_architecture_diagram_check_passes_when_current(capsys):
    assert diagram_main(["--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_compliance_matrix_check_passes_when_current(capsys):
    assert compliance_main(["--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_mass_evidence_check_passes_when_current(capsys):
    assert mass_main(["--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_clearance_evidence_check_passes_when_current(capsys):
    assert clearance_main(["--check"]) == 0
    assert "up to date" in capsys.readouterr().out
