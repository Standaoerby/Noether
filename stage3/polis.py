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
    trace = "|".join(f"{t}:{g}:{tgt}:{n}:{s:.6f}"
                     for (t, g, tgt, n, s) in w._voice_log)
    h.update(("|VOICE|" + trace).encode())
    h.update(f"|win{w.living_window()}".encode())
    return h.hexdigest()[:16]
