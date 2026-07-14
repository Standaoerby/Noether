"""
frailty.py — mod J: senescence as exhaustion of redundancy (reliability theory).

The tower's Animal is six numbers (oid,i,j,gene,body,age) and stays canon. Frailty WRAPS
it (by oid) with a hidden side-table — the same discipline mod H used for `_house` and mod
G2 for `_extort_marks` — and never replaces a byte of the substrate.

    self._blocks[oid] : int      # intact redundancy blocks; the hidden reserve

The mechanism is reliability theory, NOT a fitted Gompertz curve. μ(t)=A+B·e^{ct} is a
tautology if coded directly; here the hazard must EMERGE (or fail to) from redundancy
running out:

  * seed    intact ~ Binomial(n0, 1 - x0)         (x0 = initial damage load; fresh per pawn)
  * tick    failed ~ Binomial(intact, k); intact -= failed
  * repair  p_rep = rho_rep · f(capital)          (the elite-theory seam; rho_rep=0 default)
  * death   intact == 0

KEY PROPERTY — the stake becomes uncomputable from the body: eating repairs `body` but
NEVER a block. Frailty is unredeemable, irreversible, and not readable off the substrate
(the ВСТАВКА-27 lesson; gate MJ-NOREAD). REPAIR therefore depends on CAPITAL (owned cells)
and NEVER on body — if repair ∝ body, frailty collapses back into a body-function and the
stake is legible again.

Children get a FRESH draw (damage is not inherited: damage_inherit=False, a future knob).

Determinism: frailty runs its OWN seeded RNG stream (never self.rng, the canon stream —
zero draws), and every draw iterates a sorted-by-oid order, so the digest is invariant to
PYTHONHASHSEED (gate MJ-REPRO). OFF (arm "off"/None) => no side-table, no draw, no cull,
fingerprint_blob()==b"" => byte-identical to canon (gate MJ-OFF).

The arm presets below are PLACEHOLDER calibration; Ф2 tunes (n0,k,x0) so the MEAN lifespan
matches the measured base (pawn.py seed 7, rho=0 -> mean≈120), leaving the SHAPE of the
hazard as a prediction, never a fit (WO §3).
"""
from __future__ import annotations

import random

# A dedicated RNG stream, disjoint from canon (self.rng, seeded by SEED) and from
# _place_oases (seed·1_000_003) and the archipelago bridge — a distinct prime + salt so the
# (seed,t) lattice never collides with another module's draws.
_FRAILTY_PRIME = 2_654_435_761
_FRAILTY_SALT = 0x0F3A11
_MASK48 = 0xFFFFFFFFFFFF

# arm -> (n0, k, x0). PLACEHOLDER — Ф2 calibrates to mean≈120. The SHAPE (Gompertz vs
# Weibull) is a prediction of x0, not a setting: x0>0 -> Gompertz expected; x0=0 -> Weibull.
_ARMS = {
    # gompertz control: many blocks + a starting damage load (§5 J1 predicts log-linear μ).
    "gompertz": {"n0": 40, "k": 0.02, "x0": 0.10},
    # flat control (§4, Makeham-only): a single block => constant per-tick hazard k =>
    # geometric (exponential) lifetime, mean 1/k. The reliability machine's degenerate case.
    "flat": {"n0": 1, "k": 1.0 / 120.0, "x0": 0.0},
}


