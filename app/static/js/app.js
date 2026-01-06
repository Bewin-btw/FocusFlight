let sessionId = null;
let plannedSeconds = 0;
let startMs = 0;
let elapsedBeforePause = 0;
let timer = null;
let paused = false;

let altitude = 100;
let turbulence = 0;
let distCount = 0;

let checkpoints = [];
let nextCheckpointIdx = 0;
let pendingCheckpointId = null;

const altSeries = [];
const turbSeries = [];

function $(id){ return document.getElementById(id); }

function soundEnabled(){
  return $("soundToggle").checked;
}

/* WebAudio: no files needed */
let audioCtx = null;
function beep(freq, ms, type="sine", gain=0.06){
  if (!soundEnabled()) return;
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const t0 = audioCtx.currentTime;
  const osc = audioCtx.createOscillator();
  const g = audioCtx.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  g.gain.value = gain;
  osc.connect(g);
  g.connect(audioCtx.destination);
  osc.start(t0);
  osc.stop(t0 + ms/1000);
}
function takeoffSound(){
  if (!soundEnabled()) return;
  beep(220, 120, "sine", 0.05);
  setTimeout(() => beep(330, 120, "sine", 0.05), 110);
  setTimeout(() => beep(440, 160, "triangle", 0.06), 220);
}
function ding(){
  if (!soundEnabled()) return;
  beep(880, 90, "triangle", 0.05);
  setTimeout(() => beep(1320, 70, "triangle", 0.04), 90);
}

