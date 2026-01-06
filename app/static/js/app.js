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

function $(id) { return document.getElementById(id); }

/* Small helpers */
function normCode(x) {
  return String(x || "").trim().toUpperCase();
}

function setSelectValueSafe(selectEl, a) {
  if (!selectEl) return;
  const code = normCode(a?.code);
  if (!code) return;

  let opt = Array.from(selectEl.options).find(o => normCode(o.value) === code);
  if (!opt) {
    opt = document.createElement("option");
    opt.value = code;
    opt.textContent = airportLabel({ code, name: a?.name || code });
    selectEl.appendChild(opt);
  } else if (!opt.textContent || opt.textContent.length < 3) {
    opt.textContent = airportLabel({ code, name: a?.name || code });
  }

  selectEl.value = code;
}

function getSelectValueSafe(selectEl, fallback = "") {
  const v = normCode(selectEl?.value);
  return v || normCode(fallback);
}

/* Airport search UI */
const AIRPORT_RECENTS_KEY = "ife_airport_recents_v1";
const AIRPORT_CACHE = new Map(); // query -> items
let _searchAbort = null;

function airportLabel(a) {
  if (!a) return "";
  const code = (a.code || "").toUpperCase();
  const name = a.name || "";
  return `${code}  ${name}`.trim();
}

function airportSub(a) {
  const lat = (a.lat != null) ? Number(a.lat).toFixed(2) : null;
  const lon = (a.lon != null) ? Number(a.lon).toFixed(2) : null;
  if (lat && lon) return `Lat ${lat}, Lon ${lon}`;
  return "";
}

function loadRecents() {
  try {
    const raw = localStorage.getItem(AIRPORT_RECENTS_KEY);
    const arr = JSON.parse(raw || "[]");
    if (!Array.isArray(arr)) return [];
    return arr.slice(0, 8);
  } catch {
    return [];
  }
}

function saveRecent(a) {
  if (!a || !a.code) return;
  const code = String(a.code).toUpperCase();
  const recents = loadRecents().filter(x => String(x.code).toUpperCase() !== code);
  recents.unshift({ code, name: a.name, lat: a.lat, lon: a.lon });
  localStorage.setItem(AIRPORT_RECENTS_KEY, JSON.stringify(recents.slice(0, 8)));
}

