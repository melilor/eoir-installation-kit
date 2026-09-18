# Agent instructions — EO/IR installation kit study

## Bootstrap

Before acting in this repository, read in this order:

1. `CONTEXT.md` — the glossary. The vocabulary of the model is defined there.
2. `docs/method.md` — how the four parts of the model fit together.
3. `docs/agents/` — issue tracker, triage labels, domain docs conventions.
4. `docs/adr/` — decisions already taken; if your plan contradicts one, say so.

## Truth of the model

- The model is the source of truth: `model/requirements`, `model/verification`,
  `model/architecture/architecture.yaml`, `model/evidence.yaml`, `model/assumptions.yaml`.
- `docs/traceability.md` is **generated**. Never edit it by hand: run
  `python -m tools.traceability report`.
- A number or a result without an artifact in this repository is not a result. Evidence
  without a path is rejected by `EVIDENCE-ARTIFACT`.
- An assumption is not a fact. If you need a new input, add it to `model/assumptions.yaml`
  with status `OPEN` and a rationale, then reference it as `ASM A-00x`.
- Never promote a `WARN` to a `PASS`, and never mark a verification `PASS` before its
  artifact exists.

## Before every commit

```bash
doorstop --no-ref-check --no-level-check
python -m tools.traceability check
python -m tools.traceability report
python -m tools.diagram
python -m tools.layout
python -m tools.compliance
python -m tools.mass
python -m tools.clearance
python -m tools.power
python -m tools.loads
python -m pytest
```

The same eleven commands run in CI (`.github/workflows/ci.yml`), so a green local run and a
green pipeline are the same thing. `python -m tools.layout` runs the geometric checks and
rewrites `evidence/layout/`; `--check` instead fails when the committed evidence differs
from the model.

## How a ticket is closed

Every ticket in `.scratch/eoir-installation-kit/issues/` is closed in **one commit**, in this
order:

1. **Model first.** The numbers go into `model/` — requirements, architecture, assumptions,
   layout, mass, power, compliance — never into prose.
2. **Then the check.** A tool in `tools/` computes the result and writes the evidence under
   `evidence/<area>/`. A new rule gets a stable identifier and a case that fails on the broken
   model.
3. **Tests.** One failing case per check, an integration test on the repository model, and an
   evidence-freshness test. `python -m pytest` stays green.
4. **CI.** Add the `--check` step for the new evidence to `.github/workflows/ci.yml`.
5. **Docs in the same commit.** Status numbers in `README.md` and `docs/overview.md`, a section
   in `docs/method.md` when the model gains a part, a term in `CONTEXT.md` when one is born, and
   the revision letter in `model/evidence.yaml`.
6. **Evidence register.** The cases the evidence supports move to `PASS`, `LIMITATION` or
   `FAIL`, or stay `FUTURE`. A `PASS` or `WARN` needs an artifact that exists, a `FUTURE` needs
   a plan, and every note says what the evidence does **not** cover. A `WARN` is never promoted
   to a `PASS`.
7. **The ticket file** gets `Status: resolved` and an `## Answer`: what was built, the numbers,
   what the checks found — including the failures that changed the design — and the model state
   after the ticket.
8. **Commit** as `feat(<area>): <what> (ticket NN)`, with the findings in the body, and push.

A failing check is a result, not an obstacle: when the analysis contradicts the declared data,
the data changes and the finding is recorded in the ticket Answer.

## Working rules

- One phase at a time, one writer in the repository at a time for shared files.
- Every change to the model answers a ticket in `.scratch/eoir-installation-kit/issues/`.
- When a ticket changes the model, update the report and the tests in the same commit.
