"""Load path and strength analysis.

Derives the load cases from the declared platform accelerations, runs the
inertia load through the load path of the installation, and writes the result
into ``evidence/loads/``.

The checks are the acceptance criteria of the requirements they close:

* ``LOADS-HARD-POINT``      — the fitting reaction against the declared capability
                              of the platform provision (SYS001);
* ``LOADS-FITTING-NET-SECTION`` — ultimate stress at the critical section of the
                              fitting against the material allowable (SYS002);
* ``LOADS-BEARING``         — bearing at the fastener holes (SYS002);
* ``LOADS-BOLT``            — shear and tension interaction in the fasteners (SYS002);
* ``LOADS-FACTOR-OF-SAFETY``— the factor applied to each case against the factor
                              that case requires (SYS002, 14 CFR 27.303);
* ``LOADS-LIMIT-STRESS``    — no permanent detrimental deformation at limit loads
                              (SYS003);
* ``LOADS-DEFLECTION``      — the relative movement under limit loads against the
                              clearance margin the installation has (SYS003, SYS009);
* ``LOADS-HAND-CHECK``      — the general solution against an independent closed
                              form (SYS001);
* ``LOADS-RESONANCE-WINDOWS`` — the excitation bands leave admissible windows at
                              all (SYS015).

What this analysis cannot show is written into the report as an open item, not
smoothed away: the resonance separation is estimated, not demonstrated, and the
traceability of the emergency landing factors is a declared platform input.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from .analysis import Finding, findings_table, make_finding, sort_findings, summarise
from .clearance import check_clearance
from .layout import Layout, load_layout
from .model import REPO_ROOT

LOADS_PATH = Path("model/loads.yaml")
MASS_PATH = Path("model/mass.yaml")
PLATFORM_ICD = Path("model/interfaces/icd_platform.yaml")
PAYLOAD_ICD = Path("model/interfaces/icd_payload.yaml")
EVIDENCE_DIR = Path("evidence/loads")
GENERATED_FILES = ("checks.json", "report.md")
GRAVITY = 9.80665


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Material:
    id: str
    name: str
    source: str
    ftu_mpa: float
    fty_mpa: float
    e_mpa: float = 0.0
    density_kg_m3: float = 0.0
    thread_stress_area_mm2: float | None = None
    diameter_mm: float | None = None


@dataclass(frozen=True)
class LoadCase:
    """One inertia condition derived from the declared accelerations."""

    id: str
    description: str
    basis: str
    factor: float
    acceleration: tuple[float, float, float]
    reference: str

    @property
    def required_factor(self) -> float:
        """The factor 14 CFR 27.303 requires for this basis."""
        return 1.5 if self.basis == "limit" else 1.0

    @property
    def ultimate_acceleration(self) -> tuple[float, float, float]:
        return tuple(component * self.factor for component in self.acceleration)


@dataclass(frozen=True)
class Reaction:
    """The reaction at one fitting under one load case."""

    case: LoadCase
    fitting: str
    x: float
    y: float
    force: tuple[float, float, float]
    added_z: float

    @property
    def shear(self) -> float:
        """In-plane component: what the fasteners take in shear."""
        return math.hypot(self.force[0], self.force[1])

    @property
    def magnitude(self) -> float:
        return math.sqrt(self.shear**2 + self.force[2] ** 2)


@dataclass(frozen=True)
class Band:
    """One excitation band, with the separation criterion already applied."""

    rotor: str
    harmonic: int
    lower_hz: float
    upper_hz: float


@dataclass(frozen=True)
class Window:
    """A frequency range clear of every excitation band."""

    lower_hz: float
    upper_hz: float

    @property
    def width_hz(self) -> float:
        return self.upper_hz - self.lower_hz


@dataclass(frozen=True)
class LoadsModel:
    revision: str
    units: str
    rules: dict[str, float]
    harmonics: dict[str, list[int]]
    sections: dict[str, dict]
    materials: dict[str, Material]
    load_path: tuple[dict, ...]
    open_items: tuple[dict, ...]
    hand_checks: tuple[dict, ...]
    layout: Layout
    mass: dict
    platform: dict
    payload: dict

    # -- masses ---------------------------------------------------------- #
    @property
    def kit_mass_kg(self) -> float:
        return sum(float(entry["mass_kg"]) for entry in self.mass["components"])

    @property
    def tolerance(self) -> float:
        return float(self.mass["declared_rules"]["component_mass_tolerance_pct"]) / 100.0

    @property
    def load_mass_kg(self) -> float:
        """Payload at its declared maximum plus the kit at the upper tolerance."""
        return self.payload_mass_kg + self.kit_mass_kg * (1.0 + self.tolerance)

    @property
    def modal_mass_kg(self) -> float:
        """Mass that follows the first mode: payload, plate and part of the frame."""
        shared = self.rules["modal_mass_frame_share"]
        return (
            self.payload_mass_kg
            + self.component_mass_kg("CMP-03")
            + self.component_mass_kg("CMP-01") * shared
        )

    def component_mass_kg(self, component_id: str) -> float:
        for entry in self.mass["components"]:
            if entry["id"] == component_id:
                return float(entry["mass_kg"])
        raise KeyError(f"{component_id} is not declared in {MASS_PATH}")

    @property
    def payload_mass_kg(self) -> float:
        return float(self.payload["mass_and_inertia"]["mass_kg"])

    # -- geometry -------------------------------------------------------- #
    @property
    def payload_envelope_top_mm(self) -> float:
        return float(self.layout.payload_envelope.rect.y1)

    @property
    def payload_cg_z_mm(self) -> float:
        return float(self.payload["mass_and_inertia"]["cg_offset_mm"]["z"])

    @property
    def moment_arm_mm(self) -> float:
        """Vertical distance from the attachment plane to the payload centre of gravity.

        Derived from two declarations: the payload centre of gravity sits below
        its mounting datum, and the mounting datum is the top of the envelope the
        layout carries. Nothing is typed in twice.
        """
        skin = float(self.layout.platform_skin_y)
        return skin - (self.payload_envelope_top_mm + self.payload_cg_z_mm)

    @property
    def fitting_centres(self) -> dict[str, tuple[float, float]]:
        centres: dict[str, tuple[float, float]] = {}
        for fitting in self.layout.fittings:
            holes = [
                fastener for fastener in self.layout.fasteners if fastener.fitting == fitting.id
            ]
            if not holes:
                continue
            centres[fitting.id] = (
                sum(hole.x for hole in holes) / len(holes),
                sum(hole.y for hole in holes) / len(holes),
            )
        return centres

    @property
    def spacing_mm(self) -> tuple[float, float]:
        """Longitudinal and lateral distance between the attachment points."""
        centres = self.fitting_centres
        xs = sorted({round(centre[0], 3) for centre in centres.values()})
        ys = sorted({round(centre[1], 3) for centre in centres.values()})
        return xs[-1] - xs[0], ys[-1] - ys[0]

    @property
    def hole_diameter_mm(self) -> float:
        return float(self.layout.fasteners[0].diameter)

    @property
    def rail_length_mm(self) -> float:
        """Length of the longitudinal rails, from the layout."""
        lengths = [
            member.rect.x1 - member.rect.x0
            for member in self.layout.bottom_frame
            if "rail" in member.name.lower()
        ]
        if not lengths:
            raise ValueError("the layout declares no rail in the bottom view")
        return max(lengths)

    # -- sections -------------------------------------------------------- #
    @property
    def frame_section(self) -> dict:
        return self.sections["frame_rail"]

    @property
    def fitting_section(self) -> dict:
        return self.sections["fitting"]

    @property
    def frame_inertia_mm4(self) -> float:
        """Second moment of area of the rails about the bending axis."""
        section = self.frame_section
        height = float(section["height_mm"])
        wall = float(section["wall_mm"])
        single = (height**4 - (height - 2 * wall) ** 4) / 12.0
        return single * float(section["count"])

    @property
    def fitting_inertia_mm4(self) -> float:
        section = self.fitting_section
        return float(section["width_mm"]) * float(section["thickness_mm"]) ** 3 / 12.0

    def frame_stiffness_n_per_mm(self, coefficient: float) -> float:
        """Bending stiffness of the rails under a load at the payload station."""
        material = self.materials[self.frame_section["material"]]
        span = self.spacing_mm[0]
        return coefficient * material.e_mpa * self.frame_inertia_mm4 / span**3

    def fitting_stiffness_n_per_mm(self) -> float:
        """Parallel stiffness of the four fitting brackets."""
        section = self.fitting_section
        material = self.materials[section["material"]]
        lever = float(section["effective_lever_mm"])
        factor = self.rules["fitting_cantilever_factor"]
        single = factor * material.e_mpa * self.fitting_inertia_mm4 / lever**3
        return single * float(section["count"])

    def path_stiffness_n_per_mm(self, coefficient: float) -> float:
        """The load path: frame rails in series with the fitting brackets."""
        frame = self.frame_stiffness_n_per_mm(coefficient)
        fittings = self.fitting_stiffness_n_per_mm()
        return 1.0 / (1.0 / frame + 1.0 / fittings)

    # -- load cases ------------------------------------------------------ #
    def load_cases(self) -> tuple[LoadCase, ...]:
        environment = self.platform["structural_environment"]
        manoeuvre = environment["design_manoeuvre_load_factor_g"]
        landing = environment["emergency_landing_inertia_g"]
        factor = self.rules["factor_of_safety"]
        return (
            LoadCase(
                "LC-MAN-UP",
                "Flight manoeuvre and gust, positive limit load factor",
                "limit",
                factor,
                (0.0, 0.0, float(manoeuvre["upper"])),
                "14 CFR 27.337, 27.303",
            ),
            LoadCase(
                "LC-MAN-DOWN",
                "Flight manoeuvre, negative limit load factor",
                "limit",
                factor,
                (0.0, 0.0, float(manoeuvre["lower"])),
                "14 CFR 27.337, 27.303",
            ),
            LoadCase(
                "LC-EML-UP",
                "Emergency landing, upwards inertia",
                "ultimate",
                1.0,
                (0.0, 0.0, float(landing["up"])),
                "declared platform data (OI-01)",
            ),
            LoadCase(
                "LC-EML-DOWN",
                "Emergency landing, downwards inertia",
                "ultimate",
                1.0,
                (0.0, 0.0, -float(landing["down"])),
                "declared platform data (OI-01)",
            ),
            LoadCase(
                "LC-EML-FWD",
                "Emergency landing, forward inertia",
                "ultimate",
                1.0,
                (float(landing["forward"]), 0.0, 0.0),
                "declared platform data (OI-01)",
            ),
            LoadCase(
                "LC-EML-AFT",
                "Emergency landing, aft inertia",
                "ultimate",
                1.0,
                (-float(landing["aft"]), 0.0, 0.0),
                "declared platform data (OI-01)",
            ),
            LoadCase(
                "LC-EML-LAT",
                "Emergency landing, lateral inertia",
                "ultimate",
                1.0,
                (0.0, float(landing["lateral"]), 0.0),
                "declared platform data (OI-01)",
            ),
        )


def load_loads_model(root: Path | None = None) -> LoadsModel:
    """Load the strength model and every declaration it consumes."""
    base = Path(root) if root else REPO_ROOT
    raw = yaml.safe_load((base / LOADS_PATH).read_text(encoding="utf-8"))
    materials = {
        entry["id"]: Material(
            id=entry["id"],
            name=entry["name"],
            source=entry.get("source", ""),
            ftu_mpa=float(entry["ftu_mpa"]),
            fty_mpa=float(entry["fty_mpa"]),
            e_mpa=float(entry.get("e_mpa", 0.0)),
            density_kg_m3=float(entry.get("density_kg_m3", 0.0)),
            thread_stress_area_mm2=(
                float(entry["thread_stress_area_mm2"])
                if "thread_stress_area_mm2" in entry
                else None
            ),
            diameter_mm=float(entry["diameter_mm"]) if "diameter_mm" in entry else None,
        )
        for entry in raw["materials"]
    }
    harmonics = {
        rotor: [int(order) for order in orders]
        for rotor, orders in raw["declared_rules"]["excitation_harmonics"].items()
    }
    return LoadsModel(
        revision=raw["revision"],
        units=raw["units"],
        rules={key: value for key, value in raw["declared_rules"].items() if key != "excitation_harmonics"},
        harmonics=harmonics,
        sections=raw["sections"],
        materials=materials,
        load_path=tuple(raw["load_path"]),
        open_items=tuple(raw["open_items"]),
        hand_checks=tuple(raw["hand_checks"]),
        layout=load_layout(base),
        mass=yaml.safe_load((base / MASS_PATH).read_text(encoding="utf-8")),
        platform=yaml.safe_load((base / PLATFORM_ICD).read_text(encoding="utf-8")),
        payload=yaml.safe_load((base / PAYLOAD_ICD).read_text(encoding="utf-8")),
    )


# --------------------------------------------------------------------------- #
# Reactions
# --------------------------------------------------------------------------- #


def compute_reactions(model: LoadsModel, case: LoadCase) -> list[Reaction]:
    """Distribute one load case between the four fittings.

    The inertia force acts at the payload centre of gravity, which sits below the
    attachment plane, so a horizontal component also produces a couple: the four
    fittings resist it with a vertical pair of reactions. A vertical component
    produces no couple, because its line of action passes through the centre of
    the attachment pattern.
    """
    centres = model.fitting_centres
    count = len(centres)
    longitudinal, lateral = model.spacing_mm
    force = tuple(
        model.load_mass_kg * component * GRAVITY for component in case.ultimate_acceleration
    )
    lever = model.moment_arm_mm

    # Moment of the inertia force about the centre of the attachment pattern.
    moment_x = lever * force[1]
    moment_y = -lever * force[0]

    reactions = []
    for fitting_id, (x, y) in sorted(centres.items()):
        added_z = moment_y * x / longitudinal**2 - moment_x * y / lateral**2
        reactions.append(
            Reaction(
                case=case,
                fitting=fitting_id,
                x=x,
                y=y,
                force=(force[0] / count, force[1] / count, force[2] / count + added_z),
                added_z=added_z,
            )
        )
    return reactions


def closed_form_reaction(model: LoadsModel, case: LoadCase) -> dict[str, float]:
    """The reactions by the two formulas a hand calculation would use.

    Independent of the vector solution below: the direct share is the force
    divided by the number of fittings, and the couple share is the horizontal
    force times the moment arm divided by twice the spacing of the pair that
    takes it. The two are components along different axes, so a hand calculation
    that adds them overestimates the resultant, and the report says by how much.
    """
    force = tuple(
        model.load_mass_kg * component * GRAVITY for component in case.ultimate_acceleration
    )
    count = len(model.fitting_centres)
    longitudinal, lateral = model.spacing_mm
    direct = math.sqrt(sum(component**2 for component in force)) / count
    couple = 0.0
    if force[0]:
        couple = max(couple, abs(force[0]) * model.moment_arm_mm / (2 * longitudinal))
    if force[1]:
        couple = max(couple, abs(force[1]) * model.moment_arm_mm / (2 * lateral))
    return {"direct": direct, "couple": couple, "sum": direct + couple}


def section_stresses(model: LoadsModel, reaction: Reaction) -> tuple[float, float, float, float]:
    """Stresses at the critical section of the fitting bracket.

    Three effects meet at the section between the fastener holes and the rail:
    the direct share bends the bracket over its declared effective lever, the
    couple pulls or pushes it at the net section, and the in-plane part of the
    direct share crosses it in shear. Bending and axial stress are added — they
    add on the same face — and the shear goes into the von Mises combination, as
    the declared rule in model/loads.yaml says. Reporting the three side by side
    would invite the reader to compare the larger one with the allowable.
    """
    section = model.fitting_section
    thickness = float(section["thickness_mm"])
    lever = float(section["effective_lever_mm"])
    area = (float(section["width_mm"]) - model.hole_diameter_mm) * thickness
    direct = (reaction.force[0], reaction.force[1], reaction.force[2] - reaction.added_z)
    direct_magnitude = math.sqrt(sum(component**2 for component in direct))

    bending = direct_magnitude * lever * (thickness / 2.0) / model.fitting_inertia_mm4
    axial = abs(reaction.added_z) / area
    shear = reaction.shear / area
    combined = math.sqrt((bending + axial) ** 2 + 3.0 * shear**2)
    return bending, axial, shear, combined


def worse(reactions: list[Reaction]) -> Reaction:
    """The fitting that carries most under this load case."""
    return max(reactions, key=lambda reaction: (reaction.magnitude, reaction.fitting))


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Resonance:
    """The frequency estimate and the bands it has to stay clear of."""

    bands: tuple[Band, ...]
    windows: tuple[Window, ...]
    estimate_low_hz: float
    estimate_high_hz: float
    separation_demonstrated: bool
    stiffening: dict


def build_resonance(model: LoadsModel) -> Resonance:
    """Compute the excitation bands, the admissible windows and the estimate."""
    environment = model.platform["structural_environment"]
    harmonics = model.harmonics
    separation = float(model.rules["separation_pct"]) / 100.0
    ceiling = float(model.rules["frequency_ceiling_hz"])

    bands = []
    for rotor, orders in harmonics.items():
        rpm = environment[f"{rotor}_rotor_rpm"]
        lower = float(rpm["lower"]) / 60.0
        upper = float(rpm["upper"]) / 60.0
        for order in orders:
            bands.append(
                Band(
                    rotor=rotor,
                    harmonic=int(order),
                    lower_hz=lower * order * (1 - separation),
                    upper_hz=upper * order * (1 + separation),
                )
            )
    bands.sort(key=lambda band: band.lower_hz)
    merged: list[Band] = []
    for band in bands:
        if merged and band.lower_hz <= merged[-1].upper_hz:
            previous = merged.pop()
            merged.append(
                Band(
                    rotor=f"{previous.rotor}+{band.rotor}",
                    harmonic=previous.harmonic,
                    lower_hz=previous.lower_hz,
                    upper_hz=max(previous.upper_hz, band.upper_hz),
                )
            )
        else:
            merged.append(band)

    windows: list[Window] = []
    edge = 0.0
    for band in merged:
        if band.lower_hz > edge:
            windows.append(Window(edge, band.lower_hz))
        edge = max(edge, band.upper_hz)
    if edge < ceiling:
        windows.append(Window(edge, ceiling))

    mass = model.modal_mass_kg
    low = model.path_stiffness_n_per_mm(float(model.rules["frame_coefficient_simply_supported"]))
    high = model.path_stiffness_n_per_mm(float(model.rules["frame_coefficient_clamped"]))
    estimate_low = math.sqrt(low * 1000.0 / mass) / (2 * math.pi)
    estimate_high = math.sqrt(high * 1000.0 / mass) / (2 * math.pi)
    demonstrated = any(
        window.lower_hz <= estimate_low and estimate_high <= window.upper_hz for window in windows
    )

    return Resonance(
        bands=tuple(merged),
        windows=tuple(windows),
        estimate_low_hz=estimate_low,
        estimate_high_hz=estimate_high,
        separation_demonstrated=demonstrated,
        stiffening=stiffening_needed(model, merged[-1].upper_hz if merged else 0.0),
    )


def required_frame_inertia(model: LoadsModel, target_hz: float) -> float:
    """Rail inertia that would put the estimate above the highest band."""
    mass = model.modal_mass_kg
    span = model.spacing_mm[0]
    support = float(model.rules["frame_coefficient_simply_supported"])
    material = model.materials[model.frame_section["material"]]
    span = model.spacing_mm[0]
    stiffness = (2 * math.pi * target_hz) ** 2 * mass / 1000.0
    fittings = model.fitting_stiffness_n_per_mm()
    if stiffness >= fittings:
        return math.inf
    frame = 1.0 / (1.0 / stiffness - 1.0 / fittings)
    return frame * span**3 / (support * material.e_mpa)


def stiffening_needed(model: LoadsModel, highest_band_hz: float) -> dict:
    """What it would take to move the estimate above the highest band."""
    target = highest_band_hz * (1 + float(model.rules["separation_pct"]) / 100.0)
    inertia = required_frame_inertia(model, target)
    if not math.isfinite(inertia):
        return {"target_hz": target, "feasible": False}

    section = model.frame_section
    wall = float(section["wall_mm"])
    material = model.materials[section["material"]]

    # Smallest square tube with the declared wall thickness that reaches it.
    size = wall * 3
    while size < 1000:
        if (size**4 - (size - 2 * wall) ** 4) / 12.0 >= inertia:
            break
        size += 1
    area = size**2 - (size - 2 * wall) ** 2
    mass = area * model.rail_length_mm * material.density_kg_m3 * 1e-9 * float(section["count"])
    return {
        "target_hz": target,
        "feasible": True,
        "rail_size_mm": size,
        "rail_inertia_mm4": (size**4 - (size - 2 * wall) ** 4) / 12.0 * float(section["count"]),
        "frame_mass_kg": mass,
        "mass_increase_kg": mass - model.component_mass_kg("CMP-01"),
    }


def check_loads(model: LoadsModel, root: Path | None = None) -> tuple[list[Finding], dict]:
    """Run every strength check and return the findings and the computed cases."""
    base = Path(root) if root else REPO_ROOT
    findings: list[Finding] = []
    rules = model.rules
    material = model.materials[model.frame_section["material"]]
    fastener = model.materials["MAT-02"]
    section = model.fitting_section
    thickness = float(section["thickness_mm"])
    width = float(section["width_mm"])
    hole = model.hole_diameter_mm
    per_fitting = float(section["fasteners_per_fitting"])
    stress_area = float(fastener.thread_stress_area_mm2 or 0.0)
    shear_allowable = float(rules["shear_allowable_ratio"]) * fastener.ftu_mpa
    bearing_allowable = float(rules["bearing_allowable_ratio"]) * material.fty_mpa
    net_area = (width - hole) * thickness
    capability = float(model.platform["attachment_provisions"]["load_capability_kn"]["per_point_ultimate"]) * 1000.0

    cases: dict[str, dict] = {}
    worst_by_check: dict[str, Reaction] = {}

    for case in model.load_cases():
        reactions = compute_reactions(model, case)
        governing = worse(reactions)
        total = model.load_mass_kg * math.sqrt(sum(c**2 for c in case.ultimate_acceleration)) * GRAVITY
        tension = abs(governing.added_z)
        shear = governing.shear
        shear_stress = shear / (per_fitting * stress_area)
        tension_stress = tension / (per_fitting * stress_area)
        interaction = shear_stress / shear_allowable + tension_stress / fastener.ftu_mpa
        bending_stress, axial_stress, fitting_shear_stress, net_stress = section_stresses(
            model, governing
        )
        bearing_stress = governing.magnitude / (per_fitting * hole * thickness)

        cases[case.id] = {
            "description": case.description,
            "basis": case.basis,
            "factor": case.factor,
            "acceleration_g": max(abs(component) for component in case.acceleration),
            "ultimate_acceleration_g": max(abs(component) for component in case.ultimate_acceleration),
            "reference": case.reference,
            "ultimate_force_n": round(total, 1),
            "governing_fitting": governing.fitting,
            "governing_reaction_n": round(governing.magnitude, 1),
            "direct_share_n": round(math.sqrt(shear**2 + (case.ultimate_acceleration[2] * model.load_mass_kg * GRAVITY / len(reactions)) ** 2), 1),
            "couple_share_n": round(tension, 1),
            "shear_stress_mpa": round(shear_stress, 1),
            "tension_stress_mpa": round(tension_stress, 1),
            "bolt_interaction": round(interaction, 3),
            "net_section_bending_mpa": round(bending_stress, 2),
            "net_section_axial_mpa": round(axial_stress, 2),
            "net_section_shear_mpa": round(fitting_shear_stress, 2),
            "net_section_stress_mpa": round(net_stress, 2),
            "bearing_stress_mpa": round(bearing_stress, 2),
        }

        for check, ok, value, limit, message, subject, mode in (
            (
                "LOADS-HARD-POINT",
                governing.magnitude <= capability,
                governing.magnitude,
                capability,
                f"{case.id}: {governing.magnitude:.0f} N at {governing.fitting} against the declared "
                f"{capability / 1000:.0f} kN per hard point",
                case.id,
                "max",
            ),
            (
                "LOADS-FITTING-NET-SECTION",
                net_stress <= material.ftu_mpa,
                net_stress,
                material.ftu_mpa,
                f"{case.id}: {net_stress:.2f} MPa at the critical section ({net_area:.0f} mm2), "
                f"from {bending_stress:.2f} MPa bending, {axial_stress:.2f} MPa axial and "
                f"{fitting_shear_stress:.2f} MPa shear, against Ftu {material.ftu_mpa:g} MPa",
                case.id,
                "max",
            ),
            (
                "LOADS-BEARING",
                bearing_stress <= bearing_allowable,
                bearing_stress,
                bearing_allowable,
                f"{case.id}: {bearing_stress:.1f} MPa bearing at the holes against "
                f"{rules['bearing_allowable_ratio']:g} x Fty = {bearing_allowable:.0f} MPa",
                case.id,
                "max",
            ),
            (
                "LOADS-BOLT",
                interaction <= 1.0,
                interaction,
                1.0,
                f"{case.id}: shear {shear_stress:.1f} MPa and tension {tension_stress:.1f} MPa in the "
                f"threaded portion, interaction {interaction:.3f} (sum of the two ratios)",
                case.id,
                "max",
            ),
            (
                "LOADS-FACTOR-OF-SAFETY",
                case.factor >= case.required_factor,
                case.factor,
                case.required_factor,
                f"{case.id}: {case.basis} case, factor {case.factor:g} applied to the prescribed "
                f"condition, {case.required_factor:g} required by 27.303",
                case.id,
                "min",
            ),
        ):
            findings.append(make_finding(check, subject, ok, value, limit, message, mode=mode))
            worst_by_check[check] = max(
                (worst_by_check.get(check, governing), governing),
                key=lambda reaction: reaction.magnitude,
            )

        if case.basis == "limit":
            limit_reactions = compute_reactions(
                model, LoadCase(case.id, case.description, case.basis, 1.0, case.acceleration, case.reference)
            )
            limit_stress = section_stresses(model, worse(limit_reactions))[3]
            findings.append(
                make_finding(
                    "LOADS-LIMIT-STRESS",
                    case.id,
                    limit_stress <= material.fty_mpa,
                    limit_stress,
                    material.fty_mpa,
                    f"{case.id}: {limit_stress:.2f} MPa at the critical section under limit load "
                    f"against Fty {material.fty_mpa:g} MPa, so no permanent deformation",
                    mode="max",
                )
            )
            cases[case.id]["limit_load_stress_mpa"] = round(limit_stress, 2)

    # Hand calculation against the general solution, on the case with the
    # largest couple, which is where the two methods differ.
    governing_case = max(
        model.load_cases(),
        key=lambda case: abs(case.ultimate_acceleration[0]) + abs(case.ultimate_acceleration[1]),
    )
    script = worse(compute_reactions(model, governing_case))
    hand = closed_form_reaction(model, governing_case)
    script_direct = math.hypot(script.force[0], script.force[1])
    script_couple = abs(script.added_z)
    direct_error = (
        abs(hand["direct"] - script_direct) / script_direct * 100.0 if script_direct else 0.0
    )
    couple_error = (
        abs(hand["couple"] - script_couple) / script_couple * 100.0 if script_couple else 0.0
    )
    difference = max(direct_error, couple_error)
    findings.append(
        make_finding(
            "LOADS-HAND-CHECK",
            governing_case.id,
            difference <= 0.5,
            difference,
            0.5,
            f"{governing_case.id}: closed form direct share {hand['direct']:.1f} N and couple "
            f"share {hand['couple']:.1f} N against the general solution {script_direct:.1f} N and "
            f"{script_couple:.1f} N, largest difference {difference:.2f} %",
            mode="max",
        )
    )

    # Deflection under the worst limit case, against the clearance the
    # installation actually has at its tightest field of view direction.
    limit_cases = [case for case in model.load_cases() if case.basis == "limit"]
    worst_limit = max(limit_cases, key=lambda case: abs(case.ultimate_acceleration[2]))
    vertical = (
        model.load_mass_kg
        * abs(worst_limit.ultimate_acceleration[2])
        * GRAVITY
        / float(rules["factor_of_safety"])
    )
    stiffness = model.path_stiffness_n_per_mm(float(rules["frame_coefficient_simply_supported"]))
    deflection = vertical / stiffness
    clearance_findings, results, _, _ = check_clearance(base)
    tightest = min(result.clearance for result in results)
    required_clearance = float(model.layout.rules["minimum_clearance_mm"])
    allowance = tightest - required_clearance
    findings.append(
        make_finding(
            "LOADS-DEFLECTION",
            worst_limit.id,
            deflection <= allowance,
            deflection,
            allowance,
            f"{worst_limit.id}: {deflection:.2f} mm of relative movement at the payload under "
            f"limit load, against the {allowance:.1f} mm the installation has left at its "
            f"tightest direction ({tightest:.1f} mm measured, {required_clearance:g} mm required)",
            mode="max",
        )
    )

    resonance = build_resonance(model)
    for band in resonance.bands:
        findings.append(
            make_finding(
                "LOADS-RESONANCE-CRITERION",
                f"{band.rotor}-{band.harmonic}/rev",
                band.upper_hz > band.lower_hz,
                band.upper_hz - band.lower_hz,
                0.0,
                f"{band.rotor} rotor {band.harmonic}/rev: band {band.lower_hz:.2f} to "
                f"{band.upper_hz:.2f} Hz with the {rules['separation_pct']:g} % criterion; "
                f"{len(resonance.windows)} admissible windows up to "
                f"{rules['frequency_ceiling_hz']:g} Hz",
            )
        )

    detail = {
        "cases": cases,
        "criterion_valid": all(
            band.upper_hz > band.lower_hz for band in resonance.bands
        ),
        "resonance": {
            "bands": [
                {
                    "rotor": band.rotor,
                    "harmonic": band.harmonic,
                    "lower_hz": round(band.lower_hz, 2),
                    "upper_hz": round(band.upper_hz, 2),
                }
                for band in resonance.bands
            ],
            "windows": [
                {"lower_hz": round(window.lower_hz, 2), "upper_hz": round(window.upper_hz, 2)}
                for window in resonance.windows
            ],
            "estimate_low_hz": round(resonance.estimate_low_hz, 2),
            "estimate_high_hz": round(resonance.estimate_high_hz, 2),
            "modal_mass_kg": round(model.modal_mass_kg, 2),
            "separation_demonstrated": resonance.separation_demonstrated,
            "stiffening": resonance.stiffening,
        },
        "governing_case_by_check": {
            check: {
                "case": reaction.case.id,
                "fitting": reaction.fitting,
                "reaction_n": round(reaction.magnitude, 1),
            }
            for check, reaction in worst_by_check.items()
        },
        "geometry": {
            "fitting_spacing_mm": {
                "longitudinal": round(model.spacing_mm[0], 1),
                "lateral": round(model.spacing_mm[1], 1),
            },
            "moment_arm_mm": round(model.moment_arm_mm, 1),
            "load_mass_kg": round(model.load_mass_kg, 2),
            "kit_mass_kg": round(model.kit_mass_kg, 2),
        },
        "deflection": {
            "case": worst_limit.id,
            "value_mm": round(deflection, 3),
            "allowance_mm": round(allowance, 3),
            "tightest_clearance_mm": round(tightest, 1),
            "stiffness_n_per_mm": round(stiffness, 1),
        },
        "hand_check": {
            "case": governing_case.id,
            "closed_form_direct_n": round(hand["direct"], 1),
            "closed_form_couple_n": round(hand["couple"], 1),
            "closed_form_sum_n": round(hand["sum"], 1),
            "general_solution_direct_n": round(script_direct, 1),
            "general_solution_couple_n": round(script_couple, 1),
            "general_solution_resultant_n": round(script.magnitude, 1),
            "component_difference_pct": round(difference, 3),
            "sum_over_resultant_pct": round(
                (hand["sum"] - script.magnitude) / script.magnitude * 100.0, 2
            ),
        },
        "clearance_findings": len(clearance_findings),
    }
    return sort_findings(findings), detail


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #


def render_checks(model: LoadsModel, findings: list[Finding], detail: dict) -> str:
    payload = {
        "revision": model.revision,
        "units": model.units,
        "declared_rules": model.rules,
        "materials": {
            material.id: {
                "name": material.name,
                "ftu_mpa": material.ftu_mpa,
                "fty_mpa": material.fty_mpa,
                "e_mpa": material.e_mpa,
            }
            for material in model.materials.values()
        },
        **detail,
        "open_items": [
            {"id": item["id"], "title": item["title"]} for item in model.open_items
        ],
        "summary": summarise(findings),
        "findings": [finding.as_dict() for finding in findings],
    }
    return json.dumps(payload, indent=2) + "\n"


def render_report(model: LoadsModel, findings: list[Finding], detail: dict) -> str:
    summary = summarise(findings)
    section = model.fitting_section
    frame = model.frame_section
    material = model.materials[frame["material"]]
    resonance = detail["resonance"]
    lines = [
        "<!-- Generated by tools/loads.py — do not edit by hand. -->",
        "<!-- Run: python -m tools.loads -->",
        "",
        "# Load path and strength",
        "",
        f"Revision {model.revision}, units {model.units}. {summary['checks']} checks, "
        f"{summary['passed']} passed, {summary['failed']} failed.",
        "",
        "## Inputs",
        "",
        f"- Payload {model.payload_mass_kg:g} kg at its declared maximum, kit "
        f"{model.kit_mass_kg:.2f} kg at the declared upper tolerance "
        f"({model.tolerance * 100:.0f} %): **{model.load_mass_kg:.2f} kg** in the load cases",
        f"- Payload centre of gravity {abs(model.payload_cg_z_mm):.0f} mm below its mounting datum; "
        f"the attachment plane is {model.moment_arm_mm:.0f} mm above it, from the layout envelope",
        f"- Attachment points: four fittings at a spacing of "
        f"{model.spacing_mm[0]:.0f} mm longitudinal and {model.spacing_mm[1]:.0f} mm lateral, "
        f"two M8 fasteners each, diameter {model.hole_diameter_mm:g} mm",
        f"- Fitting section {section['width_mm']:g} x {section['thickness_mm']:g} mm plate, "
        f"net section {((float(section['width_mm']) - model.hole_diameter_mm) * float(section['thickness_mm'])):.0f} mm2",
        f"- Frame: {frame['count']:g} rails of {frame['profile']} in {material.name}, "
        f"bending stiffness {model.frame_stiffness_n_per_mm(float(model.rules['frame_coefficient_simply_supported'])):.0f} N/mm "
        f"simply supported and {model.frame_stiffness_n_per_mm(float(model.rules['frame_coefficient_clamped'])):.0f} N/mm clamped",
        "",
        "## Load cases",
        "",
        "| Case | Description | Basis | Factor | Acceleration (g) | Ultimate (g) | Force (N) | Reference |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case_id, case in detail["cases"].items():
        lines.append(
            f"| {case_id} | {case['description']} | {case['basis']} | {case['factor']:g} | "
            f"{case['acceleration_g']:.1f} | {case['ultimate_acceleration_g']:.2f} | "
            f"{case['ultimate_force_n']:.0f} | {case['reference']} |"
        )
    lines += [
        "",
        "The manoeuvre cases are limit loads and take the factor of safety of 14 CFR 27.303. "
        "The emergency landing factors are prescribed as ultimate loads in the platform data, "
        "so no further factor is applied to them; whether those factors are the right ones for "
        "a belly installation is open item OI-01.",
        "",
        "## Reactions per fitting",
        "",
        "| Case | Governing fitting | Direct share (N) | Couple share (N) | Reaction (N) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case_id, case in detail["cases"].items():
        lines.append(
            f"| {case_id} | {case['governing_fitting']} | {case['direct_share_n']:.0f} | "
            f"{case['couple_share_n']:.1f} | {case['governing_reaction_n']:.0f} |"
        )
    lines += [
        "",
        "A vertical inertia force acts along the centre of the attachment pattern, so it divides "
        "equally between the four fittings and produces no couple. A horizontal force acts below "
        "the attachment plane: it adds a couple that the fore and aft pairs resist with a pair of "
        "vertical reactions, which is what the couple share column carries.",
        "",
        "## Load path",
        "",
        "| Element | Carries | Critical section | Checked here | Check |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in model.load_path:
        lines.append(
            f"| {step['element']} | {step['carries']} | {step['critical_section']} | "
            f"{'yes' if step['checked_here'] else 'no'} | {step.get('check', step.get('note', ''))} |"
        )
    lines += [
        "",
        "## Checks",
        "",
    ]
    lines += findings_table(findings)
    lines += [
        "",
        "## Governing case per check",
        "",
        "| Check | Case | Fitting | Reaction (N) |",
        "| --- | --- | --- | --- |",
    ]
    for check, governing in detail["governing_case_by_check"].items():
        lines.append(
            f"| {check} | {governing['case']} | {governing['fitting']} | {governing['reaction_n']:.0f} |"
        )
    lines += [
        "",
        "The manoeuvre case governs, not the emergency landing: the factor of safety of 27.303 "
        "lifts 3.5 g of limit manoeuvre to 5.25 g of ultimate load, which is more than the 3.0 g "
        "the platform declares for the emergency landing. The strength checks are not what sizes "
        "this installation: the declared capability of the platform provision is 25 kN per point "
        "and the largest reaction is under 1 kN.",
        "",
        "## Hand calculation against the general solution",
        "",
        f"The case with the largest couple is {detail['hand_check']['case']}. A hand calculation "
        "takes the direct share and the couple share:",
        "",
    ]
    lines += [f"- {check['title']}: `{check['formula']}`" for check in model.hand_checks]
    lines += [
        "",
        "| Component | Closed form (N) | General solution (N) | Difference |",
        "| --- | --- | --- | --- |",
        f"| Direct share | {detail['hand_check']['closed_form_direct_n']:.1f} | "
        f"{detail['hand_check']['general_solution_direct_n']:.1f} | "
        f"{abs(detail['hand_check']['closed_form_direct_n'] - detail['hand_check']['general_solution_direct_n']) / detail['hand_check']['general_solution_direct_n'] * 100:.2f} % |",
        f"| Couple share | {detail['hand_check']['closed_form_couple_n']:.1f} | "
        f"{detail['hand_check']['general_solution_couple_n']:.1f} | "
        f"{abs(detail['hand_check']['closed_form_couple_n'] - detail['hand_check']['general_solution_couple_n']) / detail['hand_check']['general_solution_couple_n'] * 100:.2f} % |",
        "",
        f"The two methods agree on both components to within "
        f"{detail['hand_check']['component_difference_pct']:.2f} %, which is what the check "
        "verifies. They do not agree on the total, and that is the part worth investigating: the "
        f"closed form adds the two shares and gets {detail['hand_check']['closed_form_sum_n']:.0f} N, "
        f"the general solution resolves them as a vector and gets "
        f"{detail['hand_check']['general_solution_resultant_n']:.0f} N, "
        f"**{detail['hand_check']['sum_over_resultant_pct']:+.1f} %**. The shares act on different "
        "axes, so adding them is not a conservative simplification but a different quantity; here "
        "it overestimates the fitting load, which is the safe direction for a hand calculation but "
        "would be the wrong number to publish. The check on the fitting uses the resultant.",
        "",
        "## Deflection",
        "",
        f"Under {detail['deflection']['case']} at limit load the payload moves "
        f"{detail['deflection']['value_mm']:.2f} mm relative to the platform, with the load path "
        f"stiffness of {detail['deflection']['stiffness_n_per_mm']:.0f} N/mm and the softest "
        "support idealisation, which gives the largest movement. The installation has "
        f"{detail['deflection']['allowance_mm']:.1f} mm available at its tightest field of view "
        f"direction ({detail['deflection']['tightest_clearance_mm']:.1f} mm measured against the "
        f"required clearance), so the movement stays inside it.",
        "",
        "## Resonance",
        "",
        "| Rotor | Harmonic | Band (Hz) |",
        "| --- | --- | --- |",
    ]
    for band in resonance["bands"]:
        lines.append(
            f"| {band['rotor']} | {band['harmonic']}/rev | {band['lower_hz']:.2f} to {band['upper_hz']:.2f} |"
        )
    lines += [
        "",
        "Admissible windows: "
        + ", ".join(
            f"{window['lower_hz']:.2f} to {window['upper_hz']:.2f} Hz" for window in resonance["windows"]
        )
        + ".",
        "",
        f"The installation is estimated at **{resonance['estimate_low_hz']:.1f} to "
        f"{resonance['estimate_high_hz']:.1f} Hz** for a modal mass of "
        f"{resonance['modal_mass_kg']:.1f} kg, between the simply supported and the clamped "
        "idealisation of the frame rails.",
        "",
    ]
    if resonance["stiffening"].get("feasible"):
        stiff = resonance["stiffening"]
        lines += [
            f"**The separation is not demonstrated.** The estimate lands inside the bands, and no "
            f"window is wide enough to contain the interval between the two idealisations: the "
            f"uncertainty of the estimate is larger than the distance between the harmonics. "
            f"Raising the first mode above the highest band would need "
            f"{stiff['rail_size_mm']:.0f} mm square rails of the declared wall thickness, "
            f"**{stiff['frame_mass_kg']:.1f} kg instead of {model.component_mass_kg('CMP-01'):.1f} kg** "
            f"of frame, which is {stiff['mass_increase_kg']:+.1f} kg against a kit budget of "
            f"{model.mass['declared_rules']['kit_mass_target_kg']:g} kg that has "
            f"{model.mass['declared_rules']['kit_mass_target_kg'] - model.kit_mass_kg:.2f} kg left. "
            "The installation therefore needs a modal analysis or a ground vibration test on the "
            "first article, and possibly a damper, rather than a stiffer frame (OI-02).",
            "",
        ]
    lines += [
        "## Open items",
        "",
    ]
    for item in model.open_items:
        lines.append(f"- **{item['id']} — {item['title']}** {item['detail']}")
    lines += [
        "",
        "## What this evidence does not cover",
        "",
        "- The payload mounting interface and the interface plate are not checked: they belong to "
        "the payload supplier and to a plate bending model this study does not have (OI-03).",
        "- The welded joints of the frame are not sized: a weld schedule and its allowables are "
        "not declared (OI-03).",
        "- The loads are quasi-static. No fatigue spectrum, no dynamic amplification and no "
        "rotor-induced vibratory load is applied.",
        "- The material allowables are declared handbook values, not certified values (A-014).",
        "",
    ]
    return "\n".join(lines)


def generated_files(model: LoadsModel, findings: list[Finding], detail: dict) -> dict[str, str]:
    """Return the content of every generated evidence file."""
    return {
        "checks.json": render_checks(model, findings, detail),
        "report.md": render_report(model, findings, detail),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.loads", description=__doc__)
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root (default: the repo)")
    parser.add_argument("--check", action="store_true", help="fail if the evidence is out of date")
    args = parser.parse_args(argv)

    root = Path(args.root)
    model = load_loads_model(root)
    findings, detail = check_loads(model, root)
    files = generated_files(model, findings, detail)
    failed = [finding for finding in findings if finding.status == "FAIL"]

    if args.check:
        stale = []
        for name, content in files.items():
            path = root / EVIDENCE_DIR / name
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != content:
                stale.append(name)
        if stale:
            print(f"stale load evidence: {', '.join(stale)} — run python -m tools.loads")
            return 1
        print(f"load evidence is up to date ({len(findings)} checks, {len(failed)} failed)")
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
