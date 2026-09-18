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
python -m pytest
```

The same six commands run in CI (`.github/workflows/ci.yml`), so a green local run and a
green pipeline are the same thing. `python -m tools.layout` runs the geometric checks and
rewrites `evidence/layout/`; `--check` instead fails when the committed evidence differs
from the model.

## Working rules

- One phase at a time, one writer in the repository at a time for shared files.
- Every change to the model answers a ticket in `.scratch/eoir-installation-kit/issues/`.
- When a ticket changes the model, update the report and the tests in the same commit.
