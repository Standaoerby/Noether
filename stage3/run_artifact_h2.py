"""run_artifact_h2.py — mod H виток 2: removing the four confounds the vitok-1 audit found.

Vitok 1 gave a fact — creditors ruined (writeoff ~97%), no stratum, body ceiling intact — but
the PRE-REGISTERED mechanism was wrong: branch (b) needed MASS DEFAULT ("obligation needs an
enforcer"), and there were 1–2 defaults per run. Debtors were not refusing to pay. So vitok 1
said NOTHING about enforcement, and H3 (the pretorian) is not the next step — it would solve a
problem that does not exist. The audit found four confounds, each of which kills HH1
independently of enforcement. This vitok removes all four and re-asks HH1 honestly. The
vitok-1 verdict is PRELIMINARY, not entered into the thread.

  K1 — the CLAIM was mortal. A creditor's death evaporated its claim on a LIVE debtor: a
       creditor elite cannot form if its asset dies with the body. Fix: debt_claim_inherits —
       the claim passes to the creditor's _house heir. An asset that outlives the body is the
       candidate EXTRA-SOMATIC VESSEL Фаза 2 vitok-2 sought and did not find (HH2').
  K2 — _house was never on, so _find_heir always returned None: every death was a writeoff and
       HH4 (debt houses) was not refuted, it was NOT TESTED. Fix: debt_house reconstructs the
       mod-25 lineage from birth events (read-only, mass-neutral). Control: the same sweep off.
  K3 — investment ≈ 0. Claims were FREE (by presence), so borrow-to-claim was degenerate and
       credit went only to the incomeless, whose loans were unrepayable — charity, not power.
       Fix: claim_cost makes seizing a cell cost mass (body→soil); claim_cost=0 is byte-
       identical (MH2-OFF). SUBSTRATE FINDING (recorded, not hidden): even with a dear claim,
       investment credit stays ~0 — creditors (store-makers) and would-be investors do not
       co-locate and claim costs drain the very surplus that funds stores, so credit SUPPLY
       collapses. The binding constraint is not free claims but the absence of credit supply.
  K4 — the overdue trigger froze every fresh loan. 1→2 was outstanding>principal, and k>1
       makes that true from tick one: claim frozen instantly => no path to income => death =>
       writeoff. The mechanic itself guaranteed non-repayment. Fix: overdue = missed a payment
       debt_overdue_ticks (=10) in a row. Now a fresh loan is stage 1, claim free; only a real
       non-payer reaches stage 2. Effect: defaults rise (2 -> ~15), debtors survive to actually
       decide — the enforcement question can at last be asked.

PRE-REGISTRATION (both formulations fixed BEFORE the runs):
  HH1' — power from consent (re-ask). (a) with an inheritable claim AND a dear claim, creditors
         concentrate mass/power without violence or title => third conductivity 🔖 · (b) NULL:
         even with the confounds gone no stratum builds => debt is not a power mechanic on a
         conservative substrate; THEN, and only then, is H3 (the enforcer) meaningful, and the
         NULL names it honestly as the missing piece.
  HH2' — the extra-somatic vessel (MAIN). (a) a top creditor's owner_gap = (mass flowed THROUGH
         it, repayments received) / (its own lifetime body integral) > 1 under
         debt_claim_inherits=True => the claim-right is the extra-somatic vessel: power detaches
         from the body 🔖🔖 (the direct answer to Фаза 2 vitok-2) · (b) NULL: the mass still
         settles in the creditor's body — the vessel does not help, the body rules.
  HH3' — the credit cycle. (a) D/S oscillates, waves of defaults => an endogenous debt cycle 🔖 ·
         (b) monotone convergence / static.
  HH4' — debt houses (testable for the FIRST time). (a) stable creditor/debtor lines by _house,
         inherited bondage · (b) debt dissolves within a generation. (Смычка: a title on the free
         arena SPLITS between children — does the OBLIGATION stick to each? if so, право дробится,
         долг липнет — a hard asymmetry.)

GATES: MH2-OFF (claim_cost=0 & debt off => anchors bit-for-bit — the K3 refactor gate);
MH2-STAGE (K4: a fresh loan is stage 1, claim NOT frozen; only a real non-payer reaches 2);
MH2-INHERIT (K1: not a no-op — an inheritable-claim world diverges from a mortal-claim world and
the claim actually transfers); MH-mass / MH-replay / MH-ledger on all new paths; verify_all.

Run:  py stage3/run_artifact_h2.py            # gates
      py stage3/run_artifact_h2.py --hh       # gates + the HH1'-4' sweep (heavier)
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict

from stage3.run_artifact_f import _cfg, _run
from stage3.run_artifact_f2 import _run_with_history
from stage3.run_artifact_f3 import MFV3_OFF_ANCHOR_STORECAP
from stage3.run_artifact_g import _cfgg
from stage3.run_artifact_g2d import _cfgg2d
from stage3.run_artifact_g2v2 import MG2V_REPUTATION_ANCHOR

HDR = "=" * 78
RS = (0.2, 0.3, 0.5)
CLAIM_COST = 0.25          # the "noticeable" seizure cost (below the ownership-collapse point ~1.0)


def _cfgh2(r=0.3, claim_inherits=True, claim_cost=CLAIM_COST, house=True, arena=None,
           days=700, seed=7, **over):
    """vitok-2 base: debt on the store-property substrate, with the four confounds removed —
    inheritable claim (K1), _house lineage (K2), dear claim (K3), honest overdue (K4)."""
    return _cfgg(policy="off", arena=arena, days=days, seed=seed, store_access="maker",
                 debt_on=True, debt_r=r, debt_claim_inherits=claim_inherits,
                 debt_house=house, claim_cost=claim_cost, debt_overdue_ticks=10, **over)


# --------------------------------------------------------------------------- #
#  Gates                                                                       #
# --------------------------------------------------------------------------- #
def _gate_mh2_off():
    """K3 refactor gate: claim_cost=0 AND debt off => the anchors stand bit-for-bit (the new
    _do_claims delegates to canon verbatim, the debt blob is empty)."""
    checks = [
        ("store+cap", _cfgg(policy="off", days=300), 300, MFV3_OFF_ANCHOR_STORECAP),
        ("reputation", _cfgg2d(tooth="reputation", days=300), 300, MG2V_REPUTATION_ANCHOR),
    ]
    ok = True
    print("MH2-OFF  claim_cost=0 & debt off: anchors bit-for-bit (K3 refactor gate):")
    for name, cfg, days, anchor in checks:
        fp = _run(cfg, days).state_fingerprint()
        good = fp == anchor
        ok = ok and good
        print(f"          {name:>11}: {fp} == {anchor} -> {'✓' if good else '✗'}")
    assert ok


def _gate_mh2_stage():
    """K4: with the honest overdue, a fresh loan leaves the debtor at stage 1 (claim NOT frozen);
    only a debtor that missed debt_overdue_ticks payments in a row reaches stage 2."""
    from sim_eventlog import EventLog
    from stage3.polis import Polis
    w = Polis(EventLog(), _cfgh2(r=0.3, days=0))
    d = w._debt
    bad_fresh = 0                                     # stage-2 debtors that did NOT actually miss N
    saw_stage1 = False
    for _ in range(500):
        w.step()
        for oid, st in d.stage.items():
            if st == 2 and d._missed.get(oid, 0) < d.overdue_ticks:
                bad_fresh += 1
            if st == 1:
                saw_stage1 = True
    # and no stage-1 debtor ever has its claim frozen (claim-freeze is >=2 only)
    owners = set(w.owner_ids())
    frozen_owner = sum(1 for o in owners if d.stage.get(o, 0) >= 2)
    ok = (bad_fresh == 0) and saw_stage1 and (frozen_owner == 0)
    print(f"MH2-STAGE fresh loan => stage 1 (claim free); stage 2 only for real non-payers "
          f"-> {'✓' if ok else '✗'}")
    print(f"          premature-stage-2={bad_fresh} (want 0) · saw a stage-1 debtor={saw_stage1} · "
          f"frozen owners now={frozen_owner}")
    assert ok


def _gate_mh2_inherit():
    """K1: NOT a no-op. A world where the claim inherits diverges (fingerprint) from one where it
    dies with the creditor, the claim actually transfers (n_claim_inherits>0 and events exist),
    and the ledger identity still holds."""
    wi = _run(_cfgh2(claim_inherits=True, days=700), 700)
    wm = _run(_cfgh2(claim_inherits=False, days=700), 700)
    di = wi._debt
    diverges = wi.state_fingerprint() != wm.state_fingerprint()
    n_inh = di.n_claim_inherits
    ev = sum(1 for e in di.events if e[1] == "debt_claim_inherit")
    ledger_ok = abs(di.ledger_identity_residual()) < 1e-6
    ok = diverges and n_inh > 0 and ev == n_inh and ledger_ok
    print(f"MH2-INHERIT claim inheritance is real & non-no-op -> {'✓' if ok else '✗'}")
    print(f"          fp(inherit) {wi.state_fingerprint()} != fp(mortal) {wm.state_fingerprint()}: {diverges}")
    print(f"          claim_inherits={n_inh} events={ev} · ledger resid<1e-6: {ledger_ok}")
    assert ok


def _gate_mh_mass_replay_ledger():
    from sim_eventlog import EventLog
    from stage3.polis import Polis
    drift_ok = replay_ok = True
    worst = 0.0
    for r in RS:
        a = _run(_cfgh2(r=r, days=500), 500)
        b = _run(_cfgh2(r=r, days=500), 500)
        drift_ok = drift_ok and a.matter_drift() < 1e-9
        replay_ok = replay_ok and a.state_fingerprint() == b.state_fingerprint()
        w = Polis(EventLog(), _cfgh2(r=r, days=300))
        for _ in range(300):
            w.step()
            worst = max(worst, abs(w._debt.ledger_identity_residual()))
    ledger_ok = worst < 1e-6
    print(f"MH-mass/replay/ledger on the new paths (inherit-claim, dear-claim) -> "
          f"{'✓' if (drift_ok and replay_ok and ledger_ok) else '✗'}")
    print(f"          mass<1e-9: {drift_ok} · replay bit-exact: {replay_ok} · ledger |resid|<1e-6 "
          f"({worst:.1e}): {ledger_ok}")
    assert drift_ok and replay_ok and ledger_ok


# --------------------------------------------------------------------------- #
#  HH1'-4' — the sweep                                                         #
# --------------------------------------------------------------------------- #
def _creditor_flow(d):
    recv = defaultdict(float)
    for e in d.events:
        if e[1] == "debt_pay" and e[2] is not None:
            recv[e[2]] += e[4]
    return recv


def _gini(vals):
    v = sorted(x for x in vals if x == x and x >= 0)
    n = len(v)
    if n == 0 or sum(v) <= 0:
        return 0.0 if n else float("nan")
    cum = sum((i + 1) * x for i, x in enumerate(v))
    return (2 * cum) / (n * sum(v)) - (n + 1) / n


def _hh(seeds=(7, 8, 9), days=700):
    print(f"\n{HDR}\nHH1'-4' — vitok-2 sweep (arena none, store=property, _house on, claim_cost="
          f"{CLAIM_COST}).\nowner_gap = repayments received by a creditor / its lifetime body "
          f"integral. topGap>1 => HH2'\ntrophy (claim = extra-somatic vessel). (means over seeds "
          f"{seeds})\n{HDR}")
    print(f"  {'inherit':>8}{'r':>5}{'loans':>7}{'h/i/inv':>10}{'defaults':>9}{'bonded':>7}"
          f"{'topGap':>8}{'Gini':>7}{'wo_debtr':>9}{'wo_credr':>9}{'inh':>5}")
    for inh in (False, True):
        for r in RS:
            agg = defaultdict(float); n = 0
            for s in seeds:
                w, integral, _t = _run_with_history(_cfgh2(r=r, claim_inherits=inh, seed=s, days=days), days)
                assert w.matter_drift() < 1e-9, f"HH' leaked (inh{inh} r{r} s{s})"
                d = w._debt
                recv = _creditor_flow(d)
                gaps = [recv[c] / integral[c] for c in recv if integral.get(c, 0.0) > 1e-9]
                topgap = max(gaps) if gaps else float("nan")
                agg["loans"] += d.n_loans; agg["def"] += d.n_defaults; agg["bond"] += len(d._bonded)
                agg["h"] += d.reason_counts["hunger"]; agg["i"] += d.reason_counts["income_drop"]
                agg["inv"] += d.reason_counts["investment"]; agg["inh"] += d.n_claim_inherits
                agg["gap"] += (topgap if topgap == topgap else 0.0); agg["gapn"] += (1 if topgap == topgap else 0)
                agg["gini"] += _gini([a.body for a in w.pop])
                agg["wod"] += d.writeoff_debtor; agg["woc"] += d.writeoff_creditor; n += 1
            gapm = (agg["gap"] / agg["gapn"]) if agg["gapn"] else float("nan")
            reasons = f"{agg['h']/n:.0f}/{agg['i']/n:.0f}/{agg['inv']/n:.0f}"
            print(f"  {str(inh):>8}{r:>5.1f}{agg['loans']/n:>7.0f}{reasons:>10}{agg['def']/n:>9.1f}"
                  f"{agg['bond']/n:>7.1f}{gapm:>8.2f}{agg['gini']/n:>7.2f}{agg['wod']/n:>9.2f}"
                  f"{agg['woc']/n:>9.2f}{agg['inh']/n:>5.0f}")
    print("\n  read HH2' (MAIN): topGap>1 under inherit=True => the claim-right is an extra-somatic")
    print("  vessel (power off the body). HH1': Gini rises & wo_credr falls with inherit => a")
    print("  creditor stratum. wo_debtr vs wo_credr = the split writeoff (debtor line ended vs")
    print("  claim died with the body — K1's measurement). inv column: productive credit (K3).")


# --------------------------------------------------------------------------- #
def _emit_json():
    """S2 — a deterministic machine-readable result (a canonical confound-free debt world, the
    frame MH-mass/replay/ledger exercises). No timestamp => a double run is byte-identical."""
    from stage3.resultjson import write_result
    seed, days = 7, 500
    w = _run(_cfgh2(r=0.3, seed=seed, days=days), days)
    d = w._debt
    path = write_result("run_artifact_h2", w, seed=seed,
                        invariants={"drift": w.matter_drift(),
                                    "ledger_resid": d.ledger_identity_residual()},
                        metrics={"loans": d.n_loans, "defaults": d.n_defaults,
                                 "claim_inherits": d.n_claim_inherits,
                                 "bonded": len(d._bonded), "pop": len(w.pop)})
    print(f"{path} written (state_hash {w.state_fingerprint()})")


# --------------------------------------------------------------------------- #
def main():
    if "--json" in sys.argv:
        _emit_json()
        return
    print(HDR)
    print("mod H виток 2 — the four confounds removed; HH1 re-asked honestly.")
    print(HDR)
    _gate_mh2_off()
    _gate_mh2_stage()
    _gate_mh2_inherit()
    _gate_mh_mass_replay_ledger()
    if "--hh" in sys.argv or "--all" in sys.argv:
        _hh()
    print(f"\n{HDR}\nmod H vitok 2 gates green: K3 refactor-neutral (MH2-OFF), the ladder is honest")
    print("(MH2-STAGE), claim inheritance is real (MH2-INHERIT), and mass/replay/ledger hold on")
    print("every new path. The confounds are gone; the sweep re-asks HH1 without them.")
    print(HDR)


if __name__ == "__main__":
    main()
