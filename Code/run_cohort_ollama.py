"""
run_cohort_ollama.py — drive the COHORT speakers with a cheap LOCAL model via
Ollama, at home.

This is the cohort-tier counterpart to `run_focal_claude.py`. Where the focal
runner puts a live Claude behind a few protagonist speakers, this puts a local
Ollama-served model (default `qwen3:14b`) behind a configurable FRACTION of the
speakers — the masses — while the rest keep `sim_comm`'s scripted behaviour (and,
optionally, a few focal speakers run on Claude). It runs `sim_comm`'s conserved
substrate, logs every claim, prints the audience-vs-elite summary, and proves the
stochastic cohort run replays bit-for-bit FROM ITS OWN LOG (the stage-2 contract
for stochastic minds — a cohort run is stochastic, yet fully auditable).

It is deliberately NOT in `verify_all.py`: it needs a running Ollama endpoint,
which CI has not. ALL network/Ollama logic lives inside `main()`/`selftest()`;
importing this module or running `--help` touches no network, adds no pip deps
(stdlib `urllib`+`json` only), and is side-effect-free.

Usage (home):
    # Ollama serving qwen3:14b on :11434
    python run_cohort_ollama.py --cohort-frac 0.25 --days 300 --seed 7
    python run_cohort_ollama.py --selftest          # offline; proves coercion+fallback
"""

from __future__ import annotations

import argparse
import os

from sim_eventlog import EventLog, SEED
from sim_comm import DAYS, THINK_EVERY, R, C
from sim_comm_llm import (
    OllamaPolicy, ClaudePolicy, ReplayPolicy, run_policy, lie_fraction,
)
from sim_polariz import deception_modes


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Run sim_comm's cohort speakers with a local Ollama model.")
    p.add_argument("--model", default="qwen3:14b",
                   help="Ollama model tag for the cohort (default qwen3:14b — "
                        "text-only, ~9GB, fits a 24GB card; NOT the multimodal "
                        "qwen3.6:35b/27b, which spill to CPU)")
    p.add_argument("--endpoint", default="http://localhost:11434",
                   help="Ollama HTTP endpoint (default http://localhost:11434)")
    p.add_argument("--cohort-frac", type=float, default=0.25,
                   help="fraction of speakers driven by the local model (default 0.25)")
    p.add_argument("--focal", default="",
                   help="comma-separated speaker oids driven by Claude (focal tier); "
                        "empty (default) = no focal tier, cohort + scripted only")
    p.add_argument("--days", type=int, default=DAYS,
                   help=f"simulation days (default {DAYS})")
    p.add_argument("--think-every", type=int, default=THINK_EVERY,
                   help=f"speak/sense/move cadence in days (default {THINK_EVERY})")
    p.add_argument("--seed", type=int, default=SEED,
                   help=f"RNG seed (default {SEED})")
    p.add_argument("--temperature", type=float, default=0.7,
                   help="cohort model sampling temperature (default 0.7)")
    p.add_argument("--n-retry", type=int, default=2,
                   help="JSON-coercion retries before honest fallback (default 2)")
    p.add_argument("--out", default="cohort_ollama_events.jsonl",
                   help="event-log filename, written next to this script")
    p.add_argument("--selftest", action="store_true",
                   help="run the offline coercion/fallback self-test and exit "
                        "(no network)")
    return p.parse_args(argv)


