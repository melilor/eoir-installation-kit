"""Command line behaviour, as CI and the reader will use it."""

from __future__ import annotations

from tools.traceability import main


def test_check_passes_on_the_repository_model(capsys):
    assert main(["check"]) == 0
    output = capsys.readouterr().out
    assert "0 errors, 0 warnings" in output


def test_report_check_passes_when_the_matrix_is_current(capsys):
    assert main(["report", "--check"]) == 0
    assert "up to date" in capsys.readouterr().out