function escapeHtml(s) {
  return String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function markMatch(text, q) {
  const s = String(text || "");
  const query = String(q || "").trim();
  if (!query) return escapeHtml(s);
  const idx = s.toLowerCase().indexOf(query.toLowerCase());
  if (idx < 0) return escapeHtml(s);
  const a = s.slice(0, idx);
  const b = s.slice(idx, idx + query.length);
  const c = s.slice(idx + query.length);
  return `${escapeHtml(a)}<span class="combo-mark">${escapeHtml(b)}</span>${escapeHtml(c)}`;
}

/* Client-side relevance sort (exact IATA on top, then city-ish, then name) */
function guessCity(name) {
  const s = String(name || "")
    .replace(/International/gi, "")
    .replace(/Airport/gi, "")
    .replace(/\(.*?\)/g, "")
    .replace(/\s{2,}/g, " ")
    .trim();
  return s;
}

function scoreAirport(a, q) {
  const query = String(q || "").trim();
  if (!query) return 0;

  const qUp = query.toUpperCase();
  const qLo = query.toLowerCase();

  const code = normCode(a?.code);
  const name = String(a?.name || "");
  const nameLo = name.toLowerCase();
  const cityLo = guessCity(name).toLowerCase();

  let s = 0;

  if (code === qUp) s += 1000;
  else if (code.startsWith(qUp)) s += 700;
  else if (code.includes(qUp)) s += 350;

  if (cityLo.startsWith(qLo)) s += 280;
  else if (cityLo.includes(qLo)) s += 140;

  if (nameLo.startsWith(qLo)) s += 220;
  else if (nameLo.includes(qLo)) s += 120;

  const parts = qLo.split(/\s+/).filter(Boolean);
  if (parts.length && parts.every(p => nameLo.includes(p) || cityLo.includes(p))) s += 120;

  return s;
}

function sortAirports(items, q) {
  const query = String(q || "").trim();
  return [...items].sort((a, b) => {
    const sa = scoreAirport(a, query);
    const sb = scoreAirport(b, query);
    if (sb !== sa) return sb - sa;
    return normCode(a?.code).localeCompare(normCode(b?.code));
  });
}

async function apiSearchAirports(q, limit = 20) {
  const query = String(q || "").trim();
  if (!query) return [];
  const key = `${query.toLowerCase()}::${limit}`;
  if (AIRPORT_CACHE.has(key)) return AIRPORT_CACHE.get(key);

  if (_searchAbort) _searchAbort.abort();
  _searchAbort = new AbortController();

  const url = `/api/ife/airports/search?q=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit)}`;
  const res = await fetch(url, { signal: _searchAbort.signal }).catch(() => null);
  if (!res || !res.ok) return [];

  const data = await res.json().catch(() => null);
  const items = (data && Array.isArray(data.items)) ? data.items : [];
  AIRPORT_CACHE.set(key, items);
  return items;
}

function ensureSelectOption(selectEl, a) {
  setSelectValueSafe(selectEl, a);
}

function setComboDisabled(prefix, disabled) {
  const input = $(`${prefix}Input`);
  const clear = $(`${prefix}Clear`);
  const toggle = $(`${prefix}Toggle`);
  if (input) input.disabled = disabled;
  if (clear) clear.disabled = disabled;
  if (toggle) toggle.disabled = disabled;
}

function closeMenu(prefix) {
  const menu = $(`${prefix}Menu`);
  if (menu) menu.classList.remove("open");
}

function openMenu(prefix) {
  const menu = $(`${prefix}Menu`);
  if (menu) menu.classList.add("open");
}

function renderMenu(prefix, items, query, sectionTitle = null) {
  const menu = $(`${prefix}Menu`);
  if (!menu) return;

  const rows = [];

  if (sectionTitle) {
    const countTag = items.length ? `<span class="tag">${items.length}</span>` : "";
    rows.push(`<div class="combo-section"><span>${escapeHtml(sectionTitle)}</span>${countTag}</div>`);
  }

  if (!items.length) {
    rows.push(`<div class="combo-empty">No results. Try city name or IATA code.</div>`);
    menu.innerHTML = rows.join("");
    return;
  }

  for (let i = 0; i < items.length; i++) {
    const a = items[i];
    const code = String(a.code || "").toUpperCase();
    const title = a.name || code;
    const sub = airportSub(a);

    rows.push(`
      <div class="combo-item" role="option" data-idx="${i}">
        <div class="combo-code">${escapeHtml(code)}</div>
        <div class="combo-name">
          <div class="combo-title">${markMatch(title, query)}</div>
          <div class="combo-sub">${escapeHtml(sub)}</div>
        </div>
        <div class="combo-action">Select</div>
      </div>
    `);
  }

  menu.innerHTML = rows.join("");
}

function setActiveItem(prefix, idx) {
  const menu = $(`${prefix}Menu`);
  if (!menu) return;
  const items = Array.from(menu.querySelectorAll(".combo-item"));
  items.forEach(el => el.classList.remove("active"));
  const el = items[idx];
  if (el) {
    el.classList.add("active");
    el.scrollIntoView({ block: "nearest" });
  }
}

function createAirportCombobox(prefix, selectId) {
  const input = $(`${prefix}Input`);
  const menu = $(`${prefix}Menu`);
  const clearBtn = $(`${prefix}Clear`);
  const toggleBtn = $(`${prefix}Toggle`);
  const hint = $(`${prefix}Hint`);
  const selectEl = $(selectId);

  let currentItems = [];
  let activeIdx = -1;
  let lastPicked = null;
  let debounceTimer = null;

  function setHint(a) {
    if (!hint) return;
    if (!a) { hint.textContent = ""; return; }
    hint.textContent = airportSub(a);
  }

  async function showRecents() {
    const recents = loadRecents();
    currentItems = recents;
    activeIdx = recents.length ? 0 : -1;
    renderMenu(prefix, recents, "", recents.length ? "Recent airports" : null);
    openMenu(prefix);
    setActiveItem(prefix, activeIdx);
  }

  async function doSearch(q) {
    const query = String(q || "").trim();
    if (!query) {
      await showRecents();
      return;
    }

    menu.innerHTML = `<div class="combo-loading">Searching...</div>`;
    openMenu(prefix);

    const raw = await apiSearchAirports(query, 22);
    const items = sortAirports(raw, query);
    currentItems = items;
    activeIdx = items.length ? 0 : -1;
    renderMenu(prefix, items, query, "Results");
    setActiveItem(prefix, activeIdx);
  }

  function pickIndex(i) {
    const a = currentItems[i];
    if (!a) return;

    lastPicked = a;
    saveRecent(a);

    ensureSelectOption(selectEl, a);
    input.value = airportLabel(a);
    setHint(a);

    closeMenu(prefix);

    selectEl.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function normalizeOnBlur() {
    if (lastPicked) {
      input.value = airportLabel(lastPicked);
      setHint(lastPicked);
      return;
    }
    input.value = "";
    setHint(null);
    if (selectEl) selectEl.value = "";
  }

  input.addEventListener("focus", async () => {
    if (input.disabled) return;
    await showRecents();
  });

  input.addEventListener("input", () => {
    if (input.disabled) return;
    const q = input.value;

    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => { doSearch(q); }, 160);
  });

  input.addEventListener("keydown", (e) => {
    const isOpen = menu.classList.contains("open");

    if (e.key === "Escape") {
      closeMenu(prefix);
      e.preventDefault();
      return;
    }

    if (!isOpen && (e.key === "ArrowDown" || e.key === "Enter")) {
      showRecents();
      e.preventDefault();
      return;
    }

    if (!isOpen) return;

    if (e.key === "ArrowDown") {
      activeIdx = Math.min(currentItems.length - 1, activeIdx + 1);
      setActiveItem(prefix, activeIdx);
      e.preventDefault();
      return;
    }

    if (e.key === "ArrowUp") {
      activeIdx = Math.max(0, activeIdx - 1);
      setActiveItem(prefix, activeIdx);
      e.preventDefault();
      return;
    }

    if (e.key === "Enter") {
      if (activeIdx >= 0) pickIndex(activeIdx);
      e.preventDefault();
      return;
    }
  });

  clearBtn.addEventListener("click", () => {
    if (input.disabled) return;
    input.value = "";
    lastPicked = null;
    setHint(null);
    if (selectEl) selectEl.value = "";
    showRecents();
  });

  toggleBtn.addEventListener("click", async () => {
    if (input.disabled) return;
    if (menu.classList.contains("open")) {
      closeMenu(prefix);
    } else {
      await showRecents();
      input.focus();
    }
  });

  menu.addEventListener("mousedown", (e) => {
    const item = e.target.closest(".combo-item");
    if (!item) return;
    const idx = parseInt(item.getAttribute("data-idx") || "-1", 10);
    if (idx >= 0) pickIndex(idx);
  });

  document.addEventListener("mousedown", (e) => {
    const combo = $(`${prefix}Combo`);
    if (!combo) return;
    if (!combo.contains(e.target)) closeMenu(prefix);
  });

  input.addEventListener("blur", () => {
    setTimeout(() => {
      if (!menu.classList.contains("open")) normalizeOnBlur();
    }, 120);
  });

  return {
    setSelected(a) {
      if (!a) return;
      lastPicked = a;
      ensureSelectOption(selectEl, a);
      input.value = airportLabel(a);
      setHint(a);
    },
    getSelected() {
      return lastPicked;
    }
  };
}

async function fetchAirportByCode(code) {
  const c = normCode(code);
  if (!c) return null;
  const raw = await apiSearchAirports(c, 30);
  const items = sortAirports(raw, c);
  const exact = items.find(x => normCode(x.code) === c);
  return exact || items[0] || null;
}

/* IFE map state */
let map = null;
let planeMarker = null;
let routeSourceId = "routeSource";
let routeLineId = "routeLine";
let plan = null;

/* IFE view toggles */
let followPlane = true;
let use3DView = true;
let lastFollowMs = 0;
const FOLLOW_THROTTLE_MS = 800;

/* Time zones */
let originTzName = null;
let destTzName = null;
let tzTimer = null;

function currentMode() {
  const el = $("routeMode");
  return el ? el.value : "custom";
}

function isRealMode() {
  return currentMode() === "real";
}

function updateMinutesLock() {
  if (!$("minutes")) return;
  if (sessionId) {
    $("minutes").disabled = true;
    return;
  }
  $("minutes").disabled = isRealMode();
}

function effectsEnabled() {
  return $("soundToggle")?.checked;
}

function ambienceEnabled() {
  return $("ambientToggle")?.checked;
}

/* WebAudio: no files needed */
let audioCtx = null;
function beep(freq, ms, type = "sine", gain = 0.06) {
  if (!effectsEnabled()) return;
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
  osc.stop(t0 + ms / 1000);
}

function takeoffSound() {
  if (!effectsEnabled()) return;
  beep(220, 120, "sine", 0.05);
  setTimeout(() => beep(330, 120, "sine", 0.05), 110);
  setTimeout(() => beep(440, 160, "triangle", 0.06), 220);
}

function ding() {
  if (!effectsEnabled()) return;
  beep(880, 90, "triangle", 0.05);
  setTimeout(() => beep(1320, 70, "triangle", 0.04), 90);
}

let ambience = {
  gain: null,
  osc1: null,
  osc2: null,
  noise: null,
  noiseFilter: null,
  lfo: null,
  lfoGain: null
};

function ensureAudio() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}

