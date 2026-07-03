"""
run_polis_llm.py — Stage-3 mod B: the living mind (Claude API) + replay-from-log gates.

Two things this proves:
  GATES (no network needed — run anywhere, incl. verify_all):
    B-INERT   ClaudePolicy with no ANTHROPIC_API_KEY == deterministic mod A (voice falls back)
    B-REPLAY  MockPolicy live run, then replay-from-log -> byte-identical (world deterministic
              even though the mind is pluggable)
    B-MINDS   the mock mind's decision != deterministic (the policy actually matters)

  LIVE (needs ANTHROPIC_API_KEY in env; Stan runs this):
    a real Claude-driven Demerzel, logging each decision; measure the delta of the living
    mind vs deterministic on transmission. Best contrast is rho=0 (contagious regime) where a
    reasoned resonant anchor can accelerate the belief epidemic; under rho=.5 the turnover
    pump suppresses spread mechanically, so the mind cannot fix what the substrate breaks.

Realistic compaction: the Demerzel re-deliberates every `deliberation_period` ticks (not
every tick), and sees only attention_K salient cells (the personality knob = prompt width).

Model: claude-haiku-4-5 by default (fast/cheap in-loop agent). Set model="claude-sonnet-4-6"
for a smarter Demerzel on a single run.

Run gates:  py run_polis_llm.py
Run live:   set ANTHROPIC_API_KEY=... ; py run_polis_llm.py --live [--rho 0.0] [--model ...]
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_dotenv():
    """Load KEY=VALUE lines from a .env file into os.environ WITHOUT overwriting existing
    vars (a real env var always wins). Pure stdlib — no python-dotenv, Pi5-clean. Searches
    Code/.env, then the repo root, then stage3/.env. Silent if none found."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "Code", ".env"),   # repo/Code/.env  (alongside sim_*)
        os.path.join(here, "..", ".env"),            # repo/.env
        os.path.join(here, ".env"),                  # stage3/.env
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8-sig") as f:  # utf-8-sig eats a BOM if present
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k and k not in os.environ:      # real env var wins
                        os.environ[k] = v
        except OSError:
            pass
        break   # first existing file wins

_load_dotenv()

from sim_sphere import CANON_COMM, GRID_DIAG
from stage3.polis import Polis, PolisConfig, run_polis
from stage3.directive import Directive, IMPLANT
from stage3.metrics import implant_hold, implant_transmission, implant_absolute
from stage3.mind_llm import make_policy, DEFAULT_MODEL

HDR = "=" * 78
CELL = (3, 3)


