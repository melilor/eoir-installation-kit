# Spec — EO/IR payload installation kit, model-based system engineering study

Feature slug: `eoir-installation-kit`. Tracker: local markdown (`.scratch/eoir-installation-kit/issues/`).

## Problem Statement

The author is applying for entry-level system engineering roles in avionics and mission
equipment, where the blocking requirement is model-based system engineering and requirements
lifecycle management. He has a mature verification asset in a separate project (gates,
evidence, an independent review) but nothing that demonstrates the *left* side
of the V-model: requirements with sources, an architecture that owns them, and traceability
that is checked rather than asserted. There is no public artefact a hiring manager can open
today, and the application texts already promise one.

## Solution

A public repository containing a model-based system engineering study of an **installation
kit for an EO/IR payload on a light helicopter (CS-27 class) and a tactical UAV**: the
structural attachment, the electrical and avionic interfaces, the weight and balance impact,
the field of view preservation and the compliance data frame. The model is plain text —
requirements in Doorstop, architecture and evidence in YAML — and a validator in the same
repository enforces the chain requirement → architecture element → verification case →
evidence record → artifact. CI runs the validator, checks that the published traceability
matrix is current, and runs the test suite. The first published slice is real but small: 23
requirements, 11 components and 16 verification cases, all of them `FUTURE` and pointing at
the ticket that will produce the evidence — the requirement coverage ticket (02) then grew
the set to 38 requirements, 12 components and 28 verification cases.

## User Stories

1. As a hiring manager, I want to open a repository and see the requirements, the
   architecture and the verification state of a real study, so that I can judge the method
   in a few minutes.
2. As a hiring manager, I want to run one command to check the model myself, so that I do
   not have to trust the README.
3. As an interviewer, I want to see every requirement pointing at the clause or the
   assumption it comes from, so that I can challenge a single requirement without reading
   the whole model.
4. As an interviewer, I want declared assumptions separated from facts, so that I can see
   what the author knows and what he is assuming.
5. As the author, I want the validator to reject a requirement with no source, so that no
   unsupported statement survives a commit.
6. As the author, I want the validator to reject a requirement with no owning component, so
   that the architecture cannot drift away from the requirements.
7. As the author, I want the validator to reject a verification case without an evidence
   record, so that no planned verification is forgotten.
8. As the author, I want the validator to reject a `PASS` whose artifact is not in the
   repository, so that a claim without proof fails the build instead of surviving review.
9. As the author, I want a `FUTURE` verification to carry the ticket that will produce the
   evidence, so that the gaps are a plan and not a hope.
10. As the author, I want evidence produced against an open assumption to raise a warning, so
    that I cannot quietly verify a requirement against an input nobody confirmed.
11. As a reviewer, I want the traceability matrix generated from the model, so that it cannot
    drift from what the model says.
12. As a reviewer, I want CI to fail when the committed matrix is stale, so that the
    published artefact is always the current one.
13. As a reviewer, I want each rule to have a stable identifier, so that a red build points
    at a specific contract instead of at an opinion.
14. As the author, I want the model to stay diffable text, so that every change is reviewable
    and no licence or installation is needed to read it.
15. As the author, I want the standards used as a frame (CS-27, DO-160G, EASA Part 21) to be
    cited per requirement, so that the study is anchored to the documents a DOA holder
    actually works with.
16. As the author, I want this study to be independent of the author's other project, so that
    the two assets stand on their own and neither borrows the other's evidence.
17. As the author, I want the repository to be publishable before the application is sent,
    so that the follow-up message can link something real.
18. As the author, I want the remaining work split into tickets with blocking edges, so that
    each session can pick up an unblocked ticket and finish it.

## Implementation Decisions

- **Model parts.** Requirements and verification cases are Doorstop documents; architecture
  (functions, components, interfaces, externals) is one YAML file; the evidence register and
  the assumption register are one YAML file each. Each part has a single owner and a single
  location.
- **Requirement identity.** `SYS001..SYS0NN`, stable, never reused. Verification cases
  `VER001..VER0NN`. Architecture elements `FCT-`, `CMP-`, `IF-`, externals `EXT-`.
  Assumptions `A-00x`.
- **Sources.** Every requirement carries `ref` with one or more citations: `STD <document and
  clause>` or `ASM <assumption id>`. The citation syntax and the resolution of `ASM` ids are
  validated; the clause itself stays in the document where it was read.
- **Verification cases are Doorstop items** that link to their parent requirements, so the
  requirement-to-verification link is checked by Doorstop as well as by the validator.
- **Evidence register.** One record per verification case: `method`, `status`, `artifact`,
  `plan`, `note`. `PASS`/`WARN` require an artifact that exists; `FUTURE` requires a plan;
  `FAIL`/`LIMITATION`/`BLOCKED` require a note.
- **Validator.** `tools/rules.py` holds one function per rule and one identifier per failure;
  `tools/traceability.py` exposes `check` and `report [--check]` and is the CI gate. The
  validator is pure Python over loaded data, so the rules are unit-testable with in-memory
  models.
- **Traceability matrix.** `docs/traceability.md` is generated by the tool and committed;
  CI fails when the file differs from the model.
- **Doorstop deviations.** `--no-ref-check` (citations are not file paths) and
  `--no-level-check` (flat documents). Both are visible in the CI command and documented in
  `docs/method.md`.
- **Language and licence.** English for the repository; MIT for code, CC BY 4.0 for
  documentation. Identity: name and LinkedIn profile only.
- **Toolchain boundary.** Text and Python only. No GUI MBSE tool in this phase; Capella and
  System Composer remain study items, not artefacts of this repository.

## Testing Decisions

- Good tests check the *contract*, not the implementation: a model that violates a rule must
  produce that rule's identifier, and a clean model must produce no finding at all.
- One unit test per rule, each built by breaking exactly one thing in a small in-memory
  model (`tests/test_rules.py`). The behavior under test is the set of rule identifiers
  returned, not the wording of the messages.
- Integration tests on the repository model (`tests/test_model.py`): no errors, every
  requirement has a source and a verification, every verification has an evidence record,
  and the committed matrix matches the generated one.
- Command-line tests (`tests/test_cli.py`) assert the exit codes CI depends on.
- Prior art: none in this repository yet; the author's previous study in a separate workspace uses
the same shape (scripts that produce evidence, gates that check criteria, logs kept as
  evidence), which is the reason this model is built the same way.

## Out of Scope

- The design of the EO/IR sensor, its optics and its detectors.
- Certification: the study frames the compliance work but does not claim it. DO-178C,
  DO-331 and DO-254 are not applied here.
- Physical testing: no test article exists, so test-based verifications stay `FUTURE` or
  `LIMITATION` until one does.
- Graphical and behavioural modelling, SysML semantics, ReqIF/XMI exchange.
- Detailed structural sizing and drawing release (the layout ticket produces a parametric
  layout and its checks, not a released drawing).
- The author's other projects, their evidence and their repositories.

## Further Notes

- The repository is the public artefact of the application for the TPS Group Avionic System
  Engineer position; the study domain (EO/IR mission equipment, DOA/POA frame, requirements
  definition and release validation) is chosen to match it.
- The first slice is deliberately honest: nothing is verified yet, and the matrix says so.
  The value shown is the method and the discipline, not a result.
- The tickets below are the plan of the study after the first slice; each one ends with
  evidence that moves at least one verification case out of `FUTURE`.
