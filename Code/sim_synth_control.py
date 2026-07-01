"""
sim_synth_control.py — the isolation control behind module 28's keystone claim.

sim_synthesis.py reports the 2^3 verb cross-product as a mean over the 5-seed sweep; this
driver is the control that makes the "compound or interfere?" verdict auditable: it holds
each verb up ALONE against the all-three stack and against the property baseline, per seed
and in aggregate (mean +/- spread), so the direction is visibly robust (or not) rather than
resting on one averaged row. It is the module-28 analogue of the offline sweeps that backed
the 5-seed headlines of the property arc — a standalone analysis script, deliberately NOT in
verify_all's MODULES tuple (like run_focal_claude.py / run_cohort_ollama.py): it consumes the
same SynthesisWorld, adds no new simulation law, and asserts the same conservation bound.

The control contrasts, on the property base (claim, rho=0.5, salience off), box6:
  * baseline   (---) : no verb — the rho=0.5 tribute stratum alone;
  * each alone (h--/-x-/--t) : one verb on the baseline (what every prior module measured);
  * all three  (hxt) : the keystone.
The reported effect is the owner-class biomass-share lift over baseline: does hxt clear the
best single verb by a margin that holds across seeds 7-11? Pure stdlib + numpy; no network.
"""

from __future__ import annotations

import numpy as np

from sim_appropriation import BOX
from sim_synthesis import run_synthesis, synthesis_metrics, SEEDS

CONTROL = [("---", 0, 0, 0), ("h--", 1, 0, 0), ("-x-", 0, 1, 0), ("--t", 0, 0, 1),
           ("hxt", 1, 1, 1)]


def _stat(vals):
    a = np.array([v for v in vals if not (isinstance(v, float) and v != v)], dtype=float)
    return (float(a.mean()), float(a.std())) if a.size else (float("nan"), float("nan"))


def sweep(arena):
    """Return {code: {seed: metrics}} for the control configs at one arena."""
    out = {}
    max_drift = 0.0
    for code, h, x, t in CONTROL:
        out[code] = {}
        for sd in SEEDS:
            w, _ = run_synthesis(heritable=bool(h), exclusion=bool(x), exclude_mode="occupied",
                                 trade=bool(t), trade_mode="market", owner_policy="claim",
                                 arena_side=arena, injection_strength=0.0, injectors=0, seed=sd)
            d = w.matter_drift(); max_drift = max(max_drift, d)
            assert d < 1e-9, f"leak {code} arena={arena} seed={sd}: {d}"
            out[code][sd] = synthesis_metrics(w)
    return out, max_drift


def main():
    line = "=" * 78
    print(line)
    print("SYNTHESIS CONTROL — each property verb alone vs all three, per seed (box6, claim,")
    print(f"rho=0.5, salience off). Effect = owner biomass-share lift over the (---) baseline.")
    print(f"seeds {SEEDS}")
    print(line)

    data, max_drift = sweep(BOX)

    # per-seed owner_share table
    print(f"\nowner_share by seed:")
    print(f"  {'code':>5}" + "".join(f"{f's{sd}':>8}" for sd in SEEDS) + f"{'mean':>8}{'std':>7}")
    means = {}
    for code, *_ in CONTROL:
        shares = [data[code][sd]["owner_share"] for sd in SEEDS]
        mu, sd_ = _stat(shares)
        means[code] = mu
        print(f"  {code:>5}" + "".join(f"{s:>8.3f}" for s in shares) + f"{mu:>8.3f}{sd_:>7.3f}")

    base = means["---"]
    lifts = {c: means[c] - base for c in ("h--", "-x-", "--t", "hxt")}
    best_alone = max(lifts["h--"], lifts["-x-"], lifts["--t"])
    all_lift = lifts["hxt"]

    # per-seed margin (hxt lift minus best-single-verb lift), to see robustness
    print(f"\nrobustness — per-seed (hxt - best single verb) owner_share lift over baseline:")
    margins = []
    for sd in SEEDS:
        b = data["---"][sd]["owner_share"]
        singles = [data[c][sd]["owner_share"] - b for c in ("h--", "-x-", "--t")]
        m = (data["hxt"][sd]["owner_share"] - b) - max(singles)
        margins.append(m)
    print("  " + "".join(f"{f's{sd}':>8}" for sd in SEEDS))
    print("  " + "".join(f"{m:>8.3f}" for m in margins))
    frac_pos = sum(1 for m in margins if m > 0) / len(margins)

    print(f"\n{line}")
    print(f"baseline owner_share {base:.3f}; best single-verb lift +{best_alone:.3f}; "
          f"all-three lift +{all_lift:.3f}")
    print(f"all-three clears best-single in {frac_pos*100:.0f}% of seeds "
          f"(margin mean {np.mean(margins):+.3f})")
    if all_lift > best_alone + 0.02 and frac_pos >= 0.6:
        print("CONTROL VERDICT — COMPOUND is robust: the stack beats every verb alone across")
        print("a majority of seeds, not just in the averaged row.")
    else:
        print("CONTROL VERDICT — NO robust compounding: the all-three lift does not durably")
        print("exceed the strongest single verb; the averaged headline is not seed-robust.")
    print(f"matter conserved across the control sweep (<1e-9, max {max_drift:.1e} kg). "
          f"seeds {SEEDS}  ✓")


if __name__ == "__main__":
    main()
