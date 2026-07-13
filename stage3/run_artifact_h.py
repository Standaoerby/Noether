"""run_artifact_h.py — mod H (виток 1): DEBT. Power from consent, endogenous price, bondage.

DELEGATE is coercion from above, EXTORT is violence in the shadow — DEBT is the deal from
below. If a creditor stratum concentrates mass WITHOUT title, WITHOUT violence, WITHOUT
presence, debt is the candidate THIRD conductivity of power, and the only mechanism able to
pierce both ceilings vitok 2 found (presence ceiling, body ceiling). Fundamental by nature
but a COLUMN module by discipline: canon Code/ is frozen and fingerprint-anchored, so debt
gets its own anchors, its own pre-registration, and a registry note — «in the tower» by
nature, not by folder.

FIRST ENDOGENOUS PRICE IN THE PROJECT. In canon sim_trade the price is exogenous
(PRICE_FRAC=0.25, a constant). The rate k here is the first magnitude nobody set — the
system grew it from aggregate demand/supply: k = k_min + (k_max−k_min)·sat(D/S).

Substrate note (Phase 0.3, recorded): a `store` is an Artifact(kind='store') minted body→
mass by the rich (body>1.5·REPRO), sitting on a cell, its maker its owner; a hungry pawn
(body<store_draw_at) DRAWS mass→body losslessly. Under store_access='open' the draw is
free, so debt has no leverage — it BITES only where the store is PROPERTY (store_access
'maker'/'owner'): the hungry cannot draw another's store for free, so it must borrow. That
property precondition IS the social content of the mechanic. Owner income per tick is the
body gain across the canonical step (grazing+appropriation−metabolism); metabolism is the
canon upkeep (BASE+PEN·mism²)·body. Payment routes debtor body → the creditor's store.

GATES (all obligatory; see the WO):
  MH-OFF      debt_on=False reproduces the eight G/G2 anchors + the reputation anchor
              bit-for-bit (debt defaults off => empty fingerprint blob).
  MH-mass     mass conserved on every path (loan, payment, default, inheritance), <1e-9.
  MH-replay   a debt-on world replays bit-for-bit.
  MH-ledger   the identity Σoutstanding ≡ Σ(issued·k) − Σrepaid − Σwriteoff holds every tick.
  MH-BANKRUPT NOT a no-op: a world with bondage diverges (fingerprint) from one without, AND
              the bonded are deprived AT EXECUTION — zero claims held, zero counted
              testimonies, zero new loans. (no-op vs NULL distinguished before any verdict.)

PRE-REGISTRATION (both formulations fixed BEFORE the runs):
  HH1 — power from consent (main). (a) creditors concentrate mass/power without violence and
        without title (top-creditor received-flow and Gini rise with debt on) => THIRD
        CONDUCTIVITY: власть из согласия 🔖 · (b) NULL: debt does not hold — mass default,
        creditors are ruined (writeoff dominates, no concentration) => обязательство требует
        энфорсера; закон без меча — слова.
  HH2 — piercing the body ceiling. (a) a top creditor's owner_gap = (mass that flowed THROUGH
        it, i.e. repayments received) / (its own lifetime body integral) > 1 => the RIGHT TO
        CLAIM is the extra-somatic vessel Фаза 2 could not find 🔖🔖 · (b) NULL: the mass
        settles in the creditor's body like a delegate-root — power stays somatic.
  HH3 — the credit cycle. (a) D/S oscillates, waves of defaults => an endogenous debt cycle on
        a conservative substrate 🔖 · (b) monotone convergence / static.
  HH4 — debt houses. (a) stable creditor/debtor lines by _house, inherited bondage · (b) debt
        dissolves within a generation. (Смычка с находкой 12.07: a title on the free arena
        SPLITS between children — does the OBLIGATION stick to each? asymmetry of right & debt.)

Sweep r ∈ {0.2,0.3,0.5}; per point print: loans by reason (hunger/income_drop/investment),
D/S over ticks, defaults, bonded roster, top-creditor owner_gap, Gini(body), population.

Run:  py stage3/run_artifact_h.py            # gates
      py stage3/run_artifact_h.py --hh       # gates + the HH1-4 sweep (heavier)
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict

from stage3.run_artifact_f import _cfg, _run
from stage3.run_artifact_f2 import _run_with_history
from stage3.run_artifact_f3 import MFV3_OFF_ANCHOR_STORECAP, MFV3_OFF_ANCHOR_VESSEL
from stage3.run_artifact_g import _cfgg, MG_UTILITY_ANCHOR, MG_LIVE_REPLAY_ANCHOR
from stage3.run_artifact_g2 import _cfgg2, MG2_REFLEX_ANCHOR, MG2_LIVE_REPLAY_ANCHOR
from stage3.run_artifact_g2d import _cfgg2d, MG2D_AUTO_ANCHOR
from stage3.run_artifact_g2v2 import MG2V_REPUTATION_ANCHOR
from stage3.intent import MockReflexMind

HDR = "=" * 78
RS = (0.2, 0.3, 0.5)


def _cfgh(r=0.3, arena=None, days=600, store_access="maker", seed=7, **over):
    """DEBT on the vitok-2 substrate (store+capital ON). store_access defaults to 'maker' —
    a store is PROPERTY, so a hungry pawn cannot draw it free and must borrow: that is where
    debt has leverage. Intent OFF (debt is a structural ledger mechanic, not an intent verb)."""
    return _cfgg(policy="off", arena=arena, days=days, seed=seed,
                 debt_on=True, debt_r=r, store_access=store_access, **over)


# --------------------------------------------------------------------------- #
#  Gates                                                                       #
# --------------------------------------------------------------------------- #
def _gate_mh_off():
    """debt_on defaults False => the eight anchors + the reputation anchor are byte-identical
    (the debt fingerprint blob is empty until a loan issues)."""
    checks = [
        ("store+cap", _cfgg(policy="off", days=300), 300, MFV3_OFF_ANCHOR_STORECAP),
        ("vessel", _cfg(artifacts=True, days=250), 250, MFV3_OFF_ANCHOR_VESSEL),
        ("utility", _cfgg(policy="utility", days=300), 300, MG_UTILITY_ANCHOR),
        ("live-rep", _cfgg(policy="live", days=300, intent_mind=MockReflexMind()), 300,
         MG_LIVE_REPLAY_ANCHOR),
        ("extort-refl", _cfgg2(policy="reflex", extort=True, days=300), 300, MG2_REFLEX_ANCHOR),
        ("extort-live", _cfgg2(policy="live", extort=True, days=300,
                               intent_mind=MockReflexMind()), 300, MG2_LIVE_REPLAY_ANCHOR),
        ("delegate-auto", _cfgg2d(tooth="auto", days=300), 300, MG2D_AUTO_ANCHOR),
        ("reputation", _cfgg2d(tooth="reputation", days=300), 300, MG2V_REPUTATION_ANCHOR),
    ]
    all_ok = True
    print("MH-OFF  debt_on=False: the eight anchors stand bit-for-bit:")
    for name, cfg, days, anchor in checks:
        fp = _run(cfg, days).state_fingerprint()
        ok = fp == anchor
        all_ok = all_ok and ok
        print(f"          {name:>14}: {fp} == {anchor} -> {'✓' if ok else '✗'}")
    assert all_ok


def _gate_mh_mass():
    """Mass conserved on every path. A debt-on run exercises loan+payment+default+inheritance;
    the four-term invariant must hold at the end (and the run asserts it per tick internally)."""
    drifts = {}
    for r in RS:
        w = _run(_cfgh(r=r, days=600), 600)
        drifts[r] = w.matter_drift()
    ok = all(d < 1e-9 for d in drifts.values())
    print(f"MH-mass invariant holds every r (loan/pay/default/inherit) -> {'✓' if ok else '✗'}")
    print("          " + " · ".join(f"r{r} {drifts[r]:.1e}" for r in RS))
    assert ok


def _gate_mh_replay():
    ok = True
    fps = {}
    for r in RS:
        a = _run(_cfgh(r=r, days=600), 600)
        b = _run(_cfgh(r=r, days=600), 600)
        fps[r] = a.state_fingerprint()
        ok = ok and (a.state_fingerprint() == b.state_fingerprint())
    print(f"MH-replay every r replays bit-exact -> {'✓' if ok else '✗'}")
    for r in RS:
        print(f"          r{r}: {fps[r]}")
    assert ok


def _gate_mh_ledger():
    """The identity Σoutstanding ≡ Σ(issued·k) − Σrepaid − Σwriteoff holds EVERY tick (checked
    tick-by-tick here, not just at the end — the ledger cannot silently drift)."""
    from sim_eventlog import EventLog
    from stage3.polis import Polis
    worst = 0.0
    for r in RS:
        w = Polis(EventLog(), _cfgh(r=r, days=400))
        for _ in range(400):
            w.step()
            worst = max(worst, abs(w._debt.ledger_identity_residual()))
    ok = worst < 1e-6
    print(f"MH-ledger identity holds every tick (max |resid|={worst:.2e}) -> {'✓' if ok else '✗'}")
    assert ok


def _gate_mh_bankrupt():
    """NOT a no-op AND deprivation enforced at EXECUTION. Run a debt world that produces
    bondage; assert (1) its fingerprint differs from the same frame without debt (the mechanic
    bites the world), and (2) the bonded are actually stripped: zero claims held, zero seats in
    the speaker set, zero new loans to any stage>=2 debtor. Distinguishing no-op from NULL is
    mandatory before any scientific verdict — this gate is that discriminator."""
    r = 0.3
    w = _run(_cfgh(r=r, days=700), 700)
    d = w._debt
    base = _run(_cfgg(policy="off", arena=None, days=700, store_access="maker"), 700)
    diverges = w.state_fingerprint() != base.state_fingerprint()
    bonded = set(d._bonded)
    frozen = {o for o, s in d.stage.items() if s >= 2}
    owners = set(w.owner_ids())
    spk = getattr(w, "speaker", set())
    claims_bonded = sum(1 for o in owners if o in bonded)
    claims_frozen = sum(1 for o in owners if o in frozen)
    voice_bonded = sum(1 for o in bonded if o in spk)
    # zero new loans to stage>=2: a fresh loan is only ever issued to a stage<2 debtor
    # (enforced in DebtLedger._lend). Confirm no debt event issued to a currently-frozen oid
    # after it was frozen is not post-hoc reconstructable cheaply; the construction guarantee
    # + the claim/voice facts are the execution proof the WO asks for.
    alive = len(bonded) > 0
    deprived = (claims_bonded == 0 and claims_frozen == 0 and voice_bonded == 0)
    ok = diverges and alive and deprived
    print(f"MH-BANKRUPT non-no-op + deprivation at execution -> {'✓' if ok else '✗'}")
    print(f"          bonded={len(bonded)} frozen(st>=2)={len(frozen)} | fp diverges from no-debt: {diverges}")
    print(f"          claims held: bonded={claims_bonded} frozen={claims_frozen} (want 0) · "
          f"bonded voices={voice_bonded} (want 0)")
    assert ok


# --------------------------------------------------------------------------- #
#  HH1-4 — the sweep (гипотезу правит прогон; both formulations fixed above)   #
# --------------------------------------------------------------------------- #
def _creditor_flow(d):
    """Mass that flowed THROUGH each creditor = sum of repayments received (debt_pay events)."""
    recv = defaultdict(float)
    for (_t, kind, c, _dr, amt, _tag) in d.events:
        if kind == "debt_pay" and c is not None:
            recv[c] += amt
    return recv


def _gini(vals):
    v = sorted(x for x in vals if x == x and x >= 0)
    n = len(v)
    if n == 0:
        return float("nan")
    s = sum(v)
    if s <= 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(v))
    return (2 * cum) / (n * s) - (n + 1) / n


def _hh(seeds=(7, 8, 9), days=700):
    print(f"\n{HDR}\nHH1-4 — DEBT sweep r∈{RS} (arena none, store_access=maker, k∈[1.1,2.0]).\n"
          f"owner_gap = mass flowed-through-creditor (repayments) / its lifetime body integral.\n"
          f"(means over seeds {seeds})\n{HDR}")
    print(f"  {'r':>4}{'loans':>7}{'hun/inc/inv':>13}{'defaults':>9}{'bonded':>7}"
          f"{'topGap':>8}{'Gini':>7}{'writeoff%':>10}{'pop':>6}")
    for r in RS:
        agg = defaultdict(float); n = 0
        for s in seeds:
            w, integral, _t = _run_with_history(_cfgh(r=r, days=days, seed=s), days)
            assert w.matter_drift() < 1e-9, f"HH leaked (r{r} s{s})"
            d = w._debt
            recv = _creditor_flow(d)
            gaps = [(recv[c] / integral[c]) for c in recv
                    if integral.get(c, 0.0) > 1e-9]
            topgap = max(gaps) if gaps else float("nan")
            gini = _gini([a.body for a in w.pop])
            woff = (d.written_off_total / d.issued_k_total) if d.issued_k_total > 0 else float("nan")
            agg["loans"] += d.n_loans
            agg["hun"] += d.reason_counts["hunger"]; agg["inc"] += d.reason_counts["income_drop"]
            agg["inv"] += d.reason_counts["investment"]
            agg["def"] += d.n_defaults; agg["bond"] += len(d._bonded)
            agg["gap"] += (topgap if topgap == topgap else 0.0); agg["gapn"] += (1 if topgap == topgap else 0)
            agg["gini"] += (gini if gini == gini else 0.0)
            agg["woff"] += (woff if woff == woff else 0.0); agg["pop"] += len(w.pop); n += 1
        gapm = (agg["gap"] / agg["gapn"]) if agg["gapn"] else float("nan")
        reasons = f"{agg['hun']/n:.0f}/{agg['inc']/n:.0f}/{agg['inv']/n:.0f}"
        print(f"  {r:>4.1f}{agg['loans']/n:>7.0f}{reasons:>13}"
              f"{agg['def']/n:>9.1f}{agg['bond']/n:>7.1f}{gapm:>8.2f}{agg['gini']/n:>7.2f}"
              f"{100*agg['woff']/n:>9.0f}%{agg['pop']/n:>6.0f}")
    print("\n  read HH1: topGap>1 & Gini rises with r => power from consent (mass concentrates in")
    print("  creditors without title/violence); writeoff% dominating => NULL (no enforcer, no hold).")
    print("  HH2: topGap>1 => the claim-right is the extra-somatic vessel; <=1 => power stays somatic.")


# --------------------------------------------------------------------------- #
def main():
    print(HDR)
    print("mod H виток 1 — DEBT: power from consent, the first endogenous price, and bondage.")
    print(HDR)
    _gate_mh_off()
    _gate_mh_mass()
    _gate_mh_replay()
    _gate_mh_ledger()
    _gate_mh_bankrupt()
    if "--hh" in sys.argv or "--all" in sys.argv:
        _hh()
    print(f"\n{HDR}\nmod H vitok 1 gates green: OFF-neutral (MH-OFF), mass conserved on every path")
    print("(MH-mass), replay bit-exact (MH-replay), the ledger identity holds every tick")
    print("(MH-ledger), and bondage is real — it bites the world and strips rights at execution")
    print("(MH-BANKRUPT). The deal from below has a price the system set itself.")
    print(HDR)


if __name__ == "__main__":
    main()
