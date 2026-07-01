"""
sim_synthesis.py — the keystone (module 28): all three property verbs at once.

The property arc built three independent verbs, each tested in ISOLATION on the module-23
appropriating baseline (claim, rho=0.5), every other seam off:

  * inheritance (25) — a dead owner's cells pass to a living bloodline heir (persistence in
    time);
  * exclusion (26) — an owner bars a non-owner from its occupied cell (a movement-layer
    denial);
  * trade (27) — the richest living agent present buys a deed from its (living) holder (the
    first liquidity).

Each was deliberately built as an OFF-switchable seam that composes with the frozen kernel,
and each prior module hardwired the OTHER two off so the verb under test stood alone. This
module removes that hardwiring and turns all three ON together — the keystone that closes
the arch. The empirical question is emergent, not additive: inheritance keeps deeds alive
past death, a market lets the rich buy those persistent deeds, and exclusion lets an owner
monopolise the cell it stands on. Do the three verbs COMPOUND (a self-reinforcing dynastic
market that concentrates far past any verb alone), or do they interfere / wash out?

`SynthesisWorld(TradeWorld)` inherits the whole cumulative stack. TradeWorld hardwires
`exclusion=False` in its own super() call (module 27 tested trade with denial off); the ONE
structural move here is to un-hardwire that — a POST-INIT flip of `self.exclusion` /
`self.exclude_mode` after `super().__init__()` returns, since TradeWorld's ctor neither
accepts nor forwards those. Every seam already reads its flag live (the ExcludingAdapter
checks `world.exclusion` at apply time; `_do_claims` branches on `heritable`; the post-step
`_do_trades` on `trade`), so no `step()` override is needed — the composition falls out of
the three gated seams the parents already installed. With all flags off, SynthesisWorld is
byte-identical to the canon (B0) and to the module-23 self-check (B1), exactly as every
parent is: nothing new runs when nothing is turned on.

Battery: the 2^3 cross-product of {h(eritable), x(exclusion, occupied), t(rade, market)} on
the property base (claim, rho=0.5, salience off), both arenas (open / box6), averaged over 5
seeds (7-11) so the direction is not a single-seed artifact. Conservation: inheritance is a
pure ledger op, exclusion turns a move into a stay (zero mass), and the market's only mass
move is a paired body->body payment — so `matter_drift < 1e-9` at every config, asserted per
run. Pure stdlib + numpy; no network; import side-effect-free.
"""

from __future__ import annotations

import hashlib

import numpy as np

from sim_eventlog import EventLog, SEED
from sim_comm import R, C, DAYS
from sim_sphere import GRID_DIAG, CANON_COMM
from sim_salience import RAD, KK, LAG, FEW, W_INJ, AMT
from sim_appropriation import appropriation_fingerprint, ownership_metrics, RHO, BOX
from sim_institution import APPROP_FP
from sim_trade import TradeWorld, PRICE_FRAC

SEEDS = (7, 8, 9, 10, 11)               # the 5-seed sweep for the main cross-product


class SynthesisWorld(TradeWorld):
    """TradeWorld with the exclusion seam un-hardwired, so all three property verbs
    (inheritance x exclusion x trade) can run at once. With every flag off it is a true
    no-op — byte-identical to the parent chain and to the canon."""

    def __init__(self, log, seed=SEED, regime="deceptive",
                 radius=GRID_DIAG + 1.0, K=None, lag=0,
                 injection_strength=0.0, injectors=0, inject_amount=50.0,
                 decay=1.0, target_policy="decoy",
                 arena_side=None, pin_victims_only=False,
                 appropriation=0.0, owner_policy="founders", owners=FEW,
                 sigma=0.0, enforce=False, enforcers=3,
                 heritable=False, heir_fallback="revert",
                 exclusion=False, exclude_mode="occupied",
                 trade=False, trade_mode="market", price_frac=PRICE_FRAC):
        super().__init__(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                         injection_strength=injection_strength, injectors=injectors,
                         inject_amount=inject_amount, decay=decay,
                         target_policy=target_policy, arena_side=arena_side,
                         pin_victims_only=pin_victims_only, appropriation=appropriation,
                         owner_policy=owner_policy, owners=owners, sigma=sigma,
                         enforce=enforce, enforcers=enforcers, heritable=heritable,
                         heir_fallback=heir_fallback, trade=trade, trade_mode=trade_mode,
                         price_frac=price_frac)
        # TradeWorld hardwired exclusion=False in the super() call above; un-hardwire it.
        # The ExcludingAdapter is already installed and reads world.exclusion live, so this
        # post-init flip is all that is needed to activate the denial seam.
        self.exclusion = bool(exclusion)
        self.exclude_mode = exclude_mode


