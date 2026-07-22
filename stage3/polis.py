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

from sim_eventlog import SEED, DEATH
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
    extort_reputation: bool = False  # vitok-2 Фаза 4 — the mark-ledger, reused for EXTORT.
                                     # OFF (default) => inert, every extort anchor bit-for-bit.
                                     # ON => victim testimony: every owner seized from marks its
                                     # takers (guard-INDEPENDENT, deterministic). A marked pawn
                                     # loses the EXTORT affordance henceforth (одно преступление,
                                     # затем бан) — so recidivism is reputationally self-limited
                                     # where the sparse guard corps (HG2-2) cannot reach. The
                                     # mark costs ONLY EXTORT (delegation/ownership untouched).
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
    delegate_root_select: str = "auto"  # vitok-2 Фаза 2 — who is the apex on the AUTO path
                                     # (delegate_root is None):
                                     #   auto      lowest speaker not in any guard caste — the
                                     #             lowest OWNER, so the root carries a big body
                                     #             (its own tribute) beside the reaped flow.
                                     #   nonowner  the body-poor apex: lowest speaker OUTSIDE
                                     #             owners AND guards — reaps flow it never
                                     #             collected, so its only reserve is what the
                                     #             flow leaves in its own body (the HG2V-2
                                     #             owner_gap probe). Deterministic mirror of auto.
                                     # Read ONLY on the auto path; default "auto" reproduces
                                     # every anchor bit-for-bit (the field is inert otherwise).
    delegate_depth: int = 1          # vitok-2 Фаза 3 — depth of the remittance chain A←B←C.
                                     # 1 (default) => base owners remit straight to the root
                                     #   (the single-hop mechanic; byte-identical to Фаза 2).
                                     # d>=2 => (d-1) fixed intermediary delegates (the lowest
                                     #   non-owner, non-guard speakers, disjoint from the root)
                                     #   stack between base and apex: base -> B_{d-1} -> ... ->
                                     #   B_1 -> A, the meta-tribute share m taken at EVERY link
                                     #   (m^depth decay to the root). The tooth gates only the
                                     #   BASE hop (owner->apparatus); intermediary hops are
                                     #   unconditional internal routing. Each intermediary keeps
                                     #   (1-m) of what it forwards => a middle-management strata.
                                     # Read ONLY when delegate_on; d<=1 leaves every anchor bit-
                                     # for-bit (the chain path is never entered).
    # mod H (DEBT, виток 1) — power from CONSENT. A loan from a creditor's free store into a
    # hungry debtor's body (mass-neutral), an ENDOGENOUS rate fixed at the contract (vintage),
    # a per-tick payment out of the debtor's income, and a rights-deprivation ladder that a
    # default turns into bondage. DELEGATE is coercion from above, EXTORT is violence in the
    # shadow — debt is the deal from below: власть без титула, без насилия, без присутствия.
    # OFF by default => no loan is ever offered and the layer is not built => byte-identical to
    # mod G2 (gate MH-OFF). A loan needs a store to lend from, so store_on must be true too.
    debt_on: bool = False
    debt_r: float = 0.3          # share of the debtor's per-tick income paid to the creditor
                                 # (swept {0.2,0.3,0.5}); read ONLY when debt_on.
    debt_k_min: float = 1.1      # rate floor  (D/S -> 0): a loan of x mints x·k_min obligation
    debt_k_max: float = 2.0      # rate ceiling (D/S -> inf)
    debt_hunger_at: float = None # loan hunger line; None => store_draw_at (lend exactly where
                                 # hunger would otherwise draw). Read ONLY when debt_on.
    debt_income_drop: float = 0.5  # income_drop trigger: income this tick < this · trailing mean
                                 # income => a shock loan (reason=income_drop). Read ONLY debt_on.
    debt_invest_at: float = None # investment trigger: a fat non-owner (body >= this) may borrow
                                 # to fund a claim (reason=investment); None => 2·REPRO. Read
                                 # ONLY when claim_cost <= 0 (the vitok-1 degenerate trigger);
                                 # with claim_cost > 0 the trigger is "borrow to afford a claim".
    # mod H виток 2 — the four confounds the vitok-1 audit found (WO_stage3-mod-H-vitok2):
    debt_claim_inherits: bool = False  # K1: a creditor's CLAIM (право требования) passes to its
                                 # _house heir on death; else the claim on a live debtor lapses
                                 # (writeoff), the vitok-1 behaviour. Default False keeps vitok 1
                                 # byte-identical. An asset that outlives the body is the candidate
                                 # extra-somatic vessel (HH2'). Needs debt_house to find the heir.
    debt_overdue_ticks: int = 10 # K4: OVERDUE (stage 2) = a debtor missed a payment this many
                                 # ticks running — NOT the vitok-1 "outstanding>principal", which
                                 # (k>1) froze every fresh loan at stage 2 from tick one and
                                 # guaranteed non-repayment. The honest trigger.
    debt_house: bool = False     # K2: reconstruct _house (mod 25 lineage) from birth events so
                                 # heirs exist. Default False => no _house => every death writes
                                 # off (vitok 1). Read-only reconstruction, mass-neutral.
    claim_cost: float = 0.0      # K3: mass (body->soil) a pawn burns to SEIZE a cell. 0.0 =>
                                 # canon _do_claims runs verbatim => byte-identical (anchor
                                 # MH2-OFF). > 0 makes ownership scarce, so credit can buy a
                                 # SOURCE OF INCOME and the investment trigger comes alive.
    # mod H2-bis (decision-4a) — the credit CHANNEL. Lending is already same-cell co-present;
    # this WIDENS it to the substrate's existing von-Neumann movement neighbourhood (DIRS
    # N/S/W/E). False (default) => same cell only == vitok 2 (comparability, no new geometry);
    # True => a creditor on a DIRS-adjacent cell may also lend, so credit has more chances to
    # meet — the test of whether the channel was the binding constraint (HHB2). Non-no-op.
    debt_copresence: bool = False
    # mod H3 Phase 2 — the ENFORCER on debt. An overdue claim (K4 stage >= 2) is enforced by
    # FORCE — mass extracted from the debtor's body toward the creditor — but ONLY when the
    # co-located deme collectively sanctions it (majority-of-present, the Phase-1 organ), never
    # automatically. K5 is respected: the forced extraction is capped to leave the body at
    # DEATH+ (coercion takes mass, not life; the remainder stays as a claim). OFF => byte-
    # identical. HD1: does debt become power = claim × coercion?
    debt_enforce_on: bool = False
    debt_enforce_frac: float = 0.2   # fraction of the debtor's body extracted per enforcement
    debt_enforce_cost: float = 0.1   # friction: this fraction of the extracted mass -> soil
    # mod H3 — the public good + the punishment organ (WO_stage3-mod-H3). All OFF => byte-
    # identical. See stage3/publicgood.py. m calibrated in Phase 0 (n≈5 => sweep 1/5/10).
    pg_on: bool = False          # the deme's common field (contribution -> soil -> m·synergy)
    pg_m: float = 1.0            # synergy multiplier (efficiency of the pool's soil access)
    pg_stake: float = 0.005      # a full-propensity contribution unit (kg of body); calibrated
                                 # (Phase 0) small enough that the m·synergy pump does not
                                 # explode the reproducing population at m up to 10
    pg_p0: float = 0.5           # newborn contribution propensity ∈ [0,1]
    pg_learn: float = 0.1        # reinforcement step for the propensity
    contrib_visibility: str = "anon"   # anon | signed (can a punisher SEE who under-contributed)
    punish_on: bool = False      # the sanction organ (majority-of-present, victim -20% -> soil)
    punish_strategy: str = "min_contrib"   # min_contrib | max_body | coalition (the aiming rule)
    punish_frac: float = 0.2     # fraction of the victim's body destroyed to soil
    punish_cost: float = 0.1     # supporters' shared cost of sanctioning (·damage) -> soil
    # mod J (frailty / senescence): a hidden redundancy-block reserve per pawn. "off" =>
    # the FrailtyField is inert (no side-table, no draw, no cull, empty fingerprint) =>
    # byte-identical to canon (gate MJ-OFF). "flat" (Makeham-only control, constant hazard)
    # / "gompertz" (redundancy exhaustion) are the two mortal arms; the (n0,k,x0) overrides
    # default to the arm preset and are CALIBRATED in Ф2 to mean lifespan ≈ base. Repair
    # (rho_rep>0) reads CAPITAL only, never body (else the stake is legible; ВСТАВКА-27).
    # Eating repairs body but NEVER a block. See stage3/frailty.py.
    frailty: str = "off"                 # off | flat | gompertz
    frailty_n0: int | None = None        # blocks at birth (None => arm preset)
    frailty_k: float | None = None       # per-tick per-block failure prob (None => preset)
    frailty_x0: float | None = None      # initial damage load ∈ [0,1] (None => preset)
    frailty_rho_rep: float = 0.0         # repair coupling; 0 => the repair seam never fires
    # mod K (inheritance): a dead owner's cells pass to its lowest-oid LIVING bloodline heir
    # (same _house root) BEFORE the canon revert, instead of reverting to the commons — the
    # mod-25 (sim_inheritance) _inherit_dead rule ported into the Polis column. False =>
    # _inherit_dead never runs => canon revert => byte-identical (gate MK-OFF). Lives ONLY on
    # the canonical claim path (claim_cost<=0); K and K3 (claim_cost>0) are mutually exclusive
    # (gate MK-K3-UNTOUCHED). Needs the _house lineage (reuses the K2/mod-H machine). Pure
    # ledger — reassigns _cell_owner only, zero mass ops (gate MK-MASS < 1e-12). See §2.
    inherit_on: bool = False
    # faithful ledger (WO_faithful-ledger): make the EventLog a MIRROR of the Polis. Ownership,
    # inheritance and branding mutate state while emitting nothing, so any log consumer (card,
    # narrative, LLM agent, external audit) is blind to who owned what and how it passed on.
    # The observer below reconstructs it from a per-tick diff of PUBLIC state — canon untouched.
    # Emission is fingerprint-neutral (proved in Ф0: the log is in no fingerprint, and the only
    # state-affecting log reader, _update_houses, filters by kind), but it DOES change
    # events.jsonl — which β-3 anchors (V3-S7, 2735d669…). Hence a flag, default OFF: every
    # existing anchor stays byte-identical and the mirror is opt-in.
    faithful_ledger: bool = False
    heir_fallback: str = "revert"        # revert (heirless cell -> commons, == canon) |
                                         # escheat (heirless cell consolidates to the NEAREST
                                         # living owner of any house — mod-25 semantics)


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
        # Фаза 4: the mark-ledger reused for EXTORT (victim testimony). Inert unless ON.
        self._extort_reputation = bool(cfg.extort_reputation) and self._extort_on
        self._extort_marks = set()       # oids barred from EXTORT after being reported by a victim
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
        else:                            # auto path: deterministic apex, fixed at init
            excl = set(self._extort_enforcer_ids) | set(self._delegate_enforcer_ids)
            if cfg.delegate_root_select == "nonowner":
                # Фаза 2: the body-poor apex — also exclude the owner caste (spk[:n_owners],
                # sim_appropriation's static owner block), so the root reaps flow it never
                # collected and holds no reserve of its own. Mirror of the auto rule.
                excl |= set(spk[:self._n_owners])
            cand = [o for o in spk if o not in excl]
            self._delegate_root = cand[0] if cand else (spk[0] if spk else None)
        # Фаза 3: the remittance chain. depth 1 => no intermediaries (single hop, unchanged).
        # depth d => the (d-1) lowest non-owner/non-guard speakers (disjoint from the root)
        # form the chain [B_1 (nearest root) .. B_{d-1} (nearest base)]. Fixed at init, mirror
        # of the apex rule; inert (empty) when off or depth<=1, so no anchor is disturbed.
        self._delegate_depth = max(1, int(cfg.delegate_depth))
        if self._delegate_on and self._delegate_depth > 1:
            chexcl = (set(spk[:self._n_owners]) | set(self._extort_enforcer_ids)
                      | set(self._delegate_enforcer_ids) | {self._delegate_root})
            pool = [o for o in spk if o not in chexcl]
            self._delegate_chain_ids = pool[:self._delegate_depth - 1]
        else:
            self._delegate_chain_ids = []
        self._delegate_chain_recv = {}   # intermediary oid -> cumulative gross mass it handled
        self._delegate_m_income = {}     # per-tick owner->tribute income (set by _appropriate)
        self._delegate_marks = set()     # mark-ledger (b): defecting delegates barred (belief)
        self._delegate_flow = 0.0        # cumulative meta-tribute reaped by the root (kg)
        self._delegate_events = []       # (t, delegate_oid, amount) — remittances that fired
        self._delegate_defections = 0    # count of ticks a delegate withheld (any tooth)
        # mod H (DEBT): the debt layer. Inert (no loan ever offered, empty fingerprint blob)
        # unless cfg.debt_on => byte-identical to mod G2 (gate MH-OFF). See stage3/debt.py.
        from .debt import DebtLedger
        self._debt = DebtLedger(cfg)
        # mod H3: the public-good + punishment organ. Inert unless pg_on. See publicgood.py.
        from .publicgood import PublicGood
        self._pg = PublicGood(cfg)
        # mod J (frailty): the senescence side-table. Inert (no side-table, no draw, no cull,
        # empty fingerprint) unless cfg.frailty in {flat,gompertz} => byte-identical to canon
        # (gate MJ-OFF). Its RNG is a private seeded stream — self.rng never draws. See frailty.py.
        from .frailty import FrailtyField
        self._frailty = FrailtyField(
            cfg.frailty, n0=cfg.frailty_n0, k=cfg.frailty_k, x0=cfg.frailty_x0,
            rho_rep=cfg.frailty_rho_rep, seed=cfg.seed)
        # faithful ledger: opt-in mirror of ownership/inheritance/branding into the EventLog.
        # `_pending_inherit` is filled by _inherit_dead (the FACT of a succession, not a guess
        # reconstructed from a diff — a diff cannot tell "inherited by kin" from "reverted then
        # re-claimed by kin"), and drained by _emit_ledger_events at the end of the tick.
        self._ledger_on = bool(getattr(cfg, "faithful_ledger", False))
        self._pending_inherit = []
        # mod K: count of cells passed to a living bloodline heir (or escheat-consolidated)
        # this run — the MK-INHERIT-FIRES observable. Pure scalar, never fingerprinted; stays
        # 0 when inherit_off (MK-OFF untouched). Mirrors _delegate_defections/_extorted_total.
        self._inherit_events = 0
        # mod H виток 2 K2 / mod K: reconstruct _house (mod 25 lineage) from birth events so
        # debt heirs (K2) AND inheritance heirs (mod K) exist. Built when EITHER flag is on —
        # else the attribute is ABSENT, so getattr(w, "_house", None) is None and every death
        # writes off / reverts (anchor-safe). mod K reuses this same map (§2b).
        if cfg.debt_house or cfg.inherit_on:
            self._house = {}             # oid -> house root (founder); mirrors sim_inheritance
            self._house_cursor = 0       # birth-event cursor for lineage reconstruction

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
        # mod K / mod H K2: reconstruct the _house lineages BEFORE super().step() — so
        # _do_claims (inside super) sees fresh lineages when inheritance is on (§2c).
        # A single call for BOTH flags; the old late call in the debt-block is removed (§2
        # refinement A). Note: births of THIS tick are emitted INSIDE super().step(), so this
        # pre-super call folds births up to the PREVIOUS tick — correct for inheritance (heirs
        # must pre-exist a death); the debt path tolerated the one-tick shift (gate MH-OFF).
        if (self.cfg.debt_house or self.cfg.inherit_on) and hasattr(self, "_house"):
            self._update_houses()
            self._gc_houses()      # L2a: reclaim dead oids from the lineage map (see below)
        # mod H (DEBT): snapshot bodies so income THIS tick = the gain across the canonical
        # step (grazing + appropriation − metabolism). No-op unless debt_on.
        _debt_body0 = ({a.oid: a.body for a in self.pop} if self._debt.on else None)
        # faithful ledger: snapshot the ownership/branding state ON ENTRY, so the post-step
        # diff sees exactly what this tick changed. No-op (None) unless the mirror is on.
        _ledger0 = self._ledger_snapshot() if self._ledger_on else None
        if self._ledger_on:
            self._pending_inherit = []         # refilled by _inherit_dead inside super().step()
        super().step()                         # full tower + appropriation, unchanged
        # mod J (frailty): age each pawn's redundancy blocks and cull the exhausted, RIGHT
        # after the canonical step and BEFORE _gc_mark_ledgers and every consumer — so a
        # senescence death is swept from the mark-ledgers and seen by the intent/extort/
        # delegate scans exactly like a canonical starvation death. No-op unless ON (MJ-OFF).
        self._frailty.tick(self)
        # mod G2 GC: reclaim dead oids from the two mark-ledgers. Canon (sim_comm) has just
        # culled the dead from self.pop; do this BEFORE any consumer (the intent affordance
        # scan, _extort, _delegate) reads a ledger this tick, so the sweep is invisible to
        # the world. Behaviourally inert BY CONSTRUCTION — see _gc_mark_ledgers / gate
        # MG2V-GC-IDENT.
        self._gc_mark_ledgers()
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
        # mod H (DEBT): the deal from below. Runs after the G2 redistributions settle, so
        # payments/loans read this tick's final bodies; income is the canon gain measured
        # across super().step() (redistribution is not income). No-op unless debt_on.
        if self._debt.on:
            # (mod K §2c/A) lineage reconstruction moved to step() start — the old
            # self._update_debt_houses() call here is removed; _house is already fresh.
            income = {a.oid: max(0.0, a.body - _debt_body0.get(a.oid, a.body))
                      for a in self.pop}
            self._debt.set_income(income)
            self._debt.tick(self)
        # mod H3: the public-good + punishment round over co-located demes. No-op unless pg_on.
        if self._pg.on:
            self._pg.tick(self)
        if self.cfg.groom is None:
            self._step_voice_moda()            # mod A/B path, verbatim (gate C0)
        elif (getattr(self._policy, "typed", False)
              or self.cfg.replay_actions is not None):
            self._step_voice_typed()           # C-LIVE: the mind is the teacher
        else:
            self._step_voice_modc()            # mod C: дао/ученик succession layer
        # faithful ledger: emit claim/lose/inherit/mark/unmark from the tick's diff. MUST be
        # LAST: _extort and _delegate brand pawns further down this method, so an earlier
        # emission point saw the mark-ledgers unchanged and silently emitted nothing (caught
        # in Ф1 — 79 extort marks, zero events). Ownership is settled inside super().step()
        # and untouched below, so the late point is correct for it too. Pure observation.
        if self._ledger_on:
            self._emit_ledger_events(_ledger0)

    # ---- mod G2 GC: dead-oid reclamation for the mark-ledgers (WO_mark-ledger-gc) ---- #
    def _gc_mark_ledgers(self):
        """Sweep dead oids out of both G2 mark-ledgers, once per tick.

        Pawns are mortal and oids are NEVER reused (sim_comm._next is a monotonic
        counter), so a dead oid can never re-enter as a living actor: its mark gates
        nobody. Every consumer — intent_extra_affordances, _extort, _delegate_remit —
        only ever tests membership for a LIVING pawn (drawn from self.pop or the
        this-tick income of living owners), so removing a dead oid changes no decision.
        The reclamation is thus behaviourally inert BY CONSTRUCTION; gate MG2V-GC-IDENT
        proves the fingerprint is bit-identical before and after. Without it the sets
        grow monotonically with the cumulative number of ever-marked dead (the leak the
        longrun audit found: _extort_marks ×255 the living population at T=3000).

        Both ledgers are swept so the leak cannot migrate to the neighbour. No living
        mark is ever dropped — the sets are intersected with the living oids — so the
        surviving contents are identical for every living pawn. Observer seam (canon
        owns the per-pawn death path in sim_comm and must not be touched); the empty-set
        fast path keeps every OFF/asleep world a strict no-op."""
        if not (self._extort_marks or self._delegate_marks):
            return                             # nothing minted yet (OFF or asleep) => free
        living = {a.oid for a in self.pop}
        self._extort_marks &= living
        self._delegate_marks &= living

    # ---- mod H виток 2 K2: _house reconstruction from birth events (read-only) ---- #
    def house(self, oid):
        """Founder root of oid's bloodline (mod-25 house()). Founders (no birth event) map to
        themselves. Defensive getattr so the dynasty metrics can call it even when no lineage
        map exists (both flags off) — returns oid (self-root). Used by mod-K + metrics."""
        return getattr(self, "_house", {}).get(oid, oid)

    def _gc_houses(self):
        """L2a (longrun-audit-JK): reclaim dead oids from the _house lineage map, which
        otherwise grows monotonically with every pawn ever born (audit: 0->40341 at T=3000,
        ×18 the living pop, no plateau) — the direct analog of the _extort_marks leak.

        REACHABILITY-SAFE, and the timing is the whole point. Unlike _gc_mark_ledgers (a dead
        mark gates nobody, so it sweeps immediately), house(dead) IS read — _inherit_dead looks
        up a dead owner's house root to find its bloodline heir. Two reads must survive:

          1. a dead owner whose cells are still in _cell_owner. Canon order is
             super().step() [starvation deaths] -> _do_claims [inheritance], so a STARVATION
             death is inherited the same tick; but frailty culls senescence deaths AFTER
             _do_claims, so a SENESCENCE-dead owner's cells are inherited on tick T+1. Keeping
             every current _cell_owner value covers both — the entry survives until its estate
             is actually settled.
          2. a parent of a birth not yet folded. _update_houses folds tick T's births at the
             start of T+1 via _house.get(parent); a parent that died during T must still be
             present then. Calling this GC immediately AFTER _update_houses guarantees it: at
             prune time every birth is folded, and the parent was alive at the previous prune.

        Everything else is inert: house() = _house.get(oid, oid), so a dropped founder root
        still resolves to itself, and living pawns keep their own entries. _house is NOT part
        of state_fingerprint (base+dunbar+artifacts+intent+debt+pg+frailty — no _house term),
        and the reported metrics read _cell_owner + house(living), so the sweep is
        behaviourally inert BY CONSTRUCTION — gate MK-HOUSE-GC-IDENT proves it bit-for-bit.
        No len-gate here (the L2b lesson): membership is rebuilt every tick, and after the
        first sweep _house stays ~pop, so the cost is O(pop) like any other per-tick pass."""
        h = getattr(self, "_house", None)
        if not h:
            return                                   # OFF / nothing folded yet => free no-op
        keep = {a.oid for a in self.pop}              # (1) the living
        co = getattr(self, "_cell_owner", None)
        if co:
            keep |= set(co.values())                 # (2) dead owners whose estate is pending
        self._house = {o: r for o, r in h.items() if o in keep}

    # ---- faithful ledger: state-derived emission (WO_faithful-ledger Ф1) ---------- #
    def _ledger_snapshot(self):
        """Ownership + branding as of NOW. Cheap dict/set copies; read-only."""
        return (dict(self._cell_owner),
                set(getattr(self, "_extort_marks", ()) or ()),
                set(getattr(self, "_delegate_marks", ()) or ()))

    def _emit_ledger_events(self, before):
        """Mirror this tick's ownership/branding changes into the EventLog.

        The journal was blind to the thing the colony is actually about: who owned what and
        how it passed on (the E1-Ф0 finding — 30 owners, 55 cells, 7380 kg appropriated, zero
        events). This observer reconstructs it from a diff of PUBLIC state, so canon stays
        byte-identical and no fingerprint moves (Ф0 proved the log is in none of them).

        Inheritance is NOT inferred from the diff: a diff cannot distinguish "kin inherited"
        from "reverted to commons, then re-claimed by kin". `_inherit_dead` records the fact
        as it happens and we drain it here — the log states what the mechanism did, not what
        it looked like afterwards. Marks are diffed over the LIVING set only, so the dead-oid
        GC never masquerades as an un-branding.

        Emission order is fully sorted => the log is deterministic for a given scene."""
        if before is None:
            return
        own0, ext0, del0 = before
        own1 = self._cell_owner
        t = self.t
        # successions first: they explain owner changes the plain diff would call claims
        inherited = {}
        for cell, decedent, heir, mode, root in sorted(self._pending_inherit):
            inherited[cell] = heir
            self.log.emit(t, "inherit", "individual", where=cell, actor=heir,
                          data={"from": int(decedent), "house": int(root), "mode": mode})
        self._pending_inherit = []
        # ownership diff: what is owned now vs on entry
        for cell in sorted(set(own0) | set(own1)):
            a, b = own0.get(cell), own1.get(cell)
            if a == b:
                continue
            if b is None:                       # the estate fell back to the commons
                self.log.emit(t, "lose", "individual", where=cell, actor=int(a))
            elif inherited.get(cell) == b:
                continue                        # already told as `inherit`
            else:                               # seized: newly owned, or taken from another
                self.log.emit(t, "claim", "individual", where=cell, actor=int(b),
                              data=({"from": int(a)} if a is not None else {}))
        # branding diff over the LIVING set (the GC's dead sweep is not an un-branding)
        live = {x.oid for x in self.pop}
        for tag, s0, s1 in (("extort", ext0, set(getattr(self, "_extort_marks", ()) or ())),
                            ("delegate", del0, set(getattr(self, "_delegate_marks", ()) or ()))):
            for oid in sorted((s1 - s0) & live):
                self.log.emit(t, "mark", "individual", actor=int(oid), data={"ledger": tag})
            for oid in sorted((s0 - s1) & live):
                self.log.emit(t, "unmark", "individual", actor=int(oid), data={"ledger": tag})

    def _update_houses(self):
        """Fold this tick's births into self._house (oid -> founder root), mirroring
        sim_inheritance._update_houses exactly: a child inherits its parent's house root.
        Read-only over the logged births, mass-neutral, deterministic — the legal stage-3
        way to give the Polis a lineage without touching canon or the fingerprint. Shared by
        mod-H K2 (debt heirs) and mod-K (inheritance); renamed from _update_debt_houses."""
        ev = self.log.events
        for i in range(self._house_cursor, len(ev)):
            e = ev[i]
            if e.kind == "birth" and e.actor is not None:
                self._house[e.actor] = self._house.get(e.parent, e.parent)
        self._house_cursor = len(ev)

    # ---- mod K: inheritance — dead owner's cells pass to a living bloodline heir ---- #
    def _inherit_dead(self):
        """Before the canon revert, a dead owner's cells pass to its lowest-oid LIVING
        bloodline heir (same _house root). A faithful copy of sim_inheritance._inherit_dead
        (module 25) — the ONLY change is heir_fallback lives on cfg. Semantics = 'live' (owner
        dead = not in self.pop), perception-independent. PURE LEDGER: only _cell_owner is
        reassigned, zero mass-moving ops (gate MK-MASS < 1e-12). heir_fallback=revert deletes
        an heirless cell (-> commons, byte-identical to the canon revert-by-mem for that cell,
        since dead-by-live ⊆ dead-by-mem); escheat consolidates it to the nearest living owner
        of any house. Runs BEFORE super()._do_claims() so a cell handed to a living heir
        survives the canon prune; deterministic order (sorted) => hash-seed-invariant."""
        if not self._cell_owner:
            return
        live = {a.oid for a in self.pop}
        heir_of = {}                          # house root -> lowest-oid living member
        for a in sorted(self.pop, key=lambda x: x.oid):
            heir_of.setdefault(self.house(a.oid), a.oid)
        dead_cells = sorted((c, o) for c, o in self._cell_owner.items() if o not in live)
        living_owned = None
        if self.cfg.heir_fallback == "escheat":
            living_owned = sorted((c, o) for c, o in self._cell_owner.items() if o in live)
        for cell, owner in dead_cells:
            heir = heir_of.get(self.house(owner))
            if heir is not None:                          # living bloodline kin inherits
                self._cell_owner[cell] = heir
                self._inherit_events += 1                 # a real succession (MK-INHERIT-FIRES)
                if self._ledger_on:                       # faithful ledger: record the FACT of
                    self._pending_inherit.append(         # succession, not a guess from a diff
                        (cell, owner, heir, "blood", self.house(owner)))
            elif self.cfg.heir_fallback == "escheat" and living_owned:
                best = min(living_owned,                  # nearest living-owned cell consolidates
                           key=lambda co: (abs(co[0][0] - cell[0]) + abs(co[0][1] - cell[1]),
                                           co[1], co[0]))
                self._cell_owner[cell] = best[1]
                self._inherit_events += 1                 # escheat consolidation counts as firing
                if self._ledger_on:                       # escheat is NOT blood — label it so
                    self._pending_inherit.append(
                        (cell, owner, best[1], "escheat", self.house(owner)))
            else:                                         # extinct line -> commons (baseline)
                del self._cell_owner[cell]

    # ---- mod H виток 2 K3: claim costs mass (body -> soil); else canon verbatim ---- #
    def _do_claims(self):
        """Seizing a cell costs claim_cost of body (mass -> soil, conserving). claim_cost=0
        delegates to the canon _do_claims verbatim => byte-identical (anchor MH2-OFF). With a
        cost, ownership becomes scarce: a pawn too poor to self-fund the seizure must borrow
        (the K3 investment loop). The dead-owner revert is preserved exactly as canon.

        mod K: on the canonical (cost-free) path ONLY, inheritance spares heirs' cells BEFORE
        the canon revert-by-mem. K and K3 (claim_cost>0) are mutually exclusive (gate
        MK-K3-UNTOUCHED) — mixing live-inheritance with the mem-revert here would double-count
        cells; K lives at claim_cost=0, exactly where finding #5 was measured."""
        if self.cfg.claim_cost <= 0.0:
            if self.cfg.inherit_on and getattr(self, "_house", None) is not None:
                self._inherit_dead()          # reassign to living heirs before canon revert
            return super()._do_claims()
        from collections import defaultdict
        if self._cell_owner:                              # revert dead owners' cells (canon rule)
            for c in [c for c, o in self._cell_owner.items() if o not in self.mem]:
                del self._cell_owner[c]
        bycell = defaultdict(list)
        for a in self.pop:
            bycell[(a.i, a.j)].append(a)
        cost = float(self.cfg.claim_cost)
        for cell in sorted(bycell):
            if cell in self._cell_owner:
                continue
            claimant = min(bycell[cell], key=lambda a: a.oid)   # canon claimant = lowest oid
            if claimant.body - cost < DEATH:                     # cannot afford and survive => no claim
                continue
            claimant.body -= cost                                # MASS leaves the body...
            self.soil[cell[0], cell[1]] += cost                  # ...and returns to the soil
            self._cell_owner[cell] = claimant.oid

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
        if self._extort_reputation and a.oid in self._extort_marks:
            return ()                    # Фаза 4: marked (reported by a victim) -> barred henceforth
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
                      and not (self._extort_reputation and a.oid in self._extort_marks)
                      and it.allows(a.oid, EXTORT)]          # marked (Фаза 4) & intent-confirmed
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
            if self._extort_reputation:
                # Фаза 4: the seized owner testifies — every taker on this cell is marked and
                # barred from EXTORT henceforth (belief-only; no mass moves). Guard-independent,
                # so reputation reaches the shadows the sparse guard corps (HG2-2) cannot.
                # mod H §1.5: a BONDED victim (debt stage 3) has lost its standing — its
                # testimony no longer counts. The mark lands only if a NON-bonded victim was
                # seized here. With debt OFF is_bonded is always False => marks as before
                # (byte-identical, MH-OFF).
                if any(not self._debt.is_bonded(v) for v in owners_oids):
                    for tk in takers:
                        self._extort_marks.add(tk.oid)

    # ---- mod G2: DELEGATE / REVOKE — the apex reaps k cells without presence ---- #
    def _appropriate(self):
        """Canon appropriation (module 23), instrumented ONLY when delegate is on to capture
        each owner's tribute income THIS tick. The canon call runs FIRST inside
        AppropriationWorld.step (after all eating/movement), so the body delta across it is
        PURELY tribute (owners gain, non-owners lose); snapshotting is read-only, so the world
        after is byte-identical to canon and delegate_off delegates straight to super().

        faithful ledger (Ф2): the SAME body-delta snapshot also mirrors the appropriation flow
        into the log. Canon publishes only the `_appropriated_total` scalar, so the journal
        could say how much was taken overall and never who lost it or who gained it. The event
        is `scale="deme"` because the mechanism POOLS the take per cell and splits it among
        that cell's owners (the last absorbs the remainder) — a 1:1 "who -> whom" does not
        exist in the rule, the cell is its natural unit. `dm` carries the MAGNITUDE moved in
        that cell; the sign lives in payers/receivers, since one scalar cannot be negative for
        the payers and positive for the receivers at once. As a DERIVED deme event its `dm` is
        a reporting quantity, not a conservation delta — conservation is the canon mechanism's,
        and that is untouched."""
        if not (self._delegate_on or self._ledger_on):
            return super()._appropriate()
        before = {a.oid: a.body for a in self.pop}
        pos = {a.oid: (a.i, a.j) for a in self.pop} if self._ledger_on else None
        super()._appropriate()
        inc, percell = {}, {}
        for a in self.pop:
            d = a.body - before.get(a.oid, a.body)
            if d > 1e-15:                          # only owners gain in _appropriate
                inc[a.oid] = d
            if self._ledger_on and abs(d) > 1e-12:
                payers, receivers = percell.setdefault(pos[a.oid], ([], []))
                (payers if d < 0 else receivers).append((int(a.oid), abs(d)))
        if self._delegate_on:                      # unchanged mod-G2 behaviour
            self._delegate_m_income = inc
        for cell in sorted(percell):
            payers, receivers = percell[cell]
            self.log.emit(self.t, "appropriate", "deme", where=cell,
                          dm=sum(v for _o, v in payers),
                          data={"payers": [[o, v] for o, v in sorted(payers)],
                                "receivers": [[o, v] for o, v in sorted(receivers)]})

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
        if self._delegate_depth > 1:               # Фаза 3: base -> intermediaries -> root
            return self._delegate_chain(t)
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

    def _delegate_chain(self, t):
        """Фаза 3: the meta-tribute cascades base -> B_{d-1} -> ... -> B_1 -> root, share m
        taken at EVERY link (body→body, conserving). The REVOKE tooth gates only the base hop
        (owner->apparatus, marking a reputation-defector as before); the intermediary hops are
        unconditional internal routing. Each intermediary keeps (1-m) of what it forwards, so a
        middle-management strata emerges as depth grows while the root's take decays m^depth."""
        root = self._delegate_root
        live = {a.oid: a for a in self.pop}
        A = live.get(root)
        if A is None:                              # root dead -> the whole chain lapses
            return
        chain = self._delegate_chain_ids           # [B_1 (near root) .. B_{d-1} (near base)]
        bottom = chain[-1]
        Bbot = live.get(bottom)
        chain_set = set(chain)
        tooth = self.cfg.revoke_tooth
        guard_cells = ({(a.i, a.j) for a in self.pop if a.oid in self._delegate_enforcer_ids}
                       if tooth == "enforcer" else frozenset())
        recv = {}                                  # this-tick gross received per chain node
        # ---- base owners remit m·income to the bottom intermediary (tooth-gated) ----------
        if Bbot is not None:
            for oid in sorted(self._delegate_m_income):
                if oid == root or oid in self._delegate_enforcer_ids or oid in chain_set:
                    continue                       # apex, its guards, and intermediaries aren't base
                B = live.get(oid)
                if B is None:
                    continue
                if not self._delegate_remit(B, tooth, guard_cells):
                    self._delegate_defections += 1
                    if tooth == "reputation":
                        self._delegate_marks.add(oid)
                    continue
                amount = self._delegate_m * self._delegate_m_income[oid]
                if amount > B.body:
                    amount = B.body
                if amount <= 0.0:
                    continue
                B.body -= amount
                Bbot.body += amount
                recv[bottom] = recv.get(bottom, 0.0) + amount
                self._delegate_events.append((t, oid, round(amount, 9)))
                self.log.emit(t, "delegate_remit", "individual", where=(B.i, B.j), actor=oid,
                              dm=amount, data={"root": root, "via": bottom,
                                               "amount": round(amount, 6)})
        # ---- intermediaries forward m of what they got, bottom -> top (unconditional) -----
        for k in range(len(chain) - 1, -1, -1):    # child indices are > parent, so process down
            node = chain[k]
            got = recv.get(node, 0.0)
            if got > 0.0:
                self._delegate_chain_recv[node] = self._delegate_chain_recv.get(node, 0.0) + got
            N = live.get(node)
            if N is None or got <= 0.0:
                continue
            parent_oid = root if k == 0 else chain[k - 1]
            P = live.get(parent_oid)
            if P is None:                          # broken link -> the mass stays at this node
                continue
            amount = self._delegate_m * got
            if amount > N.body:
                amount = N.body
            if amount <= 0.0:
                continue
            N.body -= amount
            P.body += amount
            if parent_oid == root:
                self._delegate_flow += amount      # only mass reaching the apex is A_flow
            else:
                recv[parent_oid] = recv.get(parent_oid, 0.0) + amount
            self._delegate_events.append((t, node, round(amount, 9)))
            self.log.emit(t, "delegate_remit", "individual", where=(N.i, N.j), actor=node,
                          dm=amount, data={"root": root, "to": parent_oid,
                                           "amount": round(amount, 6)})

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
        # mod H (DEBT): the debt state enters the blob ONLY once a loan has issued; OFF
        # (and asleep-before-first-loan) returns b"", so the term is byte-identical to mod
        # G2 and every anchor is holy (gate MH-OFF).
        blob += self._debt.fingerprint_blob()
        # mod H3: the public-good/punishment state; empty until the first round => OFF is
        # byte-identical (gate MH3-OFF).
        blob += self._pg.fingerprint_blob()
        # mod J (frailty): the block table; empty (b"") when OFF => byte-identical to canon.
        # Appended LAST so the OFF empty term leaves every prior anchor's bytes untouched
        # (gate MJ-OFF); when ON it pins the block state so MJ-REPRO catches non-determinism.
        blob += self._frailty.fingerprint_blob()
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
