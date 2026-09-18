"""Electrical power budget and protection coordination.

Reads the payload demand and the bus data from the interface control files and
the kit's harness and protection from ``model/power.yaml``, then computes:

* the continuous and peak currents and the voltage drop along the power harness
  against the declared limits (SYS010);
* the conductor ampacity against the continuous current;
* the circuit breaker rating against the peak demand;
* the resulting bus load against the declared capacity (SYS011).

The outputs are written to ``evidence/power/``. The declared open items — above
all the payload inrush against the breaker rating, which needs the trip curve —
are reported there instead of being smoothed away, and they are the reason the
coordination verification carries a LIMITATION rather than a PASS.
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

POWER_PATH = Path("model/power.yaml")
PLATFORM_ICD = Path("model/interfaces/icd_platform.yaml")
PAYLOAD_ICD = Path("model/interfaces/icd_payload.yaml")
EVIDENCE_DIR = Path("evidence/power")
GENERATED_FILES = ("checks.json", "report.md")


@dataclass(frozen=True)
class Harness:
    id: str
    component: str
    description: str
    cross_section_mm2: float
    installed_length_m: float


@dataclass(frozen=True)
class Protection:
    component: str
    device: str
    rating_a: float
    trip_curve: str


@dataclass(frozen=True)
class PowerModel:
    revision: str
    rules: dict[str, float]
    harnesses: tuple[Harness, ...]
    protection: Protection
    open_items: tuple[str, ...]
    platform: dict
    payload: dict

    @property
    def bus_voltage_v(self) -> float:
        return float(self.platform["electrical"]["bus_voltage_vdc"])

    @property
    def continuous_w(self) -> float:
        return float(self.payload["power"]["continuous_w"])

    @property
    def peak_w(self) -> float:
        return float(self.payload["power"]["peak_w"])

    @property
    def inrush_a(self) -> float:
        return float(self.payload["power"]["inrush_a"])


@dataclass(frozen=True)
class Circuit:
    """The computed state of one harness circuit."""

    harness: Harness
    continuous_current_a: float
    peak_current_a: float
    continuous_drop_v: float
    peak_drop_v: float
    ampacity_a: float
    loss_w: float


def load_power_model(root: Path | None = None) -> PowerModel:
    """Load the electrical model and the interface control files."""
    base = Path(root) if root else REPO_ROOT
    raw = yaml.safe_load((base / POWER_PATH).read_text(encoding="utf-8"))
    platform = yaml.safe_load((base / PLATFORM_ICD).read_text(encoding="utf-8"))
    payload = yaml.safe_load((base / PAYLOAD_ICD).read_text(encoding="utf-8"))
    protection = raw["protection"]
    return PowerModel(
        revision=raw["revision"],
        rules={key: float(value) for key, value in raw["declared_rules"].items()},
        harnesses=tuple(
            Harness(
                id=entry["id"],
                component=entry["component"],
                description=entry.get("description", ""),
                cross_section_mm2=float(entry["conductor_cross_section_mm2"]),
                installed_length_m=float(entry["installed_length_m"]),
            )
            for entry in raw["harnesses"]
        ),
        protection=Protection(
            component=protection["component"],
            device=protection["device"],
            rating_a=float(protection["rating_a"]),
            trip_curve=protection.get("trip_curve", ""),
        ),
        open_items=tuple(raw.get("open_items", ())),
        platform=platform,
        payload=payload,
    )


def compute_circuit(model: PowerModel, harness: Harness) -> Circuit:
    """Compute the currents, the voltage drop and the ampacity of one harness."""
    resistivity = model.rules["copper_resistivity_ohm_mm2_per_m"]
    continuous = model.continuous_w / model.bus_voltage_v
    peak = model.peak_w / model.bus_voltage_v
    resistance = 2 * harness.installed_length_m * resistivity / harness.cross_section_mm2
    return Circuit(
        harness=harness,
        continuous_current_a=continuous,
        peak_current_a=peak,
        continuous_drop_v=continuous * resistance,
        peak_drop_v=peak * resistance,
        ampacity_a=harness.cross_section_mm2 * model.rules["conductor_ampacity_a_per_mm2"],
        loss_w=continuous * continuous * resistance,
    )


def check_power(model: PowerModel) -> tuple[list[Finding], list[Circuit]]:
    """Run the electrical checks and return them with the computed circuits."""
    findings: list[Finding] = []
    circuits = [compute_circuit(model, harness) for harness in model.harnesses]
    voltage = model.bus_voltage_v
    platform_electrical = model.platform["electrical"]

    for circuit in circuits:
        harness = circuit.harness
        continuous_limit = model.rules["continuous_voltage_drop_pct"] / 100 * voltage
        peak_limit = model.rules["peak_voltage_drop_pct"] / 100 * voltage
        findings.append(
            make_finding(
                "POWER-CONTINUOUS",
                harness.id,
                circuit.continuous_drop_v <= continuous_limit,
                circuit.continuous_drop_v,
                continuous_limit,
                f"{harness.id}: {circuit.continuous_current_a:.2f} A over "
                f"{harness.installed_length_m:g} m of {harness.cross_section_mm2:g} mm2, "
                f"drop {circuit.continuous_drop_v:.3f} V "
                f"({model.rules['continuous_voltage_drop_pct']:g} % limit)",
                mode="max",
            )
        )
        findings.append(
            make_finding(
                "POWER-PEAK",
                harness.id,
                circuit.peak_drop_v <= peak_limit,
                circuit.peak_drop_v,
                peak_limit,
                f"{harness.id}: {circuit.peak_current_a:.2f} A peak, drop "
                f"{circuit.peak_drop_v:.3f} V ({model.rules['peak_voltage_drop_pct']:g} % limit)",
                mode="max",
            )
        )
        findings.append(
            make_finding(
                "POWER-AMPACITY",
                harness.id,
                circuit.continuous_current_a <= circuit.ampacity_a,
                circuit.continuous_current_a,
                circuit.ampacity_a,
                f"{harness.id}: continuous current {circuit.continuous_current_a:.2f} A against "
                f"an ampacity of {circuit.ampacity_a:g} A",
                mode="max",
            )
        )

    required_rating = model.rules["breaker_margin_factor"] * max(
        circuit.peak_current_a for circuit in circuits
    )
    findings.append(
        make_finding(
            "POWER-BREAKER",
            model.protection.component,
            model.protection.rating_a >= required_rating,
            model.protection.rating_a,
            required_rating,
            f"{model.protection.device} rated {model.protection.rating_a:g} A against a "
            f"required {required_rating:.2f} A "
            f"({model.rules['breaker_margin_factor']:g} x peak demand)",
        )
    )

    added_load = model.continuous_w + sum(circuit.loss_w for circuit in circuits)
    new_load = float(platform_electrical["existing_continuous_load_w"]) + added_load
    capacity = float(platform_electrical["bus_capacity_w"])
    findings.append(
        make_finding(
            "POWER-BUS",
            "platform",
            new_load <= capacity,
            new_load,
            capacity,
            f"bus load {new_load:.0f} W after the installation "
            f"({added_load:.0f} W added) against a declared capacity of {capacity:g} W",
            mode="max",
        )
    )

    return sort_findings(findings), circuits


def render_checks(model: PowerModel, findings: list[Finding], circuits: list[Circuit]) -> str:
    """Render the machine-readable result."""
    payload = {
        "revision": model.revision,
        "bus_voltage_v": model.bus_voltage_v,
        "declared_rules": model.rules,
        "protection": {
            "component": model.protection.component,
            "device": model.protection.device,
            "rating_a": model.protection.rating_a,
            "trip_curve": model.protection.trip_curve,
        },
        "payload": {
            "continuous_w": model.continuous_w,
            "peak_w": model.peak_w,
            "inrush_a": model.inrush_a,
        },
        "circuits": [
            {
                "harness": circuit.harness.id,
                "component": circuit.harness.component,
                "cross_section_mm2": circuit.harness.cross_section_mm2,
                "installed_length_m": circuit.harness.installed_length_m,
                "continuous_current_a": round(circuit.continuous_current_a, 3),
                "peak_current_a": round(circuit.peak_current_a, 3),
                "continuous_drop_v": round(circuit.continuous_drop_v, 4),
                "peak_drop_v": round(circuit.peak_drop_v, 4),
                "ampacity_a": circuit.ampacity_a,
                "loss_w": round(circuit.loss_w, 3),
            }
            for circuit in circuits
        ],
        "open_items": list(model.open_items),
        "summary": summarise(findings),
        "findings": [finding.as_dict() for finding in findings],
    }
    return json.dumps(payload, indent=2) + "\n"


def render_report(model: PowerModel, findings: list[Finding], circuits: list[Circuit]) -> str:
    """Render the readable report."""
    platform_electrical = model.platform["electrical"]
    summary = summarise(findings)
    lines = [
        "<!-- Generated by tools/power.py — do not edit by hand. -->",
        "<!-- Run: python -m tools.power -->",
        "",
        "# Electrical power budget and protection",
        "",
        f"Revision {model.revision}, bus {model.bus_voltage_v:g} VDC. "
        f"{summary['checks']} checks, {summary['passed']} passed, {summary['failed']} failed.",
        "",
        "## Inputs",
        "",
        f"- Payload demand: {model.continuous_w:g} W continuous, {model.peak_w:g} W peak, "
        f"{model.inrush_a:g} A inrush",
        f"- Platform bus: {platform_electrical['bus_capacity_w']:g} W capacity, "
        f"{platform_electrical['existing_continuous_load_w']:g} W already loaded",
        f"- Protection: {model.protection.device.lower()} rated "
        f"{model.protection.rating_a:g} A (`{model.protection.component}`), trip curve: "
        f"{model.protection.trip_curve}",
        "",
        "## Circuits",
        "",
        "| Harness | Component | Conductor (mm2) | Length (m) | Continuous (A) | Peak (A) | "
        "Drop continuous (V) | Drop peak (V) | Ampacity (A) | Loss (W) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for circuit in circuits:
        lines.append(
            f"| {circuit.harness.id} | {circuit.harness.component} | "
            f"{circuit.harness.cross_section_mm2:g} | {circuit.harness.installed_length_m:g} | "
            f"{circuit.continuous_current_a:.2f} | {circuit.peak_current_a:.2f} | "
            f"{circuit.continuous_drop_v:.3f} | {circuit.peak_drop_v:.3f} | "
            f"{circuit.ampacity_a:g} | {circuit.loss_w:.2f} |"
        )
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines += findings_table(findings)
    lines.append("")
    lines.append("## Open items")
    lines.append("")
    for item in model.open_items:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(
        "The inrush against the breaker rating is the reason the protection coordination "
        "carries a LIMITATION in the evidence register instead of a PASS: the analysis "
        "cannot close it without the trip curve."
    )
    lines.append("")
    return "\n".join(lines)


def generated_files(model: PowerModel, findings: list[Finding], circuits: list[Circuit]) -> dict[str, str]:
    """Return the content of every generated evidence file."""
    return {
        "checks.json": render_checks(model, findings, circuits),
        "report.md": render_report(model, findings, circuits),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.power", description=__doc__)
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root (default: the repo)")
    parser.add_argument("--check", action="store_true", help="fail if the evidence is out of date")
    args = parser.parse_args(argv)

    root = Path(args.root)
    model = load_power_model(root)
    findings, circuits = check_power(model)
    files = generated_files(model, findings, circuits)
    failed = [finding for finding in findings if finding.status == "FAIL"]

    if args.check:
        stale = []
        for name, content in files.items():
            path = root / EVIDENCE_DIR / name
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != content:
                stale.append(name)
        if stale:
            print(f"stale power evidence: {', '.join(stale)} — run python -m tools.power")
            return 1
        print(f"power evidence is up to date ({len(findings)} checks, {len(failed)} failed)")
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
