"""
viz/server.py — the read-only run registry backend (PR-2, beta-back), FastAPI.

FULLY DECOUPLED from the simulation: this backend does NOT import Code/ and never calls the
canon. It works only over the captured artifacts in runs/ (`*.snap.jsonl` + paired
`*.meta.json`). `final_ownership` is recomputed from the last frame by plain arithmetic
(owner_ids + agent bodies), never via `ownership_metrics` — so no canon leaks into the
render path. Frames are loaded with `schema.frames_from_jsonl` (whose canon import is lazy,
so importing it here pulls in nothing from Code/).

Run (from viz/):  uvicorn server:app --port 8000
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from schema import frames_from_jsonl, SnapFrame       # lazy canon import -> no Code/ here

RUNS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")


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
    # stub — PR-3 mounts static/index.html here
    return {"service": "noether-viz", "runs": sorted(REGISTRY)}


@app.get("/health")
def health():
    return {
        "ok": True,
        "runs": sorted(REGISTRY),
        "total_frames": sum(len(e["frames"]) for e in REGISTRY.values()),
    }


@app.get("/runs")
def runs():
    return [_summary(name, REGISTRY[name]) for name in sorted(REGISTRY)]


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
