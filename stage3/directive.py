"""
directive.py — the god's intent layer, and the deterministic means-selector (mod A).

The voice of god is LAYERED, never mixed (see нить «Голос бога, не рука»): a Demerzel has
his own base personality PLUS a separate, logged Directive (goal + constraints). God sets
WHAT; the personality (an LLM in mod B) invents HOW. Clean attribution is the whole point:
every Demerzel move is logged as a triple directive -> means -> world_delta.

Means run through the SALIENCE channel (module 21, already built): the injected ledger is
attention-bookkeeping only (never touches mem[c].food, never touches mass), so the voice is
orthogonal to every deception layer 11-19 and cannot break the canon. With no directive the
ledger stays empty and the Polis is byte-identical to the tower.

mod A goals:
  PROMOTE(target)     raise the significance of `target`'s cell in neighbours' budgets
  SOW_DISCORD         inject decoy salience broadly (crowd out good memories -> discord)
  IMPLANT(cell)       repeatedly push one cell into listeners' budgets (anchor an agenda)
  GROOM_SUCCESSOR     задел: accepted but NO-OP in mod A (ученик/ритуал live in mod C/D)
"""
from __future__ import annotations

from dataclasses import dataclass, field

PROMOTE = "PROMOTE"
SOW_DISCORD = "SOW_DISCORD"
IMPLANT = "IMPLANT"
GROOM_SUCCESSOR = "GROOM_SUCCESSOR"

_GOALS = {PROMOTE, SOW_DISCORD, IMPLANT, GROOM_SUCCESSOR}


@dataclass
class Directive:
    goal: str
    target: int | None = None            # oid (PROMOTE) or None
    payload: dict = field(default_factory=dict)   # IMPLANT: {"cell": (i,j)}; др. params
    constraints: dict = field(default_factory=dict)  # {"covert": True, "max_exposure":0.3}
    issued_t: int = 0

    def __post_init__(self):
        if self.goal not in _GOALS:
            raise ValueError(f"unknown directive goal: {self.goal!r}")


def choose_means(world, demerzel_oid: int, personality, directive: Directive):
    """Deterministic means-selector for mod A. Returns a list of (listener_oid, cell,
    amount) salience injections the Demerzel emits this tick, given its personality and
    perception. NO randomness — reproducible. The world APPLIES these to `injected`.

    Personality biases HOW, not WHAT:
      - attention_K widens/narrows how many listeners the voice can reach this tick
      - deception_lean scales the injected amount (a louder liar pushes harder)
      - constraints.covert caps per-listener exposure (стелс -> weaker, broader)
    """
    if directive is None or directive.goal == GROOM_SUCCESSOR:
        return []   # no-op задел / no directive

    pop = world.pop
    by_oid = {a.oid: a for a in pop}
    dem = by_oid.get(demerzel_oid)
    if dem is None:
        return []   # Demerzel dead -> voice silent (living-window closes)

    # reach: how many listeners the voice touches this tick (personality-scaled)
    reach = personality.attention_K
    covert = bool(directive.constraints.get("covert", False))
    base_amt = world.inject_amount * (0.5 + personality.deception_lean)   # louder = pushier
    if covert:
        base_amt *= directive.constraints.get("max_exposure", 0.3)       # quieter, broader

    # listeners = the nearest `reach` living agents to the Demerzel (sorted by oid for
    # determinism on ties), excluding self.
    def d2(a):
        return (a.i - dem.i) ** 2 + (a.j - dem.j) ** 2
    others = sorted((a for a in pop if a.oid != demerzel_oid),
                    key=lambda a: (d2(a), a.oid))[:reach]

    emissions = []
    if directive.goal == PROMOTE:
        tgt = by_oid.get(directive.target)
        if tgt is None:
            return []                       # target dead -> nothing to promote
        cell = (tgt.i, tgt.j)               # push the target's cell into others' budgets
        for L in others:
            emissions.append((L.oid, cell, base_amt))
    elif directive.goal == IMPLANT:
        cell = tuple(directive.payload.get("cell", (dem.i, dem.j)))
        for L in others:
            emissions.append((L.oid, cell, base_amt))
    elif directive.goal == SOW_DISCORD:
        # broad noise: push each listener's OWN cell's neighbour (a distracting decoy),
        # crowding out whatever good memory they hold — spoiling, not a single anchor.
        for L in others:
            decoy = (min(L.i + 1, world._rows() - 1) if hasattr(world, "_rows") else L.i, L.j)
            emissions.append((L.oid, decoy, base_amt))
    return emissions
