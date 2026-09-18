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

The third, and the one that cost a red pipeline: **the citation map depended on the order
Doorstop reads the requirements in**, which differs between file systems. The evidence generated
on Windows attributed section 21 to SYS014 and the check on the Linux runner saw SYS016 first,
so the freshness check failed there and passed here. `cited_sections` now walks the requirements
in identifier order and reports every requirement that cites a section, and a test reverses the
order to prove the result does not move. `tools/traceability.py` had sorted its requirements all
along: the new tool was the one that forgot.

**EMC approach, stated as the ticket asks.** Twenty entries need a test on an article, two are
carried by analysis already committed in this repository (crash safety and the magnetic
assessment, the latter still open on the platform survey), one by inspection (fungus) and one by
review against a platform document (explosive atmosphere). The plan also declares the campaign
order, which follows the published practice of running the destructive tests last.

**Protection preservation.** Four means are declared — the bonding straps and grounding hardware
of CMP-07, the screened power pair with the connector shells bonded through the connector
bracket, the harness routing provisions of CMP-12, and the preservation argument itself — each
with what it serves, the section it belongs to, what it is checked against, and what cannot be
checked because the platform protection plan is referenced and not held.

**Closure**

| Case | Status | What the evidence shows | What it does not |
| --- | --- | --- | --- |
| VER010 plan review | `LIMITATION` | the sections each zone needs, with the method and the article | the categories: thirty zone selections wait for a platform input, and the standard is not held |
| VER025 fluids, sand, dust, fungus | `PASS` | the plan covers sections 11, 12 and 13 for both zones, with the fluid families, the sand and dust entry for the belly bay and the fungus assessment by material inspection | the platform fluid list, and the non-metallic items whose materials are not selected |
| VER026 lightning and static means | `PASS` | the protection means are present in the installation definition and named in the plan | whether they preserve the platform plan, which needs the plan (VER012) |
| VER009 bonding test | `LIMITATION` | the bonding path and the test planned on the first article (TP-002) | the resistance: no article exists |
| VER012 protection and radio review | `LIMITATION` | the four protection means with what each is checked against | the preservation argument and the emission limits: the plan and the radio compatibility limits are not declared (QI-01) |
| VER016 data link functional test | `LIMITATION` | the test is in the campaign as FT-01 | the test itself, and the video link format is still open |

Two `ASM-OPEN` warnings are added by this ticket (SYS033 and SYS034), because closing those two
reviews makes their evidence visible against the open assumption A-009 that the categories are
not yet selected. That is the intended behaviour, not a regression.

Model state: 38 requirements, 28 verification cases (`PASS` 13, `LIMITATION` 10, `FUTURE` 5),
15 declared assumptions, 46 qualification checks, 150 tests. Validator: 0 errors, 12 warnings.
