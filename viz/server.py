"""
viz/server.py — the run registry backend (PR-2 beta-back; PR-31 adds a gated live sandbox).

The READ-ONLY registry path (/runs, /{run}/meta, /{run}/frame, /{run}/frames) is still
FULLY DECOUPLED from the simulation: at module load this backend imports NOTHING from Code/.
It serves the captured artifacts in runs/ (`*.snap.jsonl` + paired `*.meta.json`), and
`final_ownership` is recomputed from the last frame by plain arithmetic — no `ownership_metrics`,
no canon in the render path. Frames load via `schema.frames_from_jsonl` (its canon import is
lazy).

PR-31 CAVEAT — the decoupling is NO LONGER absolute: the live endpoints `/run` and `/sweep`
import `viz.sandbox` LAZILY (inside the handler), and `sandbox` imports `Code/` via `capture`.
Every live run therefore goes through `capture.capture` — the same 4-gate function (B0-anchor,
B0-guard, reproducibility, snapshot-safe). A red gate answers HTTP 500 with the gate text, not
frames. The canon in Code/ is never mutated (capture builds and reads its own world). Nothing
outside `/run` and `/sweep` touches Code/; `/health` lists worlds from a static tuple to stay
canon-free.

Run (from viz/):  uvicorn server:app --port 8000
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from schema import frames_from_jsonl, SnapFrame       # lazy canon import -> no Code/ here

RUNS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# Live-runnable worlds, listed for /health WITHOUT importing capture (keeps /health canon-free).
# The authoritative registry is capture.WORLDS, validated inside /run (which imports it lazily).
LIVE_WORLDS = ("appropriation", "institution", "inheritance", "trade")


def _verb_bool(v) -> bool:
    return str(v).lower() in ("on", "1", "true", "yes")


def _parse_rhos(s):
    out = []
    for tok in str(s).split(","):
        tok = tok.strip()
        if tok:
            out.append(float(tok))
    return out


def _arena_side(a):
    return int(a) if (a not in (None, "", "none")) else None


def _endpoint_metrics(res):
    """Endpoint metrics from a live-run result dict (frames = list of asdict SnapFrame)."""
    frames = res["frames"]
    last = SnapFrame(**frames[-1])
    fo = final_ownership(last)
    return {
        "rho": res["rho"],
        "owner_share": fo["owner_share"],
        "owner_gap": fo["owner_gap"],
        "n_owners": fo["n_owners"],
        "alive": len(last.agents),
        "sum_body": sum(a[3] for a in last.agents),
        "births_total": sum(len(f["births"]) for f in frames),
        "deaths_total": sum(len(f["deaths"]) for f in frames),
    }


# --------------------------------------------------------------------------- #
#  final_ownership — arithmetic on the last frame (NO canon call)              #
# --------------------------------------------------------------------------- #
def _mean(xs):
    return (sum(xs) / len(xs)) if xs else None


def final_ownership(frame: SnapFrame) -> dict:
    """owner_share = sum(body owner)/sum(body all); owner_gap = mean(owner.body) -
    mean(non-owner.body). Agents are [oid, i, j, body, gene, age]. Pure arithmetic."""
    owners = set(frame.owner_ids)
    obody = [a[3] for a in frame.agents if a[0] in owners]
    nbody = [a[3] for a in frame.agents if a[0] not in owners]
    total = sum(a[3] for a in frame.agents)
    om, nm = _mean(obody), _mean(nbody)
    return {
        "owner_gap": (om - nm) if (om is not None and nm is not None) else None,
        "owner_share": (sum(obody) / total) if total > 0 else None,
        "n_owners": len(owners),
        "n_owned_cells": len(frame.cell_owner),
    }


# --------------------------------------------------------------------------- #
#  Registry — scan runs/ once at import                                        #
# --------------------------------------------------------------------------- #
def _load_registry() -> dict:
    reg = {}
    for snap in sorted(glob.glob(os.path.join(RUNS_DIR, "*.snap.jsonl"))):
        name = os.path.basename(snap)[:-len(".snap.jsonl")]
        frames = frames_from_jsonl(snap)
        if not frames:
            continue
        frames.sort(key=lambda f: f.t)
        meta_path = snap[:-len(".snap.jsonl")] + ".meta.json"
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
        reg[name] = {
            "frames": frames,
            "index": {f.t: f for f in frames},
            "meta": meta,
        }
    return reg


REGISTRY = _load_registry()


def _run_or_404(run: str) -> dict:
    if run not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"unknown run '{run}'")
    return REGISTRY[run]


def _summary(name: str, entry: dict) -> dict:
    frames = entry["frames"]
    return {
        "name": name,
        "n_frames": len(frames),
        "t_min": frames[0].t,
        "t_max": frames[-1].t,
        "final": final_ownership(frames[-1]),
    }


# --------------------------------------------------------------------------- #
#  App                                                                         #
# --------------------------------------------------------------------------- #
app = FastAPI(title="Noether viz backend", version="0.2 (PR-2 beta-back)")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    # PR-3: the two-panel viewer. Static assets are served from /static/*.
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health")
def health():
    return {
        "ok": True,
        "live": True,                              # PR-31: gated live /run + /sweep available
        "worlds": list(LIVE_WORLDS),
        "runs": sorted(REGISTRY),
        "total_frames": sum(len(e["frames"]) for e in REGISTRY.values()),
    }


@app.get("/runs")
def runs():
    return [_summary(name, REGISTRY[name]) for name in sorted(REGISTRY)]


# --------------------------------------------------------------------------- #
#  Live sandbox — gate-protected. These are the ONLY endpoints that touch Code/ #
#  (via a LAZY `import sandbox`, which imports capture -> the canon).           #
# --------------------------------------------------------------------------- #
@app.get("/run")
def live_run(world: str, rho: float = 0.5, seed: int = 0,
             arena: str = "", verb: str = "on"):
    """One live, gate-verified run. `rho` maps to the world's extraction knob
    (appropriation/inheritance -> appropriation, institution -> sigma, trade -> price_frac),
    applied only when verb=on (the mechanism); verb=off runs the untreated control. B0 is
    gate-checked against the canon on every call. Returns frames (same shape as /{run}/frames)
    plus the 3 gate fingerprints. 404 unknown world; 500 (with gate text) if a gate is red."""
    import sandbox                                 # LAZY: imports Code/ via capture, only here
    try:
        return sandbox.run(world, rho, seed, _arena_side(arena), _verb_bool(verb))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown world '{world}'")
    except sandbox.GateFailure as e:
        raise HTTPException(status_code=500, detail=f"gate failed: {e.detail}")


@app.get("/sweep")
def sweep(world: str, seed: int = 0, arena: str = "",
          rhos: str = "0,0.25,0.5,0.75,1.0"):
    """Dose-response sweep: run the mechanism (verb=on) across a grid of rho and return the
    endpoint-metric curve (cheap — no full frames). Each rho is gate-protected; rho=0 is the
    built-in control. 404 unknown world; 500 (with gate text) if any rho's gate is red."""
    import sandbox                                 # LAZY: imports Code/ via capture, only here
    a = _arena_side(arena)
    points = []
    for r in _parse_rhos(rhos):
        try:
            res = sandbox.run(world, r, seed, a, True)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown world '{world}'")
        except sandbox.GateFailure as e:
            raise HTTPException(status_code=500, detail=f"gate failed at rho={r}: {e.detail}")
        points.append(_endpoint_metrics(res))
    return {"world": world, "seed": int(seed), "arena": a, "points": points}


