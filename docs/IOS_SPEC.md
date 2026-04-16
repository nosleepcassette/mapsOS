# mapsOS iOS Integration Spec
# maps · cassette.help · MIT
# Status: SPEC ONLY — not yet built

---

## What This Is

A native SwiftUI app that gives mapsOS a mobile face: log STATE, BODY, MIND, SPIRIT, and flash on the go. View the sparkline dashboard. Get arc alerts as iOS notifications. All data goes into the same SQLite store the CLI uses.

This is not a reimplementation — the Python stack stays authoritative. The iOS app is a thin client talking to a local HTTP server running on the same machine via Tailscale.

Pattern: identical to hermetica-beta. You've built this before.

---

## Architecture

```
iPhone (SwiftUI app)
    │
    │  HTTPS via Tailscale Serve
    ▼
Mac running `maps serve` (FastAPI, localhost:7432)
    │
    ├── local_store.py (SQLite read/write)
    ├── vent_parser.py (full parse pipeline)
    ├── pattern_weaver.py (arc detection)
    └── ~/.maps_os_local.db
```

No new infrastructure. Tailscale Serve wraps the local server in HTTPS. App hits the same endpoint as hermetica — just different routes.

---

## Phase 1 — Server (`maps serve`)

A new subcommand in `bin/maps`. Adds FastAPI as an optional dependency (like rich — detected, not required for CLI).

### Endpoints

```
POST   /vent              body: {"text": "...", "date": "2026-04-14"}
                          → runs full vent_parser pipeline, writes to local_store
                          → returns: {"entries": [...parsed...], "arcs": [...active...]}

POST   /log               body: {"content": "STATE: 2026-04-14 | thriving | note"}
                          → direct write to local_store
                          → returns: {"id": 42, "dest": "local"}

GET    /check             → runs cmd_check logic
                          → returns: {"state": {...}, "arcs": [...], "survival": bool}

GET    /trend?days=30     → returns state entries for sparkline rendering
                          → returns: {"entries": [...], "days": 30}

GET    /body?days=7       → returns body entries
GET    /intentions?days=7 → returns intention entries
GET    /flash             → recent flash entries

POST   /flash             body: {"text": "laundry"}
                          → writes FLASH entry
```

### Response format

All entries returned as:
```json
{
  "content": "STATE: 2026-04-14 | thriving | things clicking",
  "ts": "2026-04-14T18:32:00Z",
  "id": 42
}
```

Arcs returned as:
```json
{
  "name": "thriving_streak",
  "severity": "insight",
  "message": "Three days of thriving. What's different?"
}
```

### Implementation (~80 lines)

