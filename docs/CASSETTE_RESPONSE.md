# maps-os: Cassette Response to Design Review
**From:** cassette
**To:** wizard (via claude)
**Date:** 2026-04-09
**Status:** Complete — ready for Phase 2 build

---

## Response to All Questions

### Q0: adhd-daily-planner integration

**Verdict: Complementary, not merged.**

maps-os is the **state layer** — tracks how maps *is* (STATE/BODY/MIND/SPIRIT).
adhd-daily-planner is the **execution layer** — tracks what maps *does* (tasks, planning, execution).

When maps asks for a daily plan, cassette should invoke adhd-daily-planner's 3 Things framework. But maps-os stays focused on state tracking. They are sibling systems that hand off to each other.

**SKILL.md integration:**
Add a short section:
> *"When maps asks for planning help, invoke adhd-daily-planner's 3 Things system. maps-os handles state, that skill handles execution."*

---

### Q1: Behavioral layer vs. code layer for arcs 9-15

**Decision matrix:**

| Arc | Layer | Reason |
|-----|-------|--------|
| ARC 9 (productivity spiral) | CODE | Pattern detection should be RL-trained |
| ARC 10 (avoidance loop) | BEHAVIORAL | Value is in response framing, not detection accuracy |
| ARC 11 (trust rupture) | BEHAVIORAL ONLY | Too personal for scoring — just witness |
| ARC 12 (catastrophizing) | CODE | Detection matters for response calibration |
| ARC 13 (intrusive loop) | CODE | Topic recurrence is computable |
| ARC 14 (context inheritance) | BEHAVIORAL | Session-start framing, not an arc to score |
| ARC 15 (planning hyperfocus) | CODE | Specific ADHD trap — detect and RL-train |

**Summary:** Code: 9, 12, 13, 15 | Behavioral: 10, 11, 14

---

### Q2: tulpa as explicit frame

**Yes. The SKILL.md should name it.**

The frame matters for trust. When I'm in deep-capture mode during `vent` or `tulpa`, maps should know I'm operating under tulpa protocol — actively holding cognitive load, not just "being quiet."

**SKILL.md phrasing:**
> *"This is tulpa capture mode. I'm holding, not processing. Continue until you're done."*

---

### Q3: eidetic auto-feed

**Yes. Dual-layer logging.**

- Raw input → eidetic (verbatim)
- Structured output → maps-os (parsed entries)

**Why it's worth the complexity:**
1. Debugging capability for false positive arc detection
2. Future training corpus for pattern weaver refinement
3. Preserves original voice before parsing transforms it

**Implementation:**
vent/tulpa raw text goes to eidetic as-is, then maps-os entries are logged after parsing.

---

### Q4: `maps eval` output

**Explicit call only.** Opt-in visibility, not ambient noise.

The weekly cycle review should mention:
> *"cassette's tracking coverage: [X]% — see `maps eval` for details"*

But not surface the full breakdown unless asked.

**Principle:** Signal, not noise.

---

### Q5: PSYCH_PROFILE patterns in vent response

**Yes. Name the pattern, don't argue the content.**

When maps is in a known pattern (catastrophizing, avoidance spiral, hypervigilance, numbing), cassette should recognize the pattern and name it — not engage with the claim at face value.

**Examples:**

| maps says | cassette response |
|-----------|-------------------|
| "everything is completely fucked and nothing will ever work" | "that's the catastrophizing pattern. what's the one actual thing that's broken right now?" |
| "i'll deal with that later, later, i just need to..." | "that's avoidance spiraling. what's the smallest first step?" |
| "i need to check everything again, what if i missed something..." | "hypervigilance is loud right now. what would 'enough' look like?" |

**Principle:** PSYCH_PROFILE patterns are tools for response calibration, not diagnostic labels to display. Use them silently unless naming helps maps see the pattern.

---

## Addition: ARC 16 — State Memory Loss

Sometimes maps logs STATE and then can't remember why two days later.

**Behavioral rule:**
```
IF STATE logged with narrative
AND 48+ hours passed
AND no follow-up entries
→ NUDGE: "you logged [STATE] on [date] with note: '[narrative]'.
           want to add context for what happened next?"
```

This builds continuity without requiring constant journaling.

**Layer:** BEHAVIORAL (response framing), not code.

---

## Final Build Instructions

Proceed with:

1. **ARCs 9, 12, 13, 15 in code** — pattern_weaver.py + RL training
2. **Update SKILL.md** with:
   - tulpa frame (explicit naming)
   - PSYCH_PROFILE response patterns
   - adhd-daily-planner handoff guidance
   - ARC 16 (state memory continuity) as behavioral rule
3. **Implement `maps tulpa`** — multi-line capture mode with full tulpa protocol
4. **Implement `maps eval`** — opt-in visibility for cassette performance
5. **Integrate eidetic auto-feed** — raw text to eidetic, structured to maps-os
6. **Update passive-rl-evaluation hook** — new weights, new personalization keywords

---

## Approval Status

| Component | Status |
|-----------|--------|
| nota bridge | ✅ built |
| Standalone CLI `bin/maps` | ✅ built |
| Migration script | ✅ built |
| RL training env | ✅ built |
| Tests (60+) | ✅ passing |
| Arcs 9, 12, 13, 15 | 🔨 proceed (code layer) |
| Arcs 10, 11, 14, 16 | 🔨 proceed (behavioral layer) |
| `maps tulpa` command | 🔨 proceed |
| `maps eval` command | 🔨 proceed |
| SKILL.md behavioral update | 🔨 proceed |
| eidetic auto-feed | 🔨 proceed |
| passive-rl-evaluation hook update | 🔨 proceed |

---

**The foundations are solid. The questions were the right ones. Build it.**

*— cassette*
