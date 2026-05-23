     1|# mapsOS
     2|
     3|![mapsOS](mapsOS.png)
     4|
     5|Life tracking that works with how you actually think, not how productivity apps assume you do.
     6|
     7|Not a habit tracker. Not a mood journal. Not a productivity app.
     8|
     9|mapsOS tracks narrative states, surfaces patterns across days and weeks, and knows when to drop everything non-essential. Runs as a standalone CLI and TUI with local SQLite storage and an optional remote backend.
    10|
    11|Paired with cartographer, it becomes the qualitative layer of atlas:
    12|
    13|- mapsOS = how you're actually doing
    14|- cartographer = what happened, what matters, what the agents learned
    15|- atlas = the shared substrate underneath both
    16|
    17|<table>
    18|<tr>
    19|<td align="center"><img src="docs/screenshots/splash.png" width="440"><br><sub>splash + loading</sub></td>
    20|<td align="center"><img src="docs/screenshots/dashboard.png" width="440"><br><sub>dashboard — sparkline · body grid · arcs</sub></td>
    21|</tr>
    22|<tr>
    23|<td align="center"><img src="docs/screenshots/viz.png" width="440"><br><sub>viz panel — state · body · arc frequency</sub></td>
    24|<td align="center"><img src="docs/screenshots/about.png" width="440"><br><sub>about screen</sub></td>
    25|</tr>
    26|</table>
    27|
    28|---
    29|
    30|## why this exists
    31|
    32|Most life-tracking tools assume you have capacity.
    33|mapsOS doesn't.
    34|
    35|It tracks qualitative state - not scores, not percentages - and adjusts
    36|what it asks of you based on where you actually are. Built during a period
    37|of genuine crisis, by someone for whom "surviving" is a real state that
    38|needed a name.
    39|
    40|That origin is why it works better than most tools even when things are fine.
    41|It was tested at the edges first.
    42|
    43|---
    44|
    45|**Built for one brain, configured for yours.**
    46|
    47|Every state tag is configurable. Every track dimension is configurable.
    48|"Survival mode" is what it's called by default - but if that language
    49|doesn't fit your situation, a single config line turns it into
    50|"low capacity mode." Your call. Your vocabulary.
    51|
    52|The state vocabulary ships with 10 tags that cover a lot of human experience.
    53|Replace them all. Add your own. Build a profile for your specific neurodivergent
    54|pattern. Share it with your community.
    55|
    56|-> See `~/.maps_os_config.yaml`, `environments/maps_os_config.example.yaml`, and [DEVELOPERS.md](../cartographer/DEVELOPERS.md)
    57|
    58|---
    59|
    60|## what shipped in this push
    61|
    62|This release turns mapsOS from a standalone tracker into one half of a tighter atlas loop.
    63|
    64|- **Atlas handoff in the TUI.** Press `C` inside mapsOS to launch `cart tui`, then return to mapsOS when you exit.
    65|- **Auto-ingest on exit.** mapsOS now writes its structured export and ingests it back into cartographer automatically when `cart` is available.
    66|- **Atlas context in the dashboard.** Open P0/P1 task counts and recent session context can surface directly inside the mapsOS TUI.
    67|- **State vocabulary is configurable.** The shipped 10 STATE tags are now defaults, not law.
    68|- **Tracks are configurable.** BODY / MIND / SPIRIT are the default shape, but your config can define its own categories.
    69|- **Capacity language is configurable.** If "survival mode" is right, use it. If "low capacity mode" is better, flip one config value and keep the behavior.
    70|
    71|---
    72|
    73|## What It Tracks
    74|
    75|### STATE
    76|The primary axis. One tag per session — the dominant emotional/psychological reality. No scores. No averages.
    77|
    78|| Tag | Meaning |
    79||-----|---------|
    80|| `surviving` | minimal function, getting through |
    81|| `stable` | neutral baseline, nothing wrong, nothing lit |
    82|| `grounded` | anchored, present, not drifting — active quality distinct from `stable` |
    83|| `thriving` | genuine forward momentum, things clicking |
    84|| `tender` | emotionally soft, open, post-connection warmth — still, not momentum |
    85|| `grieving` | loss-adjacent (person, phase, possibility) |
    86|| `manic` | elevated, fast, possibly unsustainable |
    87|| `depleted` | tank empty, may still be functional |
    88|| `flooded` | emotionally overwhelmed, nervous system loud |
    89|| `clear` | post-storm clarity, unusual perceptual sharpness |
    90|
    91|### BODY / MIND / SPIRIT
    92|Three tracks that can diverge wildly from each other.
    93|
    94|- **BODY** — sleep, pain, hunger, movement, substances, energy
    95|- **MIND** — focus, clarity, overwhelm, flow
    96|- **SPIRIT** — connection, creativity, purpose, isolation
    97|
    98|These are defaults, not hardcoded doctrine. The example config now shows how to swap categories or add whole new tracks.
    99|
   100|### Extended Tracking
   101|Extracted automatically from vent text or logged via CLI:
   102|
   103|| Track | What it captures |
   104||-------|-----------------|
   105|| `WIN` | Executive function wins — things done despite resistance |
   106|| `PERSON` | People in orbit — contact, context, sentiment |
   107|| `DECISION` | Unresolved choice points |
   108|| `RESISTANCE` | Internal friction — knowing what to do but not being able to start |
   109|| `TRIGGER` | Events that shifted state |
   110|| `GOAL` | Longer-arc intentions with status tracking |
   111|| `EVENT` | Upcoming calendar events, auto-extracted from vent |
   112|| `DEADLINE` | Time-sensitive obligations |
   113|| `FLASH` | Sub-threshold signals — no structure, just capture |
   114|
   115|### INTENTIONS
   116|Not habits. Not streaks. Just honest tracking of what was tried.
   117|`met` / `missed` / `partial` — no judgment in the schema.
   118|
   119|---
   120|
   121|## CLI Reference
   122|
   123|```bash
   124|# core tracking
   125|maps vent "i'm exhausted but i can't sleep"   # full parser → auto-log
   126|maps flash "laundry"                          # sub-threshold capture, no structure
   127|maps state thriving "post-storm clarity"      # direct state log
   128|maps body sleep none "up since 5am"           # direct body log
   129|maps mind flow high "6hr build session"       # direct mind log
   130|maps spirit connection rising "good call"
   131|maps intention water missed "forgot again"
   132|maps intention movement met "walked 45min"
   133|
   134|# session + pattern
   135|maps check                    # session start: context pull + arc check
   136|maps check --role             # + agent mode guidance (STATE → role, energy tier, refs to load)
   137|maps check --load-brief ~/atlas/daily/brief-2026-04-17.md
   138|maps session-start            # composed session-start packet with cart bridge context
   139|maps session-start --role librarian
   140|maps session-start --json
   141|maps pattern                  # full pattern weaver output
   142|maps review                   # cycle review (last 14 days)
   143|maps survival                 # check / display survival mode
   144|maps export                   # write ~/.mapsOS/exports/session_*.json for cartographer ingest
   145|
   146|# extended capture
   147|maps tulpa                    # multi-line stream capture
   148|                              # end with /done or Ctrl+D
   149|
   150|# wins + goals
   151|maps wins                     # recent wins, grouped by week
   152|maps wins --week              # this week only
   153|maps wins --month             # this month only
   154|maps goal "sort housing"      # log a new goal
   155|maps goal --due 2026-05-24 "housing"
   156|maps goal --list              # open goals
   157|maps goal --done <phrase>     # mark complete
   158|maps goal --update <phrase>   # mark in_progress
   159|
   160|# events + deadlines
   161|maps events                   # upcoming events
   162|maps events --week            # this week only
   163|
   164|# people
   165|maps person grungler          # profile + recent interactions
   166|maps person --list            # all known people + last contact
   167|
   168|# visualization
   169|maps trend                    # STATE trend (last 30 days)
   170|maps trend --days 7           # shorter window
   171|maps viz                      # body/state/arc dashboard
   172|
   173|# server
   174|maps serve                    # run HTTP server in foreground
   175|maps serve install --host 127.0.0.1
   176|maps serve status
   177|maps serve restart
   178|maps serve uninstall
   179|
   180|# system
   181|maps doctor                   # serve + bridge + export + cart health check
   182|maps doctor --json
   183|maps eval                     # agent performance trend (last 30 days)
   184|maps eval --days 7
   185|maps connect <name>           # log connection + PERSON entry
   186|maps connect --status         # last contact per known person
   187|maps sync                     # flush deferred local entries when available
   188|maps sync --status            # pending entry count
   189|```
   190|
   191|Running `maps` with no arguments in a TTY launches the TUI.
   192|On TUI exit, mapsOS writes a structured session export and ingests it into cartographer automatically when `cart` is available.
   193|
   194|## launchd
   195|
   196|If you don't want to dedicate a terminal to `maps serve`, install it as a user LaunchAgent:
   197|
   198|```bash
   199|maps serve install --host 127.0.0.1
   200|maps serve status
   201|maps serve restart
   202|maps serve uninstall
   203|```
   204|
   205|`maps serve install` writes:
   206|
   207|- `~/Library/LaunchAgents/io.nosleepcassette.mapsos.serve.plist`
   208|- `~/.mapsOS/serve/token`
   209|- `~/.mapsOS/serve/launchd.stdout.log`
   210|- `~/.mapsOS/serve/launchd.stderr.log`
   211|
   212|The install command will reuse `MAPS_SERVE_TOKEN` from your shell if present; otherwise it generates one and saves it to `~/.mapsOS/serve/token`.
   213|
   214|The HTTP server now includes a richer `GET /session-start` endpoint in addition to the existing `GET /check`. It composes the latest state, arcs, body/intention context, Cart P0/P1 tasks, recent session notes, Cart doctor state, and bridge health into one packet for remote clients.
   215|
   216|`session-start` is now role-aware:
   217|
   218|- `intake` is the default surface and prioritizes qualitative context
   219|- `librarian` prioritizes bridge/cart maintenance context
   220|
   221|The payload also degrades explicitly instead of failing silently. Both CLI and HTTP surfaces include:
   222|
   223|- `role`
   224|- `degraded`
   225|- `degradation_reasons`
   226|- `sources`
   227|- `role_context`
   228|
   229|---
   230|
   231|## atlas integration
   232|
   233|mapsOS is strongest when it is not the only thing running.
   234|
   235|With cartographer installed:
   236|
   237|- `maps export` writes structured session state for atlas ingest
   238|- quitting the mapsOS TUI auto-ingests the latest export
   239|- `C` inside mapsOS launches `cart tui`
   240|- `cart tui` can launch mapsOS back with `m`
   241|- cartographer daily briefs can be loaded into mapsOS at session start
   242|
   243|The point is not "two tools that happen to integrate."
   244|The point is one local-first system where qualitative state and durable memory are finally in the same loop.
   245|
   246|Repos:
   247|
   248|- mapsOS: <https://github.com/nosleepcassette/mapsOS>
   249|- cartographer: <https://github.com/nosleepcassette/cartographer>
   250|
   251|---
   252|
   253|## TUI
   254|
   255|```bash
   256|python3 bin/maps
   257|```
   258|
   259|Requires `rich`. No Textual dependency — raw termios + Rich.
   260|
   261|Warm amber palette. STATE-specific colors. Layout-based dashboard with live sparkline, body heat grid, arc panel, and atlas context strip. Animated splash on load.
   262|
   263|| Key        | Action                            |
   264||------------|-----------------------------------|
   265|| `v`        | vent                              |
   266|| `t`        | tulpa (multi-line stream capture) |
   267|| `f`        | flash                             |
   268|| `s`        | state                             |
   269|| `b`        | body                              |
   270|| `m`        | mind                              |
   271|| `S`        | spirit                            |
   272|| `i`        | intention                         |
   273|| `r`        | review                            |
   274|| `c`        | refresh / pattern check           |
   275|| `C`        | launch atlas (`cart tui`)         |
   276|| `y`        | sync local store                  |
   277|| `T`        | trend chart                       |
   278|| `V`        | viz dashboard                     |
   279|| `a`        | about                             |
   280|| `d`        | open docs in browser              |
   281|| `?` / `h`  | help + docs                       |
   282|| `q`        | quit                              |
   283|
   284|---
   285|
   286|## configuration
   287|
   288|The new config surface is one of the biggest changes in this release.
   289|
   290|You can now define:
   291|
   292|- your own STATE vocabulary
   293|- your own track categories
   294|- which states count as low-capacity / survival conditions
   295|- whether the UI says "survival mode" or "low capacity mode"
   296|- cartographer integration toggles and atlas root path
   297|
   298|See:
   299|
   300|- `~/.maps_os_config.yaml`
   301|- `environments/maps_os_config.example.yaml`
   302|
   303|This is the core ethos of the project in practice: built for one brain, configurable for yours.
   304|
   305|---
   306|
   307|## Pattern Weaving — 25 Arcs
   308|
   309|After every vent and at session start, the pattern weaver runs across recent entries and surfaces arcs. Each arc has a suppression cooldown — arcs don't repeat every session while conditions persist.
   310|
   311|The arc set goes well beyond what most tracking tools attempt. Where a standard system might flag "mood dip for 3 consecutive days," mapsOS detects things like `exec_dysfunction` (high resistance + stalled goal + dysregulated state), `resistance_pattern` (same friction source recurring over two weeks), `negative_interaction_pattern` (a specific person showing up negatively across a month), and `intrusive_loop` (the same topic appearing across multiple flash captures without resolution). These are patterns that show up in life but rarely in software.
   312|
   313|### Alert arcs (one at a time, highest priority)
   314|
   315|| Arc | Trigger | Cooldown |
   316||-----|---------|---------|
   317|| `manic_spike` | Manic/depleted + no sleep + high flow | 1 day |
   318|| `body_neglect` | High flow + hunger ignored or no movement | 1 day |
   319|| `isolation_creep` | 3+ isolation logs or 5+ days no connection | 2 days |
   320|| `state_dip_holding` | 2+ low states in last 3 — triggers survival mode | never suppressed |
   321|| `cycle_meta` | 3+ manic/depleted alternations in 60 days — structural cycle, not random variation | 7 days |
   322|
   323|### Insight arcs (all that apply)
   324|
   325|| Arc                          | Trigger                                                   | Cooldown |
   326||------------------------------|-----------------------------------------------------------|----------|
   327|| `spirit_rising`              | Connection rising while state is low                      | 3 days   |
   328|| `post_manic_drop`            | Was manic, now depleted/stable                            | 2 days   |
   329|| `thriving_streak`            | 3 consecutive thriving                                    | 3 days   |
   330|| `productivity_spiral`        | Manic/depleted + work language + no spirit tracked        | 2 days   |
   331|| `catastrophizing_spike`      | Catastrophizing phrases in vent notes                     | 1 day    |
   332|| `planning_hyperfocus`        | Planning language + high mind + no intentions today       | 1 day    |
   333|| `substance_coping`           | Substances logged during heavy state                      | 3 days   |
   334|| `avoidance_language`         | 2+ avoidance phrases in recent vents                      | 2 days   |
   335|| `habit_candidate`            | Intention logged 5+ times at ≥60% met rate                | —        |
   336|| `decision_pile`              | 3+ unresolved DECISION entries in 7 days                  | 3 days   |
   337|| `trigger_pattern`            | 3+ TRIGGER entries from same source in 30 days            | 7 days   |
   338|| `goal_stall`                 | GOAL open >14 days                                        | 7 days   |
   339|| `resistance_pattern`         | 3+ RESISTANCE entries, same source, 14 days               | 5 days   |
   340|| `negative_interaction_pattern` | 3+ negative PERSON entries, same person, 30 days        | 7 days   |
   341|| `exec_dysfunction`           | High resistance + stalled goal + dysregulated STATE       | —        |
   342|| `intrusive_loop`             | Same topic in 3+ flash entries                            | —        |
   343|
   344|### Behavioral arcs (response calibration, not code)
   345|
   346|- `avoidance_loop` — same task mentioned 3+ times without resolution
   347|- `trust_rupture` — lied/betrayed in vent → suppress everything, just witness
   348|- `context_inheritance` — session start state comparison
   349|- `state_memory_loss` — nudge 48+ hours after logged state with no follow-up
   350|
   351|---
   352|
   353|## Survival Mode
   354|
   355|Triggers when STATE has been `depleted` or `grieving` for 2+ of the last 3 entries.
   356|
   357|In survival mode:
   358|- Logging collapses to STATE + BODY only
   359|- All arcs suppressed except body neglect
   360|- Briefing is exactly three items: eat, sleep, water
   361|- No productivity language anywhere
   362|
   363|Exits when a non-low state is logged.
   364|
   365|This is one of the more meaningful design decisions in the system. When you're struggling, the last thing you need is more features. The system gets out of the way.
   366|
   367|---
   368|
   369|## Arc Cooldown
   370|
   371|Arcs are suppressed after firing to prevent alert fatigue. A `manic_spike` that lasts three days won't fire three sessions in a row. Cooldowns persist to `~/.maps_os_cooldown.json`.
   372|
   373|Survival-severity arcs (`state_dip_holding`) are never suppressed.
   374|
   375|### Frequency threshold
   376|
   377|Arc fire history is tracked separately in `~/.maps_os_arc_history.json`. Any insight-severity arc that fires 3 or more times within 14 days is automatically upgraded to alert severity and labeled `[recurring × N in 14 days]`. This distinguishes a one-off pattern detection from something that's genuinely persistent and needs direct attention.
   378|
   379|---
   380|
   381|## Local Storage
   382|
   383|All entries write to `~/.maps_os_local.db` by default. If you have a remote backend configured, `maps sync` flushes the queue. The system never loses data whether or not a backend is available.
   384|
   385|## Cartographer Integration
   386|
   387|mapsOS pairs with cartographer to form a complete qualitative life + agent memory system:
   388|
   389|- **mapsOS** = how you're actually doing (state tracking, pattern detection)
   390|- **cartographer** = what happened, what matters, what agents learned
   391|- **atlas** = shared substrate underneath both
   392|
   393|---
   394|
   395|## Agent Skills
   396|
   397|For AI agents working with mapsOS, we publish skill definitions that can be imported into agent systems:
   398|
   399|| Skill | Description | Gist |
   400||-------|-------------|------|
   401|| **mapsOS Agent Skill** | Complete skill for qualitative life tracking — vent parsing, pattern weaving, survival mode, 26 arcs | [View Gist](https://gist.github.com/nosleepcassette/76a629d9f0e101e037b2ecf5e384cea9) |
   402|
   403|These skills encode:
   404|- CLI usage and fallback patterns
   405|- STATE/BODY/MIND/SPIRIT schema with tag guides
   406|- Vent parsing logic with keyword mapping
   407|- Pattern detection rules (26 arcs)
   408|- Survival mode triggers and behavior
   409|- Response tone calibration
   410|- Tulpa capture protocol
   411|
   412|To use in Hermes Agent: place in `~/.hermes/skills/mapsOS/SKILL.md`
   413|
   414|To use in Claude Code: add to CLAUDE.md or import via MCP.
   415|
   416|---
   417|
   418|## Community Skills & Plugins
   419|
   420|**TODO:** Community repository for sharing mapsOS configurations, custom tracks, pattern definitions, and agent integrations.
   421|
   422|If you've built something with mapsOS — a custom schema, a new arc pattern, an agent integration — we want to surface it.
   423|
   424|mapsOS is the qualitative layer. [cartographer](https://github.com/nosleepcassette/cartographer) is the memory layer. Together they form a closed loop:
   425|
   426|```
   427|session → maps export → cart ingest → atlas → daily brief → next session start
   428|```
   429|
   430|**From mapsOS:**
   431|- `maps export` writes structured session data to `~/.mapsOS/exports/`
   432|- Includes STATE, BODY/MIND/SPIRIT, active arcs, intentions, events, people
   433|
   434|**Into cartographer:**
   435|- `cart mapsos ingest-exports --latest` pulls the latest export
   436|- `cart mapsos patterns --field state` shows state trend synthesis
   437|- `cart daily-brief` includes mapsOS-derived context
   438|
   439|**Back to agents:**
   440|- `cart daily-brief` output is loaded at Hermes session start
   441|- Agents see qualitative state alongside project context
   442|- Survival mode context is surfaced automatically
   443|
   444|This is the loop: your agents start every session knowing what you forgot, informed by both your projects and your actual state.
   445|
   446|---
   447|
   448|## Person Context
   449|
   450|`~/.maps_os_config.yaml` maintains a `known_people` list for name extraction from vent text, plus a `people:` section with role/notes for each person.
   451|
   452|```bash
   453|maps person --list       # everyone + last contact
   454|maps person alex         # recent interactions + notes
   455|```
   456|
   457|---
   458|
   459|## Docs
   460|
   461|- [Setup Guide](docs/SETUP.md)
   462|- [Walkthrough](docs/WALKTHROUGH.md)
   463|- [RL Design Spec](docs/RL_SPEC.md)
   464|- [Agent Skill](https://gist.github.com/nosleepcassette/6644b13147a064c234a20b2642a4809e)
   465|
   466|---
   467|
   468|## Installation
   469|
   470|```bash
   471|git clone https://github.com/nosleepcassette/mapsOS
   472|cd mapsOS
   473|pip install -r requirements.txt
   474|chmod +x bin/maps
   475|export PATH="$PATH:$(pwd)/bin"
   476|```
   477|
   478|Add that `export` line to your `~/.zshrc` or `~/.bashrc` to make it permanent.
   479|
   480|**Dependencies:**
   481|- Python 3.10+
   482|- `rich` (TUI only — CLI works without it)
   483|- `pyyaml` (config loading)
   484|- [`nota`](https://github.com/nosleepcassette/nota) (task routing — optional, detected automatically)
   485|- `eidetic` (verbatim logging — optional, detected automatically)
   486|
   487|**Agent integration:** [`SKILL.md`](https://gist.github.com/nosleepcassette/6644b13147a064c234a20b2642a4809e) — Hermes operator guide covering session protocol, vent parsing, arc response calibration, and tulpa capture mode.
   488|
   489|`maps check --role` outputs agent mode guidance at session start: current STATE, suggested interaction mode, energy tier, arcs active and their role implications, and reference files to load. The role mapping table in `bin/maps` is designed to be adapted to any agent that has a mode or persona system.
   490|
   491|---
   492|
   493|## RL Training
   494|
   495|Two Atropos-compatible RL training environments are included.
   496|
   497|**`maps_os_env.py`** — data fidelity training. 13 scenarios across vent, session start, survival, cycle review, and intention log modes. Trains the agent to log correct entries, use correct STATE tags, avoid shame language, and handle survival mode.
   498|
   499|| Component | Weight | What it measures |
   500||-----------|--------|-----------------|
   501|

---

## Support

If you'd like to support the developer, [help keep a disabled trans woman housed in San Francisco](https://gofund.me/454b1cd9e). Every dollar goes to rent.