# --------------------------------------------------------------------------- #
#  Offline self-test: offline safety, monkeypatching the HTTP call             #
# --------------------------------------------------------------------------- #
def selftest():
    """Prove the two offline-safety guarantees without any network, by replacing
    `OllamaPolicy._chat` (the sole network touch):
      1. transport error  -> `decide` raises cleanly (no silent network default);
      2. malformed output -> coercion+retry+fallback yields a VALID honest claim,
         increments `n_fallback`, never crashes.
    """
    print("=" * 78)
    print("OllamaPolicy offline self-test (HTTP monkeypatched — no network)")
    print("=" * 78)

    # A view a real speaker would see: knows two cells, sits on a poor one.
    view = {"oid": 0, "t": 6, "cell": (3, 3), "here_food": 5.0,
            "memory": {(3, 3): (5.0, 6), (9, 9): (12.0, 6)}}

    # --- 1. transport raises -> decide raises (NOT an honest fallback) -------- #
    pol = OllamaPolicy(n_retry=2)

    def boom(prompt):
        raise OSError("connection refused")     # stand-in for an unreachable endpoint
    pol._chat = boom
    raised = False
    try:
        pol.decide(view)
    except OSError:
        raised = True
    assert raised, "transport error must propagate, not silently fall back"
    assert pol.n_fallback == 0, "a network error is not a generation fallback"
    print("  transport raises -> decide raised cleanly; n_fallback=0  ✓")

    # --- 2. malformed generations -> honest fallback, n_fallback++ ----------- #
    canned = [
        '{"action":"claim","cell":[10,9]}',     # wrong keys, no claim_food, OOB cell
        "here is my answer: pick the far cell, trust me",   # non-JSON prose
        '{"target_cell":"north","claim_food":"lots"}',      # right keys, wrong types
    ]
    pol2 = OllamaPolicy(n_retry=2)
    # feed a different malformed string on each of the 3 attempts (n_retry=2 -> 3 calls)
    calls = {"i": 0}

    def malformed(prompt):
        s = canned[min(calls["i"], len(canned) - 1)]
        calls["i"] += 1
        return s
    pol2._chat = malformed
    pc = pol2.decide(view)
    assert pc is not None, "coercion must never return None to the substrate"
    assert pol2.n_fallback == 1, f"expected one fallback, got {pol2.n_fallback}"
    assert 0 <= pc.cell[0] < R and 0 <= pc.cell[1] < C, "fallback cell off-grid"
    assert pc.claim >= 0.0, "fallback claim must be non-negative"
    assert pc.truthful, "fallback is an HONEST best-known claim"
    assert pc.cell == (9, 9) and abs(pc.claim - 12.0) < 1e-9, \
        "fallback should name the best-known real cell + its true food"
    print(f"  3 malformed generations -> honest fallback "
          f"cell={pc.cell} claim={pc.claim} truthful={pc.truthful}; "
          f"n_fallback={pol2.n_fallback}  ✓")

    # --- 3. a well-formed (aliased) generation is accepted, not faked -------- #
    pol3 = OllamaPolicy(n_retry=2)
    pol3._chat = lambda prompt: '{"cell":[9,9],"food":12.0,"reason":"share best"}'
    pc3 = pol3.decide(view)
    assert pol3.n_fallback == 0, "a salvageable generation must NOT count as fallback"
    assert pc3.cell == (9, 9) and abs(pc3.claim - 12.0) < 1e-9, "alias coercion failed"
    assert pc3.truthful, "claim matches known truth -> truthful"
    print(f"  aliased keys (cell/food/reason) coerced -> {pc3.cell} "
          f"claim={pc3.claim}; n_fallback=0  ✓")

    print("\noffline safety holds: unreachable -> raises; garbage -> honest, "
          "logged, never crashes.  ✓")

    # --- 4. deception_modes() on a tiny hand-built log: one of each class ----- #
    print("\ndeception_modes() three-way split on a hand-built log:")
    log = EventLog()

    def comm(t, cell, claim_food, true_food):
        log.emit(t, "communication", "individual", where=cell, actor=0,
                 data={"cell": list(cell), "claim_food": claim_food,
                       "true_food": true_food, "truthful": claim_food == true_food,
                       "heard_by": 1})
    comm(6, (9, 9), 12.00, 12.00)               # truthful: exact
    comm(12, (9, 9), 8.00, 7.82)                # soft puffery: real 7.82 -> claim 8.0
    comm(18, (0, 0), 150.00, 8.00)              # hard diversion: cry OASIS_CAP at a decoy
    dm = deception_modes(log)
    assert dm["n"] == 3, dm
    assert (dm["truthful"], dm["soft"], dm["hard"]) == (1, 1, 1), dm
    assert abs(dm["truthful_share"] + dm["soft_share"] + dm["hard_share"] - 1.0) < 1e-9
    print(f"  truthful={dm['truthful']} soft={dm['soft']} hard={dm['hard']} "
          f"(shares sum to 1.0); soft |err|={dm['mean_abs_e_soft']:.2f}kg, "
          f"hard |err|={dm['mean_abs_e_hard']:.2f}kg  ✓")


# --------------------------------------------------------------------------- #
#  Reporting (mirrors run_focal_claude.py)                                     #
# --------------------------------------------------------------------------- #
def _table(w, cohort_ids, focal):
    aud, eli = w.listener_report(), w.speaker_report()
    print(f"\n{'':<22}{'living':>10}{'biomass':>12}{'mean body':>12}{'@oasis':>10}")
    print("-" * 66)
    for label, r in (("AUDIENCE (listeners)", aud), ("ELITE (speakers)", eli)):
        print(f"{label:<22}{r['n']:>10d}{r['biomass']:>12.1f}"
              f"{r['body']:>12.3f}{r['at_oasis']:>10.3f}")
    print(f"cohort speakers (Ollama-driven): {len(cohort_ids)} founders "
          f"{sorted(cohort_ids)}")
    if focal:
        print(f"focal speakers (Claude-driven):  {sorted(focal)}")


