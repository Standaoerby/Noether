r"""pg_lab.py — the LABORATORY TWIN of the public-goods game (WO_pg-lab.md).

This lives OUTSIDE the tower on purpose. There is no canon here, no polis, no soil, no
ticks, no metabolism, no birth or death, no world fingerprint to protect. It is a plain
economic replication of the letter's field experiment IN THE LETTER'S OWN CONDITIONS —
so that comparing it to the substrate showcase (viz/pg) isolates two things:
    field ↔ lab       : do the ported strategies reproduce the field in its own rules?
    lab   ↔ substrate : what did the tower's PHYSICS (metabolism + demography) add?

HONEST NON-CONSERVATION. Unlike the substrate, this lab is NOT mass-conserving: the bank
MULTIPLIES money (×2) and the sanction BURNS it — exactly like humans at a table with a
teacher who doubles the pot and pockets fines. Every unit is still accounted for (gate
LAB-CONS): Σwallets == start·n + Σ(bank injections) − Σ(burned fines). Nothing vanishes
silently; it is created and destroyed by named events.

WHAT IS PORTED FROM THE TOWER (only the agents' decision logic, re-implemented here so the
lab has zero tower dependencies; source cited line-by-line against stage3/publicgood.py):
  * adaptive contribution propensity by the marginal incentive  — publicgood.py:158-174
  * punishment aiming {min_contrib, max_body, coalition}        — publicgood.py:213-232
  * majority-of-present vote, single global strategy            — publicgood.py:177-189
WHAT IS NOT PORTED: metabolism, reproduction, death, soil, ticks. A wallet cannot go below
0 — that is the only physical bound.

CODED ASSUMPTIONS (flip on review):
  * n=12 for BOTH groups (the letter gives 12 only for the children; the teenagers' size is
    assumed equal so the two circles are comparable).
  * pre-round negotiation is NOT modelled — the adaptive strategy approximates it.
  * the coalition split is EXOGENOUS (oid parity), the same honesty flag as H3.
  * contribution is a fraction of the CURRENT wallet (0..wallet), so full cooperation
    doubles every round (gate LAB-640: 20 → 40 → 80 → 160 → 320 → 640).

FIDELITY TO THE FIELD (measured, honest — do not over-read HL4). The letter's game
COMPOUNDS: the ×2 bank on a re-stakeable wallet makes full cooperation reach 20·2^5 = 640
(gate LAB-640) — 640 is the letter's own ceiling number. Real children reached ~100 ≈ 16%
of that ceiling; these agents reach ~275 ≈ 43%. So the lab↔field gap is NOT the conditions
(they are faithful — same ×2 compounding) but STRATEGY STRENGTH: the ported reinforcement
ratchets propensity toward 1.0 deterministically, with no satiation, boredom, or noise, so
the agents under-defect relative to real children. Consequently HL4's lab↔substrate gap is
to be read QUALITATIVELY — the institution ordering (children ≫ teens ≈ anarchy) holds
across all three layers, but the absolute Δ conflates strategy strength with the physics
(metabolism/demography) it is meant to isolate. Softening the strategy to match the field's
under-cooperation is a possible follow-up; here we keep the ported logic verbatim and flag
the gap rather than tune it away.

Deterministic per seed (only the initial propensities are drawn from the seed; every later
step is arithmetic). Two runs of a seed are byte-identical (gate LAB-DET).

Run:  py lab\pg_lab.py            # gates + a one-seed demo table
      py lab\pg_lab.py --sweep    # + the 3-mode × 10-seed sweep and the HL4 layer table
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os

import numpy as np

# ---- the letter's conditions, literally (WO §1.1) ----------------------------------------- #
N = 12                 # agents
START = 20.0           # money each, at t0
TOURS = 5              # rounds
BANK_MULT = 2.0        # the pot doubles (the letter's ×2), then splits equally over all n
PUNISH_FRAC = 0.20     # a sanctioned agent loses 20% of its CURRENT total (burned)
LEARN = 0.15           # reinforcement step for the propensity (publicgood.py pg_learn)
P0_LO, P0_HI = 0.45, 0.75   # initial propensity band (seed-drawn heterogeneity)

MODES = [
    ("anarchy", "Анархия", "аноним · без наказания", "anon", None),
    ("children", "Дети", "подписано · штраф самому жадному", "signed", "min_contrib"),
    ("teens", "Подростки", "подписано · коалиция жжёт чужого", "signed", "coalition"),
]

# Field numbers from the letter (WO §3, the thread) — for the HL4 three-layer table.
FIELD = {"anarchy": {"max": 60, "alt": 45}, "children": {"max": 100}, "teens": {"max": 45},
         "note": "люди за столом · банк ×2 · штраф сжигается"}


# --------------------------------------------------------------------------- #
#  strategy (ported from stage3/publicgood.py — logic only, cited)             #
# --------------------------------------------------------------------------- #
def _target(strategy, oids, contribs, wallets):
    """Whom the group sanctions, by aiming rule. Ported from publicgood.py:213-232.
    All 12 are 'present' and contributions are signed in circle 2, so the min_contrib
    misfire-under-anon case (publicgood.py:218-219) never applies here (circle 2 is signed)."""
    if strategy == "min_contrib":                                   # publicgood.py:215-220
        return min(oids, key=lambda o: (contribs[o], o))
    if strategy == "max_body":                                      # publicgood.py:221-222
        return max(oids, key=lambda o: (wallets[o], -o))
    if strategy == "coalition":                                     # publicgood.py:223-231
        g0 = [o for o in oids if o % 2 == 0]
        g1 = [o for o in oids if o % 2 == 1]
        if not g0 or not g1:
            return None
        maj, mino = (g0, g1) if len(g0) >= len(g1) else (g1, g0)    # majority bloc sanctions ...
        return max(mino, key=lambda o: (wallets[o], -o))            # ... the richest of the minority
    return None


def _adapt(p, oid, punished, at_risk, contribs):
    """One agent's propensity update by the marginal incentive. Ported verbatim in structure
    from publicgood.py:158-174. Here the pool return per unit contributed is BANK_MULT/n =
    2/12 = 0.17 < 1, so contributing is individually unprofitable and the base move is decay —
    exactly the free-rider dilemma (publicgood.py:171-172, with m<n always true at n=12)."""
    if oid == punished:
        p += 2.0 * LEARN                                            # punished => climb out (pg:168)
    elif at_risk is not None and contribs[oid] <= at_risk:
        p += LEARN                                                  # threatened by the norm (pg:169-170)
    elif BANK_MULT < N:
        p -= LEARN                                                  # m/n < 1 => free-ride (pg:171-172)
    else:
        p += LEARN                                                  # m/n >= 1 => cooperating pays (pg:173-174)
    return 0.0 if p < 0.0 else (1.0 if p > 1.0 else p)


# --------------------------------------------------------------------------- #
#  the game                                                                     #
# --------------------------------------------------------------------------- #
def play(visibility, strategy, seed, p_init=None, adapt=True):
    """Run one game. Returns a per-tour record + the ledger. Non-conserving but fully
    accounted (LAB-CONS). Deterministic given (visibility, strategy, seed, p_init).
    `adapt=False` freezes the propensity (used by the LAB-640 full-cooperation sanity)."""
    oids = list(range(1, N + 1))
    wallets = {o: START for o in oids}
    if p_init is not None:
        prop = dict(p_init)
    else:
        rng = np.random.default_rng(seed)
        prop = {o: float(v) for o, v in zip(oids, rng.uniform(P0_LO, P0_HI, N))}
    punish_on = strategy is not None
    injected = 0.0        # Σ money the bank created (payouts beyond what was contributed)
    burned = 0.0          # Σ money the sanction destroyed
    tours = []
    for r in range(TOURS):
        # 1) CONTRIBUTE — a fraction of the current wallet (0..wallet)
        contribs = {}
        C = 0.0
        for o in oids:
            c = prop[o] * wallets[o]
            wallets[o] -= c
            contribs[o] = c
            C += c
        # 2) BANK — the pot doubles and splits equally over all n (incl. zero-givers)
        payout = C * BANK_MULT
        share = payout / N
        for o in oids:
            wallets[o] += share
        injected += payout - C            # the bank created (mult-1)·C of new money
        # 3) PUNISH — signed circle only; majority-of-present, one target, −20% burned
        punished = None
        vote = None
        if punish_on and visibility == "signed":
            target = _target(strategy, oids, contribs, wallets)
            if target is not None:
                supporters = [o for o in oids if o != target]        # everyone but the victim (pg:181)
                if len(supporters) * 2 > N:                          # strict majority of present (pg:189)
                    fine = PUNISH_FRAC * wallets[target]
                    wallets[target] -= fine
                    burned += fine
                    punished = target
                    vote = {"target": target, "votes": len(supporters),
                            "voters": supporters, "strategy": strategy, "fine": fine}
        # 4) ADAPT — marginal incentive + norm-threat (min_contrib) anticipatory compliance
        if adapt:
            at_risk = None
            if punished is not None and strategy == "min_contrib":    # pg:161-164
                vals = sorted(contribs.values())
                at_risk = vals[len(vals) // 2]                        # the deme median (pg:163-164)
            for o in oids:
                prop[o] = _adapt(prop[o], o, punished, at_risk, contribs)
        tours.append({"round": r + 1, "contribs": dict(contribs), "wallets": dict(wallets),
                      "total_contrib": C, "bank_payout": payout, "vote": vote})
    ledger = {"start_total": START * N, "injected": injected, "burned": burned,
              "final_total": sum(wallets.values())}
    return {"wallets": wallets, "tours": tours, "ledger": ledger, "prop": prop}


def _summ(game):
    monies = sorted(game["wallets"].values(), reverse=True)
    curve = [t["total_contrib"] for t in game["tours"]]
    npun = sum(1 for t in game["tours"] if t["vote"])
    return {"max": monies[0], "mean": sum(monies) / len(monies),
            "curve": curve, "n_punish": npun,
            "total_bank": sum(t["bank_payout"] for t in game["tours"])}


# --------------------------------------------------------------------------- #
#  gates                                                                        #
# --------------------------------------------------------------------------- #
def _gate_lab_640():
    """Full cooperation (every agent gives its whole wallet, no sanction) doubles the pot
    each round: 20 → 40 → 80 → 160 → 320 → 640. The letter's headline number."""
    g = play("anon", None, seed=0, p_init={o: 1.0 for o in range(1, N + 1)}, adapt=False)
    finals = set(round(w, 6) for w in g["wallets"].values())
    ok = finals == {640.0}
    print(f"LAB-640   full cooperation -> 640 each  ({sorted(finals)}) -> {'✓' if ok else '✗'}")
    assert ok


