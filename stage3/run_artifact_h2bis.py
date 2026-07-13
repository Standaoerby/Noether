"""run_artifact_h2bis.py — mod H2-bis: honest default (K5) + the credit channel (decision-4a).

Vitok 2 gave a true NULL for HH2' (the body rules) but left two tails: (1) K5 — the direct
default test — did not land in #59, so the verdict carried a caveat; (2) the K3 finding —
productive credit is dead because credit SUPPLY collapses, creditor and borrower do not meet.
This short vitok closes both before H3, so the enforcer starts from an honest default and a
live credit channel.

  K5 (§1) — DIRECT default. The trigger was the indirect proxy `r·income > metabolism` — two
       surrogate quantities, not "paying means dying". Now the payment is made only if the body
       AFTER it stays at or above the substrate's survival threshold (DEATH); else the pawn
       refuses and defaults (bondage). FINDING (HHB3): the honest test collapses natural defaults
       ~9 → ~0 — debt service (a share of a small per-tick gain) is tiny next to the body, so
       "paying = dying" almost never happens. The proxy fired on HIGH EARNERS, not the near-death:
       it was NOT empirically equivalent, so the vitok-2 caveat does NOT lift retroactively — it
       is REPLACED by the honest number (near-zero forced default).

  decision-4a (§2) — the credit CHANNEL. Lending is already same-cell co-present; debt_copresence
       widens it to the substrate's von-Neumann movement neighbourhood (sim_stage2.DIRS N/S/W/E,
       the EXISTING соседство — no new geometry). False (default) => same cell only == vitok 2
       (comparability); True => a creditor on a DIRS-adjacent cell may also lend. A triggered loan
       with no creditor in the channel is a MISSED MEETING — the measure of the channel's width.

PRE-REGISTRATION (both formulations fixed BEFORE the runs):
  HHB1 — HH1'/HH2' re-asked with an honest default and a channel. (a) copresence=True concentrates
         mass/power (topGap>1 or a durable creditor stratum) => third conductivity 🔖 · (b) NULL:
         with the channel AND the honest default no stratum builds => debt on a conservative
         substrate without an enforcer is not a power mechanic; H3 starts with a clean conscience.
  HHB2 — loan structure. (a) with copresence loans shift toward investment — productive credit
         revived · (b) investment ~= 0 even with meetings => supply is deeper than the channel
         (the surplus), honestly recorded: the channel was not the only bottleneck.
  HHB3 — K5's effect on defaults. (a) the honest test shifts the number/structure of defaults
         vs vitok 2 (compared at copresence=False) · (b) no shift => the proxy was empirically
         equivalent, the vitok-2 caveat lifts retroactively.

GATES: MH2B-OFF (debt off => anchors bit-for-bit; claim_cost=0 too); MH2-DEFAULT (§1.2 — a
constructed edge pawn: a lethal payment is NOT made and is logged as a default; a survivable one
is made); MH2B-COPRES (§2.3 — non-no-op: True diverges from False, and every loan under True is
co-localized within the channel by the log); MH-mass / MH-replay / MH-ledger; verify_all.

Run:  py stage3/run_artifact_h2bis.py            # gates
      py stage3/run_artifact_h2bis.py --hh       # gates + the HHB1-3 sweep
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict

import numpy as np

from sim_eventlog import EventLog, DEATH
from stage3.polis import Polis, PolisConfig
from stage3.debt import DebtLedger
from stage3.run_artifact_f import _run
from stage3.run_artifact_f2 import _run_with_history
from stage3.run_artifact_f3 import MFV3_OFF_ANCHOR_STORECAP
from stage3.run_artifact_g import _cfgg
from stage3.run_artifact_g2d import _cfgg2d
from stage3.run_artifact_g2v2 import MG2V_REPUTATION_ANCHOR

HDR = "=" * 78
RS = (0.3, 0.5)


def _cfghb(r=0.3, copresence=False, claim_inherits=True, arena=None, days=700, seed=7, **over):
    """H2-bis base: the vitok-2 confound-free substrate + K5 (always on now) + the credit-channel
    handle. claim_inherits=True (best case for a stratum); claim_cost off unless overridden."""
    return _cfgg(policy="off", arena=arena, days=days, seed=seed, store_access="maker",
                 debt_on=True, debt_r=r, debt_claim_inherits=claim_inherits, debt_house=True,
                 debt_overdue_ticks=10, debt_copresence=copresence, **over)


# --------------------------------------------------------------------------- #
#  Gates                                                                       #
# --------------------------------------------------------------------------- #
def _gate_mh2b_off():
    checks = [
        ("store+cap", _cfgg(policy="off", days=300), 300, MFV3_OFF_ANCHOR_STORECAP),
        ("reputation", _cfgg2d(tooth="reputation", days=300), 300, MG2V_REPUTATION_ANCHOR),
    ]
    ok = True
    print("MH2B-OFF  debt off (claim_cost=0, copresence=False): anchors bit-for-bit:")
    for name, cfg, days, anchor in checks:
        fp = _run(cfg, days).state_fingerprint()
        good = fp == anchor
        ok = ok and good
        print(f"          {name:>11}: {fp} == {anchor} -> {'✓' if good else '✗'}")
    assert ok


class _MockA:
    __slots__ = ("oid", "body", "i", "j", "gene")

    def __init__(self, oid, body):
        self.oid = oid; self.body = body; self.i = 0; self.j = 0; self.gene = 290.0


class _MockW:
    def __init__(self):
        self.t = 1; self.log = EventLog(); self.T = np.full((14, 14), 290.0)
        self.pop = []; self._artifacts = None

    def owner_ids(self):
        return set()


def _gate_mh2_default():
    """K5 §1.2 — the direct survival test, on two constructed pawns on the edge. A payment that
    would leave the body below DEATH is REFUSED (default, no debt_pay); one that leaves it alive
    is MADE. Both outcomes are ledger events."""
    cfg = PolisConfig(debt_on=True, debt_r=0.5)
    # edge: body 0.08, want = 0.5·0.10 = 0.05 => body_after 0.03 < DEATH(0.05) => refuse+default
    d1 = DebtLedger(cfg); edge = _MockA(1, 0.08); cr1 = _MockA(2, 5.0)
    w1 = _MockW(); w1.pop = [edge, cr1]; d1.debt[(2, 1)] = 1.0; d1.principal[1] = 0.5
    d1._income = {1: 0.10, 2: 0.0}; d1._pay(w1, 1, {1: edge, 2: cr1}, {})
    edge_default = (1 in d1._bonded) and edge.body == 0.08 and not any(
        e[1] == "debt_pay" and e[3] == 1 for e in d1.events) and any(
        e[1] == "debt_default" and e[3] == 1 for e in d1.events)
    # safe: body 1.0 => body_after 0.95 >= DEATH => pay
    d2 = DebtLedger(cfg); safe = _MockA(3, 1.0); cr2 = _MockA(4, 5.0)
    w2 = _MockW(); w2.pop = [safe, cr2]; d2.debt[(4, 3)] = 1.0; d2.principal[3] = 0.5
    d2._income = {3: 0.10, 4: 0.0}; d2._pay(w2, 1, {3: safe, 4: cr2}, {})
    safe_pays = (3 not in d2._bonded) and safe.body < 1.0 and any(
        e[1] == "debt_pay" and e[3] == 3 for e in d2.events)
    ok = edge_default and safe_pays
    print(f"MH2-DEFAULT direct survival test (body_after >= DEATH) -> {'✓' if ok else '✗'}")
    print(f"          edge (lethal pay refused+default, body {edge.body}): {edge_default} · "
          f"safe (pay made, body {safe.body:.2f}): {safe_pays}")
    assert ok


def _gate_mh2b_copres():
    """§2.3 — non-no-op AND every loan co-localized. A copresence=True world diverges (fingerprint)
    from copresence=False, and every loan issued under True has its creditor within von-Neumann
    distance 1 of the debtor at issue (checked from the recorded meetings)."""
    wf = _run(_cfghb(r=0.3, copresence=False, days=500), 500)
    wt = _run(_cfghb(r=0.3, copresence=True, days=500), 500)
    diverges = wf.state_fingerprint() != wt.state_fingerprint()
    dt = wt._debt
    dmax = max((abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in dt._loan_meetings), default=0)
    df = wf._debt
    dmax_f = max((abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in df._loan_meetings), default=0)
    ok = diverges and dmax <= 1 and dmax_f == 0 and dt.n_loans > 0
    print(f"MH2B-COPRES channel is non-no-op & every loan co-localized -> {'✓' if ok else '✗'}")
    print(f"          fp(True) {wt.state_fingerprint()} != fp(False) {wf.state_fingerprint()}: {diverges}")
    print(f"          max meeting dist: True={dmax} (want <=1) · False={dmax_f} (want 0) · "
          f"loans(T)={dt.n_loans} no_meeting(T)={dt.n_no_meeting}")
    assert ok


def _gate_mh_mass_replay_ledger():
    drift_ok = replay_ok = True
    worst = 0.0
    for cp in (False, True):
        for r in RS:
            a = _run(_cfghb(r=r, copresence=cp, days=400), 400)
            b = _run(_cfghb(r=r, copresence=cp, days=400), 400)
            drift_ok = drift_ok and a.matter_drift() < 1e-9
            replay_ok = replay_ok and a.state_fingerprint() == b.state_fingerprint()
            w = Polis(EventLog(), _cfghb(r=r, copresence=cp, days=250))
            for _ in range(250):
                w.step()
                worst = max(worst, abs(w._debt.ledger_identity_residual()))
    ledger_ok = worst < 1e-6
    print(f"MH-mass/replay/ledger on the K5 + channel paths -> "
          f"{'✓' if (drift_ok and replay_ok and ledger_ok) else '✗'}")
    print(f"          mass<1e-9: {drift_ok} · replay: {replay_ok} · ledger |resid|<1e-6 "
          f"({worst:.1e}): {ledger_ok}")
    assert drift_ok and replay_ok and ledger_ok


# --------------------------------------------------------------------------- #
#  HHB1-3 — the sweep                                                          #
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
    print(f"\n{HDR}\nHHB1-3 — H2-bis sweep (arena none, store=property, _house on, claim_inherits=True,\n"
          f"K5 honest default). copresence False=same-cell(=vitok2) vs True=von-Neumann channel.\n"
          f"noMeet = triggered loans with no creditor in the channel. (means over seeds {seeds})\n{HDR}")
    print(f"  {'copres':>7}{'r':>5}{'loans':>7}{'h/i/inv':>10}{'noMeet':>8}{'defaults':>9}"
          f"{'bonded':>7}{'topGap':>8}{'Gini':>7}{'wo_dr':>7}{'wo_cr':>7}")
    for cp in (False, True):
        for r in RS:
            agg = defaultdict(float); n = 0
            for s in seeds:
                w, integral, _t = _run_with_history(_cfghb(r=r, copresence=cp, seed=s, days=days), days)
                assert w.matter_drift() < 1e-9, f"HHB leaked (cp{cp} r{r} s{s})"
                d = w._debt
                recv = _creditor_flow(d)
                gaps = [recv[c] / integral[c] for c in recv if integral.get(c, 0.0) > 1e-9]
                topgap = max(gaps) if gaps else float("nan")
                agg["loans"] += d.n_loans; agg["def"] += d.n_defaults; agg["bond"] += len(d._bonded)
                agg["h"] += d.reason_counts["hunger"]; agg["i"] += d.reason_counts["income_drop"]
                agg["inv"] += d.reason_counts["investment"]; agg["nm"] += d.n_no_meeting
                agg["gap"] += (topgap if topgap == topgap else 0.0); agg["gapn"] += (1 if topgap == topgap else 0)
                agg["gini"] += _gini([a.body for a in w.pop])
                agg["wod"] += d.writeoff_debtor; agg["woc"] += d.writeoff_creditor; n += 1
            gapm = (agg["gap"] / agg["gapn"]) if agg["gapn"] else float("nan")
            reasons = f"{agg['h']/n:.0f}/{agg['i']/n:.0f}/{agg['inv']/n:.0f}"
            print(f"  {str(cp):>7}{r:>5.1f}{agg['loans']/n:>7.0f}{reasons:>10}{agg['nm']/n:>8.0f}"
                  f"{agg['def']/n:>9.1f}{agg['bond']/n:>7.1f}{gapm:>8.2f}{agg['gini']/n:>7.2f}"
                  f"{agg['wod']/n:>7.1f}{agg['woc']/n:>7.1f}")
    print("\n  read HHB1: topGap>1 or Gini rises with copresence => stratum (else NULL). HHB2: inv")
    print("  column rises with copresence => channel revived productive credit (else supply is deeper).")
    print("  HHB3: defaults here (K5, honest) vs vitok-2's 7–14 (proxy) — the shift is K5's effect.")


# --------------------------------------------------------------------------- #
def _emit_json():
    """S2 — a deterministic machine-readable result (the canonical K5 + copresence-channel debt
    world, the frame MH2B-COPRES exercises). No timestamp => a double run is byte-identical."""
    from stage3.resultjson import write_result
    seed, days = 7, 500
    w = _run(_cfghb(r=0.3, copresence=True, seed=seed, days=days), days)
    d = w._debt
    path = write_result("run_artifact_h2bis", w, seed=seed,
                        invariants={"drift": w.matter_drift(),
                                    "ledger_resid": d.ledger_identity_residual()},
                        metrics={"loans": d.n_loans, "defaults": d.n_defaults,
                                 "bonded": len(d._bonded), "no_meeting": d.n_no_meeting,
                                 "pop": len(w.pop)})
    print(f"{path} written (state_hash {w.state_fingerprint()})")


# --------------------------------------------------------------------------- #
def main():
    if "--json" in sys.argv:
        _emit_json()
        return
    print(HDR)
    print("mod H2-bis — honest default (K5) + the credit channel (decision-4a).")
    print(HDR)
    _gate_mh2b_off()
    _gate_mh2_default()
    _gate_mh2b_copres()
    _gate_mh_mass_replay_ledger()
    if "--hh" in sys.argv or "--all" in sys.argv:
        _hh()
    print(f"\n{HDR}\nmod H2-bis gates green: OFF-neutral (MH2B-OFF), the default is direct")
    print("(MH2-DEFAULT), the credit channel is real & co-localized (MH2B-COPRES), and")
    print("mass/replay/ledger hold on every new path. Two tails closed before H3.")
    print(HDR)


if __name__ == "__main__":
    main()
