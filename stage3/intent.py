"""
intent.py — mod G (виток 1): the intent layer — триггер → интент → взаимодействие → результат.

Until now the pawn met matter BLINDLY: threshold -> action. Every artifact verb of mod F
fires the instant its physical gate opens — accumulation with no intent (that was vitok
1-2's QUESTION, and it was answered: blind surplus does make a stratum, and geography
routes the flow). mod G inserts a CHOICE between the world-scan and the physics WITHOUT
touching the physics: the same gates, the same passes, the same transfers — but before
each action the actor's intent layer may decline it.

DESIGN DECISIONS (Stan, 2026-07-07/08 — fixed, do not reopen):
  * scope = ARTIFACT verbs only; movement and eating stay canonical (intent over
    movement is a future vitok).
  * intent = a SUBSET of the tick's affordances, not a single verb — the reflex policy
    then equals the status quo bit-for-bit (the double OFF-gate).
  * theta = 0.5 as честный дизайн: the average pawn does NOT read (BASELINE READ score
    ~0.29) — utility is ALLOWED to diverge from reflex radically; дыры ищем прогонами.
  * REFRESH is ambient physics (presence keeps culture loud — не акт); intent gates
    ONLY the absorption (the read into known_method).
  * outcome memory = counters {verb: [ok, denied]} per pawn; виток 1 is PURE
    MEASUREMENT — the counters accumulate and are logged, they feed NO score (feedback
    = G2, so 'character as fate' and 'experience as fate' stay attributable apart).
  * the critic is an OBSERVER (read-only metrics over counters/denies); the feedback
    critic is G2's first item.
  * utility reads the RAW structural axes (personality is frozen => a pawn's confirmed
    verb-set is fixed for life — clean HGG3 attribution). The phase-effective axes
    (Pawn.effective_caution / effective_K) are a single-seam switch left for a later
    vitok, deliberately NOT used here.

THREE SOURCES OF DENY (урок (к): не склеивать — different phenomena):
  (а) hallucination — a live mind asks a verb OUTSIDE the affordances: the typed
      «нельзя» (the CL-gate pattern), the world does not mutate;
  (б) race — the affordance stood at scan, but an earlier-oid pawn changed the world
      (drank the store, drained the soil, took the cell): intent wanted, physics vetoed;
  (в) self_preempt — the pawn's OWN earlier mint this tick reset its dwell / spent its
      body (the capital > store > vessel cascade): it displaced itself.
The желание/возможность gap is thus a measured quantity, split by mechanism.

POLICIES (PolisConfig.intent_policy):
  "off"     the layer is not built at all — zero objects, zero new computation in the
            hot path; byte-identical to vitok 2 (gate MG-OFF).
  "reflex"  confirms EVERY action at execution (not just scanned affordances — a verb
            physics enables mid-tick, e.g. copying a vessel written THIS tick, stays
            enabled). The scan runs and measures; it must not perturb the world:
            physically ≡ off (gate MG-REFLEX, the honest purity test of the layer).
  "utility" deterministic filter through the STRUCTURAL personality axes (mod A):
            score(verb) = Σ w·axis over the mapping below; verb confirmed for life iff
            score >= theta. Personality touches the material world for the first time.
  "live"    a mind confirms a SUBSET via the typed protocol (the C-LIVE dictionary
            grows object verbs when real minds are wired — a separate session). Vitok 1
            ships the interface + mock minds for the gates (the B-INERT/B-REPLAY
            pattern); requests are via-logged, replay is bit-exact and never needs a key.

THE UTILITY MAPPING (approved 2026-07-08; axes are the FACTUAL personality.py five —
hc=hunger_caution, dl=deception_lean, aK=(attention_K-4)/28, tg=trust_gate,
ss=stake_sensitivity; weights sum to 1 per verb, so score ∈ [0,1] and theta compares
across verbs):

    WRITE_VESSEL     .5·(1-hc) + .5·(1-tg)          the bold and the distrustful write originals
    COPY_VESSEL      .4·tg + .3·aK + .3·(1-hc)      the trusting, attentive (and still bold) re-inscribe
    READ_VESSEL      .6·aK + .4·tg                  the free verb of belief: attention + trust
    MINT_STORE       .6·hc + .4·ss                  the store is death-fear materialised
    MINT_CAPITAL     .5·(1-hc) + .5·(1-ss)          the secure freeze tools: no edge-fear, no pressure
    DRAW_STORE       .4·ss + .3·hc + .3·dl          the pressed, the careful — and the free-rider
    HARVEST_CAPITAL  .4·ss + .3·dl + .3·aK          the pressed free-rider who noticed the tool

hunger_caution splits the material world in two (suppresses culture, feeds safety);
deception_lean gets its material analogue (free-riding); trust_gate divides originals
from copies — all directly testable in HGG3.

CONSERVATION & ANCHORS. The layer NEVER touches mass: it only chooses between transfers
the physics already allows (gate MG-mass: drift < 1e-9). Intent state (counters + deny
digest) enters the fingerprint blob ONLY under utility/live — the same conditional-
suffix discipline as the vitok-2 kind term, so the OFF/REFLEX worlds are byte-identical
to vitok 2 and the anchors are holy (gates MG-OFF / MG-REFLEX).

Deterministic; pure stdlib. Pi5/Win11 friendly.
"""
from __future__ import annotations

