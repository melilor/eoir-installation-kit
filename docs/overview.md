# Study overview

The map of this repository: what the study is, how the model is built, what is verified and
what is not, and where the work goes next.

## What this study is

A model-based system engineering study of the **installation kit** that lets a light
helicopter (CS-27 class) or a tactical UAV carry a stabilised electro-optical / infrared
payload. The sensor is the input, not the subject: the subject is the structural attachment,
the electrical and avionic interfaces, the weight and balance impact, the preservation of
the field of view, and the compliance data frame an EASA Part 21 Design Organisation
Approval holder works with.

The study is built as a **model**, not as a folder of documents. Requirements live in a
Doorstop document, the architecture and the evidence live in YAML, and a validator in this
repository enforces the whole chain. If a requirement has no source, no owning component or
no verification case, the build is red.

**Status — revision B, 2026-09-18.** 38 requirements, 12 components, 28 verification cases,
29 tests, CI green. **No verification has been executed**: all 28 cases are `FUTURE` and each
one names the ticket that will produce its evidence. That is the honest state of the study
and it is visible in [the traceability matrix](traceability.md).

## The model, end to end

Every arrow below is a rule in `tools/rules.py`, checked in CI:

```
      ASSUMPTION A-00x                STANDARD (STD …)
      declared input                  cited clause
              \                        /
               \                      /
                ▼                    ▼
    ┌────────────────────────────────────────────────────────┐
    │ REQUIREMENT   SYS001 … SYS038                          │  REQ-SOURCE
    │ text + source + verifiable acceptance criterion        │  REQ-TEXT
    └───────────────────────┬────────────────────────────────┘
                            │
                            │  ARCH-ALLOC · ARCH-REQ · ARCH-REALIZES · ARCH-IFACE
                            ▼
    ┌────────────────────────────────────────────────────────┐
    │ ARCHITECTURE                                           │
    │ 9 functions (FCT) · 12 components (CMP)                │
    │ 9 interfaces (IF) · 6 external entities (EXT)          │
    └───────────────────────┬────────────────────────────────┘
                            │
                            │  VER-COVER · VER-LINK
                            ▼
    ┌────────────────────────────────────────────────────────┐
    │ VERIFICATION CASE   VER001 … VER028                    │
    │ method: analysis · review · inspection · test ·        │
    │         demonstration                                  │
    └───────────────────────┬────────────────────────────────┘
                            │
                            │  VER-EVIDENCE
                            ▼
    ┌────────────────────────────────────────────────────────┐
    │ EVIDENCE RECORD (one per case)                         │
    │ method · status · artifact · plan · note               │
    └───────────────────────┬────────────────────────────────┘
                            │
                            │  EVIDENCE-METHOD · EVIDENCE-STATUS
                            │  EVIDENCE-ARTIFACT · EVIDENCE-PLAN · EVIDENCE-NOTE
                            ▼
    ┌────────────────────────────────────────────────────────┐
    │ ARTIFACT IN THE REPOSITORY                             │
    │ today: none — all 28 cases are FUTURE                  │
    └────────────────────────────────────────────────────────┘

    ASM-OPEN warns when evidence is produced against an assumption that is still open.
```

## Repository map

```
eoir-installation-kit/
├── README.md            what it is / what it is not, status, quick start
├── CONTEXT.md           glossary: kit, payload, requirement, evidence, assumption…
├── AGENTS.md            how to work in the repository (gate before every commit)
│
├── model/                        ← THE MODEL
│   ├── requirements/    SYS001–SYS038   (Doorstop: text + source)
│   ├── verification/    VER001–VER028   (Doorstop: method statement, linked to its SYS)
│   ├── architecture/    architecture.yaml: FCT, CMP, IF, EXT
│   ├── assumptions.yaml A-001–A-012, all OPEN with a rationale
│   └── evidence.yaml    28 records: method, status, artifact, plan
│
├── tools/                        ← THE CHECK
│   ├── model.py         loads the four parts of the model
│   ├── rules.py         9 rules, one stable identifier per failure
│   └── traceability.py  check · report · report --check
│
├── tests/               29 tests: one failing model per rule, plus the repository model
│
├── docs/
│   ├── overview.md      this file
│   ├── traceability.md  GENERATED matrix: requirement → architecture → verification → evidence
│   ├── method.md        how the model works and why these tools
│   ├── adr/0001-…       decision: the model is versioned text, not a graphical tool
│   └── agents/          tracker, triage labels and domain-doc conventions
│
├── .scratch/eoir-installation-kit/
│   ├── spec.md          specification: problem, stories, decisions, tests, out of scope
│   └── issues/01–12     tickets with their blocking edges
│
└── .github/workflows/ci.yml     Doorstop → check → matrix freshness → tests
```

## Numbers

| Item | Count |
| --- | --- |
| System requirements (`SYS`) | **38** |
| Standard citations / assumption citations in requirements | 43 / 17 |
| Declared assumptions | **12**, all `OPEN` |
| Functions / components / interfaces / external entities | 9 / **12** / 9 / 6 |
| Verification cases (`VER`) | **28** — all `FUTURE` |
| Methods: analysis / review / inspection / test / demonstration | 8 / 11 / 5 / 2 / 2 |
| Validation rules | **9**, one identifier per failure |
| Tests | **29**, green |
| CI | green on every push |

## Requirements by class

