"""
sim_trade.py — transfer of ownership between the LIVING (module 27): does a market
concentrate, or does liquidity dissolve the stratum?

The property arc so far moved a deed only in two ways: it is CLAIMED from the commons
(23) and, on the owner's death, it REVERTS or passes to an heir (25). What it never did
is move between two *living* agents by their own wealth. That is the last obvious verb of
property — a market — and it is also the first piece of *liquidity* in the whole tower.

The open question the prior arc leaves: appropriation (23) builds an owner WEALTH stratum;
inheritance (25) makes it persist; exclusion (26) only disperses. Voluntary exchange could
go either way. The rich can buy up land and compound future tribute → CONCENTRATION; but
the rich pay the (poorer) seller on the spot → an immediate EQUALIZING flow. Which wins
over 300 days is exactly the empirical question — there is no ground truth, only the run.

`TradeWorld(ExclusionWorld)` keeps the chain cumulative with every upper layer inert by
default (exclusion=off, heritable=off, sigma=0). The market lives at a POST-STEP ownership
seam, not at grazing (grazing is inline in the frozen `sim_comm.step`) and not at movement
(that is exclusion's adapter). Mirroring appropriation's own `step()` discipline:

    def step(self):
        super().step()                 # base + claims + tribute, unchanged
        if self.trade: self._do_trades()   # gated: trade=off -> byte-identical parent

`_do_trades()` (claim policy, rho>0, so a per-cell ledger `_cell_owner` exists):
  * iterate owned cells in sorted order (deterministic);
  * the SELLER is the cell's current deed-holder (alive — `_do_claims` already pruned dead
    owners this tick — and possibly standing elsewhere: you buy the plot from its remote
    owner);
  * the BUYER pool is the agents physically ON that cell who are not the seller; the buyer
    is the richest of them (tie -> lowest oid);
  * a trade fires only if the buyer is strictly richer than the seller (`buyer.body >
    seller.body`) — "the rich buy up land", the concentrating direction under test;
  * MARKET (`price_frac>0`): the buyer pays `price = price_frac * buyer.body` body->body to
    the seller and the deed moves: `_cell_owner[cell] = buyer.oid`. price_frac<=1 keeps the
    buyer's body >= 0; the payment moves mass only between two living bodies -> conserved;
  * GIFT (`price_frac==0`): identical buyer-selection and deed move, but price=0 — isolates
    the PURE territory reshuffle (deeds drift to the locally-richest) with zero body moved,
    a clean control whose contrast with market is exactly the effect of the wealth payment;
  * one transaction per cell per tick (each cell is visited once); counters `_traded`,
    `_trade_volume` (kg moved). Under founders there is no per-cell ledger -> the seam is
    inert (noted, not headlined), exactly as for exclusion/inheritance.

trade=False is a true no-op (`step()` == parent), and the battery turns exclusion OFF, so
trade is tested in isolation on the module-23 property baseline (claim, rho=0.5) — the same
discipline used for every prior verb. Conservation: a single paired `buyer.body -= price;
seller.body += price` changes the total by exactly zero, so matter_drift stays the parent's
(< 1e-9). Pure stdlib + numpy; no network; import side-effect-free.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

import numpy as np

from sim_eventlog import EventLog, SEED
from sim_comm import R, C, DAYS, run as run_comm
from sim_sphere import GRID_DIAG, CANON_COMM
from sim_salience import RAD, KK, LAG, FEW, W_INJ, AMT
from sim_appropriation import appropriation_fingerprint, ownership_metrics, RHO, BOX
from sim_institution import APPROP_FP
from sim_inheritance import InheritanceWorld
from sim_exclusion import ExclusionWorld

PRICE_FRAC = 0.25                       # market headline: buyer pays 25% of its body


class TradeWorld(ExclusionWorld):
    """ExclusionWorld where a living agent buys an owned cell from its (living) deed-holder.
    trade=False is a true no-op (the post-step seam never runs -> byte-identical parent)."""

    def __init__(self, log, seed=SEED, regime="deceptive",
                 radius=GRID_DIAG + 1.0, K=None, lag=0,
                 injection_strength=0.0, injectors=0, inject_amount=50.0,
                 decay=1.0, target_policy="decoy",
                 arena_side=None, pin_victims_only=False,
                 appropriation=0.0, owner_policy="founders", owners=FEW,
                 sigma=0.0, enforce=False, enforcers=3,
                 heritable=False, heir_fallback="revert",
                 trade=False, trade_mode="market", price_frac=PRICE_FRAC):
        self.trade = bool(trade)
        self.trade_mode = trade_mode
        # gift == zero-price market; the mode label drives the headline price.
        self.price_frac = 0.0 if trade_mode == "gift" else float(price_frac)
        self._traded = 0
        self._trade_volume = 0.0
        super().__init__(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                         injection_strength=injection_strength, injectors=injectors,
                         inject_amount=inject_amount, decay=decay,
                         target_policy=target_policy, arena_side=arena_side,
                         pin_victims_only=pin_victims_only, appropriation=appropriation,
                         owner_policy=owner_policy, owners=owners, sigma=sigma,
                         enforce=enforce, enforcers=enforcers, heritable=heritable,
                         heir_fallback=heir_fallback, exclusion=False)

    # ---- the market seam --------------------------------------------------- #
    def _do_trades(self):
        """Move deeds (and, in market mode, body) between living agents. Pure ownership
        ledger + a conservative body->body payment; deterministic in cell/oid order."""
        if not self._cell_owner:
            return
        by_oid = {a.oid: a for a in self.pop}
        on_cell = defaultdict(list)
        for a in self.pop:
            on_cell[(a.i, a.j)].append(a)
        pf = self.price_frac
        for cell in sorted(self._cell_owner):
            seller_oid = self._cell_owner[cell]
            seller = by_oid.get(seller_oid)
            if seller is None:                       # deed-holder not alive -> skip (safety)
                continue
            cands = [a for a in on_cell.get(cell, ()) if a.oid != seller_oid]
            if not cands:
                continue                             # no prospective buyer present
            buyer = sorted(cands, key=lambda a: (-a.body, a.oid))[0]
            if buyer.body <= seller.body:
                continue                             # only the richer-than-owner buys in
            price = pf * buyer.body                  # pf<=1 -> buyer.body stays >= 0
            if price > 0.0:
                buyer.body -= price
                seller.body += price                 # paired -> exactly conservative
                self._trade_volume += price
            self._cell_owner[cell] = buyer.oid       # deed transfers (free in gift mode)
            self._traded += 1

    def step(self):
        super().step()
        if self.trade:
            self._do_trades()                        # OFF: byte-identical to parent


# --------------------------------------------------------------------------- #
#  Running + fingerprint + metrics                                             #
# --------------------------------------------------------------------------- #
def run_trade(trade=False, trade_mode="market", price_frac=PRICE_FRAC,
              owner_policy="claim", arena_side=None, appropriation=RHO,
              injection_strength=0.0, injectors=0, sigma=0.0, heritable=False,
              regime="deceptive", radius=RAD, K=KK, lag=LAG, inject_amount=AMT,
              decay=1.0, target_policy="decoy", seed=SEED, days=DAYS):
    log = EventLog()
    w = TradeWorld(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                   injection_strength=injection_strength, injectors=injectors,
                   inject_amount=inject_amount, decay=decay,
                   target_policy=target_policy, arena_side=arena_side,
                   appropriation=appropriation, owner_policy=owner_policy, owners=FEW,
                   sigma=sigma, heritable=heritable,
                   trade=trade, trade_mode=trade_mode, price_frac=price_frac)
    for _ in range(days):
        w.step()
    return w, log


def trade_fingerprint(w):
    h = hashlib.sha256()
    h.update(w.state_fingerprint().encode())
    h.update((f"|trade{int(w.trade)}|{w.trade_mode}|pf{w.price_frac:.6f}"
              f"|traded{w._traded}|vol{w._trade_volume:.6f}"
              f"|cells{len(w._cell_owner)}").encode())
    for cell, oid in sorted(w._cell_owner.items()):
        h.update(f"{cell[0]},{cell[1]}={oid}".encode())
    return h.hexdigest()[:16]


def trade_metrics(w):
    om = ownership_metrics(w)
    return {
        "alive": len(w.pop),
        "total_biomass": sum(a.body for a in w.pop),
        "owner_gap": om["owner_gap"],
        "owner_share": om["owner_bio_share"],
        "terr_gini": om["territory_gini"],
        "n_owners": om["n_owners"],
        "n_owned": om["n_owned_cells"],
        "traded": w._traded,
        "trade_volume": w._trade_volume,
    }


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
def _fmt(v, fmt="{:.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def main():
    line = "=" * 78
    print(line)
    print("TRADE — ownership moves between the living: market concentrates, or liquidity")
    print("dissolves the stratum? TradeWorld(ExclusionWorld): a post-step seam where the")
    print("richest buyer present on an owned cell buys the deed from its (living) holder.")
    print("MARKET pays price_frac*body holder<-buyer (rich->seller, but the DEED -> rich);")
    print(f"GIFT moves only the deed (zero body). grid {R}x{C}; seed {SEED}; {DAYS}d; "
          f"claim, rho={RHO}.")
    print(line)

    max_drift = 0.0

    # --- B0: trade off + all-off == canon (both policies) ------------------- #
    for pol in ("founders", "claim"):
        w0, _ = run_trade(trade=False, appropriation=0.0, owner_policy=pol,
                          radius=GRID_DIAG + 1.0, K=None, lag=0,
                          injection_strength=0.0, injectors=0, arena_side=None)
        fp = w0.state_fingerprint(); max_drift = max(max_drift, w0.matter_drift())
        ok = fp == CANON_COMM and w0._traded == 0
        print(f"B0  trade=off all-off [{pol:<8}] : {fp} vs canon {CANON_COMM} -> "
              f"{'BYTE-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
        assert ok, f"B0 [{pol}] not byte-identical to canon / nonzero trades"

    # --- B1: trade off at the appropriation headline (founders -> the fp) ---- #
    wb1, _ = run_trade(trade=False, appropriation=RHO, owner_policy="founders",
                       arena_side=BOX, injection_strength=W_INJ, injectors=FEW)
    fpb1 = appropriation_fingerprint(wb1); okb1 = fpb1 == APPROP_FP
    print(f"B1  trade=off approp-headline (founders)   : {fpb1} vs {APPROP_FP} -> "
          f"{'BYTE-IDENTICAL ✓' if okb1 else 'MISMATCH ✗'}")
    assert okb1, "B1 not byte-identical to module-23 self-check (parent drift!)"

    # --- main cross-product (claim, rho=0.5) -------------------------------- #
    print(f"\nMAIN (claim, rho={RHO}); does the market concentrate land/biomass vs gift?")
    hdr = f"{'mode':>9}{'arena':>6}{'alive':>7}{'totBio':>8}{'ownGap':>9}{'ownShr':>8}" \
          f"{'terrGini':>9}{'nOwn':>6}{'traded':>8}{'volume':>9}{'drift':>9}"
    print(hdr); print("-" * len(hdr))
    rows = {}
    configs = [("off", None), ("off", BOX)]
    for m in ("market", "gift"):
        for arena in (None, BOX):
            configs.append((m, arena))
    for mode, arena in configs:
        w, _ = run_trade(trade=(mode != "off"),
                         trade_mode=("market" if mode == "off" else mode),
                         owner_policy="claim", arena_side=arena,
                         injection_strength=0.0, injectors=0)
        d = w.matter_drift(); max_drift = max(max_drift, d)
        assert d < 1e-9, f"leak mode={mode} arena={arena}: {d}"
        tm = trade_metrics(w)
        rows[(mode, arena)] = tm
        print(f"{mode:>9}{str(arena or '-'):>6}{tm['alive']:>7}"
              f"{_fmt(tm['total_biomass'], '{:.0f}'):>8}{_fmt(tm['owner_gap'], '{:+.2f}'):>9}"
              f"{_fmt(tm['owner_share']):>8}{_fmt(tm['terr_gini']):>9}{tm['n_owners']:>6}"
              f"{tm['traded']:>8}{_fmt(tm['trade_volume'], '{:.0f}'):>9}{d:>9.1e}")

    # --- self-check fingerprint --------------------------------------------- #
    wf, _ = run_trade(trade=True, trade_mode="market", owner_policy="claim",
                      arena_side=BOX, injection_strength=0.0, injectors=0)
    fp1 = trade_fingerprint(wf)
    wf2, _ = run_trade(trade=True, trade_mode="market", owner_policy="claim",
                       arena_side=BOX, injection_strength=0.0, injectors=0)
    fp2 = trade_fingerprint(wf2)
    max_drift = max(max_drift, wf.matter_drift())
    print(f"\nTRADE_FINGERPRINT: {fp1}")
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp1 == fp2 else 'MISMATCH ✗'}")
    assert fp1 == fp2, "trade run is not reproducible"
    print(f"max matter drift across battery: {max_drift:.2e} kg")
    assert max_drift < 1e-9, "a config leaked matter"

    # --- honest verdict ----------------------------------------------------- #
    off_o, off_b = rows[("off", None)], rows[("off", BOX)]
    mkt_o, mkt_b = rows[("market", None)], rows[("market", BOX)]
    gft_o, gft_b = rows[("gift", None)], rows[("gift", BOX)]
    print(f"\n{line}")

    def dshare(on, off):
        return (on["owner_share"] or 0) - (off["owner_share"] or 0)

    print("E — does VOLUNTARY EXCHANGE concentrate (vs the rho=0.5 tribute baseline)?")
    print(f"   territory Gini : off {_fmt(off_o['terr_gini'])}/{_fmt(off_b['terr_gini'])} "
          f"-> market {_fmt(mkt_o['terr_gini'])}/{_fmt(mkt_b['terr_gini'])} "
          f"/ gift {_fmt(gft_o['terr_gini'])}/{_fmt(gft_b['terr_gini'])} (open/box)")
    print(f"   owner gap (kg) : off {_fmt(off_o['owner_gap'], '{:+.2f}')}/"
          f"{_fmt(off_b['owner_gap'], '{:+.2f}')} -> market "
          f"{_fmt(mkt_o['owner_gap'], '{:+.2f}')}/{_fmt(mkt_b['owner_gap'], '{:+.2f}')} "
          f"/ gift {_fmt(gft_o['owner_gap'], '{:+.2f}')}/{_fmt(gft_b['owner_gap'], '{:+.2f}')}")
    print(f"   owner share    : off {_fmt(off_o['owner_share'])}/{_fmt(off_b['owner_share'])} "
          f"-> market {_fmt(mkt_o['owner_share'])}/{_fmt(mkt_b['owner_share'])} "
          f"/ gift {_fmt(gft_o['owner_share'])}/{_fmt(gft_b['owner_share'])}")
    print(f"   n_owners       : off {off_o['n_owners']}/{off_b['n_owners']} "
          f"-> market {mkt_o['n_owners']}/{mkt_b['n_owners']} "
          f"/ gift {gft_o['n_owners']}/{gft_b['n_owners']} "
          f"(fewer owners = land in fewer hands)")
    print(f"   alive          : off {off_o['alive']}/{off_b['alive']} "
          f"-> market {mkt_o['alive']}/{mkt_b['alive']} "
          f"/ gift {gft_o['alive']}/{gft_b['alive']} (does liquidity harm the base?)")
    print(f"   trades/volume  : market {mkt_o['traded']}/{_fmt(mkt_o['trade_volume'],'{:.0f}')}kg "
          f"open, {mkt_b['traded']}/{_fmt(mkt_b['trade_volume'],'{:.0f}')}kg box; "
          f"gift {gft_o['traded']}/{gft_b['traded']} deeds (zero kg)")

    # The robust signal (confirmed under the 5-seed sweep) is concentration of BIOMASS into
    # the owner CLASS (owner_share up) plus a capacity cost — NOT deed-count concentration
    # (territory Gini barely moves). This single-seed headline is suggestive; the multi-seed
    # sweep is the authoritative read on direction.
    mkt_conc_share = dshare(mkt_o, off_o) > 0.05 or dshare(mkt_b, off_b) > 0.05
    base_open, base_box = off_o["alive"], off_b["alive"]
    capacity_cost = any(rows[(m, a)]["alive"] < base for m, a, base in
                        [("market", None, base_open), ("gift", None, base_open),
                         ("market", BOX, base_box), ("gift", BOX, base_box)])
    print(f"\n{line}")
    if mkt_conc_share:
        print("VERDICT — A MARKET SHARPENS THE STRATUM (biomass), AND IT COSTS THE BASE.")
        print(f"Wealth-priced exchange raises the owner class's biomass share above the tribute")
        print(f"baseline (open {_fmt(off_o['owner_share'])}->{_fmt(mkt_o['owner_share'])}, "
              f"box {_fmt(off_b['owner_share'])}->{_fmt(mkt_b['owner_share'])}): deeds drift to the")
        print("already-rich, who then collect more tribute. Notably it concentrates BIOMASS, not")
        print(f"deed-counts — territory Gini barely moves (open {_fmt(off_o['terr_gini'])}->"
              f"{_fmt(mkt_o['terr_gini'])}) — holdings stay spread even as wealth concentrates.")
        print("The price leg (rich->seller) is a weak counter-flow, not a clean equalizer (its")
        print("sign flips by arena across seeds): the deed-drift, not the payment, is load-bearing.")
    else:
        print("VERDICT — the market churns deeds without clearly sharpening the stratum at this")
        print("seed; the 5-seed sweep is the authoritative read on direction.")
    if capacity_cost:
        print("CAPACITY COST — unlike exclusion (harmless) and like the institution's levy (but by")
        print(f"a different route), a market THINS the base: alive open {base_open}->{mkt_o['alive']}"
              f"/{gft_o['alive']}, box {base_box}->{mkt_b['alive']}/{gft_b['alive']}. Reassigning")
        print("deeds to the rich strips the poor of their one bankable stock (a claimed cell + its")
        print("tribute) and exposes them fully to the levy -> they starve faster; matter conserved,")
        print("the lost living biomass returns to the substrate. Liquidity is no equalizer here.")
    else:
        print("Base intact at this seed.")
    print(f"Payment moves mass only between living bodies; matter conserved (<1e-9, max "
          f"{max_drift:.1e}); trade=off reproduces canon & module 23 byte-for-byte. "
          f"seed {SEED}  ✓")


if __name__ == "__main__":
    main()
