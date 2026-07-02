/* viz.js — two-panel canvas + metric timeline + play + contrast plaque (PR-4).
 * The front computes only DERIVED views over the preloaded frames (no sim, no new
 * endpoints). Ownership layers are empty-safe (baseline forever has no owners). */

"use strict";

const runsFor = (w) => ({ baseline: `${w}_baseline`, headline: `${w}_headline` });

/* per-world contrast text (two-register titles adapt to the selected world) */
const WORLD_META = {
  appropriation: {
    left: ["без собственности", "ρ=0"],
    right: ["с собственностью", "ρ=0.5 · перенос тело→тело"],
    sub: "Разница только в одном: слева собственности нет, справа она включена.",
  },
  institution: {
    left: ["собственность, институт выключен", "σ=0"],
    right: ["собственность + институт-страж", "σ=0.5 · налог и стража"],
    sub: "У обоих есть собственность. Справа добавлен институт: владельцев облагают налогом, стража давит вызовы владению.",
  },
  inheritance: {
    left: ["собственность без наследования", "наследование выкл."],
    right: ["собственность + наследование", "клетки переходят наследнику"],
    sub: "У обоих есть собственность. Справа клетки умершего владельца переходят живому наследнику того же дома.",
  },
  trade: {
    left: ["собственность без рынка", "рынок выкл."],
    right: ["собственность + рынок", "богатый выкупает купчие · цена 0.25"],
    sub: "У обоих есть собственность. Справа включён рынок: самый богатый живой агент выкупает купчие у держателей.",
  },
  legitimacy: {
    left: ["формула выключена", "самоцензуры нет"],
    right: ["формула включена", "порог 0.5 · миф давит вызов"],
    sub: "У обоих есть собственность. Справа включена «политическая формула»: легитимность гасит готовность оспорить владение — молчание без налога и стражи.",
  },
};
const CHARTS = [
  { id: "chart-share", key: "ownerShare", pct: true },
  { id: "chart-alive", key: "alive" },
  { id: "chart-mass", key: "sumBody" },
];
const PAD = { l: 34, r: 10, t: 12, b: 16 };

const state = {
  baseline: null, headline: null,
  gridR: 14, gridC: 14, tMin: 1, tMax: 300,
  maxPlant: 1e-9, maxBody: 1e-9,
  layers: { food: true, bodies: true, owner: true, traj: false, flow: false, legit: true },
  speed: 4, playing: false, timer: null, world: "appropriation",
  sweep: null, figTag: "appropriation", sweepWorld: "appropriation", probeMode: false,
};

const $ = (id) => document.getElementById(id);
const setStatus = (m) => { $("status").textContent = m; };

async function getJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

async function loadRun(runName) {
  const meta = await getJSON(`/${runName}/meta`);
  const frames = await getJSON(`/${runName}/frames?t0=${meta.t_min}&t1=${meta.t_max}`);
  const byT = {}, posByT = {};
  for (const f of frames) {
    byT[f.t] = f;
    const m = new Map();
    for (const a of f.agents) m.set(a[0], [a[1], a[2]]);
    posByT[f.t] = m;
  }
  return { meta, frames, byT, posByT, series: buildSeries(frames) };
}

/* A: derive the metric series once, per day */
function buildSeries(frames) {
  const s = { days: [], alive: [], sumBody: [], nOwners: [], ownerShare: [], tribute: [],
    selfcensored: [], succeeded: [] };
  for (const f of frames) {
    const owners = new Set(f.owner_ids || []);
    let sum = 0, ob = 0;
    for (const a of f.agents) { sum += a[3]; if (owners.has(a[0])) ob += a[3]; }
    s.days.push(f.t);
    s.alive.push(f.agents.length);
    s.sumBody.push(sum);
    s.nOwners.push(owners.size);
    s.ownerShare.push(sum > 0 ? ob / sum : 0);
    s.tribute.push(f.appropriated_total || 0);
    s.selfcensored.push(f.selfcensored || 0);      // agenda probe (0 for property worlds)
    s.succeeded.push(f.succeeded || 0);
  }
  return s;
}