function startAmbience() {
  if (!ambienceEnabled()) return;

  const ctx = ensureAudio();
  if (ambience.gain) return;

  const master = ctx.createGain();
  master.gain.value = 0.0001;

  const osc1 = ctx.createOscillator();
  osc1.type = "sine";
  osc1.frequency.value = 55;

  const osc2 = ctx.createOscillator();
  osc2.type = "triangle";
  osc2.frequency.value = 110;

  const noiseBuf = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
  const ch = noiseBuf.getChannelData(0);
  for (let i = 0; i < ch.length; i++) ch[i] = (Math.random() * 2 - 1) * 0.35;

  const noise = ctx.createBufferSource();
  noise.buffer = noiseBuf;
  noise.loop = true;

  const noiseFilter = ctx.createBiquadFilter();
  noiseFilter.type = "bandpass";
  noiseFilter.frequency.value = 420;
  noiseFilter.Q.value = 0.8;

  const lfo = ctx.createOscillator();
  lfo.type = "sine";
  lfo.frequency.value = 0.18;

  const lfoGain = ctx.createGain();
  lfoGain.gain.value = 0.04;

  lfo.connect(lfoGain);
  lfoGain.connect(master.gain);

  osc1.connect(master);
  osc2.connect(master);
  noise.connect(noiseFilter);
  noiseFilter.connect(master);

  master.connect(ctx.destination);

  const t = ctx.currentTime;
  master.gain.setValueAtTime(0.0001, t);
  master.gain.linearRampToValueAtTime(0.11, t + 0.9);

  osc1.start();
  osc2.start();
  noise.start();
  lfo.start();

  ambience = { gain: master, osc1, osc2, noise, noiseFilter, lfo, lfoGain };
}

function stopAmbience() {
  const ctx = audioCtx;
  if (!ctx || !ambience.gain) return;

  const t = ctx.currentTime;
  ambience.gain.gain.cancelScheduledValues(t);
  ambience.gain.gain.setValueAtTime(ambience.gain.gain.value, t);
  ambience.gain.gain.linearRampToValueAtTime(0.0001, t + 0.6);

  setTimeout(() => {
    try { ambience.osc1?.stop(); } catch { }
    try { ambience.osc2?.stop(); } catch { }
    try { ambience.noise?.stop(); } catch { }
    try { ambience.lfo?.stop(); } catch { }

    try { ambience.gain?.disconnect(); } catch { }
    ambience = { gain: null, osc1: null, osc2: null, noise: null, noiseFilter: null, lfo: null, lfoGain: null };
  }, 700);
}

function bumpAmbienceForTakeoff() {
  const ctx = audioCtx;
  if (!ctx || !ambience.gain) return;
  const t = ctx.currentTime;
  ambience.gain.gain.cancelScheduledValues(t);
  ambience.gain.gain.setValueAtTime(ambience.gain.gain.value, t);
  ambience.gain.gain.linearRampToValueAtTime(0.14, t + 0.6);
  ambience.gain.gain.linearRampToValueAtTime(0.11, t + 2.4);
}

