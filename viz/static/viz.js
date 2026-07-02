/* viz.js — two-panel synchronous canvas over the read-only backend (PR-3, beta-front).
 * The front computes nothing over the sim: it fetches captured frames and draws them.
 * Ownership layers are empty-safe (baseline forever has cell_owner={}, owner_ids=[]). */

"use strict";

const BASE_URL = "";                       // same origin (served by FastAPI)
const RUNS = { baseline: "appropriation_baseline", headline: "appropriation_headline" };

const state = {
  baseline: null,   // {meta, frames[], byT{}, posByT[]}
  headline: null,
  gridR: 14, gridC: 14,
  tMin: 1, tMax: 300,
  maxPlant: 1e-9, maxBody: 1e-9,
  layers: { food: true, bodies: true, owner: true, traj: false },
};

const $ = (id) => document.getElementById(id);
const setStatus = (m) => { $("status").textContent = m; };

async function getJSON(path) {
  const r = await fetch(BASE_URL + path);
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

async function loadRun(runName) {
  const meta = await getJSON(`/${runName}/meta`);
  const frames = await getJSON(`/${runName}/frames?t0=${meta.t_min}&t1=${meta.t_max}`);
  const byT = {};
  const posByT = {};                       // t -> Map(oid -> [i,j]) for trajectories
  for (const f of frames) {
    byT[f.t] = f;
    const m = new Map();
    for (const a of f.agents) m.set(a[0], [a[1], a[2]]);
    posByT[f.t] = m;
  }
  return { meta, frames, byT, posByT };
}

function computeScales() {
  for (const run of [state.baseline, state.headline]) {
    if (!run) continue;
    for (const f of run.frames) {
      for (const row of f.plant) for (const v of row) if (v > state.maxPlant) state.maxPlant = v;
      for (const a of f.agents) if (a[3] > state.maxBody) state.maxBody = a[3];
    }
  }
}

/* deterministic per-oid jitter so co-located agents cluster instead of overlapping */
function jitter(oid, salt, span) {
  const h = Math.sin(oid * 12.9898 + salt) * 43758.5453;
  return (h - Math.floor(h) - 0.5) * span;
}

function renderFrame(frame, canvas, meta) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const R = state.gridR, C = state.gridC;
  const cw = W / C, ch = H / R;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#05070a";
  ctx.fillRect(0, 0, W, H);

  // --- food layer: per-cell green heat -------------------------------------
  if (state.layers.food) {
    for (let i = 0; i < R; i++) {
      for (let j = 0; j < C; j++) {
        const v = Math.max(0, Math.min(1, frame.plant[i][j] / state.maxPlant));
        ctx.fillStyle = `rgb(${18 + 10 * v}, ${34 + 172 * v}, ${44 + 20 * v})`;
        ctx.fillRect(j * cw, i * ch, cw + 0.5, ch + 0.5);
      }
    }
  }
  // faint grid
  ctx.strokeStyle = "rgba(255,255,255,0.05)";
  ctx.lineWidth = 1;
  for (let k = 0; k <= C; k++) { ctx.beginPath(); ctx.moveTo(k * cw, 0); ctx.lineTo(k * cw, H); ctx.stroke(); }
  for (let k = 0; k <= R; k++) { ctx.beginPath(); ctx.moveTo(0, k * ch); ctx.lineTo(W, k * ch); ctx.stroke(); }

  // --- oasis layer: static hint from meta (final-epoch oases) ---------------
  if (state.layers.food && meta && meta.oases) {
    ctx.strokeStyle = "rgba(120,220,140,0.45)";
    ctx.lineWidth = 1.5;
    for (const [i, j] of meta.oases) ctx.strokeRect(j * cw + 1.5, i * ch + 1.5, cw - 3, ch - 3);
  }

  // --- ownership (cells) — empty-safe: baseline draws nothing ---------------
  const cellOwner = frame.cell_owner || {};
  if (state.layers.owner && Object.keys(cellOwner).length) {
    ctx.strokeStyle = "rgba(244,197,66,0.55)";
    ctx.lineWidth = 2;
    for (const key of Object.keys(cellOwner)) {
      const [i, j] = key.split(",").map(Number);
      ctx.strokeRect(j * cw + 0.5, i * ch + 0.5, cw - 1, ch - 1);
    }
  }

  // --- trajectories (optional): owners' paths up to t -----------------------
  const ownerSet = new Set(frame.owner_ids || []);
  if (state.layers.traj && ownerSet.size) {
    const run = canvas.id.endsWith("headline") ? state.headline : state.baseline;
    ctx.strokeStyle = "rgba(244,197,66,0.20)";
    ctx.lineWidth = 1.25;
    for (const oid of ownerSet) {
      ctx.beginPath();
      let started = false;
      for (let t = state.tMin; t <= frame.t; t++) {
        const p = run.posByT[t] && run.posByT[t].get(oid);
        if (!p) continue;
        const x = (p[1] + 0.5) * cw, y = (p[0] + 0.5) * ch;
        if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
      }
      if (started) ctx.stroke();
    }
  }

  // --- bodies: circle, area ∝ body (radius ∝ sqrt(body)) --------------------
  if (state.layers.bodies) {
    for (const a of frame.agents) {
      const oid = a[0], i = a[1], j = a[2], body = a[3];
      const isOwner = ownerSet.has(oid);
      const cx = (j + 0.5) * cw + jitter(oid, 0.0, cw * 0.5);
      const cy = (i + 0.5) * ch + jitter(oid, 3.1, ch * 0.5);
      const r = Math.max(1.4, 0.42 * cw * Math.sqrt(body / state.maxBody));
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = isOwner ? "rgba(244,197,66,0.92)" : "rgba(120,180,235,0.78)";
      ctx.fill();
      if (isOwner) {
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = "#f4c542";
        ctx.stroke();
      }
    }
  }
}

