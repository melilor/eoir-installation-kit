# EO/IR Payload Installation Kit — Model-Based System Engineering Study

A model-based system engineering study of the **installation kit** that lets a light
helicopter (CS-27 class) or a tactical UAV carry a stabilised electro-optical / infrared
payload: the structural attachment, the electrical and avionic interfaces, the weight and
balance impact, the preservation of the payload field of view, and the compliance data an
EASA Part 21 Design Organisation Approval (DOA) holder works with.

The study is built as a **model**, not as a folder of documents. Requirements live in a
[Doorstop](https://doorstop.readthedocs.io) document, the architecture lives in YAML, every
requirement points at its source, and a validator in this repository fails the build when a
requirement has no source, no owning architecture element or no verification case — or when
a verification claims evidence that is not in the repository.

```
$ python -m tools.traceability check
checked 23 requirements, 16 verification cases, 11 components: 0 errors, 0 warnings
```

## What this is / what this is not

| This repository is | This repository is not |
| --- | --- |
| a system engineering study of an installation kit | a design of the EO/IR sensor |
| a requirements, architecture and verification model with enforced traceability | a certification dossier |
| an application of CS-27, RTCA DO-160G and EASA Part 21 as a frame | an application of DO-178C, DO-331 or DO-254 |
| declared assumptions, marked as assumptions | measurements, test results or supplier data |
| a first published slice, with its gaps listed | a finished project |

The payload, the platform and the environment are **declared assumptions**, written in
[`model/assumptions.yaml`](model/assumptions.yaml) and referenced by the requirements that
depend on them. An assumption is an input the study needs, not a fact.

## Status

**Revision A — first published slice, 2026-09-18.** The model, the architecture allocation
and the verification structure exist and are consistent. **No verification has been
executed yet**: every one of the 16 verification cases is `FUTURE` and points at the ticket
that will produce its evidence. The
[traceability matrix](docs/traceability.md) says this case by case, and it is generated from
the model, never written by hand.

## Quick start

```bash
pip install -r requirements.txt

doorstop --no-ref-check --no-level-check      # validate the requirements documents
python -m tools.traceability check            # validate the whole model
python -m tools.traceability report           # regenerate docs/traceability.md
python -m pytest                              # run the test suite
```

## Repository layout

```
model/
  requirements/          SYS001..SYS023 — system requirements (Doorstop)
  verification/          VER001..VER016 — verification cases, linked to their requirements
  architecture/          functions, components, interfaces, external boundary
  assumptions.yaml       declared assumptions and interface data (ASM A-00x)
  evidence.yaml          one record per verification case: method, status, artifact, plan
tools/
  model.py               load the four parts of the model
  rules.py               the validation rules, one identifier per failure
  traceability.py        command line: check, report, report --check
tests/                   29 tests: one failing model per rule, plus the repository model
docs/
  traceability.md        generated matrix: requirement → architecture → verification → evidence
  method.md              how the model works and why the tools were chosen
  adr/                   decision records
```

## The model, in one picture

```
requirement (SYS) ──┬──> architecture element (CMP / FCT / IF) ──> allocation
                    │
                    └──> verification case (VER) ──> evidence record (method, status, artifact)
```

The rules that hold this together, each with a stable identifier in
[`tools/rules.py`](tools/rules.py):

| Rule | What it rejects |
| --- | --- |
| `REQ-SOURCE` | a requirement whose source is missing, malformed or an unknown assumption |
| `ARCH-ALLOC` | a requirement that no component owns |
| `ARCH-REQ` | an architecture element with no requirement, or pointing at one that does not exist |
| `ARCH-REALIZES` | a function no component realises, or a component that realises nothing |
| `VER-COVER` | a requirement with no verification case |
| `VER-EVIDENCE` | a verification case without an evidence record |
| `EVIDENCE-ARTIFACT` | a `PASS` or `WARN` claim whose artifact is not in the repository |
| `EVIDENCE-PLAN` | a `FUTURE` case with no ticket attached to it |
| `ASM-OPEN` | evidence produced against a declared assumption that is still open |

## Standards used as the frame

| Reference | Used for |
| --- | --- |
| 14 CFR Part 27 (CS-27 class) — 27.301/27.303/27.305, 27.23, 27.561, 27.1301/27.1309, 27.1316/27.1317, 27.1351–27.1367, 27.1529 | loads, factor of safety, strength, weight and balance, equipment installation, electrical systems, continued airworthiness |
| RTCA DO-160G — Sections 4, 6, 8, 14, 16, 20, 21 | environmental qualification of the installation |
| EASA Part 21 Subpart D (21.A.91/21.A.95/21.A.97) and 21.A.239 | change classification, approval route, design assurance |
| SAE ARP4754A | development process frame |
| ISO/IEC/IEEE 29148 | requirement quality criteria |
| ARINC 429 | payload control interface (declared) |

## Licence

Code: MIT (`LICENSE`). Documentation: CC BY 4.0 (`docs/LICENSE-CC-BY-4.0.md`).

## Author

Anthony Migliore — aerospace engineering graduate, Milan.
[LinkedIn](https://www.linkedin.com/in/miglioreanthony)