function bumpAmbienceForTurbulence() {
  const ctx = audioCtx;
  if (!ctx || !ambience.noiseFilter) return;
  const t = ctx.currentTime;
  ambience.noiseFilter.frequency.cancelScheduledValues(t);
  ambience.noiseFilter.frequency.setValueAtTime(ambience.noiseFilter.frequency.value, t);
  ambience.noiseFilter.frequency.linearRampToValueAtTime(720, t + 0.15);
  ambience.noiseFilter.frequency.linearRampToValueAtTime(420, t + 1.0);
}

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 1100);
}

function fmtTime(totalSeconds) {
  totalSeconds = Math.max(0, Math.floor(totalSeconds));
  const m = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const s = String(totalSeconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function addLog(text) {
  const log = $("log");
  const item = document.createElement("div");
  item.className = "log-item";
  const ts = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  item.innerHTML = `<span class="mono">${ts}</span> - ${text}`;
  log.prepend(item);
}

function setStatus(running, pausing = false) {
  const dot = $("statusDot");
  const txt = $("statusText");
  if (!running) {
    dot.style.background = "rgba(255,255,255,0.35)";
    txt.textContent = "Idle";
    return;
  }
  if (pausing) {
    dot.style.background = "rgba(255,211,107,0.95)";
    txt.textContent = "Paused";
    return;
  }
  dot.style.background = "rgba(94,240,168,0.95)";
  txt.textContent = "Flying";
}

function setControls(running) {
  $("startBtn").disabled = running;
  $("pauseBtn").disabled = !running;
  $("endBtn").disabled = !running;
  $("distBtn").disabled = !running;

  $("subject").disabled = running;
  $("originSelect").disabled = running;
  $("destSelect").disabled = running;

  if ($("routeMode")) $("routeMode").disabled = running;
  if ($("pickRouteBtn")) $("pickRouteBtn").disabled = running;

  updateMinutesLock();
  setComboDisabled("origin", running);
  setComboDisabled("dest", running);
  if ($("swapBtn")) $("swapBtn").disabled = running;
}

function gradeFromAlt(alt) {
  if (alt >= 90) return ["A", "rgba(94,240,168,0.18)", "rgba(94,240,168,0.45)"];
  if (alt >= 80) return ["B", "rgba(154,209,255,0.18)", "rgba(154,209,255,0.45)"];
  if (alt >= 65) return ["C", "rgba(255,211,107,0.18)", "rgba(255,211,107,0.45)"];
  return ["D", "rgba(255,107,139,0.18)", "rgba(255,107,139,0.45)"];
}

function updateGrade() {
  const pill = $("gradePill");
  const [g, bg, br] = gradeFromAlt(altitude);
  pill.textContent = `Grade: ${g}`;
  pill.style.background = bg;
  pill.style.borderColor = br;
}

function drawSeries(canvasId, series, labelId, scaleMax = 110) {
  const canvas = $(canvasId);
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  ctx.lineWidth = 1;
  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  for (let i = 1; i <= 4; i++) {
    const y = (h * i) / 5;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }
  if (series.length < 2) return;

  const pad = 14;
  const minV = 0, maxV = scaleMax;

  const xAt = (i) => pad + (w - pad * 2) * (i / (series.length - 1));
  const yAt = (v) => (h - pad) - (h - pad * 2) * ((v - minV) / (maxV - minV));

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
  ctx.beginPath(); ctx.arc(xAt(series.length - 1), yAt(last), 4.5, 0, Math.PI * 2); ctx.fill();

  $(labelId).textContent = (canvasId === "altChart") ? `ALT ${last}` : `TRB ${last}`;
}

/* Time zone helpers */
async function fetchTzFor(lat, lon) {
  try {
    const res = await fetch(`/api/ife/tz?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`);
    if (!res.ok) return "UTC";
    const data = await res.json();
    return data.tz || "UTC";
  } catch {
    return "UTC";
  }
}

function formatTimeInTz(tz) {
  try {
    return new Intl.DateTimeFormat([], {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: tz
    }).format(new Date());
  } catch {
    return new Intl.DateTimeFormat([], { hour: "2-digit", minute: "2-digit" }).format(new Date());
  }
}

function startTzClocks() {
  if (tzTimer) clearInterval(tzTimer);

  const tickClocks = () => {
    if (originTzName) {
      $("originTime").textContent = formatTimeInTz(originTzName);
      $("originTz").textContent = originTzName;
    }
    if (destTzName) {
      $("destTime").textContent = formatTimeInTz(destTzName);
      $("destTz").textContent = destTzName;
    }
  };

  tickClocks();
  tzTimer = setInterval(tickClocks, 1000);
}

/* IFE helpers */
function applyMapView() {
  if (!map) return;

  if (use3DView) {
    map.easeTo({ pitch: 58, bearing: -20, duration: 450 });
  } else {
    map.easeTo({ pitch: 0, bearing: 0, duration: 350 });
  }
}

function ensureMapSnapshotEl() {
  const mapEl = $("map");
  if (!mapEl) return null;

  let img = $("mapSnapshotImg");
  if (!img) {
    img = document.createElement("img");
    img.id = "mapSnapshotImg";
    img.alt = "";
    mapEl.style.position = mapEl.style.position || "relative";
    img.style.position = "absolute";
    img.style.left = "0";
    img.style.top = "0";
    img.style.right = "0";
    img.style.bottom = "0";
    img.style.width = "100%";
    img.style.height = "100%";
    img.style.objectFit = "cover";
    img.style.pointerEvents = "none";
    img.style.display = "none";
    img.style.zIndex = "5";
    mapEl.appendChild(img);
  }
  return img;
}

function updateMapSnapshot() {
  try {
    if (!map) return;
    const img = ensureMapSnapshotEl();
    const canvas = map.getCanvas?.();
    if (!img || !canvas) return;
    img.src = canvas.toDataURL("image/png");
  } catch { }
}

function setMapLiveVisible(visible) {
  const mapEl = $("map");
  if (!mapEl) return;
  const canv = mapEl.querySelector(".maplibregl-canvas");
  const ctrls = mapEl.querySelector(".maplibregl-control-container");
  const v = !!visible;

  if (canv) {
    canv.style.opacity = v ? "1" : "0";
    canv.style.pointerEvents = v ? "auto" : "none";
  }
  if (ctrls) {
    ctrls.style.opacity = v ? "1" : "0";
    ctrls.style.pointerEvents = v ? "auto" : "none";
  }
}

function initMapOnce() {
  if (map) return;

  map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      sources: {
        osm: {
          type: "raster",
          tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          tileSize: 256,
          attribution: "© OpenStreetMap contributors"
        }
      },
      layers: [{ id: "osm", type: "raster", source: "osm" }]
    },
    center: [13.4, 52.52],
    zoom: 4
  });

  map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-right");

  map.dragRotate.enable();
  map.touchZoomRotate.enableRotation();

  ensureMapSnapshotEl();
  applyMapView();
}