# ---- the verb registry (TRIGGER) — canonical order, doc §3.1 ---------------- #
MINT_CAPITAL = "MINT_CAPITAL"
MINT_STORE = "MINT_STORE"
WRITE_VESSEL = "WRITE_VESSEL"
READ_VESSEL = "READ_VESSEL"
COPY_VESSEL = "COPY_VESSEL"
DRAW_STORE = "DRAW_STORE"
HARVEST_CAPITAL = "HARVEST_CAPITAL"
# mod G2 (control without ownership): the FIRST non-artifact verb — a conserving body→body
# seizure from a co-present owner, the reverse-signed tribute (module 23 inverted). Its
# affordance comes from the WORLD (Polis.intent_extra_affordances), not the artifact field,
# so intent.py stays the single intent authority while the mechanic lives in stage3/polis.
# Appended at the END of VERBS: when extort is OFF the verb is never counted, so the
# fingerprint blob (which lists only counted verbs) is byte-identical and the mod-G anchors
# stand (gate MG2-OFF).
EXTORT = "EXTORT"

VERBS = (MINT_CAPITAL, MINT_STORE, WRITE_VESSEL, READ_VESSEL,
         COPY_VESSEL, DRAW_STORE, HARVEST_CAPITAL, EXTORT)

# deny reasons (урок (к): three mechanisms, never conflated in the data)
DENY_HALLUCINATION = "hallucination"   # (а) the mind asked outside the menu
DENY_RACE = "race"                     # (б) an earlier oid changed the world
DENY_SELF_PREEMPT = "self_preempt"     # (в) own earlier mint this tick displaced it

# ---- the utility mapping (INTENT) — (weight, axis, inverted) triples -------- #
UTILITY_W = {
    MINT_CAPITAL:    ((0.5, "hc", True), (0.5, "ss", True)),
    MINT_STORE:      ((0.6, "hc", False), (0.4, "ss", False)),
    WRITE_VESSEL:    ((0.5, "hc", True), (0.5, "tg", True)),
    READ_VESSEL:     ((0.6, "aK", False), (0.4, "tg", False)),
    COPY_VESSEL:     ((0.4, "tg", False), (0.3, "aK", False), (0.3, "hc", True)),
    DRAW_STORE:      ((0.4, "ss", False), (0.3, "hc", False), (0.3, "dl", False)),
    HARVEST_CAPITAL: ((0.4, "ss", False), (0.3, "dl", False), (0.3, "aK", False)),
    # EXTORT is the PREDATORY verb: deception_lean-led (its second material analogue after
    # DRAW_STORE's free-riding), plus the bold (low caution) and the pressed. Weights sum to
    # 1 so score ∈ [0,1] compares across verbs at the same theta (proposal, flagged to Stan
    # at stop-point 1.6 like rho_extort — the vitok-1 seven were approved, this row is new).
    EXTORT:          ((0.5, "dl", False), (0.3, "hc", True), (0.2, "ss", False)),
}


