"""resultjson.py — S2 (WO_consolidation-sprint): machine-readable runner results.

Editable stage3 runners can emit a `results/<runner>.result.json` under `--json`, so a
consumer (CI, the vault, a diff tool) sees a runner's outcome as DATA, not as scraped
stdout. The schema is deliberately small and DETERMINISTIC on a fixed commit — no
timestamp — so a double run is byte-identical (the S2 gate). Two levels of proof, made
explicit (S2.2):
  * state_hash  — the world's `state_fingerprint()`: proves the SUBSTRATE is identical.
  * event_hash  — a digest of the event log: proves the same HISTORY was produced.
  * stdout-SHA256 (legacy, canon modules) only proves "the program printed the same
    bytes twice" — strictly weaker. Canon `sim_*` are not editable, so they keep it.

Usage (in a runner's `--json` branch):
    from stage3.resultjson import write_result
    write_result("run_artifact_h3", world, seed=7,
                 invariants={"drift": world.matter_drift()},
                 metrics={"loans": w._debt.n_loans, ...})
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RESULTS = os.path.join(_ROOT, "results")


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_ROOT,
                              capture_output=True, text=True).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def event_hash(world) -> str:
    """A stable 16-hex digest of the world's event log — same history => same hash."""
    ev = getattr(getattr(world, "log", None), "events", None) or ()
    h = hashlib.sha256()
    for e in ev:
        # the invariant fields of an Event: (t, kind, scale, actor, dm)
        h.update(f"{e.t}|{e.kind}|{getattr(e, 'scale', '')}|{e.actor}|"
                 f"{round(float(getattr(e, 'dm', 0.0) or 0.0), 9)}\n".encode())
    return h.hexdigest()[:16]


def write_result(runner: str, world, seed=None, invariants=None, metrics=None) -> str:
    """Write results/<runner>.result.json. Returns the path. Deterministic on a commit
    (no timestamp): a double run is byte-identical."""
    payload = {
        "schema": 1,
        "runner": runner,
        "commit": _commit(),
        "seed": seed,
        "state_hash": world.state_fingerprint(),
        "event_hash": event_hash(world),
        "invariants": {k: (round(v, 12) if isinstance(v, float) else v)
                       for k, v in (invariants or {}).items()},
        "metrics": {k: (round(v, 9) if isinstance(v, float) else v)
                    for k, v in (metrics or {}).items()},
    }
    os.makedirs(_RESULTS, exist_ok=True)
    path = os.path.join(_RESULTS, f"{runner}.result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    return path