# --------------------------------------------------------------------------- #
#  Running + fingerprint + metrics                                             #
# --------------------------------------------------------------------------- #
def run_synthesis(heritable=False, heir_fallback="revert",
                  exclusion=False, exclude_mode="occupied",
                  trade=False, trade_mode="market", price_frac=PRICE_FRAC,
                  owner_policy="claim", arena_side=None, appropriation=RHO,
                  injection_strength=0.0, injectors=0, sigma=0.0,
                  regime="deceptive", radius=RAD, K=KK, lag=LAG, inject_amount=AMT,
                  decay=1.0, target_policy="decoy", seed=SEED, days=DAYS):
    log = EventLog()
    w = SynthesisWorld(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                       injection_strength=injection_strength, injectors=injectors,
                       inject_amount=inject_amount, decay=decay,
                       target_policy=target_policy, arena_side=arena_side,
                       appropriation=appropriation, owner_policy=owner_policy, owners=FEW,
                       sigma=sigma, heritable=heritable, heir_fallback=heir_fallback,
                       exclusion=exclusion, exclude_mode=exclude_mode,
                       trade=trade, trade_mode=trade_mode, price_frac=price_frac)
    for _ in range(days):
        w.step()
    return w, log


def synth_fingerprint(w):
    """Canonical module-28 digest (verbatim from the delivery log): the state fingerprint,
    then the two normally-off verb flags/counters, then the sorted deed ledger. It composes
    on state_fingerprint (not the parent verb fp), so all-off reduces cleanly to the canon."""
    h = hashlib.sha256()
    h.update(w.state_fingerprint().encode())
    h.update((f"|H{int(getattr(w, 'heritable', False))}"
              f"|X{int(w.exclusion)}:{w.exclude_mode}"
              f"|T{int(w.trade)}:{w.trade_mode}"
              f"|traded{w._traded}|excl{w._excluded_moves}"
              f"|cells{len(w._cell_owner)}").encode())
    for cell, oid in sorted(w._cell_owner.items()):
        h.update(f"{cell[0]},{cell[1]}={oid}".encode())
    return h.hexdigest()[:16]


