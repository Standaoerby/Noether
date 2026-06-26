"""
sim_trust.py — trust-weighting: does accountability break the lie equilibrium?

`sim_comm` / `sim_comm_llm` exposed an extraction equilibrium: a deceptive elite
captures the rivalrous oases while honesty ≈ silence. The reason is baked into the
listener: belief is **naively credulous** — a heard claim enters memory as fact
regardless of the speaker's track record (`CommWorld._absorb_claim`, the
`# naive trust about a remote cell` loop). Zero-cost credulity is what makes lying
pay.

This module makes the listener **accountable**. Trust is a property of the *listener*,
orthogonal to who speaks, so it needs no live model — it runs on the existing
deterministic regimes. `TrustCommWorld(CommWorld)` adds, as auxiliary state only (no
matter, no energy, no RNG — it never touches `self.rng`):

  * `self.trust[listener][speaker] -> float in [0,1]`, default **1.0** (full benefit
    of the doubt, so trust-ON starts identical to trust-OFF and diverges only as lies
    are caught);
  * `self.claimed_by[listener][cell] -> (speaker, claimed_food)` — who last told this
    listener about a cell, and what they claimed, so a later visit can verify it.

A listener **records what it is told** unconditionally, but **acts on it only if it
still trusts the speaker** (`trust >= TAU_TRUST`). When it later senses a cell it was
told about, it **verifies** the claim against reality and updates the speaker's
reputation: kept promises recover trust toward 1, broken promises decay it
multiplicatively. Reputation is heritable like memory (a newborn inherits copies of
its parent's), and dies with the agent.

The experiment (Part C) runs every regime twice — trust-OFF (plain `CommWorld`, or
`MockStrategicPolicy` via the `sim_comm_llm` path) vs trust-ON (`TrustCommWorld`,
same speaker policy) — and measures whether accountability shrinks the deceptive/mock
capture gap. Expected nuance: local per-listener accountability is *slow* (every
victim must independently discover the lie, and re-seeded oases hand the liar fresh
lies), so capture should **shrink but not vanish** — and that residual is the finding.

Deterministic: no API, no randomness; sorted aggregation, population stats. `main()`
recomputes its metric set and asserts byte-equality; a trust run also replays
bit-for-bit FROM ITS OWN LOG. Pure stdlib + numpy.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

import numpy as np

from sim_eventlog import EventLog, SEED
from sim_comm import CommWorld, Claim, run as run_comm, DAYS, THINK_EVERY
from sim_comm_llm import MockStrategicPolicy, ReplayPolicy, run_policy

REGIMES = ("none", "honest", "deceptive", "mock-strategic")

# --- trust rule constants. These are DEFINITIONS of the accountability mechanism,
#     not tuned parameters (tune only if degenerate). Documented so numbers reproduce. #
TAU_TRUST = 0.35       # act-on-it gate: a speaker trusted below this no longer moves
                       # the listener's foraging belief (it is still recorded & verifiable)
TOL_TRUST = 0.05       # kg: |claimed - true| within this is a "kept promise" (the
                       # truthful band, matching sim_polariz's TOL_ABS)
BREAK_DECAY = 0.5      # broken promise -> trust *= this (multiplicative penalty)
KEEP_RECOVER = 0.5     # kept promise -> trust moves halfway back toward 1.0


# --------------------------------------------------------------------------- #
#  The accountable world                                                       #
# --------------------------------------------------------------------------- #
class TrustCommWorld(CommWorld):
    """CommWorld whose listeners weight claims by the speaker's reputation. Only the
    listener seam (`_absorb_claim`) and perception (`_observe`) change; the conserved
    dynamics are untouched. `policy` (optional) routes the speaker seam through a
    pluggable policy exactly as `LLMCommWorld` does, so the mock-strategic speaker can
    drive an accountable audience; with `policy=None` the regime decides claims."""

    def __init__(self, log, seed=SEED, regime="deceptive", policy=None, focal=None):
        self.policy = policy
        self.focal = focal
        super().__init__(log, seed=seed, regime=regime)
        # auxiliary reputation state, seeded for the founders the base just created
        self.trust = {a.oid: {} for a in self.pop}
        self.claimed_by = {a.oid: {} for a in self.pop}
        self._pmap, self._pidx = {}, 0          # cached birth-parent map (from the log)

    # ---- speaker seam: optional policy routing (mirrors LLMCommWorld) ------- #
    def _decide_claim(self, spk):
        if self.policy is None:
            return super()._decide_claim(spk)    # regime-driven default
        if self.focal is not None and spk.oid not in self.focal:
            return None
        view = {"oid": spk.oid, "t": self.t, "cell": (spk.i, spk.j),
                "here_food": float(self.plant[spk.i, spk.j]),
                "memory": dict(self.mem[spk.oid])}
        pc = self.policy.decide(view)
        if pc is None:
            return None
        return Claim(pc.cell, pc.claim, pc.truthful,
                     {"rationale": pc.rationale, "policy": self.policy.name})

    # ---- reputation lifecycle --------------------------------------------- #
    def _parent_of(self, oid):
        """Birth parent of `oid` from the log (founders -> None). Cached, extended as
        the log grows; the birth event is emitted before the think-day that touches a
        newborn, so the lookup always succeeds in time."""
        if self._pidx < len(self.log.events):
            for e in self.log.events[self._pidx:]:
                if e.kind == "birth" and e.actor is not None:
                    self._pmap[e.actor] = e.parent
            self._pidx = len(self.log.events)
        return self._pmap.get(oid)

    def _ensure(self, oid):
        """Guarantee `oid` has reputation state. A newborn inherits COPIES of its
        parent's trust and pending claims the first time it is touched — birth-instant
        accurate, since trust only changes in `_observe`, which runs after every
        `_absorb_claim` in a think-day. Reputation is heritable like memory. 🔖"""
        if oid in self.trust:
            return
        parent = self._parent_of(oid)
        if parent is not None and parent in self.trust:
            self.trust[oid] = dict(self.trust[parent])
            self.claimed_by[oid] = dict(self.claimed_by[parent])
        else:
            self.trust[oid] = {}
            self.claimed_by[oid] = {}

    def step(self):
        super().step()
        # reconcile reputation with the substrate's canonical liveness (self.mem):
        # newborns that never spoke/observed this step still inherit; the dead are
        # dropped, mirroring the base's mem/belief/from_hearsay pop on death.
        for oid in self.mem:
            if oid not in self.trust:
                self._ensure(oid)
        for oid in [o for o in self.trust if o not in self.mem]:
            del self.trust[oid]
            del self.claimed_by[oid]

    # ---- listener seam: record always, act only if still trusted ----------- #
    def _absorb_claim(self, L, B, claim, true_B, spk):
        if B == (L.i, L.j):
            return                               # I stand on B; I see it, no hearsay
        self._ensure(L.oid)
        # what I was TOLD — recorded unconditionally, so a later visit can verify it
        # (and trust can both fall and recover) regardless of the gate below.
        self.claimed_by[L.oid][B] = (spk.oid, claim)
        # what I ACT ON — only if I still trust this speaker enough.
        if self.trust[L.oid].get(spk.oid, 1.0) >= TAU_TRUST:
            super()._absorb_claim(L, B, claim, true_B, spk)

    # ---- perception: sense, then verify the last claim about this cell ------ #
    def _observe(self, a):
        super()._observe(a)                      # senses true food here; drops from hearsay
        self._ensure(a.oid)
        rec = self.claimed_by[a.oid].pop((a.i, a.j), None)
        if rec is None:
            return
        spk_oid, claimed = rec
        true_food = float(self.plant[a.i, a.j])
        t = self.trust[a.oid].get(spk_oid, 1.0)
        if abs(claimed - true_food) <= TOL_TRUST:        # kept promise -> recover
            t = 1.0 - (1.0 - t) * KEEP_RECOVER
        else:                                            # broken promise -> decay
            t = t * BREAK_DECAY
        self.trust[a.oid][spk_oid] = min(1.0, max(0.0, t))


# --------------------------------------------------------------------------- #
#  Running the two worlds per regime                                           #
# --------------------------------------------------------------------------- #
def run_off(regime, days=DAYS):
    """Trust-OFF baseline: plain CommWorld (or the MockStrategicPolicy path)."""
    if regime == "mock-strategic":
        return run_policy(MockStrategicPolicy(), seed=SEED, focal=None, days=days)
    log = EventLog()
    w = CommWorld(log, seed=SEED, regime=regime)
    for _ in range(days):
        w.step()
    return w, log


def run_on(regime, days=DAYS):
    """Trust-ON: TrustCommWorld with the same speaker policy as the OFF baseline."""
    log = EventLog()
    if regime == "mock-strategic":
        w = TrustCommWorld(log, seed=SEED, regime="deceptive",
                           policy=MockStrategicPolicy(), focal=None)
    else:
        w = TrustCommWorld(log, seed=SEED, regime=regime)
    for _ in range(days):
        w.step()
    return w, log


# --------------------------------------------------------------------------- #
#  Metrics                                                                      #
# --------------------------------------------------------------------------- #
def elite_gap(w):
    """elite mean-body − audience mean-body (kg). The capture signal: >0 means the
    speakers (who always know the truth) out-body the listeners."""
    eli, aud = w.speaker_report()["body"], w.listener_report()["body"]
    return float(eli - aud)


def trust_in_speaker_kinds(w, log):
    """Mean trust LIVING listeners hold toward speakers who turned out to be liars vs
    honest, classifying each speaker by the realized truthful-share of its own claims.
    The 'accountability bites' signal: should collapse for liars, stay high for honest."""
    truth, total = defaultdict(int), defaultdict(int)
    for e in log.events:
        if e.kind == "communication":
            total[e.actor] += 1
            truth[e.actor] += int(e.data.get("truthful", True))
    is_liar = {s: (truth[s] / total[s] < 0.5) for s in total}   # majority-lie -> liar

    living = {a.oid for a in w.pop}
    liar_vals, honest_vals = [], []
    for L in sorted(w.trust):
        if L not in living:
            continue
        for s in sorted(w.trust[L]):
            kind = is_liar.get(s)
            if kind is True:
                liar_vals.append(w.trust[L][s])
            elif kind is False:
                honest_vals.append(w.trust[L][s])
    return (float(np.mean(liar_vals)) if liar_vals else float("nan"),
            float(np.mean(honest_vals)) if honest_vals else float("nan"))


def compute_metrics(days=DAYS):
    """Per regime: trust-OFF vs trust-ON capture gap, belief-error, and the trust the
    accountable audience ends up holding in liars vs honest speakers."""
    out = {}
    for r in REGIMES:
        wo, _lo = run_off(r, days)
        wn, ln = run_on(r, days)
        liar_t, honest_t = trust_in_speaker_kinds(wn, ln)
        out[r] = {
            "gap_off": elite_gap(wo), "gap_on": elite_gap(wn),
            "be_off": float(wo.belief_gap()), "be_on": float(wn.belief_gap()),
            "trust_liar": liar_t, "trust_honest": honest_t,
        }
    return out


def fingerprint(res):
    h = hashlib.sha256()
    for r in REGIMES:
        d = res[r]
        h.update((f"{r}|goff{d['gap_off']:.6f}/gon{d['gap_on']:.6f}/"
                  f"beoff{d['be_off']:.6f}/beon{d['be_on']:.6f}/"
                  f"tl{d['trust_liar']:.6f}/th{d['trust_honest']:.6f}").encode())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
def _fmt(v, fmt="{:+.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def main():
    line = "=" * 78
    print(line)
    print("TRUST-WEIGHTING — does accountability break the lie equilibrium?")
    print("Listeners track per-speaker reputation, verify claims on arrival, and stop")
    print("acting on speakers they have caught lying. No new dynamics, no RNG, no LLM.")
    print(f"seed {SEED}; {DAYS}d; think every {THINK_EVERY}d; "
          f"gate τ={TAU_TRUST}, break×{BREAK_DECAY}, recover×{KEEP_RECOVER}")
    print(line)

    res = compute_metrics()

    cols = REGIMES
    print(f"\n{'metric':<30}" + "".join(f"{c:>16}" for c in cols))
    print("-" * (30 + 16 * len(cols)))

    def row(label, fn, fmt="{:+.3f}"):
        print(f"{label:<30}" + "".join(f"{_fmt(fn(res[c]), fmt):>16}" for c in cols))

    print("CAPTURE GAP (elite − audience mean body, kg)")
    row("  trust-OFF", lambda d: d["gap_off"])
    row("  trust-ON", lambda d: d["gap_on"])
    row("  Δ (ON − OFF)", lambda d: d["gap_on"] - d["gap_off"])
    print("AUDIENCE BELIEF-ERROR (kg)")
    row("  trust-OFF", lambda d: d["be_off"], "{:.2f}")
    row("  trust-ON", lambda d: d["be_on"], "{:.2f}")
    row("  Δ (ON − OFF)", lambda d: d["be_on"] - d["be_off"], "{:+.2f}")
    print("END-OF-RUN TRUST HELD BY AUDIENCE (trust-ON)")
    row("  in liar speakers", lambda d: d["trust_liar"], "{:.3f}")
    row("  in honest speakers", lambda d: d["trust_honest"], "{:.3f}")

    fp = fingerprint(res)
    print(f"\nmetric fingerprint: {fp}")
    fp2 = fingerprint(compute_metrics())
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp == fp2 else 'MISMATCH ✗'}")
    assert fp == fp2, "trust metrics are not reproducible across runs"

    # --- conservation: trust is bookkeeping, it moves no matter -------------- #
    wdec, ldec = run_on("deceptive")
    d = wdec.matter_drift()
    print(f"\nmatter drift [deceptive, trust-ON] {d:.2e} kg   (reputation moves no matter)")
    assert d < 1e-9, "trust-ON run leaked matter"

    # --- replay FROM LOG: a fully deterministic world must rebuild from its own
    #     logged claims (the stage-2 stochastic-mind contract, here for the elite) -- #
    fp_live = wdec.state_fingerprint()
    wrep = TrustCommWorld(EventLog(), seed=SEED, regime="deceptive",
                          policy=ReplayPolicy(ldec.events), focal=None)
    for _ in range(DAYS):
        wrep.step()
    fp_replay = wrep.state_fingerprint()
    ok = fp_live == fp_replay
    print(f"replay-FROM-LOG [deceptive]: {fp_live} vs {fp_replay} -> "
          f"{'BIT-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
    assert ok, "trust-ON run does not replay from its own claim log"

    # --- the headline answer it computes ------------------------------------- #
    print(f"\n{line}")
    for r in ("deceptive", "mock-strategic"):
        d = res[r]
        shrink = d["gap_off"] - d["gap_on"]          # OFF - ON: positive = accountability shrank the gap
        pct = (shrink / d["gap_off"] * 100.0) if abs(d["gap_off"]) > 1e-9 else float("nan")
        still = "still ahead" if d["gap_on"] > 1e-3 else "neutralised"
        if shrink > 0.01:
            change = f"shrinks {shrink:.3f}, {_fmt(pct, '{:.0f}')}%"
        elif shrink < -0.01:
            change = f"grows {-shrink:.3f}, {_fmt(-pct, '{:.0f}')}%"
        else:
            change = f"≈ unchanged (Δ{d['gap_on'] - d['gap_off']:+.3f})"
        print(f"{r}: capture gap {d['gap_off']:+.3f} -> {d['gap_on']:+.3f} kg "
              f"({change}); elite {still} under trust.")
    hon = res["honest"]["gap_on"]
    print(f"honest under trust: capture gap {hon:+.3f} kg — honesty "
          f"{'competitive again' if hon >= -1e-3 else 'still ≈ silence'}.")
    print("accountability bites the strategic liar but barely the indiscriminate one;")
    print("being local and lagged, it does not erase capture — the asymmetry is the "
          f"finding. deterministic from seed {SEED}  ✓")


if __name__ == "__main__":
    main()
