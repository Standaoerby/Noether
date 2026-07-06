"""
run_polis_live_c.py — C-LIVE: the living mind as the teacher (Stage-3 mod C, live arm).

WHY: the deterministic mod C measured the succession CHANNELS with two heuristics and
one god privilege (vector-seeing god_pick; always-teach; death-bed ritual). C-LIVE
removes ALL of it: there is NO GOD in this arm. The mind PICKs its own apprentice from
the K nearest pawns it can SEE (its own attention_K — a narrow teacher literally sees
fewer students), decides teach-vs-preach, times the ritual gamble itself, may stay
silent. Physics stays physics (dao ticks, co-presence window, mortality, stutter).
Non-determinism lives ONLY in the action stream — logged, replayable byte-for-byte.

Emission targeting stays deterministic (choose_means with the head's own vector):
mod B already answered the targeting question (mind-NULL); this arm isolates JUDGMENT
(selection + timing).

GATES (no network):
  CL0  the full deterministic battery (C0-C3) re-green on the patched code
  CL1  FaithfulClone through the typed protocol == deterministic machine, byte-for-
       byte WORLD identity (state fp + decision log + windows + outcome + depth) on
       all 10 seed x rho combos. The groom DIARY legitimately differs (typed event
       vocabulary), so polis_fp is not compared — the world is.
  CL2  mock typed live -> action-replay bit-identical (FULL polis fp, typed log incl.)
  CL3  every action witnessed (EMIT/TEACH/RITUAL/PASS/PICK) + the stumble paths
       (pick a ghost; teach/pick/ritual without the дао; abandon a ritual mid-act)

PRE-REGISTERED (написаны до живого прогона; гипотезу правит прогон):
  HL1  timing/selection by a live mind vs the death-bed machine: does judgment beat
       the heuristic anywhere? (the rhyme series predicts NULL: mind-NULL, selection-
       NULL -> judgment-NULL; rho=.5 is the interesting cell — sudden death is sudden
       for the mind too)
  HL2  economics discovery: does the mind PICK apprentices already inside its reach
       (the lesson≡sermon freebie) and avoid teaching an out-of-reach apprentice
       (the wasted tick)? The prompt states PHYSICS only — the economics is never told.
  HL3  PASS usage: does a live mind spend ticks on the dominated action?

Honesty notes:
  * The view quantizes body to 3 decimals (mortal sensing); the clone reads the world
    raw — it is a gate fixture, not a fair mind (measured: the 0.1999 vs 0.2 despair
    bar flip, s10 rho=.5 t=353).
  * has_voice in the view is `directive is not None` — a voice SUCCESSOR has both
    learned and the voice; the `learned is None` первая версия broke every chain at
    depth 2 (measured, s10). Recorded as the kind of bug only deep chains expose.
  * Live calls need ANTHROPIC_API_KEY (env). Without it the live policy is INERT
    (EMIT) — the house pattern; gates never need a key.

Run:  py run_polis_live_c.py                 (gates, ~1.5 min)
      py run_polis_live_c.py --live haiku    (gates + live matrix; needs key; ~$)
      py run_polis_live_c.py --live haiku --seeds 7 --rho 0.5   (one cell)
      py run_polis_live_c.py --analyze       (re-read logged live runs, verdicts)
"""
from __future__ import annotations

import glob
import json
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import statistics as stx
from collections import Counter

from sim_eventlog import EventLog
from stage3.polis import Polis, PolisConfig, polis_fingerprint
from stage3.directive import Directive, IMPLANT
from stage3.succession import GroomConfig, TYPED_ACTIONS
from stage3.metrics import implant_absolute, succession_outcome, survival_excess
from stage3.mind_llm import make_typed_policy

HDR = "=" * 78
CELL = (3, 3)
LOGDIR = os.path.dirname(os.path.abspath(__file__))


def _mk(rho, *, seed=7, days=530, awaken=100, a_max=300, groom=None, policy=None,
        replay_actions=None, directive=True):
    owner = "claim" if rho > 0 else "founders"
    d = Directive(goal=IMPLANT, payload={"cell": CELL}) if directive else None
    return PolisConfig(appropriation=rho, owner_policy=owner, arena_side=6,
                       t_awaken=(awaken if directive else 10 ** 9),
                       demerzel_directive=d, seed=seed, days=days,
                       demerzel_a_max=a_max, groom=groom or GroomConfig(),
                       policy=policy, replay_actions=replay_actions)


def _run(cfg, sample_every=None):
    w = Polis(EventLog(), cfg)
    samples = []
    for t in range(cfg.days):
        w.step()
        if sample_every and t % sample_every == 0:
            a = implant_absolute(w, CELL)
            samples.append((t, a["infected_total"], a["infected_spread"], a["pop"]))
    assert w.matter_drift() < 1e-9, f"matter drift {w.matter_drift()}"
    return (w, samples) if sample_every else w


