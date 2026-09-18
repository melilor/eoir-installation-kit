# 03: Architecture and interfaces

**What to build:** the architecture model completed and readable — functions with their requirements, components realising the functions, interfaces between kit and boundary (platform structure, payload, bus, mission system, maintainer, environment) — plus a diagram generated from the YAML.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] Every function realised by at least one component, every component realising at least one function
- [ ] Every requirement allocated to at least one component; no component without a requirement
- [ ] Interface list with both endpoints declared, including the payload interface control data
- [ ] A diagram (Mermaid or SVG) generated from the model by a script, not drawn by hand
- [ ] `python -m tools.traceability check` green; matrix regenerated
