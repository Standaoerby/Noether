"""
sim_sphere.py — the observer: local materialization, an attention budget, and
information lag (module 20, the first vertebra of the embodied world).

NO living minds beyond sim_comm's deterministic forager, NO LLM, NO network. This is
the honest substrate the game will later sit on — the nail, not the bow. It encodes
the three deliberately-divergent ontological levels we fixed:

  1. What IS — the objective event-log / god view. Conservation, determinism and
     replay live in the tower below and are inherited UNBROKEN.
  2. What is MATERIALIZED — the union of agents' presence neighbourhoods (geometry).
     Physics (the existing conserved food/heat update) runs ONLY on the materialized
     set; a dormant region is FROZEN as a conserved invariant. A dormant region is by
     definition in flux-balance across its boundary (in sim_comm, matter crosses a
     cell boundary only when an agent carries its body across — and dormant cells hold
     no agents), so freezing it is physics, not a cheat: it leaks zero matter. The
     whole grid is never required to update at once.
  3. What an agent KNOWS — an attention budget of at most K observed elements, ranked
     by endogenous significance, reaching the agent after an information lag.

Matter exists materially whether observed or not (level 2). The budget (level 3) is a
property of belief, never of matter: falling out of the budget is FORGETTING, not
annihilation.

Design — each layer independently degenerates to a no-op at its OFF value, so the OFF
configuration is byte-identical to sim_comm's CommWorld:
  * Materialization: presence = a disc of `radius` around each agent (continuous
    coords; measured on the integer grid). `radius >= grid diagonal` -> every cell
    materialized -> `step()` delegates verbatim to `CommWorld.step`. With a finite
    radius, the dormant cells are snapshotted before the (reused) base step and
    restored after — freezing them. Because a dormant cell changes only via the base
    step's per-cell soil<->plant swap (no cross-cell flow without an agent), its total
    matter is invariant, so the restore is exactly conservative.
  * Attention budget: `K = None` (infinite) -> no eviction -> belief untouched. A
    finite K evicts the lowest-significance cells from an agent's memory until |mem|==K
    and logs each as a `forget` (sleep/consolidation) candidate. The budget prunes what
    the agent KNOWS (hence forages on), never what exists.
  * Information lag: `lag = 0` -> heard claims enter belief immediately (the canon
    path). `lag = d > 0` -> a heard claim is buffered and committed to the listener's
    memory `d` think-cycles later, so belief lawfully trails truth by `d` with no
    deception involved. Lag is logged and measured.

Significance (used for eviction) is ENDOGENOUS (a fixed function of observed stimulus
features only), OUTCOME-NEUTRAL (it never knows who lies, who is elite, or who
benefits — it ranks stimuli; who wins a slot is a measured result), and DETERMINISTIC.

Pure stdlib + numpy; importing is side-effect-free; no network.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict

import numpy as np

from sim_eventlog import EventLog, SEED
from sim_comm import CommWorld, R, C, DAYS, THINK_EVERY, run as run_comm

# --- significance weights: fixed, endogenous, outcome-neutral, documented ----- #
# sig(cell) = W_MAG*food + W_PROX*proximity + W_REC*recency + W_THREAT*co-occupants
# All four terms are observable stimulus features; none encodes who lies/wins.
W_MAG, W_PROX, W_REC, W_THREAT = 1.0, 5.0, 2.0, 3.0

GRID_DIAG = math.hypot(R - 1, C - 1)        # radius >= this -> whole grid materialized
CANON_COMM = "a91480561b6de937"             # sim_comm deceptive state fingerprint (OFF target)


class SphereWorld(CommWorld):
    """CommWorld observed through a presence sphere, an attention budget, and an
    information lag. All three are additive and degenerate to no-ops at their OFF
    values (radius>=diagonal, K=None, lag=0), so OFF reproduces CommWorld byte-for-byte.

    Eviction tie-break (documented): cells are ranked by (significance, cell) ascending
    and the lowest are evicted; among equal significance the cell with the SMALLER
    (row, col) is evicted first. Deterministic and independent of dict order."""

    def __init__(self, log, seed=SEED, regime="deceptive",
                 radius=GRID_DIAG + 1.0, K=None, lag=0):
        self.radius = float(radius)
        self.K = K                          # None = infinite budget (OFF)
        self.lag = int(lag)                 # think-cycles of hearsay lag (0 = OFF)
        self._pending = []                  # buffered heard facts (commit_t,L,B,claim,trueB,spk,heard_t)
        self._evictions = []                # (t, oid, cell, sig) forgetting candidates
        self._lag_samples = []              # realized commit delays (ticks)
        self._active_frac = []              # materialized-cell fraction per step (diagnostic)
        super().__init__(log, seed=seed, regime=regime)

    # ---- level 2: presence geometry / materialization --------------------- #
    def _covers_all(self):
        return self.radius >= GRID_DIAG

    def _active_mask(self):
        """Boolean (R,C) mask: cells inside any agent's presence disc."""
        if self._covers_all():
            return np.ones((R, C), dtype=bool)
        ii, jj = np.mgrid[0:R, 0:C]
        active = np.zeros((R, C), dtype=bool)
        r2 = self.radius * self.radius
        for a in self.pop:
            active |= ((ii - a.i) ** 2 + (jj - a.j) ** 2) <= r2
        return active

    def step(self):
        # OFF / fully-materialized: run the base step verbatim (canon path).
        if self._covers_all():
            self._active_frac.append(1.0)
            return super().step()
        active = self._active_mask()
        self._active_frac.append(float(active.mean()))
        dormant = ~active
        if not dormant.any():
            return super().step()
        # freeze the dormant region: snapshot, run the (reused) conserved base step,
        # then restore. A dormant cell's matter changes only via an internal
        # soil<->plant swap during the base step, so its total is invariant and the
        # restore leaks exactly zero matter.
        soil_d = self.soil[dormant].copy()
        plant_d = self.plant[dormant].copy()
        super().step()
        self.soil[dormant] = soil_d
        self.plant[dormant] = plant_d

    # ---- level 3: information lag on hearsay ------------------------------ #
    def _absorb_claim(self, L, B, claim, true_B, spk):
        # zero-lag or a claim about one's own cell -> immediate (the canon path).
        if self.lag <= 0 or B == (L.i, L.j):
            return super()._absorb_claim(L, B, claim, true_B, spk)
        commit_t = self.t + self.lag * THINK_EVERY
        self._pending.append((commit_t, L.oid, B, claim, true_B, spk.oid, self.t))

    def _commit_pending(self):
        """Commit buffered hearsay whose lag has elapsed, into the listener's memory.
        Deterministic order: (commit_t, listener oid, cell). A fact whose listener has
        died is lost; a listener now standing on the cell senses it directly instead."""
        if not self._pending:
            return
        ready = [p for p in self._pending if p[0] <= self.t]
        if not ready:
            return
        self._pending = [p for p in self._pending if p[0] > self.t]
        byoid = {a.oid: a for a in self.pop}
        for commit_t, Loid, B, claim, true_B, spkoid, heard_t in sorted(
                ready, key=lambda p: (p[0], p[1], p[2])):
            if Loid not in self.mem:            # listener died -> fact lost
                continue
            L = byoid.get(Loid)
            if L is not None and B == (L.i, L.j):
                continue                        # now sensed directly, no stale hearsay
            self.mem[Loid][B] = (claim, self.t)
            if abs(claim - true_B) > 1e-9:
                self.from_hearsay[Loid].add(B)
            else:
                self.from_hearsay[Loid].discard(B)
            self._lag_samples.append(self.t - heard_t)

    # ---- level 3: attention budget / endogenous significance -------------- #
    def _sig(self, a, cell, rec, occ):
        """Endogenous, outcome-neutral significance of `cell` to agent `a`."""
        food, day = rec
        manh = abs(cell[0] - a.i) + abs(cell[1] - a.j)
        prox = 1.0 / (1.0 + manh)
        recency = (day + 1.0) / (self.t + 1.0)      # more recently seen -> higher
        threat = occ.get(cell, 0)                   # observable co-occupants
        return W_MAG * food + W_PROX * prox + W_REC * recency + W_THREAT * threat

    def _apply_budget(self, here):
        if self.K is None:
            return
        occ = defaultdict(int)
        for a in self.pop:
            occ[(a.i, a.j)] += 1
        for a in self.pop:                          # self.pop is ordered -> deterministic
            mem = self.mem[a.oid]
            if len(mem) <= self.K:
                continue
            ranked = sorted(mem.keys(),
                            key=lambda c: (self._sig(a, c, mem[c], occ), c))
            for c in ranked[:len(mem) - self.K]:    # evict lowest-significance
                sig = self._sig(a, c, mem[c], occ)
                del mem[c]
                self.from_hearsay[a.oid].discard(c)
                self._evictions.append((self.t, a.oid, c, round(sig, 6)))
                self.log.emit(self.t, "forget", "individual", where=(a.i, a.j),
                              actor=a.oid, data={"cell": list(c), "sig": round(sig, 6)})

    def _social_exchange(self, here):
        # runs after sensation, before cognition (the sim_comm seam). Commit matured
        # lagged hearsay, then enforce the attention budget. Both are no-ops at OFF
        # values, so this reduces to CommWorld's empty _social_exchange.
        self._commit_pending()
        self._apply_budget(here)