# --------------------------------------------------------------------------- #
def _gate_cl0():
    print(HDR)
    print("C-LIVE — the living mind as the teacher (no god in this arm)")
    print("The mind PICKs from what it SEES (its own attention_K), times teaching and")
    print("the ritual itself. Physics is physics; judgment is the only variable.")
    print(HDR)
    from stage3.run_polis_succession import _gate_c0, _gate_c1, _gate_c2, _gate_c3
    _gate_c0(); _gate_c1(); _gate_c2(); _gate_c3()
    print("CL0 full deterministic battery re-green on the typed-seam code ✓")


def _gate_cl1():
    fails = []
    for rho in (0.0, 0.5):
        for seed in (7, 8, 9, 10, 11):
            wd = _run(_mk(rho, seed=seed))
            wc = _run(_mk(rho, seed=seed,
                          policy=make_typed_policy("clone", gcfg=GroomConfig())))
            ok = (wd.state_fingerprint() == wc.state_fingerprint()
                  and dict(wd._decision_log) == dict(wc._decision_log)
                  and wd._outcome == wc._outcome and wd._depth == wc._depth
                  and wd.living_window() == wc.living_window()
                  and wd.line_window() == wc.line_window())
            if not ok:
                fails.append((rho, seed))
    print(f"CL1 faithful clone == machine (world byte-identity, 10 combos) -> "
          f"{'ALL ≡ ✓' if not fails else f'✗ {fails}'}")
    assert not fails, f"CL1 diverged on {fails}"


def _gate_cl2():
    wm = _run(_mk(0.0, seed=7, policy=make_typed_policy("mock")))
    wr = _run(_mk(0.0, seed=7,
                  replay_actions={t: a for t, a in wm._typed_log.items()}))
    ok = (polis_fingerprint(wm) == polis_fingerprint(wr)
          and wm.state_fingerprint() == wr.state_fingerprint())
    print(f"CL2 mock live vs action-replay: {polis_fingerprint(wm)} vs "
          f"{polis_fingerprint(wr)} -> {'BIT-IDENTICAL ✓' if ok else '✗'}")
    assert ok


class _CrashTest:
    """Stumble-path fixture: picks a ghost, teaches without the дао as a voice
    gambler, abandons a ritual mid-act. Exercises every coercion branch."""
    typed = True

    def act(self, world, head_oid, personality, directive, view):
        t = view["t"]
        app = view.get("apprentice")
        if t == 105:
            return ("PICK", 99999999)                  # a ghost -> pick_stumble
        if app is None:
            c = [x for x in view["candidates"] if x["phase"] == "MATURE"]
            return ("PICK", c[0]["oid"]) if c else ("EMIT",)
        if t in (120, 122):                            # begin then walk away
            return ("RITUAL",)                         # (untrained early gamble)
        if t == 121 or t == 123:
            return ("EMIT",)                           # -> ritual_abandoned
        if not app["dao_done"]:
            return ("TEACH",)
        return ("EMIT",)


def _gate_cl3():
    # full action space on the calm regime
    wm = _run(_mk(0.0, seed=7, policy=make_typed_policy("mock")))
    acts = Counter(a[0] for a in wm._typed_log.values())
    missing = [a for a in TYPED_ACTIONS if acts.get(a, 0) == 0]
    so = succession_outcome(wm)
    print(f"CL3 mock action space      : {dict(acts)} outcome={so['outcome']} "
          f"depth={so['depth']} -> {'ALL WITNESSED ✓' if not missing else f'✗ {missing}'}")
    assert not missing
    # stumble paths
    wx = _run(_mk(0.5, seed=7, policy=_CrashTest()))
    evs = {e for (_t, e, _d) in wx._groom_log}
    need = {"pick_stumble", "ritual_abandoned"}
    got = need & evs
    print(f"CL3 stumble paths          : {sorted(got)} -> "
          f"{'✓' if got == need else f'✗ missing {need - got}'}  (drift {wx.matter_drift():.1e})")
    assert got == need


# --------------------------------------------------------------------------- #
def _live_matrix(kind, seeds, rhos, period=10, days=530):
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        print("\n--live: ANTHROPIC_API_KEY is not set -> the mind would be inert. Abort.")
        return
    print(f"\n{HDR}\nC-LIVE matrix: policy={kind}, period={period}, seeds {seeds}, "
          f"rho {rhos}\n{HDR}")
    for rho in rhos:
        for seed in seeds:
            pol = make_typed_policy(kind, deliberation_period=period)
            w, _s = _run(_mk(rho, seed=seed, days=days, policy=pol), sample_every=5)
            so = succession_outcome(w)
            acts = Counter(a[0] for a in w._typed_log.values())
            # immediate replay proof: the world is deterministic given the actions
            wr = _run(_mk(rho, seed=seed, days=days,
                          replay_actions={t: a for t, a in w._typed_log.items()}))
            rep = polis_fingerprint(w) == polis_fingerprint(wr)
            path = os.path.join(LOGDIR, f"clive_{kind}_rho{rho}_s{seed}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"meta": {"kind": kind, "rho": rho, "seed": seed,
                                    "days": days, "period": period,
                                    "calls": pol.calls,
                                    "outcome": so["outcome"], "depth": so["depth"],
                                    "living": list(w.living_window()),
                                    "line": list(w.line_window()),
                                    "state_fp": w.state_fingerprint(),
                                    "polis_fp": polis_fingerprint(w)},
                           "actions": {str(t): a for t, a in w._typed_log.items()},
                           "livelog": pol.livelog}, f, ensure_ascii=False)
            print()
            print(f"  rho={rho} s{seed}: {str(so['outcome']):<10} d{so['depth']} "
                  f"acts {dict(acts)} calls={pol.calls} replay={'≡' if rep else '✗'} "
                  f"-> {os.path.basename(path)}")