def synthesis_metrics(w):
    om = ownership_metrics(w)
    return {
        "alive": len(w.pop),
        "total_biomass": sum(a.body for a in w.pop),
        "owner_gap": om["owner_gap"],
        "owner_share": om["owner_bio_share"],
        "terr_gini": om["territory_gini"],
        "n_owners": om["n_owners"],
        "n_owned": om["n_owned_cells"],
        "excluded_moves": w._excluded_moves,
        "traded": w._traded,
        "trade_volume": w._trade_volume,
    }


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
def _fmt(v, fmt="{:.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def _mean(vals):
    vals = [v for v in vals if not (isinstance(v, float) and v != v)]
    return float(np.mean(vals)) if vals else float("nan")


def main():
    line = "=" * 78
    print(line)
    print("SYNTHESIS — the keystone: inheritance x exclusion x trade, all three at once.")
    print("SynthesisWorld(TradeWorld) un-hardwires the exclusion seam (post-init flip) so the")
    print("three property verbs run together on the appropriating base. Each was tested alone")
    print("with the others off; here they compound — does a dynastic, exclusionary market")
    print(f"concentrate past any single verb, or do they interfere? grid {R}x{C}; {DAYS}d; "
          f"claim, rho={RHO}; seeds {SEEDS}.")
    print(line)

    max_drift = 0.0

    # --- B0: all verbs off + all-off == canon (both policies) --------------- #
    for pol in ("founders", "claim"):
        w0, _ = run_synthesis(heritable=False, exclusion=False, trade=False,
                              appropriation=0.0, owner_policy=pol,
                              radius=GRID_DIAG + 1.0, K=None, lag=0,
                              injection_strength=0.0, injectors=0, arena_side=None)
        fp = w0.state_fingerprint(); max_drift = max(max_drift, w0.matter_drift())
        ok = (fp == CANON_COMM and w0._excluded_moves == 0 and w0._traded == 0
              and not w0._house)
        print(f"B0  all-verbs-off all-off [{pol:<8}] : {fp} vs canon {CANON_COMM} -> "
              f"{'BYTE-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
        assert ok, f"B0 [{pol}] not byte-identical to canon / a seam fired when off"

    # --- B1: all verbs off at the appropriation headline (founders -> the fp) - #
    wb1, _ = run_synthesis(heritable=False, exclusion=False, trade=False,
                           appropriation=RHO, owner_policy="founders", arena_side=BOX,
                           injection_strength=W_INJ, injectors=FEW)
    fpb1 = appropriation_fingerprint(wb1); okb1 = fpb1 == APPROP_FP
    print(f"B1  all-verbs-off approp-headline (founders)   : {fpb1} vs {APPROP_FP} -> "
          f"{'BYTE-IDENTICAL ✓' if okb1 else 'MISMATCH ✗'}")
    assert okb1, "B1 not byte-identical to module-23 self-check (parent drift!)"

    # --- main cross-product: 2^3 verbs x 2 arenas, mean over 5 seeds --------- #
    print(f"\nMAIN (claim, rho={RHO}, salience off); the 2^3 verb cross-product, "
          f"mean over seeds {SEEDS}:")
    hdr = f"{'hxt':>4}{'arena':>6}{'alive':>7}{'totBio':>8}{'ownGap':>9}{'ownShr':>8}" \
          f"{'terrGini':>9}{'nOwn':>6}{'exMov':>7}{'traded':>7}{'drift':>9}"
    print(hdr); print("-" * len(hdr))
    combos = [(h, x, t) for h in (0, 1) for x in (0, 1) for t in (0, 1)]
    rows = {}
    for arena in (None, BOX):
        for (h, x, t) in combos:
            agg = {k: [] for k in ("alive", "total_biomass", "owner_gap", "owner_share",
                                   "terr_gini", "n_owners", "excluded_moves", "traded")}
            run_max = 0.0
            for sd in SEEDS:
                w, _ = run_synthesis(heritable=bool(h), exclusion=bool(x),
                                     exclude_mode="occupied", trade=bool(t),
                                     trade_mode="market", owner_policy="claim",
                                     arena_side=arena, injection_strength=0.0, injectors=0,
                                     seed=sd)
                d = w.matter_drift(); max_drift = max(max_drift, d); run_max = max(run_max, d)
                assert d < 1e-9, f"leak h={h} x={x} t={t} arena={arena} seed={sd}: {d}"
                m = synthesis_metrics(w)
                for k in agg:
                    agg[k].append(m[k])
            code = f"{'h' if h else '-'}{'x' if x else '-'}{'t' if t else '-'}"
            am = {k: _mean(v) for k, v in agg.items()}
            rows[(code, arena)] = am
            print(f"{code:>4}{str(arena or '-'):>6}{am['alive']:>7.1f}"
                  f"{_fmt(am['total_biomass'], '{:.0f}'):>8}"
                  f"{_fmt(am['owner_gap'], '{:+.2f}'):>9}{_fmt(am['owner_share']):>8}"
                  f"{_fmt(am['terr_gini']):>9}{am['n_owners']:>6.1f}"
                  f"{am['excluded_moves']:>7.0f}{am['traded']:>7.1f}{run_max:>9.1e}")

    # --- self-check fingerprint (in-process; verify_all adds cross-process) --- #
    wf, _ = run_synthesis(heritable=True, exclusion=True, exclude_mode="occupied",
                          trade=True, trade_mode="market", owner_policy="claim",
                          arena_side=BOX, injection_strength=0.0, injectors=0, seed=SEED)
    f1 = synth_fingerprint(wf)
    wf2, _ = run_synthesis(heritable=True, exclusion=True, exclude_mode="occupied",
                           trade=True, trade_mode="market", owner_policy="claim",
                           arena_side=BOX, injection_strength=0.0, injectors=0, seed=SEED)
    f2 = synth_fingerprint(wf2)
    max_drift = max(max_drift, wf.matter_drift())
    print(f"\nSYNTH_FINGERPRINT (HXT box{BOX}, seed {SEED}): {f1}")
    print(f"self-check (recompute): {f2} -> "
          f"{'BIT-IDENTICAL ✓' if f1 == f2 else 'MISMATCH ✗'}")
    assert f1 == f2, "synthesis run is not reproducible"
    print(f"max matter drift across battery: {max_drift:.2e} kg")
    assert max_drift < 1e-9, "a config leaked matter"

    # --- honest verdict (box6: none vs each-alone vs all-three) ------------- #
    none_b = rows[("---", BOX)]
    all_b = rows[("hxt", BOX)]
    alone = {"h": rows[("h--", BOX)], "x": rows[("-x-", BOX)], "t": rows[("--t", BOX)]}
    print(f"\n{line}")

    def dshare(a, b):
        return (a["owner_share"] or 0) - (b["owner_share"] or 0)

    best_alone_share = max(dshare(alone[k], none_b) for k in alone)
    all_share_lift = dshare(all_b, none_b)
    compounds = all_share_lift > best_alone_share + 0.02
    base_none, base_all = none_b["alive"], all_b["alive"]
    costs_base = base_all < base_none - 0.5
    print("E — do the three verbs COMPOUND beyond any one alone (box6, vs the rho=0.5 base)?")
    print(f"   owner share : base(---) {_fmt(none_b['owner_share'])} -> "
          f"h {_fmt(alone['h']['owner_share'])} / x {_fmt(alone['x']['owner_share'])} / "
          f"t {_fmt(alone['t']['owner_share'])} -> ALL(hxt) {_fmt(all_b['owner_share'])}")
    print(f"   owner gap   : base {_fmt(none_b['owner_gap'], '{:+.2f}')} -> "
          f"ALL {_fmt(all_b['owner_gap'], '{:+.2f}')} (kg)")
    print(f"   terr Gini   : base {_fmt(none_b['terr_gini'])} -> ALL {_fmt(all_b['terr_gini'])}; "
          f"n_owners base {none_b['n_owners']:.1f} -> ALL {all_b['n_owners']:.1f}")
    print(f"   alive       : base {base_none:.1f} -> ALL {base_all:.1f} "
          f"(does the compounded stratum cost the base?)")
    print(f"   activity    : ALL(hxt) exMoves {all_b['excluded_moves']:.0f}, "
          f"traded {all_b['traded']:.1f} deeds")
    print(line)
    if compounds:
        print("VERDICT — THE VERBS COMPOUND: run together, inheritance x exclusion x trade lift")
        print(f"the owner class's biomass share ({_fmt(none_b['owner_share'])}->"
              f"{_fmt(all_b['owner_share'])}) further than the strongest single verb "
              f"(+{best_alone_share:.3f}) manages alone (+{all_share_lift:.3f} combined).")
        print("Persistent (heritable) deeds give the market something durable to concentrate,")
        print("and exclusion lets the accumulating owner eat the freed share — a self-reinforcing")
        print("dynastic market, the keystone the isolated verbs only hinted at.")
    else:
        print("VERDICT — the verbs do NOT clearly compound at this scale: run together they")
        print(f"lift the owner share to {_fmt(all_b['owner_share'])} (+{all_share_lift:.3f}), no")
        print(f"more than the strongest verb alone (+{best_alone_share:.3f}). On a conserved")
        print("substrate with room to flee, liquidity + heredity + denial interfere as much as")
        print("they stack — concentration stays bounded by the same escape valve as the parts.")
    if costs_base:
        print(f"CAPACITY COST — the compounded stratum thins the base (alive {base_none:.1f}->"
              f"{base_all:.1f}): the market's known cost dominates, denial and heredity do not")
        print("rescue it. Matter conserved; the lost living biomass returns to the substrate.")
    else:
        print(f"Base roughly intact under the full stack (alive {base_none:.1f}->{base_all:.1f}).")
    print("Inheritance is pure ledger, a denied move is a stay, the price is a paired body->body")
    print(f"transfer; matter conserved (<1e-9, max {max_drift:.1e}); all-off reproduces canon &")
    print(f"module 23 byte-for-byte. seeds {SEEDS}  ✓")


if __name__ == "__main__":
    main()