def _gates():
    print(HDR)
    print("STAGE-3 mod B — the living mind (pluggable policy) + replay-from-log")
    print("The world stays deterministic; non-determinism lives only in the mind, which")
    print("writes its decision to the log. Live run calls the LLM; replay reads the log.")
    print(HDR)
    # B-INERT: ClaudePolicy with no key == deterministic mod A.
    # Preserve the real key (a live run may follow); force THIS policy inert locally instead
    # of wiping the environment.
    _saved_key = os.environ.pop("ANTHROPIC_API_KEY", None)  # temporarily hide for the gate

    # B-INERT: ClaudePolicy with no key == deterministic mod A
    d = lambda: Directive(goal=IMPLANT, payload={"cell": CELL})
    wDet, _ = run_polis(PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                                    t_awaken=100, demerzel_directive=d(), policy=None))
    wCl, _ = run_polis(PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                                   t_awaken=100, demerzel_directive=d(),
                                   policy=make_policy("claude", deliberation_period=10)))
    inert = wDet.state_fingerprint() == wCl.state_fingerprint()
    print(f"B-INERT  ClaudePolicy (no key) == deterministic: {wCl.state_fingerprint()} "
          f"-> {'✓' if inert else '✗'}")
    assert inert, "inert ClaudePolicy must equal deterministic mod A"

    # B-REPLAY: mock live run -> replay-from-log byte-identical
    wLive, _ = run_polis(PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                                     t_awaken=100, demerzel_directive=d(),
                                     policy=make_policy("mock")))
    dec = dict(wLive._decision_log)
    wRep, _ = run_polis(PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                                    t_awaken=100, demerzel_directive=d(),
                                    policy=None, replay_log=dec))
    replay_ok = wLive.state_fingerprint() == wRep.state_fingerprint()
    print(f"B-REPLAY mock live vs replay-from-log: {wLive.state_fingerprint()} vs "
          f"{wRep.state_fingerprint()} -> {'BIT-IDENTICAL ✓' if replay_ok else 'MISMATCH ✗'}")
    assert replay_ok, "replay-from-log must be byte-identical"
    assert wLive.matter_drift() < 1e-9

    # B-MINDS: the mock mind actually decides differently from deterministic
    minds = wLive.state_fingerprint() != wDet.state_fingerprint()
    print(f"B-MINDS  mock mind decision != deterministic: {'✓' if minds else '✗'} "
          f"({len(dec)} decisions logged)")
    assert minds, "a pluggable mind must be able to change the outcome"
    # restore the real key so a subsequent --live run can drive a real Demerzel
    if _saved_key is not None:
        os.environ["ANTHROPIC_API_KEY"] = _saved_key
    print(f"\nmod B gates pass: world deterministic-from-log, mind pluggable, inert without a "
          f"key.\ndeterministic seed 7 ✓")