@app.get("/{run}/meta")
def run_meta(run: str):
    entry = _run_or_404(run)
    frames = entry["frames"]
    out = dict(entry["meta"])
    out.update({
        "name": run,
        "n_frames": len(frames),
        "t_min": frames[0].t,
        "t_max": frames[-1].t,
        "final_ownership": final_ownership(frames[-1]),
    })
    return out


@app.get("/{run}/frame/{t}")
def run_frame(run: str, t: int):
    entry = _run_or_404(run)
    fr = entry["index"].get(t)
    if fr is None:
        raise HTTPException(status_code=404,
                            detail=f"frame t={t} out of range "
                                   f"[{entry['frames'][0].t}, {entry['frames'][-1].t}]")
    return asdict(fr)


@app.get("/{run}/frames")
def run_frames(run: str,
               t0: int = Query(None), t1: int = Query(None),
               stride: int = Query(1, ge=1)):
    entry = _run_or_404(run)
    frames = entry["frames"]
    lo = frames[0].t if t0 is None else t0
    hi = frames[-1].t if t1 is None else t1
    return [asdict(f) for f in frames if lo <= f.t <= hi and (f.t - lo) % stride == 0]


# static assets (index.html is served on / above; viz.js / viz.css from /static/*).
# Mounted last so the explicit API routes take precedence.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
