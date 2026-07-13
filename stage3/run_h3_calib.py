"""run_h3_calib.py — mod H3 Phase 0: empirical calibration of the public-good multiplier.

The public good opens a SOIL flow with efficiency m and splits it over a co-located deme
(n present pawns). The classic dilemma lives at m/n around 1 (contributing is individually
unprofitable when m/n < 1). But m may not promise mass the soil does not hold — so the sweep
points are chosen from MEASURED single-pawn yield, soil reservoir and deme size, not from a
lab game with an unbounded multiplier.

Measures, from a default world (no new handles), averaged over the run:
  * single-pawn yield  = mean per-tick body gain from grazing (the income scale)
  * soil reservoir     = mean soil per cell (the pool draws from here)
  * deme size n        = mean co-located group size on shared cells (deme == cell)
  * available flow     = soil a cell can physically yield vs what m·C would demand

Run:  py stage3/run_h3_calib.py
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict
import numpy as np

from sim_eventlog import EventLog
from stage3.polis import Polis
from stage3.run_artifact_f import _cfg

HDR = "=" * 78


def main():
    print(HDR)
    print("mod H3 Phase 0 — empirical calibration of the public-good multiplier m")
    print(HDR)
    # default vitok-2 substrate world (store+capital on), arena none, no debt/pg
    cfg = _cfg(artifacts=True, arena=None, days=0)
    w = Polis(EventLog(), cfg)
    T = 500
    yields = []                 # per-tick body gain per living pawn (grazing income)
    soils = []                  # mean soil per cell
    demes = []                  # co-located group sizes (>=2) — the deme sizes
    cell_soils = []             # soil on cells that host >=2 pawns (the reservoir a deme taps)
    prev = {a.oid: a.body for a in w.pop}
    for _ in range(T):
        w.step()
        # income = positive body delta across the tick (grazing minus upkeep, before any transfer)
        gains = [max(0.0, a.body - prev.get(a.oid, a.body)) for a in w.pop]
        yields.extend(g for g in gains if g > 0)
        prev = {a.oid: a.body for a in w.pop}
        soils.append(float(np.asarray(w.soil).mean()))
        bycell = defaultdict(list)
        for a in w.pop:
            bycell[(a.i, a.j)].append(a)
        for cell, members in bycell.items():
            if len(members) >= 2:
                demes.append(len(members))
                cell_soils.append(float(w.soil[cell[0], cell[1]]))

    y_mean = float(np.mean(yields)) if yields else float("nan")
    y_med = float(np.median(yields)) if yields else float("nan")
    soil_mean = float(np.mean(soils))
    n_mean = float(np.mean(demes)) if demes else float("nan")
    n_med = float(np.median(demes)) if demes else float("nan")
    cell_soil_mean = float(np.mean(cell_soils)) if cell_soils else float("nan")

    print(f"\nMeasured over T={T} (arena none, default substrate):")
    print(f"  single-pawn yield (body gain/tick):   mean {y_mean:.4f}  median {y_med:.4f}")
    print(f"  soil reservoir (mean per cell):        {soil_mean:.2f}")
    print(f"  soil on shared cells (deme taps this): mean {cell_soil_mean:.2f}")
    print(f"  deme size n (co-located, >=2):         mean {n_mean:.2f}  median {n_med:.1f}")
    print(f"  shared-cell samples: {len(demes)}  ·  final pop {len(w.pop)}")

    # a deme's per-round contribution scale C ~ n · (a fraction of yield); the pool demands m·C
    # from soil. Anchor the sweep on the MEASURED n (critical m/n = 1 at m = n).
    n = n_med if n_med == n_med else 2.0
    C_scale = n_mean * y_mean if (n_mean == n_mean and y_mean == y_mean) else float("nan")
    print(f"\n  critical multiplier m == n (median deme) = {n:.1f}")
    print(f"  a full-contribution round demands ~m·C = m·{C_scale:.3f} kg from a cell holding "
          f"~{cell_soil_mean:.1f} kg soil")
    cap_m = (cell_soil_mean / C_scale) if (C_scale and C_scale == C_scale and C_scale > 0) else float("nan")
    print(f"  => soil caps the multiplier around m ~ {cap_m:.1f} before the promise outruns the "
          f"reservoir")
    print(f"\n  PROPOSED SWEEP POINTS (justified below):")
    print(f"    m = 1.0   control — no synergy (pool just redistributes contributions)")
    print(f"    m = {n:.1f}   threshold m/n=1 — contributing is individually break-even")
    print(f"    m = {min(2*n, cap_m):.1f}   above threshold — individually profitable, "
          f"but {'SOIL-CAPPED (honest ceiling)' if 2*n > cap_m else 'within reservoir'}")
    print(HDR)


if __name__ == "__main__":
    main()
