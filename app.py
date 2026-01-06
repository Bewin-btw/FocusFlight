from fastapi import FastAPI, Body
from fastapi.responses import HTMLResponse, JSONResponse
import sqlite3
from datetime import datetime, timezone, date

APP_TITLE = "FocusFlight"

DB_PATH = "focusflight.db"

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = connect()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        planned_minutes INTEGER NOT NULL,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        actual_seconds INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS distractions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        noted_at TEXT NOT NULL,
        note TEXT,
        FOREIGN KEY(session_id) REFERENCES sessions(id)
    )
    """)

    con.commit()
    con.close()

app = FastAPI(title=APP_TITLE)

INDEX_HTML = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{APP_TITLE}</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      margin: 24px;
      max-width: 980px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}
    @media (max-width: 820px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
    .card {{
      border: 1px solid #ddd;
      border-radius: 14px;
      padding: 16px;
    }}
    .row {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
    }}
    input, button, textarea {{
      font: inherit;
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid #ccc;
    }}
    textarea {{ width: 100%; min-height: 70px; }}
    button {{
      cursor: pointer;
      border: 1px solid #333;
      background: #111;
      color: #fff;
    }}
    button.secondary {{
      background: #fff;
      color: #111;
      border: 1px solid #111;
    }}
    button.danger {{
      background: #b00020;
      border-color: #7a0016;
    }}
    .muted {{ color: #666; font-size: 14px; }}
    .big {{ font-size: 22px; font-weight: 700; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
    .bar {{
      height: 14px;
      border-radius: 999px;
      background: #eee;
      overflow: hidden;
    }}
    .bar > div {{
      height: 100%;
      width: 0%;
      background: #111;
      transition: width 250ms linear;
    }}
    .sky {{
      position: relative;
      height: 160px;
      border-radius: 14px;
      border: 1px solid #ddd;
      overflow: hidden;
      background: linear-gradient(#eaf3ff, #ffffff);
    }}
    .plane {{
      position: absolute;
      left: 12px;
      top: 70px;
      font-size: 26px;
      transition: left 250ms linear, top 250ms linear;
      user-select: none;
    }}
    .turbulence {{
      position: absolute;
      right: 12px;
      top: 12px;
      font-size: 12px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid #ddd;
      background: rgba(255,255,255,0.8);
    }}
    .log {{
      max-height: 240px;
      overflow: auto;
      border: 1px solid #eee;
      border-radius: 12px;
      padding: 10px;
    }}
    .log-item {{
      padding: 8px 0;
      border-bottom: 1px dashed #eee;
    }}
    .log-item:last-child {{ border-bottom: none; }}
  </style>
</head>
<body>
  <h1>{APP_TITLE}</h1>
  <p class="muted">
    A flight metaphor for focus: takeoff, cruise, landing.
    Distractions add turbulence and drop altitude. Sessions are saved locally (SQLite).
  </p>

  <div class="grid">
    <div class="card">
      <div class="big">Flight Controls</div>
      <div class="row" style="margin-top: 12px;">
        <input id="subject" placeholder="Subject (e.g., Algorithms)" style="flex: 1; min-width: 220px;" />
        <input id="minutes" type="number" min="5" max="180" value="50" style="width: 120px;" />
      </div>
      <div class="row" style="margin-top: 12px;">
        <button id="startBtn" onclick="startFlight()">Start flight</button>
        <button class="secondary" id="pauseBtn" onclick="togglePause()" disabled>Pause</button>
        <button class="danger" id="endBtn" onclick="endFlight()" disabled>End flight</button>
      </div>

      <div style="margin-top: 14px;">
        <div class="row" style="justify-content: space-between;">
          <div class="muted">Progress</div>
          <div id="timeLeft" class="mono muted">00:00</div>
        </div>
        <div class="bar" style="margin-top: 6px;">
          <div id="barFill"></div>
        </div>
      </div>

      <div style="margin-top: 14px;">
        <div class="sky" id="sky">
          <div class="turbulence">
            Altitude: <span id="altitude">100</span> |
            Turbulence: <span id="turb">0</span>
          </div>
          <div class="plane" id="plane">✈️</div>
        </div>
        <div class="muted" style="margin-top: 8px;">
          Tip: Keep turbulence low. One distraction costs altitude. Finish at least 80 altitude for a “smooth landing”.
        </div>
      </div>
    </div>

    <div class="card">
      <div class="big">Distractions</div>
      <p class="muted">Log any interruption. Be honest. The goal is awareness, not perfection.</p>
      <textarea id="note" placeholder="What distracted you? (optional)"></textarea>
      <div class="row" style="margin-top: 10px;">
        <button class="secondary" id="distBtn" onclick="logDistraction()" disabled>Log distraction</button>
        <div class="muted">Count: <span id="distCount">0</span></div>
      </div>

      <div style="margin-top: 14px;">
        <div class="big" style="font-size: 18px;">Today</div>
        <div class="row" style="margin-top: 8px; gap: 18px;">
          <div>Focus: <span class="mono" id="todayFocus">0</span> min</div>
          <div>Sessions: <span class="mono" id="todaySessions">0</span></div>
          <div>Distractions: <span class="mono" id="todayDistractions">0</span></div>
        </div>
      </div>

      <div style="margin-top: 14px;">
        <div class="big" style="font-size: 18px;">Flight log</div>
        <div class="log" id="log"></div>
      </div>
    </div>
  </div>

<script>
  let sessionId = null;
  let plannedSeconds = 0;
  let startMs = 0;
  let elapsedBeforePause = 0;
  let timer = null;
  let paused = false;

  let altitude = 100;
  let turbulence = 0;
  let distCount = 0;

  function fmtTime(totalSeconds) {{
    totalSeconds = Math.max(0, Math.floor(totalSeconds));
    const m = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
    const s = String(totalSeconds % 60).padStart(2, "0");
    return `${{m}}:${{s}}`;
  }}

  function addLog(text) {{
    const log = document.getElementById("log");
    const item = document.createElement("div");
    item.className = "log-item";
    const ts = new Date().toLocaleTimeString([], {{hour: "2-digit", minute: "2-digit", second: "2-digit"}});
    item.innerHTML = `<span class="mono">${{ts}}</span> - ${{text}}`;
    log.prepend(item);
  }}

  function setControls(running) {{
    document.getElementById("startBtn").disabled = running;
    document.getElementById("pauseBtn").disabled = !running;
    document.getElementById("endBtn").disabled = !running;
    document.getElementById("distBtn").disabled = !running;
    document.getElementById("subject").disabled = running;
    document.getElementById("minutes").disabled = running;
  }}

  function updateUI(progress) {{
    const bar = document.getElementById("barFill");
    bar.style.width = `${{Math.min(100, Math.max(0, progress * 100))}}%`;

    document.getElementById("altitude").textContent = altitude;
    document.getElementById("turb").textContent = turbulence;
    document.getElementById("distCount").textContent = distCount;

    const sky = document.getElementById("sky");
    const plane = document.getElementById("plane");

    const w = sky.clientWidth;
    const left = 12 + (w - 48) * progress;

    const topBase = 90;
    const top = topBase - (altitude - 50) * 0.6 + (turbulence % 5) * 2;

    plane.style.left = `${{left}}px`;
    plane.style.top = `${{Math.max(14, Math.min(120, top))}}px`;
  }}

  function tick() {{
    if (!sessionId || paused) return;

    const now = Date.now();
    const elapsed = elapsedBeforePause + Math.floor((now - startMs) / 1000);
    const left = plannedSeconds - elapsed;

    document.getElementById("timeLeft").textContent = fmtTime(left);

    const progress = Math.min(1, elapsed / plannedSeconds);
    updateUI(progress);

    if (left <= 0) {{
      addLog("Landing complete. Ending flight.");
      endFlight();
    }}
  }}

  async function refreshStats() {{
    const res = await fetch("/api/stats/today");
    const data = await res.json();
    document.getElementById("todayFocus").textContent = data.focus_minutes;
    document.getElementById("todaySessions").textContent = data.sessions;
    document.getElementById("todayDistractions").textContent = data.distractions;
  }}

  async function startFlight() {{
    const subject = document.getElementById("subject").value.trim() || "Study";
    const minutes = parseInt(document.getElementById("minutes").value || "50", 10);

    const res = await fetch("/api/session/start", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ subject, planned_minutes: minutes }})
    }});

    const data = await res.json();
    sessionId = data.session_id;

    plannedSeconds = minutes * 60;
    startMs = Date.now();
    elapsedBeforePause = 0;
    paused = false;

    altitude = 100;
    turbulence = 0;
    distCount = 0;

    setControls(true);
    document.getElementById("pauseBtn").textContent = "Pause";
    addLog(`Takeoff: ${{subject}}, plan ${{minutes}} min, session #${{sessionId}}`);

    if (timer) clearInterval(timer);
    timer = setInterval(tick, 250);

    tick();
    await refreshStats();
  }}

  function togglePause() {{
    if (!sessionId) return;

    if (!paused) {{
      paused = true;
      const now = Date.now();
      elapsedBeforePause += Math.floor((now - startMs) / 1000);
      document.getElementById("pauseBtn").textContent = "Resume";
      addLog("Paused.");
    }} else {{
      paused = false;
      startMs = Date.now();
      document.getElementById("pauseBtn").textContent = "Pause";
      addLog("Resumed.");
    }}
  }}

  async function logDistraction() {{
    if (!sessionId) return;

    const noteEl = document.getElementById("note");
    const note = noteEl.value.trim();
    noteEl.value = "";

    const res = await fetch("/api/distraction", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ session_id: sessionId, note }})
    }});

    if (!res.ok) {{
      addLog("Failed to log distraction.");
      return;
    }}

    distCount += 1;
    turbulence += 7;
    altitude = Math.max(40, altitude - 6);

    addLog(note ? `Turbulence: ${{note}}` : "Turbulence: distraction logged");
    await refreshStats();
  }}

  async function endFlight() {{
    if (!sessionId) return;

    // compute elapsed
    let elapsed = elapsedBeforePause;
    if (!paused) {{
      elapsed += Math.floor((Date.now() - startMs) / 1000);
    }}
    elapsed = Math.max(0, Math.min(plannedSeconds, elapsed));

    const smooth = altitude >= 80 ? "Smooth landing" : (altitude >= 60 ? "Bumpy landing" : "Rough landing");
    addLog(`${{smooth}}. Altitude ${{altitude}}, distractions ${{distCount}}`);

    const res = await fetch("/api/session/end", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ session_id: sessionId, actual_seconds: elapsed }})
    }});

    if (!res.ok) {{
      addLog("Failed to end session on server (still ended locally).");
    }}

    sessionId = null;
    paused = false;

    setControls(false);
    document.getElementById("timeLeft").textContent = "00:00";
    updateUI(0);

    if (timer) clearInterval(timer);
    timer = null;

    await refreshStats();
  }}

  refreshStats();
</script>
</body>
</html>
"""

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(INDEX_HTML)