async function fetchAirportsOnce(url) {
  const res = await fetch(url);
  if (!res.ok) return null;
  const data = await res.json().catch(() => null);
  if (!data || !Array.isArray(data.items)) return null;
  return data.items;
}

async function loadAirportsIntoSelects() {
  let items = await fetchAirportsOnce("/api/ife/airports?limit=4000");

  if (items && items.length < 30) {
    const alt = await fetchAirportsOnce("/api/ife/airports/airports?limit=4000");
    if (alt && alt.length > items.length) items = alt;
  }

  if (!items || !items.length) {
    toast("IFE airports failed");
    return false;
  }

  items.sort((a, b) => String(a.code).localeCompare(String(b.code)));

  const oSel = $("originSelect");
  const dSel = $("destSelect");

  oSel.innerHTML = "";
  dSel.innerHTML = "";

  for (const a of items) {
    const opt1 = document.createElement("option");
    opt1.value = a.code;
    opt1.textContent = `${a.code}  ${a.name}`;
    oSel.appendChild(opt1);

    const opt2 = document.createElement("option");
    opt2.value = a.code;
    opt2.textContent = `${a.code}  ${a.name}`;
    dSel.appendChild(opt2);
  }

  if (items.find(x => x.code === "BER")) oSel.value = "BER";
  else if (items[0]) oSel.value = items[0].code;

  if (items.find(x => x.code === "IST")) dSel.value = "IST";
  else if (items[1]) dSel.value = items[1].code;

  return true;
}

async function loadPlan(plannedMinutes) {
  const oFallback = originComboApi?.getSelected?.()?.code || "";
  const dFallback = destComboApi?.getSelected?.()?.code || "";

  const origin = getSelectValueSafe($("originSelect"), oFallback);
  const dest = getSelectValueSafe($("destSelect"), dFallback);

  if (!origin || !dest) return null;

  let url = `/api/ife/plan?origin=${encodeURIComponent(origin)}&dest=${encodeURIComponent(dest)}`;

  if (!isRealMode()) {
    url += `&planned_minutes=${encodeURIComponent(plannedMinutes)}`;
  }

  const res = await fetch(url);
  if (!res.ok) return null;

  const data = await res.json().catch(() => null);
  if (!data || data.error) return null;

  return data;
}

function setRouteOnMap(p) {
  plan = p;
  $("routeText").textContent = `${p.origin.code} to ${p.dest.code}`;
  $("speedText").textContent = String(p.speed_kmh ?? 0);

  if (!map) return;

  const bounds = new maplibregl.LngLatBounds();
  for (const c of p.path) bounds.extend(c);
  map.fitBounds(bounds, { padding: 40, duration: 600 });

  const geo = {
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      properties: {},
      geometry: { type: "LineString", coordinates: p.path }
    }]
  };

  if (!map.getSource(routeSourceId)) {
    map.addSource(routeSourceId, { type: "geojson", data: geo });
    map.addLayer({
      id: routeLineId,
      type: "line",
      source: routeSourceId,
      paint: {
        "line-width": 4,
        "line-opacity": 0.85
      }
    });
  } else {
    map.getSource(routeSourceId).setData(geo);
  }

  if (!planeMarker) {
    const el = document.createElement("div");
    el.textContent = "✈️";
    el.style.fontSize = "22px";
    planeMarker = new maplibregl.Marker({ element: el, rotationAlignment: "map" })
      .setLngLat(p.path[0])
      .addTo(map);
  } else {
    planeMarker.setLngLat(p.path[0]);
  }

  lastFollowMs = 0;
}

/* Weather */
function wxCodeToText(code) {
  const m = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Drizzle",
    53: "Drizzle",
    55: "Drizzle",
    61: "Rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Snow",
    73: "Snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Rain showers",
    82: "Heavy showers",
    95: "Thunderstorm"
  };
  return m[code] || `Weather code ${code}`;
}

