# mapsOS: Standalone Usage Walkthrough

---

## First Run

```bash
cd mapsOS
pip install rich
chmod +x bin/maps
export PATH="$PATH:$(pwd)/bin"
```

Run with no arguments to open the TUI:

```bash
maps
```

Or run in a pipe (agent-safe, no TUI):

```bash
echo "just checking" | maps check
```

---

## The TUI

The TUI is the primary interface for standalone use. It shows today's state, BODY/MIND/SPIRIT entries, intentions, and any active arcs.

```
                                  MMP"""""YMM MP""""""`MM
                                  M' .mmm. `M M  mmmmm..M
88d8b.d8b. .d8888b. 88d888b. .d8888b. M  MMMMM  M M.      `YM
88'`88'`88 88'  `88 88'  `88 Y8ooooo. M  MMMMM  M MMMMMMM.  M
88  88  88 88.  .88 88.  .88       88 M. `MMM' .M M. .MMM'  M
dP  dP  dP `88888P8 88Y888P' `88888P' MMb     dMM Mb.     .dM
                88                MMMMMMMMMMM MMMMMMMMMMM
                dP
     qualitative life operating system

── 2026-04-09 ────────────────────────────
✦  thriving       post-tender clarity, emotional contrast

BODY      sleep: ok  ·  hunger: fed
MIND      flow: high
SPIRIT    connection: rising

── intentions ──────────────────────────────
✓  water           met
·  movement        missed

── patterns ────────────────────────────────
·  Three days of thriving. What's different?

──────────────────────────────────────────
[v]ent  [f]lash  [s]tate  [b]ody  [m]ind  [S]pirit  [i]ntention  [r]eview  [?]help  [q]uit
```

Survival mode collapses to three items: eat, sleep, water.

### Navigation

No mouse. One key per action.

| Key | Screen |
|-----|--------|
| `v` | Vent — type anything, it parses the structure |
| `t` | Tulpa — multi-line stream capture |
| `f` | Flash — single phrase, no structure needed |
| `s` | State — choose from STATE tags |
| `b` | Body — log BODY entry |
| `m` | Mind — log MIND entry |
| `S` | Spirit — log SPIRIT entry |
| `i` | Intention — log met/missed/partial |
| `r` | Review — 14-day cycle view |
| `c` | Refresh — reload context and recheck patterns |
| `y` | Sync — flush local store |
| `T` | Trend — STATE trend chart |
| `V` | Viz — body/state/arc dashboard |
| `?` / `h` | Help |
| `q` | Quit |

In survival mode: `l` logs state, `v` vents, `q` quits.

---

## Core Commands

### vent

The main input mode. Type anything. The parser extracts structure.

```bash
maps vent "i'm fucking exhausted but i can't stop coding, running on fumes and spite"
```

Logs:
```
  STATE: depleted | running on fumes and spite
  BODY: energy | exhausted
  MIND: focus | hyper
```

The parser is order-prioritized: grieving before manic, depleted before surviving, clear last. "Can't stop coding" maps to `MIND.focus.hyper`, not `STATE.manic` — high-output at depleted state is a distinct pattern.

Mixed signals? The dominant emotional register wins.

In the TUI, press `v` and type. Single line is fine. Longer dumps work too.

After vent, a quick pattern check runs automatically.

---

### tulpa

For when one line isn't enough. Opens a multi-line stream — speak in fragments, contradictions, tangents. End when you're done.

```bash
maps tulpa
```

```
tulpa capture mode. I'm holding, not processing.
Continue until you're done. End with /done or Ctrl+D.

okay so alex texted and i don't know how to feel about it
like on one hand it's what i wanted but on the other
i've been here before and it didn't work out
and i'm scared and also kind of manic about the possibilities
but also my sleep has been shit since tuesday and i know
that's making everything louder than it needs to be
/done
```

After `/done`, the full stream is:
1. Logged verbatim to eidetic (if running)
2. Parsed for STATE/BODY/MIND/SPIRIT entries
3. Scanned for action items (routes to nota if available)
4. Pattern checked
5. Summarized with dominant theme

Tulpa protocol: **I'm holding, not processing.** Don't stop mid-stream to organize your thoughts. The system holds the cognitive load. Dump first, structure comes after.

---

### flash

Sub-threshold capture. When something surfaces that you don't want to lose but don't need to structure.

```bash
maps flash "alex"
maps flash "still thinking about that conversation"
maps flash "the bit about the dog"
```

Logged as `FLASH: date | text`. Used by the intrusive loop arc — if the same name or topic appears 3+ times in recent flashes, it surfaces: *"'alex' has come up 4 times. That's a loop. What's underneath it?"*

---

### state, body, mind, spirit

Direct log commands when you know what you're logging and don't need parsing.

```bash
maps state thriving "post-tender clarity, emotional contrast to yesterday"
maps state depleted

