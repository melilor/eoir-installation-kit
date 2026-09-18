"""Mass and balance analysis.

Reads the declared component masses from ``model/mass.yaml``, the platform data
from ``model/interfaces/icd_platform.yaml`` and the payload data from
``model/interfaces/icd_payload.yaml``; computes the kit mass budget and the
platform centre of gravity for every declared configuration; and writes the
result into ``evidence/mass/``.

The checks are the acceptance criteria of the requirements they close:

* ``MASS-KIT``  — the kit mass stays within the target (SYS005);
* ``MASS-PAYLOAD`` — the payload mass and CG stay within the declared envelope (SYS006);
* ``MASS-BALANCE`` — the platform CG stays inside the certified range (SYS007);
* ``MASS-MTOW`` — the total mass stays below the maximum take-off mass.

No mass is typed into a document: every figure comes from the model or from this
calculation, and the artifacts the evidence points at are the files below.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from .analysis import Finding, findings_table, make_finding, sort_findings, summarise
from .model import REPO_ROOT

MASS_PATH = Path("model/mass.yaml")
PLATFORM_ICD = Path("model/interfaces/icd_platform.yaml")
PAYLOAD_ICD = Path("model/interfaces/icd_payload.yaml")
EVIDENCE_DIR = Path("evidence/mass")
GENERATED_FILES = ("checks.json", "report.md")


@dataclass(frozen=True)
class ComponentMass:
    id: str
    mass_kg: float
    source: str
    note: str


@dataclass(frozen=True)
class Configuration:
    id: str
    description: str
    payload: str
    payload_cg_offset_mm: float
    kit_mass_factor: float


@dataclass(frozen=True)
class MassModel:
    revision: str
    units: str
    rules: dict[str, float]
    kit_station_mm: float
    payload_station_mm: float
    components: tuple[ComponentMass, ...]
    configurations: tuple[Configuration, ...]
    platform: dict
    payload: dict

    @property
    def kit_mass_kg(self) -> float:
        return sum(component.mass_kg for component in self.components)

    @property
    def payload_mass_kg(self) -> float:
        return float(self.payload["mass_and_inertia"]["mass_kg"])

    @property
    def payload_cg_envelope_mm(self) -> float:
        return float(self.payload["mass_and_inertia"]["cg_envelope_mm"]["x"])


def load_mass_model(root: Path | None = None) -> MassModel:
    """Load the mass model and the two interface control files."""
    base = Path(root) if root else REPO_ROOT
    raw = yaml.safe_load((base / MASS_PATH).read_text(encoding="utf-8"))
    platform = yaml.safe_load((base / PLATFORM_ICD).read_text(encoding="utf-8"))
    payload = yaml.safe_load((base / PAYLOAD_ICD).read_text(encoding="utf-8"))
    return MassModel(
        revision=raw["revision"],
        units=raw["units"],
        rules={key: float(value) for key, value in raw["declared_rules"].items()},
        kit_station_mm=float(raw["installation"]["kit_station_mm_aft_of_datum"]),
        payload_station_mm=float(raw["installation"]["payload_station_mm_aft_of_datum"]),
        components=tuple(
            ComponentMass(
                id=entry["id"],
                mass_kg=float(entry["mass_kg"]),
                source=entry.get("source", ""),
                note=entry.get("note", ""),
            )
            for entry in raw["components"]
        ),
        configurations=tuple(
            Configuration(
                id=entry["id"],
                description=entry.get("description", ""),
                payload=entry["payload"],
                payload_cg_offset_mm=float(entry.get("payload_cg_offset_mm", 0)),
                kit_mass_factor=float(entry.get("kit_mass_factor", 1.0)),
            )
            for entry in raw["configurations"]
        ),
        platform=platform,
        payload=payload,
    )


@dataclass(frozen=True)
class Balance:
    """The computed mass and balance of one configuration."""

    configuration: Configuration
    kit_mass_kg: float
    payload_mass_kg: float
    total_mass_kg: float
    cg_mm: float
    margin_forward_mm: float
    margin_aft_mm: float


def compute_balance(model: MassModel, configuration: Configuration) -> Balance:
    """Compute the platform CG with the kit and, where declared, the payload."""
    platform = model.platform["mass_and_inertia"]
    empty_mass = float(platform["empty_mass_kg"])
    empty_cg = float(platform["empty_cg_mm_aft_of_datum"])

    kit_mass = model.kit_mass_kg * configuration.kit_mass_factor
    payload_mass = model.payload_mass_kg if configuration.payload == "installed" else 0.0
    payload_station = model.payload_station_mm + configuration.payload_cg_offset_mm

    moment = empty_mass * empty_cg + kit_mass * model.kit_station_mm + payload_mass * payload_station
    total = empty_mass + kit_mass + payload_mass
    cg = moment / total

    forward = float(platform["cg_range_mm_aft_of_datum"]["forward"])
    aft = float(platform["cg_range_mm_aft_of_datum"]["aft"])
    return Balance(
        configuration=configuration,
        kit_mass_kg=kit_mass,
        payload_mass_kg=payload_mass,
        total_mass_kg=total,
        cg_mm=cg,
        margin_forward_mm=cg - forward,
        margin_aft_mm=aft - cg,
    )


def check_mass(model: MassModel) -> tuple[list[Finding], list[Balance]]:
    """Run the mass and balance checks and return them with the computed cases."""
    findings: list[Finding] = []
    balances = [compute_balance(model, configuration) for configuration in model.configurations]

    target = float(model.rules["kit_mass_target_kg"])
    envelope = model.payload_cg_envelope_mm
    for balance in balances:
        configuration = balance.configuration
        findings.append(
            make_finding(
                "MASS-KIT",
                configuration.id,
                balance.kit_mass_kg <= target,
                balance.kit_mass_kg,
                target,
                f"{configuration.id}: kit mass {balance.kit_mass_kg:.2f} kg "
                f"(target {target:g} kg, factor {configuration.kit_mass_factor:g})",
                mode="max",
            )
        )
        findings.append(
            make_finding(
                "MASS-PAYLOAD",
                configuration.id,
                abs(configuration.payload_cg_offset_mm) <= envelope
                and balance.payload_mass_kg <= model.payload_mass_kg,
                abs(configuration.payload_cg_offset_mm),
                envelope,
                f"{configuration.id}: payload CG offset "
                f"{configuration.payload_cg_offset_mm:+.0f} mm of the mounting datum "
                f"(declared envelope ±{envelope:g} mm)",
                mode="max",
            )
        )
        nearest = min(balance.margin_forward_mm, balance.margin_aft_mm)
        findings.append(
            make_finding(
                "MASS-BALANCE",
                configuration.id,
                nearest >= 0,
                balance.cg_mm,
                balance.cg_mm - nearest,
                f"{configuration.id}: platform CG {balance.cg_mm:.1f} mm aft of datum, "
                f"closest limit {nearest:+.1f} mm away",
            )
        )
        mtow = float(model.platform["mass_and_inertia"]["mtow_kg"])
        findings.append(
            make_finding(
                "MASS-MTOW",
                configuration.id,
                balance.total_mass_kg <= mtow,
                balance.total_mass_kg,
                mtow,
                f"{configuration.id}: total mass {balance.total_mass_kg:.1f} kg "
                f"(maximum take-off mass {mtow:g} kg)",
                mode="max",
            )
        )

    return sort_findings(findings), balances


def render_checks(model: MassModel, findings: list[Finding], balances: list[Balance]) -> str:
    """Render the machine-readable result."""
    payload = {
        "revision": model.revision,
        "units": model.units,
        "declared_rules": model.rules,
        "kit_mass_kg": round(model.kit_mass_kg, 3),
        "component_masses": [
            {"id": component.id, "mass_kg": component.mass_kg, "source": component.source}
            for component in model.components
        ],
        "configurations": [
            {
                "id": balance.configuration.id,
                "description": balance.configuration.description,
                "kit_mass_kg": round(balance.kit_mass_kg, 3),
                "payload_mass_kg": round(balance.payload_mass_kg, 3),
                "total_mass_kg": round(balance.total_mass_kg, 3),
                "cg_mm_aft_of_datum": round(balance.cg_mm, 2),
                "margin_forward_mm": round(balance.margin_forward_mm, 2),
                "margin_aft_mm": round(balance.margin_aft_mm, 2),
            }
            for balance in balances
        ],
        "summary": summarise(findings),
        "findings": [finding.as_dict() for finding in findings],
    }
    return json.dumps(payload, indent=2) + "\n"


def render_report(model: MassModel, findings: list[Finding], balances: list[Balance]) -> str:
    """Render the readable report."""
    platform = model.platform["mass_and_inertia"]
    summary = summarise(findings)
    lines = [
        "<!-- Generated by tools/mass.py — do not edit by hand. -->",
        "<!-- Run: python -m tools.mass -->",
        "",
        "# Mass and balance",
        "",
        f"Revision {model.revision}, units {model.units}. "
        f"{summary['checks']} checks, {summary['passed']} passed, {summary['failed']} failed.",
        "",
        "## Inputs",
        "",
        f"- Kit mass, computed from {len(model.components)} component masses: "
        f"**{model.kit_mass_kg:.2f} kg** (target {model.rules['kit_mass_target_kg']:g} kg)",
        f"- Component mass tolerance: {model.rules['component_mass_tolerance_pct']:g} %",
        f"- Platform empty mass and CG: {platform['empty_mass_kg']:g} kg at "
        f"{platform['empty_cg_mm_aft_of_datum']:g} mm aft of datum "
        f"(certified range {platform['cg_range_mm_aft_of_datum']['forward']:g} to "
        f"{platform['cg_range_mm_aft_of_datum']['aft']:g} mm)",
        f"- Kit installation station: {model.kit_station_mm:g} mm aft of datum; "
        f"payload station {model.payload_station_mm:g} mm",
        f"- Payload: {model.payload_mass_kg:g} kg, CG envelope ±{model.payload_cg_envelope_mm:g} mm",
        "",
        "## Configurations",
        "",
        "| Configuration | Description | Kit (kg) | Payload (kg) | Total (kg) | CG (mm) | Forward margin (mm) | Aft margin (mm) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for balance in balances:
        lines.append(
            f"| {balance.configuration.id} | {balance.configuration.description} | "
            f"{balance.kit_mass_kg:.2f} | {balance.payload_mass_kg:.2f} | "
            f"{balance.total_mass_kg:.1f} | {balance.cg_mm:.1f} | "
            f"{balance.margin_forward_mm:+.1f} | {balance.margin_aft_mm:+.1f} |"
        )
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines += findings_table(findings)
    lines.append("")
    lines.append("## Component masses")
    lines.append("")
    lines.append("| Component | Mass (kg) | Source | Note |")
    lines.append("| --- | --- | --- | --- |")
    for component in model.components:
        lines.append(
            f"| {component.id} | {component.mass_kg:.2f} | {component.source} | {component.note} |"
        )
    lines.append("")
    lines.append(
        "Every mass here is a declared engineering estimate: the study has no weighed article. "
        "The payload is at its declared envelope limit and the tolerance cases are used on "
        "purpose, so the configuration table is a bound and not a nominal case."
    )
    lines.append("")
    return "\n".join(lines)


def generated_files(model: MassModel, findings: list[Finding], balances: list[Balance]) -> dict[str, str]:
    """Return the content of every generated evidence file."""
    return {
        "checks.json": render_checks(model, findings, balances),
        "report.md": render_report(model, findings, balances),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.mass", description=__doc__)
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root (default: the repo)")
    parser.add_argument("--check", action="store_true", help="fail if the evidence is out of date")
    args = parser.parse_args(argv)

    root = Path(args.root)
    model = load_mass_model(root)
    findings, balances = check_mass(model)
    files = generated_files(model, findings, balances)
    failed = [finding for finding in findings if finding.status == "FAIL"]

    if args.check:
        stale = []
        for name, content in files.items():
            path = root / EVIDENCE_DIR / name
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != content:
                stale.append(name)
        if stale:
            print(f"stale mass evidence: {', '.join(stale)} — run python -m tools.mass")
            return 1
        print(f"mass evidence is up to date ({len(findings)} checks, {len(failed)} failed)")
        return 1 if failed else 0

    target = root / EVIDENCE_DIR
    target.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (target / name).write_text(content, encoding="utf-8")
    print(
        f"wrote {EVIDENCE_DIR}: {len(findings)} checks, "
        f"{len(findings) - len(failed)} passed, {len(failed)} failed"
    )
    for finding in failed:
        print(f"  FAIL {finding.check}: {finding.message}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
