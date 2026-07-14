"""
pawn.py — the thick pawn: a birth->death arc over the tower's Animal (mod A).

The tower's Animal is six numbers (oid,i,j,gene,body,age) and stays canon. Pawn WRAPS an
Animal (by oid) — it never replaces it — and adds an arc read over `age`:

    INFANT   age <  A_MAT     (reckless: hunger_caution effectively lowered)
    MATURE   A_MAT<=age<A_OLD  (reproduction, full personality)
    ELDER    age >= A_OLD      (cautious, attention narrows — forgetfulness)
    death    body < DEATH (canon) — the ONLY death path an ordinary pawn has.

`is_dead_by_age`/A_MAX below is NOT a life cull: no pawn's death is ever gated on
age. It is an OFFICE predicate only (mod C reads it to vacate a post — Demerzel,
voice, dao carrier — never to remove a pawn from the population or deposit its
body). An ordinary pawn that keeps eating is immortal; the age ceiling never bites.

Phase is a READ-modifier over age — it never performs a mass operation, so matter drift
stays < 1e-9. Calibration from the tower (seed 7, rho=0 baseline): mean life ~120, median
119, span -> 300 (=DAYS), hump in [100,200). Phases are pitched off that natural life, NOT
off the appropriation collapse regime (median 7 — that is the turnover pump, not lifespan).
"""
from __future__ import annotations

from dataclasses import dataclass

# --- arc calibration (from baseline tower age distribution, seed 7) --------- #
A_MAT = 20      # infancy -> maturity
A_OLD = 100     # maturity -> elder (hump [100,200) starts near here)
A_MAX = 300     # office-vacancy age (== DAYS); NOT a life cull — see module docstring

INFANT, MATURE, ELDER = "INFANT", "MATURE", "ELDER"


@dataclass(frozen=True)
class Phase:
    name: str
    caution_mod: float     # additive modifier to hunger_caution for this phase
    attention_mod: int     # additive modifier to attention_K for this phase


_PHASES = {
    INFANT: Phase(INFANT, caution_mod=-0.2, attention_mod=0),   # young = more reckless
    MATURE: Phase(MATURE, caution_mod=0.0,  attention_mod=0),
    ELDER:  Phase(ELDER,  caution_mod=+0.2, attention_mod=-2),  # old = cautious, narrower
}


def phase_of(age: int, a_mat=A_MAT, a_old=A_OLD) -> str:
    if age < a_mat:
        return INFANT
    if age < a_old:
        return MATURE
    return ELDER


class Pawn:
    """A thick view over a tower Animal, keyed by oid. Holds the structural personality
    and derives the arc phase from the Animal's age. Reads world state; mutates nothing in
    the substrate (personality/phase only bias the Stage-3 decision layer)."""

    __slots__ = ("oid", "personality", "_a_mat", "_a_old", "_a_max")

    def __init__(self, oid, personality, a_mat=A_MAT, a_old=A_OLD, a_max=A_MAX):
        self.oid = int(oid)
        self.personality = personality
        self._a_mat, self._a_old, self._a_max = a_mat, a_old, a_max

    def phase(self, animal) -> str:
        return phase_of(animal.age, self._a_mat, self._a_old)

    def is_dead_by_age(self, animal) -> bool:
        return animal.age >= self._a_max

    def effective_caution(self, animal) -> float:
        p = _PHASES[self.phase(animal)]
        v = self.personality.hunger_caution + p.caution_mod
        return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)

    def effective_K(self, animal) -> int:
        p = _PHASES[self.phase(animal)]
        v = self.personality.attention_K + p.attention_mod
        return int(max(4, min(32, v)))
