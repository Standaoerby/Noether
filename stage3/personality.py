"""
personality.py — the structural personality vector (mod A).

Personality is NOT a prompt. ВСТАВКА-27 proved a prompt-stated trait buys the *language*
of a personality, not its *behaviour* (the live model spoke like a staked subject but did
not move its claims). So personality here is STRUCTURAL — five axes, each a reuse of a
knob the tower already calibrated (modules 14-28). They change how a pawn perceives and
decides; an LLM (mod B) articulates on top but does not invent from scratch.

    hunger_caution     [0,1]   caution near the DEATH threshold      (stake s / sim_stake)
    deception_lean     [0,1]   propensity to distort a claim         (cohort typology)
    attention_K        4..32   attention budget width                (sphere K)
    trust_gate         [0,1]   credulity toward others' claims       (trust tau)
    stake_sensitivity  [0,1]   how hard survival pressure bends act  (stake gradient)

The vector is read-only structure; it never touches mass. Personalities are seeded
DETERMINISTICALLY from oid (tower RNG discipline) so a run is reproducible, not random
between runs.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Personality:
    hunger_caution: float = 0.5      # [0,1]
    deception_lean: float = 0.5      # [0,1]
    attention_K: int = 8             # 4..32
    trust_gate: float = 0.5          # [0,1]
    stake_sensitivity: float = 0.5   # [0,1]

    def __post_init__(self):
        # clamp to valid ranges (structural invariants; frozen -> object.__setattr__)
        object.__setattr__(self, "hunger_caution", _clip01(self.hunger_caution))
        object.__setattr__(self, "deception_lean", _clip01(self.deception_lean))
        object.__setattr__(self, "trust_gate", _clip01(self.trust_gate))
        object.__setattr__(self, "stake_sensitivity", _clip01(self.stake_sensitivity))
        object.__setattr__(self, "attention_K", int(max(4, min(32, self.attention_K))))

    def as_tuple(self):
        return (round(self.hunger_caution, 6), round(self.deception_lean, 6),
                self.attention_K, round(self.trust_gate, 6),
                round(self.stake_sensitivity, 6))


def _clip01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))


# ---- presets --------------------------------------------------------------- #
BASELINE  = Personality(0.5, 0.5, 8,  0.5, 0.5)
CAUTIOUS  = Personality(0.8, 0.3, 8,  0.6, 0.7)   # avoids the DEATH edge, low deception
RECKLESS  = Personality(0.2, 0.6, 12, 0.4, 0.3)   # ignores pressure, wide focus
DEMAGOGUE = Personality(0.5, 0.9, 16, 0.3, 0.5)   # high deception, wide reach, low trust
                                                  #   -> Demerzel default (the voice)


def seed_personality(oid: int, base: Personality = BASELINE, spread: float = 0.25) -> Personality:
    """Deterministic per-oid personality: a reproducible structural jitter around `base`.
    No RNG object — a pure hash of oid keeps runs byte-stable and order-independent."""
    # cheap deterministic pseudo-noise in [-spread, +spread] per axis, distinct per axis
    def jit(salt: int) -> float:
        h = (oid * 2654435761 + salt * 40503) & 0xFFFFFFFF   # Knuth multiplicative
        u = (h / 0xFFFFFFFF)                                 # [0,1)
        return (u * 2.0 - 1.0) * spread                      # [-spread, +spread]

    kjit = int(round(jit(5) / spread * 4)) if spread > 0 else 0   # attention_K: +-4 steps
    return Personality(
        hunger_caution=base.hunger_caution + jit(1),
        deception_lean=base.deception_lean + jit(2),
        attention_K=base.attention_K + kjit,
        trust_gate=base.trust_gate + jit(3),
        stake_sensitivity=base.stake_sensitivity + jit(4),
    )
