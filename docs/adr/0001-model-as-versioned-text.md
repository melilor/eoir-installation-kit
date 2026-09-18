# Requirements, architecture and verification as versioned text files

The study needs a model that supports the chain requirement → architecture → verification →
evidence, and that a reviewer can inspect without installing a proprietary tool. The
alternative was a graphical MBSE workbench (Capella, or a SysML tool) or a requirements
management server (DOORS-class). The decision is to keep the model as text — Doorstop for
the requirements, YAML for the architecture and the evidence register — and to enforce the
chain with a validator in this repository, run in CI on every commit.

**Considered Options**

- **A graphical MBSE workbench (Capella/Arcadia, System Composer, a SysML tool)**: rejected as
  the *source of truth* for this study. It would give a proper metamodel and diagrams, but the
  model would live in binary or XML artefacts that a reviewer cannot diff, and consistency
  would depend on the tool being installed. It remains the right next step for functional and
  behavioural modelling, and it is where the same requirements would be imported next.
- **A requirements management server (DOORS-class)**: rejected. No licence, no server, and the
  discipline it enforces — identity, source, links, verification method — is exactly what the
  rules in `tools/rules.py` enforce on plain files.
- **Plain documents (a compliance matrix in a spreadsheet)**: rejected. It cannot be checked,
  it drifts silently, and it proves nothing about the links.

**Consequences**

- Every model change is a diff, reviewable like code, and CI rejects a broken chain
  (`REQ-SOURCE`, `ARCH-ALLOC`, `VER-COVER`, `EVIDENCE-ARTIFACT`, ...).
- The model has no graphical notation and no SysML semantics: figures are generated from the
  YAML when needed, and the absence of behavioural modelling is declared, not hidden.
- Doorstop's external-reference and level checks are disabled by design, because `ref`
  carries citation strings and the documents are flat. The deviation is visible in the CI
  command and explained in `docs/method.md`.
- The citations are strings, not resolvable links: the model records *which clause* a
  requirement comes from, and the clause itself stays in the document where it was read.