function toast(msg){
  const el = $("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 1100);
}

function fmtTime(totalSeconds){
  totalSeconds = Math.max(0, Math.floor(totalSeconds));
  const m = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const s = String(totalSeconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function addLog(text){
  const log = $("log");
  const item = document.createElement("div");
  item.className = "log-item";
  const ts = new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit", second:"2-digit"});
  item.innerHTML = `<span class="mono">${ts}</span> - ${text}`;
  log.prepend(item);
}

function setStatus(running, pausing=false){
  const dot = $("statusDot");
  const txt = $("statusText");
  if (!running){
    dot.style.background = "rgba(255,255,255,0.35)";
    txt.textContent = "Idle";
    return;
  }
  if (pausing){
    dot.style.background = "rgba(255,211,107,0.95)";
    txt.textContent = "Paused";
    return;
  }
  dot.style.background = "rgba(94,240,168,0.95)";
  txt.textContent = "Flying";
}

function setControls(running){
  $("startBtn").disabled = running;
  $("pauseBtn").disabled = !running;
  $("endBtn").disabled = !running;
  $("distBtn").disabled = !running;
  $("subject").disabled = running;
  $("minutes").disabled = running;
}

function gradeFromAlt(alt){
  if (alt >= 90) return ["A", "rgba(94,240,168,0.18)", "rgba(94,240,168,0.45)"];
  if (alt >= 80) return ["B", "rgba(154,209,255,0.18)", "rgba(154,209,255,0.45)"];
  if (alt >= 65) return ["C", "rgba(255,211,107,0.18)", "rgba(255,211,107,0.45)"];
  return ["D", "rgba(255,107,139,0.18)", "rgba(255,107,139,0.45)"];
}

function updateGrade(){
  const pill = $("gradePill");
  const [g, bg, br] = gradeFromAlt(altitude);
  pill.textContent = `Grade: ${g}`;
  pill.style.background = bg;
  pill.style.borderColor = br;
}

function drawSeries(canvasId, series, labelId, scaleMax=110){
  const canvas = $(canvasId);
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  ctx.lineWidth = 1;
  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  for (let i = 1; i <= 4; i++){
    const y = (h * i) / 5;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }
  if (series.length < 2) return;

  const pad = 14;
  const minV = 0, maxV = scaleMax;

  const xAt = (i) => pad + (w - pad*2) * (i / (series.length - 1));
  const yAt = (v) => (h - pad) - (h - pad*2) * ((v - minV) / (maxV - minV));

  ctx.lineWidth = 3;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.strokeStyle = "rgba(154,209,255,0.9)";
  ctx.beginPath();
  ctx.moveTo(xAt(0), yAt(series[0]));
  for (let i = 1; i < series.length; i++) ctx.lineTo(xAt(i), yAt(series[i]));
  ctx.stroke();

  ctx.globalAlpha = 0.22;
  ctx.fillStyle = "rgba(154,209,255,0.7)";
  ctx.beginPath();
  ctx.moveTo(xAt(0), yAt(series[0]));
  for (let i = 1; i < series.length; i++) ctx.lineTo(xAt(i), yAt(series[i]));
  ctx.lineTo(xAt(series.length - 1), h - pad);
  ctx.lineTo(xAt(0), h - pad);
  ctx.closePath();
  ctx.fill();
  ctx.globalAlpha = 1;

  const last = series[series.length - 1];
  ctx.fillStyle = "rgba(255,255,255,0.9)";
  ctx.beginPath(); ctx.arc(xAt(series.length - 1), yAt(last), 4.5, 0, Math.PI*2); ctx.fill();

  $(labelId).textContent = (canvasId === "altChart") ? `ALT ${last}` : `TRB ${last}`;
}

function updateUI(progress){
  $("barFill").style.width = `${Math.min(100, Math.max(0, progress * 100))}%`;

  $("altitude").textContent = altitude;
  $("turb").textContent = turbulence;
  $("distCount").textContent = distCount;

  updateGrade();

  const sky = $("sky");
  const plane = $("plane");
  const trail = $("trail");

  const w = sky.clientWidth;
  const left = 18 + (w - 90) * progress;

  const topMin = 52;
  const topMax = 190;
  const t = 1 - ((altitude - 40) / 60);
  let top = topMin + (topMax - topMin) * Math.max(0, Math.min(1, t));

  const jig = Math.min(10, Math.floor(turbulence / 12));
  top += jig ? (Math.sin(Date.now() / 70) * jig) : 0;

  plane.style.left = `${left}px`;
  plane.style.top = `${top}px`;

  const tilt = (progress < 0.12) ? -10 : (progress > 0.88 ? 10 : 0);
  const turTilt = Math.max(-8, Math.min(8, (turbulence / 18)));
  plane.style.transform = `rotate(${tilt + turTilt}deg)`;

  trail.style.top = `${top + 22}px`;
  trail.style.width = `${Math.max(0, left - 10)}px`;

  altSeries.push(altitude);
  turbSeries.push(turbulence);
  if (altSeries.length > 120) altSeries.shift();
  if (turbSeries.length > 120) turbSeries.shift();

  drawSeries("altChart", altSeries, "altLabel", 110);
  drawSeries("turbChart", turbSeries, "turbLabel", 110);
}

/* Autopilot checkpoints */
async function loadCheckpoints(){
  const res = await fetch(`/api/session/${sessionId}/checkpoints`);
  if (!res.ok) return;
  const data = await res.json();
  checkpoints = data.items || [];
  nextCheckpointIdx = 0;
  pendingCheckpointId = null;
}

function showCheckpointModal(checkpointId){
  pendingCheckpointId = checkpointId;
  $("checkpointNote").value = "";
  $("checkpointModal").classList.add("show");
  $("checkpointModal").setAttribute("aria-hidden", "false");
  toast("Checkpoint");
}

function hideCheckpointModal(){
  $("checkpointModal").classList.remove("show");
  $("checkpointModal").setAttribute("aria-hidden", "true");
  pendingCheckpointId = null;
}

async function completeCheckpointNow(){
  if (!pendingCheckpointId) return;
  const note = $("checkpointNote").value.trim();
  await fetch("/api/checkpoint/complete", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ checkpoint_id: pendingCheckpointId, note })
  });
  addLog(note ? `Checkpoint done: ${note}` : "Checkpoint done");
  hideCheckpointModal();
}

function maybeTriggerCheckpoint(elapsedSeconds){
  while (nextCheckpointIdx < checkpoints.length){
    const cp = checkpoints[nextCheckpointIdx];
    if (cp.completed_at){
      nextCheckpointIdx += 1;
      continue;
    }
    if (elapsedSeconds >= cp.due_seconds){
      showCheckpointModal(cp.id);
      nextCheckpointIdx += 1;
      return;
    }
    break;
  }
}

function tick(){
  if (!sessionId || paused) return;

  const now = Date.now();
  const elapsed = elapsedBeforePause + Math.floor((now - startMs) / 1000);
  const left = plannedSeconds - elapsed;

  $("timeLeft").textContent = fmtTime(left);

  const progress = Math.min(1, elapsed / plannedSeconds);
  updateUI(progress);

  maybeTriggerCheckpoint(elapsed);

  if (left <= 0){
    addLog("Landing complete. Ending flight.");
    endFlight();
  }
}

async function refreshHistory(){
  const res = await fetch("/api/sessions/recent?limit=10");
  if (!res.ok) return;
  const data = await res.json();
  renderRecent(data.items || []);
}

