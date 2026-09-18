"""Command line behaviour, as CI and the reader will use it."""

from __future__ import annotations

from tools.diagram import main as diagram_main
from tools.traceability import main


def test_check_passes_on_the_repository_model(capsys):
    assert main(["check"]) == 0
    output = capsys.readouterr().out
    assert "0 errors, 0 warnings" in output


def test_report_check_passes_when_the_matrix_is_current(capsys):
    assert main(["report", "--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_architecture_diagram_check_passes_when_current(capsys):
    assert diagram_main(["--check"]) == 0
    assert "up to date" in capsys.readouterr().out
