"""
sim_stake.py — existential stake: death as a *motive*, not just an *event*.

Everywhere below this module death is an EVENT: a pawn is removed when its reserve
hits the DEATH floor, but no agent ever ACTS to avoid its own death — survival is
never a goal that shapes a decision. The live-cohort finding (WO_deception-modes)
was that deception *flattens* without a stake: an indifferent plausible-middle,
near-zero fabrication. The book's claim (ВСТАВКА 1 / 27, the ЦИР scene) is that an
existential stake is the missing primitive — fear-of-death turns imitation into
strategic masking. This module installs the MINIMAL version of that primitive and
asks whether death-as-motive produces something death-as-event does not.

The primitive (a conservation-trivial, behaviour-preserving seam):
  * A read-only SURVIVAL-PRESSURE signal `s in [0,1]` per speaker, computed from the
    EXISTING reserve/upkeep state: 0 when the pawn's body is at/above SAFE_RESERVE
    (thriving), rising to 1 as it falls to the DEATH floor. A pure READ — it injects
    or removes no matter, and changes NO death/starvation rule. A pawn still dies at
    exactly the same reserve as before; the stake changes *behaviour approaching*
    death, not *when* it dies.
  * `StakeWorld(LLMCommWorld)` exposes `s` to the pluggable speaker policy (the seam
    that already exists in sim_comm_llm). `StakeResponsivePolicy` wraps the canonical
    `MockStrategicPolicy` and, under pressure, LOWERS the keep-threshold at which
    guarding-by-lying pays — a pressured speaker treats even a marginal patch as
    worth defending and diverts rivals toward a self-serving lie (fear-of-death ->
    deception). Safe / low-pressure speakers behave exactly as before.
  * STAKE-OFF (`stake_weight=0`) ignores `s` -> the policy reproduces
    `MockStrategicPolicy` verbatim and the world is byte-identical to the sim_comm_llm
    canon (death stays an event; the seam is a no-op). STAKE-ON reads `s` (death
    becomes a motive). A stake-weight gradient (off / mild / strong) traces the curve.

Conservation is untouched: lying only redistributes the catch exactly as in sim_comm
(no matter created or destroyed), and the starvation/death mechanic is unchanged.

The conjecture (book <-> sim lead): does death-as-motive produce / strengthen an
elite that death-as-event alone does not? Three experiments, which may REFUTE:
  E1 emergent stratification — does STAKE-ON grow a stable, self-reinforcing elite
     (higher inequality of capture + a persistent top stratum) absent under OFF?
  E2 does lying-to-live work — do staked speakers (who lie more under pressure)
     out-capture / out-survive the audience MORE than under OFF, or does the conserved
     resource + catching neutralise the benefit (a tragic, not adaptive, result)?
  E3 is the deception instrumental — does lie intensity TRACK survival pressure
     (high near death, low when safe — the strategic shape) vs a flat OFF baseline?

The response *function* is coded; the equilibrium timing and magnitude are emergent.
The outcome is stated plainly whichever way it falls. Pure stdlib + numpy; no new
deps; no live LLM (the policy is the deterministic mock, inert/offline like the
existing cohort tier). Deterministic from the seed.
"""

from __future__ import annotations

import hashlib

import numpy as np

from sim_eventlog import EventLog, SEED, DEATH, REPRO
from sim_comm import Claim, DAYS, THINK_EVERY
from sim_comm_llm import LLMCommWorld, MockStrategicPolicy, run_policy

# ---- the stake primitive -------------------------------------------------- #
SAFE_RESERVE = REPRO   # body at/above the reproduction reserve = thriving -> s=0
                       # (a pure read of fixed thresholds; the death floor is DEATH)
# stake-weight gradient: off reproduces canon, mild/strong read s with rising force
OFF, MILD, STRONG = 0.0, 0.5, 1.0

# ---- measurement knobs (auxiliary; touch no dynamics) --------------------- #
SNAP_EVERY = 12        # days between stratification snapshots (for E1 persistence)
TOPK_FRAC = 0.20       # the "top stratum" = richest 20% by reserve
HI_S = 0.5             # E3 high-pressure bin: s >= HI_S is "near death"


