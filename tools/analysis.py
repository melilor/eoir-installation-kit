"""Shared structures for the analysis tools.

The layout, mass, clearance and power tools all produce the same shape of
result: one finding per check, with the measured value, the limit and the
margin, so a failure names the violated constraint instead of reporting a
feeling. Those structures live here, once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Finding:
    """The result of one check on one subject."""

    check: str
    subject: str
    status: str
    value: float
    limit: float
    margin: float
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "subject": self.subject,
            "status": self.status,
            "value": round(self.value, 3),
            "limit": self.limit,
            "margin": round(self.margin, 3),
            "message": self.message,
        }


def make_finding(
    check: str,
    subject: str,
    ok: bool,
    value: float,
    limit: float,
    message: str,
    mode: str = "min",
) -> Finding:
    """Build a finding.

    ``mode`` is the direction of the constraint: ``min`` means the value must be
    at least the limit, ``max`` means it must be at most the limit. ``margin`` is
    therefore always positive when the check passes.
    """
    margin = value - limit if mode == "min" else limit - value
    return Finding(
        check=check,
        subject=subject,
        status="PASS" if ok else "FAIL",
        value=value,
        limit=limit,
        margin=margin,
        message=message,
    )


def summarise(findings: list[Finding]) -> dict[str, int]:
    """Count the findings by status."""
    return {
        "checks": len(findings),
        "passed": sum(1 for finding in findings if finding.status == "PASS"),
        "failed": sum(1 for finding in findings if finding.status == "FAIL"),
    }


def findings_table(findings: list[Finding]) -> list[str]:
    """Render the findings as a Markdown table."""
    lines = [
        "| Check | Subject | Status | Value | Limit | Margin |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for finding in findings:
        lines.append(
            f"| {finding.check} | {finding.subject} | {finding.status} | "
            f"{finding.value:.2f} | {finding.limit:g} | {finding.margin:+.2f} |"
        )
    return lines


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Failures first, then by check and subject."""
    return sorted(
        findings, key=lambda finding: (finding.status != "FAIL", finding.check, finding.subject)
    )
