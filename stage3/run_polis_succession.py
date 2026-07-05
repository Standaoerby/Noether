"""
run_polis_succession.py — Stage-3 mod C: дао/ученик (succession) gates + the headline
experiment.

WHY (measured, not assumed): mod A's survival-NULL — the implant Δ collapses to
background after the Demerzel's death (+0.246 -> +0.164 -> ~0), and under the turnover
pump the idea is INFUSED, not contagious (rho=.5 spread 6% vs rho=0 23-50%) — meaning
must be REPEATED to persist. mod B: a smarter voice does not fix this (mind 2/5). The
only path past the carrier's death is TEACHING. mod C builds the two succession channels
of STAGE3_constitution §6 (передача дао / ритуал голоса) and measures whether they beat
the обрыв.

GATES (deterministic, no network):
  C0  groom=None == mod A byte-for-byte (cited fps, 450d IMPLANT, both regimes)
      + the full mod A gate battery (B0/B1/PRE/FP) re-run on the patched code
  C1  groom armed but toothless (teach_slots=0, ritual unreachable) -> substrate and
      decision log IDENTICAL to mod A (the machine watches, the world can't tell)
  C2  mock-mind live + groom -> replay-from-log bit-identical (incl. the groom log)
  C3  all four §6 outcomes witnessed: dao+voice / dao-only / voice-only / none
  C4  the headline: seeds 7-11 x rho {0,.5} x arms {обрыв, random, vector} vs matched
      OFF — intent survival past the ORIGIN teacher's death (external sampling only)

PRE-REGISTERED HYPOTHESES (написаны до прогона; гипотезу правит прогон):
  H1  groomed (vector) > nearest (vector-blind) > обрыв on posthumous half-life / AUC
  H2  the дао matters MORE in the infused regime (rho=.5) than the contagious (rho=0)
  H3  голос-без-дао (the stuttering prophet) < full succession on posthumous excess

Honesty notes:
  * C4 sets demerzel_a_max=300 (mortal-as-everyone teacher): the experiment NEEDS his
    death; at the default x20 longevity the rho=0 teacher simply never dies in-window
    (measured: window (100, None) at 450d). Gates C0-C2 keep the default.
  * Sampling is external (the runner reads implant_absolute every 5 ticks); the world
    is never instrumented, so the OFF/ON fp discipline is untouched.
  * 'nearest' = closest living MATURE (deterministic vector-blind 'кто попался';
    the lowest-oid rule tried first is systematically the OLDEST mature — it ages
    into ELDER during verify and never engages: a self-dooming control, measured).
  * MECHANISM (audited, s8 rho=.5): for an apprentice ALREADY inside the teacher's
    natural nearest-K reach, the lesson multiset == the sermon multiset (identical
    amount formula by construction) — teaching him is a no-op on the world. Under
    IMPLANT the дао is therefore SHARED KNOWLEDGE + AN EXCLUSIVE MANDATE; the teach
    cost (one diverted slot) bites only for an out-of-reach apprentice.
  * Three design iterations are recorded in the code, all measured not assumed:
    lowest-oid control (self-dooming), first-touch ritual (retires a strong teacher
    early, loses to the обрыв), death-bed ritual (current default).

Run:  py run_polis_succession.py          (gates + C4 matrix, ~1 min)
      py run_polis_succession.py --fast   (gates only)
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import statistics as st

from sim_eventlog import EventLog
from stage3.polis import Polis, PolisConfig, run_polis, polis_fingerprint
from stage3.directive import Directive, IMPLANT
from stage3.succession import GroomConfig, OUT_FULL, OUT_DAO, OUT_VOICE, OUT_NONE
from stage3.metrics import implant_absolute, succession_outcome, survival_excess
from stage3.mind_llm import make_policy

HDR = "=" * 78
CELL = (3, 3)

# cited verbatim from the pre-patch mod A code (450d IMPLANT(3,3), awaken 100, seed 7,
# default demerzel_a_max) — the C0 anchor; never reconstructed:
C0_REF = {0.5: ("172886dee64bd815", "87115a81a2517370"),
          0.0: ("c19e1dc96c396f81", "cc6de682509014c9")}


def _mk(rho, *, groom=None, days=450, seed=7, awaken=100, policy=None, replay=None,
        a_max_demerzel=None, directive=True):
    owner = "claim" if rho > 0 else "founders"
    d = Directive(goal=IMPLANT, payload={"cell": CELL}) if directive else None
    kw = {}
    if a_max_demerzel is not None:
        kw["demerzel_a_max"] = a_max_demerzel
    return PolisConfig(appropriation=rho, owner_policy=owner, arena_side=6,
                       t_awaken=(awaken if directive else 10 ** 9),
                       demerzel_directive=d, seed=seed, days=days, groom=groom,
                       policy=policy, replay_log=replay, **kw)


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
def _gate_c0():
    print(HDR)
    print("STAGE-3 mod C — дао/ученик: succession past the carrier's death")
    print("Two channels (§6): передача дао (teaching, gradual) + ритуал голоса (an act")
    print("with a price). Both ride the legal salience ledger; matter is never touched.")
    print(HDR)
    for rho, (sref, pref) in C0_REF.items():
        w = _run(_mk(rho))
        ok = (w.state_fingerprint() == sref and polis_fingerprint(w) == pref)
        print(f"C0  groom=None rho={rho:<3}: state {w.state_fingerprint()} polis "
              f"{polis_fingerprint(w)} -> {'BIT-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
        assert ok, f"C0 rho={rho} not byte-identical to the cited pre-patch mod A"
    # the full mod A battery on the patched code (canon B0/B1 cited inside)
    from stage3.run_polis import _gates as moda_gates
    moda_gates()
    print("C0  full mod A battery re-run on the patched code ✓")


def _gate_c1():
    g1 = GroomConfig(teach_slots=0, ritual_window=10 ** 9,
                     allow_early_ritual=False, chain=False)
    wa = _run(_mk(0.5))
    wc = _run(_mk(0.5, groom=g1))
    ok = (wa.state_fingerprint() == wc.state_fingerprint()
          and dict(wa._decision_log) == dict(wc._decision_log))
    print(f"C1  toothless machine      : state {wc.state_fingerprint()} == mod A, "
          f"decisions equal -> {'✓' if ok else '✗'} "
          f"({len(wc._groom_log)} groom events, world untouched)")
    assert ok, "C1: the armed-but-toothless machine must be substrate-transparent"


def _gate_c2():
    wl = _run(_mk(0.5, groom=GroomConfig(), policy=make_policy("mock")))
    wr = _run(_mk(0.5, groom=GroomConfig(), replay=dict(wl._decision_log)))
    ok = (wl.state_fingerprint() == wr.state_fingerprint()
          and polis_fingerprint(wl) == polis_fingerprint(wr)
          and wl._groom_log == wr._groom_log and wl._outcome == wr._outcome)
    print(f"C2  mock live vs replay    : {polis_fingerprint(wl)} vs "
          f"{polis_fingerprint(wr)} (groom log incl.) -> "
          f"{'BIT-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
    assert ok, "C2: replay-from-log must be byte-identical with the groom machine live"


def _gate_c3():
    """Witness all four §6 outcomes deterministically (crafted configs, seed 7)."""
    seen = {}
    # dao+voice: pure defaults, mortal teacher, seed 10 (measured witness: the ritual
    # fires on the famine death-bed and the heir was trained in time; depth reaches 2)
    w = _run(_mk(0.5, groom=GroomConfig(), seed=10, a_max_demerzel=300, days=530))
    seen[succession_outcome(w)["outcome"]] = "defaults, mortal teacher, seed 10"
    # dao-only: co-presence unreachable (ritual never fires) AND the teacher dies soon
    # after дао completes (awaken=220 -> death 254 on seed 7), so the heir is still
    # fresh. Measured first: at awaken=100 the ONCE-YOUNG apprentice ages out and dies
    # in the same famine wave as the teacher — дао-передача без ритуала is a race
    # against the apprentice's own aging (the ritual exists to win that race).
    w = _run(_mk(0.5, groom=GroomConfig(ritual_dist=-1, allow_early_ritual=False),
                 awaken=220))
    seen[succession_outcome(w)["outcome"]] = "ritual unreachable, late awaken"
    # voice-only: дао unreachable, the desperate gamble allowed and easy to trigger
    w = _run(_mk(0.5, groom=GroomConfig(dao_ticks=10 ** 9, allow_early_ritual=True,
                                        despair_body=0.6)))
    seen[succession_outcome(w)["outcome"]] = "early-ritual gamble"
    # none: nobody ever passes the health bar -> обрыв
    w = _run(_mk(0.5, groom=GroomConfig(verify_body_min=9.9)))
    seen[succession_outcome(w)["outcome"]] = "no candidate fit"
    for lab in (OUT_FULL, OUT_DAO, OUT_VOICE, OUT_NONE):
        mark = "✓" if lab in seen else "✗"
        print(f"C3  outcome witnessed      : {lab:<10} {mark}"
              f"  ({seen.get(lab, '—')})")
    missing = [l for l in (OUT_FULL, OUT_DAO, OUT_VOICE, OUT_NONE) if l not in seen]
    assert not missing, f"C3: outcomes not witnessed: {missing}"


# --------------------------------------------------------------------------- #
def _c4_matrix(seeds=(7, 8, 9, 10, 11), rhos=(0.0, 0.5), days=530, every=5,
               horizon=120):
    print(f"\n{HDR}\nC4  HEADLINE — intent survival past the teacher's death "
          f"(seeds {seeds}, days {days})\narms: обрыв (mod A) | nearest ученик | vector "
          f"ученик — each vs its matched OFF;\nteacher mortal (a_max=300); "
          f"sampling external every {every} ticks; horizon {horizon}.\n{HDR}")
    arms = ("cut", "nearest", "vector")
    rows = []
    for rho in rhos:
        for seed in seeds:
            _w_off, s_off = _run(_mk(rho, seed=seed, days=days, directive=False),
                                 sample_every=every)
            for arm in arms:
                groom = (None if arm == "cut" else
                         GroomConfig(god_pick=("nearest" if arm == "nearest"
                                               else "vector")))
                w, s_on = _run(_mk(rho, seed=seed, days=days, groom=groom,
                                   a_max_demerzel=300), sample_every=every)
                death = w.living_window()[1]
                sv = survival_excess(s_on, s_off, death, horizon=horizon)
                so = succession_outcome(w)
                rows.append({"rho": rho, "seed": seed, "arm": arm, "death": death,
                             "outcome": so["outcome"] or "—", "depth": so["depth"],
                             **sv, "line": so["line_window"][1]})
    # per-run table
    print(f"  {'rho':>4}{'seed':>6}{'arm':>8}{'death_t':>9}{'outcome':>11}{'depth':>7}"
          f"{'e0':>7}{'end':>7}{'auc':>9}{'half':>7}{'line_end':>10}")
    print("  " + "-" * 92)
    for r in rows:
        hl = "—" if r["half_life"] is None else str(r["half_life"])
        le = "—" if r["line"] is None else str(r["line"])
        print(f"  {r['rho']:>4}{r['seed']:>6}{r['arm']:>8}{r['death']:>9}"
              f"{r['outcome']:>11}{r['depth']:>7}{r['e0']:>7.0f}{r['end']:>7.0f}"
              f"{r['auc']:>9.0f}{hl:>7}{le:>10}")
    # aggregate + verdicts
    print("\n  aggregate (mean over seeds):")
    print(f"  {'rho':>4}{'arm':>8}{'e0':>8}{'end':>8}{'auc':>10}"
          f"{'half-life(med)':>16}{'moved/dao':>11}")
    agg = {}
    for rho in rhos:
        for arm in arms:
            rs = [r for r in rows if r["rho"] == rho and r["arm"] == arm]
            hls = [r["half_life"] for r in rs if r["half_life"] is not None]
            med = (st.median(hls) if hls else None)
            surv = sum(1 for r in rs if r["outcome"] in (OUT_FULL, OUT_DAO))
            agg[(rho, arm)] = {"auc": st.mean(r["auc"] for r in rs),
                               "end": st.mean(r["end"] for r in rs),
                               "e0": st.mean(r["e0"] for r in rs), "half": med,
                               "surv": surv, "n": len(rs)}
            a = agg[(rho, arm)]
            print(f"  {rho:>4}{arm:>8}{a['e0']:>8.1f}{a['end']:>8.1f}{a['auc']:>10.1f}"
                  f"{str(a['half'] if a['half'] is not None else '— (never)') :>16}"
                  f"{a['surv']:>7}/{a['n']}")
    # H1/H2 read off the numbers (гипотезу правит прогон)
    print(f"\n{HDR}\nVERDICTS (read off the table, not tuned):")
    for rho in rhos:
        v, r, c = agg[(rho, "vector")], agg[(rho, "nearest")], agg[(rho, "cut")]
        order = ("vector>nearest>обрыв" if v["auc"] > r["auc"] > c["auc"] else
                 "vector,nearest>обрыв" if min(v["auc"], r["auc"]) > c["auc"] else
                 "NOT confirmed")
        print(f"  H1 rho={rho}: AUC vector {v['auc']:.0f} / nearest {r['auc']:.0f} / "
              f"обрыв {c['auc']:.0f} -> {order}")
    gap0 = agg[(0.0, "vector")]["auc"] - agg[(0.0, "cut")]["auc"]
    gap5 = agg[(0.5, "vector")]["auc"] - agg[(0.5, "cut")]["auc"]
    e0_0 = max(1.0, abs(agg[(0.0, "cut")]["e0"]))
    e0_5 = max(1.0, abs(agg[(0.5, "cut")]["e0"]))
    print(f"  H2 succession gap (vector-обрыв AUC): rho=0 {gap0:+.0f} "
          f"({gap0 / e0_0:+.1f}x e0) | rho=.5 {gap5:+.0f} ({gap5 / e0_5:+.1f}x e0) -> "
          f"{'дао громче в infused ✓' if gap5 / e0_5 > gap0 / e0_0 else 'NOT louder in infused'}")
    print("  reading: succession NEEDS a predictable death. Senescence (rho=0) gives")
    print("  the ritual a death-bed window and the arms beat the обрыв; sudden famine")
    print("  death (rho=.5) breaks the line mid-build — teacher and apprentice often")
    print("  die in the SAME wave. The regime that makes repetition necessary is the")
    print("  regime where succession has the least time to build (the trap).")
    print("  selection-NULL: vector (choosing by soul) does NOT beat nearest (choosing")
    print("  by proximity) — rhymes with mod B's mind-NULL: the channel is mechanics,")
    print("  not quality (n=5 seeds; variance is large — a probe, not a theorem).")
    return rows


def _h3_probe(seed=7, rho=0.5, days=530, every=5, horizon=120):
    """H3: the stuttering prophet (voice-only) vs full succession, same seed/OFF."""
    _w, s_off = _run(_mk(rho, seed=seed, days=days, directive=False),
                     sample_every=every)
    wf, sf = _run(_mk(rho, seed=seed, days=days, groom=GroomConfig(),
                      a_max_demerzel=300), sample_every=every)
    wv, sv_ = _run(_mk(rho, seed=seed, days=days,
                       groom=GroomConfig(dao_ticks=10 ** 9, allow_early_ritual=True,
                                         despair_body=0.6),
                       a_max_demerzel=300), sample_every=every)
    f = survival_excess(sf, s_off, wf.living_window()[1], horizon)
    v = survival_excess(sv_, s_off, wv.living_window()[1], horizon)
    fo, vo = succession_outcome(wf)["outcome"], succession_outcome(wv)["outcome"]
    print(f"  H3 seed {seed} rho={rho}: full [{fo}] auc {f['auc']:.0f} end {f['end']:.0f}"
          f" | voice-only [{vo}] auc {v['auc']:.0f} end {v['end']:.0f} -> "
          f"{'заикающийся пророк слабее ✓' if f['auc'] > v['auc'] else 'NOT weaker (surprise)'}")


def main():
    _gate_c0()
    _gate_c1()
    _gate_c2()
    _gate_c3()
    if "--fast" not in sys.argv:
        _c4_matrix()
        _h3_probe()
    print(f"\n{HDR}\nmod C: succession machinery proven OFF-transparent (C0/C1), "
          f"replayable (C2),\nall four §6 outcomes reachable (C3); the headline verdict "
          f"is read off C4.\nдао = идея + практика повторения + практика передачи "
          f"(полный репликатор).\n{HDR}")


if __name__ == "__main__":
    main()