@app.post("/api/session/start")
def session_start(payload: dict = Body(...)):
    subject = (payload.get("subject") or "Study").strip()
    planned_minutes = int(payload.get("planned_minutes") or 50)

    if planned_minutes < 5:
        planned_minutes = 5
    if planned_minutes > 240:
        planned_minutes = 240

    con = connect()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO sessions(subject, planned_minutes, started_at) VALUES(?,?,?)",
        (subject, planned_minutes, utc_now_iso())
    )
    session_id = cur.lastrowid
    con.commit()
    con.close()

    return {"session_id": session_id}

@app.post("/api/distraction")
def distraction(payload: dict = Body(...)):
    session_id = int(payload.get("session_id"))
    note = (payload.get("note") or "").strip()

    con = connect()
    cur = con.cursor()

    # confirm session exists and not ended
    row = cur.execute("SELECT id, ended_at FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row or row["ended_at"] is not None:
        con.close()
        return JSONResponse({"error": "invalid session"}, status_code=400)

    cur.execute(
        "INSERT INTO distractions(session_id, noted_at, note) VALUES(?,?,?)",
        (session_id, utc_now_iso(), note if note else None)
    )
    con.commit()
    con.close()

    return {"ok": True}

@app.post("/api/session/end")
def session_end(payload: dict = Body(...)):
    session_id = int(payload.get("session_id"))
    actual_seconds = int(payload.get("actual_seconds") or 0)
    actual_seconds = max(0, actual_seconds)

    con = connect()
    cur = con.cursor()

    row = cur.execute("SELECT id, ended_at FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        con.close()
        return JSONResponse({"error": "not found"}, status_code=404)

    if row["ended_at"] is None:
        cur.execute(
            "UPDATE sessions SET ended_at = ?, actual_seconds = ? WHERE id = ?",
            (utc_now_iso(), actual_seconds, session_id)
        )
        con.commit()

    con.close()
    return {"ok": True}

@app.get("/api/stats/today")
def stats_today():
    today = date.today().isoformat()

    con = connect()
    cur = con.cursor()

    # SQLite ISO strings: started_at has timezone, we match by prefix yyyy-mm-dd
    sessions_row = cur.execute(
        "SELECT COUNT(*) AS c, COALESCE(SUM(actual_seconds), 0) AS s "
        "FROM sessions WHERE started_at LIKE ? AND ended_at IS NOT NULL",
        (today + "%",)
    ).fetchone()

    distractions_row = cur.execute(
        "SELECT COUNT(*) AS c "
        "FROM distractions WHERE noted_at LIKE ?",
        (today + "%",)
    ).fetchone()

    con.close()

    focus_minutes = int(round((sessions_row["s"] or 0) / 60))

    return {
        "date": today,
        "sessions": int(sessions_row["c"] or 0),
        "focus_minutes": focus_minutes,
        "distractions": int(distractions_row["c"] or 0),
    }
