"""run_frailty_lifetable.py — mod-J Ф3: J1 (emergence: Gompertz vs Weibull) + J2 (Strehler-
Mildvan). The lifetable is built from the EXISTING log — death events carry data={"age":...};
no new instrumentation (WO §5).

J1 is a PREDICTION, never a fit of the shape. Ф2 flagged a warning (WO §5 amendment): the
gompertz arm's median/mean ≈ 0.99 (near-symmetric) is NOT the left-skewed Gompertz signature
— redundancy exhaustion should give median > mean. So BEFORE fitting (B,c) we report the
pre-fit diagnostic (median/mean, IQR, skew) per arm; if gompertz is not left-skewed, x0=0.10
is too small to leave the Weibull corner (rectangularization) — that is a J1 FINDING, not a
failure, and NOT a licence to tune x0 (shape-fitting = tautology).

Discrete actuarial hazard from the lifespan sample (ages of ALL deaths): μ(a) = d(a)/n(a),
d(a)=deaths at age a, n(a)=#died at age ≥ a (at risk entering age a). Then on 20..100:
  Gompertz: log μ(a) linear in a          (slope c, intercept log B)
  Weibull:  log μ(a) linear in log a      (slope = shape−1)
Higher R² picks the family; the late-life window (>100) is inspected for a plateau.

Science config (WO §7.1): institution at rho=0 is INERT (enforcers own nothing, owner_share
0 — a finding for J2/J4), so for the J1 lifetable it is identical to plain rho=0 founders,
arena=None, T=1200 — the regime where senescence DOMINATES deaths (~73%), the clean signal.

Run:  py stage3/run_frailty_lifetable.py
"""
from __future__ import annotations

import os
import statistics as stx
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                      # noqa: E402
from stage3.polis import Polis                         # noqa: E402
from stage3.run_artifact_f import _cfg                 # noqa: E402

HDR = "=" * 78
T = 1200
SEEDS = (7, 8, 9)
ARMS = ("off", "flat", "gompertz")
FIT_LO, FIT_HI = 20, 100          # the pre-registered lifetable window (WO §5 J1)


def _ages(arm, seed, *, rho=0.0, owner="founders", rho_rep=0.0):
    cfg = _cfg(days=0, seed=seed, frailty=arm, rho=rho, owner=owner, arena=None,
               frailty_rho_rep=rho_rep)
    w = Polis(EventLog(), cfg)
    for _ in range(T):
        w.step()
        if len(w.pop) == 0:
            break
    return [(e.data or {}).get("age") for e in w.log.events
            if e.kind == "death" and (e.data or {}).get("age") is not None]


def _skew(xs):
    if len(xs) < 3:
        return float("nan")
    m, s = stx.mean(xs), stx.pstdev(xs)
    return sum((x - m) ** 3 for x in xs) / (len(xs) * s ** 3) if s > 0 else 0.0


