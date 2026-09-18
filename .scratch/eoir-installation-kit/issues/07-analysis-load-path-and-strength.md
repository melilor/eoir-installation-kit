# 07: Load path and strength

**What to build:** the load cases, the load path through the attachment fittings and the frame, the factor-of-safety check and the resonance separation assessment — with the analysis script and its output committed as evidence.

**Blocked by:** 02, 08.

**Status:** resolved

- [x] Load case set derived from the payload mass and envelope, the manoeuvre and gust envelope and the emergency landing inertia conditions
- [x] Internal load path stated and the critical section identified per fitting
- [x] Factor of safety 1.5 applied to limit loads, results against allowable with the margin stated (SYS002, SYS003)
- [x] Resonance separation from the declared rotor excitation frequencies (SYS015)
- [x] Where a closed-form hand calculation and the script disagree, the difference is investigated, not averaged
- [x] Output committed under `evidence/` and referenced by VER001, VER002 and VER011
- [x] Matrix regenerated

## Answer

Closed on 2026-09-18. `model/loads.yaml` declares the material allowables, the structural
idealisation and the design rules; `tools/loads.py` derives the seven load cases from the
declared accelerations, runs each one through the load path and writes `evidence/loads/`
(`checks.json`, `report.md`, 44 checks, all passing).

**The geometry was wrong before the loads could be run.** The four attachment points did not
form the rectangle the platform interface control file declares: the two aft fittings carried
bolt patterns at 140 mm and 170 mm where the forward pair sat at 150 mm, giving a lateral
spacing of 320 mm against the declared 300 mm, and one of the two aft patterns had its two
holes collinear instead of mirrored. The load path shares the reaction equally between four
fittings, so the defect was fixed in `model/layout.yaml` (both aft fittings moved to the
mirror position) and a check was added that would have caught it: `ATTACHMENT-SPACING` measures
the bolt-pattern centres against the platform provisions, and `ATTACHMENT-PATTERN` fails when
the four centres are not a rectangle. 93 layout checks now.

**The load cases, and which one governs.** Five of the seven are listed in the platform data;
the two manoeuvre cases are limit loads and take the factor of safety, the emergency landing
conditions are prescribed as ultimate and take none.

| Case | Basis | Prescribed | Ultimate | Force | Governing fitting |
| --- | --- | --- | --- | --- | --- |
| LC-MAN-UP | limit | 3.5 g | 5.25 g | 3052 N | 763 N |
| LC-MAN-DOWN | limit | −1.0 g | −1.5 g | 872 N | 218 N |
| LC-EML-UP | ultimate | 3.0 g | 3.0 g | 1744 N | 436 N |
| LC-EML-DOWN | ultimate | 3.0 g | 3.0 g | 1744 N | 436 N |
| LC-EML-FWD | ultimate | 4.0 g | 4.0 g | 2325 N | 600 N |
| LC-EML-AFT | ultimate | 4.0 g | 4.0 g | 2325 N | 600 N |
| LC-EML-LAT | ultimate | 2.0 g | 2.0 g | 1163 N | 366 N |

**The manoeuvre case governs, not the emergency landing**: the factor of safety lifts 3.5 g of
limit manoeuvre to 5.25 g of ultimate load, more than the 3.0 g the platform declares for the
crash case. Everything downstream is sized by that case.

**A vertical force makes no couple, a horizontal one does.** The payload centre of gravity sits
115 mm below the attachment plane — derived from the payload interface data and the layout
envelope, not typed in. A vertical inertia force acts along the centre of the attachment
pattern, so it divides equally between the four fittings. A horizontal force acts *below* the
plane: it adds a couple, and the fittings resist it in pairs, 148.6 N of tension or compression
when the payload pushes forward at 4 g.

**The strength checks are not what sizes this installation.**

| Check | Worst value | Limit | Margin |
| --- | --- | --- | --- |
| `LOADS-HARD-POINT` | 763 N | 25 000 N per point | +24 237 N |
| `LOADS-FITTING-NET-SECTION` | 15.26 MPa | 310 MPa | +295 MPa |
| `LOADS-BEARING` | 4.77 MPa | 390 MPa | +385 MPa |
| `LOADS-BOLT` (shear and tension interaction) | 0.019 | 1.0 | +0.98 |
| `LOADS-LIMIT-STRESS` at limit load | 10.17 MPa | 260 MPa (Fty) | +250 MPa |

At the critical section of the fitting the analysis combines three effects — bending from the
direct share over the declared lever, axial stress from the couple, and the in-plane shear —
by the combination rule declared in the model, because comparing only the largest one with the
allowable would flatter the result.

