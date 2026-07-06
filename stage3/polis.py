"""
polis.py — the Polis: the unit of play, and the t_awaken seam for Demerzel (mod A).

A Polis is a resource-bounded community living on a tower world. We inherit
AppropriationWorld (module 23) so the Polis has an ECONOMY — a leader can be an owner, and
the god's directive touches the turnover kinetics, not just belief: the Polis is a
microcosm of the whole tower ("на казусах отрабатывают те же законы").

Anthropological start (not a number, an initial condition): the founders/claim machinery
of the tower already seeds a population; size is EMERGENT from the resource profile via
`eat<=avail/n` and turnover — there is NO hard "30" cap in code.

The Demerzel seam:
  - before `t_awaken` the Polis IS a plain AppropriationWorld run -> state_fingerprint ==
    that world's canon. t_awaken=inf (default) => byte-identical to the tower.
  - at `t_awaken` one living pawn (lowest-oid living non-owner by default, or a configured
    oid) becomes the Demerzel: it carries the Directive and, each subsequent step, emits
    salience into listeners' `injected` ledgers via the deterministic means-selector.
  - the voice uses the salience channel (injected ledger, attention-only, mass-neutral),
    so it can NEVER break conservation. injection_strength is 0 until awakening (canon),
    then set > 0 so the injected term actually biases perception.
  - Demerzel is MORTAL: if it dies (body<DEATH or age>=A_max), the voice goes silent and
    the Polis reverts to stochastic tower dynamics. The living window [issued_t, death_t]
    is recorded for attribution.

Deterministic; pure stdlib + numpy. Pi5/Win11 friendly.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from sim_eventlog import SEED
from sim_comm import DAYS
from sim_sphere import GRID_DIAG, CANON_COMM
from sim_salience import RAD, KK, LAG, FEW, W_INJ, AMT
from sim_appropriation import AppropriationWorld, appropriation_fingerprint, run_appropriation

from .personality import Personality, DEMAGOGUE, seed_personality, BASELINE
from .directive import Directive, choose_means, GROOM_SUCCESSOR
from .pawn import Pawn, A_MAT, A_OLD, A_MAX

# Demerzel longevity: order of a civilisational arc. First proxy = 20x normal ceiling
# (~6000 ticks); in practice the Polis is far shorter, so the Demerzel almost always
# outlives the оча́г — which is what we want. Calibrate to _house-line length in acceptance.
DEMERZEL_A_MAX = 20 * A_MAX


@dataclass
class PolisConfig:
    seed: int = SEED
    # substrate / economy
    appropriation: float = 0.5          # rho — the Polis has an economy
    owner_policy: str = "claim"         # emergent territory
    arena_side: int | None = 6          # box6 (bounded polygon)
    # voice of god
    t_awaken: int = 10 ** 9             # inf by default -> pure aquarium == canon
    demerzel_oid: int | None = None     # None -> lowest-oid living non-owner at t_awaken
    demerzel_personality: Personality = DEMAGOGUE
    demerzel_directive: Directive | None = None
    demerzel_a_max: int = DEMERZEL_A_MAX
    voice_strength: float = W_INJ       # injection_strength once awake (0 while asleep)
    inject_amount: float = AMT
    # mod B: mind policy (None -> mod A deterministic choose_means). replay_log: {t: emissions}
    # read from a prior LIVE run so the world replays byte-identically without calling the LLM.
    policy: object = None
    replay_log: dict = None
    # mod C (дао/ученик): the god's standing meta-order (GROOM_SUCCESSOR as a working
    # layer). None => the succession machinery is entirely absent => byte-identical to
    # mod A/B (gate C0). See stage3/succession.py.
    groom: object = None
    # C-LIVE (typed protocol): if set, actions are READ from this {t: action} log and
    # the policy is never called — the world replays byte-identically (non-determinism
    # lives ONLY in the action stream).
    replay_actions: dict = None
    # perception preset — MUST match the headline appropriation run so the sleeping Polis
    # is byte-identical (run_appropriation defaults to the salience preset RAD/KK/LAG,
    # NOT AppropriationWorld's bare defaults). radius=RAD(0.0), K=KK(8), lag=LAG(1).
    radius: float = RAD
    K: int | None = KK
    lag: int = LAG
    regime: str = "deceptive"
    target_policy: str = "decoy"
    # arc calibration (from baseline tower age distribution)
    a_mat: int = A_MAT
    a_old: int = A_OLD
    a_max: int = A_MAX
    days: int = DAYS


class Polis(AppropriationWorld):
    """AppropriationWorld plus a t_awaken Demerzel seam. Asleep (t < t_awaken or no
    directive) it is byte-identical to the parent AppropriationWorld."""

    def __init__(self, log, cfg: PolisConfig):
        self.cfg = cfg
        self._t_awaken = int(cfg.t_awaken)
        self._demerzel_oid = cfg.demerzel_oid
        self._demerzel_personality = cfg.demerzel_personality
        self._directive = cfg.demerzel_directive
        self._awake = False
        self._issued_t = None            # tick the voice actually began
        self._death_t = None             # tick the Demerzel died (voice silenced)
        self._voice_log = []             # attribution triples (directive, means, delta)
        self._pawns = {}                 # oid -> Pawn (thick view; lazily built)
        # mod B: pluggable mind policy + replay-from-log. policy=None -> mod A deterministic.
        self._policy = cfg.policy
        self._decision_log = {}          # t -> [(listener_oid, [i,j], amount), ...]  (for replay)
        self._replay_log = cfg.replay_log  # if given, decisions are READ from here (no LLM)
        # mod C (дао/ученик) state — inert when cfg.groom is None (gate C0):
        self._groom = None            # active GroomState (one machine per line head)
        self._voice_oid = None        # current voice holder (the origin, then successors)
        self._dao_carrier = None      # voiceless carrier of the practice (дао without god)
        self._learned = {}            # oid -> LearnedDao
        self._succ_reign = 0          # ticks under the current successor (stutter phase)
        self._depth = 0               # succession depth (0 = origin only)
        self._outcome = None          # the 2x2 label fixed at the FIRST succession point
        self._carriers = []           # (t, oid, kind, trained) — line history
        self._groom_log = []          # (t, event, data)
        self._line_death_t = None     # tick the LINE fell silent (no emitter left)
        # C-LIVE (typed protocol) state — inert unless the policy is typed:
        self._typed_log = {}          # t -> action (JSON-safe list) — the mind's diary
        self._typed_events = []       # events since the mind's last look (view feed)
        # start ASLEEP: injection_strength=0 so the injected term is inert => canon.
        # perception preset (radius/K/lag/regime/target_policy) MUST mirror the headline
        # appropriation run, else the sleeping Polis is not byte-identical to it.
        super().__init__(
            log, seed=cfg.seed, regime=cfg.regime, radius=cfg.radius, K=cfg.K, lag=cfg.lag,
            arena_side=cfg.arena_side, target_policy=cfg.target_policy,
            appropriation=cfg.appropriation, owner_policy=cfg.owner_policy,
            injection_strength=0.0, injectors=0, inject_amount=cfg.inject_amount,
        )

    # ---- pawn views (thick personalities, deterministic from oid) ---------- #
    def pawn(self, oid) -> Pawn:
        p = self._pawns.get(oid)
        if p is None:
            pers = (self._demerzel_personality if oid == self._demerzel_oid
                    else seed_personality(oid, base=BASELINE))
            amax = (self.cfg.demerzel_a_max if oid == self._demerzel_oid else self.cfg.a_max)
            p = Pawn(oid, pers, self.cfg.a_mat, self.cfg.a_old, amax)
            self._pawns[oid] = p
        return p

    def _rows(self):    # for directive means-selector (grid rows)
        from sim_comm import R
        return R

    # ---- the awakening: pick a living pawn to carry the voice -------------- #
    def _awaken(self):
        if self._demerzel_oid is None:
            owners = self.owner_ids()
            living = sorted(a.oid for a in self.pop if a.oid not in owners)
            if not living:
                living = sorted(a.oid for a in self.pop)
            if not living:
                return False
            self._demerzel_oid = living[0]
        # rebind the chosen pawn with the Demerzel personality + longevity
        self._pawns.pop(self._demerzel_oid, None)
        self._awake = True
        self._issued_t = self.t
        if self._directive is not None:
            self._directive.issued_t = self.t
            # PROMOTE with no explicit target: pick someone to elevate. Default = the
            # lowest-oid living owner other than the Demerzel (a would-be leader to back);
            # if no owners yet, the lowest-oid living non-Demerzel pawn.
            from .directive import PROMOTE as _PROMOTE
            if self._directive.goal == _PROMOTE and self._directive.target is None:
                owners = sorted(o for o in self.owner_ids() if o != self._demerzel_oid)
                if owners:
                    self._directive.target = owners[0]
                else:
                    cand = sorted(a.oid for a in self.pop if a.oid != self._demerzel_oid)
                    if cand:
                        self._directive.target = cand[0]
        # turn the voice ON: injected term now biases perception
        self.injection_strength = float(self.cfg.voice_strength)
        return True

    # ---- the step seam ----------------------------------------------------- #
    def step(self):
        super().step()                         # full tower + appropriation, unchanged
        if self.cfg.groom is None:
            self._step_voice_moda()            # mod A/B path, verbatim (gate C0)
        elif (getattr(self._policy, "typed", False)
              or self.cfg.replay_actions is not None):
            self._step_voice_typed()           # C-LIVE: the mind is the teacher
        else:
            self._step_voice_modc()            # mod C: дао/ученик succession layer

    def _step_voice_moda(self):
        # mortality check for an already-awake Demerzel
        if self._awake and self._death_t is None:
            dem = next((a for a in self.pop if a.oid == self._demerzel_oid), None)
            pw = self.pawn(self._demerzel_oid) if dem is not None else None
            if dem is None or (pw is not None and pw.is_dead_by_age(dem)):
                self._death_t = self.t
                self.injection_strength = 0.0  # voice silenced -> revert to stochastic
                return
        # awaken exactly at t_awaken
        if (not self._awake) and self.t >= self._t_awaken:
            if not self._awaken():
                return
        # emit the voice this tick. Source of the emissions, in priority order:
        #   1. replay_log (a prior LIVE run's logged decisions) -> world replays byte-identical
        #   2. policy.choose(...) (LLM or mock) -> LIVE decision, logged for later replay
        #   3. deterministic choose_means (mod A default, policy=None)
        if self._awake and self._death_t is None and self._directive is not None:
            if self._replay_log is not None and self.t in self._replay_log:
                emissions = [(oid, tuple(cell), amt)
                             for (oid, cell, amt) in self._replay_log[self.t]]
            elif self._policy is not None:
                emissions = self._policy.choose(self, self._demerzel_oid,
                                                self._demerzel_personality,
                                                self._directive, self._decision_log)
            else:
                emissions = choose_means(self, self._demerzel_oid,
                                         self._demerzel_personality, self._directive)
            # log the decision for replay (list form, JSON-safe: cell as [i,j])
            self._decision_log[self.t] = [(oid, [c[0], c[1]], amt)
                                          for (oid, c, amt) in emissions]
            for (listener_oid, cell, amount) in emissions:
                led = self.injected.setdefault(listener_oid, {})
                led[cell] = led.get(cell, 0.0) + amount
            # attribution triple: directive -> means (count/amt) -> world_delta (owner share)
            om_share = self._owner_share_now()
            self._voice_log.append((self.t, self._directive.goal,
                                    self._directive.target, len(emissions),
                                    round(om_share, 6)))


    # ---- mod C: дао/ученик — the succession layer (cfg.groom is not None) --- #
    def _step_voice_modc(self):
        """The mod C step: same voice physics, plus the succession machine. One-emitter
        invariant: at any tick at most ONE of {voice holder, дао carrier} emits. The
        substrate is never touched — teaching and practice ride the same legal salience
        ledger. See stage3/succession.py for the mechanics and the privilege firewall."""
        from .succession import GroomState, teach_cell, advance_groom
        g = self.cfg.groom
        # awaken exactly as mod A; arm the groom machine at the same tick
        if not self._awake:
            if self.t >= self._t_awaken:
                if not self._awaken():
                    return
                self._voice_oid = self._demerzel_oid
                self._groom = GroomState(teacher_oid=self._voice_oid, started_t=self.t)
                self._gev("groom_issued", {"teacher": self._voice_oid})
            else:
                return
        alive = {a.oid for a in self.pop}
        # deaths of carriers (voice or дао): outcome resolution + line bookkeeping
        self._resolve_deaths_modc(alive)
        # emissions from the single active emitter
        ems, taught, head, phase, kind = self._emit_modc(alive)
        if head is not None:
            self._decision_log[self.t] = [(oid, [c[0], c[1]], amt)
                                          for (oid, c, amt) in ems]
            for (listener_oid, cell, amount) in ems:
                led = self.injected.setdefault(listener_oid, {})
                led[cell] = led.get(cell, 0.0) + amount
            om_share = self._owner_share_now()
            goal = self._directive.goal if self._directive is not None else None
            tgt = self._directive.target if self._directive is not None else None
            self._voice_log.append((self.t, goal, tgt, len(ems),
                                    round(om_share, 6), head, phase, kind))
        # advance the machine (the taught flag is of THIS tick)
        st = self._groom
        if st is not None and head is not None and st.teacher_oid == head:
            if head == self._voice_oid:
                icell = teach_cell(self, self._directive)
            else:
                L = self._learned.get(head)
                icell = tuple(L.cell) if (L is not None and L.cell) else None
            hb = next((a for a in self.pop if a.oid == head), None)
            desperate = (hb is not None and
                         (hb.body < g.despair_body
                          or hb.age >= self.pawn(head)._a_max - g.despair_age))
            ev = advance_groom(self, st, g, head, head == self._voice_oid,
                               taught, icell, head_desperate=desperate)
            if ev == "MOVED":
                self._do_ritual_move(st)
            elif ev is not None:
                self._gev(ev, {"head": head, "cand": st.candidate_oid,
                               "dao": st.dao_progress, "phase": st.phase})
        # voice lifecycle: strength ON while an emitter exists, else the world is silent
        has_emitter = ((self._voice_oid is not None and self._voice_oid in alive)
                       or (self._dao_carrier is not None
                           and self._dao_carrier in alive))
        self.injection_strength = (float(self.cfg.voice_strength)
                                   if has_emitter else 0.0)
        if (self._line_death_t is None and self._issued_t is not None
                and not has_emitter):
            self._line_death_t = self.t

    def _resolve_deaths_modc(self, alive):
        """Carrier mortality, mod C semantics. The ORIGIN's death always closes the mod-A
        living window (attribution semantics unchanged). A dying voice holder LOSES the
        voice (it moves only by ritual) — but a TRAINED heir inherits the дао; a dying
        дао carrier passes the practice only to his own trained heir. The 2x2 outcome is
        fixed at the FIRST succession point (MOVED or unmoved death)."""
        from .succession import OUT_DAO, OUT_NONE
        # (a) origin body: closes the mod-A living window whenever it dies
        if self._awake and self._death_t is None:
            dem = next((a for a in self.pop if a.oid == self._demerzel_oid), None)
            pw = self.pawn(self._demerzel_oid) if dem is not None else None
            if dem is None or (pw is not None and pw.is_dead_by_age(dem)):
                self._death_t = self.t
        # (b) the current voice holder
        if self._voice_oid is not None:
            v = next((a for a in self.pop if a.oid == self._voice_oid), None)
            pw = self.pawn(self._voice_oid) if v is not None else None
            if v is None or (pw is not None and pw.is_dead_by_age(v)):
                st = (self._groom if (self._groom is not None and
                                      self._groom.teacher_oid == self._voice_oid)
                      else None)
                self._gev("voice_died", {"oid": self._voice_oid})
                trained_heir = (st is not None and st.dao_done
                                and st.candidate_oid in alive)
                if self._outcome is None:
                    self._outcome = OUT_DAO if trained_heir else OUT_NONE
                self._voice_oid = None
                if trained_heir:
                    self._install_dao_carrier(st)
                else:
                    self._groom = None
        # (c) the дао carrier (voiceless line)
        elif self._dao_carrier is not None:
            c = next((a for a in self.pop if a.oid == self._dao_carrier), None)
            pw = self.pawn(self._dao_carrier) if c is not None else None
            if c is None or (pw is not None and pw.is_dead_by_age(c)):
                st = (self._groom if (self._groom is not None and
                                      self._groom.teacher_oid == self._dao_carrier)
                      else None)
                self._gev("carrier_died", {"oid": self._dao_carrier})
                trained_heir = (st is not None and st.dao_done
                                and st.candidate_oid in alive)
                self._dao_carrier = None
                if trained_heir:
                    self._install_dao_carrier(st)
                else:
                    self._groom = None

    def _emit_modc(self, alive):
        """The single emitter's emissions this tick. Returns (emissions, taught, head,
        phase, kind). Source priority for the ORIGIN is exactly mod A/B (replay ->
        policy -> deterministic means); successors run the SAME directive through their
        OWN vector + stutter; a дао carrier repeats his learned practice by his own
        will. On replay everything (incl. teaching) is read from the log and the taught
        flag is DERIVED from the logged set — byte-identical worlds (gate C2)."""
        from .succession import (teach_step, teach_cell, carrier_means, stutter,
                                 TEACH as PH_TEACH, RITUAL as PH_RITUAL)
        g, st = self.cfg.groom, self._groom
        taught = False
        if (self._voice_oid is not None and self._voice_oid in alive
                and self._directive is not None):
            head, kind = self._voice_oid, "voice"
        elif self._dao_carrier is not None and self._dao_carrier in alive:
            head, kind = self._dao_carrier, "dao"
        else:
            return [], False, None, None, None
        phase = st.phase if (st is not None and st.teacher_oid == head) else "-"
        in_ritual = (st is not None and st.teacher_oid == head
                     and st.phase == PH_RITUAL)
        if kind == "voice":
            icell = teach_cell(self, self._directive)
        else:
            L = self._learned.get(head)
            icell = tuple(L.cell) if (L is not None and L.cell) else None
        can_teach = (head == self._demerzel_oid
                     or bool(self._learned.get(head) is not None
                             and self._learned[head].can_teach))
        teaching = (not in_ritual and can_teach and st is not None
                    and st.teacher_oid == head and st.phase == PH_TEACH
                    and g.teach_slots > 0 and st.candidate_oid is not None
                    and icell is not None)

        # 1) replay takes absolute priority — the world replays byte-identical
        if self._replay_log is not None and self.t in self._replay_log:
            ems = [(oid, tuple(cell), amt)
                   for (oid, cell, amt) in self._replay_log[self.t]]
            if teaching:
                taught = any(e[0] == st.candidate_oid
                             and tuple(e[1]) == tuple(icell) for e in ems)
            if head != self._demerzel_oid:
                self._succ_reign += 1
            return ems, taught, head, phase, ("silent" if in_ritual else kind)

        # 2) live
        if in_ritual:
            return [], False, head, phase, "silent"     # silence: the ritual's price
        if kind == "voice":
            if head == self._demerzel_oid:
                # the ORIGIN: exact mod A/B source priority; NEVER stuttered (the god
                # picked this body directly — there was no transfer)
                pers = self._demerzel_personality
                if self._policy is not None:
                    ems = self._policy.choose(self, head, pers,
                                              self._directive, self._decision_log)
                else:
                    ems = choose_means(self, head, pers, self._directive)
            else:
                # a successor executes the SAME directive with HIS OWN vector
                pers = self.pawn(head).personality
                ems = choose_means(self, head, pers, self._directive)
                if g.stutter_on:
                    L = self._learned.get(head)
                    ems = stutter(ems, self, head, pers,
                                  trained=bool(L is not None and L.can_teach),
                                  reign_tick=self._succ_reign)
                self._succ_reign += 1
        else:
            # дао carrier: the practice by his own will (trained by construction)
            pers = self.pawn(head).personality
            ems = carrier_means(self, head, pers, self._learned.get(head))
            if g.stutter_on:
                ems = stutter(ems, self, head, pers, trained=True,
                              reign_tick=self._succ_reign)
            self._succ_reign += 1
        # teaching diverts listener slots from the goal to the apprentice
        if teaching:
            tch = teach_step(self, head, st.candidate_oid, icell,
                             self.inject_amount * (0.5 + pers.deception_lean),
                             g.teach_dist)
            if tch:
                keep = max(0, len(ems) - g.teach_slots)
                ems = [e for e in ems if e[0] != st.candidate_oid][:keep] + tch
                taught = True
        return ems, taught, head, phase, kind

    def _do_ritual_move(self, st):
        """The ritual completes: the god relocates into the apprentice's body. Longevity
        moves WITH the voice (the god sustains the vessel); the apprentice keeps his OWN
        personality vector — that is the whole experiment. An untrained successor (the
        early-ritual gamble) cannot teach: his line ends with him."""
        from .succession import LearnedDao, GroomState, OUT_FULL, OUT_VOICE
        from .directive import IMPLANT
        from .pawn import Pawn
        succ = st.candidate_oid
        pers = self.pawn(succ).personality
        self._pawns[succ] = Pawn(succ, pers, self.cfg.a_mat, self.cfg.a_old,
                                 self.cfg.demerzel_a_max)
        old = self._voice_oid
        self._voice_oid = succ
        cell = None
        if self._directive is not None and self._directive.goal == IMPLANT:
            c = self._directive.payload.get("cell")
            cell = tuple(c) if c else None
        self._learned[succ] = LearnedDao(goal=self._directive.goal, cell=cell,
                                         target=self._directive.target,
                                         can_teach=bool(st.dao_done))
        self._succ_reign = 0
        self._depth += 1
        if self._outcome is None:                 # the headline 2x2: first succession
            self._outcome = OUT_FULL if st.dao_done else OUT_VOICE
        self._carriers.append((self.t, succ, "voice", bool(st.dao_done)))
        self._groom = (GroomState(teacher_oid=succ, started_t=self.t)
                       if (self.cfg.groom.chain and st.dao_done) else None)
        self._gev("voice_moved", {"from": old, "to": succ,
                                  "trained": bool(st.dao_done), "depth": self._depth})

    def _install_dao_carrier(self, st):
        """A trained heir inherits the дао (no voice: the god died with the old vessel).
        The practice is his own will now; if the chain is on, he grooms the next link."""
        from .succession import LearnedDao, GroomState
        from .directive import IMPLANT
        heir = st.candidate_oid
        self._dao_carrier = heir
        self._depth += 1
        src = self._learned.get(st.teacher_oid)
        if src is not None:
            goal, cell, tgt = src.goal, (tuple(src.cell) if src.cell else None), src.target
        else:
            goal, tgt = self._directive.goal, self._directive.target
            c = self._directive.payload.get("cell") if goal == IMPLANT else None
            cell = tuple(c) if c else None
        self._learned[heir] = LearnedDao(goal=goal, cell=cell, target=tgt,
                                         can_teach=True)
        self._carriers.append((self.t, heir, "dao", True))
        self._succ_reign = 0
        self._groom = (GroomState(teacher_oid=heir, started_t=self.t)
                       if self.cfg.groom.chain else None)
        self._gev("dao_inherited", {"to": heir, "depth": self._depth})

    def _gev(self, event, data=None):
        self._groom_log.append((self.t, event, dict(data or {})))

    def line_window(self):
        """The LINE's window [issued_t, line_death_t]: when the succession line fell
        silent (no emitter left). living_window stays the FIRST teacher's (mod A)."""
        return (self._issued_t, self._line_death_t)


    # ---- C-LIVE: the typed step — the mind is the teacher, no god anywhere --- #
    def _step_voice_typed(self):
        """The typed-protocol step. The deterministic machine (mod C) kept two
        heuristics and one privilege; here ALL judgment is the mind's: it PICKs its
        apprentice from what it can SEE, decides teach-vs-preach, gambles the ritual,
        may stay silent. Emissions derive DETERMINISTICALLY from (action, world) —
        targeting was mod B's question (answered NULL); this arm isolates judgment.
        Non-determinism lives ONLY in the action stream (self._typed_log), so a
        replay from that log is byte-identical (gate CL2)."""
        from .succession import (GroomState, teach_cell, typed_view,
                                 apply_typed_action, ACT_EMIT, ACT_TEACH,
                                 ACT_RITUAL, ACT_PICK)
        g = self.cfg.groom
        if not self._awake:
            if self.t >= self._t_awaken:
                if not self._awaken():
                    return
                self._voice_oid = self._demerzel_oid
                self._groom = GroomState(teacher_oid=self._voice_oid, started_t=self.t)
                self._gev("mind_issued", {"teacher": self._voice_oid})
            else:
                return
        alive = {a.oid for a in self.pop}
        n0 = len(self._groom_log)
        self._resolve_deaths_modc(alive)
        # deaths feed the mind's next view (the world changed while it looked away)
        self._typed_events.extend(e for (_t, e, _d) in self._groom_log[n0:])
        # the head this tick (one-emitter invariant, same as mod C)
        head = None
        if (self._voice_oid is not None and self._voice_oid in alive
                and self._directive is not None):
            head, kind = self._voice_oid, "voice"
        elif self._dao_carrier is not None and self._dao_carrier in alive:
            head, kind = self._dao_carrier, "dao"
        st = self._groom
        if head is not None:
            pers = (self._demerzel_personality if head == self._demerzel_oid
                    else self.pawn(head).personality)
            learned = self._learned.get(head)
            can_teach = (head == self._demerzel_oid
                         or bool(learned is not None and learned.can_teach))
            has_machine = (st is not None and st.teacher_oid == head and can_teach)
            # the mind acts: replay -> logged action; live -> policy.act(view)
            if (self.cfg.replay_actions is not None
                    and self.t in self.cfg.replay_actions):
                a = self.cfg.replay_actions[self.t]
                action = tuple(a) if isinstance(a, (list, tuple)) else (a,)
            elif self.cfg.replay_actions is not None:
                action = (ACT_EMIT,)               # replay gap: inert default
                self._typed_events.append("replay_gap")
            else:
                view = typed_view(self, head, pers,
                                  self._directive if kind == "voice" else None,
                                  learned, st if has_machine else None, g,
                                  self._typed_events)
                action = self._policy.act(self, head, pers,
                                          self._directive if kind == "voice" else None,
                                          view)
                action = (tuple(action) if isinstance(action, (list, tuple))
                          else (action,))
            self._typed_events = []
            self._typed_log[self.t] = list(action)
            akind = action[0]
            # a head without the дао cannot teach/pick/ritual — the дао is the full
            # replicator; an untrained voice-gambler's line ends with him (same LAW
            # as the deterministic machine, kept for comparability).
            if not has_machine and akind in (ACT_TEACH, ACT_PICK, ACT_RITUAL):
                akind, action = ACT_EMIT, (ACT_EMIT,)
                self._typed_events.append("no_dao_cannot")
            ems, taught, vkind = self._typed_emissions(
                action, head, kind, pers, learned,
                st if has_machine else None, g)
            self._decision_log[self.t] = [(oid, [c[0], c[1]], amt)
                                          for (oid, c, amt) in ems]
            for (listener_oid, cell, amount) in ems:
                led = self.injected.setdefault(listener_oid, {})
                led[cell] = led.get(cell, 0.0) + amount
            om = self._owner_share_now()
            goal = self._directive.goal if self._directive is not None else None
            tgt = self._directive.target if self._directive is not None else None
            self._voice_log.append((self.t, goal, tgt, len(ems), round(om, 6),
                                    head, (st.phase if has_machine else "-"), vkind))
            # physics advances from the action
            if has_machine:
                icell = (teach_cell(self, self._directive) if kind == "voice"
                         else (tuple(learned.cell)
                               if (learned is not None and learned.cell) else None))
                ev = apply_typed_action(self, st, g, head, kind == "voice",
                                        action, taught, icell)
                if ev == "MOVED":
                    self._do_ritual_move(st)
                    self._typed_events.append("voice_moved")
                elif ev is not None:
                    self._gev(ev, {"head": head, "cand": st.candidate_oid,
                                   "dao": st.dao_progress, "act": akind})
                    self._typed_events.append(ev)
        # voice lifecycle identical to mod C
        has_emitter = ((self._voice_oid is not None and self._voice_oid in alive)
                       or (self._dao_carrier is not None
                           and self._dao_carrier in alive))
        self.injection_strength = (float(self.cfg.voice_strength)
                                   if has_emitter else 0.0)
        if (self._line_death_t is None and self._issued_t is not None
                and not has_emitter):
            self._line_death_t = self.t

    def _typed_emissions(self, action, head, kind, pers, learned, st, g):
        """Emissions derived deterministically from the mind's chosen action.
        Returns (emissions, taught, voice_log_kind). PICK preaches like EMIT
        (designation costs nothing — matches the deterministic whisper);
        RITUAL is silence (the act's price); PASS is chosen silence."""
        from .succession import (teach_step, teach_cell, carrier_means, stutter,
                                 ACT_TEACH, ACT_RITUAL, ACT_PASS)
        akind = action[0]
        if akind == ACT_RITUAL:
            return [], False, "silent"
        if akind == ACT_PASS:
            return [], False, "pass"
        if kind == "voice":
            ems = choose_means(self, head, pers, self._directive)
            if head != self._demerzel_oid:
                if g.stutter_on:
                    ems = stutter(ems, self, head, pers,
                                  trained=bool(learned is not None
                                               and learned.can_teach),
                                  reign_tick=self._succ_reign)
                self._succ_reign += 1
        else:
            ems = carrier_means(self, head, pers, learned)
            if g.stutter_on:
                ems = stutter(ems, self, head, pers, trained=True,
                              reign_tick=self._succ_reign)
            self._succ_reign += 1
        taught = False
        if akind == ACT_TEACH and st is not None and st.candidate_oid is not None:
            icell = (teach_cell(self, self._directive) if kind == "voice"
                     else (tuple(learned.cell)
                           if (learned is not None and learned.cell) else None))
            if icell is not None:
                tch = teach_step(self, head, st.candidate_oid, icell,
                                 self.inject_amount * (0.5 + pers.deception_lean),
                                 g.teach_dist)
                if tch:
                    keep = max(0, len(ems) - g.teach_slots)
                    ems = [e for e in ems if e[0] != st.candidate_oid][:keep] + tch
                    taught = True
        return ems, taught, kind

    # ---- helpers ----------------------------------------------------------- #
    def _owner_share_now(self) -> float:
        owners = self.owner_ids()
        tot = sum(a.body for a in self.pop)
        if tot <= 0:
            return float("nan")
        return sum(a.body for a in self.pop if a.oid in owners) / tot

    def living_window(self):
        return (self._issued_t, self._death_t)