async function fetchDestinationWeather(p) {
  try {
    const lat = p.dest.lat;
    const lon = p.dest.lon;

    const url =
      `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
      `&current_weather=true&forecast_days=1&timezone=auto`;

    const res = await fetch(url);
    if (!res.ok) {
      $("wxText").textContent = "Weather unavailable";
      $("wxSub").textContent = "";
      return;
    }

    const data = await res.json();
    if (!data.current_weather) {
      $("wxText").textContent = "No weather data";
      $("wxSub").textContent = "";
      return;
    }

    const cw = data.current_weather;
    const t = cw.temperature;
    const w = cw.windspeed;
    const code = cw.weathercode;

    $("wxText").textContent = `${wxCodeToText(code)}, ${t}°C`;
    $("wxSub").textContent = `Wind ${w} km/h, updated ${cw.time}`;
  } catch {
    $("wxText").textContent = "Weather failed";
    $("wxSub").textContent = "";
  }
}

function updateIFEProgress(progress) {
  if (!plan) return;

  const total = plan.path?.length || 0;
  if (total < 2) return;

  const idx = Math.max(0, Math.min(total - 1, Math.floor(progress * (total - 1))));
  const pos = plan.path[idx];

  if (planeMarker) planeMarker.setLngLat(pos);

  const remainKm = Math.max(0, (plan.total_km ?? 0) * (1 - progress));
  $("distRemain").textContent = String(Math.round(remainKm));

  const remainS = Math.max(0, Math.floor((plan.duration_s ?? 0) * (1 - progress)));
  const eta = new Date(Date.now() + remainS * 1000);
  const hh = String(eta.getHours()).padStart(2, "0");
  const mm = String(eta.getMinutes()).padStart(2, "0");
  $("etaText").textContent = `${hh}:${mm}`;

  if (map && followPlane) {
    const now = Date.now();
    if (now - lastFollowMs > FOLLOW_THROTTLE_MS) {
      lastFollowMs = now;
      map.easeTo({
        center: pos,
        duration: 650,
        pitch: use3DView ? 58 : 0,
        bearing: use3DView ? -20 : 0
      });
    }
  }
}

async function applyPlanToIFE(p) {
  initMapOnce();

  const apply = async () => {
    setRouteOnMap(p);

    if (!sessionId && isRealMode() && p.planned_minutes) {
      $("minutes").value = String(p.planned_minutes);
      updateMinutesLock();
    }

    originTzName = await fetchTzFor(p.origin.lat, p.origin.lon);
    destTzName = await fetchTzFor(p.dest.lat, p.dest.lon);
    startTzClocks();

    await fetchDestinationWeather(p);
    updateIFEProgress(0);

    if (document.body.classList.contains("cabin-on")) {
      updateMapSnapshot();
    }
  };

  if (!map) return;

  if (map.loaded()) {
    await apply();
  } else {
    map.once("load", async () => { await apply(); });
  }
}

async function setupIFEForFlight(plannedMinutes) {
  const p = await loadPlan(plannedMinutes);
  if (!p) {
    toast("IFE route failed");
    return null;
  }
  await applyPlanToIFE(p);
  return p;
}

async function pickRouteForSession(minutesOverride = null) {
  const minutes = minutesOverride ?? parseInt($("minutes").value || "50", 10);
  const originFallback = originComboApi?.getSelected?.()?.code || "";
  const origin = getSelectValueSafe($("originSelect"), originFallback);

  const res = await fetch(`/api/ife/pick?minutes=${encodeURIComponent(minutes)}&origin=${encodeURIComponent(origin)}`);
  if (!res.ok) {
    toast("Pick failed");
    return null;
  }

  const p = await res.json().catch(() => null);
  if (!p || p.error) {
    toast("Pick failed");
    return null;
  }

  if (p.dest?.code) setSelectValueSafe($("destSelect"), p.dest);

  await applyPlanToIFE(p);

  if (!sessionId && isRealMode() && p.planned_minutes) {
    $("minutes").value = String(p.planned_minutes);
    updateMinutesLock();
  }

  toast("Route picked");
  return p;
}

/* Main UI update */
function updateUI(progress) {
  $("barFill").style.width = `${Math.min(100, Math.max(0, progress * 100))}%`;

  $("altitude").textContent = altitude;
  $("turb").textContent = turbulence;
  $("distCount").textContent = distCount;

  updateGrade();

  const sky = $("sky");
  const planeEl = $("plane");
  const trail = $("trail");

  const w = sky.clientWidth;
  const left = 18 + (w - 90) * progress;

  const topMin = 52;
  const topMax = 190;
  const t = 1 - ((altitude - 40) / 60);
  let top = topMin + (topMax - topMin) * Math.max(0, Math.min(1, t));

  const jig = Math.min(10, Math.floor(turbulence / 12));
  top += jig ? (Math.sin(Date.now() / 70) * jig) : 0;

  planeEl.style.left = `${left}px`;
  planeEl.style.top = `${top}px`;

  const tilt = (progress < 0.12) ? -10 : (progress > 0.88 ? 10 : 0);
  const turTilt = Math.max(-8, Math.min(8, (turbulence / 18)));
  planeEl.style.transform = `rotate(${tilt + turTilt}deg)`;

  trail.style.top = `${top + 22}px`;
  trail.style.width = `${Math.max(0, left - 10)}px`;

  altSeries.push(altitude);
  turbSeries.push(turbulence);
  if (altSeries.length > 120) altSeries.shift();
  if (turbSeries.length > 120) turbSeries.shift();

  drawSeries("altChart", altSeries, "altLabel", 110);
  drawSeries("turbChart", turbSeries, "turbLabel", 110);

  updateIFEProgress(progress);
}

/* Autopilot checkpoints */
async function loadCheckpoints() {
  const res = await fetch(`/api/session/${sessionId}/checkpoints`);
  if (!res.ok) return;
  const data = await res.json();
  checkpoints = data.items || [];
  nextCheckpointIdx = 0;
  pendingCheckpointId = null;
}

function showCheckpointModal(checkpointId) {
  pendingCheckpointId = checkpointId;
  $("checkpointNote").value = "";
  $("checkpointModal").classList.add("show");
  $("checkpointModal").setAttribute("aria-hidden", "false");
  toast("Checkpoint");
}

function hideCheckpointModal() {
  $("checkpointModal").classList.remove("show");
  $("checkpointModal").setAttribute("aria-hidden", "true");
  pendingCheckpointId = null;
}

async function completeCheckpointNow() {
  if (!pendingCheckpointId) return;
  const note = $("checkpointNote").value.trim();
  await fetch("/api/checkpoint/complete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ checkpoint_id: pendingCheckpointId, note })
  });
  addLog(note ? `Checkpoint done: ${note}` : "Checkpoint done");
  hideCheckpointModal();
}

function maybeTriggerCheckpoint(elapsedSeconds) {
  while (nextCheckpointIdx < checkpoints.length) {
    const cp = checkpoints[nextCheckpointIdx];
    if (cp.completed_at) {
      nextCheckpointIdx += 1;
      continue;
    }
    if (elapsedSeconds >= cp.due_seconds) {
      showCheckpointModal(cp.id);
      nextCheckpointIdx += 1;
      return;
    }
    break;
  }
}

function tick() {
  if (!sessionId || paused) return;

  const now = Date.now();
  const elapsed = elapsedBeforePause + Math.floor((now - startMs) / 1000);
  const left = plannedSeconds - elapsed;

  $("timeLeft").textContent = fmtTime(left);

  const progress = Math.min(1, elapsed / plannedSeconds);
  updateUI(progress);

  maybeTriggerCheckpoint(elapsed);

  if (left <= 0) {
    addLog("Landing complete. Ending flight.");
    endFlight();
  }
}

async function refreshHistory() {
  const res = await fetch("/api/sessions/recent?limit=10");
  if (!res.ok) return;
  const data = await res.json();
  renderRecent(data.items || []);
}

function renderRecent(items) {
  const root = $("recentCards");
  root.innerHTML = "";

  if (!items.length) {
    root.innerHTML = `<div class="muted mini">No finished flights yet</div>`;
    return;
  }

  for (const s of items) {
    const card = document.createElement("div");
    card.className = "flight-card";

    const g = s.grade || "-";
    const junk = (s.altitude_end ?? 100);
    const tmp = gradeFromAlt(junk);
    const bg = tmp[1];
    const br = tmp[2];

    card.innerHTML = `
      <div class="topline">
        <div>
          <div style="font-weight:720">${escapeHtml(s.subject)}</div>
          <div class="mini muted">${escapeHtml(s.started_at || "")}</div>
        </div>
        <div class="badge" style="background:${bg}; border-color:${br}">Grade ${g}</div>
      </div>
      <div class="mini muted" style="margin-top:8px">
        planned ${s.planned_minutes}m · actual ${Math.round((s.actual_seconds || 0) / 60)}m · distractions ${s.distractions_count} · altitude ${s.altitude_end}
      </div>
    `;
    root.appendChild(card);
  }
}

/* API actions */
async function startFlight() {
  const subject = $("subject").value.trim() || "Study";

  let minutes = parseInt($("minutes").value || "50", 10);

  // harden selects before route calls
  const oFallback = originComboApi?.getSelected?.()?.code || "";
  const dFallback = destComboApi?.getSelected?.()?.code || "";
  const oCode = getSelectValueSafe($("originSelect"), oFallback);
  const dCode = getSelectValueSafe($("destSelect"), dFallback);

  if (oCode) setSelectValueSafe($("originSelect"), { code: oCode, name: oCode });
  if (dCode) setSelectValueSafe($("destSelect"), { code: dCode, name: dCode });

  if (isRealMode()) {
    const p = await loadPlan(minutes);
    if (!p) {
      toast("IFE route failed");
      return;
    }

    if (p.planned_minutes) {
      minutes = parseInt(p.planned_minutes, 10);
      $("minutes").value = String(minutes);
    }

    await applyPlanToIFE(p);
    updateMinutesLock();
  }

  const res = await fetch("/api/session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  
  addLog(`Takeoff: ${subject}, plan ${Math.floor(plannedSeconds / 60)} min, session #${sessionId}`);
  takeoffSound();
  toast("Takeoff");
  startAmbience();
  bumpAmbienceForTakeoff();

  await loadCheckpoints();

  if (!isRealMode()) {
    const freshMinutes = parseInt($("minutes").value || "50", 10);
    await setupIFEForFlight(freshMinutes);
  }

  if (timer) clearInterval(timer);
  timer = setInterval(tick, 250);

  updateUI(0);
}

function togglePause() {
  if (!sessionId) return;

  if (!paused) {
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

async function logDistraction() {
  if (!sessionId) return;

  const note = $("note").value.trim();
  $("note").value = "";

  const res = await fetch("/api/distraction", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, note })
  });
  if (!res.ok) {
    addLog("Failed to log distraction.");
    toast("Log failed");
    return;
  }

  distCount += 1;
  turbulence += 7;
  if (ambienceEnabled()) bumpAmbienceForTurbulence();
  altitude = Math.max(40, altitude - 6);

  addLog(note ? `Turbulence: ${note}` : "Turbulence: distraction logged");
  ding();
  toast("Ding");
}