function readout(frame, elId) {
  const agents = frame.agents;
  const owners = new Set(frame.owner_ids || []);
  let sumBody = 0, ownerBody = 0;
  for (const a of agents) { sumBody += a[3]; if (owners.has(a[0])) ownerBody += a[3]; }
  const ownerShare = sumBody > 0 ? ownerBody / sumBody : 0;
  const el = $(elId);
  el.innerHTML =
    `<span>agents <b>${agents.length}</b></span>` +
    `<span>Σ body <b>${sumBody.toFixed(1)}</b> kg</span>` +
    `<span>owners <b>${owners.size}</b></span>` +
    `<span class="gold">owner share <b>${ownerShare.toFixed(3)}</b></span>` +
    `<span>tribute <b>${(frame.appropriated_total || 0).toFixed(0)}</b> kg</span>`;
}

function draw(t) {
  $("day").textContent = t;
  for (const side of ["baseline", "headline"]) {
    const run = state[side];
    if (!run) continue;
    const frame = run.byT[t];
    if (!frame) continue;
    renderFrame(frame, $(`cv-${side}`), run.meta);
    readout(frame, `ro-${side}`);
  }
}

function wireControls() {
  const scrub = $("scrub");
  scrub.min = state.tMin; scrub.max = state.tMax; scrub.value = state.tMin;
  scrub.addEventListener("input", () => draw(parseInt(scrub.value, 10)));
  const map = { "ly-food": "food", "ly-bodies": "bodies", "ly-owner": "owner", "ly-traj": "traj" };
  for (const [id, key] of Object.entries(map)) {
    $(id).addEventListener("change", (e) => {
      state.layers[key] = e.target.checked;
      draw(parseInt(scrub.value, 10));
    });
  }
}

async function main() {
  try {
    setStatus("loading runs…");
    const runs = await getJSON("/runs");
    const names = new Set(runs.map((r) => r.name));
    if (!names.has(RUNS.baseline) || !names.has(RUNS.headline)) {
      throw new Error(`expected ${RUNS.baseline} & ${RUNS.headline}; got [${[...names].join(", ")}]`);
    }
    setStatus("preloading frames…");
    [state.baseline, state.headline] = await Promise.all([loadRun(RUNS.baseline), loadRun(RUNS.headline)]);

    const m = state.headline.meta;
    state.gridR = m.R || 14; state.gridC = m.C || 14;
    state.tMin = m.t_min; state.tMax = m.t_max;
    computeScales();
    wireControls();
    draw(state.tMin);

    const hf = state.headline.frames.length, bf = state.baseline.frames.length;
    setStatus(`ready — baseline ${bf} frames, headline ${hf} frames; ` +
      `day ${state.tMin}–${state.tMax}. Scrub to watch the stratum appear on the right, never on the left.`);
  } catch (err) {
    setStatus("error: " + err.message + " — did you run capture.py (headline + baseline) first?");
    console.error(err);
  }
}

main();
