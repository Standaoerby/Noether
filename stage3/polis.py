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
    # mod E (Dunbar): social attention locus. None => OFF => byte-identical to canon.
    # A cap on active social ties (registry of known other-oids), distinct from the
    # spatial attention budget K. See stage3/dunbar.py.
    dunbar_K: int | None = None
    # mod F (material culture, vitok 1 = vessel): a DUAL-LAYER artifact reservoir — the
    # FIRST extension of the mass invariant (soil+plant+Σbody+Σartifact.mass). False =>
    # OFF => empty field => sum_mass()=0.0 => _matter byte-identical to canon (gate
    # MF-OFF). See stage3/artifact.py. Thresholds are deterministic (WE TEST them).
    artifacts: bool = False
    write_stasis: int = 8            # ticks a fat pawn must dwell before it writes
    write_stake: float = 0.30        # kg of body frozen into a new vessel
    mat_decay: float = 0.001         # material-decay rate (mass → soil; slow for vessel)
    sem_decay: float = 0.02          # semantic-decay rate (salience → 0)
    read_threshold: float = 0.5      # salience below this => unreadable ruin
    salience0: float = 1.0           # starting / copy-refreshed cultural loudness
    # mod F vitok 2 — store (a printable mass reserve: hunger draws mass→body back)
    # and capital (a productivity tool: soil→body extraction gated on presence).
    # Both False => byte-identical to the vitok-1 vessel run (gate MFv2-OFF).
    # Floors live in artifact.py (STORE_BODY_FLOOR / CAPITAL_BODY_FLOOR — measured
    # calibration); access ∈ open|owner|maker is the HG1/HG3 experimental axis.
    store_on: bool = False
    store_stake: float = 0.30        # kg of body frozen into a store
    store_draw_at: float = 0.40      # hunger line: body below this may draw
    store_draw_rate: float = 0.10    # kg per tick a drawer may extract
    store_access: str = "open"       # open | owner | maker
    capital_on: bool = False
    capital_stake: float = 0.50      # kg of body frozen into a tool
    capital_rate: float = 0.02       # soil→body per tick per kg of tool (measured: 0.10
                                     # is a demographic pump; 0.02 is minimally invasive)
    capital_access: str = "open"     # open | owner | maker
    # mod F vitok 3 (v2) — two flags, both OFF => byte-identical to vitok 2.
    #  store_settle: a store minted this tick is not drawable until the next (a physical
    #    settling pause; delays transfer one tick so the object STANDS long enough to be
    #    seen — the fix for v1 diagnosis (b): stores annihilated at the point of demand).
    #  store_vision: an ORGAN inside canonical perception. Polis overrides _observe so a
    #    pawn, on sensing its own cell, also folds the drawable standing store on it into
    #    cell-memory (belief only; mass untouched) — the fix for v1 diagnosis (a): the
    #    post-hoc end-of-step write was overwritten by the next _observe before decide.
    #    Store-only, own-cell-only, access-filtered in the eyes. See stage3/vision.py.
    store_settle: bool = False
    store_vision: bool = False
    # mod G (intent, виток 1): триггер → интент → взаимодействие → результат — between
    # the world-scan and the artifact physics a CHOICE appears, WITHOUT touching the
    # physics. "off" => the layer is not built at all => byte-identical to vitok 2
    # (gate MG-OFF). "reflex" confirms every action => physically ≡ off (gate
    # MG-REFLEX: the scan itself must not perturb the world). "utility" filters verbs
    # through the STRUCTURAL personality axes (score = Σ w·axis >= intent_theta) —
    # personality touches matter for the first time. "live" takes a confirmed subset
    # from a mind via the typed protocol (mock in vitok 1; via-log replay bit-exact;
    # live прогоны — a separate session). See stage3/intent.py.
    intent_policy: str = "off"
    intent_theta: float = 0.5        # utility threshold (0.5 = честный дизайн, не калибровка)
    intent_mind: object = None       # live: the mind; .decide(world, t, affordances)
    intent_replay: dict = None       # live: {t: {oid: [verbs]}} — requests read from via-log
    # mod G2 (control without ownership, Фаза 1) — EXTORT: a conserving body→body seizure
    # from a co-present owner, the reverse-signed tribute (module 23 inverted). It fires
    # ONLY when a guard (enforcer caste) is NOT co-located on the cell — crime lives in the
    # shadow of presence (VERIFY #3: co-located = same cell, sim_institution._do_challenges).
    # OFF by default => the verb does not exist => byte-identical to mod G (gate MG2-OFF).
    # Requires an intent policy (reflex/utility/live) — under "off" there is no approve seam,
    # so extort is a no-op. rho_extort=None mirrors the legitimate tribute rate (rho).
    extort_on: bool = False
    rho_extort: float = None         # seizure rate; None => = appropriation (rho), the mirror
    extort_enforcers: int = 0        # guard caste size (0 => no guard => gate always open)
    extort_guard_everywhere: bool = False  # saturated surveillance: the gate is closed on
                                     # EVERY cell => EXTORT never fires (gate MG2-illegit:
                                     # a fully-guarded world is byte-identical to no verb)
    # mod G2 (Фаза 2) — DELEGATE / REVOKE: the michelsian hole. A root A holds a delegation
    # RIGHT over the tribute-collecting owners (delegates B); each tick a delegate remits a
    # share m of the tribute it collected up to A (body→body, conserving) — so A reaps k
    # cells at once WITHOUT being present anywhere: an institutional bypass of the hard
    # presence ceiling (VERIFY #1). The relation is permission-only and mass-neutral; only
    # the remittance moves mass. REVOKE has TEETH — what makes a delegate actually remit:
    #   none       unenforceable: every delegate defects, A reaps nothing (delegate ≡
    #              distributed ownership; the apparatus without a tooth is empty).
    #   reputation the mark-ledger: a defecting delegate is marked and loses its delegate
    #              standing (barred from the network); compliant (low-deception) delegates
    #              remit. Soft — A's flow is capped at the compliant fraction.
    #   enforcer   spatial: a delegate remits only when a guard (delegate enforcer caste) is
    #              co-located — the ceiling "turtles down" to the guard's own presence.
    #   auto       the ledger self-enforces (god-physics): full remittance. ⛔ a substrate
    #              CHEAT — the honesty control (MG2D-teeth), never a working regime.
    # OFF by default => no root, no remittance => byte-identical to Фаза 1 (gate MG2D-OFF).
    delegate_on: bool = False
    delegate_m: float = 0.7          # meta-tribute share B→A (Stan 2026-07-09; root's cut)
    delegate_root: int = None        # apex oid; None => auto (lowest-oid speaker, non-guard)
    revoke_tooth: str = "none"       # none | reputation | enforcer | auto  (the REVOKE sweep)
    delegate_enforcers: int = 0      # guard caste size for the enforcer tooth (0 => none)
    delegate_compliance_dl: float = 0.5  # reputation tooth: a delegate complies (remits) iff
                                     # its deception_lean <= this. Read ONLY when delegate_on
                                     # and tooth="reputation"; default 0.5 reproduces vitok-1
                                     # bit-for-bit (gate MG2V-REFACTOR). The compliant FRACTION
                                     # it induces (not the threshold) is the social parameter.


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
        # mod E (Dunbar): social attention locus — pure belief overlay, no mass touched.
        # Inert (None) => byte-identical to canon (gate ME-OFF).
        from .dunbar import DunbarRegistry
        self._dunbar = DunbarRegistry(cfg.dunbar_K)
        # mod F (material culture): the artifact reservoir. MUST exist BEFORE super().__init__,
        # because _matter() (overridden below) is called inside CommWorld.__init__ to set M0
        # — the field is empty then, sum_mass()=0.0, so M0 is measured as pure canon. OFF
        # (cfg.artifacts=False) => empty field forever => _matter ≡ canon (gate MF-OFF).
        from .artifact import ArtifactField
        self._artifacts = ArtifactField(
            enabled=cfg.artifacts, write_stasis=cfg.write_stasis,
            write_stake=cfg.write_stake, mat_decay=cfg.mat_decay,
            sem_decay=cfg.sem_decay, read_threshold=cfg.read_threshold,
            salience0=cfg.salience0,
            store_on=cfg.store_on, store_stake=cfg.store_stake,
            store_draw_at=cfg.store_draw_at, store_draw_rate=cfg.store_draw_rate,
            store_access=cfg.store_access, store_settle=cfg.store_settle,
            capital_on=cfg.capital_on, capital_stake=cfg.capital_stake,
            capital_rate=cfg.capital_rate, capital_access=cfg.capital_access,
        )
        # mod G (intent): built ONLY when asked — "off" leaves the artifact passes with
        # zero new computation in the hot path (self._artifacts.intent stays None).
        if cfg.intent_policy != "off":
            from .intent import IntentLayer
            self._artifacts.intent = IntentLayer(
                cfg.intent_policy, theta=cfg.intent_theta,
                mind=cfg.intent_mind, replay=cfg.intent_replay)
        # start ASLEEP: injection_strength=0 so the injected term is inert => canon.
        # perception preset (radius/K/lag/regime/target_policy) MUST mirror the headline
        # appropriation run, else the sleeping Polis is not byte-identical to it.
        super().__init__(
            log, seed=cfg.seed, regime=cfg.regime, radius=cfg.radius, K=cfg.K, lag=cfg.lag,
            arena_side=cfg.arena_side, target_policy=cfg.target_policy,
            appropriation=cfg.appropriation, owner_policy=cfg.owner_policy,
            injection_strength=0.0, injectors=0, inject_amount=cfg.inject_amount,
        )
        # mod G2 (EXTORT): built AFTER super().__init__ so self.speaker / owner caste exist.
        # The guard caste mirrors sim_institution's: the M_e lowest-oid founder speakers AFTER
        # the owner block, a fixed identity disjoint from owners. OFF (extort_on False) leaves
        # every field inert and the step-seam a no-op (byte-identical, gate MG2-OFF).
        self._extort_on = bool(cfg.extort_on)
        self._rho_extort = (cfg.appropriation if cfg.rho_extort is None
                            else float(cfg.rho_extort))
        self._extorted_total = 0.0       # cumulative seized mass (kg) — bankable metric
        self._extort_events = []         # (t, cell, victim_oid, [taker_oids], amount)
        spk = sorted(self.speaker)
        self._extort_enforcer_ids = (set(spk[self._n_owners:self._n_owners + int(cfg.extort_enforcers)])
                                     if self._extort_on else set())
        self._extort_cache_t = -1        # per-tick position cache (positions fixed within a tick)
        self._extort_cache = {}          # cell -> (frozenset owner_oids present, guard_present)
        # mod G2 (DELEGATE / REVOKE): the apex A and its guard caste (disjoint from the owner
        # block AND the extort guards, so the castes never overlap). OFF => no root => the
        # remittance seam is a no-op and _appropriate delegates straight to canon (MG2D-OFF).
        self._delegate_on = bool(cfg.delegate_on)
        self._delegate_m = float(cfg.delegate_m)
        de = int(cfg.delegate_enforcers)
        off0 = self._n_owners + int(cfg.extort_enforcers)
        self._delegate_enforcer_ids = (set(spk[off0:off0 + de])
                                       if self._delegate_on and cfg.revoke_tooth == "enforcer"
                                       else set())
        if not self._delegate_on:
            self._delegate_root = None
        elif cfg.delegate_root is not None:
            self._delegate_root = int(cfg.delegate_root)
        else:                            # auto: lowest-oid speaker not in any guard caste
            cand = [o for o in spk if o not in self._extort_enforcer_ids
                    and o not in self._delegate_enforcer_ids]
            self._delegate_root = cand[0] if cand else (spk[0] if spk else None)
        self._delegate_m_income = {}     # per-tick owner->tribute income (set by _appropriate)
        self._delegate_marks = set()     # mark-ledger (b): defecting delegates barred (belief)
        self._delegate_flow = 0.0        # cumulative meta-tribute reaped by the root (kg)
        self._delegate_events = []       # (t, delegate_oid, amount) — remittances that fired
        self._delegate_defections = 0    # count of ticks a delegate withheld (any tooth)

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

    # ---- mod F vitok 3 (v2): store_vision as an organ inside canonical perception ---- #
    def _observe(self, a):
        """Documented canon seam (same pattern mod B used to swap the speaker): run the
        canonical CommWorld._observe (senses true plant, stamps freshness, drops hearsay),
        THEN, if store_vision is on, fold the drawable standing store on this pawn's OWN
        cell into its cell-memory. Order is correct by construction — our observe (truth +
        vision) precedes decide within the think cycle — which is exactly what v1's
        end-of-step write could not achieve. Belief only; no mass is touched."""
        super()._observe(a)
        if self.cfg.store_vision:
            from .vision import observe_stores
            observe_stores(self, a)

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
        # mod E: refresh the social registry from this tick's co-locations (no-op if OFF)
        self._dunbar.register_contacts(self, self.t)
        # mod F: writing / reading / copying / dual decay (no-op if OFF). Runs AFTER the
        # tower's plant-growth+grazing for this tick, so material decay returns mass to
        # soil that only next tick's growth can draw on — the slow civilisational arc.
        self._artifacts.tick(self)
        # mod G2 (EXTORT): the reverse-signed seizure, gated by the SAME intent layer the
        # artifact verbs use. No-op unless extort_on AND an intent policy is built (approve
        # seam). Runs after the artifact tick — the scan (tick-start) already set EXTORT
        # affordances; positions are fixed within a tick, so the illegitimacy gate is stable.
        if self._extort_on and self._artifacts.intent is not None:
            self._extort(self.t)
        # mod G2 (DELEGATE): the root reaps its meta-tribute from the delegates' collections
        # (body→body), gated by the REVOKE tooth. No-op unless delegate_on. Runs after extort
        # so the tick's transfers settle before the apex takes its cut.
        if self._delegate_on and self._delegate_root is not None:
            self._delegate(self.t)
        if self.cfg.groom is None:
            self._step_voice_moda()            # mod A/B path, verbatim (gate C0)
        elif (getattr(self._policy, "typed", False)
              or self.cfg.replay_actions is not None):
            self._step_voice_typed()           # C-LIVE: the mind is the teacher
        else:
            self._step_voice_modc()            # mod C: дао/ученик succession layer

    # ---- mod G2: EXTORT — reverse-signed seizure in the shadow of presence ---- #
    def _build_extort_cache(self):
        """Per-tick map cell -> (frozenset of co-present owner oids, guard_present). Positions
        are fixed within a tick (movement ran in super().step()), so ONE build per tick serves
        both the affordance scan (tick-start) and the _extort pass (later, same tick)."""
        from collections import defaultdict
        bycell = defaultdict(list)
        for a in self.pop:
            bycell[(a.i, a.j)].append(a)
        cache = {}
        everywhere = self.cfg.extort_guard_everywhere
        for cell, members in bycell.items():
            owners = self._owners_at(cell, members)          # co-present owners (both policies)
            guard = everywhere or any(a.oid in self._extort_enforcer_ids for a in members)
            cache[cell] = (frozenset(o.oid for o in owners), guard)
        self._extort_cache = cache
        self._extort_cache_t = self.t

    def intent_extra_affordances(self, a):
        """World-contributed intent affordances (the hook intent.scan calls). EXTORT is
        afforded to a pawn that is NEITHER a co-present owner NOR a guard, standing on a cell
        where an owner IS present and NO guard is co-located (the illegitimacy gate — crime in
        the shadow of presence). Empty when extort is OFF => the artifact menu is untouched."""
        if not self._extort_on:
            return ()
        from .intent import EXTORT
        if self._extort_cache_t != self.t:
            self._build_extort_cache()
        owners, guard = self._extort_cache.get((a.i, a.j), (frozenset(), False))
        if guard or not owners:
            return ()
        if a.oid in owners or a.oid in self._extort_enforcer_ids:
            return ()
        return (EXTORT,)

    def _extort(self, t):
        """Execute the intent-confirmed EXTORT seizures. On each cell with a co-present owner
        and NO guard, the confirmed extortionists seize rho_extort of each present owner's
        body (body->body, conserving), pooled and split evenly among the takers (sorted oid,
        last takes the float remainder). The exact mirror-reverse of appropriation-23."""
        from collections import defaultdict
        from .intent import EXTORT
        it = self._artifacts.intent
        if self._extort_cache_t != t:
            self._build_extort_cache()
        bycell = defaultdict(list)
        for a in self.pop:
            bycell[(a.i, a.j)].append(a)
        for cell in sorted(bycell):
            owners_oids, guard = self._extort_cache.get(cell, (frozenset(), False))
            if guard or not owners_oids:
                continue
            members = bycell[cell]
            takers = [a for a in sorted(members, key=lambda x: x.oid)
                      if a.oid not in owners_oids
                      and a.oid not in self._extort_enforcer_ids
                      and it.allows(a.oid, EXTORT)]          # confirmed by the intent layer
            if not takers:
                continue
            T = 0.0
            for v in sorted((a for a in members if a.oid in owners_oids),
                            key=lambda x: x.oid):
                seize = self._rho_extort * v.body
                if seize > v.body:                           # rho<=1 => never; clamp body >= 0
                    seize = v.body
                v.body -= seize                              # MASS leaves the owner...
                T += seize
            share = T / len(takers)
            given = 0.0
            for tk in takers[:-1]:
                tk.body += share                             # ...and enters the takers
                given += share
                it.note_ok(tk.oid, EXTORT)
            takers[-1].body += (T - given)                   # last takes remainder => pool exact
            it.note_ok(takers[-1].oid, EXTORT)
            self._extorted_total += T
            self._extort_events.append((t, cell, tuple(sorted(owners_oids)),
                                        tuple(tk.oid for tk in takers), round(T, 9)))
            self.log.emit(t, "extort", "individual", where=cell, actor=takers[0].oid, dm=T,
                          data={"victims": sorted(owners_oids),
                                "takers": [tk.oid for tk in takers], "amount": round(T, 6)})

    # ---- mod G2: DELEGATE / REVOKE — the apex reaps k cells without presence ---- #
    def _appropriate(self):
        """Canon appropriation (module 23), instrumented ONLY when delegate is on to capture
        each owner's tribute income THIS tick. The canon call runs FIRST inside
        AppropriationWorld.step (after all eating/movement), so the body delta across it is
        PURELY tribute (owners gain, non-owners lose); snapshotting is read-only, so the world
        after is byte-identical to canon and delegate_off delegates straight to super()."""
        if not self._delegate_on:
            return super()._appropriate()
        before = {a.oid: a.body for a in self.pop}
        super()._appropriate()
        inc = {}
        for a in self.pop:
            d = a.body - before.get(a.oid, a.body)
            if d > 1e-15:                          # only owners gain in _appropriate
                inc[a.oid] = d
        self._delegate_m_income = inc

    def _delegate_remit(self, B, tooth, guard_cells):
        """Does delegate B remit to the root this tick? The REVOKE tooth decides:
        none -> never (unenforceable); auto -> always (god-physics cheat); enforcer -> only
        when a guard is co-located (spatial); reputation -> the compliant (low-deception)
        remit, a marked defector never does (barred from the network)."""
        if tooth == "auto":
            return True
        if tooth == "enforcer":
            return (B.i, B.j) in guard_cells
        if tooth == "reputation":
            if B.oid in self._delegate_marks:
                return False                       # already marked -> out of the apparatus
            return self.pawn(B.oid).personality.deception_lean <= self.cfg.delegate_compliance_dl
        return False                               # "none" (and any unknown): all defect

    def _delegate(self, t):
        """Each delegate (a tribute-collecting owner, not the root, not a guard) remits share
        m of its tribute income to the physically-absent root A — body→body, conserving. The
        tooth gates the remittance; a reputation-defector is marked (loses delegate standing).
        A reaps k cells at once without being present: the institutional bypass of presence."""
        root = self._delegate_root
        live = {a.oid: a for a in self.pop}
        A = live.get(root)
        if A is None:                              # root dead -> the right lapses this tick
            return
        tooth = self.cfg.revoke_tooth
        guard_cells = ({(a.i, a.j) for a in self.pop if a.oid in self._delegate_enforcer_ids}
                       if tooth == "enforcer" else frozenset())
        for oid in sorted(self._delegate_m_income):
            if oid == root or oid in self._delegate_enforcer_ids:
                continue                           # the apex and its guards are not delegates
            B = live.get(oid)
            if B is None:
                continue
            if not self._delegate_remit(B, tooth, guard_cells):
                self._delegate_defections += 1
                if tooth == "reputation":
                    self._delegate_marks.add(oid)  # the mark-ledger: barred henceforth
                continue
            amount = self._delegate_m * self._delegate_m_income[oid]
            if amount > B.body:                    # cannot remit more body than one has
                amount = B.body
            if amount <= 0.0:
                continue
            B.body -= amount                       # MASS leaves the delegate...
            A.body += amount                       # ...and reaches the absent root
            self._delegate_flow += amount
            self._delegate_events.append((t, oid, round(amount, 9)))
            self.log.emit(t, "delegate_remit", "individual", where=(B.i, B.j), actor=oid,
                          dm=amount, data={"root": root, "amount": round(amount, 6)})

    def _matter(self):
        # FIRST extension of the tower's conservation law in 28 modules: artifact mass is
        # a fourth reservoir beside soil/plant/body. Canon Code/ is untouched; the +Σmass
        # enters ONLY here (a legal seam — Polis already overrides step/fingerprint). With
        # artifacts OFF the field is empty, sum_mass() returns float 0.0, and _matter is
        # byte-identical to canon (gate MF-OFF trivially).
        return super()._matter() + self._artifacts.sum_mass()

    def state_fingerprint(self):
        # canon state hash + Dunbar registry + artifact field (each empty when its module
        # is OFF => canon-identical). Blobs are concatenated in a fixed order (Dunbar, then
        # artifacts); when BOTH are empty the base hash is returned unchanged (MF-OFF/ME-OFF).
        base = super().state_fingerprint()
        blob = self._dunbar.fingerprint_blob() + self._artifacts.fingerprint_blob()
        # mod G: intent state (counters + deny digest) enters the blob ONLY under
        # utility/live — the vitok-2 conditional-suffix discipline (the kind term):
        # off has no layer, reflex returns b"", so the OFF/REFLEX terms are
        # byte-identical to vitok 2 and the anchors are holy (MG-OFF / MG-REFLEX).
        it = self._artifacts.intent
        if it is not None:
            blob += it.fingerprint_blob()
        if not blob:
            return base
        import hashlib
        return hashlib.sha256(base.encode() + blob).hexdigest()[:16]

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