function computeScales() {
  state.maxPlant = 1e-9; state.maxBody = 1e-9;     // reset (world switch recomputes from scratch)
  for (const run of [state.baseline, state.headline]) {
    for (const f of run.frames) {
      for (const row of f.plant) for (const v of row) if (v > state.maxPlant) state.maxPlant = v;
      for (const a of f.agents) if (a[3] > state.maxBody) state.maxBody = a[3];
    }
  }
}

const at = (run, key, t) => run.series[key][t - state.tMin];

/* ------------------------------------------------------------------ panels */
function jitter(oid, salt, span) {
  const h = Math.sin(oid * 12.9898 + salt) * 43758.5453;
  return (h - Math.floor(h) - 0.5) * span;
}

function renderFrame(frame, canvas, meta) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height, R = state.gridR, C = state.gridC;
  const cw = W / C, ch = H / R;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#05070a"; ctx.fillRect(0, 0, W, H);

  if (state.layers.food) {
    for (let i = 0; i < R; i++) for (let j = 0; j < C; j++) {
      const v = Math.max(0, Math.min(1, frame.plant[i][j] / state.maxPlant));
      ctx.fillStyle = `rgb(${18 + 10 * v}, ${34 + 172 * v}, ${44 + 20 * v})`;
      ctx.fillRect(j * cw, i * ch, cw + 0.5, ch + 0.5);
    }
  }
  ctx.strokeStyle = "rgba(255,255,255,0.05)"; ctx.lineWidth = 1;
  for (let k = 0; k <= C; k++) { ctx.beginPath(); ctx.moveTo(k * cw, 0); ctx.lineTo(k * cw, H); ctx.stroke(); }
  for (let k = 0; k <= R; k++) { ctx.beginPath(); ctx.moveTo(0, k * ch); ctx.lineTo(W, k * ch); ctx.stroke(); }

  if (state.layers.food && meta && meta.oases) {
    ctx.strokeStyle = "rgba(120,220,140,0.45)"; ctx.lineWidth = 1.5;
    for (const [i, j] of meta.oases) ctx.strokeRect(j * cw + 1.5, i * ch + 1.5, cw - 3, ch - 3);
  }

  // agenda "silence" layer: the myth map (legit_cells) — slate overlay ∝ legitimacy weight.
  // Empty-safe: property worlds have no legit_cells, so this simply does not draw.
  const lc = frame.legit_cells;
  if (state.layers.legit && lc && lc.length) {
    let mw = 0; for (const c of lc) if (c[2] > mw) mw = c[2];
    for (const [i, j, wt] of lc) {
      const a = 0.10 + 0.55 * (mw > 0 ? wt / mw : 0);
      ctx.fillStyle = `rgba(109,134,168,${a})`;
      ctx.fillRect(j * cw, i * ch, cw, ch);
    }
  }

  const cellOwner = frame.cell_owner || {};
  if (state.layers.owner && Object.keys(cellOwner).length) {
    ctx.strokeStyle = "rgba(244,197,66,0.55)"; ctx.lineWidth = 2;
    for (const key of Object.keys(cellOwner)) {
      const [i, j] = key.split(",").map(Number);
      ctx.strokeRect(j * cw + 0.5, i * ch + 0.5, cw - 1, ch - 1);
    }
  }

  const ownerSet = new Set(frame.owner_ids || []);
  if (state.layers.traj && ownerSet.size) {
    const run = canvas.id.endsWith("headline") ? state.headline : state.baseline;
    ctx.strokeStyle = "rgba(244,197,66,0.20)"; ctx.lineWidth = 1.25;
    for (const oid of ownerSet) {
      ctx.beginPath(); let started = false;
      for (let t = state.tMin; t <= frame.t; t++) {
        const p = run.posByT[t] && run.posByT[t].get(oid);
        if (!p) continue;
        const x = (p[1] + 0.5) * cw, y = (p[0] + 0.5) * ch;
        if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
      }
      if (started) ctx.stroke();
    }
  }

  if (state.layers.bodies) {
    for (const a of frame.agents) {
      const oid = a[0], i = a[1], j = a[2], body = a[3], isOwner = ownerSet.has(oid);
      const cx = (j + 0.5) * cw + jitter(oid, 0.0, cw * 0.5);
      const cy = (i + 0.5) * ch + jitter(oid, 3.1, ch * 0.5);
      const r = Math.max(1.4, 0.42 * cw * Math.sqrt(body / state.maxBody));
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = isOwner ? "rgba(244,197,66,0.92)" : "rgba(108,176,234,0.78)";
      ctx.fill();
      if (isOwner) { ctx.lineWidth = 1.5; ctx.strokeStyle = "#f4c542"; ctx.stroke(); }
    }
  }

  // turnover flow: green flash on births, red flash on deaths (this snapped day)
  if (state.layers.flow) {
    const flash = (i, j, color) => {
      ctx.beginPath(); ctx.arc((j + 0.5) * cw, (i + 0.5) * ch, cw * 0.42, 0, Math.PI * 2);
      ctx.fillStyle = color; ctx.fill();
    };
    for (const b of (frame.births || [])) flash(b[1], b[2], "rgba(60,230,110,0.55)");  // [oid,i,j]
    for (const d of (frame.deaths || [])) flash(d[0], d[1], "rgba(240,70,70,0.50)");   // [i,j]
  }
}

