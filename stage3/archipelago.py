"""
archipelago.py — mod D: two Polis worlds side by side, joined by a migration bridge
with an EXIT STAKE, to test one pre-registered question of the "Редукция и горизонт"
thread:

    Does a lineage whose carriers PAY THE EXIT STAKE (a lethal, irreversible migration
    cost) out-copy a lineage that sits in the local optimum — with NO télos, on a blind
    conservative substrate?

If the "expansive" (migrating) lineage wins blindly, we have measured that
transcendence/expansion is an EQUILIBRIUM of the payoff structure, not an intent — the
same shape as the deception result (lying is an equilibrium, not an instruction).

ARCHITECTURE (decided 2026-07-06, Stan's default):
  * Two ISOLATED Polis worlds (home, frontier) — NOT one shared grid. Each keeps its own
    canon invariant (state_fingerprint, matter_drift vs its own M0). The bridge is a
    layer ABOVE the pair, never a new World subclass, so OFF ≡ two independent canon runs.
  * A MIGRATION CHANNEL, not spatial adjacency: an oid leaves the source pop and appears
    in the destination pop with (mostly) its mass. Cheap, deterministic, canon-safe.
  * EXIT STAKE = a mass lottery. Crossing costs a fixed fraction of body; a draw against
    a survival probability can KILL the migrant in transit (body -> 0, dies before
    arrival). This is spore/dispersal-as-strategy operationalised: the gamble is real and
    irreversible.
  * SUBSTRATE GRADIENT: the frontier has richer resource (higher KP_HIGH oases / avail),
    so a survivor breeds better there — the payoff that could reward paying the stake.
  * WHO LEAVES is a DETERMINISTIC THRESHOLD (crowding/hunger), never a mind. This is the
    sharpest form of the test: if a BLIND rule wins blindly, télos is not needed. (Live-
    mind migration and multi-god proxy war are mod D+2, after the base is measured.)

MASS CONSERVATION (the spine — this is the first gate, MD-mass):
  A migrant carries body B. On crossing:
      stake_loss = stake_frac * B          -> returned to the SOURCE world's plant grid
                                              (the stake is burned at home: the cost of
                                              leaving stays in the home substrate)
      if RNG draw >= survive_p:            -> the migrant DIES in transit; its remaining
          the whole remaining (B - loss)      (B - loss) also returns to SOURCE plant
          returns to source plant             (nothing reaches the frontier)
      else (survives):                     -> (B - loss) becomes the arriving body in the
                                              DESTINATION world's pop
  Therefore: source loses exactly B from its pop; of that, stake_loss (always) and the
  full remainder (on death) go back to source plant; only a survivor's remainder leaves
  the source and enters the destination. Each world's own (soil+plant+Σbody) is preserved
  to <1e-9, AND the pair's total is preserved — proved bit-exactly in gate MD-mass.

DETERMINISM: the crossing lottery uses a dedicated stdlib Random seeded from
(seed, t, oid) — never the world RNG, so the substrate stays byte-identical to canon
between migrations, and the whole archipelago replays identically from its seed.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

from sim_eventlog import EventLog, DEATH
from sim_comm import R, C

from .polis import Polis, PolisConfig


# --------------------------------------------------------------------------- #
@dataclass
class BridgeConfig:
    """The migration channel between two polises. All-OFF (migrate_every huge / rate 0)
    -> the two worlds never interact -> archipelago == two independent canon runs."""
    open_t: int = 100                 # no crossings before this tick (let polises settle)
    migrate_every: int = 5            # evaluate the exit threshold every N ticks
    stake_frac: float = 0.25          # fraction of body burned to the SOURCE plant on exit
    survive_p: float = 0.6            # P(reach the far shore); else die in transit
    # deterministic exit threshold (who leaves) — crowding OR hunger drives dispersal:
    crowd_frac: float = 0.7           # leave if local cell occupancy >= crowd_frac * peak
    hunger_body: float = 3.0 * DEATH  # ...or if body below this (starving -> gamble out)
    max_leavers_per_wave: int = 2     # cap emigration per evaluation (deterministic order)
    one_way: bool = True              # True: home->frontier only (the expansion test);
                                      # False: symmetric (both may shed migrants)
    frontier_richness: float = 2.0    # substrate GRADIENT: frontier oasis capacity ×this
                                      # (1.0 = no gradient -> pure "why leave a copy of
                                      # your world?" null). Applied as a bridge-layer hook
                                      # after each oasis relocation, so canon Polis is
                                      # untouched (richness 1.0 == byte-identical canon).


def _bridge_rng(seed: int, t: int, oid: int) -> random.Random:
    """A dedicated deterministic stream for one crossing lottery. NEVER the world RNG —
    keeps the substrate byte-identical to canon between migrations."""
    return random.Random((seed * 1_000_003) ^ (t * 9176 + 12345) ^ (oid * 2_654_435_761))


class Archipelago:
    """Two Polis worlds + a migration bridge. Steps both worlds each tick, then (on the
    bridge cadence, past open_t) evaluates the deterministic exit threshold and moves
    qualifying bodies across, paying the exit stake. Records per-lineage copy counts so
    the pre-registered question can be read off the run."""

    def __init__(self, home_cfg: PolisConfig, frontier_cfg: PolisConfig,
                 bridge: BridgeConfig | None = None, seed: int = 0):
        self.bridge = bridge or BridgeConfig()
        self.seed = int(seed)
        self.home = Polis(EventLog(), home_cfg)
        self.frontier = Polis(EventLog(), frontier_cfg)
        self.t = 0
        # migration ledger: (t, from, to, oid, body_in, survived, arrived_body)
        self.crossings = []
        self._migrant_oids = {"home": set(), "frontier": set()}   # who is an immigrant
        # provenance: (world_tag, oid) -> ("migrant", source_oid) for lineage copy-counting
        self._provenance = {}
        self._n_deaths_in_transit = 0
        # mass flux bookkeeping: each world's M0 is fixed at birth, but migration legally
        # moves mass ACROSS worlds. A per-world matter_drift vs static M0 is therefore
        # meaningless for an OPEN system; we track imported/exported mass so the honest
        # invariant is  matter - M0 - imported + exported ≈ 0  per world, AND the pair sum
        # is conserved absolutely (imports of one == exports of the other).
        self._flux = {"home": {"in": 0.0, "out": 0.0},
                      "frontier": {"in": 0.0, "out": 0.0}}
        self._days = min(home_cfg.days, frontier_cfg.days)

    # ---- the exit threshold (deterministic; no mind) ---------------------- #
    def _peak_occupancy(self, w: Polis) -> int:
        occ = {}
        for a in w.pop:
            occ[(a.i, a.j)] = occ.get((a.i, a.j), 0) + 1
        return max(occ.values()) if occ else 1

    def _leavers(self, w: Polis) -> list:
        """Bodies that qualify to emigrate this wave, by the blind threshold. Deterministic
        order (oid); capped. Crowding uses the world's own peak so it scales with density."""
        b = self.bridge
        peak = self._peak_occupancy(w)
        occ = {}
        for a in w.pop:
            occ[(a.i, a.j)] = occ.get((a.i, a.j), 0) + 1
        out = []
        for a in sorted(w.pop, key=lambda x: x.oid):
            crowded = occ[(a.i, a.j)] >= b.crowd_frac * peak
            hungry = a.body < b.hunger_body
            if crowded or hungry:
                out.append(a)
            if len(out) >= b.max_leavers_per_wave:
                break
        return out

    # ---- one crossing (mass-neutral by construction) ---------------------- #
    def _cross(self, src: Polis, dst: Polis, src_tag: str, dst_tag: str, a):
        b = self.bridge
        B = float(a.body)
        stake = b.stake_frac * B
        remainder = B - stake
        i0, j0 = a.i, a.j
        # detach the migrant's SOUL from the source substrate: its per-oid dicts (memory,
        # belief, gen, hearsay, speaker, injected) leave WITH it. Cleaning the source is
        # mandatory — a stale oid left in src.mem/injected corrupts _observe and the
        # fingerprint (measured: KeyError in _observe on first crossing).
        soul = self._detach_soul(src, a.oid)
        # remove the body from the source pop (its mass leaves pop)
        src.pop = [x for x in src.pop if x is not a]
        # the stake is ALWAYS burned back into the source substrate (plant grid)
        self._return_to_plant(src, i0, j0, stake)
        rng = _bridge_rng(self.seed, self.t, a.oid)
        survived = rng.random() < b.survive_p
        arrived = 0.0
        if not survived:
            # dies in transit: the whole remainder also returns to source plant; the soul
            # is discarded (nothing reaches the far shore)
            self._return_to_plant(src, i0, j0, remainder)
            self._n_deaths_in_transit += 1
        else:
            # arrives on the far shore with the remainder as its new body and its soul.
            # Only a SURVIVOR moves mass across worlds: `remainder` leaves src, enters dst.
            self._place_immigrant(dst, dst_tag, a, remainder, soul)
            arrived = remainder
            self._flux[src_tag]["out"] += remainder
            self._flux[dst_tag]["in"] += remainder
        self.crossings.append((self.t, src_tag, dst_tag, a.oid, B, survived, arrived))

    def _detach_soul(self, w: Polis, oid: int) -> dict:
        """Pop every per-oid substrate entry for `oid` out of the source world and return
        it as a portable bundle. Mirrors exactly the dicts CommWorld/SalienceWorld seed at
        birth, so re-attaching is a faithful inverse."""
        was_speaker = oid in w.speaker
        w.speaker.discard(oid)
        return {
            "gen": w.gen.pop(oid, 0),
            "mem": w.mem.pop(oid, {}),
            "belief": w.belief.pop(oid, ""),
            "from_hearsay": w.from_hearsay.pop(oid, set()),
            "speaker": was_speaker,
            "injected": (w.injected.pop(oid, {})
                         if getattr(w, "injected", None) is not None else {}),
        }

    def _return_to_plant(self, w: Polis, i: int, j: int, mass: float):
        """Burn `mass` back into the world's plant grid at (i,j) — keeps THIS world's
        (soil+plant+Σbody) invariant when a body leaves its pop."""
        if mass <= 0.0:
            return
        w.plant[i, j] += mass

    def _place_immigrant(self, dst: Polis, dst_tag: str, a, body: float, soul: dict):
        """Insert the surviving migrant into the destination pop AND re-seed all its
        per-oid substrate dicts from the ported soul. Body is the post-stake remainder,
        taken FROM the source — the destination gains exactly `body`, no more.

        CRITICAL (measured: KeyError on oid 12): the two worlds number oids independently
        from the same allocator, so their oid spaces OVERLAP. A migrant keeping its source
        oid would clobber the destination native of the same number and corrupt future
        births. The migrant is therefore RE-LABELLED to a fresh destination oid
        (dst._next++), exactly as a newborn would be; its old (world, oid) is remembered in
        the provenance map for lineage copy-counting."""
        old_oid = a.oid
        new_oid = dst._next
        dst._next += 1
        a.oid = new_oid
        a.body = body
        # land at the destination's lowest-oid occupied cell region (deterministic);
        # fall back to (0,0) of the arena if empty.
        if dst.pop:
            anchor = min(dst.pop, key=lambda x: x.oid)
            a.i, a.j = anchor.i, anchor.j
        else:
            a.i, a.j = 0, 0
        dst.pop.append(a)
        # re-attach the soul under the NEW oid: memory/belief/lineage travel with it
        dst.gen[new_oid] = soul["gen"]
        dst.mem[new_oid] = soul["mem"]
        dst.belief[new_oid] = soul["belief"]
        dst.from_hearsay[new_oid] = soul["from_hearsay"]
        if soul["speaker"]:
            dst.speaker.add(new_oid)
        if soul["injected"] and getattr(dst, "injected", None) is not None:
            dst.injected[new_oid] = soul["injected"]
        self._migrant_oids[dst_tag].add(new_oid)
        # provenance: the frontier oid traces back to a home-born migrant (lineage tag)
        self._provenance[(dst_tag, new_oid)] = ("migrant", old_oid)
        # ensure the destination can build a thick pawn view for the newcomer
        dst._pawns.pop(new_oid, None)

    # ---- the step ---------------------------------------------------------- #
    def _apply_gradient(self):
        """Bridge-layer substrate gradient: lift the frontier's oasis carrying capacity by
        frontier_richness. Re-applied right after each oasis relocation (OASIS_PERIOD),
        because _place_oases resets KPc. NEVER touches home; a richness of 1.0 is a no-op
        so the frontier stays byte-identical to canon (gate MD-OFF holds)."""
        b = self.bridge
        if b.frontier_richness == 1.0:
            return
        from sim_comm import KP_HIGH, KP_LOW
        import numpy as np
        w = self.frontier
        hi = KP_HIGH * b.frontier_richness
        # oasis cells are those currently at KP_HIGH; lift only those
        w.KPc = np.where(w.KPc >= KP_HIGH - 1e-9, hi, w.KPc)

    def step(self):
        self.home.step()
        self.frontier.step()
        # gradient rides on the tick AFTER a relocation reset (frontier.t already advanced)
        from sim_comm import OASIS_PERIOD
        if self.frontier.t % OASIS_PERIOD == 0:
            self._apply_gradient()
        self.t += 1
        b = self.bridge
        if self.t >= b.open_t and (self.t % b.migrate_every == 0):
            for a in self._leavers(self.home):
                self._cross(self.home, self.frontier, "home", "frontier", a)
            if not b.one_way:
                for a in self._leavers(self.frontier):
                    self._cross(self.frontier, "home", "home", "frontier", a)

    # ---- conservation over the PAIR --------------------------------------- #
    def pair_matter(self) -> float:
        return self.home._matter() + self.frontier._matter()

    def pair_drift(self) -> float:
        return abs(self.pair_matter() - (self.home.M0 + self.frontier.M0))

    def world_drift(self, tag: str) -> float:
        """Honest conservation for an OPEN world: matter - M0 - imported + exported.
        A closed world (no crossings) reduces to the canon matter_drift."""
        w = self.home if tag == "home" else self.frontier
        fx = self._flux[tag]
        return abs(w._matter() - w.M0 - fx["in"] + fx["out"])

    # ---- metrics ----------------------------------------------------------- #
    def report(self) -> dict:
        surv = sum(1 for c in self.crossings if c[5])
        return {
            "t": self.t,
            "home_pop": len(self.home.pop),
            "frontier_pop": len(self.frontier.pop),
            "crossings": len(self.crossings),
            "survived": surv,
            "died_in_transit": self._n_deaths_in_transit,
            "frontier_immigrants": len(self._migrant_oids["frontier"]),
            "home_drift": self.world_drift("home"),          # flux-adjusted (open system)
            "frontier_drift": self.world_drift("frontier"),
            "pair_drift": self.pair_drift(),                 # absolute (closed pair)
        }

    def lineage_scores(self) -> dict:
        """The pre-registered read: does the EXPANSIVE lineage out-copy the STAY-HOME one?

        expansive = surviving migrants on the frontier + their frontier-born descendants
                    (traced by birth provenance);
        stay_home = everyone still resident in home.

        We count LIVING COPIES (bodies) at the end of the run, plus cumulative births on
        each side, so 'out-copy' is read as both standing stock and flow. Descendants of
        migrants are identified by walking the destination birth log: any frontier birth
        whose parent is (transitively) a migrant oid is expansive.

        NOTE: a migrant that DIES in transit leaves no copy — that is the stake, and it is
        already reflected by absence from the frontier pop. The question is whether the
        surviving-and-breeding tail beats the local optimum DESPITE the lethal toll."""
        # 1. seed expansive set with surviving migrant oids on the frontier
        migrant_oids = set(self._migrant_oids["frontier"])
        expansive = set(migrant_oids)
        # 2. close over frontier births: parent expansive -> child expansive. The frontier
        #    event log carries chronological birth events (dataclass Event: .kind/.actor/
        #    .parent), so one forward pass closes the lineage.
        for e in self.frontier.log.events:
            if e.kind == "birth" and e.parent in expansive and e.actor is not None:
                expansive.add(e.actor)
        living_expansive = sum(1 for a in self.frontier.pop if a.oid in expansive)
        living_frontier_native = len(self.frontier.pop) - living_expansive
        return {
            "living_home": len(self.home.pop),             # stay-home standing stock
            "living_expansive": living_expansive,          # migrant lineage on frontier
            "living_frontier_native": living_frontier_native,
            "migrants_sent": len(self.crossings),
            "migrants_survived": sum(1 for c in self.crossings if c[5]),
            "expansive_descendants": living_expansive - sum(
                1 for a in self.frontier.pop if a.oid in migrant_oids),
        }

    def fingerprint(self) -> str:
        h = hashlib.sha256()
        h.update(self.home.state_fingerprint().encode())
        h.update(self.frontier.state_fingerprint().encode())
        cr = ";".join(f"{t}:{fr}->{to}:{oid}:{B:.6f}:{int(s)}:{arr:.6f}"
                      for (t, fr, to, oid, B, s, arr) in self.crossings)
        h.update(("|CROSS|" + cr).encode())
        return h.hexdigest()[:16]


def run_archipelago(home_cfg: PolisConfig, frontier_cfg: PolisConfig,
                    bridge: BridgeConfig | None = None, seed: int = 0, days: int | None = None):
    arc = Archipelago(home_cfg, frontier_cfg, bridge=bridge, seed=seed)
    n = days if days is not None else arc._days
    for _ in range(n):
        arc.step()
    return arc