def _gate_lab_cons():
    """Accounting: at the END, Σwallets == start·n + Σinjected − Σburned (money is created by
    the bank and burned by the fine, never lost silently). Checked on all three modes."""
    ok = True
    for key, _l, _s, vis, strat in MODES:
        g = play(vis, strat, seed=7)
        L = g["ledger"]
        lhs = L["final_total"]
        rhs = L["start_total"] + L["injected"] - L["burned"]
        good = abs(lhs - rhs) < 1e-9
        ok = ok and good
        print(f"LAB-CONS  [{key:>8}] Σwallets {lhs:.4f} == start+inj−burn {rhs:.4f} -> {'✓' if good else '✗'}")
    assert ok


def _run_blob(vis, strat, seed):
    g = play(vis, strat, seed)
    h = hashlib.sha256()
    for t in g["tours"]:
        for o in sorted(t["contribs"]):
            h.update(f"{t['round']}|{o}|{t['contribs'][o]:.9f}|{t['wallets'][o]:.9f}".encode())
        if t["vote"]:
            h.update(f"|v{t['vote']['target']}:{t['vote']['fine']:.9f}".encode())
    return h.hexdigest()[:16]


def _gate_lab_det():
    """Two runs of a seed produce a byte-identical game (determinism — one seed, one story)."""
    ok = True
    for key, _l, _s, vis, strat in MODES:
        a = _run_blob(vis, strat, 7)
        b = _run_blob(vis, strat, 7)
        good = a == b
        ok = ok and good
        print(f"LAB-DET   [{key:>8}] {a} == {b} -> {'✓' if good else '✗'}")
    assert ok


