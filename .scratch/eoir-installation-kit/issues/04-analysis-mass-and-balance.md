# 04: Mass and balance analysis

**What to build:** the analysis that produces the kit mass budget and the platform weight and balance impact, as a script with its output committed as the artifact of the verification cases it closes.

**Blocked by:** 01, 02.

**Status:** resolved

- [x] Component masses are declared per element and summarised by the script, not typed into a table
- [x] Kit mass compared with the SYS005 target, with the margin stated
- [x] Platform centre of gravity computed for the loadable configurations, compared with the SYS007 range
- [x] Payload envelope check (SYS006) using the declared interface data
- [x] Output committed under `evidence/` and referenced by the artifact field of VER003 and VER004
- [x] The three verification cases move out of `FUTURE` with the status the result supports

## Answer

Closed on 2026-09-18.

**One declaration, one computation.** `model/mass.yaml` declares one mass per architecture
component (twelve entries, `source: DECLARED`, each with a note on where the estimate comes
from), the two installation stations and four loadable configurations. The platform data
(empty mass, empty CG, certified CG range, MTOW) and the payload data (mass, CG envelope) are
read from the interface control files, so those numbers live in exactly one place. The new
rule `MASS-COVERAGE` fails the build when a component has no declared mass, when a mass entry
names a component that does not exist, when a mass is not positive, or when the source is not
`DECLARED` or `DERIVED`.

**The result, as a bound rather than a nominal case.** The four configurations use the payload
CG envelope limits and the 5 % component mass tolerance on purpose, so the table is a worst
case:

| Configuration | Kit (kg) | Total (kg) | Platform CG (mm) | Closest limit |
| --- | --- | --- | --- | --- |
| CFG-01 forward payload CG, kit at +5 % | 14.28 | 1409.3 | 2987.0 | +87.0 mm (forward) |
| CFG-02 nominal | 13.60 | 1408.6 | 2992.1 | +92.1 mm |
| CFG-03 aft payload CG | 13.60 | 1408.6 | 2996.9 | +153.1 mm |
| CFG-04 payload removed | 14.28 | 1364.3 | 3013.0 | +113.0 mm |

Kit mass 13.60 kg against the 15 kg target (1.40 kg of margin, 9.3 %). Sixteen checks, all
passing: `MASS-KIT`, `MASS-PAYLOAD`, `MASS-BALANCE`, `MASS-MTOW` on every configuration.

**Evidence.** `evidence/mass/checks.json` (machine readable, with the component list and every
configuration) and `evidence/mass/report.md` (inputs, configurations, checks, component
masses). CI runs `python -m tools.mass --check`, so the committed evidence cannot drift from
the model.

**Verification cases closed**

| Case | Status | What the evidence shows | What it does not |
| --- | --- | --- | --- |
| VER003 mass and balance | `PASS` | kit mass against the target and the platform CG against the certified range, four configurations | any weighed mass: every figure is a declared estimate |
| VER004 payload envelope | `PASS` | the payload is carried at its declared mass and at both CG envelope limits | a heavier payload or one outside the envelope, which is a design change |

Three `ASM-OPEN` warnings appear on `SYS005`, `SYS006` and `SYS007`: the whole analysis rests
on the declared payload and platform data (`A-001`, `A-002`, `A-004`), and the warnings say so.

Model state: 38 requirements, 28 verification cases (`PASS` 7, `LIMITATION` 4, `FUTURE` 17),
15 rules, 85 tests. Validator: 0 errors, 6 warnings.

**Refactor carried out with the ticket**: the result structure shared by the analysis tools
(`Finding`, the margin convention, the table renderer) moved into `tools/analysis.py`, so the
layout, mass and next analyses produce the same shape of evidence.