async function endFlight() {
  if (!sessionId) return;

  let elapsed = elapsedBeforePause;
  if (!paused) elapsed += Math.floor((Date.now() - startMs) / 1000);
  elapsed = Math.max(0, Math.min(plannedSeconds, elapsed));

  await fetch("/api/session/end", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      actual_seconds: elapsed,
      altitude_end: altitude,
      turbulence_end: turbulence
    })
  }).catch(() => null);

  addLog(`Landing. altitude ${altitude} · distractions ${distCount}`);
  stopAmbience();
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
function setCabinMode(on) {
  const enabled = !!on;
  document.body.classList.toggle("cabin-on", enabled);

  const img = ensureMapSnapshotEl();

  if (enabled) {
    updateMapSnapshot();
    if (img) img.style.display = "block";
    setMapLiveVisible(false);
  } else {
    if (img) img.style.display = "none";
    setMapLiveVisible(true);
    if (map) setTimeout(() => { try { map.resize(); } catch { } }, 280);
  }
}

$("cabinToggle")?.addEventListener("change", () => {
  setCabinMode($("cabinToggle").checked);
});

let originComboApi = null;
let destComboApi = null;

$("swapBtn")?.addEventListener("click", async () => {
  if (sessionId) return;

  const oSel = $("originSelect");
  const dSel = $("destSelect");

  const oCode = getSelectValueSafe(oSel, originComboApi?.getSelected?.()?.code);
  const dCode = getSelectValueSafe(dSel, destComboApi?.getSelected?.()?.code);

  if (!oCode || !dCode) return;

  setSelectValueSafe(oSel, { code: dCode, name: dCode });
  setSelectValueSafe(dSel, { code: oCode, name: oCode });

  const newO = await fetchAirportByCode(dCode);
  const newD = await fetchAirportByCode(oCode);

  if (originComboApi) originComboApi.setSelected(newO || { code: dCode, name: dCode });
  if (destComboApi) destComboApi.setSelected(newD || { code: oCode, name: oCode });

  oSel.dispatchEvent(new Event("change", { bubbles: true }));
  dSel.dispatchEvent(new Event("change", { bubbles: true }));
});

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

