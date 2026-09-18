# Method

How the model is built, what holds it together, and what has been left out on purpose.

## The four parts

| Part | File | Owns |
| --- | --- | --- |
| Requirements | `model/requirements/SYS*.yml` (Doorstop) | what the installation must satisfy |
| Verification cases | `model/verification/VER*.yml` (Doorstop) | how each requirement is shown to be satisfied |
| Architecture | `model/architecture/architecture.yaml` | functions, components, interfaces and who owns what |
| Interface control data | `model/interfaces/icd_payload.yaml`, `model/interfaces/icd_platform.yaml` | the declared payload and platform interface values |
| Evidence | `model/evidence.yaml` | method, status, artifact and plan of every verification case |

Declared assumptions live in `model/assumptions.yaml` and are referenced by the requirements
that depend on them. An assumption that rests on interface data carries a `data_file` pointer,
and the `ASM-FILE` rule fails the build when that file is missing.

## Why Doorstop

Doorstop keeps requirements as versioned YAML items and checks their links. In this
repository it owns the requirement-to-verification link (`VER` items link to `SYS` items)
and the requirement text itself. Two Doorstop checks are disabled in CI and in
`tools/model.py`:

- **external reference check** — the `ref` field carries a *citation* (`STD 14 CFR 27.303`,
  `ASM A-006`), not a file path or a URL. `tools/rules.py` checks the citation syntax and
  resolves every `ASM` against the assumptions register.
- **level check** — the two documents are flat lists, so every item sits at level 1.

Both are visible in the CI command (`doorstop --no-ref-check --no-level-check`), not hidden
in a configuration file. Every other Doorstop check runs.

## Why the validator exists

`docs/architecture.md` and `docs/traceability.md` are both generated: the first by
`tools/diagram.py` (Mermaid diagram and allocation tables), the second by
`tools/traceability.py` (the requirement matrix). CI fails when either file differs from
the model, so the published documents cannot drift.

Doorstop knows nothing about the architecture and nothing about evidence. The chain that
matters for this study is longer than a requirement tree:

```
requirement → architecture element → verification case → evidence record → artifact
```

`tools/rules.py` enforces the whole chain with one rule identifier per failure, so a red
build points at a rule, not at an opinion. The rules are the contract:

- no requirement without a source;
- no requirement without an owning component;
- no architecture element without a requirement, no interface with an unknown endpoint;
- no requirement without a verification case, no verification case without an evidence record;
- no `PASS`/`WARN` without an artifact that exists;
- no `FUTURE` without a plan, no `LIMITATION`/`FAIL`/`BLOCKED` without a note;
- a warning when evidence is produced against an assumption that is still open.

## The layout and its checks

`model/layout.yaml` is the single source of truth for every dimension of the kit: a
two-view 2D envelope model (rectangles, circles and orthogonal harness paths, in
millimetres). `tools/layout.py` runs twelve geometric and data checks on it — removal
corridor, connector access, fitting edge distance, hole pitch, fastener locking, inspection
access, harness orthogonality, bend radius, clamp position and spacing, clearance to hot
zones and moving parts, and agreement with the interface control data — and writes four
files into `evidence/layout/`: the machine-readable `checks.json`, a readable `report.md`, an
SVG figure and a DXF R12 export. CI runs `python -m tools.layout --check`, so the published
evidence cannot differ from the model.

## The field of view and the clearance

`model/layout.yaml` declares the gimbal centre, the head radius and the sampling step of the
swept sector; the elevation range is read from the payload interface data, so those numbers
live in one place. `tools/clearance.py` samples the sector with one ray per step and checks
every ray against the declared structure and the platform skin: no obstruction, no ray
reaching the skin, and a minimum clearance of at least the declared value. The report lists
the clearance direction by direction and flags the directions whose margin is inside twice
the limit, so a tight direction is reported instead of averaged away. A figure of the sector
with the rays is generated into `evidence/clearance/sweep.svg`.

## The compliance frame

`model/compliance.yaml` holds two things: the change classification (one criterion per
appreciable effect, the approval route and the privileges it relies on) and the document
register, which assigns every requirement to exactly one document — the one that will show
compliance. `tools/compliance.py` renders `docs/compliance-matrix.md` from it, and the
`COMPLIANCE-COVERAGE` rule fails the build when a requirement has no document or two. The
instructions for continued airworthiness are outlined in `docs/ica.md`.

## How to add a requirement

1. `doorstop add SYS` in `model/requirements`, then write `header`, `text` and `ref`
   (`STD <citation>` and/or `ASM <id>`).
2. Allocate it to at least one component in `model/architecture/architecture.yaml`.
3. Add a `VER` item that links to it, and an evidence record for that `VER`.
4. Add it to exactly one document in `model/compliance.yaml`.
5. If it is an installation requirement, add the geometry to `model/layout.yaml` and the
   mass to `model/mass.yaml`.
6. Run `python -m tools.traceability check`, the analysis tools (`layout`, `mass`,
   `clearance`), `python -m tools.traceability report` and `python -m tools.compliance`.

## How to close a verification case

Paths in the evidence record are relative to the repository root for `artifact`
(`evidence/...`) and relative to `.scratch/eoir-installation-kit/` for `plan`
(`issues/04-analysis-mass-and-balance`).

1. Produce the artifact (analysis script and its output, test report, review record).
2. Put the path in the `artifact` field of the evidence record and set the status.
3. If the evidence depends on a declared assumption, say so: if the assumption is still
   `OPEN` the validator emits the `ASM-OPEN` warning, and the warning stays until either the
   assumption is closed or the limitation is accepted in writing.

## What this method gives up

It is not a SysML model and it is not a Capella model: there is no graphical notation, no
simulable functional model, no tool-level metamodel exchange (ReqIF, XMI). The layout is a
2D envelope model, not 3D CAD: interference checking in three dimensions is separate work.
What it gives is a model that a reviewer can read in a diff, that CI can check, and that
does not depend on a licence. The trade-off is recorded in `docs/adr/0001`.
