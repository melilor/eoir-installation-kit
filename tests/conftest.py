"""Shared fixtures: small, hand-built models for the rule tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.model import (  # noqa: E402  (path setup must run first)
    ArchitectureElement,
    Assumption,
    Evidence,
    Model,
    Requirement,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_model(
    requirements=None,
    verifications=None,
    functions=None,
    components=None,
    interfaces=None,
    externals=("EXT-PLATFORM",),
    evidence=None,
    assumptions=None,
    doorstop_issues=(),
) -> Model:
    """Build a small valid model, letting each test override one part."""
    requirements = requirements if requirements is not None else {
        "SYS001": Requirement(
            uid="SYS001",
            header="Mechanical interface",
            text="The kit shall attach the payload.",
            ref="STD 14 CFR 27.1301",
            active=True,
            document="SYS",
        )
    }
    verifications = verifications if verifications is not None else {
        "VER001": Requirement(
            uid="VER001",
            header="Attachment verification",
            text="Verify by inspection that the kit is attached.",
            ref="",
            active=True,
            links=("SYS001",),
            document="VER",
        )
    }
    functions = functions if functions is not None else (
        ArchitectureElement(id="FCT-01", name="Attach", requirements=("SYS001",)),
    )
    components = components if components is not None else (
        ArchitectureElement(
            id="CMP-01", name="Frame", requirements=("SYS001",), realizes=("FCT-01",)
        ),
    )
    interfaces = interfaces if interfaces is not None else ()
    evidence = evidence if evidence is not None else {
        "VER001": Evidence(
            verification="VER001",
            method="inspection",
            status="FUTURE",
            plan="issues/01-foundation",
        )
    }
    assumptions = assumptions if assumptions is not None else {}
    return Model(
        requirements=requirements,
        verifications=verifications,
        functions=functions,
        components=components,
        interfaces=interfaces,
        externals=externals,
        evidence=evidence,
        assumptions=assumptions,
        doorstop_issues=doorstop_issues,
    )


@pytest.fixture
def model() -> Model:
    return build_model()
