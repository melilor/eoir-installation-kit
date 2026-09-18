# 10: Environmental qualification plan

**What to build:** the environmental qualification plan of the installation: DO-160G sections and categories selected per installation zone, the test matrix, the resonance and EMC assessment approach, and the platform protection preservation check against the protection plan.

**Blocked by:** 03, 09.

**Status:** resolved

- [x] Installation zones defined and the applicable DO-160G sections selected per zone, with the category for each
- [x] Category selection argued (temperature and altitude, vibration, humidity, salt spray, power input, RF emission and susceptibility) and every value traced to the declared zone
- [x] EMC approach stated: what is assessed by analysis and what requires a test on an article
- [x] Lightning and HIRF preservation check against the platform protection plan
- [x] What cannot be done without a test article declared as a limitation, not as an open item
- [x] Matrix regenerated; plan committed under `docs/`

## Answer

Closed on 2026-09-18. `model/qualification.yaml` declares the zones, the sections, the
categories, the methods, the articles and the protection means; `tools/qualification.py` checks
the plan and writes it into `docs/qualification-plan.md`, which is the compliance document
TP-001 — the register now points at it and the validator fails if it points anywhere else. 46
checks, all passing.

**The zones.** Three, taken from the layout rather than assumed: the external belly bay (Z-01,
ten components, everything below the skin line), the unpressurised fuselage interior with the
protection assembly and the mission system panel (Z-02, four components, from the platform
interface data), and a zone for what is not installed (Z-03, the documentation set, exempt from
qualification with the reason written down). Every architecture component is placed in a zone,
and that is checked.

**The sections.** 24 entries covering all 26 sections of the standard except the ones that do
not reach this installation, plus a functional test for the ARINC 429 control link and the
video link. The check that matters: **every DO-160G section a requirement cites appears in the
plan**, computed from the requirement references themselves — sections 4, 6, 8, 11, 12, 13, 14,
16, 20, 21 come from SYS014, SYS016, SYS033 and SYS034, and the plan answers all ten.

**What is selected, and what is not.** This is the honest part of the ticket. The standard is
not in this repository, so a category is written down only where a declared input of this study
and a public statement about the standard fix it:

| Selection | Why it is defensible |
| --- | --- |
| Section 4, family D for the belly bay | The bay is unpressurised external mounting, which is the D family; the declared payload range (−40/+55 operating, −55/+85 storage) sits inside the −55/+85 the section spans |
| Section 10, category T | T is externally mounted equipment subject to direct rainfall and washing, which is what the bay is |
| Section 16, category Z | The installation is 28 Vdc equipment, and Z is the 28 Vdc category for all other systems and is accepted in lieu of A or B, so it covers the platform whether the dc comes from a transformer-rectifier unit or from engine-driven generators with a battery on the bus |
| Section 8, family R or U | The robust categories apply to rotary wing, tested sine-on-random; the curve still comes from the table of categorisation by aircraft type and equipment location |
| Sections 7.3, 9, 10 for the interior bay, 12, 14, 23 and 24 outside the belly bay | The section does not reach that zone, and the reason is written next to it |

Thirty zone selections stay **open on a named input**: the compartment map, the design altitude,
the ramp rate, the HIRF and lightning environment, the radio compatibility limits, the fluid
list, the bus transient data, the icing approval, the platform magnetic survey. None of them is
filled with a plausible letter.

**Three entries are closed now, by analysis or inspection**, not by test: crash safety (7.3),
which the published statement limits to places where detached equipment can hurt somebody, so
the crash inertia loads are carried by the structural analysis of ticket 07 instead; explosive
atmosphere (9), which needs the platform to confirm that no fuel vapour zone reaches the
installation; and fungus (13), assessed by inspecting the declared materials, which are metals.

**Two findings the last two miles of work produced.**

The first: **the ticket-06 and 07 edits had left two evidence records for four verification
cases** (VER001, VER002, VER006, VER007). The loader kept the last one silently, so every check
stayed green while the register contradicted itself. The duplicates are gone, `tools/model.py`
now exposes them and `tools/rules.py` reports `EVIDENCE-DUPLICATE`, with a test that fails on a
model with two records for one case. That is a defect this study introduced and then caught by
checking its own register, and it is worth more than the plan itself.

The second: **`CONTEXT.md` had not been updated by ticket 07**, because a two-part edit of that
file failed as a whole and the failure was missed. The load path vocabulary and the
qualification vocabulary are in it now.

The third, and the one that cost five red pipelines: **the evidence leaked the platform's path
separator**. The success message of the plan check interpolated the `Path` object, so it read
`docs\qualification-plan.md` on the machine that generated the evidence and
`docs/qualification-plan.md` on the runner, and the freshness check compared one line of JSON
that differed by one character. The comparison next to it had been normalised; the message had
not. The same latent landmine sat in a layout check message and is fixed with it.

It took that long to find because **the log of a public repository needs a login**. What worked
was making the pipeline report a freshness failure as an annotation: the changed files, the
difference and the interpreter versions, which are readable without one. That script is now in
`.github/scripts/check_freshness.sh` and the step that needed it reports through it. The lesson
is not the path separator: it is that a check whose failure cannot be read is not a check.

The second finding of the same kind was a real order dependency, even if it turned out not to be
the cause: **the citation map was built in the order Doorstop reads the requirements in**, which
differs between file systems. `cited_sections` now walks them in identifier order and names
every requirement that cites a section, and a test reverses the order to prove the result does
not move. `tools/traceability.py` had sorted its requirements all along; the new tool had not.

Model state: 38 requirements, 28 verification cases (`PASS` 13, `LIMITATION` 10, `FUTURE` 5),
15 declared assumptions, 46 qualification checks, 150 tests. Validator: 0 errors, 12 warnings.
