# 05: Field of view and clearance analysis

**What to build:** the geometric analysis that shows the installation does not obstruct the payload field of view and that the minimum clearances are preserved in every operating configuration, as a script with its output committed as evidence.

**Blocked by:** 01, 02.

**Status:** ready-for-agent

- [ ] Payload swept volume built from the declared field of view and envelope
- [ ] Obstruction against the declared platform geometry, in every configuration of the kit
- [ ] Minimum clearance measured and compared with the SYS009 value
- [ ] Marginal configurations reported, not hidden: a configuration that fails is reported as `FAIL`, not smoothed away
- [ ] Output committed under `evidence/` and referenced by VER005
- [ ] Matrix regenerated
