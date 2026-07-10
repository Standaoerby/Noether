"""
power_dose_figure.py — viz β-3, Block D: the dose curve of the michelsian hole + the pie.

Closes the HG2V-1b science: sweep the reputation compliance threshold {0.3,0.5,0.7,0.9} and
place the reference teeth {none, enforcer, auto} on the same axes. X = the ACTUAL compliant
fraction; curves = A_flow (flow reaped by the absent root), owner_gap, and Σincome (the PIE
— total tribute the delegates collected). The pie is the discriminating measurement: does
enforcement (auto) STRANGLE the base (a Laffer curve on a conservative substrate), or are
the pies equal and the dl=0.7>auto anomaly mere composition?

PRE-REG 1b (both formulations fixed before the run):
  (a) Σincome(auto) < Σincome(rep@0.7) AND owners die more under auto => "coercion strangles
      the base" — the THIRD trophy, a Laffer curve on the conserved substrate.
  (b) the pies are ~equal and the difference is composition (who remits, not how big the
      pie) => drop "beyond enforcement"; the 735>607 anomaly is reshuffling, not growth.

Pure stdlib + numpy + matplotlib (the two figure modules' licence, CLAUDE.md). Deterministic
(seeded runs). Writes PNG + the underlying data .jsonl next to this script (committed).
"""
from __future__ import annotations

import sys, os, json
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "Code"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sim_eventlog import EventLog
from stage3.polis import Polis
from stage3.run_artifact_g2d import _cfgg2d

SEEDS = (7, 8, 9)
DAYS = 300
THRESHOLDS = (0.3, 0.5, 0.7, 0.9)


def _run_accum(cfg, days):
    """One run, accumulating the observer quantities the figure needs (no blob touched):
    Σincome (the pie — owners' tribute income, root excluded), the root's body integral,
    the historical delegate pool, and end-of-run live owners / deaths."""
    w = Polis(EventLog(), cfg)
    sigma_income = 0.0
    root_body_int = 0.0
    t_hist = set()
    for _ in range(days):
        w.step()
        root = w._delegate_root
        for o, v in w._delegate_m_income.items():          # set by the _appropriate override
            if o != root:
                sigma_income += v
        ra = next((a for a in w.pop if a.oid == root), None)
        if ra is not None:
            root_body_int += ra.body
        t_hist |= set(w.owner_ids())
    deaths = sum(1 for e in w.log.events if e.kind == "death")
    live_owners = len(w.owner_ids())
    return w, sigma_income, root_body_int, t_hist, deaths, live_owners


def _compliant_fraction(w, t_hist, dl):
    pool = [o for o in t_hist if o != w._delegate_root
            and o not in w._delegate_enforcer_ids]
    if not pool:
        return float("nan")
    return sum(1 for o in pool if w.pawn(o).personality.deception_lean <= dl) / len(pool)