```python
# In bin/maps, new subcommand:
def cmd_serve(args):
    try:
        from fastapi import FastAPI
        import uvicorn
    except ImportError:
        print("maps serve requires fastapi + uvicorn: pip install fastapi uvicorn")
        sys.exit(1)

    from environments.local_store import write, recall_resilient
    from environments.vent_parser import parse_vent
    from environments.pattern_weaver import weave
    from environments.survival_mode import evaluate as eval_survival

    app = FastAPI()
    PORT = getattr(args, "port", 7432)

    @app.post("/vent")
    def route_vent(body: dict):
        entries = parse_vent(body["text"], log_date=body.get("date"))
        logged = []
        for e in entries:
            content = e.to_garden()
            write(content)
            logged.append({"content": content, "track": e.track})
        # Quick arc check
        states = [e for e in logged if e["track"] == "STATE"]
        return {"entries": logged, "count": len(logged)}

    @app.post("/log")
    def route_log(body: dict):
        row_id = write(body["content"])
        return {"id": row_id, "dest": "local"}

    @app.get("/check")
    def route_check():
        from environments.local_store import recall_resilient
        states, _ = recall_resilient("STATE:", limit=7)
        body, _ = recall_resilient("BODY:", limit=14)
        mind, _ = recall_resilient("MIND:", limit=5)
        spirit, _ = recall_resilient("SPIRIT:", limit=5)
        intentions, _ = recall_resilient("INTENTION:", limit=7)
        flash, _ = recall_resilient("FLASH:", limit=10)
        arcs = weave(states, body, mind, spirit, intentions, flash)
        survival = eval_survival(states)
        return {
            "state": states[-1] if states else None,
            "arcs": [{"name": a.name, "severity": a.severity, "message": a.message} for a in arcs],
            "survival": survival.active,
        }

    @app.get("/trend")
    def route_trend(days: int = 30):
        entries, _ = recall_resilient("STATE:", limit=days * 2)
        return {"entries": [e for e in entries], "days": days}

    @app.get("/body")
    def route_body(days: int = 7):
        entries, _ = recall_resilient("BODY:", limit=days * 5)
        return {"entries": entries, "days": days}

    @app.get("/intentions")
    def route_intentions(days: int = 7):
        entries, _ = recall_resilient("INTENTION:", limit=days * 5)
        return {"entries": entries}

    @app.post("/flash")
    def route_flash(body: dict):
        from datetime import date
        content = f"FLASH: {date.today().isoformat()} | {body['text']}"
        row_id = write(content)
        return {"id": row_id}

    print(f"maps serve  →  http://localhost:{PORT}")
    print("wrap with Tailscale Serve for HTTPS on iPhone")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
```

Optional deps: `fastapi`, `uvicorn`. Neither is in requirements.txt. Add to requirements-optional.txt or document separately.

---

## Phase 2 — iOS App (SwiftUI)

Stack: SwiftUI + async/await. No Combine boilerplate. Identical pattern to hermetica-beta.

### Screens

**Dashboard** (home tab)
- STATE sparkline (last 30 days) — rendered natively in SwiftUI with Canvas
- Active arcs list — severity badge (● ◆ ▲) + message
- Today's body signals as compact row
- Pending sync count if > 0

**Log** (compose tab)
- `[v] vent` — multiline text field, sends to `/vent`, shows parsed results
- `[f] flash` — single line, sends to `/flash`
- `[s] state` — picker (10 tags with glyphs + colors), sends to `/log`
- `[b/m/S]` — category pickers for body/mind/spirit

**Trend** (chart tab)
- Full sparkline (Canvas, 90 days)
- Distribution bars (SwiftUI progress view, state color)

**Intentions** (tab 4 or embedded in dashboard)
- Today's intentions with met/missed/partial status

### SwiftUI sparkline (Canvas approach)

```swift
struct StateSparkline: View {
    let entries: [StateEntry]  // (date, tag, energyLevel, color)
    let days: Int = 30

    var body: some View {
        Canvas { ctx, size in
            let barW = size.width / CGFloat(days)
            for (i, entry) in entries.enumerated() {
                let barH = (CGFloat(entry.energyLevel) / 7.0) * size.height
                let x = CGFloat(i) * barW
                let rect = CGRect(
                    x: x, y: size.height - barH,
                    width: barW - 1, height: barH
                )
                ctx.fill(Path(rect), with: .color(entry.color))
            }
        }
        .frame(height: 60)
    }
}
```

This gives a smooth, native sparkline with exact state colors — better than terminal block chars.

### State colors in Swift

```swift
extension Color {
    static let stateColors: [String: Color] = [
        "depleted":  Color(hex: "#7a7a7a"),
        "grieving":  Color(hex: "#7b9eb5"),
        "surviving": Color(hex: "#c47c7c"),
        "flooded":   Color(hex: "#d4893a"),
        "manic":     Color(hex: "#b07fd4"),
        "stable":    Color(hex: "#c0bdb4"),
        "grounded":  Color(hex: "#5fa89b"),
        "tender":    Color(hex: "#c97a95"),
        "thriving":  Color(hex: "#7ab87e"),
        "clear":     Color(hex: "#6abdd4"),
    ]
}
```

Same palette as the TUI. Visual consistency across Mac terminal + iPhone.

