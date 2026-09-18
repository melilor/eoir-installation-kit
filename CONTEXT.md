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
- **Load case**: one inertia condition of the installation, derived by `tools/loads.py` from a
  declared acceleration and a declared load factor — the payload and kit mass accelerated in a
  direction. The cases are not listed in the model: they are computed, so changing the platform
  data changes the analysis.
- **Limit load**: the maximum load expected in service. A condition the platform prescribes as
  a limit load takes the factor of safety of 14 CFR 27.303 to reach the ultimate load.
- **Ultimate load**: the limit load multiplied by the factor of safety. A condition the
  platform prescribes as an ultimate load — the emergency landing inertia factors — takes no
  further factor, which is what 27.303 says.
- **Factor of safety**: 1.5 unless the condition is already prescribed as ultimate. The applied
  factor is checked per case against the factor that case requires, so the bookkeeping is
  visible instead of implied.
- **Load path**: the chain that carries the load from the payload centre of gravity to the
  platform structure — interface plate, frame rails, fittings, fasteners, hard points. Each
  element names the section it is checked at in `model/loads.yaml`.
- **Attachment plane**: the plane of the platform provisions the fittings bolt to, taken at the
  platform skin in the layout. The payload centre of gravity sits below it, so a horizontal
  inertia force produces a couple that the fittings resist in pairs.
- **Excitation band**: the frequency range of a rotor harmonic over the declared rotor speed
  range, widened by the declared separation percentage. **Admissible window**: a frequency range
  clear of every band. SYS015 requires the installation to stay out of the bands, which is a
  statement about the installation, not about the bands.
- **Limitation class**: why the study cannot make a statement — `INPUT` (a declared
  input is missing or unconfirmed), `METHOD` (the method cannot show it), `ARTICLE`
  (it needs a physical article), `AUTHORITY` (it needs the platform, the installer or
  the competent authority), `INDEPENDENCE` (the limitation of the review itself). The
  class is written once, in `model/report.yaml`, and the review refuses a limitation
  without one.
- **Review**: the mechanical check of the package: the model, the evidence files, the
  numbers the documents quote and the tickets still open, read by `tools/report.py`.
  It is reproducible and it is not independent — the study has one author — and the
  report states that instead of letting the word suggest otherwise.
- **Installation zone**: a place the installation occupies, with the environmental exposure
  that comes with it — the external belly bay and the unpressurised fuselage interior in this
  study, plus a zone for what is not installed. The zone is what a DO-160G category encodes, so
  the zone definition belongs to the platform and the category selection is a joint decision.
- **Category**: the severity an equipment is qualified to within a DO-160G section. It is
  written in `model/qualification.yaml` only where a declared input of this study and a public
  statement about the standard fix it; otherwise the entry names the input the category waits
  for. The standard itself is not in this repository.
- **Qualification state of an entry**: `ASSESSED` when the design already answers it by analysis
  or inspection, `PLANNED` when it needs a test on an article, `OPEN` when the selection cannot
  be completed with the declared inputs.
- **Protection preservation**: the argument that the installation keeps the lightning, HIRF and
  bonding characteristics the platform protection plan gives it, recorded with the means the
  installation provides and what cannot be checked because the plan is referenced, not held.
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
