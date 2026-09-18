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
  challenge. Evidence produced against an `OPEN` assumption is reported as a warning.
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
  release, not assumed.
- **Compliance data**: the set of documents that demonstrate satisfaction of the
  requirements — compliance matrix, drawings list, analysis reports, test plans and
  reports.
