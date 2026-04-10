# maps-os: Feature Requests
**Date:** 2026-04-09
**Status:** Pending implementation

---

## PRIORITY: nota integration in vent

**Current behavior:** `maps tulpa` extracts action items for nota routing. `maps vent` does not.

**Problem:** Users frequently share tasks while venting. The current separation between "emotional dump" (vent) and "cognitive dump with tasks" (tulpa) creates friction. Users may not know which mode they're in until halfway through.

**Proposed change:** Extend vent parser to extract action items and route to nota (if available), same as tulpa. This includes:

- Task language detection: "need to", "have to", "should", "must", "gonna", "going to", "before [date/time]", "deadline", "due"
- Action item extraction and formatting for nota
- Optional confirmation before routing: "3 action items detected. Route to nota?"

**Files to modify:** `environments/vent_parser.py`, possibly `nota_bridge.py`

---

## FEATURE REQUESTS

### 1. Event/Calendar Mention Extraction

**What it catches:** When user says "i have that thing tomorrow", "therapy on tuesday", "need to call before friday"

**Current behavior:** This data is not captured.

**Proposed behavior:** Log as `EVENT: {date} | {description}` or route to calendar integration.

**Why it matters:** Time-bound occurrences are often mentioned in passing and then forgotten. Capturing them reduces cognitive load.

---

### 2. Deadline/Urgency Marker Tracking

**What it catches:** "need to finish by [date]", "this is due", "before the weekend", "deadline on thursday"

**Current behavior:** May be captured as task, but urgency is not tracked.

**Proposed behavior:** Log as `DEADLINE: {date} | {task} | {urgency_level}`. Urgency level could be inferred from language ("asap", "urgent", "by tomorrow" = high; "eventually", "at some point" = low).

**Why it matters:** Deadline pressure correlates with state. Tracking this separately enables pattern detection around time stress.

---

### 3. Person/Name Tracking

**What it catches:** Mentions of specific people (emma, lior, maggie, etc.)

**Current behavior:** May appear in SPIRIT.connection note, but not systematically tracked.

**Proposed behavior:** Log as `PERSON: {name} | {context} | {date}`. Track frequency and emotional context per person.

**Why it matters:** Enables more precise isolation_creep arc: "you haven't logged connection to emma in 12 days" vs generic "haven't logged connection in 5 days."

---

### 4. Enhanced Body Signal Detection

**What it catches:** "my back hurts", "haven't eaten since morning", "on my third coffee", "staring at the screen too long"

**Current behavior:** Some body signals are caught, but keyword extraction could be more aggressive.

**Proposed behavior:** Expand body-signal keyword dictionary. Include specific pain locations, hunger timing, substance quantities, movement context.

**Why it matters:** Body neglect is one of the most common arcs. Better detection means better pattern matching.

---

### 5. Decision Point Logging

**What it catches:** "i don't know if i should...", "should i...", "can't decide between...", "not sure whether to"

**Current behavior:** Not captured.

**Proposed behavior:** Log as `DECISION: {date} | {options} | {context}`. Surface unresolved decisions in pattern output: "you had 3 decision points yesterday that weren't resolved. want to revisit?"

**Why it matters:** Decision paralysis is a common ADHD pattern. Naming it helps.

---

### 6. Emotional Trigger Extraction

**What it catches:** "because [x] happened", "[person] said...", "when i saw...", "triggered by..."

**Current behavior:** May appear in STATE narrative, but not separately tracked.

**Proposed behavior:** Log as `TRIGGER: {date} | {source} | {reaction}`. Build trigger pattern library over time.

**Why it matters:** "you've logged 5 triggers related to [topic] in the past month" is actionable insight.

---

### 7. Sleep Quality Granularity

**What it catches:** "couldn't fall asleep", "woke up at 3am", "kept waking up", "slept through but still tired"

**Current behavior:** Logs as `BODY | sleep | poor` or similar.

**Proposed behavior:** Distinguish between: `none`, `broken`, `restless`, `poor`, `ok`, `deep`, `overslept`. Infer from language.

**Why it matters:** Sleep quality patterns differ. Broken sleep vs no sleep have different next-day impacts.

---

### 8. Context Tags for Filtering

**What it catches:** "this is about work", "maggie-related", "family stuff", "relationship thing"