def _diagnostic(xs):
    xs = sorted(xs)
    n = len(xs)
    q1, q3 = xs[n // 4], xs[(3 * n) // 4]
    mean, median = stx.mean(xs), stx.median(xs)
    return {"n": n, "mean": mean, "median": median, "med_mean": median / mean if mean else 0,
            "iqr": q3 - q1, "skew": _skew(xs)}


def _hazard(ages):
    """Discrete actuarial hazard μ(a)=d(a)/n(a) over integer ages. Returns (a, mu) arrays."""
    ages = np.asarray(ages, dtype=int)
    amax = int(ages.max())
    a = np.arange(0, amax + 1)
    d = np.bincount(ages, minlength=amax + 1).astype(float)           # deaths AT age a
    n = d[::-1].cumsum()[::-1]                                          # at risk: died at age ≥ a
    with np.errstate(divide="ignore", invalid="ignore"):
        mu = np.where(n > 0, d / n, np.nan)
    return a, mu


def _linfit(x, y):
    """OLS slope/intercept + R² + slope SE. x,y are 1-D arrays (finite)."""
    n = len(x)
    sl, ic = np.polyfit(x, y, 1)
    yhat = sl * x + ic
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    se = float(np.sqrt(ss_res / (n - 2) / np.sum((x - x.mean()) ** 2))) if n > 2 else float("nan")
    return sl, ic, r2, se


def _fits(a, mu):
    """Gompertz (log μ ~ a) vs Weibull (log μ ~ log a) on [FIT_LO, FIT_HI]."""
    m = (a >= FIT_LO) & (a <= FIT_HI) & np.isfinite(mu) & (mu > 0)
    aa, lm = a[m].astype(float), np.log(mu[m])
    g = _linfit(aa, lm)                       # slope=c, intercept=log B
    w = _linfit(np.log(aa), lm)               # slope=shape-1
    return {"gompertz": g, "weibull": w, "npts": int(m.sum())}


def main():
    print(HDR)
    print(f"mod-J Ф3 — J1 lifetable (Gompertz vs Weibull) · science config rho=0, arena=none, T={T}")
    print(HDR)

    # ---- J1 pre-fit diagnostic (BLOCKS the fit; WO §5) --------------------- #
    print("J1 pre-fit diagnostic — median/mean < 1 ⇒ right-skew (NOT Gompertz); ≈1 ⇒ symmetric:")
    print(f"  {'arm':<9}{'seed':>5}{'mean':>8}{'median':>8}{'med/mean':>10}{'IQR':>7}{'skew':>8}{'n':>8}")
    diag = {}
    for arm in ARMS:
        for s in SEEDS:
            d = _diagnostic(_ages(arm, s))
            diag[(arm, s)] = d
            print(f"  {arm:<9}{s:>5}{d['mean']:>8.1f}{d['median']:>8}{d['med_mean']:>10.3f}"
                  f"{d['iqr']:>7}{d['skew']:>8.2f}{d['n']:>8}")
        print()

    # ---- J1 fit: Gompertz vs Weibull per seed on the gompertz & flat arms --- #
    print(f"J1 fit — log μ(age) on [{FIT_LO},{FIT_HI}]; higher R² picks the family:")
    print(f"  {'arm':<9}{'seed':>5}{'Gz_R2':>8}{'Gz_c':>9}{'Gz_cSE':>9}{'Wb_R2':>8}{'Wb_shape':>10}{'winner':>9}")
    fitagg = {a: {"gz_r2": [], "wb_r2": [], "c": []} for a in ("flat", "gompertz")}
    for arm in ("flat", "gompertz"):
        for s in SEEDS:
            a, mu = _hazard(_ages(arm, s))
            f = _fits(a, mu)
            gz, wb = f["gompertz"], f["weibull"]
            winner = "Gompertz" if gz[2] > wb[2] else "Weibull"
            fitagg[arm]["gz_r2"].append(gz[2]); fitagg[arm]["wb_r2"].append(wb[2])
            fitagg[arm]["c"].append(gz[0])
            print(f"  {arm:<9}{s:>5}{gz[2]:>8.3f}{gz[0]:>9.4f}{gz[3]:>9.4f}"
                  f"{wb[2]:>8.3f}{wb[0] + 1:>10.3f}{winner:>9}")
        print()

    # ---- late-life plateau (μ beyond the fit window) ---------------------- #
    print("late-life: mean μ over (100,140] vs the Gompertz extrapolation (plateau if << ):")
    for arm in ("flat", "gompertz"):
        a, mu = _hazard(_ages(arm, 7))
        late = (a > 100) & (a <= 140) & np.isfinite(mu)
        obs = float(np.nanmean(mu[late])) if late.any() else float("nan")
        gz = _fits(a, mu)["gompertz"]
        pred = float(np.exp(gz[0] * 120 + gz[1]))     # Gompertz μ at age 120
        print(f"  {arm:<9} observed μ̄(100,140]={obs:.3f}  Gompertz-pred μ(120)={pred:.3f}  "
              f"{'plateau' if obs < 0.5 * pred else 'no plateau'}")
    print(HDR)

    # ---- verdicts --------------------------------------------------------- #
    gz_wins = np.mean(fitagg["gompertz"]["gz_r2"]) > np.mean(fitagg["gompertz"]["wb_r2"])
    med_mean = np.mean([diag[("gompertz", s)]["med_mean"] for s in SEEDS])
    c_mean = np.mean(fitagg["gompertz"]["c"]); c_sd = np.std(fitagg["gompertz"]["c"])
    print("J1 VERDICT (gompertz arm):")
    print(f"  median/mean = {med_mean:.3f} (>1 ⇒ left-skew Gompertz; ≈1 ⇒ symmetric/Weibull corner)")
    print(f"  R²: Gompertz {np.mean(fitagg['gompertz']['gz_r2']):.3f} vs "
          f"Weibull {np.mean(fitagg['gompertz']['wb_r2']):.3f} → "
          f"{'Gompertz' if gz_wins else 'Weibull'} family")
    print(f"  c (Gompertz slope) = {c_mean:.4f} ± {c_sd:.4f} (across seeds)")
    left_skew = med_mean > 1.0
    if gz_wins and left_skew:
        v = "CONFIRM Gompertz — hazard emerges log-linear AND left-skewed (redundancy exhaustion)"
    elif not gz_wins:
        v = "Weibull — x0=0.10 too small to leave the Weibull corner (WO §5: FINDING, not failure; do NOT tune x0)"
    else:
        v = "neither clean — Gompertz R² wins but distribution not left-skewed (mixed; report as-is)"
    print(f"  ⇒ {v}")
    print(HDR)

    # ---- J2 (Strehler-Mildvan): the repair seam needs CAPITAL (owned cells) --- #
    # WO §7.1 pins rho=0, but ownership needs rho>0: at rho=0 there are ZERO owned cells,
    # so f(capital)=0 and the repair seam is INERT — the rho_rep sweep is a flat no-op and
    # J2 cannot run there. rho=0.1 is the candidate: ownership AND senescence coexist.
    print("J2 (Strehler-Mildvan) — the repair seam is capital-funded; does rho_rep move life?")
    def _rr(rho, owner, rr):
        cfg = _cfg(days=0, seed=7, frailty="gompertz", rho=rho, owner=owner, arena=None,
                   frailty_rho_rep=rr)
        w = Polis(EventLog(), cfg)
        for _ in range(800):
            w.step()
            if len(w.pop) == 0:
                break
        ag = [(e.data or {}).get("age") for e in w.log.events
              if e.kind == "death" and (e.data or {}).get("age") is not None]
        return (stx.mean(ag) if ag else 0.0), w._owner_share_now()
    for tag, rho, owner in [("rho=0 founders (§7.1 config)", 0.0, "founders"),
                            ("rho=0.1 claim (candidate)", 0.1, "claim")]:
        row = [f"rho_rep={rr}:{_rr(rho, owner, rr)[0]:.1f}" for rr in (0.0, 2.0)]
        osh0 = _rr(rho, owner, 0.0)[1]
        print(f"  {tag:<30} {'  '.join(row)}  owner_share@0={osh0:.3f}")
    print("  J2 VERDICT: INERT at rho=0 (capital=0 → repair never fires) — NOT runnable at the")
    print("             §7.1 config. rho=0.1 moves life (89→111) → the config J2/J4 actually need.")
    print(HDR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