def _analyze(days=530):
    files = sorted(glob.glob(os.path.join(LOGDIR, "clive_*_rho*.json")))
    if not files:
        print("--analyze: no clive_*.json logs found")
        return
    print(f"\n{HDR}\nC-LIVE analysis over {len(files)} logged runs (vs machine arm, "
          f"matched OFF)\n{HDR}")
    print(f"  {'rho':>4}{'seed':>6}{'mind':>7}{'outcome':>11}{'d':>3}{'auc':>8}"
          f"{'|':>2}{'machine':>11}{'d':>3}{'auc':>8}{'|':>2}{'pick_in':>8}"
          f"{'teach':>7}{'pass':>6}")
    rows = []
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        m = d["meta"]
        rho, seed = m["rho"], m["seed"]
        # replay the live world (never re-call the LLM), matched OFF, machine arm
        acts = {int(t): a for t, a in d["actions"].items()}
        wl, sl = _run(_mk(rho, seed=seed, days=days, replay_actions=acts),
                      sample_every=5)
        _wo, so_off = _run(_mk(rho, seed=seed, days=days, directive=False),
                           sample_every=5)
        wm, sm = _run(_mk(rho, seed=seed, days=days), sample_every=5)
        svl = survival_excess(sl, so_off, wl.living_window()[1], 120)
        svm = survival_excess(sm, so_off, wm.living_window()[1], 120)
        # HL2 economics from the livelog: PICK distance & out-of-reach teaching
        pick_in = teach = passes = 0
        picks = 0
        for e in d["livelog"]:
            a, v = e["action"], e["view"]
            if a[0] == "PICK":
                picks += 1
                cd = {c["oid"]: c for c in v.get("candidates", [])}
                c = cd.get(a[1]) if len(a) > 1 else None
                if c is not None and c["dist"] <= v.get("teach_dist", 2):
                    pick_in += 1
            elif a[0] == "PASS":
                passes += 1
        for t, a in acts.items():
            if a[0] == "TEACH":
                teach += 1
        lo = succession_outcome(wl)
        mo = succession_outcome(wm)
        rows.append({"rho": rho, "seed": seed, "l_auc": svl["auc"],
                     "m_auc": svm["auc"], "lo": lo, "mo": mo,
                     "pick_in": pick_in, "picks": picks, "passes": passes})
        print(f"  {rho:>4}{seed:>6}{'':>7}{str(lo['outcome']):>11}{lo['depth']:>3}"
              f"{svl['auc']:>8.0f}{'|':>2}{str(mo['outcome']):>11}{mo['depth']:>3}"
              f"{svm['auc']:>8.0f}{'|':>2}{f'{pick_in}/{picks}':>8}"
              f"{teach:>7}{passes:>6}")
    for rho in sorted({r["rho"] for r in rows}):
        rs = [r for r in rows if r["rho"] == rho]
        la = stx.mean(r["l_auc"] for r in rs)
        ma = stx.mean(r["m_auc"] for r in rs)
        print(f"  HL1 rho={rho}: live AUC {la:.0f} vs machine {ma:.0f} -> "
              f"{'live>machine' if la > ma else 'NULL or worse (rhyme holds)'}")
    tp = sum(r["picks"] for r in rows)
    ti = sum(r["pick_in"] for r in rows)
    print(f"  HL2: picks-in-reach {ti}/{tp} "
          f"({'economics discovered' if tp and ti / tp > 0.7 else 'not evident'})")
    print(f"  HL3: PASS ticks total {sum(r['passes'] for r in rows)}")


def main():
    if "--skip-gates" in sys.argv:
        print("(gates skipped: cell-by-cell live mode)")
    else:
        _gate_cl0()
        _gate_cl1()
        _gate_cl2()
        _gate_cl3()
    if "--live" in sys.argv:
        kind = sys.argv[sys.argv.index("--live") + 1] \
            if len(sys.argv) > sys.argv.index("--live") + 1 else "haiku"
        seeds = ([int(sys.argv[sys.argv.index("--seeds") + 1])]
                 if "--seeds" in sys.argv else [7, 8, 9, 10, 11])
        rhos = ([float(sys.argv[sys.argv.index("--rho") + 1])]
                if "--rho" in sys.argv else [0.0, 0.5])
        _live_matrix(kind, seeds, rhos)
    if "--analyze" in sys.argv:
        _analyze()
    print(f"\n{HDR}\nC-LIVE: the typed seam is a pure re-parameterization (CL1, 10/10"
          f" byte-identical);\nthe world stays deterministic given the action stream "
          f"(CL2). The mind's judgment\nis now the only variable — the live matrix "
          f"reads the verdict.\n{HDR}")


if __name__ == "__main__":
    main()
