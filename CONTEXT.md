# Glossary

The vocabulary of this repository. One term, one meaning. If a document in this repository
uses a word that is not here and is not standard domain language, that is a gap.

- **Installation kit (the kit)**: the product under study. The structural attachment, the
  electrical and avionic interfaces, the bonding, the environmental provisions and the
  documentation that let the platform carry the payload. The kit is the subject of every
  requirement in this repository.
- **Payload**: the stabilised EO/IR unit that the kit carries. It is an input to the study,
  described by declared interface data, never by a supplier data sheet.
- **Platform**: the CS-27 class light helicopter or tactical UAV that carries the kit. Its
  structure, bus and mission system are the external boundary of the study.
- **Requirement (`SYS`)**: a statement the installation must satisfy, written with a
  *source* (`STD` citation or `ASM` assumption) and an acceptance criterion that can be
  verified. Requirements live in the Doorstop document under `model/requirements`.
- **Verification case (`VER`)**: the statement of *how* a requirement is shown to be
  satisfied, with a method. A verification case links to the requirement it closes and has
  exactly one evidence record.
- **Method**: how a verification case is executed — `analysis`, `simulation`, `test`,
  `inspection`, `demonstration` or `review`.
- **Evidence**: the state of a verification case: the method, the status, the artifact and
  the plan. Evidence lives in `model/evidence.yaml`, one record per verification case.
- **Artifact**: the file in this repository that contains the result of a verification.
  A `PASS` or `WARN` status without an artifact that exists is a broken claim, and the
  validator rejects it.
- **Status**: `PASS`, `WARN`, `FAIL`, `LIMITATION`, `BLOCKED` or `FUTURE`. `FUTURE` means
  the verification has not been executed and carries the ticket that will execute it.
  A `WARN` is never promoted to a `PASS`.
- **Declared assumption (`ASM`)**: an input the study needs and cannot derive — payload
  mass and envelope, platform data, environmental categories, maintainability targets.
  Assumptions have a status (`OPEN`, `CLOSED`, `REJECTED`) and are the first thing to
  challenge. Evidence produced against an `OPEN` assumption is reported as a warning. An
  assumption that rests on interface data declares it in `data_file`, and the `ASM-FILE`
  rule rejects a pointer to a file that does not exist.
- **Layout**: the dimensional definition of the kit, in `model/layout.yaml` at revision A:
a two-view 2D envelope model (side and bottom view) with rectangles, circles and orthogonal
harness paths. It is the single source of truth for every dimension, and the geometric checks
in `tools/layout.py` run against it.
- **Layout check**: one of the geometric or data checks on the layout, each with a stable
identifier (`REMOVAL-CORRIDOR`, `CONNECTOR-ACCESS`, `FITTING-EDGE-DISTANCE`, `HOLE-PITCH`,
`FASTENER-LOCKING`, `INSPECTION-ACCESS`, `HARNESS-ORTHOGONAL`, `BEND-RADIUS`,
`CLAMP-ON-PATH`, `CLAMP-SPACING`, `HARNESS-CLEARANCE`, `ICD-CONSISTENCY`). A failing check
stops the tool and names the violated constraint.
- **Swept sector**: the volume the rotating head of the payload sweeps around its gimbal
  axis, bounded by the declared elevation range. In the side view it is a circular sector;
  `tools/clearance.py` samples it with one ray per declared step and checks every ray against
  the structure and the platform skin. The sector exists only with the payload installed.
- **Interface control data (ICD)**: the declared values of the payload and the platform
  interfaces — mass and inertia, envelope, mounting pattern, power, buses, field of view,
  attachment provisions, structural environment. They live in `model/interfaces/` and are
  inputs of the study, not supplier data.
- **Architecture element**: a function (`FCT`), a component (`CMP`) or an interface
  (`IF`). Each one declares the requirements allocated to it; each requirement is owned by
  at least one component.
- **External (`EXT`)**: something outside the study boundary that the kit touches — the
  platform structure, the payload, the bus, the mission system, the maintenance crew, the
  environment.
- **Allocation**: the link from a requirement to the architecture element that realises it.
- **Traceability**: the chain requirement → architecture element → verification case →
  evidence record. The chain is enforced by `tools/rules.py`.
- **Traceability matrix**: the generated table in `docs/traceability.md` that shows the
  chain and the state of every link. Generated from the model; never edited by hand.
- **Change classification**: the assessment, under EASA Part 21 Subpart D, of whether the
  installation is a minor or major change to the type design. It has to be recorded before
  release, not assumed. The study records it in `model/compliance.yaml` with one criterion per
  appreciable effect and keeps the status `OPEN` until the platform procedure confirms it.
- **Compliance document**: a document in the register that shows compliance with the
  requirements it covers. Every requirement is covered by exactly one document; the coverage
  is enforced by the `COMPLIANCE-COVERAGE` rule.
- **Document register**: the list of compliance documents in `model/compliance.yaml`: identity,
  title, type, state, the requirements each one covers and the ticket that will produce it.
  States: `PLANNED`, `DRAFT`, `OUTLINE`, `GENERATED`, `ISSUED`.
- **Compliance data**: the set of documents that demonstrate satisfaction of the
  requirements — compliance matrix, drawings list, analysis reports, test plans and
  reports.
