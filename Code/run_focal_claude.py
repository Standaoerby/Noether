"""
run_focal_claude.py — drive the focal speakers with a LIVE Claude model, at home.

This is the wired-at-home counterpart to sim_comm_llm's CI-safe demo. It puts a
real Claude behind `ClaudePolicy` for a handful of FOCAL speakers, runs sim_comm's
conserved substrate, logs every claim, and then proves the stochastic speaker
replays bit-for-bit from that log alone (the stage-2 contract for stochastic minds).

It is deliberately NOT in `verify_all.py`: it needs network + an API key, neither of
which exists in CI. The `anthropic` SDK is imported only inside `main()`, after
argument parsing, so importing this module or running `--help` touches no network.

Usage (home):
    export ANTHROPIC_API_KEY=...
    python run_focal_claude.py --focal 0,4,8 --days 300 --think-every 6 \
                               --seed 7 --model claude-sonnet-4-6
"""

from __future__ import annotations

import argparse
import os

from sim_eventlog import EventLog, SEED
from sim_comm import DAYS, THINK_EVERY
from sim_comm_llm import (
    ClaudePolicy, ReplayPolicy, run_policy, lie_fraction,
)


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Run sim_comm's focal speakers with a live Claude model.")
    p.add_argument("--focal", default="0,4,8",
                   help="comma-separated speaker oids driven by Claude "
                        "(default: 0,4,8 — a few founder speakers)")
    p.add_argument("--days", type=int, default=DAYS,
                   help=f"simulation days (default {DAYS})")
    p.add_argument("--think-every", type=int, default=THINK_EVERY,
                   help=f"speak/sense/move cadence in days (default {THINK_EVERY})")
    p.add_argument("--seed", type=int, default=SEED,
                   help=f"RNG seed (default {SEED})")
    p.add_argument("--model", default="claude-sonnet-4-6",
                   help="Claude model id (default claude-sonnet-4-6)")
    p.add_argument("--out", default="focal_claude_events.jsonl",
                   help="event-log filename, written next to this script")
    return p.parse_args(argv)


def _table(w, focal):
    aud, eli = w.listener_report(), w.speaker_report()
    print(f"\n{'':<22}{'living':>10}{'biomass':>12}{'mean body':>12}{'@oasis':>10}")
    print("-" * 66)
    for label, r in (("AUDIENCE (listeners)", aud), ("ELITE (speakers)", eli)):
        print(f"{label:<22}{r['n']:>10d}{r['biomass']:>12.1f}"
              f"{r['body']:>12.3f}{r['at_oasis']:>10.3f}")
    print(f"focal speakers (Claude-driven): {sorted(focal)}")


def _rationale_vs_outcome(log):
    comms = [e for e in log.events if e.kind == "communication"]
    if not comms:
        print("\n(no claims were broadcast — focal speakers never shared a cell "
              "with a listener)")
        return
    frac, n = lie_fraction(log)
    print(f"\nclaims broadcast: {n}   ·   lie fraction (truthful=False): {frac:.3f}")
    print("\nrationale vs outcome (sample of focal claims):")
    for e in comms[: min(8, len(comms))]:
        kind = "LIE " if not e.data["truthful"] else "true"
        print(f"  day {e.t:>4} #{e.actor} -> {tuple(e.data['cell'])}: {kind} "
              f"claim {e.data['claim_food']} (real {e.data['true_food']}) "
              f"to {e.data['heard_by']} listener(s)")
        if e.data.get("rationale"):
            print(f"           why: {e.data['rationale']}")


def main(argv=None):
    args = parse_args(argv)
    focal = {int(x) for x in args.focal.split(",") if x.strip() != ""}

    # Guarded here, after parsing: importing this module / running --help is offline.
    from anthropic import Anthropic

    client = Anthropic()                      # reads ANTHROPIC_API_KEY from env
    policy = ClaudePolicy(client=client, model=args.model)

    print("=" * 78)
    print(f"FOCAL CLAUDE — live speakers {sorted(focal)} on sim_comm's substrate")
    print(f"model {args.model}; seed {args.seed}; {args.days}d; "
          f"think every {args.think_every}d")
    print("=" * 78)

    w, log = run_policy(policy, seed=args.seed, focal=focal,
                        days=args.days, think_every=args.think_every)

    _table(w, focal)
    _rationale_vs_outcome(log)

    # persist the log next to the script (like sim_eventlog) ------------------ #
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    log.to_jsonl(out)
    print(f"\nevent log written: {out}")

    # prove the stochastic speaker replays bit-for-bit from its log ----------- #
    fp_live = w.state_fingerprint()
    relog = EventLog.from_jsonl(out)
    fp_replay = run_policy(ReplayPolicy(relog.events), seed=args.seed, focal=focal,
                           days=args.days, think_every=args.think_every
                           )[0].state_fingerprint()
    ok = fp_live == fp_replay
    print(f"replay-FROM-LOG: live {fp_live} vs log {fp_replay} -> "
          f"{'BIT-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
    print(f"\nmatter drift {w.matter_drift():.2e} kg — a live claim still moves no "
          "matter, only belief.")


if __name__ == "__main__":
    main()
