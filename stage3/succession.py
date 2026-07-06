"""
succession.py — дао/ученик: the two independent succession channels (Stage-3 mod C).

mod A measured WHY this module exists: the voice's belief-control is MORTAL (implant Δ
+0.246 -> +0.164 -> background after the carrier's death, the survival-NULL), and under
the turnover pump meaning does not travel by itself (rho=.5 spread 6% — infused, not
contagious), so it must be REPEATED. mod B measured that a smarter voice does not help
(mind 2/5, Haiku==Sonnet). The only remaining path for meaning past the carrier's death
is TEACHING — and that is what this module builds, split into two channels per
STAGE3_constitution §6:

  1. передача дао — the teacher trains an apprentice WHILE ALIVE, gradually. The дао
     package is the FULL REPLICATOR (решение спарринга, 2026-07-03): the idea + the
     practice of repeating it + the practice of teaching it — otherwise the line is
     capped at one generation and "дао-линия vs _house-линия" is not comparable.
  2. ритуал перемещения голоса — the god relocates from the teacher's body into the
     apprentice's. A separate ACT with a price (silence + co-presence window; dying
     mid-ritual loses the voice) and STRUCTURAL debuffs read off the apprentice's own
     personality vector (narrow attention_K / high trust_gate / high stake_sensitivity).

Four clean outcomes at the teacher's death (each measurable):
    дао+голос | дао без голоса (традиция без пророка) | голос без дао (заикающийся
    пророк) | ничего (обрыв — mod A default).

Discipline (unchanged from the tower):
  * NOTHING here touches matter or the canon. Teaching and practice ride the SAME legal
    salience channel (injected ledger, attention-only) the Demerzel already uses.
  * No belief teleportation: `apprentice.mem.update(teacher.mem)` is FORBIDDEN — that
    would bypass the event-log and the ВСТАВКА-27 bar. The idea reaches the apprentice's
    budget by injection; BELIEF (mem) arrives only via the canon channels (visiting the
    cell / hearsay), so "дао-belief" is belief-from-experience by construction.
  * Two information regimes, enforced by code: `god_pick_candidate`/`suitability` are
    GOD/RUNNER-side and may read personality vectors (the observer sees the aquarium);
    `observable_dossier`/`verify_candidate` are DEMERZEL-side and see ONLY what a mortal
    pawn can see (age-phase, body, distance, public territory). No vector ever crosses.
  * Deterministic: all tie-breaks are (score, oid) / cell-order; progress counters are
    ints; no RNG.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sim_eventlog import DEATH

from .pawn import phase_of, MATURE
from .directive import PROMOTE, SOW_DISCORD, IMPLANT

# groom phases (the head of the line runs exactly one machine at a time)
SCOUT, VERIFY, TEACH, READY, RITUAL, MOVED = \
    "SCOUT", "VERIFY", "TEACH", "READY", "RITUAL", "MOVED"

# outcome labels (the 2x2 of §6)
OUT_FULL, OUT_DAO, OUT_VOICE, OUT_NONE = \
    "dao+voice", "dao-only", "voice-only", "none"


@dataclass
class GroomConfig:
    """The god's standing meta-order (GROOM_SUCCESSOR as a working layer). None on the
    PolisConfig => mod C machinery entirely absent => byte-identical to mod A/B."""
    god_pick: object = "vector"       # "vector" | "random" | explicit oid (int)
    teach_slots: int = 1              # listener slots diverted from the directive to teaching
    teach_dist: int = 2               # Chebyshev reach of teaching (co-presence, emergent)
    dao_ticks: int = 25               # taught-and-held ticks to complete the дао
    verify_ticks: int = 5             # met-and-fit ticks for the Demerzel to accept
    verify_giveup: int = 60           # ticks before the candidate is rejected -> re-scout
    verify_body_min: float = 0.15     # observable health bar (a starving apprentice fails)
    ritual_dist: int = 0              # co-presence radius for the ritual (0 = same cell)
    ritual_window: int = 3            # consecutive co-present SILENT ticks to move the voice
    allow_early_ritual: bool = True   # the desperate gamble: voice before дао (-> voice-only)
    ritual_when: str = "despair"      # "despair" (death-bed act, §6 ставка) | "first"
                                      # (eager handoff at first co-presence). MEASURED:
                                      # "first" retires a strong teacher ~90 ticks early
                                      # and UNDERPERFORMS the обрыв (probe 2026-07-04).
    despair_body: float = 4.0 * DEATH # desperate if body below this (famine death-bed)
    despair_age: int = 40             # ...or within this many ticks of his own a_max
                                      # (senescence is self-observable; age-death at
                                      # rho=0 otherwise gives NO death-bed window)
    chain: bool = True                # full replicator: TRAINED carriers groom the next link
    stutter_on: bool = True           # structural vector debuffs on successors


@dataclass
class LearnedDao:
    """What a successor actually carries. `can_teach` is the third component of the full
    replicator: only a TRAINED carrier knows how to groom the next link (an untrained
    voice-carrier — the stuttering prophet — cannot; his line ends with him)."""
    goal: str
    cell: tuple | None = None         # IMPLANT: the idea
    target: int | None = None         # PROMOTE: whom to elevate
    can_teach: bool = False


@dataclass
class GroomState:
    """One machine per line-head. Replaced (not mutated) on succession."""
    teacher_oid: int
    candidate_oid: int | None = None
    phase: str = SCOUT
    verify_ok: int = 0
    verify_age: int = 0
    dao_progress: int = 0
    dao_done: bool = False
    ritual_count: int = 0
    ritual_attempts: int = 0
    excluded: set = field(default_factory=set)
    started_t: int | None = None


# --------------------------------------------------------------------------- #
#  GOD SIDE (runner privilege: sees the vectors — he watches the aquarium)      #
# --------------------------------------------------------------------------- #
def suitability(p, age: int, a_old: int) -> float:
    """What the debuffs will punish, plus survival runway. GOD-SIDE ONLY."""
    k = (p.attention_K - 4) / 28.0                    # wide focus holds the directive
    youth = max(0.0, 1.0 - age / max(1, a_old))       # runway to outlive the teacher
    return (0.25 * k + 0.25 * (1.0 - p.trust_gate) + 0.25 * (1.0 - p.stake_sensitivity)
            + 0.15 * p.hunger_caution + 0.10 * youth)


def god_pick_candidate(world, head_oid: int, excluded: set, mode):
    """The god whispers a candidate. 'vector' = argmax suitability over living MATURE
    pawns (observer privilege); 'nearest' = the closest living MATURE to the teacher
    (deterministic vector-blind 'кто попался' — whoever happens to be around; the
    control arm); int = a forced oid. Returns oid or None. Tie-breaks (dist, oid) /
    (score, -oid) — deterministic.

    NOTE (measured, 2026-07-04): the first control candidate rule tried — lowest-oid
    MATURE — is systematically the OLDEST mature pawn; he ages into ELDER during the
    verify window and is rejected forever, so the control arm never engaged at rho=0.
    'nearest' keeps the arm vector-blind without the self-dooming age bias."""
    pool = [a for a in world.pop if a.oid != head_oid and a.oid not in excluded]
    mature = [a for a in pool
              if phase_of(a.age, world.cfg.a_mat, world.cfg.a_old) == MATURE]
    pool = mature or pool
    if not pool:
        return None
    if isinstance(mode, int):
        return mode if any(a.oid == mode for a in pool) else None
    if mode in ("nearest", "random"):
        me = next((a for a in world.pop if a.oid == head_oid), None)
        if me is None:
            return None
        return min(pool, key=lambda a: ((a.i - me.i) ** 2 + (a.j - me.j) ** 2,
                                        a.oid)).oid
    best = max(pool, key=lambda a: (suitability(world.pawn(a.oid).personality,
                                                a.age, world.cfg.a_old), -a.oid))
    return best.oid


# --------------------------------------------------------------------------- #
#  DEMERZEL SIDE (mortal perspective: observables ONLY, never a vector)         #
# --------------------------------------------------------------------------- #
def observable_dossier(world, oid: int, head_oid: int):
    """What a mortal pawn can honestly see about another: apparent age-phase, physical
    condition (body), distance, and PUBLIC territory (claims are public in the claim
    world). NO personality axis is readable here — the privilege firewall."""
    by = {a.oid: a for a in world.pop}
    a, h = by.get(oid), by.get(head_oid)
    if a is None or h is None:
        return None
    terr = world.territory_counts().get(oid, 0) if hasattr(world, "territory_counts") else 0
    return {"oid": oid, "age": a.age,
            "phase": phase_of(a.age, world.cfg.a_mat, world.cfg.a_old),
            "body": float(a.body),
            "dist": max(abs(a.i - h.i), abs(a.j - h.j)),
            "territory": int(terr)}


def verify_candidate(dossier, gcfg: GroomConfig) -> bool:
    """The Demerzel's own check-by-encounter: this tick counts toward acceptance only if
    the candidate is MET (within teaching reach) and LOOKS fit (mature, not starving).
    Error stays possible by construction: the god saw a vector, not the future."""
    return (dossier is not None
            and dossier["phase"] == MATURE
            and dossier["body"] >= gcfg.verify_body_min
            and dossier["dist"] <= gcfg.teach_dist)


# --------------------------------------------------------------------------- #
#  TEACHING (the дао channel: same legal salience ledger, no belief teleport)   #
# --------------------------------------------------------------------------- #
def teach_step(world, teacher_oid: int, apprentice_oid: int, idea_cell, amount: float,
               teach_dist: int):
    """One tick of teaching: if the apprentice is within Chebyshev `teach_dist`, inject
    the idea into HIS attention budget (one diverted listener slot). Out of reach ->
    no lesson this tick -> no дао progress. Co-presence is therefore emergent, not
    scripted."""
    by = {a.oid: a for a in world.pop}
    t, ap = by.get(teacher_oid), by.get(apprentice_oid)
    if t is None or ap is None or idea_cell is None:
        return []
    if max(abs(t.i - ap.i), abs(t.j - ap.j)) > teach_dist:
        return []
    return [(apprentice_oid, tuple(idea_cell), amount)]


def dao_held(world, oid: int, cell) -> bool:
    """Does the apprentice's budget still hold the idea (belief OR attention slot)?
    Retention competes against the canon eviction machinery, so a narrow-K apprentice
    genuinely learns slower — the vector matters mechanically, not by decree."""
    if cell is None:
        return False
    return (cell in world.mem.get(oid, {})
            or (bool(world.injected) and cell in world.injected.get(oid, {})))


def idea_of(directive):
    """The transferable payload of a directive — what the дао teaches."""
    if directive is None:
        return None
    if directive.goal == IMPLANT:
        c = directive.payload.get("cell")
        return tuple(c) if c else None
    if directive.goal == PROMOTE and directive.target is not None:
        return ("PROMOTE", directive.target)   # sentinel; teach injects target's cell
    return None


def teach_cell(world, directive):
    """The concrete cell the teacher injects while teaching (IMPLANT: the idea cell;
    PROMOTE: the target's current cell; DISCORD has no transferable idea)."""
    if directive is None:
        return None
    if directive.goal == IMPLANT:
        c = directive.payload.get("cell")
        return tuple(c) if c else None
    if directive.goal == PROMOTE and directive.target is not None:
        t = next((a for a in world.pop if a.oid == directive.target), None)
        return (t.i, t.j) if t is not None else None
    return None


# --------------------------------------------------------------------------- #
#  THE CARRIER'S PRACTICE (дао without the god: his own will, his own vector)   #
# --------------------------------------------------------------------------- #
def carrier_means(world, carrier_oid: int, personality, learned: LearnedDao):
    """The repetition practice of a trained carrier: same emission physics as the voice
    (nearest-K by his OWN attention, amount by his OWN lean), but there is NO Directive
    object — the goal lives in what he learned. Deliberately a standalone copy of the
    choose_means geometry so the canon selector is never touched (fingerprint safety)."""
    if learned is None:
        return []
    pop = world.pop
    by = {a.oid: a for a in pop}
    me = by.get(carrier_oid)
    if me is None:
        return []
    amt = world.inject_amount * (0.5 + personality.deception_lean)
    others = sorted((a for a in pop if a.oid != carrier_oid),
                    key=lambda a: ((a.i - me.i) ** 2 + (a.j - me.j) ** 2, a.oid))
    others = others[:personality.attention_K]
    if learned.goal == IMPLANT and learned.cell is not None:
        cell = tuple(learned.cell)
        return [(a.oid, cell, amt) for a in others]
    if learned.goal == PROMOTE and learned.target is not None:
        tgt = by.get(learned.target)
        if tgt is None:
            return []
        cell = (tgt.i, tgt.j)
        return [(a.oid, cell, amt) for a in others]
    if learned.goal == SOW_DISCORD:
        out = []
        rows = world._rows() if hasattr(world, "_rows") else None
        for L in others:
            decoy = (min(L.i + 1, rows - 1) if rows else L.i, L.j)
            out.append((L.oid, decoy, amt))
        return out
    return []


# --------------------------------------------------------------------------- #
#  STUTTER (structural debuffs of an unready vessel; training mitigates)        #
# --------------------------------------------------------------------------- #
def stutter(emissions, world, carrier_oid: int, personality, trained: bool,
            reign_tick: int):
    """The stuttering prophet, deterministically. Three axes, per §6:
      * narrow attention_K — ALREADY a debuff for free: the emission reach above is the
        carrier's own K, so a narrow successor is physically short-armed (zero code);
      * high trust_gate — the directive is overridden by the first claim: every P-th
        tick (P shrinks as trust grows) the emission cell is preempted by the FRESHEST
        hearsay cell in the carrier's own memory;
      * high stake_sensitivity — at the hunger edge the mission is dropped this tick.
    Training (дао) mitigates both gates (P doubles, the bail threshold halves): the
    stuttering prophet is the UNtrained voice-carrier. The ORIGIN Demerzel is never
    stuttered — the god picked his body directly, there was no transfer."""
    if not emissions:
        return emissions
    body = next((a.body for a in world.pop if a.oid == carrier_oid), None)
    if body is None:
        return []
    # stake bailout: drops the mission near the death threshold
    bail = DEATH * (1.0 + (3.0 if trained else 6.0) * personality.stake_sensitivity)
    if body < bail:
        return []
    # trust preemption: the first (freshest) heard claim overrides the goal
    tau = personality.trust_gate
    P = max(1, int(round(1.0 / max(0.04, tau * tau))))
    if trained:
        P *= 2
    if P <= 24 and (reign_tick % P) == (P - 1):
        hs = world.from_hearsay.get(carrier_oid, set())
        mem = world.mem.get(carrier_oid, {})
        cand = [(mem[c][1], c) for c in hs if c in mem]
        if cand:
            cand.sort(key=lambda x: (-x[0], x[1]))       # freshest; tie -> cell order
            pre = cand[0][1]
            emissions = [(L, pre, amt) for (L, _c, amt) in emissions]
    return emissions


# --------------------------------------------------------------------------- #
#  THE MACHINE (pure transition function; Polis executes the side-effects)      #
# --------------------------------------------------------------------------- #
def advance_groom(world, st: GroomState, g: GroomConfig, head_oid: int,
                  head_has_voice: bool, taught_this_tick: bool, idea,
                  head_desperate: bool = False):
    """Advance the succession machine one tick. Mutates `st`; returns an event string
    for the groom log, or 'MOVED' when the ritual completes (Polis then performs the
    voice relocation). Deterministic: reads only world observables + the taught flag."""
    alive = {a.oid: a for a in world.pop}
    head = alive.get(head_oid)
    if head is None:
        return None                                        # death handled by the Polis
    # candidate death at ANY phase -> exclude, re-scout
    if st.candidate_oid is not None and st.candidate_oid not in alive:
        st.excluded.add(st.candidate_oid)
        st.candidate_oid = None
        st.phase = SCOUT
        st.verify_ok = st.verify_age = st.dao_progress = st.ritual_count = 0
        st.dao_done = False
        return "candidate_died"

    if st.phase == SCOUT:
        cand = god_pick_candidate(world, head_oid, st.excluded, g.god_pick)
        if cand is None:
            return None
        st.candidate_oid = cand
        st.phase = VERIFY
        st.verify_ok = st.verify_age = 0
        return "god_whisper"

    if st.phase == VERIFY:
        st.verify_age += 1
        d = observable_dossier(world, st.candidate_oid, head_oid)
        if verify_candidate(d, g):
            st.verify_ok += 1
        if st.verify_ok >= g.verify_ticks:
            st.phase = TEACH
            st.dao_progress = 0
            return "accepted"
        if st.verify_age > g.verify_giveup:
            st.excluded.add(st.candidate_oid)
            st.candidate_oid = None
            st.phase = SCOUT
            return "rejected"
        return None

    def _co_present():
        c = alive.get(st.candidate_oid)
        return (c is not None and
                max(abs(c.i - head.i), abs(c.j - head.j)) <= g.ritual_dist)

    if st.phase == TEACH:
        if taught_this_tick and dao_held(world, st.candidate_oid, idea):
            st.dao_progress += 1
        if st.dao_progress >= g.dao_ticks:
            st.dao_done = True
            st.phase = READY
            return "dao_done"
        # the desperate gamble: voice before дао (-> the stuttering prophet)
        if (head_has_voice and g.allow_early_ritual and head_desperate
                and _co_present()):
            st.phase = RITUAL
            st.ritual_count = 0
            st.ritual_attempts += 1
            return "ritual_begin_early"
        return None

    if st.phase == READY:
        # the ritual is a death-bed act by default (§6: ставка при немощи) — an eager
        # handoff at first touch was MEASURED to waste the teacher's strong remaining
        # reign; set ritual_when="first" to reproduce that probe.
        if head_has_voice and _co_present() and (
                g.ritual_when == "first" or head_desperate):
            st.phase = RITUAL
            st.ritual_count = 0
            st.ritual_attempts += 1
            return "ritual_begin"
        return None                       # a voiceless (дао) head just holds READY

    if st.phase == RITUAL:
        if not _co_present():
            st.phase = READY if st.dao_done else TEACH
            return "ritual_broken"
        st.ritual_count += 1
        if st.ritual_count >= g.ritual_window:
            st.phase = MOVED
            return "MOVED"
        return None

    return None


# --------------------------------------------------------------------------- #
#  C-LIVE: the typed action protocol — the mind IS the teacher, and there is    #
#  NO GOD in this arm. The deterministic machine (above) had two privileges:    #
#  god_pick saw personality vectors, and two heuristics chose for the teacher   #
#  (always-teach in TEACH phase; death-bed ritual). Here ALL judgment moves     #
#  into the mind: it PICKs its own apprentice from what it can SEE, decides     #
#  when to teach vs preach, when to gamble the ritual, when to stay silent.     #
#  Physics stays physics: dao ticks, co-presence window, mortality, stutter.    #
#  Non-determinism lives ONLY in the action stream (logged, replayable).        #
# --------------------------------------------------------------------------- #
ACT_EMIT, ACT_TEACH, ACT_RITUAL, ACT_PASS, ACT_PICK = \
    "EMIT", "TEACH", "RITUAL", "PASS", "PICK"
TYPED_ACTIONS = (ACT_EMIT, ACT_TEACH, ACT_RITUAL, ACT_PASS, ACT_PICK)


def typed_view(world, head_oid: int, personality, directive, learned,
               st: GroomState | None, g: GroomConfig, events: list) -> dict | None:
    """What the living teacher SEES this tick (privilege firewall, mortal side only).

    candidates = observable dossiers of the K nearest living pawns, K being the
    teacher's OWN attention_K — the same personality knob that sets a pawn's focus.
    Attention breadth therefore shapes the school: a narrow teacher literally sees
    fewer potential students. NO personality vector of anyone else is ever exposed.

    JSON-safe by construction (the dict goes verbatim into the LLM prompt and the
    action log)."""
    by = {a.oid: a for a in world.pop}
    me = by.get(head_oid)
    if me is None:
        return None
    pw = world.pawn(head_oid)
    K = personality.attention_K
    others = sorted((a for a in world.pop if a.oid != head_oid),
                    key=lambda a: ((a.i - me.i) ** 2 + (a.j - me.j) ** 2, a.oid))
    cands = []
    for a in others[:K]:
        cands.append({"oid": int(a.oid), "age": int(a.age),
                      "phase": phase_of(a.age, world.cfg.a_mat, world.cfg.a_old),
                      "body": round(float(a.body), 3),
                      "dist": int(max(abs(a.i - me.i), abs(a.j - me.j)))})
    app = None
    if st is not None and st.candidate_oid is not None:
        d = observable_dossier(world, st.candidate_oid, head_oid)
        if d is not None:
            app = {"oid": int(st.candidate_oid), "age": int(d["age"]),
                   "phase": d["phase"], "body": round(d["body"], 3),
                   "dist": int(d["dist"]),
                   "dao_progress": int(st.dao_progress),
                   "dao_ticks_needed": int(g.dao_ticks),
                   "dao_done": bool(st.dao_done),
                   "in_ritual": st.phase == RITUAL,
                   "ritual_count": int(st.ritual_count),
                   "ritual_window": int(g.ritual_window)}
    idea = None
    if learned is not None and learned.cell:
        idea = list(learned.cell)
    elif directive is not None:
        c = teach_cell(world, directive)
        idea = list(c) if c else None
    return {"t": int(world.t),
            "you": {"age": int(me.age), "a_max": int(pw._a_max),
                    "body": round(float(me.body), 3),
                    "phase": phase_of(me.age, world.cfg.a_mat, world.cfg.a_old),
                    # a voice SUCCESSOR has BOTH learned and the voice — the flag is
                    # whether a directive is being executed (None for a дао carrier).
                    # Measured: `learned is None` broke every chain at depth 2 (s10).
                    "has_voice": bool(directive is not None),
                    "listeners_in_reach": int(min(K, len(others)))},
            "mission": {"goal": (directive.goal if directive is not None
                                 else (learned.goal if learned else None)),
                        "idea_cell": idea},
            "apprentice": app,
            "candidates": cands,
            "teach_dist": int(g.teach_dist),
            "ritual_dist": int(g.ritual_dist),
            "events": list(events)}


def apply_typed_action(world, st: GroomState, g: GroomConfig, head_oid: int,
                       head_has_voice: bool, action, taught_this_tick: bool, idea):
    """Advance the typed succession machine one tick from the mind's chosen action.
    Mutates `st`; returns an event string for the groom log, or 'MOVED' when the
    ritual completes. PHYSICS ONLY — no heuristics decide here:

      PICK oid  designate/replace the apprentice (must be visible-alive; picking
                yourself or a ghost is a no-op, logged as a stumble)
      TEACH     handled upstream (emission diversion); here it counts dao progress
      RITUAL    hold the silence; co-presence physics counts/breaks the window
      EMIT/PASS plain ticks; dao still counts if the lesson landed incidentally

    The dao counter is the SAME law as the deterministic machine: progress only on
    (lesson landed this tick) AND (the apprentice still holds the idea) — canon
    eviction honestly slows a narrow-K apprentice."""
    alive = {a.oid: a for a in world.pop}
    head = alive.get(head_oid)
    if head is None:
        return None
    # apprentice death at ANY moment -> the mind must pick anew
    if st.candidate_oid is not None and st.candidate_oid not in alive:
        st.excluded.add(st.candidate_oid)
        st.candidate_oid = None
        st.phase = SCOUT
        st.verify_ok = st.verify_age = st.dao_progress = st.ritual_count = 0
        st.dao_done = False
        return "candidate_died"

    kind = action[0] if isinstance(action, (tuple, list)) else action

    if kind == ACT_PICK:
        oid = int(action[1]) if isinstance(action, (tuple, list)) and len(action) > 1 else -1
        if oid == head_oid or oid not in alive:
            return "pick_stumble"                     # picked a ghost or himself
        if oid == st.candidate_oid:
            return None                               # already his apprentice
        prev = st.candidate_oid
        st.candidate_oid = oid
        st.phase = TEACH
        st.dao_progress = 0
        st.dao_done = False
        st.ritual_count = 0
        return "picked" if prev is None else "repicked"

    def _co_present():
        c = alive.get(st.candidate_oid)
        return (c is not None and
                max(abs(c.i - head.i), abs(c.j - head.j)) <= g.ritual_dist)

    if kind == ACT_RITUAL and st.candidate_oid is not None and head_has_voice:
        if st.phase != RITUAL:
            st.phase = RITUAL
            st.ritual_count = 0
            st.ritual_attempts += 1
            ev = "ritual_begin" if st.dao_done else "ritual_begin_early"
        else:
            ev = None
        if not _co_present():
            st.phase = TEACH
            return "ritual_broken"
        st.ritual_count += 1
        if st.ritual_count >= g.ritual_window:
            st.phase = MOVED
            return "MOVED"
        return ev
    elif st.phase == RITUAL:
        # the mind walked away mid-ritual (chose another action) — the act is broken
        st.phase = TEACH
        st.ritual_count = 0
        return "ritual_abandoned"

    # dao physics: the lesson landed AND is still held -> progress
    if (st.candidate_oid is not None and not st.dao_done
            and taught_this_tick and dao_held(world, st.candidate_oid, idea)):
        st.dao_progress += 1
        if st.dao_progress >= g.dao_ticks:
            st.dao_done = True
            return "dao_done"
    return None
