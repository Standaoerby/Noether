"""
gradient_figures.py — book figures for the gradient-revision probe (viz Phase 4B).

Two publication PNGs for "Теория Элит", straight from the same runs sim_gradient_probe
fingerprints. This is a READER over the closed tower — it calls run_appropriation /
run_sphere read-only, mutates nothing, adds no dynamics. Canon is untouched by construction
(it lives in viz/, outside Code/, and only reads public final state).

FIGURE 1 — tail_ranksize.png : the body distribution under appropriation is NOT a smooth
  Pareto tail. Log-log rank-size of three runs shows a metabolic-ceiling PLATE (~0.9 kg)
  with a discrete over-ceiling stratum breaking off it — the visual form of "80/20 does not
  reproduce; concentration is caste-like, not gradient". CTRL (rho=0) is the flat control:
  no tail at all. A CCDF panel restates the same fact as "fraction of bodies heavier than x".

FIGURE 2 — kwindow.png : attention scarcity is a DOSE CURVE WITH A FINITE WINDOW, not a flat
  zero. Eviction-concentration (Gini, the load-bearing metric) rises with K, peaks near the
  natural memory size, and switches OFF at K_off (budget stops binding). The small-denominator
  region near the window edge is drawn faded, matching the probe's honest caveat.

Style follows sim_portfolio.py / sim_pareto.py: Agg backend, dpi 140, C0/C3 palette, rounded
info boxes. Deterministic from the canonical seed. Requires numpy + matplotlib.

Run:  python3 gradient_figures.py            # writes both PNGs next to this file
      python3 gradient_figures.py --seed 8   # a different seed (structure is seed-robust)
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# the probe and the worlds it reads (viz/ imports Code/ read-only, like sandbox/server do)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Code"))
from sim_appropriation import run_appropriation           # noqa: E402
from sim_sphere import run_sphere, eviction_concentration  # noqa: E402
from sim_gradient_probe import CEILING, K_GRID, gini       # noqa: E402

OUTDIR = os.path.dirname(os.path.abspath(__file__))
SEED = 7

# (label, rho, owner_policy, arena, colour, marker)
TAIL_RUNS = [
    ("CTRL rho=0 (no appropriation)", 0.0, "founders", None, "0.55", "."),
    ("E1 rho=1.0 box6 (despot spike)", 1.0, "founders", 6,   "C3",   "o"),
    ("CLAIM rho=0.5 box6 (gentry)",    0.5, "claim",    6,   "C0",   "s"),
]


def _bodies(rho, pol, arena, seed):
    w, _ = run_appropriation(appropriation=rho, owner_policy=pol, arena_side=arena,
                             injection_strength=0.0, injectors=0, seed=seed)
    return np.sort(np.asarray([a.body for a in w.pop], float))[::-1]   # descending


# --------------------------------------------------------------------------- #
#  Figure 1 — rank-size + CCDF                                                 #
# --------------------------------------------------------------------------- #
def figure_tail(seed=SEED):
    fig, (axR, axC) = plt.subplots(1, 2, figsize=(13.5, 5.4))

    for (label, rho, pol, arena, col, mk) in TAIL_RUNS:
        b = _bodies(rho, pol, arena, seed)
        ranks = np.arange(1, len(b) + 1)
        # rank-size (log-log): rank on x, body mass on y
        axR.plot(ranks, b, marker=mk, ms=3.2, lw=0.9, color=col, alpha=0.85, label=label)
        # CCDF: P(body >= x)
        xs = np.sort(b)
        ccdf = 1.0 - np.arange(len(xs)) / len(xs)
        axC.plot(xs, ccdf, lw=1.6, color=col, alpha=0.9, label=label)

    # shade the over-ceiling zone: everything above the plate is the caste that broke off
    axR.axhspan(CEILING, 1e3, color="C3", alpha=0.05)
    axR.axhline(CEILING, color="0.3", ls="--", lw=1.0)
    axR.text(1.15, CEILING * 1.06, f"metabolic ceiling ≈ {CEILING} kg",
             fontsize=8.5, color="0.3", va="bottom")
    axR.text(1.15, 40, "over-ceiling stratum\n(the caste)", fontsize=8.2,
             color="C3", va="top", ha="left", alpha=0.85)
    axR.set_xscale("log")
    axR.set_yscale("log")
    axR.set_xlabel("rank (heaviest = 1)")
    axR.set_ylabel("body mass (kg)")
    axR.set_title("A. Rank–size: a ceiling plate + a discrete stratum, not a Pareto line",
                  fontsize=10.5)
    axR.legend(loc="lower left", fontsize=8.2)
    axR.grid(True, which="both", ls=":", lw=0.4, alpha=0.5)
    axR.text(0.97, 0.95,
             "a smooth power law\nwould be a straight\ndescending line —\nhere: flat plate\n+ a broken-off spike",
             transform=axR.transAxes, fontsize=8.2, va="top", ha="right",
             bbox=dict(boxstyle="round", fc="white", ec="0.6", alpha=0.9))

    axC.axvline(CEILING, color="0.3", ls="--", lw=1.0)
    axC.set_xscale("log")
    axC.set_yscale("log")
    axC.set_xlabel("body mass x (kg)")
    axC.set_ylabel("P(body ≥ x)")
    axC.set_title("B. CCDF: the tail is a step off the ceiling, not a slope", fontsize=10.5)
    axC.legend(loc="lower left", fontsize=8.2)
    axC.grid(True, which="both", ls=":", lw=0.4, alpha=0.5)

    fig.suptitle("Appropriation does not reproduce Pareto's 80/20: a conservative substrate "
                 "with a metabolic ceiling\nforces concentration into a caste (ceiling + "
                 "break-off), not a continuous gradient",
                 fontsize=11.5, y=1.03)
    fig.tight_layout()
    out = os.path.join(OUTDIR, "tail_ranksize.png")
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
#  Figure 2 — K-window                                                         #
# --------------------------------------------------------------------------- #
def figure_kwindow(seed=SEED):
    Ks, top5, evgini, nev = [], [], [], []
    for K in K_GRID:
        w, _ = run_sphere(regime="deceptive", radius=0.0, K=K, lag=1, seed=seed)
        ne, _nc, t5 = eviction_concentration(w)
        from collections import Counter
        counts = sorted(Counter(c for (_t, _o, c, _s) in w._evictions).values(), reverse=True)
        Ks.append(K)
        nev.append(ne)
        top5.append(t5 if ne else np.nan)
        evgini.append(gini(counts) if counts else np.nan)

    Ks = np.array(Ks, float)
    top5 = np.array(top5, float)
    evgini = np.array(evgini, float)
    nev = np.array(nev, float)

    # window: from first K where eviction concentrates to K_off (first K with zero evictions)
    k_off = next((k for k, n in zip(Ks, nev) if n == 0), None)
    # "thin-denominator" edge: where evictions drop below ~500 (top5 becomes unreliable)
    thin = nev < 500

    fig, ax = plt.subplots(figsize=(9.5, 5.6))

    # shaded window up to K_off
    if k_off is not None:
        ax.axvspan(Ks[nev > 0].min(), k_off, color="C0", alpha=0.06)
        ax.axvline(k_off, color="0.3", ls="--", lw=1.1)
        ax.text(k_off + 0.6, 0.05, f"K_off = {k_off:.0f}\n(budget stops binding)",
                fontsize=8.5, color="0.3", va="bottom")

    # evict-Gini: the load-bearing metric (solid, full alpha)
    ax.plot(Ks, evgini, "-o", color="C3", lw=1.9, ms=5, label="eviction Gini (load-bearing)")

    # top-5 share: solid where dense, faded where thin denominator
    ax.plot(Ks[~thin], top5[~thin], "-s", color="C0", lw=1.6, ms=4.5,
            label="top-5 cell share (dense evictions)")
    ax.plot(Ks[thin], top5[thin], ":s", color="C0", lw=1.2, ms=4.5, alpha=0.45,
            label="top-5 share (thin denominator — unreliable)")

    ax.set_xlabel("attention budget K (memory slots)")
    ax.set_ylabel("eviction concentration")
    ax.set_title("Attention scarcity is a dose curve with a finite window, not a flat NULL",
                 fontsize=11)
    ax.set_ylim(0, 1.0)
    ax.grid(True, ls=":", lw=0.4, alpha=0.5)
    ax.legend(loc="upper left", fontsize=8.6)

    # annotate the two regimes
    ax.text(0.30, 0.14,
            "hard scarcity (small K):\nforgetting is egalitarian → flat",
            transform=ax.transAxes, fontsize=8.4, va="bottom",
            bbox=dict(boxstyle="round", fc="white", ec="0.6", alpha=0.9))
    ax.text(0.50, 0.72,
            "soft scarcity (K near memory size):\nforgetting is selective → concentrated",
            transform=ax.transAxes, fontsize=8.4, va="bottom",
            bbox=dict(boxstyle="round", fc="white", ec="0.6", alpha=0.9))

    fig.suptitle("mod-20 revisited: the 'third NULL' on attention was partly the narrow K "
                 "range — concentration lives\nin a window near the natural memory size, then "
                 "the mechanism switches off",
                 fontsize=10.5, y=1.02)
    fig.tight_layout()
    out = os.path.join(OUTDIR, "kwindow.png")
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    print("=" * 78)
    print("GRADIENT FIGURES (viz Phase 4B) — read-only book figures over the closed tower.")
    print(f"seed {args.seed}; style matches sim_portfolio / sim_pareto (Agg, dpi 140).")
    print("=" * 78)
    f1 = figure_tail(args.seed)
    print(f"figure 1 written: {f1}")
    f2 = figure_kwindow(args.seed)
    print(f"figure 2 written: {f2}")
    print("\nBoth read run_appropriation / run_sphere read-only; canon untouched. ✓")


if __name__ == "__main__":
    main()