$("originSelect").addEventListener("change", async () => {
  const minutes = plannedSeconds ? Math.floor(plannedSeconds / 60) : parseInt($("minutes").value || "50", 10);

  if (isRealMode()) {
    const p = await loadPlan(minutes);
    if (p && p.planned_minutes && !sessionId) {
      $("minutes").value = String(p.planned_minutes);
      updateMinutesLock();
    }
    if (p) await applyPlanToIFE(p);
    return;
  }

  await setupIFEForFlight(minutes);
});

$("destSelect").addEventListener("change", async () => {
  const minutes = plannedSeconds ? Math.floor(plannedSeconds / 60) : parseInt($("minutes").value || "50", 10);

  if (isRealMode()) {
    const p = await loadPlan(minutes);
    if (p && p.planned_minutes && !sessionId) {
      $("minutes").value = String(p.planned_minutes);
      updateMinutesLock();
    }
    if (p) await applyPlanToIFE(p);
    return;
  }

  await setupIFEForFlight(minutes);
});

$("pickRouteBtn").addEventListener("click", async () => {
  const minutes = parseInt($("minutes").value || "50", 10);

  const p = await pickRouteForSession(minutes);
  if (p && isRealMode() && p.planned_minutes && !sessionId) {
    $("minutes").value = String(p.planned_minutes);
    updateMinutesLock();
  }
});

if ($("routeMode")) {
  $("routeMode").addEventListener("change", async () => {
    updateMinutesLock();

    const minutes = parseInt($("minutes").value || "50", 10);

    if (isRealMode()) {
      const p = await loadPlan(minutes);
      if (p && p.planned_minutes && !sessionId) {
        $("minutes").value = String(p.planned_minutes);
      }
      if (p) await applyPlanToIFE(p);
      updateMinutesLock();
      return;
    }

    await setupIFEForFlight(minutes);
  });
}

$("view3dToggle").addEventListener("change", () => {
  use3DView = $("view3dToggle").checked;
  applyMapView();
});

$("followToggle").addEventListener("change", () => {
  followPlane = $("followToggle").checked;
});

$("ambientToggle")?.addEventListener("change", () => {
  if ($("ambientToggle").checked) {
    if (sessionId && !paused) startAmbience();
  } else {
    stopAmbience();
  }
});

/* Initial */
(async () => {
  refreshHistory();
  setStatus(false, false);

  use3DView = $("view3dToggle") ? $("view3dToggle").checked : true;
  followPlane = $("followToggle") ? $("followToggle").checked : true;

  originComboApi = createAirportCombobox("origin", "originSelect");
  destComboApi = createAirportCombobox("dest", "destSelect");

  const recents = loadRecents();
  const defaultOrigin = recents[0]?.code || "BER";
  const defaultDest = (recents.find(x => x.code !== defaultOrigin)?.code) || "IST";

  const oA = await fetchAirportByCode(defaultOrigin);
  const dA = await fetchAirportByCode(defaultDest);

  if (oA) {
    originComboApi.setSelected(oA);
    setSelectValueSafe($("originSelect"), oA);
  } else {
    const fb = { code: defaultOrigin, name: defaultOrigin };
    originComboApi.setSelected(fb);
    setSelectValueSafe($("originSelect"), fb);
  }

  if (dA) {
    destComboApi.setSelected(dA);
    setSelectValueSafe($("destSelect"), dA);
  } else {
    const fb = { code: defaultDest, name: defaultDest };
    destComboApi.setSelected(fb);
    setSelectValueSafe($("destSelect"), fb);
  }

  updateMinutesLock();
  setControls(false);

  const minutes = parseInt($("minutes").value || "50", 10);

  if (isRealMode()) {
    const p = await loadPlan(minutes);
    if (p) await applyPlanToIFE(p);
    updateMinutesLock();
    return;
  }

  await setupIFEForFlight(minutes);
})();