### Network layer

```swift
class MapsClient: ObservableObject {
    let baseURL: URL  // Tailscale Serve URL, e.g. https://maps-mini.tail12345.ts.net

    func check() async throws -> CheckResponse { ... }
    func vent(_ text: String) async throws -> VentResponse { ... }
    func flash(_ text: String) async throws -> Void { ... }
    func logEntry(_ content: String) async throws -> Void { ... }
    func trend(days: Int = 30) async throws -> [StateEntry] { ... }
    func bodyData(days: Int = 7) async throws -> [BodyEntry] { ... }
}
```

All calls use `async/await` + `URLSession`. No third-party networking.

### iOS notifications for arc alerts

On each `/check` response, compare returned arcs against last-known arc list stored in UserDefaults. If new alert-severity arc appears: fire local notification.

```swift
func checkAndNotify() async {
    let response = try await client.check()
    let newAlerts = response.arcs.filter { $0.severity == "alert" && !knownAlerts.contains($0.name) }
    for arc in newAlerts {
        let content = UNMutableNotificationContent()
        content.title = "mapsOS"
        content.body = arc.message
        content.sound = .default
        let req = UNNotificationRequest(identifier: arc.name, content: content, trigger: nil)
        UNUserNotificationCenter.current().add(req)
    }
    knownAlerts = Set(response.arcs.map { $0.name })
}
```

Background fetch or push (via APNs if server is remote) — start with manual refresh button, add background fetch later.

### Connection setup

Identical to hermetica-beta:
1. `maps serve` starts on Mac (can be a Login Item or launchd plist)
2. `tailscale serve 7432` wraps it in HTTPS
3. App settings screen: enter Tailscale URL once
4. Done

---

## Build Order

| Step | Effort | What you get |
|------|--------|-------------|
| 1. `maps serve` subcommand | ~2hr | REST API, testable with curl |
| 2. SwiftUI scaffold + network layer | ~1hr | Xcode project, MapsClient |
| 3. Dashboard screen (check + arc list) | ~2hr | Core loop working |
| 4. Log screen (vent + flash + state) | ~2hr | Full logging from phone |
| 5. Sparkline + trend screen | ~2hr | Native Canvas chart |
| 6. Notifications | ~1hr | Arc alerts on phone |
| 7. Tailscale Serve integration | ~30min | HTTPS, sideloadable |

Total: ~10-12 hours of build time (with AI assist). Sideloadable on your own device via Xcode free account.

---

## What This Is NOT

- Not a standalone app (Python server must be running)
- Not a cloud sync solution (Tailscale = same as being on your local network)
- Not a replacement for the TUI (different contexts: desk vs. pocket)
- Not App Store-ready without a paid Apple Developer account ($99/yr)

---

## Files to Create

```
ios/
├── mapsOS.xcodeproj
├── mapsOS/
│   ├── App.swift
│   ├── MapsClient.swift          — network layer
│   ├── Models.swift              — StateEntry, Arc, BodyEntry, etc.
│   ├── Views/
│   │   ├── DashboardView.swift
│   │   ├── LogView.swift
│   │   ├── TrendView.swift
│   │   └── SettingsView.swift
│   └── Components/
│       ├── StateSparkline.swift  — Canvas sparkline
│       ├── ArcBadge.swift        — severity badge
│       └── BodyHeatGrid.swift    — grid view
└── bin/maps                      — add cmd_serve()
```

---

## Prerequisite Changes to mapsOS

1. **`maps serve` subcommand** — as above
2. **`--json` flag on key commands** (optional but useful for debugging):
   ```bash
   maps check --json     # machine-readable arc output
   maps trend --json     # raw entry list
   ```
3. **CORS headers on the server** — required for any web-based client (not iOS, but good practice):
   ```python
   from fastapi.middleware.cors import CORSMiddleware
   app.add_middleware(CORSMiddleware, allow_origins=["*"])
   ```

---

*maps · cassette.help · MIT*