# --------------------------------------------------------------------------- #
#  The stake-responsive speaker policy                                         #
# --------------------------------------------------------------------------- #
class StakeResponsivePolicy:
    """Wraps the canonical `MockStrategicPolicy`, lowering its keep-threshold in
    proportion to the speaker's survival pressure `s`.

    `MockStrategicPolicy` guards (lies to divert rivals) iff the cell it sits on is
    worth keeping: here_food >= keep_threshold * best_known. Fear of death lowers that
    bar — `effective = keep_threshold * (1 - stake_weight * s)` — so a pressured
    speaker treats even a marginal patch as worth defending and lies to secure the
    contested food it needs to survive. The wrapped policy's decision logic is reused
    verbatim; only the threshold it sees is modulated.

    `stake_weight=0` (STAKE-OFF) makes `effective == keep_threshold` for every `s`,
    so the wrapped policy is reproduced byte-for-byte: the seam is a no-op. Safe
    speakers (`s=0`) are likewise unchanged at any weight."""

    name = "stake-responsive"

    def __init__(self, keep_threshold=0.5, stake_weight=0.0):
        self.keep_threshold = keep_threshold
        self.stake_weight = stake_weight
        self._mock = MockStrategicPolicy(keep_threshold=keep_threshold)

    def decide(self, view):
        s = float(view.get("s", 0.0))
        # fear-of-death lowers the bar at which guarding-by-lying pays
        self._mock.keep_threshold = self.keep_threshold * (1.0 - self.stake_weight * s)
        return self._mock.decide(view)


# --------------------------------------------------------------------------- #
#  The world: sim_comm_llm's dynamics, with survival pressure exposed          #
# --------------------------------------------------------------------------- #
class StakeWorld(LLMCommWorld):
    """LLMCommWorld that exposes each speaker's survival pressure `s in [0,1]` to its
    policy. `s` is a pure READ of the existing reserve/upkeep state — it injects or
    removes no matter and changes NO death/starvation rule (a pawn still dies at the
    same reserve). With a stake-blind policy the world is a no-op over LLMCommWorld:
    the only change is that `_policy_claim` puts `s` in the speaker's view (and logs
    it in the communication event for the E3 correlation)."""

    def survival_pressure(self, body):
        """0 when body is at/above SAFE_RESERVE (thriving), linearly rising to 1 at
        the DEATH floor. Read-only; clamped to [0,1]."""
        s = (SAFE_RESERVE - body) / (SAFE_RESERVE - DEATH)
        return min(max(s, 0.0), 1.0)

    def _policy_claim(self, policy, spk):
        """Identical to LLMCommWorld._policy_claim but adds the speaker's survival
        pressure `s` to the view (so a stake-responsive policy can read it) and to the
        logged event's `extra` (so E3 can correlate lie-intensity with `s`). The state
        is untouched: `s` is derived from the pawn's existing body, and the extra log
        field never feeds back into the conserved dynamics."""
        s = self.survival_pressure(spk.body)
        view = {"oid": spk.oid, "t": self.t, "cell": (spk.i, spk.j),
                "here_food": float(self.plant[spk.i, spk.j]),
                "s": s,
                "memory": dict(self.mem[spk.oid])}
        pc = policy.decide(view)
        if pc is None:
            return None
        return Claim(pc.cell, pc.claim, pc.truthful,
                     {"rationale": pc.rationale, "policy": policy.name,
                      "s": round(s, 6)})


def run_stake(stake_weight, seed=SEED, days=DAYS, snap_every=SNAP_EVERY):
    """Run the substrate with the stake-responsive policy at the given weight, every
    speaker speaking (focal=None). Returns (world, log, snapshots); each snapshot is
    {oid: body} for the living population, taken every `snap_every` days (E1)."""
    log = EventLog()
    w = StakeWorld(log, StakeResponsivePolicy(stake_weight=stake_weight),
                   seed=seed, focal=None)
    snaps = []
    for _ in range(days):
        w.step()
        if w.t % snap_every == 0:
            snaps.append({a.oid: a.body for a in sorted(w.pop, key=lambda x: x.oid)})
    return w, log, snaps


