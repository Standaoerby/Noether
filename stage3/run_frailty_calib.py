"""run_frailty_calib.py — mod-J Ф2: calibration on the REALIZED mean + control arm binding.

WO §3 (amended 14.07): the binding condition is NOT "≈120" — that was the first-edition
error (120 is the STARVATION base; senescence is a competing risk on a conserved substrate,
so the realized mean cannot be pinned to it a priori). The correct target: the two mortal
arms `flat` and `gompertz` must land on the SAME realized mean (τ ± 2%), so J5 (concentration
at equal mean) is well-posed. `off` is the uncalibrated base — the third comparison point.

Procedure (WO §3): gompertz is left at a sane preset and DEFINES τ; only `flat`'s k is tuned
(baked into frailty._ARMS). The realized mean is measured from the log over ALL death events,
both causes (starvation + senescence) — the same age field J1's lifetable reads. NOT an
analytic senescence-only mean.

  MJ-MATCH (blocks Ф3/Ф4): |mean(flat) − mean(gompertz)| / mean(gompertz) ≤ 2% on seeds 7/8/9.
  MJ-SEED (one line): the FrailtyField constructor threads seed=cfg.seed. If it defaulted to
    0, seeds 7/8/9 would share ONE frailty stream and the whole seed sweep would be a lie.

SCIENCE CONFIG (pinned): arena=None (field, the J3/J4/J5 arena), rho=0 founders (the only
regime where senescence competes — rho>0 is the turnover pump, natural life ~7, senescence
never fires), T=1200. The realized mean is NON-STATIONARY in T (rho=0 is a growing world), so
the match is T-specific — Ф3/Ф4 MUST run at this T. See frailty._ARMS for the calibration note.

Acceptance (WO §8): trust the LITERAL output line and $LASTEXITCODE, never a notification.

Run:  py stage3/run_frailty_calib.py
"""
from __future__ import annotations

import os
import statistics as stx
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                          # noqa: E402
from stage3.polis import Polis                             # noqa: E402
from stage3.run_artifact_f import _cfg                     # noqa: E402

HDR = "=" * 78
T = 1200                       # pinned science T (see module docstring / frailty._ARMS)
SEEDS = (7, 8, 9)
ARMS = ("off", "flat", "gompertz")
MATCH_TOL = 0.02               # ±2% (MJ-MATCH)


def _realized(arm, seed):
    """Drive the pinned config T ticks; return realized life stats from the death log
    (age field, ALL deaths, both causes) plus a per-cause split."""
    cfg = _cfg(days=0, seed=seed, frailty=arm, rho=0.0, owner="founders", arena=None)
    w = Polis(EventLog(), cfg)
    for _ in range(T):
        w.step()
        if len(w.pop) == 0:
            break
    ages, by_cause = [], {"starvation": 0, "senescence": 0}
    for e in w.log.events:
        if e.kind != "death":
            continue
        a = (e.data or {}).get("age")
        c = (e.data or {}).get("cause", "starvation")
        if a is not None:
            ages.append(a)
            by_cause[c if c in by_cause else "starvation"] += 1
    return {
        "mean": round(stx.mean(ages), 1) if ages else 0.0,
        "median": int(stx.median(ages)) if ages else 0,
        "n": len(ages),
        "sen": by_cause["senescence"],
        "starv": by_cause["starvation"],
    }


def _mj_seed_line():
    """MJ-SEED: show the constructor really threads seed=cfg.seed (default 0 would collapse
    the seed sweep). Read it straight from polis.py so the report can't lie about the code."""
    src = os.path.join(os.path.dirname(__file__), "polis.py")
    with open(src, encoding="utf-8") as f:
        lines = f.read().splitlines()
    hit = [ln.strip() for ln in lines if "FrailtyField(" in ln or "rho_rep=cfg.frailty_rho_rep" in ln]
    threaded = any("seed=cfg.seed" in ln for ln in hit)
    return threaded, hit


def main():
    print(HDR)
    print(f"mod-J Ф2 — calibration on the realized mean (field, rho=0 founders, T={T})")
    print(HDR)

    # MJ-SEED first (cheap, and it gates the meaning of the whole seed sweep)
    threaded, hit = _mj_seed_line()
    print("MJ-SEED — frailty RNG is per-seed (seed=cfg.seed threaded, not default 0):")
    for ln in hit:
        print(f"    polis.py: {ln}")
    print(f"  MJ-SEED: {'✓ seed threaded' if threaded else '✗ SEED NOT THREADED — sweep is void'}")
    print(HDR)

    # the calibration table: realized mean/median × 3 arms × 3 seeds
    res = {(arm, s): _realized(arm, s) for arm in ARMS for s in SEEDS}
    print(f"  {'arm':<10}{'seed':>5}{'mean':>8}{'median':>8}{'n_death':>9}{'senesc':>8}{'starv':>8}")
    for arm in ARMS:
        for s in SEEDS:
            r = res[(arm, s)]
            print(f"  {arm:<10}{s:>5}{r['mean']:>8}{r['median']:>8}{r['n']:>9}{r['sen']:>8}{r['starv']:>8}")
        print()

    # MJ-MATCH: flat ≡ gompertz within ±2% per seed
    print("MJ-MATCH — realized mean(flat) ≡ mean(gompertz) within ±2% (blocks Ф3/Ф4):")
    ok = True
    for s in SEEDS:
        mf, mg = res[("flat", s)]["mean"], res[("gompertz", s)]["mean"]
        d = abs(mf - mg) / mg if mg else 1.0
        good = d <= MATCH_TOL
        ok = ok and good
        print(f"  seed {s}: flat={mf:.1f} gompertz={mg:.1f} diff={d*100:.2f}% {'✓' if good else '✗'}")
    # off is the base — report the gap, not a gate
    for s in SEEDS:
        print(f"  seed {s}: base off={res[('off', s)]['mean']:.1f} "
              f"(mortal arms vs base: flat {res[('flat', s)]['mean']:.1f}, "
              f"gompertz {res[('gompertz', s)]['mean']:.1f})")
    print(f"\n  MJ-MATCH: {'✓ arms bound to a common mean' if ok else '✗ NOT MATCHED — retune flat k'}")
    print(HDR)
    ok_all = ok and threaded
    print("mod-J Ф2 calibration: MJ-SEED ✓  MJ-MATCH ✓" if ok_all
          else "mod-J Ф2 calibration: FAILED — see above")
    print(HDR)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