function readout(frame, elId) {
  const owners = new Set(frame.owner_ids || []);
  let sumBody = 0, ownerBody = 0;
  for (const a of frame.agents) { sumBody += a[3]; if (owners.has(a[0])) ownerBody += a[3]; }
  const share = sumBody > 0 ? ownerBody / sumBody : 0;
  $(elId).innerHTML =
    `<span>сколько живых <b>${frame.agents.length}</b></span>` +
    `<span>всего массы <b>${sumBody.toFixed(1)}</b> кг</span>` +
    `<span>владельцев <b>${owners.size}</b></span>` +
    `<span class="gold">доля богатства <b>${share.toFixed(3)}</b></span>` +
    `<span>отобрано <b>${(frame.appropriated_total || 0).toFixed(0)}</b> кг</span>`;
}

/* --------------------------------------------------------------- A: charts */
function chartGeom(cv) { return { W: cv.width, H: cv.height, iw: cv.width - PAD.l - PAD.r, ih: cv.height - PAD.t - PAD.b }; }
function xAt(g, day) { return PAD.l + (day - state.tMin) / (state.tMax - state.tMin) * g.iw; }
function yAt(g, v, yMax) { return PAD.t + g.ih - (yMax > 0 ? v / yMax : 0) * g.ih; }

function drawChart(cv, key, t, pct) {
  const ctx = cv.getContext("2d"), g = chartGeom(cv);
  ctx.clearRect(0, 0, g.W, g.H);
  const bs = state.baseline.series[key], hs = state.headline.series[key];
  let yMax = 0; for (const v of bs) if (v > yMax) yMax = v; for (const v of hs) if (v > yMax) yMax = v;
  yMax = yMax > 0 ? yMax * 1.1 : 1;

  // axes: 0 and max ticks
  ctx.strokeStyle = "rgba(255,255,255,0.08)"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(PAD.l, yAt(g, 0, yMax)); ctx.lineTo(g.W - PAD.r, yAt(g, 0, yMax)); ctx.stroke();
  ctx.fillStyle = "#6a7681"; ctx.font = "10px sans-serif"; ctx.textAlign = "right";
  const lab = (v) => pct ? Math.round(v * 100) + "%" : (v >= 100 ? Math.round(v) : v.toFixed(1));
  ctx.fillText(lab(yMax / 1.1), PAD.l - 4, PAD.t + 8);
  ctx.fillText(lab(0), PAD.l - 4, yAt(g, 0, yMax) - 1);

  const line = (arr, color, w) => {
    ctx.strokeStyle = color; ctx.lineWidth = w; ctx.beginPath();
    for (let i = 0; i < arr.length; i++) {
      const x = xAt(g, state.tMin + i), y = yAt(g, arr[i], yMax);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.stroke();
  };
  line(bs, "#6cb0ea", 1.6);
  line(hs, "#f4c542", 2);

  // current-day marker
  const mx = xAt(g, t);
  ctx.strokeStyle = "rgba(255,255,255,0.35)"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(mx, PAD.t); ctx.lineTo(mx, PAD.t + g.ih); ctx.stroke();
  const i = t - state.tMin;
  for (const [arr, c] of [[bs, "#6cb0ea"], [hs, "#f4c542"]]) {
    ctx.fillStyle = c; ctx.beginPath(); ctx.arc(mx, yAt(g, arr[i], yMax), 3, 0, Math.PI * 2); ctx.fill();
  }
}

function drawCharts(t) { for (const c of CHARTS) drawChart($(c.id), c.key, t, c.pct); }

/* ------------------------------------------------------- C: plaque + summary */
function fmtPct(from, to) {
  if (!from) return "";
  const d = (to - from) / from * 100;
  return (d >= 0 ? "+" : "") + Math.round(d) + "%";
}
function block(k, left, right, pct, cls) {
  return `<span class="k">${k}</span><span class="v"><span class="a">${left}</span>`
    + `<span class="arw">→</span><span class="b ${cls}">${right}</span>`
    + (pct ? `<span class="pct ${cls}">${pct}</span>` : "") + `</span>`;
}

function updatePlaque(t) {
  if (state.probeMode) return updateProbePlaque(t);
  const bA = at(state.baseline, "alive", t), hA = at(state.headline, "alive", t);
  const bM = at(state.baseline, "sumBody", t), hM = at(state.headline, "sumBody", t);
  const bS = at(state.baseline, "ownerShare", t), hS = at(state.headline, "ownerShare", t);
  $("plq-alive").innerHTML = block("сколько живых", bA, hA, fmtPct(bA, hA), "warn");
  $("plq-mass").innerHTML = block("всего живой массы", bM.toFixed(0) + " кг", hM.toFixed(0) + " кг", fmtPct(bM, hM), "warn");
  $("plq-share").innerHTML = block("доля у владельцев",
    Math.round(bS * 100) + "%", Math.round(hS * 100) + "%", "", "gold");
}

function updateProbePlaque(t) {
  // probe axis: silence (self-censored), capacity intact, and share DILUTED (no stratum)
  const bC = at(state.baseline, "selfcensored", t), hC = at(state.headline, "selfcensored", t);
  const bA = at(state.baseline, "alive", t), hA = at(state.headline, "alive", t);
  const bS = at(state.baseline, "ownerShare", t), hS = at(state.headline, "ownerShare", t);
  $("plq-alive").innerHTML = block("подавлено вызовов", bC, hC, "", "gold");
  $("plq-mass").innerHTML = block("живых (без цены базы)", bA, hA, fmtPct(bA, hA), "gold");
  $("plq-share").innerHTML = block("доля у владельцев (не строит страту)",
    Math.round(bS * 100) + "%", Math.round(hS * 100) + "%", "", "warn");
}

function updateSummary(t) {
  if (state.probeMode) {
    const hC = at(state.headline, "selfcensored", t), hA = at(state.headline, "alive", t);
    const bS = at(state.baseline, "ownerShare", t), hS = at(state.headline, "ownerShare", t);
    $("summary").textContent =
      `День ${t}: формула подавила ${hC} вызовов, живых ${hA} (ёмкость цела — без налога). ` +
      `Владельцы держат ${Math.round(hS * 100)}% массы — не выше базы ${Math.round(bS * 100)}%: молчание, не страта.`;
    return;
  }
  const bA = at(state.baseline, "alive", t);
  const hO = at(state.headline, "nOwners", t), hS = at(state.headline, "ownerShare", t), hA = at(state.headline, "alive", t);
  $("summary").textContent =
    `День ${t}: слева никто не владеет, живых ${bA}. ` +
    `Справа ${hO} владельцев держат ${Math.round(hS * 100)}% массы, живых осталось ${hA}.`;
}

/* -------------------------------------------------------------------- draw */
function draw(t) {
  if (!state.baseline || !state.headline) return;   // not loaded yet
  $("day").textContent = t;
  renderFrame(state.baseline.byT[t], $("cv-baseline"), state.baseline.meta);
  renderFrame(state.headline.byT[t], $("cv-headline"), state.headline.meta);
  readout(state.baseline.byT[t], "ro-baseline");
  readout(state.headline.byT[t], "ro-headline");
  updatePlaque(t);
  updateSummary(t);
  drawCharts(t);
  if (state.probeMode) drawChart($("chart-censor"), "selfcensored", t);   // silence timeline
}

/* ----------------------------------------------------------------- B: play */
/* setInterval (not rAF) so autoplay keeps advancing even when the tab is hidden;
 * step = one day per tick, interval = 1000/speed ms (speed = days per second). */
function stopPlay() {
  state.playing = false;
  if (state.timer) { clearInterval(state.timer); state.timer = null; }
  $("play").textContent = "▶";
}
function scheduleTimer() {
  if (state.timer) clearInterval(state.timer);
  state.timer = setInterval(() => {
    const s = $("scrub");
    const cur = parseInt(s.value, 10) + 1;
    if (cur >= state.tMax) { s.value = state.tMax; draw(state.tMax); stopPlay(); return; }
    s.value = cur; draw(cur);
  }, Math.max(30, 1000 / state.speed));
}
function startPlay() {
  const s = $("scrub");
  if (parseInt(s.value, 10) >= state.tMax) s.value = state.tMin;
  state.playing = true; $("play").textContent = "⏸";
  scheduleTimer();
}

/* --------------------------------------------------------------- controls */
function showTip(cv, key, e) {
  const g = chartGeom(cv), rect = cv.getBoundingClientRect();
  const px = (e.clientX - rect.left) / rect.width * cv.width;
  let day = Math.round(state.tMin + (px - PAD.l) / g.iw * (state.tMax - state.tMin));
  day = Math.max(state.tMin, Math.min(state.tMax, day));
  const b = at(state.baseline, key, day), h = at(state.headline, key, day);
  const fmt = (v) => key === "ownerShare" ? Math.round(v * 100) + "%" : (v >= 100 ? Math.round(v) : v.toFixed(1));
  const tip = $("tip");
  tip.innerHTML = `день ${day}<br><span class="a">без: ${fmt(b)}</span> · <span class="b">с: ${fmt(h)}</span>`;
  tip.style.left = (e.clientX + 12) + "px"; tip.style.top = (e.clientY + 12) + "px"; tip.hidden = false;
}

function wireControls() {
  const scrub = $("scrub");
  scrub.min = state.tMin; scrub.max = state.tMax; scrub.value = state.tMin;
  scrub.addEventListener("input", () => { stopPlay(); draw(parseInt(scrub.value, 10)); });

  $("play").addEventListener("click", () => state.playing ? stopPlay() : startPlay());
  const sp = $("speed");
  sp.addEventListener("input", () => {
    state.speed = parseInt(sp.value, 10); $("speed-val").textContent = state.speed + "×";
    if (state.playing) scheduleTimer();          // apply new speed immediately
  });

  const map = { "ly-food": "food", "ly-bodies": "bodies", "ly-owner": "owner", "ly-traj": "traj", "ly-flow": "flow", "ly-legit": "legit" };
  for (const [id, k] of Object.entries(map)) {
    $(id).addEventListener("change", (e) => { state.layers[k] = e.target.checked; draw(parseInt(scrub.value, 10)); });
  }

  $("world").addEventListener("change", (e) => { stopPlay(); loadWorld(e.target.value); });

  // PR-31: sandbox + sweep + export
  $("sb-rho").addEventListener("input", (e) => { $("sb-rho-val").textContent = (+e.target.value).toFixed(1); });
  $("sb-run").addEventListener("click", sbRun);
  $("sb-sweep").addEventListener("click", sbSweep);
  $("ex-fig").addEventListener("click", exportFigure);
  $("ex-sweep").addEventListener("click", exportSweep);
  $("fig-mode").addEventListener("change", (e) => document.body.classList.toggle("figure-mode", e.target.checked));
  const swcv = $("sweep");
  swcv.addEventListener("mousemove", (e) => showSweepTip(e));
  swcv.addEventListener("mouseleave", () => { $("sweep-tip").hidden = true; });

  const help = $("help-btn"), legend = $("legend");
  help.addEventListener("click", () => {
    legend.hidden = !legend.hidden;
    help.setAttribute("aria-expanded", String(!legend.hidden));
  });

  for (const c of CHARTS) {
    const cv = $(c.id);
    cv.addEventListener("mousemove", (e) => showTip(cv, c.key, e));
    cv.addEventListener("mouseleave", () => { $("tip").hidden = true; });
  }
}

/* ------------------------------------------------- PR-31: live sandbox + sweep */
function setSbStatus(m, err) {
  const el = $("sb-status"); el.textContent = m; el.classList.toggle("err", !!err);
}

async function fetchRun(w, rho, seed, arena, verb) {
  const u = `/run?world=${w}&rho=${rho}&seed=${seed}&arena=${arena}&verb=${verb}`;
  const r = await fetch(u);
  if (!r.ok) { const j = await r.json().catch(() => ({ detail: r.status })); throw new Error(j.detail || r.status); }
  return r.json();
}

function runFromLive(resp) {
  const frames = resp.frames, byT = {}, posByT = {};
  for (const f of frames) {
    byT[f.t] = f;
    const m = new Map(); for (const a of f.agents) m.set(a[0], [a[1], a[2]]);
    posByT[f.t] = m;
  }
  const meta = Object.assign({}, resp.meta, { t_min: resp.t_min, t_max: resp.t_max });
  return { meta, frames, byT, posByT, series: buildSeries(frames) };
}

function setLiveTitles(w, rho, seed, arena, verbOn) {
  const wm = WORLD_META[w];
  const probe = w === "legitimacy";
  const doseName = probe ? "порог" : "ρ";
  $("left-title").textContent = probe ? "формула выключена" : "контроль (механизм выкл)";
  $("left-cfg").textContent = "";
  $("right-title").textContent = verbOn ? (wm ? wm.right[0] : w) : "контроль";
  $("right-cfg").textContent = `живой прогон · ${doseName}=${(+rho).toFixed(1)}`;
  $("contrast-sub").textContent =
    `Живой прогон «${w}»: сид ${seed}, арена ${arena || "открытая"}. ` +
    `Слева контроль, справа механизм при ${doseName}=${(+rho).toFixed(1)} — посчитано на бэке под 4-гейтом.`;
  $("world-hint").textContent = "живой прогон (гейт-защищён)";
}

async function sbRun() {
  const w = $("sb-world").value, rho = $("sb-rho").value, seed = $("sb-seed").value,
    arena = $("sb-arena").value, verbOn = $("sb-verb").checked;
  stopPlay();
  setSbStatus("гоняю живой прогон… (4 гейта: B0 · reproducibility · snapshot-safe)");
  try {
    const [lo, hi] = await Promise.all([
      fetchRun(w, rho, seed, arena, "off"),                 // left = control
      fetchRun(w, rho, seed, arena, verbOn ? "on" : "off"), // right = mechanism (or control)
    ]);
    state.baseline = runFromLive(lo); state.headline = runFromLive(hi);
    state.world = "__live__"; state.figTag = `live_${w}_r${(+rho).toFixed(1)}_s${seed}`;
    const m = state.headline.meta;
    state.gridR = m.R || 14; state.gridC = m.C || 14; state.tMin = hi.t_min; state.tMax = hi.t_max;
    computeScales();
    applyProbeUI(w === "legitimacy");
    setLiveTitles(w, rho, seed, arena, verbOn);
    const scrub = $("scrub"); scrub.min = state.tMin; scrub.max = state.tMax; scrub.value = state.tMin;
    draw(state.tMin);
    setSbStatus(`готово · гейт ✓ · B0 ${hi.b0_fp} (канон) · safe ${hi.safe_fp}`);
  } catch (err) {
    setSbStatus("ГЕЙТ КРАСНЫЙ / ошибка: " + err.message, true);
    console.error(err);
  }
}

async function sbSweep() {
  const w = $("sb-world").value, seed = $("sb-seed").value, arena = $("sb-arena").value;
  setSbStatus("свип по ρ… (гейт на каждой точке; rho=0 — встроенный контроль)");
  try {
    const r = await fetch(`/sweep?world=${w}&seed=${seed}&arena=${arena}&rhos=0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0`);
    if (!r.ok) { const j = await r.json().catch(() => ({})); throw new Error(j.detail || r.status); }
    const data = await r.json();
    state.sweep = data.points; state.sweepWorld = w;
    $("sweep-wrap").hidden = false;
    drawSweep(data.points);
    $("sweep-wrap").scrollIntoView({ behavior: "smooth", block: "nearest" });
    setSbStatus(`свип готов · ${data.points.length} точек ρ (гейт ✓ на каждой)`);
  } catch (err) {
    setSbStatus("свип — ГЕЙТ КРАСНЫЙ / ошибка: " + err.message, true);
    console.error(err);
  }
}

const SW_PAD = { l: 38, r: 12, t: 12, b: 26 };
const SWEEP_LEGEND = {
  property: '<span class="ln headline">— доля богатства (owner share)</span>'
    + '<span class="ln baseline">— живых (alive)</span>'
    + '<span class="ln birth">— рождений (оборот↑)</span><span class="ln death">— смертей (оборот↓)</span>',
  legitimacy: '<span class="ln" style="color:#6d86a8">— подавлено вызовов (self-censored)</span>'
    + '<span class="ln baseline">— живых (alive · база цела)</span>'
    + '<span class="ln death">— переворотов владения (succeeded)</span>',
};
function drawSweep(points) {
  const probe = state.sweepWorld === "legitimacy";
  $("sweep-legend").innerHTML = probe ? SWEEP_LEGEND.legitimacy : SWEEP_LEGEND.property;
  const cv = $("sweep"), ctx = cv.getContext("2d");
  const W = cv.width, H = cv.height, iw = W - SW_PAD.l - SW_PAD.r, ih = H - SW_PAD.t - SW_PAD.b;
  ctx.clearRect(0, 0, W, H);
  const xs = points.map(p => p.rho), xmin = Math.min(...xs), xmax = Math.max(...xs);
  const X = r => SW_PAD.l + (xmax > xmin ? (r - xmin) / (xmax - xmin) : 0) * iw;
  const Y = v => SW_PAD.t + ih - Math.max(0, Math.min(1, v)) * ih;
  const maxAlive = Math.max(1, ...points.map(p => p.alive));
  const maxTurn = Math.max(1, ...points.map(p => Math.max(p.births_total, p.deaths_total)));
  const maxCensor = Math.max(1, ...points.map(p => p.selfcensored || 0));
  const maxSucc = Math.max(1, ...points.map(p => p.succeeded || 0));

  ctx.strokeStyle = "rgba(255,255,255,0.08)"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(SW_PAD.l, Y(0)); ctx.lineTo(W - SW_PAD.r, Y(0)); ctx.stroke();
  ctx.fillStyle = "#6a7681"; ctx.font = "10px sans-serif";
  ctx.textAlign = "right"; ctx.fillText("1.0", SW_PAD.l - 4, SW_PAD.t + 8); ctx.fillText("0", SW_PAD.l - 4, Y(0));
  ctx.textAlign = "center";
  for (const r of xs) ctx.fillText(r.toFixed(1), X(r), H - 10);
  ctx.textAlign = "left"; ctx.fillText(probe ? "порог легитимации →" : "ρ (доза) →", SW_PAD.l, H - 2);

  const series = probe ? [
    [p => (p.selfcensored || 0) / maxCensor, "#6d86a8"],   // silence
    [p => p.alive / maxAlive, "#6cb0ea"],                  // capacity (flat-high)
    [p => (p.succeeded || 0) / maxSucc, "#f04646"],        // challenges that survived
  ] : [
    [p => (p.owner_share || 0), "#f4c542"],      // absolute 0..1
    [p => p.alive / maxAlive, "#6cb0ea"],
    [p => p.births_total / maxTurn, "#3ce66e"],
    [p => p.deaths_total / maxTurn, "#f04646"],
  ];
  for (const [nf, c] of series) {
    ctx.strokeStyle = c; ctx.lineWidth = 2; ctx.beginPath();
    points.forEach((p, i) => { const x = X(p.rho), y = Y(nf(p)); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
    ctx.stroke();
    ctx.fillStyle = c;
    for (const p of points) { ctx.beginPath(); ctx.arc(X(p.rho), Y(nf(p)), 3, 0, Math.PI * 2); ctx.fill(); }
  }
}

function showSweepTip(e) {
  if (!state.sweep) return;
  const cv = $("sweep"), rect = cv.getBoundingClientRect();
  const px = (e.clientX - rect.left) / rect.width * cv.width;
  const iw = cv.width - SW_PAD.l - SW_PAD.r;
  const xs = state.sweep.map(p => p.rho), xmin = Math.min(...xs), xmax = Math.max(...xs);
  const rho = xmin + (px - SW_PAD.l) / iw * (xmax - xmin);
  let best = state.sweep[0], bd = Infinity;
  for (const p of state.sweep) { const d = Math.abs(p.rho - rho); if (d < bd) { bd = d; best = p; } }
  const tip = $("sweep-tip");
  if (state.sweepWorld === "legitimacy") {
    tip.innerHTML = `порог=${best.rho.toFixed(2)}<br>подавлено ${best.selfcensored || 0} · <span class="a">живых ${best.alive}</span>`
      + `<br>переворотов ${best.succeeded || 0}`;
  } else {
    tip.innerHTML = `ρ=${best.rho.toFixed(1)}<br><span class="b">доля ${(best.owner_share || 0).toFixed(3)}</span> · <span class="a">живых ${best.alive}</span>`
      + `<br>рожд ${best.births_total} · смерт ${best.deaths_total}`;
  }
  tip.style.left = (e.clientX + 12) + "px"; tip.style.top = (e.clientY + 12) + "px"; tip.hidden = false;
}

/* ------------------------------------------------------- PR-31: PNG export */
function download(dataURL, name) {
  const a = document.createElement("a"); a.href = dataURL; a.download = name; a.click();
}
function exportFigure() {
  const bl = $("cv-baseline"), hl = $("cv-headline"); if (!bl.width) return;
  const pad = 18, gap = 18, headH = 60;
  const W = pad * 2 + bl.width + gap + hl.width, H = headH + Math.max(bl.height, hl.height) + pad;
  const off = document.createElement("canvas"); off.width = W; off.height = H;
  const x = off.getContext("2d");
  x.fillStyle = "#0c0f12"; x.fillRect(0, 0, W, H);
  x.fillStyle = "#d8e0e6"; x.font = "bold 16px sans-serif";
  x.fillText(`Noether · день ${$("day").textContent}/${state.tMax}`, pad, 22);
  x.font = "13px sans-serif"; x.fillStyle = "#8a97a2";
  x.fillText($("plq-share").textContent.replace(/\s+/g, " "), pad, 42);
  x.font = "12px sans-serif"; x.fillStyle = "#8a97a2";
  x.fillText("Мир " + $("left-title").textContent, pad, headH - 6);
  x.fillText("Мир " + $("right-title").textContent, pad + bl.width + gap, headH - 6);
  x.drawImage(bl, pad, headH); x.drawImage(hl, pad + bl.width + gap, headH);
  download(off.toDataURL("image/png"), `noether_${state.figTag}_t${$("day").textContent}.png`);
}
function exportSweep() {
  download($("sweep").toDataURL("image/png"), `noether_sweep_${state.sweepWorld}.png`);
}

/* ------------------------------------------------------------- world switch */
function applyProbeUI(on) {
  state.probeMode = on;
  $("ly-legit-wrap").hidden = !on;
  $("probe-note").hidden = !on;
  $("chart-censor-wrap").hidden = !on;
}

function applyWorldMeta(w) {
  const wm = WORLD_META[w]; if (!wm) return;
  $("left-title").textContent = wm.left[0]; $("left-cfg").textContent = wm.left[1];
  $("right-title").textContent = wm.right[0]; $("right-cfg").textContent = wm.right[1];
  $("contrast-sub").textContent = wm.sub;
  $("world-hint").textContent = "слева — контроль, справа — тот же мир с включённым механизмом";
}

async function loadWorld(w) {
  try {
    state.world = w; state.figTag = w;
    const r = runsFor(w);
    setStatus(`загрузка «${w}»…`);
    const [bl, hl] = await Promise.all([loadRun(r.baseline), loadRun(r.headline)]);
    state.baseline = bl; state.headline = hl;
    const m = hl.meta;
    state.gridR = m.R || 14; state.gridC = m.C || 14; state.tMin = m.t_min; state.tMax = m.t_max;
    computeScales();
    applyWorldMeta(w);
    applyProbeUI(w === "legitimacy");
    const scrub = $("scrub");
    scrub.min = state.tMin; scrub.max = state.tMax; scrub.value = state.tMin;
    draw(state.tMin);
    setStatus(`готово — «${w}», по ${hl.frames.length} кадра на прогон, дни ${state.tMin}–${state.tMax}. ` +
      `Тяни ползунок или жми ▶; переключай мир в списке выше.`);
  } catch (err) {
    setStatus(`ошибка загрузки «${w}»: ${err.message} — прогонял ли ты capture.py для этого мира?`);
    console.error(err);
  }
}

/* -------------------------------------------------------------------- main */
async function main() {
  wireControls();
  await loadWorld($("world").value || state.world);
}

main();