# --------------------------------------------------------------------------- #
#  Running + fingerprint                                                       #
# --------------------------------------------------------------------------- #
def run_sphere(regime="deceptive", radius=GRID_DIAG + 1.0, K=None, lag=0,
               seed=SEED, days=DAYS):
    log = EventLog()
    w = SphereWorld(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag)
    for _ in range(days):
        w.step()
    return w, log


def sphere_fingerprint(w):
    """Stable fingerprint over the conserved state AND the knowledge layer (budget
    contents, eviction order/ranking, lag samples) — the determinism self-check."""
    h = hashlib.sha256()
    h.update(w.state_fingerprint().encode())
    # final budget contents: per-living-agent memory size, sorted by oid
    sizes = sorted((oid, len(w.mem[oid])) for oid in w.mem)
    h.update(("|sizes" + ",".join(f"{o}:{n}" for o, n in sizes)).encode())
    # full eviction order + ranking
    h.update(f"|ev{len(w._evictions)}".encode())
    for (t, oid, c, sig) in w._evictions:
        h.update(f"{t},{oid},{c[0]},{c[1]},{sig}".encode())
    # lag
    h.update(f"|lag{len(w._lag_samples)},{sum(w._lag_samples)}".encode())
    return h.hexdigest()[:16]


def eviction_concentration(w):
    """How concentrated are evictions across cells? Returns (n_evict, n_cells,
    top5_share). Concentrated -> a few cells absorb most forgetting."""
    if not w._evictions:
        return 0, 0, float("nan")
    per = defaultdict(int)
    for (_t, _oid, c, _sig) in w._evictions:
        per[c] += 1
    counts = sorted(per.values(), reverse=True)
    return len(w._evictions), len(per), sum(counts[:5]) / sum(counts)


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
def main():
    line = "=" * 78
    print(line)
    print("SPHERE — the observer: local materialization, attention budget, info lag")
    print("Three levels: what IS (god log) · what is MATERIALIZED (presence union) ·")
    print("what an agent KNOWS (K observed elements, ranked by endogenous significance,")
    print("reaching it after a lag). Matter exists unobserved; the budget is belief.")
    print(f"grid {R}x{C}; seed {SEED}; {DAYS}d; think every {THINK_EVERY}d")
    print(line)

    # --- OFF == canon, byte-identical --------------------------------------- #
    w_off, _ = run_sphere(regime="deceptive")            # radius>=diag, K=inf, lag=0
    off_fp = w_off.state_fingerprint()
    canon_fp = run_comm("deceptive")[0].state_fingerprint()
    print(f"\nOFF (radius=inf, K=inf, lag=0) vs sim_comm canon:")
    print(f"  sphere {off_fp}  ·  canon {canon_fp}  ·  target {CANON_COMM}")
    ok_off = off_fp == CANON_COMM == canon_fp
    print(f"  -> {'BYTE-IDENTICAL ✓' if ok_off else 'MISMATCH ✗'} "
          f"(module 20 does not perturb the 1-19 tower)")
    assert ok_off, "OFF mode is not byte-identical to sim_comm canon"
    assert w_off.matter_drift() < 1e-9, "OFF run leaked matter"

    # --- a budgeted + lagged + materialized run ----------------------------- #
    # Headline ON: presence = the cell underfoot (radius 0, the minimal disc). On this
    # small grid the population saturates the 196 cells, so only this tight presence
    # leaves a substantive dormant region to freeze; the radius sweep below shows
    # materialization filling in as the disc grows.
    RAD, KK, LAG = 0.0, 8, 1
    w_on, log_on = run_sphere(regime="deceptive", radius=RAD, K=KK, lag=LAG)
    drift = w_on.matter_drift()
    af = np.array(w_on._active_frac)
    n_ev, n_cells, top5 = eviction_concentration(w_on)
    mean_lag = (sum(w_on._lag_samples) / len(w_on._lag_samples)) if w_on._lag_samples else 0.0
    print(f"\nON  (presence radius {RAD} = cell underfoot, budget K={KK}, lag {LAG} cycle):")
    print(f"  materialized fraction over steps        : min {af.min():.3f} · "
          f"mean {af.mean():.3f} · max {af.max():.3f}  (rest frozen dormant)")
    print(f"  matter drift over active set+boundaries : {drift:.2e} kg")
    print(f"  attention evictions (forgetting cands.) : {n_ev} over {n_cells} cells; "
          f"top-5 cells hold {top5:.3f} of them")
    print(f"  information lag: {len(w_on._lag_samples)} hearsay facts committed, "
          f"mean realized lag {mean_lag:.1f} ticks ({LAG} cycle = {LAG*THINK_EVERY} ticks)")
    print(f"  audience belief-error (trails truth)    : {w_on.belief_gap():.1f} kg")
    assert drift < 1e-9, "budgeted/lagged run leaked matter"
    print(f"\n  up to {(1-af.min())*100:.0f}% of the grid was dormant at the sparsest step, "
          f"yet whole-grid matter drift is {drift:.2e} kg -> the dormant region folded "
          f"with zero leak.")

    # --- materialization scales with presence radius (level 2) -------------- #
    print(f"\npresence-radius sweep (materialization fills in as the disc grows):")
    print(f"  {'radius':>8}{'mat.frac(mean)':>16}{'min':>8}{'drift(kg)':>14}")
    for rad in (0.0, 1.0, 2.5, GRID_DIAG + 1.0):
        wr, _ = run_sphere(regime="deceptive", radius=rad, K=KK, lag=LAG)
        a = np.array(wr._active_frac)
        tag = "inf" if rad >= GRID_DIAG else f"{rad:.1f}"
        print(f"  {tag:>8}{a.mean():>16.3f}{a.min():>8.3f}{wr.matter_drift():>14.2e}")

    # --- determinism: budget contents, eviction order, ranking, lag --------- #
    fp1 = sphere_fingerprint(w_on)
    w_on2, _ = run_sphere(regime="deceptive", radius=RAD, K=KK, lag=LAG)
    fp2 = sphere_fingerprint(w_on2)
    print(f"\nself-check fingerprint (state+budget+evictions+lag): {fp1}")
    print(f"recompute (rerun): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp1 == fp2 else 'MISMATCH ✗'}")
    assert fp1 == fp2, "budgeted/lagged run is not reproducible (budget/eviction/lag)"

    # --- attention as a scarce resource: does eviction concentrate? (K-sweep) #
    print(f"\nattention budget sweep (does eviction concentrate?):")
    print(f"  {'K':>4}{'evictions':>12}{'cells':>8}{'top5 share':>12}{'mat.frac':>10}")
    for K in (4, 8, 16):
        wk, _ = run_sphere(regime="deceptive", radius=RAD, K=K, lag=LAG)
        ne, nc, t5 = eviction_concentration(wk)
        print(f"  {K:>4}{ne:>12}{nc:>8}{t5:>12.3f}{np.mean(wk._active_frac):>10.3f}")

    print(f"\n{line}")
    print("OFF is the 1-19 tower untouched; ON materializes only where agents are,")
    print("forgets the least-significant beliefs under a finite budget, and lets belief")
    print("trail truth by a finite information lag — all matter-conserving, deterministic,")
    print(f"and replayable. The observer is a substrate, not a premise. seed {SEED}  ✓")


if __name__ == "__main__":
    main()