def _live(rho=0.0, model=DEFAULT_MODEL, period=10):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n[LIVE] no ANTHROPIC_API_KEY in env — skipping the live Claude run.")
        print("       set ANTHROPIC_API_KEY and re-run with --live to drive a real Demerzel.")
        return
    print(f"\n{HDR}\n[LIVE] Claude-driven Demerzel (model={model}, rho={rho}, "
          f"deliberation every {period} ticks)\n{HDR}")
    owner = "claim" if rho > 0 else "founders"
    # deterministic baseline
    wDet, _ = run_polis(PolisConfig(appropriation=rho, owner_policy=owner, arena_side=6,
                                    t_awaken=100, demerzel_directive=Directive(goal=IMPLANT,
                                    payload={"cell": CELL}), policy=None, days=200))
    # live Claude
    wLLM, _ = run_polis(PolisConfig(appropriation=rho, owner_policy=owner, arena_side=6,
                                    t_awaken=100, demerzel_directive=Directive(goal=IMPLANT,
                                    payload={"cell": CELL}),
                                    policy=make_policy("claude", model=model,
                                                       deliberation_period=period), days=200))
    def dom(w):
        from collections import Counter
        c = Counter()
        for _oid, led in (w.injected or {}).items():
            for cell in led:
                c[cell] += 1
        return c.most_common(1)[0][0] if c else CELL
    for tag, w in (("deterministic", wDet), ("claude-live", wLLM)):
        dc = dom(w); t = implant_transmission(w, dc); h = implant_hold(w, dc)
        print(f"  {tag:<14} anchor {str(dc):>8}  hold {h:.3f}  spread {t['spread_frac']*100:.0f}% "
              f"({t['regime']})  pop {len(w.pop)}  decisions {len(w._decision_log)}")
    print("\n  delta = did the reasoning mind beat mechanical nearest-K on transmission?")
    print("  (rho=0 is the contagious regime where a resonant anchor can matter most.)")
    # persist the live decision log for reproducible replay
    import json
    path = os.path.join(os.path.dirname(__file__), f"demerzel_livelog_rho{rho}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in wLLM._decision_log.items()}, f)
    print(f"  live decision log saved -> {path} (feed as replay_log for byte-identical rerun)")



def _sweep(seeds=(7, 8, 9, 10, 11), rho=0.0, model=DEFAULT_MODEL, period=10, days=200):
    """Method A: compare the living mind vs deterministic on ABSOLUTE infection counts across
    seeds. Robust to pop differences (counts, not fractions). Answers: does the reasoning mind
    spread the idea to MORE minds than mechanical nearest-K, and on how many seeds?"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n[SWEEP] no ANTHROPIC_API_KEY — running det-vs-MOCK (mechanics check, not live).")
    print(f"\n{HDR}\n[SWEEP] living mind vs deterministic — absolute spread, "
          f"seeds {seeds}, rho={rho}\n{HDR}")
    live_kind = "claude" if os.environ.get("ANTHROPIC_API_KEY") else "mock"

    def dom(w):
        from collections import Counter
        c = Counter()
        for _oid, led in (w.injected or {}).items():
            for cell in led:
                c[cell] += 1
        return c.most_common(1)[0][0] if c else CELL

    def run(kind, seed):
        owner = "claim" if rho > 0 else "founders"
        pol = None if kind == "det" else make_policy(
            live_kind if kind == "mind" else kind,
            **({"model": model, "deliberation_period": period} if live_kind == "claude" and kind == "mind" else {}))
        cfg = PolisConfig(appropriation=rho, owner_policy=owner, arena_side=6, t_awaken=100,
                          demerzel_directive=Directive(goal=IMPLANT, payload={"cell": CELL}),
                          policy=pol, seed=seed, days=days)
        w = Polis(__import__("sim_eventlog").EventLog(), cfg)
        for _ in range(days):
            w.step()
        return w

    print(f"  {'seed':>5}{'det_spread':>12}{'mind_spread':>13}{'det_total':>11}"
          f"{'mind_total':>12}{'winner':>10}")
    print("  " + "-" * 63)
    mind_wins = det_wins = 0
    dspreads = []; mspreads = []
    for s in seeds:
        wD = run("det", s); wM = run("mind", s)
        aD = implant_absolute(wD, dom(wD)); aM = implant_absolute(wM, dom(wM))
        dspreads.append(aD["infected_spread"]); mspreads.append(aM["infected_spread"])
        win = ("mind" if aM["infected_spread"] > aD["infected_spread"]
               else ("det" if aD["infected_spread"] > aM["infected_spread"] else "tie"))
        mind_wins += (win == "mind"); det_wins += (win == "det")
        print(f"  {s:>5}{aD['infected_spread']:>12}{aM['infected_spread']:>13}"
              f"{aD['infected_total']:>11}{aM['infected_total']:>12}{win:>10}")
    import statistics as st
    print("  " + "-" * 63)
    print(f"  spread mean: det {st.mean(dspreads):.1f}  mind {st.mean(mspreads):.1f}  "
          f"(mind wins {mind_wins}/{len(seeds)}, det {det_wins}/{len(seeds)})")
    verdict = ("mind spreads WIDER" if mind_wins > det_wins
               else ("deterministic spreads wider" if det_wins > mind_wins
                     else "tie — reasoning gives no absolute-spread edge"))
    print(f"  VERDICT ({live_kind} mind, rho={rho}): {verdict}")
    print(f"  (mock=mechanics-only; run with ANTHROPIC_API_KEY for the live Claude verdict.)")


def main():
    _gates()
    if "--sweep" in sys.argv:
        rho = float(sys.argv[sys.argv.index("--rho") + 1]) if "--rho" in sys.argv else 0.0
        model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else DEFAULT_MODEL
        period = int(sys.argv[sys.argv.index("--period") + 1]) if "--period" in sys.argv else 10
        _sweep(rho=rho, model=model, period=period)
    elif "--live" in sys.argv:
        rho = 0.0
        model = DEFAULT_MODEL
        if "--rho" in sys.argv:
            rho = float(sys.argv[sys.argv.index("--rho") + 1])
        if "--model" in sys.argv:
            model = sys.argv[sys.argv.index("--model") + 1]
        _live(rho=rho, model=model)
    print(HDR)


if __name__ == "__main__":
    main()