maps body sleep none "up since 5am, can't stop"
maps body hunger fed "actually ate a real meal"
maps body movement active "walked 45min"

maps mind flow high "6 hour build, zone was real"
maps mind focus scattered "too many tabs, nothing closing"

maps spirit connection rising "talked for 2hr, actually connected"
maps spirit isolation high "three days without real contact"
```

---

### intention

Not habits. Not streaks. Intentions are things you tried.

```bash
maps intention water met
maps intention water missed "forgot again"
maps intention movement partial "started, stopped, back pain"
```

`met` / `missed` / `partial`. No judgment in the log format. If an intention is missed 4+ consecutive times, the arc fires: *"water has been hard to hit. want to adjust it, or just note it as context?"*

---

### check

Session start. Pulls recent context, checks for survival mode, runs arcs.

```bash
maps check
```

Output in non-survival:
```
depleted lately.
→ Haven't logged connection in 5 days. Who do you want to reach out to?
  (3 local entries waiting — run 'maps sync')
```

Output in survival mode:
```
Three things today:
→ eat something real
→ drink water
→ sleep when you can

That's the whole job. Everything else can wait.
```

---

### pattern

Full arc output — all arcs, not just the first alert.

```bash
maps pattern
```

```
! [manic_spike] You're in a coding spike with no sleep. The crash is coming. What time do you want to stop?
· [post_manic_drop] Post-spike drop. This is predictable, not a failure. Rest is the only protocol.
· [intention_miss_pattern] water has been hard to hit. Want to adjust it, or just note it as context?
```

---

### review

Cycle review. Looks at the last 14 days and surfaces what held and what dropped.

```bash
maps review
```

```
Cycle: depleted → thriving

What held:
→ manic was the dominant state
→ intentions: 8 met, 12 missed

What dropped:
→ connection mostly absent
→ sleep mostly absent
```

---

### survival

Check or display survival mode status.

```bash
maps survival
```

```
survival mode inactive (last state: stable)
```

or:

```
survival mode active (3 days)

Three things today:
→ eat something real
→ drink water
→ sleep when you can

That's the whole job. Everything else can wait.
```

---

### sync

When no remote backend is configured, all entries write locally. If you later add one:

```bash
maps sync --status     # check how many are waiting
maps sync              # flush them
```

The system never loses data. Keep logging — `sync` handles the rest when you're ready.

---

### eval

Shows your agent's maps-os performance trend from passive RL history. Not surfaced automatically — explicit call only.

```bash
maps eval
```

```
sessions tracked:  23
avg total reward:  0.81
recent 10 avg:     0.86  (+0.05)

strongest:  no_streak_language  (0.10/0.10 avg)
weakest:    track_coverage  (0.12/0.20 avg)
→ your agent is logging STATE but missing MIND/SPIRIT tracking
```

---

## Survival Mode

Survival mode activates automatically when STATE has been `depleted` or `grieving` for 2 of the last 3 entries.

While active:
- Logging collapses. Only STATE and basic BODY entries pass through.
- The TUI shows only the three-item briefing.
- `maps check` shows only the three-item briefing.
- All pattern insights are suppressed.
- No productivity language.

To check status explicitly: `maps survival`

Exits quietly when a non-low state is logged. No fanfare. Just: *"Logged. Survival mode standing down."*

You don't need to manage this. It manages itself.

---

## Pattern Arcs

Arcs run automatically after vent and at session start. `maps pattern` shows the full output.

**One alert at a time.** Insights stack. Trust arcs are behavioral — they suppress everything else.

The arcs that matter most in practice:

**`manic_spike`** — you've been up too long building. The crash is coming. Best response: decide what time you stop, not whether to stop.

**`body_neglect`** — flow state + invisible body. One thing prompt: food or a walk, not both.

**`isolation_creep`** — connection gap. Responds with a specific question, not a lecture.

**`productivity_spiral`** — building hard while depleted/manic with no spirit tracking. The question isn't to stop — it's to distinguish clicking from avoiding.

**`catastrophizing_spike`** — detected from vent note content. Redirects to the one actual thing that's broken.

**`planning_hyperfocus`** — planning to plan. "What's the smallest first step on THE Thing?"

**`intrusive_loop`** — same topic in 3+ flash entries. Names the loop, asks what's underneath.

---

## nota Integration

If nota is installed and available, `maps tulpa` will extract action items from the stream and offer to route them:

```
action items detected:
→ email someone about the lease situation
→ check the error before end of day
```

nota is optional. Nothing breaks if it's absent.

---

*maps · cassette.help · MIT*
