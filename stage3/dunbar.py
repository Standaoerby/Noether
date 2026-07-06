"""
dunbar.py — mod E: the SOCIAL attention locus (Dunbar's number) as a pure belief-layer
overlay on the Polis. NO mass is touched; this is entirely a property of what a pawn
KNOWS about OTHER PAWNS, mirroring the sphere layer's spatial attention budget but over
PEOPLE instead of PLACES.

WHY A NEW AXIS (not a reuse of attention_K): the sphere budget (module 21) caps memory of
CELLS — what food was seen where, decayed by recency, evicted when the budget overflows.
Dunbar's number is a different organ: a cap on active SOCIAL ties — how many other oids a
pawn actively "holds" (their reputation, whether they are kin, owner, familiar). Spatial
memory and social capacity are biologically distinct (hippocampal place memory vs
neocortical social tracking), so `dunbar_K` is its own knob.

THE REGISTRY. Each pawn carries
    known: dict[oid -> (last_contact_t, salience)]
Two pawns sharing a cell on a step is a CONTACT: each enters (or refreshes) the other in
its registry. A known-other's salience:
  * rises with contact frequency (each meeting bumps it),
  * carries a standing bonus for KIN (same _house line) and for OWNERS (status),
  * decays by recency every step (long unseen -> withers).
When the registry exceeds `dunbar_K`, the least-salient known-other is EVICTED = social
forgetting (logged as `unknow`, the mirror of the sphere's `forget`).

THE POINT (for the book). Trust/reputation (module 14 trust_gate; the slander machinery of
11-19) can only flow WITHIN the active registry: slander about someone you have forgotten
never lands; reputation outside the locus does not exist. This yields a natural CEILING on
the size of a coherent group — Dunbar's thesis, measured on a conservative substrate — and
connects straight to C-LIVE: a single pawn cannot carry influence past its own social
locus, which is why a tradition with no repeating carrier fades.

CONSERVATION. The registry is pure belief state. It never reads or writes body/soil/plant,
so matter_drift stays byte-identical to canon. With `dunbar_K = None` the whole overlay is
OFF and the Polis is bit-for-bit the tower (gate ME-OFF).

DETERMINISM. Contacts are read from the deterministic co-location map; eviction ties break
on (salience, oid); the registry is folded into the fingerprint so a replay is provable.
"""
from __future__ import annotations

# standing salience bonuses (outcome-neutral, structural — mirror sphere's _sig weights)
W_MEET = 1.0        # each co-location contact adds this to the known-other's salience
W_KIN = 2.0         # standing bonus if same _house line (kin are sticky)
W_OWNER = 1.5       # standing bonus if the known-other is an owner (status is memorable)
REC_HALFLIFE = 20.0  # ticks; recency decay so an unseen tie halves its salience


class DunbarRegistry:
    """Per-world social-tie bookkeeping. Owns every pawn's `known` map and the eviction
    rule. A no-op when dunbar_K is None. Kept OUT of the conserved substrate entirely."""

    def __init__(self, dunbar_K):
        self.K = dunbar_K
        self.known = {}            # oid -> {other_oid: [last_t, salience]}
        self.evictions = []        # (t, oid, dropped_oid, salience) — social forgetting log

    # ---- salience of a known-other (structural, outcome-neutral) ---------- #
    def _standing_bonus(self, world, other_oid) -> float:
        b = 0.0
        # kin: same _house founding line (module 25), if the world tracks it
        house = getattr(world, "_house", None)
        if house is not None:
            # _house maps oid -> line id; kinship = shared line
            pass  # resolved per-contact below where both oids are in hand
        return b

    def _decay_factor(self, dt: int) -> float:
        # exponential recency decay; dt ticks since last contact
        return 0.5 ** (dt / REC_HALFLIFE)

    # ---- the contact step (called once per world.step, after co-location) - #
    def register_contacts(self, world, t: int):
        """Read the deterministic co-location map and refresh registries, then decay and
        enforce the budget. No-op when K is None."""
        if self.K is None:
            return
        # 1. who shares a cell with whom this tick (deterministic order)
        bycell = {}
        for a in sorted(world.pop, key=lambda x: x.oid):
            bycell.setdefault((a.i, a.j), []).append(a.oid)
        owners = getattr(world, "_owner_ids", set())
        house = getattr(world, "_house", None)
        # 2. each co-located pair refreshes each other's registry
        for cell, oids in bycell.items():
            if len(oids) < 2:
                continue
            for me in oids:
                reg = self.known.setdefault(me, {})
                for other in oids:
                    if other == me:
                        continue
                    bonus = 0.0
                    if other in owners:
                        bonus += W_OWNER
                    if house is not None and house.get(me) is not None \
                            and house.get(me) == house.get(other):
                        bonus += W_KIN
                    rec = reg.get(other)
                    if rec is None:
                        reg[other] = [t, W_MEET + bonus]
                    else:
                        rec[0] = t
                        rec[1] += W_MEET + bonus
        # 3. decay by recency for every tie not refreshed this tick, then evict overflow.
        # Decay is computed from the ORIGINAL last-contact tick and never rewrites it — the
        # salience field alone carries the decayed value, so an unseen tie keeps withering
        # tick over tick without the timestamp drifting to 'now' (measured bug: rewriting
        # last_t to t reset the clock and produced 1.4M spurious evictions).
        for me, reg in self.known.items():
            for other, rec in reg.items():
                if rec[0] != t:                     # not refreshed this tick -> wither one step
                    rec[1] *= self._decay_factor(1)
            if len(reg) > self.K:
                # evict the least-salient ties; deterministic tie-break (salience, oid)
                ranked = sorted(reg.keys(), key=lambda o: (reg[o][1], o))
                for drop in ranked[:len(reg) - self.K]:
                    self.evictions.append((t, me, drop, round(reg[drop][1], 6)))
                    del reg[drop]

    # ---- queries the trust/slander layers can gate on --------------------- #
    def knows(self, me: int, other: int) -> bool:
        """True iff `other` is currently within `me`'s active social locus. Trust and
        reputation may only flow when this holds (the Dunbar ceiling in action)."""
        if self.K is None:
            return True  # OFF -> unlimited social memory -> everyone is 'known' (canon)
        return other in self.known.get(me, {})

    def locus_size(self, me: int) -> int:
        return len(self.known.get(me, {})) if self.K is not None else -1

    # ---- fingerprint contribution (proves determinism; empty when OFF) ---- #
    def fingerprint_blob(self) -> bytes:
        if self.K is None:
            return b""
        parts = []
        for me in sorted(self.known):
            ties = ";".join(f"{o}:{self.known[me][o][0]}:{self.known[me][o][1]:.6f}"
                            for o in sorted(self.known[me]))
            parts.append(f"{me}|{ties}")
        return ("||DUNBAR||" + "#".join(parts)).encode()
