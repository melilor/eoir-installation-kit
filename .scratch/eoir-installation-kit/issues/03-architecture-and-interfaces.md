# 03: Architecture and interfaces

**What to build:** the architecture model completed and readable — functions with their requirements, components realising the functions, interfaces between kit and boundary (platform structure, payload, bus, mission system, maintainer, environment) — plus a diagram generated from the YAML.

**Blocked by:** 01.

**Status:** resolved

- [x] Every function realised by at least one component, every component realising at least one function
- [x] Every requirement allocated to at least one component; no component without a requirement
- [x] Interface list with both endpoints declared, including the payload interface control data
- [x] A diagram (Mermaid or SVG) generated from the model by a script, not drawn by hand
- [x] `python -m tools.traceability check` green; matrix regenerated

## Answer

Closed on 2026-09-18.

**Interface control data became files.** `model/interfaces/icd_payload.yaml` and
`model/interfaces/icd_platform.yaml` hold the declared interface values (mass and inertia,
envelope, mounting pattern, power, buses, field of view, attachment provisions, structural
environment, certification basis). The assumptions that rest on those values now carry a
`data_file` pointer, and a new rule, `ASM-FILE`, fails the build when the pointer does not
resolve. Seven assumptions point at the two files; one rule test covers the missing-file
case and one covers the accepted case.

**The architecture document is generated.** `tools/diagram.py` renders
`docs/architecture.md` from the model: a Mermaid diagram of the components and the external
boundary with one edge per interface, plus the function, component, interface and external
boundary tables. CI runs `python -m tools.diagram --check`, so the committed document cannot
differ from the model. Mermaid node identifiers cannot contain a hyphen, so the identifiers
are the element ids with hyphens removed and the labels carry the real id.

**Allocation state after the ticket**

| Element | State |
| --- | --- |
| 9 functions | each one realises at least one requirement and is realised by at least one component |
| 12 components | each one owns 2 to 11 requirements, each one realises at least one function |
| 9 interfaces | both endpoints declared, source and target never the same, all endpoints resolve to a component or a declared external |
| 6 externals | platform structure, payload, platform bus, mission system, maintainer, environment |

Model state: 38 requirements, 28 verification cases, 12 components, 12 assumptions, 10 rules,
34 tests. Validator green with 0 errors and 0 warnings; both generated documents current.
