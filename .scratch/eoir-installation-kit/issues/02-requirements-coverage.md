# 02: Requirements coverage

**What to build:** the requirement set completed by class — structure and loads, mass and balance, electrical and data interfaces, power, environment and qualification, electromagnetic compatibility, maintainability and access, certification and documentation — with every requirement carrying a verifiable acceptance criterion and a source.

**Blocked by:** 01.

**Status:** resolved

- [x] Every class of the installation covered by at least one requirement
- [x] Every requirement readable as a single verifiable statement (ISO/IEC IEEE 29148 criteria: unambiguous, verifiable, no design imposed)
- [x] Every requirement with a source: a standard clause (`STD`) or a declared assumption (`ASM`)
- [x] Every new assumption written in `model/assumptions.yaml` with rationale and status
- [x] No requirement without an acceptance criterion that the verification case can test
- [x] `python -m tools.traceability check` green; matrix regenerated

## Answer

Closed on 2026-09-18. Fifteen requirements added (`SYS024`–`SYS038`) after a gap review
against 14 CFR Part 27 Subpart D and the DO-160G section list:

| Area | Added |
| --- | --- |
| Structural design rules | `SYS024` fitting factor 1.15 (27.625), `SYS025` material design values (27.613), `SYS026` fastener locking (27.607), `SYS027` protection of structure (27.609), `SYS028` inspection provisions (27.611), `SYS029` critical parts (27.602) |
| Harness, connectors and power distribution | `SYS030` routing and protection, `SYS031` connector retention and access, `SYS032` circuit protection reachable and labelled |
| Environmental breadth | `SYS033` fluids (§11), `SYS034` sand, dust and fungus (§12, §13), `SYS035` lightning and static electricity protection (27.610) |
| Certification and configuration | `SYS036` configuration control, `SYS037` loading information and flight manual effect (27.1589, 27.1583), `SYS038` part identification |

Twelve verification cases (`VER017`–`VER028`) and their evidence records were added, all
`FUTURE` with the ticket that will produce the evidence. One assumption was added
(`A-012`, harness installation rules) and one component (`CMP-12`, harness routing and
protection provisions), which realises four functions. One interface was added (`IF-09`).

Clause numbers were verified against the public text of 14 CFR Part 27 (Subpart D and
Subpart G) before being cited; no clause is quoted from memory.

Model state after the ticket: 38 requirements, 28 verification cases, 12 components, 9
functions, 9 interfaces, 12 declared assumptions, validator green with 0 errors and 0
warnings.