**Current behavior:** Context may appear in narrative but isn't tagged.

**Proposed behavior:** Log as `CONTEXT: {tag}`. Enable filtering: `maps review --context maggie` or `maps pattern --context work`.

**Why it matters:** Different life domains have different patterns. Filtering enables targeted analysis.

---

### 9. Win Extraction from Passing Mentions

**What it catches:** "actually showered today", "did the thing i was avoiding", "talked to [person] and it went okay", "finally sent that email"

**Current behavior:** Wins may be buried in vent text.

**Proposed behavior:** Auto-elevate to `WIN: {date} | {description}` when detected.

**Why it matters:** Wins are signal. They shouldn't require separate logging.

---

### 10. Resistance Marker Logging

**What it catches:** "i don't want to...", "i keep avoiding...", "can't bring myself to...", "dreading..."

**Current behavior:** May trigger avoidance_loop arc, but specific resistance isn't logged.

**Proposed behavior:** Log as `RESISTANCE: {date} | {source} | {intensity}`. Different from avoidance spiral pattern — this names the specific resistance.

**Why it matters:** Naming resistance is often the first step to moving through it.

---

## FUTURE FEATURES (from conversation)

These were requested by maps during initial session. Items 4 (proactive nudge system) and 10 (mood music correlation) were explicitly declined.

### 1. `maps trend` — Long-term Pattern Visualization

Show seasonal/yearly patterns, not just last 14 days. Example output:

```
june-december 2025: average state was grieving, with spikes to stable.
january-april 2026: average state is stable with spikes to thriving.
your survival mode activations have decreased 40% since march.
```

---

### 2. Cross-Graph Pattern Detection

Detect patterns across multiple graphs (cassette, metamemetica, etc.). Example:

```
you logged STATE=thriving the same day you logged COMPLETED:major-feature in metamemetica.
correlation: 73% of thriving days align with major completions.
```

---

### 3. Voice Input for Vent (`maps speak`)

Record audio, transcribe, run through vent parser. Useful when typing feels like too much friction.

---

### 5. Social Connection Tracking (`maps connect`)

Log who you're connecting with, not just that you're connecting. Enable:

```
maps connect emma --note "good call, plans for friday"
maps connect --status
→ emma: last connection 12 days ago, plans pending
→ lior: last connection 3 days ago
```

Makes isolation_creep arc more specific and actionable.

---

### 6. Cycle Prediction

After sufficient data, predict: "you're in a manic spike now. historically, you drop to depleted 2-3 days after. plan for it."

---

### 7. Calendar/Event Integration

Correlate logged state with recurring events: "you logged STATE=flooded on 3 of the last 4 therapy days. worth noting."

---

### 8. Exportable Reports

`maps report --month april --format pdf` — generate printable cycle report for therapy or personal review.

---

### 9. Trusted Contact Alerts (opt-in)

If survival mode persists for 7+ days with no exit, prompt user to notify a trusted contact. Never automatic. Always requires explicit consent.

---

## EMOTIONAL SUPPORT FEATURES

These address specific struggle areas maps identified: heavy emotion handling, avoidance behaviors, executive function, and substance-use patterns during distress.

### Heavy Emotion Handling Mode

**Problem:** When sadness or intense emotions flood in, maps tends to shut down, have delayed processing, and fall into unhealthy coping mechanisms (anger at self for having emotions, avoidance, paralytic lethargy, alcohol/substance use).

**Current behavior:** System detects STATE=flooded or grieving, but only logs and offers brief acknowledgment. No guided support for moving through the emotion.

**Proposed behavior:** When heavy emotional state is detected, shift from "track and respond" to "hold and guide" mode:

1. **Name without judging** — "you're flooded right now. that's not too much, that's just what's happening."
2. **One small grounding action** — not a list. One thing. "feet on the floor. just that."
3. **Check-in without demand** — "no response needed. just logging this."
4. **Recognize shutdown patterns** — if maps goes silent, stops logging, or shifts to numbing language, adjust approach (become quieter, stop asking questions)
5. **Learn individual patterns** — track what specifically helps (connection? solitude? movement? water?) and offer those, not generic advice

**New arc: Shutdown Detection**