def run_polis(cfg: PolisConfig | None = None):
    from sim_eventlog import EventLog
    cfg = cfg or PolisConfig()
    log = EventLog()
    w = Polis(log, cfg)
    for _ in range(cfg.days):
        w.step()
    return w, log


def polis_fingerprint(w: Polis) -> str:
    """Substrate fp (canon-anchored) + a hash of the voice trace, so the Demerzel layer is
    reproducible independently of the conserved substrate."""
    h = hashlib.sha256()
    h.update(appropriation_fingerprint(w).encode())
    if getattr(w.cfg, "groom", None) is None:
        trace = "|".join(f"{t}:{g}:{tgt}:{n}:{s:.6f}"
                         for (t, g, tgt, n, s) in w._voice_log)
        h.update(("|VOICE|" + trace).encode())
        h.update(f"|win{w.living_window()}".encode())
    else:
        # mod C: extended 8-tuple trace + the succession line (outcome, depth, groom log)
        trace = "|".join(f"{t}:{g}:{tgt}:{n}:{s:.6f}:{c}:{ph}:{k}"
                         for (t, g, tgt, n, s, c, ph, k) in w._voice_log)
        h.update(("|VOICE|" + trace).encode())
        h.update(f"|win{w.living_window()}|line{w.line_window()}".encode())
        h.update(f"|out{w._outcome}|depth{w._depth}".encode())
        gl = ";".join(f"{t}:{e}" for (t, e, _d) in w._groom_log)
        h.update(("|GROOM|" + gl).encode())
        if getattr(w, "_typed_log", None):
            tl = ";".join(f"{t}:{','.join(map(str, a))}"
                          for t, a in sorted(w._typed_log.items()))
            h.update(("|TYPED|" + tl).encode())
    return h.hexdigest()[:16]
