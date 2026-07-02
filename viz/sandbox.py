"""
viz/sandbox.py — the ONLY place the viz backend runs the canon live (PR-31, beta-sandbox).

Every live run goes through `capture.capture(...)` — the SAME 4-gate function that snapshots
the battery (B0-anchor, B0-guard, reproducibility, snapshot-safe). This module NEVER calls
`run_*` directly and NEVER re-implements the sim loop: it registers a one-off entry in
`capture.WORLDS` (copying the base world's run/fp/B0/guard, overriding the config with the
requested dose/seed/arena), hands it to `capture.capture`, and returns the gate-verified
frames. If any gate is red, `capture.capture` raises `AssertionError`; we surface it as a
`GateFailure` so the endpoint answers HTTP 500 with the gate text — garbage never reaches the
front.

Importing this module imports `Code/` (via `capture`) — the single sanctioned coupling. That
is why `server.py` imports `sandbox` LAZILY, only inside `/run` and `/sweep`.

Dose mapping (rho in [0,1] -> the world's extraction knob):
  appropriation, inheritance -> appropriation
  institution                -> sigma
  trade                      -> price_frac
The dose is applied only to the mechanism (verb=on / headline) config; the control
(verb=off / baseline) runs as-is, so a two-panel contrast stays control-vs-treatment. B0 is
gate-checked against the canon on EVERY run regardless of rho (the built-in control).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import tempfile
import threading
from dataclasses import asdict

import capture as cap        # imports Code/ (the canon) — the single sanctioned coupling

DOSE = {
    "appropriation": "appropriation",
    "inheritance": "appropriation",
    "institution": "sigma",
    "trade": "price_frac",
}

_LOCK = threading.Lock()      # WORLDS mutation + capture serialized (local single-user tool)
_CACHE: dict = {}             # (world, rho, seed, arena, verb) -> result dict
_SCRATCH = os.path.join(tempfile.gettempdir(), "noether_live")   # throwaway snap/meta files

_FP_RE = {
    "b0": re.compile(r"B0 gate\s*:\s*([0-9a-f]{16})"),
    "repro": re.compile(r"reproducibility:\s*([0-9a-f]{16})"),
    "safe": re.compile(r"snapshot-safe\s*:\s*([0-9a-f]{16})"),
}


class GateFailure(Exception):
    """A live run failed one of capture's 4 gates. `detail` is the human-readable reason."""
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


def worlds():
    return sorted(cap.WORLDS)


def _cfg_for(world, rho, seed, arena, verb):
    base = cap.WORLDS[world]
    ckey = "headline" if verb else "baseline"
    cfg = dict(base[ckey])
    if verb:
        cfg[DOSE[world]] = float(rho)          # dose only on the mechanism config
    cfg["seed"] = int(seed)
    cfg["arena_side"] = arena                   # None (open) or int
    return ckey, cfg


def run(world, rho, seed, arena, verb):
    """Gate-protected live run. Returns a dict with frames (asdict) + the 3 gate fingerprints.
    Raises KeyError for an unknown world, GateFailure if any gate is red."""
    if world not in cap.WORLDS:
        raise KeyError(world)
    key = (world, float(rho), int(seed), arena, bool(verb))
    if key in _CACHE:
        return _CACHE[key]

    ckey, cfg = _cfg_for(world, rho, seed, arena, verb)
    base = cap.WORLDS[world]
    tmp = f"__live__:{world}:{rho}:{seed}:{arena}:{verb}"
    out_path = os.path.join(_SCRATCH, re.sub(r"[^0-9A-Za-z]+", "_", tmp) + ".snap.jsonl")
    buf = io.StringIO()

    with _LOCK:
        cap.WORLDS[tmp] = {k: base[k] for k in ("run", "fp", "B0", "B0_anchor", "B0_guard")}
        cap.WORLDS[tmp][ckey] = cfg
        try:
            with contextlib.redirect_stdout(buf):
                frames, written = cap.capture(tmp, ckey, out_path=out_path)  # 4 gates or raise
        except AssertionError as e:
            raise GateFailure(f"{e}  ||  {buf.getvalue().strip().splitlines()[-1] if buf.getvalue().strip() else ''}") from e
        finally:
            cap.WORLDS.pop(tmp, None)

    log = buf.getvalue()
    meta_path = written.replace(".snap.jsonl", ".meta.json")
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as fh:
            meta = json.load(fh)

    def _fp(k):
        m = _FP_RE[k].search(log)
        return m.group(1) if m else None

    result = {
        "world": world, "rho": float(rho), "seed": int(seed),
        "arena": arena, "verb": bool(verb),
        "b0_fp": _fp("b0"), "repro_fp": _fp("repro"), "safe_fp": _fp("safe"),
        "n_frames": len(frames),
        "t_min": frames[0].t if frames else None,
        "t_max": frames[-1].t if frames else None,
        "meta": meta,
        "frames": [asdict(f) for f in frames],
    }
    _CACHE[key] = result
    return result