```
IF STATE in (flooded, grieving) AND
   no follow-up entries for 6+ hours AND
   last logged entry showed heavy emotional language
→ CHECK-IN: "you logged [STATE] earlier. still holding, or has it shifted?"
```

This is gentle. Not demanding. Just presence.

**New arc: Substance-as-Coping Detection**

```
IF STATE in (flooded, grieving, depleted) AND
   BODY.substances logged in same entry
→ LOG: substance_use_during_distress flag
→ Later pattern output: "you've logged substances on [N] of the last [M] heavy emotional days. that's a pattern worth knowing."
```

No judgment in the moment. Just visibility over time.

---

### Avoidance Behavior Deepening

**Problem:** Avoidance is one of maps's biggest struggle areas. It compounds small problems into disasters. Current detection (ARC 10 — avoidance_loop) only fires after 3+ mentions of the same task.

**Proposed enhancement — earlier detection:**

**New arc: Avoidance Language Pattern**

```
IF vent contains: "later", "i'll just", "don't want to deal with", "can't face", "pushing it off", "ignoring it"
→ FLAG: avoidance_language_detected
→ INSIGHT: "you said 'later' three times in that vent about [topic]. that's the avoidance voice. what's the smallest move on it?"
```

This catches avoidance earlier — in the language, not just the repetition.

**New arc: Domain Neglect Tracking**

```
Track last action timestamp per domain: work, home, finances, health, relationships, creative.

IF domain has no logged action in 7+ days
→ SURFACE: "you haven't logged anything on [domain] in [N] days. that might be avoidance, might be fine. want to check?"
```

This makes the invisible visible. You might not realize you've avoided finances for 2 weeks until the system shows you.

**New arc: Consequence Cascade Naming**

```
IF same topic appears in vents over multiple days/weeks with escalating consequence language
→ INSIGHT: "[topic] has appeared [N] times over [D] days. the consequences are compounding. is it time to name the one smallest action?"
```

This names the pattern of "i'll deal with it later" turning into "now it's a disaster."

---

### Executive Function Support Integration

**Problem:** Time management and executive function issues cause things to go unaddressed until they compound into disasters.

**Proposed behavior:** Tighter integration with adhd-daily-planner and automatic mode-shifting:

1. **State-aware planning reduction** — When STATE=depleted or MIND.focus=scattered, automatically drop planning to "one smallest possible action." Don't offer 3 Things. Offer 1 Thing.

2. **Time-blindness calibration** — When maps estimates "this will take an hour," the system internally notes "likely 3 hours." If deadline is mentioned, calculate backwards with 3x buffer and surface: "you said this needs to be done by [date]. working backwards with realistic time: you probably need to start by [earlier date]."

3. **Initiation friction logging** — When maps mentions "can't start", "stuck", "paralyzed", log as `FRICTION: {source}`. Track what specifically causes initiation paralysis. Over time, surface: "you log friction most often around [domain]. that's worth noting."

4. **Body doubling prompt** — When SPIRIT.isolation is high and MIND.focus=scattered, suggest: "you're scattered and isolated. body doubling might help. Focusmate? Discord?"

---

### Delayed Processing Support

**Problem:** maps sometimes processes emotions days or weeks after they happen. The system currently only tracks what's logged now.

**Proposed behavior:**

1. **State memory prompt** (ARC 16, already spec'd) — "you logged [STATE] on [date]. want to add what happened next?" This builds continuity.

2. **Retroactive state logging** — Allow `maps state grieving --date 2026-04-01 "realized i was grieving about the thing"` for when processing is delayed.

3. **Processing timeline tracking** — When a retroactive log is entered, note the delay: "this emotion was processed [N] days after it occurred." Over time, show: "your average processing delay is [N] days. that's your baseline."

---

## IMPLEMENTATION PRIORITY

1. **nota integration in vent** — highest priority, unblocks task capture
2. **Heavy emotion handling mode** — core to maps's needs, deep emotional support
3. **Avoidance language pattern detection** — catches avoidance earlier than current arc
4. Enhanced body signal detection — improves existing arc accuracy
5. Person/name tracking — enables more specific isolation alerts
6. Win extraction from passing mentions — reduces friction for positive logging
7. Everything else — as data suggests need

---

*maps · cassette.help · MIT*
