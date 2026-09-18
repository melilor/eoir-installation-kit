# 07: Load path and strength

**What to build:** the load cases, the load path through the attachment fittings and the frame, the factor-of-safety check and the resonance separation assessment — with the analysis script and its output committed as evidence.

**Blocked by:** 02, 08.

**Status:** ready-for-agent

- [ ] Load case set derived from the payload mass and envelope, the manoeuvre and gust envelope and the emergency landing inertia conditions
- [ ] Internal load path stated and the critical section identified per fitting
- [ ] Factor of safety 1.5 applied to limit loads, results against allowable with the margin stated (SYS002, SYS003)
- [ ] Resonance separation from the declared rotor excitation frequencies (SYS015)
- [ ] Where a closed-form hand calculation and the script disagree, the difference is investigated, not averaged
- [ ] Output committed under `evidence/` and referenced by VER001, VER002 and VER011
- [ ] Matrix regenerated