def main():
    ap = argparse.ArgumentParser(description="public-goods laboratory twin")
    ap.add_argument("--sweep", action="store_true", help="also run the 10-seed sweep + HL4 table")
    args = ap.parse_args()
    HDR = "=" * 78
    print(HDR)
    print("pg-lab — the public-goods game in the letter's own conditions (bank ×2, closed")
    print("wallets, no metabolism). A laboratory twin of the substrate showcase.")
    print(HDR)
    _gate_lab_640()
    _gate_lab_cons()
    _gate_lab_det()
    print(HDR)
    print("one-seed demo (seed 7):")
    for key, label, _s, vis, strat in MODES:
        s = _summ(play(vis, strat, 7))
        curve = "  ".join(f"{c:6.1f}" for c in s["curve"])
        print(f"  {label:>10}: вклад [{curve} ]  макс {s['max']:6.1f}  средний {s['mean']:6.1f}  штрафов {s['n_punish']}")
    print(HDR)
    print("pg-lab gates green: LAB-640 (cooperation math), LAB-CONS (accounting), LAB-DET")
    print("(determinism). Non-conserving BY DESIGN — money is created and burned, not lost.")
    print(HDR)
    if args.sweep:
        from lab.sweep import run_sweep      # noqa: E402  (heavy path, imported on demand)
        run_sweep()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
