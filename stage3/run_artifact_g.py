"""
run_artifact_g.py — mod G (виток 1): the intent layer — триггер → интент → взаимодействие
→ результат. Gates + first measurements.

Vitok 1-2 answered its QUESTION (blind surplus DOES make a stratum, geography routes the
flow). mod G inserts a CHOICE between the affordance scan and the artifact physics WITHOUT
touching the physics: the same gates, the same passes, the same transfers — but before
each verb the actor's intent layer may decline it. See stage3/intent.py for the contract.

POLICIES (PolisConfig.intent_policy):
  off      the layer is not built — byte-identical to vitok 2 (MG-OFF; the layer object
           is None, zero new computation in the hot path).
  reflex   the scan runs and MEASURES but confirms every action — physically ≡ off
           (MG-REFLEX; the scan's purity test: counting must not perturb the world; the
           fingerprint blob stays empty so the anchors hold).
  utility  a deterministic filter through the STRUCTURAL personality axes (score >= theta):
           personality touches the material world for the first time — the world diverges.
  live     a mind confirms a subset via the typed protocol (mock minds here; via-log
           replay is bit-exact and never needs a key — the B-INERT/B-REPLAY pattern).

GATES (deterministic, no network):
  MG-OFF     intent_policy=off -> both vitok-2 anchors stand bit-for-bit (41bb81b4 @300
             store+capital, 48d9729d @250 vessel-only) — the refactor of the gates into
             predicates is transparent.
  MG-REFLEX  intent_policy=reflex -> the SAME two anchors: the affordance scan runs (and
             counters accumulate) but the world is byte-identical (empty fingerprint blob).
  MG-mass    every policy keeps the four-term invariant (<1e-9); and utility is ALIVE
             (its fingerprint differs from reflex — personality actually filters verbs).
  MG-deny    a MockHallucinatorMind asks the impossible -> deny(hallucination) fires AND
             the PHYSICAL substrate (intent overlay detached) is identical to the honest
             mind's: the typed «нельзя» never mutates the world.
  MG-replay  a live run's via-log replays bit-for-bit (full fingerprint, no key); and two
             mind-runs are identical (pure determinism).

PRE-REGISTERED EXPERIMENTS (гипотезу правит прогон; honest bases from tick one — pop base
= everyone who lived, elite sets on the HISTORICAL owner_ids() union, base rates printed):
  HGG1  does intent convert into MATERIAL fate? reflex vs utility across two arenas — a
        NULL-rhyme series. Expectation to be falsified: geography (arena) moves the
        material outcomes (deaths/draws/method depth) more than intent (policy) does.
  HGG2  does deny concentrate among the RICH LANDLESS (want to mint wealth, not settled)?
        unmet_mint (ticks a pawn wanted store/capital but had no affordance) vs wealth
        (lifetime body integral) and landlessness (never in the owner history).
  HGG3  does the personality profile stratify material BEHAVIOUR? Measured on OUTCOMES
        (lifespan, body integral, drawn mass) split by a structural axis — NOT on verb
        frequency (that would be the tautology 'weight -> frequency').
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict

from sim_eventlog import EventLog
from stage3.polis import Polis, PolisConfig
from stage3.intent import (VERBS, MINT_STORE, MINT_CAPITAL, MockReflexMind,
                            MockHallucinatorMind)
from stage3.run_artifact_f import _cfg, _run, _gini, _deaths_births
from stage3.run_artifact_f2 import _cfg2, _life_stats, _run_with_history
from stage3.run_artifact_f3 import _cfg3, MFV3_OFF_ANCHOR_STORECAP, MFV3_OFF_ANCHOR_VESSEL

HDR = "=" * 78

# mod-G anchors, captured from the first green run below (utility/live shape the world, so
# they get their OWN fingerprints; OFF/REFLEX reuse the vitok-2 anchors above).
MG_UTILITY_ANCHOR = "12069a0ed9280bc8"    # utility @300 store+capital, theta 0.5, box6 rho0.5 seed7
MG_LIVE_REPLAY_ANCHOR = "ef87914913c6586f"  # live(MockReflex) @300, same frame


def _cfgg(policy="off", theta=0.5, **over):
    """mod-G intent on the vitok-2 substrate (store+capital ON, settle/vision OFF): all
    seven verbs are on the menu, so the intent layer meets a full affordance space. The
    frame mirrors the store+capital anchor exactly, so OFF/REFLEX reproduce it."""
    return _cfg3(settle=False, vision=False, intent_policy=policy, intent_theta=theta, **over)


def _substrate_fp(w):
    """The PHYSICAL fingerprint with the intent overlay DETACHED — proves the world
    (soil/plant/body/artifact mass + dunbar) is identical regardless of intent bookkeeping.
    Detaching touches no physical state, so this is a pure read."""
    it = w._artifacts.intent
    w._artifacts.intent = None
    fp = w.state_fingerprint()
    w._artifacts.intent = it
    return fp


# --------------------------------------------------------------------------- #
#  Gates                                                                       #
# --------------------------------------------------------------------------- #
def _gate_mg_off():
    sc = _run(_cfgg(policy="off", days=300), 300)              # store+capital frame
    ve = _run(_cfg(artifacts=True, days=250, intent_policy="off"), 250)  # vessel-only
    fsc, fve = sc.state_fingerprint(), ve.state_fingerprint()
    layer_none = sc._artifacts.intent is None
    ok = (fsc == MFV3_OFF_ANCHOR_STORECAP and fve == MFV3_OFF_ANCHOR_VESSEL
          and sc.matter_drift() < 1e-9 and layer_none)
    print(f"MG-OFF   intent off ≡ vitok 2 (layer not built) -> {'✓' if ok else '✗'}")
    print(f"          store+cap {fsc} == {MFV3_OFF_ANCHOR_STORECAP}")
    print(f"          vessel    {fve} == {MFV3_OFF_ANCHOR_VESSEL}  ·  drift {sc.matter_drift():.1e}"
          f"  ·  layer None: {layer_none}")
    assert ok


def _gate_mg_reflex():
    # the purity test: the scan runs and counters accumulate, but the world must be
    # byte-identical to OFF (fingerprint blob empty for reflex).
    sc = _run(_cfgg(policy="reflex", days=300), 300)
    ve = _run(_cfg(artifacts=True, days=250, intent_policy="reflex"), 250)
    fsc, fve = sc.state_fingerprint(), ve.state_fingerprint()
    it = sc._artifacts.intent
    counted = sum(rec[0] + rec[1] for cv in it.counters.values() for rec in cv.values())
    blob_empty = (it.fingerprint_blob() == b"")
    ok = (fsc == MFV3_OFF_ANCHOR_STORECAP and fve == MFV3_OFF_ANCHOR_VESSEL
          and sc.matter_drift() < 1e-9 and blob_empty and counted > 0)
    print(f"MG-REFLEX scan measures but does not perturb -> {'✓' if ok else '✗'}")
    print(f"          store+cap {fsc} == {MFV3_OFF_ANCHOR_STORECAP}  ·  blob empty: {blob_empty}")
    print(f"          vessel    {fve} == {MFV3_OFF_ANCHOR_VESSEL}  ·  outcomes counted: {counted}")
    assert ok


def _gate_mg_mass():
    # invariant on every policy; and utility must be ALIVE (world diverges from reflex).
    drifts = {}
    fps = {}
    for pol, kw in (("reflex", {}), ("utility", {}),
                    ("live", dict(intent_mind=MockReflexMind()))):
        w = _run(_cfgg(policy=pol, days=300, **kw), 300)
        drifts[pol] = w.matter_drift()
        fps[pol] = w.state_fingerprint()
    alive = fps["utility"] != fps["reflex"]                   # personality actually filters
    ok = all(d < 1e-9 for d in drifts.values()) and alive
    print(f"MG-mass  invariant holds on every policy; utility is alive -> {'✓' if ok else '✗'}")
    print(f"          drift reflex {drifts['reflex']:.1e} · utility {drifts['utility']:.1e} · "
          f"live {drifts['live']:.1e}")
    print(f"          utility fp {fps['utility']} != reflex fp {fps['reflex']}  (alive: {alive})")
    assert ok


def _gate_mg_deny():
    # a hallucinating mind asks the impossible: the typed «нельзя» must fire and the
    # PHYSICAL substrate must equal the honest mind's (the world never mutates on a deny).
    honest = _run(_cfgg(policy="live", days=300, intent_mind=MockReflexMind()), 300)
    hallu = _run(_cfgg(policy="live", days=300,
                       intent_mind=MockHallucinatorMind()), 300)
    hb = hallu._artifacts.intent.deny_breakdown()
    n_hall = sum(n for (v, r), n in hb.items() if r == "hallucination")
    substrate_ok = _substrate_fp(honest) == _substrate_fp(hallu)
    ok = n_hall > 0 and substrate_ok
    print(f"MG-deny  hallucination denied, substrate untouched -> {'✓' if ok else '✗'}")
    print(f"          hallucination denies: {n_hall}  ·  substrate honest≡hallu: {substrate_ok}")
    print(f"          substrate fp {_substrate_fp(honest)} (both)")
    assert ok


def _gate_mg_replay():
    # a live run's via-log replays bit-for-bit with NO key; two mind-runs are identical.
    w1 = _run(_cfgg(policy="live", days=300, intent_mind=MockReflexMind()), 300)
    w2 = _run(_cfgg(policy="live", days=300, intent_mind=MockReflexMind()), 300)
    log = w1._artifacts.intent.request_log
    wr = _run(_cfgg(policy="live", days=300, intent_replay=log), 300)
    f1, f2, fr = (w1.state_fingerprint(), w2.state_fingerprint(), wr.state_fingerprint())
    determinism = (f1 == f2)
    replay = (f1 == fr)
    anchor = (f1 == MG_LIVE_REPLAY_ANCHOR) if MG_LIVE_REPLAY_ANCHOR != "PENDING" else True
    ok = determinism and replay and anchor
    print(f"MG-replay via-log replays bit-exact, no key -> {'✓' if ok else '✗'}")
    print(f"          mind-run {f1} == {f2} (determinism: {determinism})")
    print(f"          replay   {fr} == {f1} (via-log: {replay})  ·  anchor {MG_LIVE_REPLAY_ANCHOR}")
    assert ok
    return f1


def _gate_utility_anchor():
    # utility gets its OWN deterministic fingerprint (it shapes the world); pin it.
    a = _run(_cfgg(policy="utility", days=300), 300)
    b = _run(_cfgg(policy="utility", days=300), 300)
    fa, fb = a.state_fingerprint(), b.state_fingerprint()
    anchor = (fa == MG_UTILITY_ANCHOR) if MG_UTILITY_ANCHOR != "PENDING" else True
    ok = (fa == fb) and anchor
    print(f"MG-util   utility replays bit-exact -> {'✓' if ok else '✗'}")
    print(f"          {fa} == {fb}  ·  anchor {MG_UTILITY_ANCHOR}")
    assert ok
    return fa


# --------------------------------------------------------------------------- #
#  Experiments (гипотезу правит прогон)                                        #
# --------------------------------------------------------------------------- #
def _material(w):
    """Material outcomes of a run: deaths, median life, draws & Σdrawn, method depth,
    live method share. Pure reads of the world + logs."""
    af = w._artifacts
    deaths, med = _life_stats(w)
    ndraw = len(af.draws)
    drawn = sum(d[3] for d in af.draws)
    return dict(deaths=deaths, med=med, draws=ndraw, drawn=drawn,
                method=af.carried_max(), spread=af.live_method_share())


def _hgg1(seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHGG1 — does INTENT convert into material fate? reflex vs utility across\n"
          f"two arenas (a NULL-rhyme series). If arena moves the outcomes more than policy,\n"
          f"geography routes the flow and intent is (materially) epiphenomenal — виток 1's\n"
          f"honest null. (means over seeds {seeds})\n{HDR}")
    print(f"  {'arena':>7}{'policy':>9}{'deaths':>8}{'med.life':>9}{'draws':>7}{'Σdrawn':>9}"
          f"{'method':>8}{'spread':>8}")
    cell = {}
    for arena, tag in ((6, "box6"), (None, "none")):
        for pol in ("reflex", "utility"):
            agg = defaultdict(float)
            for s in seeds:
                w = _run(_cfgg(policy=pol, arena=arena, seed=s, days=days), days)
                assert w.matter_drift() < 1e-9, f"HGG1 leaked ({tag} {pol} s{s})"
                m = _material(w)
                for k, v in m.items():
                    agg[k] += v
            n = len(seeds)
            cell[(tag, pol)] = {k: agg[k] / n for k in agg}
            c = cell[(tag, pol)]
            print(f"  {tag:>7}{pol:>9}{c['deaths']:>8.0f}{c['med']:>9.1f}{c['draws']:>7.0f}"
                  f"{c['drawn']:>9.2f}{c['method']:>8.1f}{c['spread']:>8.3f}")
    # crude effect sizes: |utility - reflex| within arena vs |box6 - none| within policy.
    def d(a, b, k):
        return abs(cell[a][k] - cell[b][k])
    print("\n  read (deaths | Σdrawn | method):")
    for tag in ("box6", "none"):
        print(f"    intent effect @{tag:>4}: "
              f"{d((tag,'reflex'),(tag,'utility'),'deaths'):.1f} | "
              f"{d((tag,'reflex'),(tag,'utility'),'drawn'):.2f} | "
              f"{d((tag,'reflex'),(tag,'utility'),'method'):.1f}")
    for pol in ("reflex", "utility"):
        print(f"    arena  effect @{pol:>7}: "
              f"{d(('box6',pol),('none',pol),'deaths'):.1f} | "
              f"{d(('box6',pol),('none',pol),'drawn'):.2f} | "
              f"{d(('box6',pol),('none',pol),'method'):.1f}")
    print("  if the arena effect dwarfs the intent effect, HGG1 is a NULL (geography wins).")


def _hgg2(seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHGG2 — does deny concentrate among the RICH LANDLESS? unmet_mint (ticks a\n"
          f"pawn wanted store/capital but had no affordance) split by wealth (lifetime body\n"
          f"integral) quartile and landedness (ever in the owner history). utility only.\n{HDR}")
    print(f"  {'arena':>7}{'group':>16}{'n':>5}{'unmet_mint':>12}{'unmet/pawn':>11}")
    for arena, tag in ((6, "box6"), (None, "none")):
        # pool the classification across seeds (each seed's oids are a separate world; we
        # aggregate the group means, honest to per-world membership).
        rows = defaultdict(lambda: [0, 0.0])   # group -> [n_pawns, Σunmet]
        for s in seeds:
            w, integral, t_hist = _run_with_history(
                _cfgg(policy="utility", arena=arena, seed=s, days=days), days)
            it = w._artifacts.intent
            lived = sorted(integral)                       # everyone who drew breath
            if not lived:
                continue
            wealth_sorted = sorted(lived, key=lambda o: integral[o])
            q = max(1, len(wealth_sorted) // 4)
            top_wealth = set(wealth_sorted[-q:])            # richest quartile by integral
            for o in lived:
                rich = o in top_wealth
                landed = o in t_hist                        # ever held territory
                grp = (("rich" if rich else "poor") + "/"
                       + ("landed" if landed else "landless"))
                rows[grp][0] += 1
                rows[grp][1] += it.unmet_mint(o)
        for grp in ("rich/landless", "rich/landed", "poor/landless", "poor/landed"):
            n, tot = rows[grp]
            per = (tot / n) if n else float("nan")
            print(f"  {tag:>7}{grp:>16}{n:>5}{tot:>12.0f}{per:>11.2f}")
    print("\n  read: HGG2 predicts unmet/pawn peaks at rich/landless — wealth that cannot")
    print("  crystallise for want of a settled place (finding 8 through the pawn's own eyes).")


def _hgg3(seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHGG3 — does the PROFILE stratify material behaviour? Outcomes (median life,\n"
          f"body integral, Σ drawn RECEIVED) split by hunger_caution (the axis that halves\n"
          f"the material world). Measured on OUTCOMES, never on verb frequency (tautology).\n"
          f"utility only; median split of the LIVING population. (means over seeds {seeds})\n{HDR}")
    print(f"  {'arena':>7}{'hc-group':>12}{'n':>5}{'mean.life':>10}{'body∫/pawn':>12}"
          f"{'drawn/pawn':>11}")
    for arena, tag in ((6, "box6"), (None, "none")):
        grp = {"hc<med": [0, 0.0, 0.0, 0.0], "hc>=med": [0, 0.0, 0.0, 0.0]}
        for s in seeds:
            w, integral, _t = _run_with_history(
                _cfgg(policy="utility", arena=arena, seed=s, days=days), days)
            death, birth = _deaths_births(w)
            af = w._artifacts
            recv = defaultdict(float)
            for (_t2, _aid, drawer, amount, _mk) in af.draws:
                recv[drawer] += amount
            lived = sorted(integral)
            hcs = {o: w.pawn(o).personality.hunger_caution for o in lived
                   if w.pawn(o) is not None}
            if not hcs:
                continue
            vals = sorted(hcs.values())
            med_hc = vals[len(vals) // 2]
            for o in lived:
                hc = hcs.get(o)
                if hc is None:
                    continue
                key = "hc>=med" if hc >= med_hc else "hc<med"
                life = (death[o] - birth[o]) if (o in death and o in birth) else None
                grp[key][0] += 1
                if life is not None:
                    grp[key][1] += life
                grp[key][2] += integral[o]
                grp[key][3] += recv[o]
        for key in ("hc<med", "hc>=med"):
            n, lifesum, intsum, rcv = grp[key]
            ml = (lifesum / n) if n else float("nan")
            bi = (intsum / n) if n else float("nan")
            dr = (rcv / n) if n else float("nan")
            print(f"  {tag:>7}{key:>12}{n:>5}{ml:>10.1f}{bi:>12.1f}{dr:>11.3f}")
    print("\n  read: hunger_caution feeds MINT_STORE/DRAW and suppresses culture — if the")
    print("  cautious out-survive or out-hoard the bold, the profile has a material shadow.")


# --------------------------------------------------------------------------- #
def main():
    print(HDR)
    print("mod G — vitok 1: the intent layer (триггер → интент → взаимодействие → результат).")
    print("A choice between the affordance scan and the physics, WITHOUT touching the physics.")
    print(HDR)
    _gate_mg_off()
    _gate_mg_reflex()
    _gate_mg_mass()
    _gate_mg_deny()
    _gate_mg_replay()
    _gate_utility_anchor()
    if "--hgg1" in sys.argv or "--all" in sys.argv:
        _hgg1()
    if "--hgg2" in sys.argv or "--all" in sys.argv:
        _hgg2()
    if "--hgg3" in sys.argv or "--all" in sys.argv:
        _hgg3()
    print(f"\n{HDR}\nmod G vitok 1 gates green: OFF ≡ vitok 2 (MG-OFF), the scan is pure")
    print("(MG-REFLEX), the invariant holds on every policy and utility is alive (MG-mass),")
    print("hallucination is denied without mutating the world (MG-deny), and a live run")
    print("replays bit-exact with no key (MG-replay). Intent is chosen, physics disposes.")
    print(HDR)


if __name__ == "__main__":
    main()