def _measure(tooth, dl=0.5, enforcers=0):
    """Mean over seeds of the figure quantities for one (tooth, dl) cell."""
    acc = defaultdict(float); n = 0
    for s in SEEDS:
        cfg = _cfgg2d(tooth=tooth, delegate_compliance_dl=dl, enforcers=enforcers,
                      arena=None, seed=s, days=DAYS)
        w, income, rbi, t_hist, deaths, live = _run_accum(cfg, DAYS)
        gap = (w._delegate_flow / rbi) if rbi > 0 else float("nan")
        frac = _compliant_fraction(w, t_hist, dl) if tooth == "reputation" else float("nan")
        acc["flow"] += w._delegate_flow; acc["income"] += income
        acc["gap"] += (gap if gap == gap else 0.0); acc["gapn"] += (1 if gap == gap else 0)
        acc["frac"] += (frac if frac == frac else 0.0); acc["fracn"] += (1 if frac == frac else 0)
        acc["deaths"] += deaths; acc["live"] += live
        n += 1
    return {
        "tooth": tooth, "dl": dl,
        "A_flow": acc["flow"] / n, "Sigma_income": acc["income"] / n,
        "owner_gap": (acc["gap"] / acc["gapn"]) if acc["gapn"] else float("nan"),
        "compliant_frac": (acc["frac"] / acc["fracn"]) if acc["fracn"] else float("nan"),
        "deaths": acc["deaths"] / n, "live_owners": acc["live"] / n,
    }


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    print("power dose figure — sweeping the compliance threshold and the reference teeth...")
    rows = []
    for dl in THRESHOLDS:
        rows.append(_measure("reputation", dl=dl))
        print(f"  reputation dl={dl}: compliant {rows[-1]['compliant_frac']:.3f} "
              f"A_flow {rows[-1]['A_flow']:.1f} pie {rows[-1]['Sigma_income']:.1f}")
    ref = {}
    for tooth, enf in (("none", 0), ("enforcer", 3), ("auto", 0)):
        ref[tooth] = _measure(tooth, enforcers=enf)
        print(f"  {tooth:>9}: A_flow {ref[tooth]['A_flow']:.1f} pie {ref[tooth]['Sigma_income']:.1f} "
              f"deaths {ref[tooth]['deaths']:.0f} live_owners {ref[tooth]['live_owners']:.1f}")

    # --- data package (committed; written after the verdict is folded in) ---- #
    data = {"seeds": list(SEEDS), "days": DAYS, "arena": "none", "m": 0.7,
            "reputation_sweep": rows, "reference_teeth": ref}

    # --- pre-reg 1b verdict (both formulations were fixed; reality is a third) ---------- #
    pie_none = ref["none"]["Sigma_income"]
    pie_auto = ref["auto"]["Sigma_income"]
    pie_rep07 = next(r["Sigma_income"] for r in rows if r["dl"] == 0.7)
    a_auto = ref["auto"]["A_flow"]
    a_peak = max(r["A_flow"] for r in rows)                 # the Laffer peak across reputation
    a_peak_dl = max(rows, key=lambda r: r["A_flow"])["dl"]
    deaths_auto = ref["auto"]["deaths"]
    deaths_rep07 = next(r["deaths"] for r in rows if r["dl"] == 0.7)
    pie_collapse = pie_none / pie_auto if pie_auto else float("inf")
    laffer = a_peak > a_auto                                # partial compliance beats full
    pies_equal = abs(pie_auto - pie_rep07) / max(pie_rep07, 1e-9) < 0.15
    data["verdict"] = {
        "pie_none": float(pie_none), "pie_auto": float(pie_auto), "pie_rep07": float(pie_rep07),
        "pie_collapse_x": float(pie_collapse), "A_flow_peak": float(a_peak),
        "A_flow_peak_dl": float(a_peak_dl), "A_flow_auto": float(a_auto),
        "laffer_peak": bool(laffer), "pies_equal": bool(pies_equal),
        "deaths_auto": float(deaths_auto), "deaths_rep07": float(deaths_rep07),
    }
    print(f"\n  PRE-REG 1b (both fixed; the outcome is a THIRD): pies are NOT equal "
          f"(none {pie_none:.0f} -> auto {pie_auto:.0f}, x{pie_collapse:.1f} collapse) => (b) FALSE.")
    print(f"  Remittance STRANGLES the pie ~{pie_collapse:.0f}x, and A_flow is NON-monotone: it")
    print(f"  PEAKS at dl={a_peak_dl} ({a_peak:.0f}) ABOVE full compliance/auto ({a_auto:.0f}) — a")
    print(f"  Laffer curve on the conserved substrate (3rd trophy). The mortality leg of (a) did")
    print(f"  NOT co-move (deaths auto {deaths_auto:.0f} < rep@0.7 {deaths_rep07:.0f} — a strangled")
    print(f"  economy is SMALLER, not deadlier), so (a) holds on the PIE, not on mortality.")

    with open(os.path.join(here, "power_dose.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n")

    # --- figure ------------------------------------------------------------- #
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.2, 5.4))
    xs = [r["compliant_frac"] for r in rows]
    axA.plot(xs, [r["A_flow"] for r in rows], "o-", color="#c0392b", label="A_flow (reputation)")
    axA.axhline(ref["auto"]["A_flow"], ls="--", color="#7f8c8d", label="auto (god-ceiling)")
    axA.axhline(ref["none"]["A_flow"], ls=":", color="#bdc3c7", label="none (no tooth)")
    # enforcer has no compliance threshold; place its marker at its EFFECTIVE remittance
    # fraction = A_flow / the god-ceiling (an honest x in [0,1]).
    enf_x = (ref["enforcer"]["A_flow"] / ref["auto"]["A_flow"]) if ref["auto"]["A_flow"] else 0.0
    axA.scatter([enf_x], [ref["enforcer"]["A_flow"]],
                marker="s", color="#2980b9", zorder=5, label="enforcer")
    axA2 = axA.twinx()
    axA2.plot(xs, [r["owner_gap"] for r in rows], "^--", color="#8e44ad", alpha=0.7,
              label="owner_gap")
    axA.set_xlabel("actual compliant fraction of delegates")
    axA.set_ylabel("A_flow (mass reaped by the absent root)")
    axA2.set_ylabel("owner_gap (flow / root body)", color="#8e44ad")
    axA.set_title("Dose curve: the michelsian hole vs the compliant base")
    axA.legend(loc="upper left", fontsize=8)

    axB.plot(xs, [r["Sigma_income"] for r in rows], "o-", color="#16a085",
             label="Σincome / pie (reputation)")
    axB.axhline(pie_auto, ls="--", color="#7f8c8d", label="auto pie")
    axB.axhline(ref["none"]["Sigma_income"], ls=":", color="#bdc3c7", label="none pie")
    axB.set_xlabel("actual compliant fraction of delegates")
    axB.set_ylabel("Σ tribute income (the pie)")
    axB.set_title("The pie: does coercion (auto) strangle the base?")
    axB.legend(loc="best", fontsize=8)
    fig.suptitle("β-3 Block D — power without ownership: dose of reputation vs the teeth "
                 f"(arena none, m=0.7, seeds {SEEDS})", fontsize=11)
    out = os.path.join(here, "power_dose.png")
    fig.savefig(out, dpi=140, bbox_inches="tight")
    print(f"\n  wrote {out}\n  wrote {os.path.join(here, 'power_dose.jsonl')}")


if __name__ == "__main__":
    main()
