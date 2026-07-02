"""
viz/capture.py — capture a provably-faithful snapshot of a canon run (PR-1, beta-core).

`capture()` runs four gates before it writes a single frame, so a green run is a PROOF that
the snapshot shows exactly the measured trajectory:

  1. B0 gate        — the world's off-config reproduces its canon byte-anchor (and books no
                      tribute), i.e. the harness is wired to the real kernel.
  2. reproducibility — two clean headline runs share a fingerprint (the run is deterministic).
  3. capture        — a THIRD headline run is stepped by hand, snapping a SnapFrame every
                      `every` ticks (the loop duplicates run_*: build the world, step, read).
  4. snapshot-safe  — the snapped world's fingerprint == the clean run's fingerprint. This is
                      the key gate: reading frames mid-run did NOT perturb the trajectory.

The world registry is extended with one line per world. It touches no canon: every value is
imported from Code/ and read-only. `run(**cfg, days=0)` returns the pristine, un-stepped
world (every run_* loops `for _ in range(days)`), so the capture loop drives an identically
constructed world without reimplementing construction.
"""

from __future__ import annotations

import os
import sys

_CODE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Code")
if _CODE not in sys.path:
    sys.path.insert(0, _CODE)

from sim_comm import DAYS                                        # noqa: E402
from sim_sphere import GRID_DIAG, CANON_COMM                     # noqa: E402
from sim_appropriation import (                                  # noqa: E402
    run_appropriation, appropriation_fingerprint, ownership_metrics,
)

from schema import frame_from_world, frames_to_jsonl, meta       # noqa: E402
import json                                                      # noqa: E402

RUNS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")


# --------------------------------------------------------------------------- #
#  The world registry — one entry per capturable world (extend with one line). #
# --------------------------------------------------------------------------- #
WORLDS = {
    "appropriation": {
        "run": run_appropriation,                 # from sim_appropriation
        "fp":  appropriation_fingerprint,
        "B0":  dict(appropriation=0.0, owner_policy="founders",
                    radius=GRID_DIAG + 1.0, K=None, lag=0,
                    injection_strength=0.0, injectors=0, arena_side=None),
        "B0_anchor": CANON_COMM,                  # "a91480561b6de937"
        "headline": dict(appropriation=0.5, owner_policy="claim", arena_side=6,
                         injection_strength=0.0, injectors=0),   # rho=0.5 claim, box6, sal off
        "baseline": dict(appropriation=0.0, owner_policy="claim", arena_side=6,
                         injection_strength=0.0, injectors=0),   # rho=0 control, SAME arena/seed
    },
}


def _default_out(name, config_key) -> str:
    return os.path.join(RUNS_DIR, f"{name}_{config_key}.snap.jsonl")


def capture(name, config_key="headline", every=1, out_path=None):
    spec = WORLDS[name]
    run, fp = spec["run"], spec["fp"]
    line = "-" * 66

    # --- 1. B0 gate: off-config reproduces the canon anchor, books no tribute -- #
    wb0, _ = run(**spec["B0"])
    fpb0 = wb0.state_fingerprint()
    ok_b0 = (fpb0 == spec["B0_anchor"] and wb0._appropriated_total == 0.0)
    print(f"B0 gate       : {fpb0} vs {spec['B0_anchor']}  -> "
          f"{'BYTE-IDENTICAL ✓' if ok_b0 else 'MISMATCH ✗'}   "
          f"(appropriated_total={wb0._appropriated_total})")
    assert ok_b0, "B0 gate failed: not byte-identical to the canon anchor / nonzero tribute"

    # --- 2. reproducibility: two clean headline runs agree -------------------- #
    cfg = spec[config_key]
    w1, _ = run(**cfg)
    w2, _ = run(**cfg)
    f_clean, f2 = fp(w1), fp(w2)
    ok_rep = f_clean == f2
    print(f"reproducibility: {f_clean} == {f2}  -> "
          f"{'BIT-IDENTICAL ✓' if ok_rep else 'MISMATCH ✗'}")
    assert ok_rep, "reproducibility gate failed: headline run is not deterministic"

    # --- 3. capture: rebuild the SAME world (days=0 -> pristine) and step ------ #
    ws, _ = run(**cfg, days=0)                     # constructed identically, not yet stepped
    frames = []
    for _ in range(DAYS):
        ws.step()
        if ws.t % every == 0 or ws.t == DAYS:      # ws.t = 1..300 -> label is the TRUE sim-day
            frames.append(frame_from_world(ws, ws.t))

    # --- 4. snapshot-safe: the snapped run == the clean run ------------------- #
    f_snap = fp(ws)
    ok_safe = f_snap == f_clean
    print(f"snapshot-safe : {f_snap} == {f_clean}  -> "
          f"{'BIT-IDENTICAL ✓' if ok_safe else 'MISMATCH ✗'}   "
          f"<- snapshot did not perturb the run")
    assert ok_safe, "snapshot-safe gate failed: capturing frames changed the trajectory"

    # --- 5. write frames (+ meta sidecar) and report -------------------------- #
    out_path = out_path or _default_out(name, config_key)
    frames_to_jsonl(frames, out_path)
    meta_path = out_path.replace(".snap.jsonl", ".meta.json")
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta(ws), fh, sort_keys=True)

    om = ownership_metrics(ws)
    print(f"captured      : {len(frames)} frames -> {os.path.relpath(out_path)}")
    print(line)
    print(f"final ownership: owner_gap={om['owner_gap']:+.4f}  "
          f"owner_share={om['owner_bio_share']:.4f}  "
          f"n_owners={om['n_owners']}  n_owned_cells={om['n_owned_cells']}")
    print(f"meta          : {os.path.relpath(meta_path)}")
    return frames, out_path


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "appropriation"
    ckey = sys.argv[2] if len(sys.argv) > 2 else "headline"
    every = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    capture(name, ckey, every=every)
