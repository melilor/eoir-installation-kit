# 05: Field of view and clearance analysis

**What to build:** the geometric analysis that shows the installation does not obstruct the payload field of view and that the minimum clearances are preserved in every operating configuration, as a script with its output committed as evidence.

**Blocked by:** 01, 02.

**Status:** resolved

- [x] Payload swept volume built from the declared field of view and envelope
- [x] Obstruction against the declared platform geometry, in every configuration of the kit
- [x] Minimum clearance measured and compared with the SYS009 value
- [x] Marginal configurations reported, not hidden
- [x] Output committed under `evidence/` and referenced by VER005
- [x] Matrix regenerated

## Answer

Closed on 2026-09-18.

**The analysis found a real conflict and the design was changed because of it.** The first
run put the existing belly antenna (`SM-04`, at x −100…100, y −490…−430, directly below the
gimbal) inside the swept sector: **229 of 301 rays obstructed, over 114 degrees of
elevation**. The antenna moved outboard and forward (x −520…−380, y −660…−600), out of the
sector and out of the removal corridor. The run that produced that failure is not in the
repository — the repository holds the corrected design and the analysis that proves it — but
the number is recorded here because it is the reason the layout changed.

**How the sector is built.** `model/layout.yaml` declares the gimbal centre, the head radius
(190 mm, from the payload envelope) and the sampling step (0.5°); the elevation range
(−120° to +30°) is read from the payload interface data, so no number is written twice. The
sector is sampled with one ray per step: 301 rays for the declared range.

**Three checks, and the marginal directions.**

| Check | Result |
| --- | --- |
| `FOV-OBSTRUCTION` | 0 of 301 rays obstructed, sector −120° to +30° clear |
| `FOV-SKIN` | highest ray 325 mm below the platform skin (requirement 25 mm) |
| `FOV-CLEARANCE` | tightest direction 0.0°, nearest element `SM-05` (lower fuselage step): **30 mm against the 25 mm requirement** |

The report lists the clearance direction by direction and has a *marginal directions*
section: the horizontal directions near 0° keep 30 mm, inside twice the requirement, and they
are named instead of averaged into a comfortable number. `evidence/clearance/` holds
`checks.json`, `report.md` and `sweep.svg` (the sector and the rays over the side view, with
obstructed rays in red and marginal rays in orange).

**Configurations.** The sector exists only with the payload installed; with the payload
removed there is nothing to sweep, and that configuration is bounded by the removal-corridor
check in the layout evidence. The report says so instead of pretending to analyse an empty
installation.

**Closure**

| Case | Status | What the evidence shows | What it does not |
| --- | --- | --- | --- |
| VER005 field of view and clearance | `PASS` | the swept sector is clear and the clearance is met in the declared geometry | the platform geometry is a declared 2D envelope, not a CAD model: the analysis bounds the clearance, it does not replace a 3D check |

Two `ASM-OPEN` warnings appear (`SYS008` on the declared field of view, `SYS009` on the
declared clearance), by design: the analysis is only as good as the declared envelope.

Model state: 38 requirements, 28 verification cases (`PASS` 8, `LIMITATION` 4, `FUTURE` 16),
90 layout checks, 96 tests. Validator: 0 errors, 8 warnings.