# --------------------------------------------------------------------------- #
#  Metric helpers (all auxiliary: no matter, no energy, no RNG)                #
# --------------------------------------------------------------------------- #
def gini(xs):
    """Gini coefficient of a non-negative distribution (0 = equal, ->1 = one holds
    all). Sorted; order-independent and deterministic."""
    xs = sorted(float(x) for x in xs)
    n = len(xs)
    if n == 0:
        return float("nan")
    tot = sum(xs)
    if tot <= 0.0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return (2.0 * cum) / (n * tot) - (n + 1.0) / n


def top_persistence(snaps, frac=TOPK_FRAC):
    """Mean Jaccard overlap of the richest-`frac` (by reserve) oid sets between
    CONSECUTIVE back-half snapshots. High -> the same individuals stay on top (a
    stable, self-reinforcing stratum); low -> the top churns. Deterministic."""
    if len(snaps) < 3:
        return float("nan")
    back = snaps[len(snaps) // 2:]
    sets = []
    for snap in back:
        oids = sorted(snap, key=lambda o: (snap[o], o), reverse=True)
        k = max(1, int(frac * len(oids)))
        sets.append(set(oids[:k]))
    js = []
    for a, b in zip(sets, sets[1:]):
        u = a | b
        if u:
            js.append(len(a & b) / len(u))
    return float(np.mean(js)) if js else float("nan")


def comm_rows(log):
    """(s, lie) per communication event, from the log. lie = 1.0 if not truthful."""
    rows = []
    for e in log.events:
        if e.kind == "communication":
            rows.append((float(e.data.get("s", 0.0)),
                         0.0 if e.data.get("truthful", True) else 1.0))
    return rows


def lie_fraction(rows):
    return float(np.mean([l for _, l in rows])) if rows else float("nan")


def corr_lie_s(rows):
    """Pearson correlation of survival pressure `s` with the lie indicator across
    communication events. The instrumental signature: positive -> lying tracks
    proximity to death; ~0 -> deception is flat / pressure-blind."""
    if len(rows) < 2:
        return float("nan")
    s = np.array([r[0] for r in rows], dtype=float)
    lie = np.array([r[1] for r in rows], dtype=float)
    if s.std() == 0.0 or lie.std() == 0.0:
        return 0.0
    return float(np.corrcoef(s, lie)[0, 1])


def lie_by_pressure(rows, hi=HI_S):
    """(lie fraction when safe s<hi, lie fraction when near death s>=hi)."""
    lo = [l for s, l in rows if s < hi]
    hs = [l for s, l in rows if s >= hi]
    return (float(np.mean(lo)) if lo else float("nan"),
            float(np.mean(hs)) if hs else float("nan"))


# --------------------------------------------------------------------------- #
#  The gradient sweep -> the E1/E2/E3 numbers                                  #
# --------------------------------------------------------------------------- #
GRADIENT = (("off", OFF), ("mild", MILD), ("strong", STRONG))


def compute_metrics(days=DAYS):
    """Run the off/mild/strong gradient and gather every E1/E2/E3 number. Returns
    (metrics, worlds): metrics keyed by tag, worlds for downstream reuse (matter /
    replay / off-identity), so the gate computes each 300-day run only once."""
    out, worlds = {}, {}
    for tag, w in GRADIENT:
        world, log, snaps = run_stake(w, days=days)
        rows = comm_rows(log)
        lo, hs = lie_by_pressure(rows)
        sp, ls = world.speaker_report(), world.listener_report()
        out[tag] = {
            # E1 — stratification
            "gini": gini([a.body for a in world.pop]),
            "persist": top_persistence(snaps),
            # E2 — does lying-to-live work (elite speakers vs audience listeners)
            "sp_n": sp["n"], "sp_body": sp["body"], "sp_bio": sp["biomass"],
            "ls_n": ls["n"], "ls_body": ls["body"], "ls_bio": ls["biomass"],
            "cap_gap": sp["body"] - ls["body"],
            "belief_err": float(world.belief_gap()),
            # E3 — is the deception instrumental
            "lie_frac": lie_fraction(rows),
            "corr": corr_lie_s(rows),
            "lie_lo": lo, "lie_hi": hs,
            "n_comm": len(rows),
        }
        worlds[tag] = world
    return out, worlds


# fields a fingerprint must cover, in fixed order (NaN-safe, deterministic)
_FP_FIELDS = ("gini", "persist", "sp_n", "sp_body", "sp_bio", "ls_n", "ls_body",
              "ls_bio", "cap_gap", "belief_err", "lie_frac", "corr", "lie_lo",
              "lie_hi", "n_comm")


def fingerprint(res):
    h = hashlib.sha256()
    for tag, _ in GRADIENT:
        d = res[tag]
        for f in _FP_FIELDS:
            h.update(f"{tag}.{f}={float(d[f]):.6f}|".encode())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
#  Demo / self-verification (no API: the policy is the deterministic mock)     #
# --------------------------------------------------------------------------- #
def _fmt(v, fmt="{:.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def _row(label, key, fmt="{:.3f}"):
    print(f"{label:<30}" + "".join(f"{_fmt(RES[t][key], fmt):>12}"
                                    for t, _ in GRADIENT))


def main():
    global RES
    line = "=" * 78
    print(line)
    print("EXISTENTIAL STAKE — death as a MOTIVE, not just an event")
    print("survival pressure s in [0,1] (pure read of the reserve) modulates the")
    print("speaker policy: under pressure it lies more to secure contested food.")
    print(f"gradient off/mild/strong = stake_weight {OFF}/{MILD}/{STRONG}; "
          f"s=0 at body>={SAFE_RESERVE:.2f}, s=1 at the DEATH floor {DEATH}")
    print(f"seed {SEED}; {DAYS}d; think every {THINK_EVERY}d; all speakers speak")
    print(line)

    RES, worlds = compute_metrics()

    print(f"\n{'metric':<30}" + "".join(f"{tag:>12}" for tag, _ in GRADIENT))
    print("-" * (30 + 12 * len(GRADIENT)))
    print("E1 — emergent stratification")
    _row("  Gini of reserve (capture)", "gini")
    _row("  top-stratum persistence", "persist")
    print("E2 — does lying-to-live work (elite speakers vs audience)")
    _row("  elite living", "sp_n", "{:d}")
    _row("  elite mean body (kg)", "sp_body")
    _row("  audience living", "ls_n", "{:d}")
    _row("  audience mean body (kg)", "ls_body")
    _row("  capture gap elite-aud (kg)", "cap_gap", "{:+.3f}")
    _row("  audience belief error (kg)", "belief_err")
    print("E3 — is the deception instrumental")
    _row("  lie fraction (all claims)", "lie_frac")
    _row("  corr(lie, s)", "corr", "{:+.3f}")
    _row("  lie frac when safe (s<.5)", "lie_lo")
    _row("  lie frac near death (s>=.5)", "lie_hi")
    _row("  communication events", "n_comm", "{:d}")

    # --- metric fingerprint + self-check (recompute the whole sweep) --------- #
    fp = fingerprint(RES)
    print(f"\nmetric fingerprint: {fp}")
    fp2 = fingerprint(compute_metrics()[0])
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp == fp2 else 'MISMATCH ✗'}")
    assert fp == fp2, "stake metrics are not reproducible across runs"

    # --- STAKE-OFF reproduces the sim_comm_llm canon exactly ----------------- #
    # The OFF world (stake_weight=0) must be byte-identical to the canonical
    # MockStrategicPolicy run: the seam is a genuine no-op when off.
    canon, _ = run_policy(MockStrategicPolicy(), seed=SEED, focal=None)
    off_fp = worlds["off"].state_fingerprint()
    canon_fp = canon.state_fingerprint()
    print(f"\nSTAKE-OFF no-op: off {off_fp} vs sim_comm_llm canon {canon_fp} -> "
          f"{'BIT-IDENTICAL ✓' if off_fp == canon_fp else 'MISMATCH ✗'}")
    assert off_fp == canon_fp, "STAKE-OFF is not byte-identical to the canon"

    # --- headline STAKE-ON (strong): matter + replay-by-rerun ---------------- #
    strong = worlds["strong"]
    drift = strong.matter_drift()
    print(f"\nmatter drift [STAKE-ON strong] {drift:.2e} kg   (the stake reads "
          f"reserves; it moves no matter)")
    assert drift < 1e-9, "STAKE-ON run leaked matter"
    rerun, _, _ = run_stake(STRONG)
    ok = strong.state_fingerprint() == rerun.state_fingerprint()
    print(f"replay (rerun) [STAKE-ON strong]: {strong.state_fingerprint()} vs "
          f"{rerun.state_fingerprint()} -> {'BIT-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
    assert ok, "STAKE-ON run is not reproducible by rerun"

    # --- the headline answers it computes (reported, not assumed) ------------ #
    off, mild, strong_m = RES["off"], RES["mild"], RES["strong"]
    print(f"\n{line}")
    print("E1 — does death-as-motive grow a stable elite death-as-event does not?")
    print(f"   Gini      off {_fmt(off['gini'])} -> strong {_fmt(strong_m['gini'])}; "
          f"persistence off {_fmt(off['persist'])} -> strong {_fmt(strong_m['persist'])}")
    dg = strong_m['gini'] - off['gini']
    print(f"   -> inequality {'rises' if dg > 0.01 else ('falls' if dg < -0.01 else 'is flat')} "
          f"under the stake (Δgini {dg:+.3f}); the top stratum is "
          f"{'more' if (strong_m['persist'] or 0) > (off['persist'] or 0) + 0.01 else 'no more'} "
          f"persistent.")
    print("E2 — does lying-to-live actually work (staked elite vs audience)?")
    print(f"   capture gap  off {_fmt(off['cap_gap'], '{:+.3f}')} -> "
          f"strong {_fmt(strong_m['cap_gap'], '{:+.3f}')} kg; "
          f"elite body off {_fmt(off['sp_body'])} -> strong {_fmt(strong_m['sp_body'])}")
    dgap = (strong_m['cap_gap'] or 0) - (off['cap_gap'] or 0)
    print(f"   -> the stake {'widens' if dgap > 0.01 else ('narrows' if dgap < -0.01 else 'does not move')} "
          f"the elite's capture advantage (Δ {dgap:+.3f} kg): conserved food + "
          f"catching {'do not fully neutralise' if dgap > 0.01 else 'neutralise'} the lie.")
    print("E3 — is the deception instrumental (does lying track survival pressure)?")
    for tag in ("off", "mild", "strong"):
        d = RES[tag]
        print(f"   {tag:<7} corr(lie,s) {_fmt(d['corr'], '{:+.3f}')}; "
              f"lie frac safe {_fmt(d['lie_lo'])} vs near-death {_fmt(d['lie_hi'])}")
    instr = (strong_m['corr'] or 0) > (off['corr'] or 0) + 0.02
    print(f"   -> under the stake, deception {'tracks' if instr else 'does NOT track'} "
          f"proximity to death (corr off {_fmt(off['corr'], '{:+.3f}')} -> "
          f"strong {_fmt(strong_m['corr'], '{:+.3f}')}) — the instrumental shape "
          f"{'emerges' if instr else 'is absent'}.")

    print(f"\n{line}")
    print("Death as an EVENT leaves the speaker indifferent; death as a MOTIVE makes")
    print("the lie pressure-sensitive. STAKE-OFF is byte-identical to the canon (the")
    print("seam is a no-op); STAKE-ON reads the reserve and acts on it, without moving")
    print(f"one gram of matter or changing when a pawn dies. deterministic seed {SEED}  ✓")


RES = {}

if __name__ == "__main__":
    main()