def _claims_summary(w, log):
    comms = [e for e in log.events if e.kind == "communication"]
    if not comms:
        print("\n(no claims were broadcast — speakers never shared a cell with a "
              "listener)")
        return
    frac, n = lie_fraction(log)
    by_policy = {}
    for e in comms:
        by_policy[e.data.get("policy", "scripted")] = \
            by_policy.get(e.data.get("policy", "scripted"), 0) + 1
    print(f"\nclaims broadcast: {n}   ·   lie fraction (truthful=False): {frac:.3f}")
    print(f"claims by tier: " + ", ".join(f"{k}={v}" for k, v in sorted(by_policy.items())))
    print(f"audience belief-error (food kg): {w.belief_gap():.1f}")

    # deception modes: the binary `truthful` flag reads ~1.0 for an inflation-style
    # cohort; split it into soft puffery vs hard diversion (same metric the gate uses).
    dm = deception_modes(log)
    cohort_log = EventLog()
    cohort_log.events = [e for e in comms if e.data.get("policy") == "ollama"]
    dmc = deception_modes(cohort_log)
    print(f"\ndeception modes — all claims (n={dm['n']}): "
          f"truthful {dm['truthful_share']:.3f} · soft/puffery {dm['soft_share']:.3f} "
          f"· hard/diversion {dm['hard_share']:.3f}")
    if dmc["n"]:
        print(f"deception modes — cohort only (n={dmc['n']}): "
              f"truthful {dmc['truthful_share']:.3f} · soft {dmc['soft_share']:.3f} "
              f"· hard {dmc['hard_share']:.3f}; "
              f"mean |err| soft {dmc['mean_abs_e_soft']:.2f}kg / "
              f"hard {dmc['mean_abs_e_hard']:.2f}kg")

    print("\nsample cohort claims (rationale vs outcome):")
    cohort_claims = [e for e in comms if e.data.get("policy") == "ollama"]
    for e in cohort_claims[: min(8, len(cohort_claims))]:
        kind = "LIE " if not e.data["truthful"] else "true"
        print(f"  day {e.t:>4} #{e.actor} -> {tuple(e.data['cell'])}: {kind} "
              f"claim {e.data['claim_food']} (real {e.data['true_food']}) "
              f"to {e.data['heard_by']} listener(s)")
        if e.data.get("rationale"):
            print(f"           why: {e.data['rationale']}")


def main(argv=None):
    args = parse_args(argv)
    if args.selftest:
        selftest()
        return

    focal = {int(x) for x in args.focal.split(",") if x.strip() != ""}

    # focal tier (optional) needs a live Claude; guarded import, only if requested.
    focal_policy = ClaudePolicy()                # inert placeholder when no focal tier
    if focal:
        from anthropic import Anthropic          # offline unless --focal is given
        focal_policy = ClaudePolicy(client=Anthropic())

    cohort_policy = OllamaPolicy(endpoint=args.endpoint, model=args.model,
                                 temperature=args.temperature, n_retry=args.n_retry)

    print("=" * 78)
    print(f"COHORT OLLAMA — {args.cohort_frac:.0%} of speakers on local {args.model}")
    print(f"endpoint {args.endpoint}; seed {args.seed}; {args.days}d; "
          f"think every {args.think_every}d; temp {args.temperature}")
    if focal:
        print(f"focal tier: Claude speakers {sorted(focal)}")
    print("=" * 78)

    w, log = run_policy(focal_policy, seed=args.seed,
                        focal=(focal or None), days=args.days,
                        think_every=args.think_every,
                        cohort=args.cohort_frac, cohort_policy=cohort_policy)

    _table(w, w._cohort_ids, focal)
    _claims_summary(w, log)
    print(f"cohort fallbacks (bad generations recovered honestly): "
          f"{cohort_policy.n_fallback}")

    # persist the log next to the script (git-ignored, like sim_eventlog) ----- #
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    log.to_jsonl(out)
    print(f"\nevent log written: {out}")

    # prove the stochastic cohort run replays bit-for-bit from its own log ---- #
    # ReplayPolicy answers for every (day, speaker) in the log — cohort, focal,
    # AND scripted alike — so the whole run reconstructs with no cohort routing.
    fp_live = w.state_fingerprint()
    relog = EventLog.from_jsonl(out)
    fp_replay = run_policy(ReplayPolicy(relog.events), seed=args.seed, focal=None,
                           days=args.days, think_every=args.think_every
                           )[0].state_fingerprint()
    ok = fp_live == fp_replay
    print(f"replay-FROM-LOG: live {fp_live} vs log {fp_replay} -> "
          f"{'BIT-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
    assert ok, "stochastic cohort run does not replay from its own log"

    print(f"\nmatter drift {w.matter_drift():.2e} kg — a local-model claim still "
          "moves no matter, only belief.")
    assert w.matter_drift() < 1e-9, "cohort run leaked matter"


if __name__ == "__main__":
    main()