function renderRecent(items){
  const root = $("recentCards");
  root.innerHTML = "";

  if (!items.length){
    root.innerHTML = `<div class="muted mini">No finished flights yet</div>`;
    return;
  }

  for (const s of items){
    const card = document.createElement("div");
    card.className = "flight-card";

    const g = s.grade || "-";
    const [_, bg, br] = gradeFromAlt(s.altitude_end ?? 100);

    card.innerHTML = `
      <div class="topline">
        <div>
          <div style="font-weight:720">${escapeHtml(s.subject)}</div>
          <div class="mini muted">
            ${escapeHtml(s.started_at || "")}
          </div>
        </div>
        <div class="badge" style="background:${bg}; border-color:${br}">Grade ${g}</div>
      </div>
      <div class="mini muted" style="margin-top:8px">
        planned ${s.planned_minutes}m · actual ${Math.round((s.actual_seconds || 0)/60)}m · distractions ${s.distractions_count} · altitude ${s.altitude_end}
      </div>
    `;
    root.appendChild(card);
  }
}

function escapeHtml(s){
  return String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
}

/* API actions */
async function startFlight(){
  const subject = $("subject").value.trim() || "Study";
  const minutes = parseInt($("minutes").value || "50", 10);

  const res = await fetch("/api/session/start", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ subject, planned_minutes: minutes })
  });
  const data = await res.json();

  sessionId = data.session_id;
  plannedSeconds = (data.planned_minutes || minutes) * 60;

  startMs = Date.now();
  elapsedBeforePause = 0;
  paused = false;

  altitude = 100;
  turbulence = 0;
  distCount = 0;

  altSeries.length = 0;
  turbSeries.length = 0;

  setControls(true);
  setStatus(true, false);
  $("pauseBtn").textContent = "Pause";
  $("timeLeft").textContent = fmtTime(plannedSeconds);

  addLog(`Takeoff: ${subject}, plan ${Math.floor(plannedSeconds/60)} min, session #${sessionId}`);
  takeoffSound();
  toast("Takeoff");

  await loadCheckpoints();

  if (timer) clearInterval(timer);
  timer = setInterval(tick, 250);

  updateUI(0);
}

function togglePause(){
  if (!sessionId) return;

  if (!paused){
    paused = true;
    elapsedBeforePause += Math.floor((Date.now() - startMs) / 1000);
    $("pauseBtn").textContent = "Resume";
    setStatus(true, true);
    addLog("Paused.");
    toast("Paused");
  } else {
    paused = false;
    startMs = Date.now();
    $("pauseBtn").textContent = "Pause";
    setStatus(true, false);
    addLog("Resumed.");
    toast("Resumed");
  }
}

async function logDistraction(){
  if (!sessionId) return;

  const note = $("note").value.trim();
  $("note").value = "";

  const res = await fetch("/api/distraction", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ session_id: sessionId, note })
  });
  if (!res.ok){
    addLog("Failed to log distraction.");
    toast("Log failed");
    return;
  }

  distCount += 1;
  turbulence += 7;
  altitude = Math.max(40, altitude - 6);

  addLog(note ? `Turbulence: ${note}` : "Turbulence: distraction logged");
  ding();
  toast("Ding");
}

async function endFlight(){
  if (!sessionId) return;

  let elapsed = elapsedBeforePause;
  if (!paused) elapsed += Math.floor((Date.now() - startMs) / 1000);
  elapsed = Math.max(0, Math.min(plannedSeconds, elapsed));

  const res = await fetch("/api/session/end", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      actual_seconds: elapsed,
      altitude_end: altitude,
      turbulence_end: turbulence
    })
  });

  const data = await res.json().catch(() => ({}));
  addLog(`Landing. Grade ${(data.grade || "-")} · altitude ${altitude} · distractions ${distCount}`);
  toast("Landed");

  sessionId = null;
  paused = false;

  setControls(false);
  setStatus(false, false);

  if (timer) clearInterval(timer);
  timer = null;

  await refreshHistory();
}

/* Wire up */
$("startBtn").addEventListener("click", startFlight);
$("pauseBtn").addEventListener("click", togglePause);
$("endBtn").addEventListener("click", endFlight);
$("distBtn").addEventListener("click", logDistraction);
$("refreshHistoryBtn").addEventListener("click", refreshHistory);

$("checkpointDone").addEventListener("click", completeCheckpointNow);
$("checkpointSkip").addEventListener("click", () => {
  addLog("Checkpoint skipped");
  hideCheckpointModal();
});

refreshHistory();
setStatus(false, false);
