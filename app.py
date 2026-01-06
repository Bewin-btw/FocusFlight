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
    :root {{
      --bg0: #0b1020;
      --bg1: #0f1b3a;
      --card: rgba(255,255,255,0.08);
      --card2: rgba(255,255,255,0.06);
      --stroke: rgba(255,255,255,0.14);
      --text: rgba(255,255,255,0.92);
      --muted: rgba(255,255,255,0.68);
      --good: #5ef0a8;
      --warn: #ffd36b;
      --bad: #ff6b8b;
      --accent: #9ad1ff;
      --accent2: #c7a7ff;
      --shadow: 0 14px 40px rgba(0,0,0,0.35);
      --radius: 18px;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      color: var(--text);
      background: radial-gradient(1200px 700px at 20% 10%, rgba(154,209,255,0.18), transparent 60%),
                  radial-gradient(900px 650px at 80% 15%, rgba(199,167,255,0.16), transparent 60%),
                  linear-gradient(160deg, var(--bg0), var(--bg1));
      min-height: 100vh;
    }}

    .wrap {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 22px 18px 40px;
    }}

    .top {{
      display: flex;
      gap: 14px;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}

    .brand {{
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}

    h1 {{
      margin: 0;
      font-size: 28px;
      letter-spacing: 0.2px;
    }}

    .sub {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.35;
      max-width: 740px;
    }}

    .pillrow {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      justify-content: flex-end;
    }}

    .pill {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 8px 10px;
      border-radius: 999px;
      background: rgba(255,255,255,0.06);
      border: 1px solid var(--stroke);
      backdrop-filter: blur(10px);
      box-shadow: 0 10px 30px rgba(0,0,0,0.2);
      color: var(--muted);
      font-size: 13px;
    }}

    .dot {{
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: rgba(255,255,255,0.35);
    }}

    .grid {{
      display: grid;
      grid-template-columns: 1.2fr 1fr;
      gap: 14px;
      align-items: start;
    }}
    @media (max-width: 920px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}

    .card {{
      border-radius: var(--radius);
      background: linear-gradient(180deg, var(--card), var(--card2));
      border: 1px solid var(--stroke);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}

    .card .hd {{
      padding: 14px 16px 10px;
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid rgba(255,255,255,0.07);
    }}

    .title {{
      font-weight: 720;
      font-size: 16px;
      letter-spacing: 0.2px;
    }}

    .hint {{
      font-size: 13px;
      color: var(--muted);
    }}

    .bd {{
      padding: 14px 16px 16px;
    }}

    .row {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
    }}

    input, textarea {{
      font: inherit;
      color: var(--text);
      background: rgba(0,0,0,0.22);
      border: 1px solid rgba(255,255,255,0.14);
      border-radius: 12px;
      padding: 10px 12px;
      outline: none;
    }}
    input:focus, textarea:focus {{
      border-color: rgba(154,209,255,0.5);
      box-shadow: 0 0 0 3px rgba(154,209,255,0.12);
    }}

    textarea {{
      width: 100%;
      min-height: 74px;
      resize: vertical;
    }}

    button {{
      font: inherit;
      border: 1px solid rgba(255,255,255,0.22);
      border-radius: 12px;
      padding: 10px 12px;
      cursor: pointer;
      background: rgba(255,255,255,0.10);
      color: var(--text);
      transition: transform 120ms ease, background 120ms ease, border-color 120ms ease;
    }}
    button:hover {{
      transform: translateY(-1px);
      background: rgba(255,255,255,0.14);
      border-color: rgba(255,255,255,0.28);
    }}
    button:disabled {{
      opacity: 0.5;
      cursor: not-allowed;
      transform: none;
    }}

    .primary {{
      background: linear-gradient(135deg, rgba(154,209,255,0.22), rgba(199,167,255,0.16));
      border-color: rgba(154,209,255,0.34);
    }}
    .danger {{
      background: rgba(255,107,139,0.16);
      border-color: rgba(255,107,139,0.35);
    }}

    .mini {{
      font-size: 12px;
      color: var(--muted);
    }}

    .bar {{
      height: 14px;
      border-radius: 999px;
      background: rgba(255,255,255,0.10);
      border: 1px solid rgba(255,255,255,0.10);
      overflow: hidden;
    }}
    .bar > div {{
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, rgba(94,240,168,0.9), rgba(154,209,255,0.9));
      transition: width 200ms linear;
    }}

    /* Sky scene */
    .sky {{
      position: relative;
      height: 260px;
      border-radius: 16px;
      border: 1px solid rgba(255,255,255,0.14);
      background:
        radial-gradient(600px 220px at 20% 10%, rgba(154,209,255,0.22), transparent 60%),
        radial-gradient(520px 240px at 80% 30%, rgba(199,167,255,0.18), transparent 62%),
        linear-gradient(180deg, rgba(255,255,255,0.06), rgba(0,0,0,0.12));
      overflow: hidden;
      box-shadow: inset 0 -50px 70px rgba(0,0,0,0.18);
    }}

    .sun {{
      position: absolute;
      left: 22px;
      top: 20px;
      width: 70px;
      height: 70px;
      border-radius: 999px;
      background: radial-gradient(circle at 35% 35%, rgba(255,255,255,0.95), rgba(255,255,255,0.35));
      filter: blur(0.2px);
      box-shadow:
        0 0 40px rgba(154,209,255,0.35),
        0 0 70px rgba(199,167,255,0.22);
      opacity: 0.85;
    }}

    .cloud {{
      position: absolute;
      top: 30px;
      width: 120px;
      height: 42px;
      opacity: 0.75;
      filter: blur(0.1px);
      animation: drift 22s linear infinite;
    }}
    .cloud.c2 {{ top: 64px; width: 160px; opacity: 0.55; animation-duration: 28s; }}
    .cloud.c3 {{ top: 110px; width: 140px; opacity: 0.60; animation-duration: 25s; }}
    .cloud.c4 {{ top: 150px; width: 190px; opacity: 0.45; animation-duration: 32s; }}

    @keyframes drift {{
      0% {{ transform: translateX(-220px); }}
      100% {{ transform: translateX(1400px); }}
    }}

    .hud {{
      position: absolute;
      right: 12px;
      top: 12px;
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
      padding: 10px 10px;
      border-radius: 14px;
      background: rgba(0,0,0,0.22);
      border: 1px solid rgba(255,255,255,0.12);
      backdrop-filter: blur(10px);
    }}

    .hud .metric {{
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 120px;
    }}
    .hud .metric .k {{ font-size: 11px; color: var(--muted); }}
    .hud .metric .v {{ font-size: 14px; font-weight: 720; }}
    .hud .grade {{
      padding: 7px 10px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.14);
      font-size: 12px;
      color: var(--muted);
      min-width: 112px;
      text-align: center;
    }}

    .plane {{
      position: absolute;
      left: 16px;
      top: 130px;
      width: 62px;
      height: 62px;
      transform-origin: 50% 50%;
      transition: left 200ms linear, top 200ms linear, transform 200ms ease;
      user-select: none;
      pointer-events: none;
      filter: drop-shadow(0 10px 18px rgba(0,0,0,0.35));
    }}

    .trail {{
      position: absolute;
      left: 12px;
      top: 150px;
      height: 2px;
      width: 0px;
      background: linear-gradient(90deg, rgba(255,255,255,0.0), rgba(255,255,255,0.7), rgba(154,209,255,0.2));
      filter: blur(0.3px);
      opacity: 0.9;
      transition: width 200ms linear;
    }}

    .shake {{
      animation: shake 240ms ease-in-out 1;
    }}
    @keyframes shake {{
      0% {{ transform: translateX(0); }}
      30% {{ transform: translateX(-2px); }}
      60% {{ transform: translateX(2px); }}
      100% {{ transform: translateX(0); }}
    }}

    .panel {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 12px;
    }}
    @media (max-width: 520px) {{
      .panel {{ grid-template-columns: 1fr; }}
    }}

    .gauge {{
      border-radius: 16px;
      border: 1px solid rgba(255,255,255,0.10);
      background: rgba(0,0,0,0.18);
      padding: 12px;
      position: relative;
      overflow: hidden;
    }}

    .gauge .gtitle {{
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      gap: 10px;
    }}

    canvas {{
      width: 100%;
      height: 120px;
      display: block;
      border-radius: 12px;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.03);
    }}

    .log {{
      max-height: 260px;
      overflow: auto;
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 14px;
      padding: 10px 10px;
      background: rgba(0,0,0,0.12);
    }}
    .log-item {{
      padding: 8px 0;
      border-bottom: 1px dashed rgba(255,255,255,0.10);
      color: rgba(255,255,255,0.86);
      font-size: 13px;
    }}
    .log-item:last-child {{ border-bottom: none; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}

    .toast {{
      position: fixed;
      left: 50%;
      bottom: 18px;
      transform: translateX(-50%);
      padding: 10px 12px;
      border-radius: 999px;
      background: rgba(0,0,0,0.55);
      border: 1px solid rgba(255,255,255,0.14);
      color: rgba(255,255,255,0.9);
      backdrop-filter: blur(10px);
      box-shadow: 0 18px 40px rgba(0,0,0,0.35);
      opacity: 0;
      pointer-events: none;
      transition: opacity 140ms ease, transform 140ms ease;
      font-size: 13px;
    }}
    .toast.show {{
      opacity: 1;
      transform: translateX(-50%) translateY(-2px);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div class="brand">
        <h1>{APP_TITLE}</h1>
        <p class="sub">
          Flight metaphor for studying: takeoff, cruise, landing.
          Distractions add turbulence and reduce altitude.
          Sessions are saved locally in SQLite.
        </p>
      </div>

      <div class="pillrow">
        <div class="pill"><span class="dot" id="statusDot"></span><span id="statusText">Idle</span></div>
        <div class="pill">Today focus <span class="mono" id="todayFocus">0</span> min</div>
        <div class="pill">Sessions <span class="mono" id="todaySessions">0</span></div>
        <div class="pill">Distractions <span class="mono" id="todayDistractions">0</span></div>
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <div class="hd">
          <div class="title">Flight deck</div>
          <div class="hint">Keep altitude high, land smoothly</div>
        </div>
        <div class="bd">

          <div class="row">
            <input id="subject" placeholder="Subject (example: Algorithms)" style="flex: 1; min-width: 220px;" />
            <input id="minutes" type="number" min="5" max="180" value="50" style="width: 120px;" />
            <button class="primary" id="startBtn" onclick="startFlight()">Start</button>
            <button id="pauseBtn" onclick="togglePause()" disabled>Pause</button>
            <button class="danger" id="endBtn" onclick="endFlight()" disabled>End</button>
          </div>

          <div style="margin-top: 12px;">
            <div class="row" style="justify-content: space-between;">
              <div class="mini">Progress</div>
              <div class="mono mini" id="timeLeft">00:00</div>
            </div>
            <div class="bar" style="margin-top: 8px;">
              <div id="barFill"></div>
            </div>
          </div>

          <div style="margin-top: 14px;">
            <div class="sky" id="sky">
              <div class="sun"></div>

              <svg class="cloud c1" viewBox="0 0 200 80" style="left:-220px; animation-delay: 0s;">
                <path fill="rgba(255,255,255,0.75)" d="M62 60c-18 0-32-10-32-24s14-24 32-24c4 0 8 1 12 2C80 6 92 0 106 0c20 0 36 12 40 28 2-1 6-2 10-2 24 0 44 14 44 32S180 92 154 92H62z"/>
              </svg>
              <svg class="cloud c2" viewBox="0 0 200 80" style="left:-320px; animation-delay: 6s;">
                <path fill="rgba(255,255,255,0.70)" d="M58 62c-16 0-28-9-28-22S42 18 58 18c4 0 8 1 11 2C74 9 86 2 100 2c18 0 32 10 36 24 2-1 6-2 9-2 22 0 40 12 40 28S168 78 144 78H58z"/>
              </svg>
              <svg class="cloud c3" viewBox="0 0 200 80" style="left:-260px; animation-delay: 12s;">
                <path fill="rgba(255,255,255,0.72)" d="M60 58c-15 0-27-8-27-20s12-20 27-20c4 0 8 1 11 2C76 10 88 4 102 4c18 0 31 10 35 23 2-1 6-2 9-2 22 0 40 12 40 27S168 74 144 74H60z"/>
              </svg>
              <svg class="cloud c4" viewBox="0 0 200 80" style="left:-380px; animation-delay: 18s;">
                <path fill="rgba(255,255,255,0.66)" d="M58 60c-18 0-32-10-32-24s14-24 32-24c4 0 8 1 12 2C78 6 90 0 104 0c20 0 36 12 40 28 2-1 6-2 10-2 24 0 44 14 44 32S176 90 150 90H58z"/>
              </svg>

              <div class="trail" id="trail"></div>

              <svg class="plane" id="plane" viewBox="0 0 64 64" aria-hidden="true">
                <defs>
                  <linearGradient id="pg" x1="0" x2="1">
                    <stop offset="0" stop-color="rgba(255,255,255,0.92)"/>
                    <stop offset="1" stop-color="rgba(154,209,255,0.80)"/>
                  </linearGradient>
                </defs>
                <path fill="url(#pg)" d="M52 33l-16-5V9c0-2-1-4-3-4s-3 2-3 4v19l-16 5c-2 1-3 3-2 5s3 3 5 2l13-4v10l-5 4c-1 1-2 2-1 4 1 1 3 2 4 1l5-3 5 3c1 1 3 0 4-1 1-2 0-3-1-4l-5-4V36l13 4c2 1 4-1 5-2s0-4-2-5z"/>
                <circle cx="34" cy="18" r="2.2" fill="rgba(0,0,0,0.20)"/>
              </svg>

              <div class="hud">
                <div class="metric">
                  <div class="k">Altitude</div>
                  <div class="v"><span id="altitude">100</span></div>
                </div>
                <div class="metric">
                  <div class="k">Turbulence</div>
                  <div class="v"><span id="turb">0</span></div>
                </div>
                <div class="metric">
                  <div class="k">Distractions</div>
                  <div class="v"><span id="distCount">0</span></div>
                </div>
                <div class="grade" id="gradePill">Grade: -</div>
              </div>
            </div>

            <div class="panel">
              <div class="gauge">
                <div class="gtitle">
                  <span>Altitude over time</span>
                  <span class="mono" id="altLabel">ALT 100</span>
                </div>
                <canvas id="altChart" width="900" height="240"></canvas>
              </div>
              <div class="gauge">
                <div class="gtitle">
                  <span>Turbulence over time</span>
                  <span class="mono" id="turbLabel">TRB 0</span>
                </div>
                <canvas id="turbChart" width="900" height="240"></canvas>
              </div>
            </div>

          </div>

        </div>
      </div>

      <div class="card">
        <div class="hd">
          <div class="title">Distractions log</div>
          <div class="hint">Log it fast, then refocus</div>
        </div>
        <div class="bd">
          <textarea id="note" placeholder="What distracted you? (optional)"></textarea>

          <div class="row" style="margin-top: 10px;">
            <button id="distBtn" onclick="logDistraction()" disabled>Log distraction</button>
            <div class="mini">Tip: one distraction reduces altitude</div>
          </div>

          <div style="margin-top: 12px;">
            <div class="title" style="font-size: 14px;">Flight events</div>
            <div class="log" id="log" style="margin-top: 8px;"></div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="toast" id="toast"></div>

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

  const altSeries = [];
  const turbSeries = [];

  function toast(msg) {{
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 1200);
  }}

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

  function setStatus(running, pausing=false) {{
    const dot = document.getElementById("statusDot");
    const txt = document.getElementById("statusText");
    if (!running) {{
      dot.style.background = "rgba(255,255,255,0.35)";
      txt.textContent = "Idle";
      return;
    }}
    if (pausing) {{
      dot.style.background = "rgba(255,211,107,0.95)";
      txt.textContent = "Paused";
      return;
    }}
    dot.style.background = "rgba(94,240,168,0.95)";
    txt.textContent = "Flying";
  }}

  function setControls(running) {{
    document.getElementById("startBtn").disabled = running;
    document.getElementById("pauseBtn").disabled = !running;
    document.getElementById("endBtn").disabled = !running;
    document.getElementById("distBtn").disabled = !running;
    document.getElementById("subject").disabled = running;
    document.getElementById("minutes").disabled = running;
  }}

  function gradeFromAlt(alt) {{
    if (alt >= 90) return ["A", "rgba(94,240,168,0.18)", "rgba(94,240,168,0.45)"];
    if (alt >= 80) return ["B", "rgba(154,209,255,0.18)", "rgba(154,209,255,0.45)"];
    if (alt >= 65) return ["C", "rgba(255,211,107,0.18)", "rgba(255,211,107,0.45)"];
    return ["D", "rgba(255,107,139,0.18)", "rgba(255,107,139,0.45)"];
  }}

  function updateGrade() {{
    const pill = document.getElementById("gradePill");
    const [g, bg, br] = gradeFromAlt(altitude);
    pill.textContent = `Grade: ${{g}}`;
    pill.style.background = bg;
    pill.style.borderColor = br;
  }}

  function drawSeries(canvasId, series, labelId, scaleMax=110) {{
    const canvas = document.getElementById(canvasId);
    const ctx = canvas.getContext("2d");

    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // grid
    ctx.globalAlpha = 1;
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    for (let i = 1; i <= 4; i++) {{
      const y = (h * i) / 5;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }}

    if (series.length < 2) return;

    const pad = 14;
    const minV = 0;
    const maxV = scaleMax;

    function xAt(i) {{
      return pad + (w - pad * 2) * (i / (series.length - 1));
    }}
    function yAt(v) {{
      const t = (v - minV) / (maxV - minV);
      return (h - pad) - (h - pad * 2) * t;
    }}

    // line
    ctx.lineWidth = 3;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.strokeStyle = "rgba(154,209,255,0.9)";
    ctx.beginPath();
    ctx.moveTo(xAt(0), yAt(series[0]));
    for (let i = 1; i < series.length; i++) {{
      ctx.lineTo(xAt(i), yAt(series[i]));
    }}
    ctx.stroke();

    // fill
    ctx.globalAlpha = 0.22;
    ctx.fillStyle = "rgba(154,209,255,0.7)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(xAt(0), yAt(series[0]));
    for (let i = 1; i < series.length; i++) {{
      ctx.lineTo(xAt(i), yAt(series[i]));
    }}
    ctx.lineTo(xAt(series.length - 1), h - pad);
    ctx.lineTo(xAt(0), h - pad);
    ctx.closePath();
    ctx.fill();
    ctx.globalAlpha = 1;

    // last dot
    const last = series[series.length - 1];
    ctx.fillStyle = "rgba(255,255,255,0.9)";
    ctx.beginPath();
    ctx.arc(xAt(series.length - 1), yAt(last), 4.5, 0, Math.PI * 2);
    ctx.fill();

    document.getElementById(labelId).textContent = (canvasId === "altChart") ? `ALT ${{last}}` : `TRB ${{last}}`;
  }}

  function updateUI(progress) {{
    // progress bar
    const bar = document.getElementById("barFill");
    bar.style.width = `${{Math.min(100, Math.max(0, progress * 100))}}%`;

    // metrics
    document.getElementById("altitude").textContent = altitude;
    document.getElementById("turb").textContent = turbulence;
    document.getElementById("distCount").textContent = distCount;
    document.getElementById("altLabel").textContent = `ALT ${{altitude}}`;
    document.getElementById("turbLabel").textContent = `TRB ${{turbulence}}`;
    updateGrade();

    // plane position
    const sky = document.getElementById("sky");
    const plane = document.getElementById("plane");
    const trail = document.getElementById("trail");

    const w = sky.clientWidth;
    const left = 18 + (w - 90) * progress;

    // altitude to y (higher altitude means smaller top)
    const topMin = 52;
    const topMax = 190;
    const t = 1 - ((altitude - 40) / (100 - 40)); // altitude 100 => 0, altitude 40 => 1
    let top = topMin + (topMax - topMin) * Math.max(0, Math.min(1, t));

    // turbulence adds jitter feel
    const jig = Math.min(10, Math.floor(turbulence / 12));
    top += (jig ? (Math.sin(Date.now() / 70) * jig) : 0);

    plane.style.left = `${{left}}px`;
    plane.style.top = `${{top}}px`;

    // slight tilt depending on progress and turbulence
    const tilt = (progress < 0.12) ? -10 : (progress > 0.88 ? 10 : 0);
    const turTilt = Math.max(-8, Math.min(8, (turbulence / 18)));
    plane.style.transform = `rotate(${{tilt + turTilt}}deg)`;

    // contrail width
    trail.style.top = `${{top + 26}}px`;
    trail.style.width = `${{Math.max(0, left - 10)}}px`;

    // charts
    altSeries.push(altitude);
    turbSeries.push(turbulence);
    if (altSeries.length > 120) altSeries.shift();
    if (turbSeries.length > 120) turbSeries.shift();

    drawSeries("altChart", altSeries, "altLabel", 110);
    drawSeries("turbChart", turbSeries, "turbLabel", 110);
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

    plannedSeconds = Math.max(5, Math.min(240, minutes)) * 60;
    startMs = Date.now();
    elapsedBeforePause = 0;
    paused = false;

    altitude = 100;
    turbulence = 0;
    distCount = 0;

    altSeries.length = 0;
    turbSeries.length = 0;

    setControls(true);
    document.getElementById("pauseBtn").textContent = "Pause";
    setStatus(true, false);
    addLog(`Takeoff: ${{subject}}, plan ${{Math.floor(plannedSeconds/60)}} min, session #${{sessionId}}`);
    toast("Takeoff");

    if (timer) clearInterval(timer);
    timer = setInterval(tick, 250);

    document.getElementById("timeLeft").textContent = fmtTime(plannedSeconds);
    updateUI(0);
    await refreshStats();
  }}

  function togglePause() {{
    if (!sessionId) return;

    if (!paused) {{
      paused = true;
      const now = Date.now();
      elapsedBeforePause += Math.floor((now - startMs) / 1000);
      document.getElementById("pauseBtn").textContent = "Resume";
      setStatus(true, true);
      addLog("Paused.");
      toast("Paused");
    }} else {{
      paused = false;
      startMs = Date.now();
      document.getElementById("pauseBtn").textContent = "Pause";
      setStatus(true, false);
      addLog("Resumed.");
      toast("Resumed");
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
      toast("Log failed");
      return;
    }}

    distCount += 1;
    turbulence += 7;
    altitude = Math.max(40, altitude - 6);

    const sky = document.getElementById("sky");
    sky.classList.remove("shake");
    void sky.offsetWidth;
    sky.classList.add("shake");

    addLog(note ? `Turbulence: ${{note}}` : "Turbulence: distraction logged");
    toast("Turbulence");
    await refreshStats();
  }}

  async function endFlight() {{
    if (!sessionId) return;

    let elapsed = elapsedBeforePause;
    if (!paused) {{
      elapsed += Math.floor((Date.now() - startMs) / 1000);
    }}
    elapsed = Math.max(0, Math.min(plannedSeconds, elapsed));

    const [g] = gradeFromAlt(altitude);
    const landing =
      altitude >= 90 ? "Smooth landing" :
      altitude >= 80 ? "Good landing" :
      altitude >= 65 ? "Bumpy landing" :
      "Rough landing";

    addLog(`${{landing}}. Grade ${{g}}, altitude ${{altitude}}, distractions ${{distCount}}`);
    toast(`Landing: ${{g}}`);

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
    setStatus(false, false);

    if (timer) clearInterval(timer);
    timer = null;

    await refreshStats();
  }}

  refreshStats();
  setStatus(false, false);
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
