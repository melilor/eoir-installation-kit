# 06: Power budget and bonding

**What to build:** the electrical power budget and the protection coordination check, plus the bonding requirement recorded for the test that will close it.

**Blocked by:** 01, 02.

**Status:** resolved

- [x] Continuous and peak demand compared with the harness and protection sizing (SYS010)
- [x] Circuit protection coordinated with the platform distribution, with the load analysis entry identified (SYS011)
- [x] Voltage drop along the harness computed for the declared current and length
- [x] Bonding requirement (SYS013) kept FUTURE until a test article exists, with the limitation written down
- [x] Output committed under `evidence/` and referenced by VER006 and VER007
- [x] Matrix regenerated

## Answer

Closed on 2026-09-18.

**The numbers.** Payload demand 150 W continuous and 400 W peak at 28 VDC, over 2.4 m of
2.5 mm² copper:

| Quantity | Value | Limit | Margin |
| --- | --- | --- | --- |
| Continuous current | 5.36 A | 20 A (conductor ampacity) | +14.64 A |
| Continuous voltage drop | 0.180 V | 0.560 V (2 % of the bus) | +0.38 V |
| Peak voltage drop | 0.480 V | 1.120 V (4 %) | +0.64 V |
| Breaker rating | 20 A | 17.86 A required (1.25 × peak) | +2.14 A |
| Bus load after the installation | 2251 W | 3000 W | +749 W |

Five checks, all passing: `POWER-CONTINUOUS`, `POWER-PEAK`, `POWER-AMPACITY`, `POWER-BREAKER`,
`POWER-BUS`. `evidence/power/` holds `checks.json` and `report.md`.

**An open item found by the analysis, and kept open.** The declared payload inrush is 25 A,
above the 20 A breaker rating, and the breaker trip curve is not available in this study: the
coordination of the transient cannot be closed with the declared data. It is written into
`model/power.yaml` as an open item, it appears in the generated report, and it is the reason
`VER007` carries a `LIMITATION` instead of a `PASS` — either a curve with a suitable delay or a
higher rating with a larger conductor, and both are design changes to be taken deliberately.
The second open item is the load analysis entry itself, which belongs to the platform
document; this study computes the value to enter.

**Bonding stays open by design.** `VER009` remains `FUTURE` with the plan pointing at the
qualification ticket: the 2.5 mΩ limit is the declared design rule `A-008`, still open, and the
bonding path is declared in the layout, not measured. Nothing is promoted.

**Closure**

| Case | Status | What the evidence shows | What it does not |
| --- | --- | --- | --- |
| VER006 power budget | `PASS` | currents, voltage drop, ampacity, breaker sizing and bus load against the declared limits | the payload demand and the bus data are declared inputs |
| VER007 protection coordination | `LIMITATION` | steady and peak coordination, and the value for the load analysis entry | the transient: the trip curve is not available |

One `ASM-OPEN` warning is added (`SYS010` on the declared payload power demand); the existing
warnings stand.

Model state: 38 requirements, 28 verification cases (`PASS` 9, `LIMITATION` 5, `FUTURE` 14),
107 tests. Validator: 0 errors, 9 warnings.