class FrailtyField:
    """Side-table senescence organ. Inert (a strict no-op, empty fingerprint) unless the
    arm is one of {"flat","gompertz"}; mirrors DebtLedger/PublicGood's OFF discipline."""

    def __init__(self, arm="off", *, n0=None, k=None, x0=None, rho_rep=0.0, seed=0):
        self.arm = arm
        self.on = arm not in (None, "off")
        preset = _ARMS.get(arm, {})
        self.n0 = int(n0 if n0 is not None else preset.get("n0", 0))
        self.k = float(k if k is not None else preset.get("k", 0.0))
        self.x0 = float(x0 if x0 is not None else preset.get("x0", 0.0))
        self.rho_rep = float(rho_rep)          # 0 => the repair seam never fires
        self.seed = int(seed)
        self._blocks: dict[int, int] = {}      # oid -> intact redundancy blocks (hidden)

    # ---- own RNG: canon self.rng gets ZERO draws (gate MJ-OFF/MJ-REPRO) ------ #
    def _rng(self, t: int) -> random.Random:
        return random.Random((self.seed * _FRAILTY_PRIME + t * 9176 + _FRAILTY_SALT) & _MASK48)

    def _seed_intact(self, r: random.Random) -> int:
        # intact ~ Binomial(n0, 1 - x0): undamaged blocks at birth (fresh draw per pawn).
        p = 1.0 - self.x0
        return sum(1 for _ in range(self.n0) if r.random() < p)

    def _capital_of(self, w, oid: int) -> int:
        # CAPITAL, never body: count of cells this oid owns. If repair depended on body,
        # frailty would be legible off the substrate again (ВСТАВКА-27). Guarded by rho_rep>0.
        co = getattr(w, "_cell_owner", None)
        return sum(1 for o in co.values() if o == oid) if co else 0

    # ---- the tick: seed -> age (+optional repair) -> cull -------------------- #
    def tick(self, w):
        if not self.on:
            return
        # prune to the living: canon (sim_comm, inside super().step()) has just culled the
        # starvation-dead from w.pop; drop their stale blocks so the table never leaks and
        # the fingerprint holds only living oids (the mark-ledger-GC lesson, mod G2).
        living = {a.oid for a in w.pop}
        if len(self._blocks) != len(living):
            self._blocks = {o: v for o, v in self._blocks.items() if o in living}
        r = self._rng(w.t)
        pop = sorted(w.pop, key=lambda a: a.oid)     # sorted => hash-seed-invariant draws
        # 1) seed any unseen pawn (initial population AND this tick's births) with a fresh,
        #    non-inherited draw.
        for a in pop:
            if a.oid not in self._blocks:
                self._blocks[a.oid] = self._seed_intact(r)
        # 2) age blocks, optional capital-funded repair; collect the exhausted.
        dead = []
        for a in pop:
            intact = self._blocks[a.oid]
            if intact > 0:
                failed = sum(1 for _ in range(intact) if r.random() < self.k)
                intact -= failed
                if self.rho_rep > 0.0 and failed > 0:      # the elite-theory repair seam
                    p_rep = min(1.0, self.rho_rep * self._capital_of(w, a.oid))
                    if p_rep > 0.0:
                        intact += sum(1 for _ in range(failed) if r.random() < p_rep)
                self._blocks[a.oid] = intact
            if intact <= 0:
                dead.append(a)
        # 3) cull — the canonical death path, byte-for-byte (sim_comm.step step 3).
        if dead:
            self._cull(w, dead)

    def _cull(self, w, dead):
        """Deposit body to soil, emit the death event (cause="senescence"), scrub the pawn's
        belief ledgers and speaker membership, drop its blocks — then remove it from the
        population. An exact copy of the canonical body<DEATH path, so mass is MOVED
        (Σbody -> soil), never made (gate MJ-MASS), and a senescence-dead oid is
        indistinguishable downstream from a starvation-dead one (mark-GC sweeps it next)."""
        deadset = {a.oid for a in dead}
        for a in dead:
            w.soil[a.i, a.j] += a.body
            w.log.emit(w.t, "death", "individual", where=(a.i, a.j),
                       actor=a.oid, dm=-a.body,
                       data={"age": a.age, "cause": "senescence"})
            for d in (w.mem, w.belief, w.from_hearsay):
                d.pop(a.oid, None)
            w.speaker.discard(a.oid)
            self._blocks.pop(a.oid, None)
        w.pop = [a for a in w.pop if a.oid not in deadset]

    # ---- fingerprint: empty when OFF (byte-identical to main); sorted blocks when
    #      ON so any non-determinism surfaces (gate MJ-REPRO). MUST be appended LAST in
    #      state_fingerprint so the OFF b"" leaves the prior concatenation untouched. ---- #
    def fingerprint_blob(self) -> bytes:
        if not self.on or not self._blocks:
            return b""
        s = ";".join(f"{oid}:{self._blocks[oid]}" for oid in sorted(self._blocks))
        return ("|FRAIL|" + s).encode()
