"""
artifact.py — mod F (виток 1): material culture as a DUAL-LAYER reservoir sitting on
the Polis. This is the FIRST extension of the tower's conservation law in 28 modules:
the mass invariant gains a fourth term,

    soil + plant + Σbody + Σartifact.mass = M0   (drift < 1e-9 still holds).

An artifact is mass taken OUT of circulation and frozen into an object — lawful (mass
never vanishes, it changes form), but it needs its own reservoir beside soil/plant/body.
The +Σmass enters the invariant ONLY through Polis._matter() (a legal seam — Polis
already overrides step/fingerprint); with artifacts OFF the field is empty, sum_mass()
is 0.0, and _matter is byte-identical to canon (gate MF-OFF).

WHY (the diagnosis from the apprentice experiments, mod C / C-LIVE): дао-transmission
rots within a generation — a belief is a string in a head, dying with its carrier
(measured: a tradition with no repeating prophet fades). Civilisation requires that
knowledge/labour SETTLE OUTSIDE THE BODY — in an object that outlives its maker and is
read by the next. One pawn cannot push experience past its own generation through
communication alone.

TWO INDEPENDENT DECAY LAWS (divorced to the death, like дао ≠ voice):
  1. MATERIAL decay — reduction that CONSERVES mass. Each tick d = mat_decay·mass is
     returned to world.soil[i,j] (ruins → soil). Mass changes form, the invariant holds.
     Slow for a vessel (mat_decay is a property of `kind`). Return target is soil (not
     plant): keeps the civilisational arc slow, denies artifacts the role of cheat
     fast-food.
  2. SEMANTIC decay — forgetting that does NOT touch mass. salience ← salience·(1−sem_decay),
     decaying by its own law toward zero. Below read_threshold the object still STANDS
     (mass intact) but is NO LONGER READ: an unreadable ruin. COPYING RESETS the timer —
     only copied meaning is eternal (culture holds by retelling).

Material durability and semantic durability DIVERGE (the rhyme with C-LIVE: дао ≠ voice,
idea ≠ agency). A stone monument stands a thousand years — what it meant is forgotten in
three generations. A clay tablet crumbles — but while it is copied, the meaning outlives
the carrier. The carrier is the bridge: meaning outlives the body only if the matter
survives to the next reader OR the payload is copied before the old one falls silent.
Civilisation = the race of copying meaning against a double decay.

CONSERVATION. The only mass operations are TRANSFERS, all inside _matter's reach:
writing moves body→mass, material decay moves mass→soil, copying is payload-only (never
mass). The semantic layer (payload/salience) and the carried-method overlay are pure
belief state — they never read or write body/soil/plant, so a run with reading/copying
but no writing/decay leaves Σmass bit-exact (gate MF-semantic).

DETERMINISM. Pawns are walked in sorted(oid) order; artifacts in aid order; the aid
namespace is disjoint from oid (base offset), mirroring the archipelago's re-claim of a
migrant's oid. The field folds into the fingerprint so a replay is provable.

VITOK 1 = kind="vessel" only (carrier of knowledge + both decays): fixes the apprentice
problem, the core of civilisation. kind="store" (a printable mass reserve against
hunger) and kind="capital" (an artifact multiplying avail) are VITOK 2, once the vessel
is measured. Не хвататься за всё сразу.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sim_eventlog import REPRO, DEATH

# aid namespace disjoint from oid: pawns number from 0 upward (into the thousands);
# artifacts start far above so a merged structure could never collide (measured lesson
# from the archipelago: overlapping id-spaces silently overwrite — KeyError). Cosmetic
# but load-bearing for any future oid/aid join.
ARTIFACT_AID_BASE = 10_000_000

# material-decay rate by kind: vessel is SLOW (a durable carrier); a store rots faster
# (grain spoils); capital wears fastest (a tool erodes with use). A property of the
# object, not a global knob — deterministic thresholds WE TEST.
KIND_MAT_DECAY = {"vessel": 1.0, "store": 3.0, "capital": 5.0}

# vitok-2 mint floors (measured calibration, seed 7 rho0.5 claim box6: tick-p99 body
# ≈ 4.7, tick-max ≈ 6.5, while p90 sits BELOW REPRO — mass lives in a narrow top).
# The floors stratify the mints by wealth: the merely-fat write (REPRO), the rich
# store a surplus (1.5·REPRO), the richest freeze a tool (2·REPRO). Blind rules, no
# intent — does blind surplus make a stratum?
STORE_BODY_FLOOR = 1.5 * REPRO     # body after store_stake must stay above this
CAPITAL_BODY_FLOOR = 2.0 * REPRO   # body after capital_stake must stay above this

# a written body-stake must not kill its author: writing may not pull body below this
# floor (a small margin above the canon DEATH threshold). Otherwise writing is suicide
# and no pawn ever writes (measured guard, documented as a calibration, not a fudge).
WRITE_BODY_FLOOR = REPRO           # never write below the reproduction line: only the fat write


@dataclass
class Artifact:
    """A dual-layer reservoir at a cell. MATERIAL layer (`mass`) is conserved and enters
    the invariant; SEMANTIC layer (`payload`, `salience`) is pure belief and decays on
    its own clock. Metadata records provenance and kind."""
    aid: int
    i: int
    j: int
    mass: float                                   # MATERIAL layer — in the invariant
    payload: dict = field(default_factory=dict)   # SEMANTIC layer — {belief:str, method_level:int}
    salience: float = 0.0                          # cultural loudness — decays to zero
    maker_oid: int | None = None
    born_t: int = 0
    kind: str = "vessel"


class ArtifactField:
    """Per-world owner of every artifact — the overlay, built EXACTLY on the
    DunbarRegistry pattern: owns the list, ticks BOTH decays, contributes to the
    invariant (sum_mass) and to the fingerprint (fingerprint_blob, empty when OFF),
    a no-op when disabled. The MATERIAL layer is the only thing it puts into the
    conserved substrate (via Polis._matter); everything else is belief overlay."""

    def __init__(self, enabled: bool, write_stasis: int = 8, write_stake: float = 0.30,
                 mat_decay: float = 0.001, sem_decay: float = 0.02,
                 read_threshold: float = 0.5, salience0: float = 1.0,
                 store_on: bool = False, store_stake: float = 0.30,
                 store_draw_at: float = 0.40, store_draw_rate: float = 0.10,
                 store_access: str = "open",
                 capital_on: bool = False, capital_stake: float = 0.50,
                 capital_rate: float = 0.02, capital_access: str = "open"):
        self.on = bool(enabled)
        # thresholds (deterministic — WE TEST them; first question is whether BLIND
        # accumulation makes a civilisation with no intent, same logic as expansion-as-
        # equilibrium-not-télos)
        self.write_stasis = int(write_stasis)      # ticks a pawn must dwell before it writes
        self.write_stake = float(write_stake)      # kg of body frozen into a new artifact
        self.mat_decay = float(mat_decay)          # base material-decay rate (× kind multiplier)
        self.sem_decay = float(sem_decay)          # semantic-decay rate (salience → 0)
        self.read_threshold = float(read_threshold)  # salience below this => unreadable ruin
        self.salience0 = float(salience0)          # starting/refreshed cultural loudness
        # vitok 2 — store (a printable mass reserve) and capital (a productivity tool).
        # Both OFF by default => the vitok-1 vessel run is byte-identical (gate MFv2-OFF).
        self.store_on = bool(store_on)
        self.store_stake = float(store_stake)      # kg of body frozen into a store
        self.store_draw_at = float(store_draw_at)  # hunger line: body below this may draw
        self.store_draw_rate = float(store_draw_rate)  # kg per tick a drawer may extract
        self.store_access = str(store_access)      # open | owner | maker
        self.capital_on = bool(capital_on)
        self.capital_stake = float(capital_stake)  # kg of body frozen into a tool
        self.capital_rate = float(capital_rate)    # soil→body per tick per kg of tool
        self.capital_access = str(capital_access)  # open | owner | maker

        self.artifacts: list[Artifact] = []
        self._next_aid = ARTIFACT_AID_BASE
        # belief overlays (pure state, never mass):
        self.known_method: dict[int, int] = {}     # oid -> highest method_level it carries
        self._dwell: dict[int, tuple] = {}         # oid -> (cell, consecutive_ticks)
        self._read_seen: dict[int, set] = {}       # oid -> {aid} already absorbed (read dedup)
        # logs (for HF1–HF3 attribution; never touch mass):
        self.writes: list[tuple] = []              # (t, aid, maker, cell, stake, method)
        self.reads: list[tuple] = []               # (t, aid, reader, method, maker, born_t)
        self.copies: list[tuple] = []              # (t, aid, copier, old_method, new_method)
        self.ruins: list[tuple] = []               # (t, aid, cell, returned_mass) — fully decayed
        # vitok-2 logs (attribution for HG1–HG3; never touch mass):
        self.stores: list[tuple] = []              # (t, aid, maker, cell, stake)
        self.capitals: list[tuple] = []            # (t, aid, maker, cell, stake)
        self.draws: list[tuple] = []               # (t, aid, drawer, amount, maker)
        self.boosts: list[tuple] = []              # (t, harvester, cell, extra, cap_mass)

    # ---- invariant contribution (0.0 when OFF => _matter ≡ canon) --------- #
    def sum_mass(self) -> float:
        # float 0.0 (not int 0) so the ':.9f' fingerprint term is byte-identical to canon
        if not self.on:
            return 0.0
        return float(sum(a.mass for a in self.artifacts))

    # ---- the tick (called once per world.step, after Dunbar) -------------- #
    def tick(self, world):
        """Writing → reading → copying → material decay → semantic decay. No-op when OFF.
        Order matters and is documented: a freshly written artifact (salience0 >
        read_threshold) is readable the SAME tick, but its maker already carries that
        method, so self-reading is a natural no-op; decays run last so a just-written
        vessel is not eroded on the tick it is born."""
        if not self.on:
            return
        t = world.t
        pop_sorted = sorted(world.pop, key=lambda a: a.oid)
        alive = {a.oid for a in world.pop}
        self._update_dwell(pop_sorted)
        # vitok-2 mints run FIRST, in descending wealth-floor order (capital > store >
        # vessel): the richest freeze a tool, the rich store a surplus, the merely-fat
        # write. Any mint resets dwell, so a pawn mints AT MOST ONCE per tick and the
        # cascade is deterministic. Both passes are no-ops when OFF => the vitok-1
        # vessel order (writing→reading→copying→decays) is untouched (gate MFv2-OFF).
        self._capitalizing(world, pop_sorted, t)   # tools by the richest (body→mass)
        self._storing(world, pop_sorted, t)        # surplus by the rich (body→mass)
        self._writing(world, pop_sorted, t)        # originals on bare cells (body→mass)
        self._reading(world, pop_sorted, t)        # first-contact absorb + refresh salience
        self._copying(world, pop_sorted, t)        # improved copies on readable carriers (body→mass)
        # vitok-2 flows run AFTER the mints: a store laid this tick is drawable the same
        # tick by ANOTHER hungry pawn (the minter itself is fat by gate); decays still
        # run LAST so a newborn object is not eroded on its birth tick.
        self._store_draw(world, pop_sorted, t)     # hunger draw (mass→body), conserved
        self._capital_harvest(world, pop_sorted, t)  # tool-gated extraction (soil→body)
        self._material_decay(world, t)             # mass → soil (ruins), conserved
        self._semantic_decay()                     # salience → 0 (forgetting), no mass
        # drop overlay state for the dead (belief only; no mass)
        for oid in [o for o in self.known_method if o not in alive]:
            del self.known_method[oid]
        for oid in [o for o in self._dwell if o not in alive]:
            del self._dwell[oid]
        for oid in [o for o in self._read_seen if o not in alive]:
            del self._read_seen[oid]

    # ---- dwell bookkeeping (stasis threshold for writing) ----------------- #
    def _update_dwell(self, pop_sorted):
        for a in pop_sorted:
            cell = (a.i, a.j)
            rec = self._dwell.get(a.oid)
            if rec is not None and rec[0] == cell:
                self._dwell[a.oid] = (cell, rec[1] + 1)
            else:
                self._dwell[a.oid] = (cell, 1)

    # ---- write eligibility (fat, non-hungry, settled) --------------------- #
    def _can_write(self, a) -> bool:
        """Deterministic threshold WE TEST: only a fat pawn (body > REPRO) that has dwelt
        long enough writes, and only if the stake would not pull it below the reproduction
        line (WRITE_BODY_FLOOR guard — writing must never starve the author). Blind
        accumulation by the fat: does it make a civilisation with no intent?"""
        if a.body <= REPRO:
            return False
        if self._dwell.get(a.oid, ((a.i, a.j), 0))[1] < self.write_stasis:
            return False
        return a.body - self.write_stake >= WRITE_BODY_FLOOR

    def _mint(self, world, a, method, t, is_copy):
        """Freeze write_stake of body into a NEW vessel carrying `method` — the single
        body→mass transfer (writing an original OR minting an improved copy). Resets the
        author's dwell so writing has a cadence (~1/write_stasis) — the copy-rate knob HF2
        turns against the two decay clocks."""
        stake = self.write_stake
        a.body -= stake                            # MASS leaves the body...
        art = Artifact(
            aid=self._next_aid, i=a.i, j=a.j, mass=stake,   # ...and enters the artifact
            payload={"belief": world.belief.get(a.oid, ""), "method_level": method},
            salience=self.salience0, maker_oid=a.oid, born_t=t, kind="vessel",
        )
        self._next_aid += 1
        self.artifacts.append(art)
        self.known_method[a.oid] = max(self.known_method.get(a.oid, 0), method)
        self._dwell[a.oid] = ((a.i, a.j), 0)       # spent the effort; re-settle to write again
        ev = "artifact_copy" if is_copy else "artifact_write"
        world.log.emit(t, ev, "individual", where=(a.i, a.j), actor=a.oid, dm=-stake,
                       data={"aid": art.aid, "method": method, "stake": round(stake, 6)})
        return art

    # ---- WRITING: body → mass, an ORIGINAL on a bare cell ----------------- #
    def _writing(self, world, pop_sorted, t):
        """An eligible pawn on a cell with NO readable carrier writes an ORIGINAL vessel
        (method = the method it already carries, usually 0 for a first-mover): the blind
        first act of deposition. On a cell that already holds a readable carrier it writes
        nothing here — copying (below) improves the existing lineage instead."""
        # ONLY a readable VESSEL occupies a cell for writing purposes: a store/capital
        # standing here must not block the knowledge layer (kind-isolation, vitok 2).
        occupied = {(art.i, art.j) for art in self.artifacts
                    if art.kind == "vessel" and art.salience > self.read_threshold}
        for a in pop_sorted:
            if (a.i, a.j) in occupied:             # a readable carrier here -> copying's job
                continue
            if not self._can_write(a):
                continue
            method = self.known_method.get(a.oid, 0)
            art = self._mint(world, a, method, t, is_copy=False)
            self.writes.append((t, art.aid, a.oid, (a.i, a.j), self.write_stake, method))

    def _readable_bycell(self):
        # kind-isolation (vitok 2): only a VESSEL is a carrier of meaning. A store or a
        # capital is semantically mute from birth (salience 0.0, empty payload) — it is
        # never read, never refreshed, never copied. In a vessel-only world (vitok 1)
        # the filter is a no-op, so the MF-* anchors stand byte-identical.
        bycell = {}
        for art in self.artifacts:
            if art.kind == "vessel" and art.salience > self.read_threshold:
                bycell.setdefault((art.i, art.j), []).append(art)
        return bycell

    # ---- READING: absorb payload WITHOUT a living teacher; keep it loud ---- #
    def _reading(self, world, pop_sorted, t):
        """A pawn on a cell with a READABLE carrier (salience > read_threshold) does two
        things, divorced so each is measurable:

          READ (first contact, once per (oid,aid)) — absorbs the carrier's method into its
            belief overlay (known_method, max). This is what the C-LIVE apprentice lacked:
            knowledge with NO living teacher. Logged on first contact regardless of
            method_level — even method 0 is a belief surviving its maker — the HF1 signal:
            does a carrier reach a reader born AFTER its maker's death? Absorption never
            touches the conserved belief string (планка ВСТАВКИ-27); payload.belief is the
            maker's frozen snapshot.

          REFRESH (every tick a reader is present) — salience → salience0: a carrier with a
            live reader never falls silent (культура держится пересказом). Idempotent, not
            logged, replay-stable. Copying resets nothing extra — presence alone sustains."""
        bycell = self._readable_bycell()
        if not bycell:
            return
        for a in pop_sorted:
            here = bycell.get((a.i, a.j))
            if not here:
                continue
            seen = self._read_seen.setdefault(a.oid, set())
            for art in sorted(here, key=lambda ar: ar.aid):
                art.salience = self.salience0          # REFRESH: presence keeps it loud
                if art.aid in seen:
                    continue
                seen.add(art.aid)                      # READ: first contact
                m = art.payload.get("method_level", 0)
                if m > self.known_method.get(a.oid, 0):
                    self.known_method[a.oid] = m
                self.reads.append((t, art.aid, a.oid, m, art.maker_oid, art.born_t))
                world.log.emit(t, "artifact_read", "individual", where=(a.i, a.j),
                               actor=a.oid, data={"aid": art.aid, "method": m,
                                                  "maker": art.maker_oid, "born_t": art.born_t})

    # ---- COPYING: mint an IMPROVED copy on a readable carrier (ratchet) --- #
    def _copying(self, world, pop_sorted, t):
        """An eligible pawn (fat, settled — the same write gate) standing on a readable
        carrier mints a NEW vessel carrying method = max(what it read, what it carries) + 1
        — copying-WITH-IMPROVEMENT (Тэйнтер/Бозеруп ratchet: complexity climbs one step
        each time meaning is re-inscribed). The copy costs body→mass exactly like an
        original (invariant intact); minting resets dwell, so the copy-rate is ~1/write_stasis
        — the knob HF2 turns against the two decay clocks. Meaning thus replicates on a
        material substrate: a carrier lineage deepens only while fat, settled readers keep
        re-inscribing it; let them thin, and method freezes at its last copied depth while
        salience decays the carriers to silent ruins."""
        bycell = self._readable_bycell()
        if not bycell:
            return
        for a in pop_sorted:
            here = bycell.get((a.i, a.j))
            if not here or not self._can_write(a):
                continue
            src = max(here, key=lambda ar: (ar.payload.get("method_level", 0), ar.aid))
            base = max(self.known_method.get(a.oid, 0), src.payload.get("method_level", 0))
            new_method = base + 1                      # ratchet: an improved re-inscription
            art = self._mint(world, a, new_method, t, is_copy=True)
            self.copies.append((t, art.aid, a.oid, src.payload.get("method_level", 0), new_method))

    # ==================== VITOK 2: store + capital ========================= #
    def _access_ok(self, world, art, a, mode) -> bool:
        """Deterministic access filter — the experimental axis of HG1/HG3:
        open  — anyone present may use the object (a commons);
        owner — only the TERRITORIAL owner of the cell it stands on (a locked barn;
                _cell_owner is the full territorial map, the honest class base);
        maker — only the author (a private hoard)."""
        if mode == "open":
            return True
        if mode == "maker":
            return art.maker_oid == a.oid
        if mode == "owner":
            return world._cell_owner.get((art.i, art.j)) == a.oid
        return False

    def _mint_object(self, world, a, kind, stake, t, ev):
        """Freeze `stake` of body into a semantically MUTE object (store/capital):
        payload empty, salience 0.0 — matter without meaning. The same body→mass
        transfer as a vessel mint; resets dwell (one mint per tick, cadence
        ~1/write_stasis). The invariant holds by construction."""
        a.body -= stake                            # MASS leaves the body...
        art = Artifact(aid=self._next_aid, i=a.i, j=a.j, mass=stake,
                       payload={}, salience=0.0, maker_oid=a.oid, born_t=t, kind=kind)
        self._next_aid += 1
        self.artifacts.append(art)
        self._dwell[a.oid] = ((a.i, a.j), 0)
        world.log.emit(t, ev, "individual", where=(a.i, a.j), actor=a.oid, dm=-stake,
                       data={"aid": art.aid, "stake": round(stake, 6)})
        return art

    # ---- CAPITALIZING: the richest freeze a TOOL (body → mass) ------------ #
    def _capitalizing(self, world, pop_sorted, t):
        """A settled pawn rich enough that capital_stake leaves it above
        CAPITAL_BODY_FLOOR (2·REPRO — the richest stratum only) mints ONE capital on a
        cell that has none: past labour frozen into a productivity tool. One live tool
        per cell (a second mill adds nothing; prevents unbounded stacking)."""
        if not self.capital_on:
            return
        has_cap = {(art.i, art.j) for art in self.artifacts if art.kind == "capital"}
        for a in pop_sorted:
            if (a.i, a.j) in has_cap:
                continue
            if self._dwell.get(a.oid, ((a.i, a.j), 0))[1] < self.write_stasis:
                continue
            if a.body - self.capital_stake < CAPITAL_BODY_FLOOR:
                continue
            art = self._mint_object(world, a, "capital", self.capital_stake, t,
                                    "artifact_capital")
            self.capitals.append((t, art.aid, a.oid, (a.i, a.j), self.capital_stake))
            has_cap.add((a.i, a.j))

    # ---- STORING: the rich lay a SURPLUS by (body → mass) ----------------- #
    def _storing(self, world, pop_sorted, t):
        """A settled pawn rich enough that store_stake leaves it above STORE_BODY_FLOOR
        (1.5·REPRO — a surplus beyond reproduction) lays a store on its cell. Stores
        STACK (a granary grows in heaps): blind accumulation, no intent — the vitok-1
        question again, now for pure matter."""
        if not self.store_on:
            return
        for a in pop_sorted:
            if self._dwell.get(a.oid, ((a.i, a.j), 0))[1] < self.write_stasis:
                continue
            if a.body - self.store_stake < STORE_BODY_FLOOR:
                continue
            art = self._mint_object(world, a, "store", self.store_stake, t,
                                    "artifact_store")
            self.stores.append((t, art.aid, a.oid, (a.i, a.j), self.store_stake))

    # ---- STORE DRAW: hunger unprints the reserve (mass → body) ------------ #
    def _store_draw(self, world, pop_sorted, t):
        """A HUNGRY pawn (body < store_draw_at) on a cell with an accessible store
        extracts min(store.mass, store_draw_rate) back into its body — the inverse of
        writing, a pure mass transfer (the invariant holds trivially). LOSSLESS BY
        DESIGN: canonical eating pays EFF=0.55 (metabolic cost of CONVERTING plant to
        body), but reservoir-to-reservoir TRANSFERS never pay it — writing (body→mass)
        was lossless in vitok 1, so un-printing (mass→body) is its exact lossless
        inverse: the stored mass was already metabolised once. Transfer ≠ conversion.
        Draws walk pawns
        in oid order and stores in aid order (oldest heap first); one draw per pawn per
        tick. A store drained to zero is swept by material decay the same tick (its
        remaining 0.0 goes to soil and the object is removed as a ruin)."""
        if not self.store_on:
            return
        bycell = {}
        for art in self.artifacts:
            if art.kind == "store" and art.mass > 0.0:
                bycell.setdefault((art.i, art.j), []).append(art)
        if not bycell:
            return
        for a in pop_sorted:
            if a.body >= self.store_draw_at:
                continue
            here = bycell.get((a.i, a.j))
            if not here:
                continue
            for art in sorted(here, key=lambda ar: ar.aid):
                if art.mass <= 0.0:
                    continue
                if not self._access_ok(world, art, a, self.store_access):
                    continue
                amount = min(art.mass, self.store_draw_rate)
                art.mass -= amount                 # MASS leaves the store...
                a.body += amount                   # ...and returns to the body
                self.draws.append((t, art.aid, a.oid, round(amount, 9), art.maker_oid))
                world.log.emit(t, "artifact_store_draw", "individual",
                               where=(a.i, a.j), actor=a.oid, dm=amount,
                               data={"aid": art.aid, "maker": art.maker_oid,
                                     "amount": round(amount, 6)})
                break                              # one draw per pawn per tick

    # ---- CAPITAL HARVEST: tool-gated extraction (soil → body) ------------- #
    def _capital_harvest(self, world, pop_sorted, t):
        """A pawn on a cell with an accessible capital extracts
        extra = min(soil[i,j], capital_rate · Σtool_mass) from the SOIL into its body.
        THE INVARIANT SUBTLETY (the sharpest gate of vitok 2): capital NEVER creates
        mass — it opens a reservoir (soil) that the canonical eat (which grazes PLANT)
        cannot reach: irrigation/deep tillage. Lossless like every reservoir transfer
        (the EFF=0.55 toll is the metabolic price of the plant→body CONVERSION, not a
        tax on moving mass between reservoirs — same law as writing and drawing).
        Productivity is proportional to the
        tool's remaining mass (a worn mill grinds worse — material decay IS
        amortisation). Pawns are walked in oid order; each takes from what soil
        remains — deterministic contention."""
        if not self.capital_on:
            return
        bycell = {}
        for art in self.artifacts:
            if art.kind == "capital" and art.mass > 0.0:
                bycell.setdefault((art.i, art.j), []).append(art)
        if not bycell:
            return
        for a in pop_sorted:
            here = bycell.get((a.i, a.j))
            if not here:
                continue
            cap_mass = sum(ar.mass for ar in here
                           if self._access_ok(world, ar, a, self.capital_access))
            if cap_mass <= 0.0:
                continue
            extra = min(float(world.soil[a.i, a.j]), self.capital_rate * cap_mass)
            if extra <= 0.0:
                continue
            world.soil[a.i, a.j] -= extra          # MASS leaves the soil...
            a.body += extra                        # ...through the tool, into the body
            self.boosts.append((t, a.oid, (a.i, a.j), round(extra, 9),
                                round(cap_mass, 9)))
            world.log.emit(t, "artifact_capital_boost", "individual",
                           where=(a.i, a.j), actor=a.oid, dm=extra,
                           data={"cap_mass": round(cap_mass, 6),
                                 "extra": round(extra, 6)})

    # ---- MATERIAL decay: mass → soil (ruins to ground; conserved) --------- #
    def _material_decay(self, world, t):
        """Each tick d = mat_decay·mass returns to world.soil[i,j]. Mass changes form; the
        invariant holds exactly. When an artifact's mass falls below EPS it has fully
        crumbled: the remainder goes to soil and the object is removed (a nameless ruin)."""
        EPS = 1e-12
        survivors = []
        for art in self.artifacts:
            rate = self.mat_decay * KIND_MAT_DECAY.get(art.kind, 1.0)
            d = rate * art.mass
            if art.mass - d <= EPS:
                # fully decayed this tick: return ALL remaining mass, drop the object
                world.soil[art.i, art.j] += art.mass
                self.ruins.append((t, art.aid, (art.i, art.j), round(art.mass, 9)))
                world.log.emit(t, "artifact_ruin", "individual", where=(art.i, art.j),
                               actor=art.maker_oid, dm=art.mass, data={"aid": art.aid})
                continue
            art.mass -= d
            world.soil[art.i, art.j] += d          # ruins → soil, mass conserved
            survivors.append(art)
        self.artifacts = survivors

    # ---- SEMANTIC decay: salience → 0 (forgetting; NO mass touched) ------- #
    def _semantic_decay(self):
        """salience ← salience·(1−sem_decay), toward zero. Below read_threshold the object
        still stands (mass intact) but is no longer read. Copying (above) is the only
        thing that resets it — the meaning-vs-matter divergence made literal."""
        f = 1.0 - self.sem_decay
        for art in self.artifacts:
            art.salience *= f

    # ---- fingerprint contribution (empty when OFF => canon-identical) ----- #
    def fingerprint_blob(self) -> bytes:
        if not self.on:
            return b""
        parts = []
        for art in sorted(self.artifacts, key=lambda a: a.aid):
            term = (f"{art.aid}:{art.i},{art.j}:{art.mass:.9f}:"
                    f"{art.payload.get('method_level', 0)}:{art.salience:.9f}:"
                    f"{art.maker_oid}:{art.born_t}")
            # vitok 2: kind enters the blob ONLY for non-vessel objects — a vessel term
            # is byte-identical to vitok 1, so the MF-replay anchor (48d9729d...) stands.
            if art.kind != "vessel":
                term += f":{art.kind}"
            parts.append(term)
        km = ";".join(f"{o}:{self.known_method[o]}" for o in sorted(self.known_method))
        return ("||ARTIFACT||" + "#".join(parts) + "||KM||" + km).encode()

    # ---- metrics for HF1–HF3 (read-only; never touch mass) ---------------- #
    def carried_max(self) -> int:
        return max(self.known_method.values(), default=0)

    def live_method_share(self) -> float:
        """Fraction of living carriers holding method_level >= 1 — proxy for how far
        knowledge has spread beyond its origin (HF2 surface)."""
        if not self.known_method:
            return 0.0
        held = sum(1 for m in self.known_method.values() if m >= 1)
        return held / len(self.known_method)