def utility_axes(p) -> dict:
    """The FACTUAL five structural axes of personality.py, normalised to [0,1].
    attention_K (4..32) maps as (K-4)/28. Axis names are personality.py's — не выдуманы."""
    return {"hc": p.hunger_caution, "dl": p.deception_lean,
            "aK": (p.attention_K - 4) / 28.0, "tg": p.trust_gate,
            "ss": p.stake_sensitivity}


def utility_score(p, verb) -> float:
    ax = utility_axes(p)
    return sum(w * ((1.0 - ax[k]) if inv else ax[k])
               for (w, k, inv) in UTILITY_W[verb])


def utility_ok(p, theta) -> frozenset:
    """The pawn's lifelong confirmed verb-set: personality is frozen, so this is a pure
    function of the vector — the SAME oid classifies identically across runs (the base
    of the HGG1/HGG3 reflex-vs-utility comparison)."""
    return frozenset(v for v in VERBS if utility_score(p, v) >= theta)


class IntentLayer:
    """The intent layer of one Polis. Owned by ArtifactField (field.intent), built by
    Polis ONLY when intent_policy != "off". Pure belief state: it never reads or writes
    body/soil/plant/artifact mass — it only answers allows() before an already-gated
    action and counts outcomes. The affordance scan calls the SAME gate predicates the
    passes use (the single source of truth, refactored into ArtifactField._can_*)."""

    def __init__(self, policy: str, theta: float = 0.5, mind=None, replay=None):
        if policy not in ("reflex", "utility", "live"):
            raise ValueError(f"intent_policy must be reflex|utility|live, got {policy!r}")
        if policy == "live" and mind is None and replay is None:
            raise ValueError("live policy needs a mind or a replay log (gates never need a key)")
        self.policy = policy
        self.theta = float(theta)
        self.mind = mind                 # live: .decide(world, t, affordances) -> {oid: verbs}
        self.replay = replay             # live: {t: {oid: [verbs]}} — requests via-log
        # per-tick state (rebuilt by scan)
        self.affordances = {}            # oid -> tuple(verbs) — возможность at scan
        self.approved = {}               # live only: oid -> frozenset(verbs) confirmed
        self._minted = set()             # oids that minted THIS tick (в: self-preemption)
        self._t = 0
        # accumulated belief state (never mass)
        self.counters = {}               # oid -> {verb: [ok, denied]}  (§3.4)
        self.denies = []                 # (t, oid, verb, reason)
        self.unmet = {}                  # utility: oid -> {verb: ticks wanted-not-afforded}
        self.request_log = {}            # live via-log: t -> {oid: [verbs requested]}
        self._util_ok = {}               # oid -> frozenset (lifelong; personality frozen)

    # ---- TRIGGER: the affordance scan (pure reads; MG-REFLEX guards purity) - #
    def scan(self, field, world, pop_sorted, t):
        """Build, per pawn (sorted oid), the tick's affordances through the field's OWN
        gate predicates, then let the policy confirm. Called by ArtifactField.tick right
        after the dwell update, before the first pass — so 'возможность' is the world as
        the tick's physics is about to meet it. MUST NOT mutate anything."""
        self._t = t
        self._minted.clear()
        aff = {}
        has_cap = ({(art.i, art.j) for art in field.artifacts if art.kind == "capital"}
                   if field.capital_on else ())
        occupied = field._vessel_occupied()
        readable = field._readable_bycell()
        stores = field._stores_bycell() if field.store_on else {}
        caps = field._capitals_bycell() if field.capital_on else {}
        for a in pop_sorted:
            cell = (a.i, a.j)
            vs = []
            if field.capital_on and cell not in has_cap and field._can_capitalize(a):
                vs.append(MINT_CAPITAL)
            if field.store_on and field._can_store(a):
                vs.append(MINT_STORE)
            if cell not in occupied and field._can_write(a):
                vs.append(WRITE_VESSEL)
            here = readable.get(cell)
            if here:
                seen = field._read_seen.get(a.oid, ())
                if any(art.aid not in seen for art in here):
                    vs.append(READ_VESSEL)          # an UNSEEN readable carrier here
                if field._can_write(a):
                    vs.append(COPY_VESSEL)
            if field.store_on and field._can_draw(a):
                sh = stores.get(cell)
                if sh and any(art.mass > 0.0
                              and field._access_ok(world, art, a, field.store_access)
                              for art in sh):
                    vs.append(DRAW_STORE)
            if field.capital_on:
                ch = caps.get(cell)
                if ch:
                    cm = sum(ar.mass for ar in ch
                             if field._access_ok(world, ar, a, field.capital_access))
                    if cm > 0.0 and float(world.soil[a.i, a.j]) > 0.0:
                        vs.append(HARVEST_CAPITAL)
            # mod G2: non-artifact verbs (EXTORT, later DELEGATE...) — the WORLD contributes
            # affordances through a hook. Absent hook / feature OFF => empty => the artifact
            # menu is untouched and OFF stays byte-identical.
            extra = getattr(world, "intent_extra_affordances", None)
            if extra is not None:
                vs.extend(extra(a))
            aff[a.oid] = tuple(vs)
        self.affordances = aff
        # ---- INTENT: the policy confirms ------------------------------------ #
        if self.policy == "utility":
            for a in pop_sorted:
                ok = self._util_ok.get(a.oid)
                if ok is None:
                    ok = utility_ok(world.pawn(a.oid).personality, self.theta)
                    self._util_ok[a.oid] = ok
                # critic-observer: desire without possibility (HGG2's surface) — the
                # rich landless WANT to mint but are not settled. Observer data only:
                # never in the blob, never in a score (feedback = G2).
                want_not_have = ok.difference(aff[a.oid])
                if want_not_have:
                    u = self.unmet.setdefault(a.oid, {})
                    for v in want_not_have:
                        u[v] = u.get(v, 0) + 1
        elif self.policy == "live":
            if self.replay is not None:
                requests = self.replay.get(t, {})
            else:
                requests = self.mind.decide(world, t, dict(aff))
            self.request_log[t] = {int(o): list(requests[o]) for o in sorted(requests)}
            approved = {}
            for oid in sorted(requests):
                have = set(aff.get(oid, ()))
                ok = []
                for v in requests[oid]:
                    if v in have:
                        ok.append(v)
                    else:
                        # (а) the mind's hallucination: typed «нельзя», world untouched
                        self._count(oid, v)[1] += 1
                        self.denies.append((t, oid, v, DENY_HALLUCINATION, None))
                approved[oid] = frozenset(ok)
            self.approved = approved
        # reflex confirms at execution (allows() below) — nothing to prepare

    # ---- INTERACTION: the passes ask before each action ---------------------- #
    def allows(self, oid, verb) -> bool:
        """Is this verb confirmed for this actor? reflex: everything (physically ≡ off —
        including opportunities physics opens mid-tick, e.g. copying a vessel written
        this very tick). utility: the lifelong score-set. live: the mind's confirmed
        subset of THIS tick's menu. Pure — no counting here (note_ok counts on the
        actual execution)."""
        if self.policy == "reflex":
            return True
        if self.policy == "utility":
            ok = self._util_ok.get(oid)
            return ok is not None and verb in ok
        return verb in self.approved.get(oid, ())

    def note_ok(self, oid, verb):
        """The action EXECUTED (called right after the mutation) — RESULT, ok++."""
        self._count(oid, verb)[0] += 1

    def note_gate_fail(self, oid, verb, cell=None):
        """A physical gate refused an actor at execution. A deny is logged ONLY if the
        actor both WANTED the verb (policy allows) and COULD at scan (affordance stood):
        (в) self_preempt if its own mint this tick displaced it, else (б) race — an
        earlier-oid pawn changed the world. Everything else is silence (either the
        policy filtered it, or it was never possible — not a frustration event). `cell` is
        the LOCUS (кто/где отказал) — recorded in the deny record for the reputation/
        DELEGATE metrics; it never enters the fingerprint digest (keyed by verb/reason
        only), so loci are observer-state and the anchors stay byte-identical."""
        if verb not in self.affordances.get(oid, ()):
            return
        if not self.allows(oid, verb):
            return
        reason = DENY_SELF_PREEMPT if oid in self._minted else DENY_RACE
        self._count(oid, verb)[1] += 1
        self.denies.append((self._t, oid, verb, reason, cell))

    def _count(self, oid, verb):
        c = self.counters.setdefault(oid, {})
        rec = c.get(verb)
        if rec is None:
            rec = c[verb] = [0, 0]
        return rec

    # ---- fingerprint contribution (§3.5: ONLY utility/live; empty otherwise) - #
    def fingerprint_blob(self) -> bytes:
        """Intent state enters the blob ONLY when the policy actually shapes the world
        (utility/live) — the vitok-2 conditional-suffix discipline: off has no layer,
        reflex returns b'', so the OFF/REFLEX fingerprint terms are byte-identical to
        vitok 2 and the anchors stand. Counters + a deny digest are enough to prove a
        replay (denies/oks derive deterministically from the same stream)."""
        if self.policy == "reflex":
            return b""
        if not self.counters and not self.denies:
            return b""
        parts = []
        for oid in sorted(self.counters):
            c = self.counters[oid]
            parts.append(f"{oid}:" + ",".join(f"{v}={c[v][0]}/{c[v][1]}"
                                              for v in VERBS if v in c))
        dd = {}
        for rec in self.denies:                       # (t, oid, verb, reason[, cell])
            key = (rec[2], rec[3])                     # digest keyed by verb/reason ONLY —
            dd[key] = dd.get(key, 0) + 1               # loci (rec[4]) stay observer-state
        dpart = ";".join(f"{v}:{r}={n}" for (v, r), n in sorted(dd.items()))
        head = f"||INTENT||{self.policy}:{self.theta:.6f}||"
        return (head + "#".join(parts) + "||DENY||" + dpart).encode()

    # ---- RESULT: the critic-observer (read-only; feedback = G2) -------------- #
    def frustration(self) -> dict:
        """oid -> denied/(ok+denied) over all verbs — the frustration index. Honest
        bases (historical classes, lifetime integrals) are the RUNNER's job: it holds
        the world histories; the layer only counts."""
        out = {}
        for oid, cv in self.counters.items():
            ok = sum(rec[0] for rec in cv.values())
            den = sum(rec[1] for rec in cv.values())
            out[oid] = (den / (ok + den)) if (ok + den) else float("nan")
        return out

    def deny_breakdown(self) -> dict:
        """(verb, reason) -> count — the три источника, kept apart in the data."""
        out = {}
        for rec in self.denies:                       # (t, oid, verb, reason[, cell])
            key = (rec[2], rec[3])
            out[key] = out.get(key, 0) + 1
        return out

    def deny_loci(self, verb=None) -> dict:
        """LOCUS breakdown (кто/где отказал): cell -> deny count, optionally for one verb.
        Observer-only (never in the blob) — infrastructure for the reputation smychka and
        the DELEGATE owner_gap. A deny with no recorded cell is skipped."""
        out = {}
        for rec in self.denies:
            cell = rec[4] if len(rec) > 4 else None
            if cell is None or (verb is not None and rec[2] != verb):
                continue
            out[cell] = out.get(cell, 0) + 1
        return out

    def unmet_mint(self, oid) -> int:
        """Ticks this pawn WANTED to mint wealth (store/capital) but had no affordance —
        finding 8 through the pawn's own eyes («богатство без места не кристаллизуется»)."""
        u = self.unmet.get(oid)
        if not u:
            return 0
        return u.get(MINT_STORE, 0) + u.get(MINT_CAPITAL, 0)


# ---- mock minds for the live gates (the B-INERT / B-REPLAY pattern) --------- #
class MockReflexMind:
    """Confirms exactly the menu — the interface without judgment. live(mock-reflex)
    is NOT ≡ reflex: it confirms only what stood at SCAN, while reflex also passes
    opportunities physics opens mid-tick — the gap is itself a measurement."""

    def decide(self, world, t, affordances):
        return {oid: tuple(vs) for oid, vs in affordances.items()}


class MockHallucinatorMind:
    """Asks the impossible: for every pawn, the menu PLUS verbs NOT on it. The typed
    «нельзя» must fire (deny reason=hallucination) and the world must not mutate
    (gate MG-deny: substrate fingerprint identical to the honest mind's). Deterministic:
    a pure function of the affordances — replays via-log bit-exact."""

    def __init__(self, extra=(MINT_CAPITAL, HARVEST_CAPITAL)):
        self.extra = tuple(extra)

    def decide(self, world, t, affordances):
        out = {}
        for oid, vs in affordances.items():
            out[oid] = tuple(vs) + tuple(v for v in self.extra if v not in vs)
        return out
