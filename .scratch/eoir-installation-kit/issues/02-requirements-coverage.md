# 02: Requirements coverage

**What to build:** the requirement set completed by class — structure and loads, mass and balance, electrical and data interfaces, power, environment and qualification, electromagnetic compatibility, maintainability and access, certification and documentation — with every requirement carrying a verifiable acceptance criterion and a source.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] Every class of the installation covered by at least one requirement
- [ ] Every requirement readable as a single verifiable statement (ISO/IEC IEEE 29148 criteria: unambiguous, verifiable, no design imposed)
- [ ] Every requirement with a source: a standard clause (`STD`) or a declared assumption (`ASM`)
- [ ] Every new assumption written in `model/assumptions.yaml` with rationale and status
- [ ] No requirement without an acceptance criterion that the verification case can test
- [ ] `python -m tools.traceability check` green; matrix regenerated
