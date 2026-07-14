"""run_frailty_noread.py — mod-J gate MJ-NOREAD: the pawn cannot read its own frailty.

The ВСТАВКА-27 lesson, wired into a gate. A stake that is legible off the body
(s = (SAFE_RESERVE-body)/(SAFE_RESERVE-DEATH)) is readable, reversible, non-accumulating —
and produced a NULL. Frailty must stay UNCOMPUTABLE from the substrate: `_blocks` may never
appear in the view a mind is handed, hence never in the LLM prompt (the ClaudeTypedPolicy
user message is literally json.dumps(view); the SYSTEM string is fixed and states only the
readable age/a_max/body).

This harness drives a C-LIVE run (a typed mock mind IS the teacher) with frailty ON, so a
mind is consulted under real senescence pressure — pawns around it are dying of exhausted
redundancy — and captures EVERY view.act() hands the mind. For every captured view (== the
prompt) it asserts no frailty token is present. The static SYSTEM prompt is checked too.

If any token leaks: STOP AND REPORT — the stake became legible and we would reproduce the
ВСТАВКА-27 NULL, only more expensively.

Run:  py stage3/run_frailty_noread.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                                   # noqa: E402
from stage3.polis import Polis                                     # noqa: E402
from stage3.succession import GroomConfig                          # noqa: E402
from stage3.mind_llm import make_typed_policy, ClaudeTypedPolicy   # noqa: E402
from stage3.run_polis_live_c import _mk                            # noqa: E402

HDR = "=" * 78
# The pawn's hidden frailty must never surface in the mind's information. age/a_max/body
# stay READABLE (canon) — they are not here. "frail" also covers "frailty"/"_frailty".
FORBIDDEN = ("_blocks", "frail", "redundancy", "senescence")


class _CapturingMind:
    """Wrap a typed policy; record every view handed to act(). The view is the mind's
    ENTIRE information surface — the live LLM prompt is json.dumps(view) + a fixed SYSTEM."""
    typed = True

    def __init__(self, inner):
        self.inner = inner
        self.views = []

    def act(self, world, head_oid, personality, directive, view):
        if view is not None:
            self.views.append(view)
        return self.inner.act(world, head_oid, personality, directive, view)


def _drive(arm, *, seed=7, days=400, awaken=100):
    mind = _CapturingMind(make_typed_policy("mock"))
    cfg = _mk(0.5, seed=seed, days=days, awaken=awaken, groom=GroomConfig(), policy=mind)
    cfg.frailty = arm                       # senescence live (PolisConfig is mutable)
    w = Polis(EventLog(), cfg)
    for _ in range(days):
        w.step()
    sen = sum(1 for e in w.log.events
              if e.kind == "death" and (e.data or {}).get("cause") == "senescence")
    return mind.views, sen, w


def _scan(views):
    bad = []
    for v in views:
        s = json.dumps(v, default=str)
        for tok in FORBIDDEN:
            if tok in s:
                bad.append((v.get("t"), tok))
    return bad


def main():
    print(HDR)
    print("MJ-NOREAD — the pawn cannot read its own frailty (ВСТАВКА-27, wired to a gate)")
    print(HDR)
    ok = True
    for arm in ("gompertz", "flat"):
        views, sen, _ = _drive(arm)
        bad = _scan(views)
        good = (not bad) and len(views) > 0 and sen > 0
        ok = ok and good
        note = "" if good else (f"  LEAK {bad[:3]}" if bad
                                else "  (no views / no senescence — harness not exercised)")
        print(f"  {arm:>9}: views={len(views):>4}  senescence_deaths={sen:>4}  "
              f"tokens-absent={'✓' if not bad else '✗'}{note}")
    sys_bad = [tok for tok in FORBIDDEN if tok in ClaudeTypedPolicy.SYSTEM]
    ok = ok and not sys_bad
    print(f"  SYSTEM prompt clean of frailty tokens: {'✓' if not sys_bad else '✗ ' + str(sys_bad)}")
    print(f"\n  MJ-NOREAD: {'✓ frailty is uncomputable from the view (every prompt clean)' if ok else '✗ STOP AND REPORT'}")
    assert ok, "MJ-NOREAD: a frailty token reached a mind — the stake became legible"
    print(HDR)


if __name__ == "__main__":
    main()