| Class | Requirements | Main source |
| --- | --- | --- |
| Structure and loads | SYS001–SYS004 | 14 CFR 27.301/303/305/561 |
| Structural design rules | SYS024–SYS029 (fitting factor, material design values, fastener locking, protection of structure, inspection provisions, critical parts) | 14 CFR 27.602/607/609/611/613/625 |
| Mass and balance | SYS005–SYS007 | 14 CFR 27.23 + declared platform data |
| Installation, field of view, access | SYS008, SYS009, SYS018, SYS019, SYS028 | declared assumptions |
| Electrical and data | SYS010–SYS013, SYS030–SYS032 | 14 CFR 27.601 and 27.1351–27.1367 + declared interface data |
| Environment and EMC | SYS014–SYS017, SYS033–SYS035 | RTCA DO-160G Sections 4, 6, 8, 11–14, 16, 20, 21; 14 CFR 27.609/610/1309/1316/1317 |
| Certification and documentation | SYS020–SYS023, SYS036–SYS038 | EASA Part 21 21.A.239; 14 CFR 27.1529, 27.1583, 27.1589 |

Every clause number in the model was checked against the public text of the referenced
document before being cited.

## Architecture

| Component | Requirements | Realises |
| --- | --- | --- |
| CMP-01 Interface frame | 11 | attach, carry loads, preserve field of view |
| CMP-02 Platform attachment fittings | 9 | attach, carry loads |
| CMP-03 Payload interface plate | 7 | attach, preserve field of view |
| CMP-04 Power harness | 4 | supply power |
| CMP-05 Data harness | 4 | route data and video |
| CMP-06 Circuit protection assembly | 3 | protect power |
| CMP-07 Bonding straps and grounding hardware | 2 | bond the payload |
| CMP-08 Fastener and quick-release set | 3 | install and remove |
| CMP-09 Payload connector bracket and strain relief | 3 | route data, install and remove |
| CMP-10 Documentation and marking set | 8 | carry identity and compliance data |
| CMP-11 Environmental protection provisions | 7 | sustain the environment |
| CMP-12 Harness routing and protection provisions | 6 | route power and data, protect them |

The 9 interfaces connect the kit to the platform structure, the payload, the platform bus,
the mission system, the maintainer and the environment.

## What is verified, honestly

Nothing. All 28 verification cases are `FUTURE`, each one pointing at the ticket that will
produce the evidence. The study demonstrates a method and a discipline, not a result; the
matrix states this case by case, and the README says it before a reader has to ask.

## The gate

```bash
doorstop --no-ref-check --no-level-check      # validate the requirements documents
python -m tools.traceability check            # validate the whole model
python -m tools.traceability report           # regenerate the matrix
python -m pytest                              # run the test suite
```

The same four commands run in CI on every push. `report --check` fails when the committed
matrix differs from the model, so the published artefact cannot drift.

## What this demonstrates

| Question a reviewer asks | Where the answer is |
| --- | --- |
| Can this person structure a system model? | `model/`, the chain above, 38 requirements over 9 functions and 12 components |
| Can they manage requirements? | Doorstop, cited sources, declared assumptions, no requirement without a criterion |
| Do they understand verification? | 28 cases with a declared method and an honest state, plus rules that reject unsupported claims |
| Do they automate their own discipline? | `tools/rules.py`, 29 tests, CI, generated matrix |
| Do they write documentation? | this file, `docs/method.md`, the ADR, the spec, the tickets |
| Do they know the standards frame? | CS-27/14 CFR Part 27, DO-160G, EASA Part 21, ARINC 429, ISO/IEC/IEEE 29148 |

## Limits, stated before anyone asks

- No verification executed: all cases `FUTURE`.
- All 12 assumptions are `OPEN`: payload, platform and environment are declared inputs, not
  measurements.
- No graphical or behavioural model, no SysML semantics, no ReqIF/XMI exchange (ADR 0001).
- The sensor is not designed and will not be.
- DO-178C, DO-331 and DO-254 are framed, not applied.

## Where the work goes next

```
                 ┌────────────────────────────────┐
                 │ 01 FOUNDATION ✅               │
                 │ 02 REQUIREMENTS ✅             │
                 └───────────────┬────────────────┘
                                 ▼
                      ┌─────────────────────┐
                      │ 03 ARCHITECTURE     │  ← unblocked now
                      └──────────┬──────────┘
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
 ┌──────────────┐        ┌──────────────┐         ┌──────────────────┐
 │04 MASS & CG  │        │05 FOV &      │         │08 GEOMETRY       │
 │  unblocked   │        │  CLEARANCE   │         │  unblocked       │
 │              │        │  unblocked   │         │                  │
 └──────┬───────┘        └──────┬───────┘         └────────┬─────────┘
        │                       │                          │
 ┌──────┴───────┐        ┌──────┴───────┐                  │
 │06 POWER &    │        │09 COMPLIANCE │◀─────────────────┘
 │  BONDING     │        └──────┬───────┘
 │  unblocked   │               │
 └──────┬───────┘        ┌──────┴───────┐        ┌──────────────────┐
        │                │10 QUALIFI-   │        │07 LOAD PATH      │
        │                │  CATION PLAN │        │ (after 02 + 08)  │
        │                └──────┬───────┘        └────────┬─────────┘
        └───────────┬───────────┴─────────────────────────┘
                    ▼
          ┌─────────────────────┐       ┌─────────────────────────┐
          │ 11 TECHNICAL REPORT │──────▶│ 12 PUBLICATION AND      │
          │   + INDEPENDENT     │       │   APPLICATION ALIGNMENT │
          │   REVIEW            │       └─────────────────────────┘
          └─────────────────────┘
```

Tickets live in `.scratch/eoir-installation-kit/issues/`, one file per ticket, each declaring
its blocking edges and its acceptance criteria. The spec behind them is
`.scratch/eoir-installation-kit/spec.md`.