**The hand calculation and the script agree on the components and disagree on the total, and
the difference is the interesting part.** On LC-EML-FWD the closed form gives 581.3 N of direct
share and 148.6 N of couple share; the general solution gives the same two numbers to within
0.00 %, which is what `LOADS-HAND-CHECK` verifies. But the closed form adds them — 730 N —
while the general solution resolves them as a vector — 600 N, **+21.6 %**. The two shares act
on different axes, so adding them is not a conservative simplification but a different
quantity. It errs on the safe side for a hand calculation, and it would be the wrong number to
publish: the checks use the resultant.

**Deflection fits inside the clearance the field of view analysis left.** Under LC-MAN-UP at
limit load the payload moves 2.18 mm relative to the platform, with the load path stiffness of
933 N/mm and the softest support idealisation, which is the one that gives the largest
movement. The tightest direction of the swept sector has 30 mm against a requirement of 25 mm,
so 5 mm were available: the movement uses 44 % of the margin. This is the first time the
structural analysis and the geometric analysis have been checked against each other, which is
what SYS009 asks for and what a single discipline would have missed.

**The resonance separation is not demonstrated, and the analysis says why.** The excitation
bands are computed from the declared rotor speeds, the three blade main rotor and the two blade
tail rotor, with the 10 % criterion applied:

| Rotor | Harmonic | Band |
| --- | --- | --- |
| main | 1/rev | 5.25 – 7.33 Hz |
| main | 2/rev | 10.50 – 14.67 Hz |
| main | 3/rev | 15.75 – 22.00 Hz |
| tail | 1/rev | 30.00 – 44.00 Hz |
| tail | 2/rev | 60.00 – 88.00 Hz |

Six admissible windows exist between the bands. The installation is estimated at **21.9 to
43.3 Hz** — the interval between the simply supported and the clamped idealisation of the frame
rails, which is the honest range a single degree of freedom model can give. That interval
crosses the 3/rev band and the tail rotor 1/rev band, and **no window is wide enough to contain
it**: the uncertainty of the estimate is wider than the gap between the harmonics. Raising the
first mode above the highest band would need 136 mm square rails of the declared wall
thickness, 8.8 kg of frame instead of 5.6 kg — 3.2 kg more against a kit budget with 1.4 kg
left. So the case is closed as a `LIMITATION` with an open item: it needs a modal analysis or a
ground vibration test on the first article, and possibly a damper, not a blind stiffness
increase.

**A traceability gap that the loads exposed.** The declared emergency landing factors (3.0 g up,
3.0 g down, 4.0 g forward, 4.0 g aft, 2.0 g lateral) are platform criteria, and the study runs
them as ultimate. They are not 14 CFR 27.561: that clause covers each occupant and the items of
mass *inside the cabin*, with factors of 4 g up / 16 g forward / 8 g sideward / 20 g down /
1.5 g rearward; 27.561(c) covers items of mass above and behind the cabin, and 27.561(d) the
structure in the fuel tank area. A belly installation is outside all three, so the factors are
declared data whose traceability has to be confirmed by the platform. Recorded as open item
OI-01 rather than dressed up as a citation.

**The hand calculation block was not the only reference: the clauses were checked.** 14 CFR
27.301 (prescribed loads are limit loads unless otherwise provided), 27.303 (factor of safety
1.5, and no factor where a condition is prescribed as ultimate), 27.305 (limit loads without
detrimental deformation, ultimate loads without failure), 27.337 (manoeuvre envelope +3.5 to
−1.0) and 27.561 (emergency landing) were read on the public text before being cited.

**Closure**

| Case | Status | What the evidence shows | What it does not |
| --- | --- | --- | --- |
| VER001 load transfer | `PASS` | seven cases, four fittings, reactions computed from the inertia force and the couple, against the declared hard point capability | the platform capability is declared data; the payload interface and the plate are not checked |
| VER002 factor of safety | `PASS` | the factor per case against the factor that case requires, and the stresses against the declared allowables | the allowables are declared handbook values (A-014); welds and the interface plate are not sized |
| VER011 resonance | `LIMITATION` | the excitation bands and the admissible windows, and the estimate with its uncertainty | the separation itself: a single degree of freedom model cannot establish it (OI-02) |

Model state: 38 requirements, 28 verification cases (`PASS` 11, `LIMITATION` 6, `FUTURE` 11),
15 declared assumptions, 93 layout checks, 44 load path checks, 127 tests. Validator: 0 errors,
10 warnings.
