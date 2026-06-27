"""
sim_coalition.py — collective sanction (module 19): the first *joint* political verb.

Every layer so far acts ALONE. Communication (11), polarization (13), and the whole
accountability vertical (14–17) all change THE RECEIVER'S OWN belief: gossip averages
others' reports into *my* trust (15), warn takes the min (16), evidence waits for *K*
credible reports (17) — then *I* act on *my* updated trust. The target's reach drops
only INDIRECTLY, because more receivers privately distrust it. And module 18 added an
individual *motive* (fear of death). No agent has ever taken a JOINT action that
changes the world for a non-consenting third party.

This module installs the minimal form of that political verb (the book's ВСТАВКА
13–14: alpha/coalition → institutionalization). The new verb is ENFORCEMENT, not
updating:

  14–17 (persuasion):  others' reports move *my* trust; I then act on *my* belief.
                       A credulous agent keeps believing the liar and keeps getting
                       redirected.
  19 (enforcement):    when a QUORUM of co-located agents have each gated target `T`
                       (trust `< τ_sanction`), `T`'s claims are BLOCKED from entering
                       any nearby listener's perspective this tick — *even a listener
                       who personally still trusts `T`*. The collective overrides the
                       individual; the group's verdict becomes binding on a non-member.

It has teeth because power here flows through NARRATIVE: a lie redirects the audience's
foraging → the liar/elite extracts. Silencing the liar's voice cuts the actual
extraction channel. The collective sanction that bites in a narrative-driven world is
control of WHO GETS HEARD.

`CoalitionWorld(TrustCommWorld)` overrides only the claim-absorption seam
(`_absorb_claim`, the same behaviour-preserving seam module 14 uses). Coalitions form
from ALREADY-CAUGHT liars — the existing per-listener `trust[A][T]` the trust layer
maintains; no new signal is invented. The quorum is a deterministic, order-independent
count of co-located gated agents.

  * `A == T` (the speaker rating itself) is EXCLUDED from the count — a speaker is not
    a witness against its own honesty (and `trust[T][T]` defaults to 1.0 anyway, so it
    could never gate). Documented, like evidence's `A == S` choice.
  * Suppression is a FULL block: a sanctioned claim is neither recorded nor acted on
    nor later verified — it never enters the listener's perspective. This is what makes
    enforcement different from updating.

SANCTION-OFF (`q_quorum=None`, i.e. quorum = ∞): the seam is a PURE no-op — every
`_absorb_claim` delegates straight to the trust layer, so the world is `TrustCommWorld`
byte-for-byte (proven against the trust self-check `6f31f775912f5e96`).

SMEAR harness (reusing the module 16/17 designated-smearer scaffold): a lying elite of
`M` agents fabricates total distrust (0.0) of an honest rival to MANUFACTURE a false
quorum it never earned — `lone` (M=1) vs `coord` (M=Q). E2 asks whether the quorum
protects the innocent or de-platforms it.

Conservation is trivial (claims carry no matter; the conserved `eat ≤ avail/n` split
and the death rule are untouched) but asserted anyway. No new RNG; the quorum count
(set-count + threshold) is order-independent. Pure stdlib + numpy; no LLM, no network.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

import numpy as np

from sim_eventlog import EventLog, SEED
from sim_comm import DAYS, THINK_EVERY, run as run_comm
from sim_comm_llm import MockStrategicPolicy, ReplayPolicy
from sim_trust import (
    TrustCommWorld, run_off, elite_gap, trust_in_speaker_kinds, TAU_TRUST,
    REGIMES as TRUST_REGIMES, fingerprint as trust_fingerprint,
)

# τ below which a co-located agent counts as having "caught" T (= the trust gate τ;
# a definition, not a tuned knob — an agent that no longer acts on T's word is exactly
# one that has gated T).
TAU_SANCTION = TAU_TRUST

# quorum sweep (SANCTION-OFF is q_quorum=None; "majority" = majority-of-present)
Q_SWEEP = (2, 3, "majority")

# measurement knobs (auxiliary; touch no dynamics)
SNAP_EVERY = 12        # days between stratification snapshots (E3)
TOPK_FRAC = 0.20       # top stratum = richest / most-heard 20%

# protected fingerprints this module must leave intact (asserted in the demo)
CANON_COMM = "a91480561b6de937"      # sim_comm deceptive (no lower seam)
CANON_TRUST = "6f31f775912f5e96"     # sim_trust metric self-check


# --------------------------------------------------------------------------- #
#  The enforcing world                                                         #
# --------------------------------------------------------------------------- #
class CoalitionWorld(TrustCommWorld):
    """TrustCommWorld with a collective-sanction seam over claim absorption.

    Before listener `B` ingests speaker `T`'s claim, count the distinct agents `A`
    co-located with `B` (the same cell `T` broadcast in) for which the *effective*
    distrust toward `T` is below `tau_sanction` (`A != T`). If that count reaches the
    quorum, `T` is sanctioned at this locale this tick and `B` does NOT ingest the
    claim — regardless of `trust[B][T]`. Below quorum, `B` ingests exactly as in the
    trust layer.

    `q_quorum`: None -> SANCTION-OFF (pure no-op); an int -> fixed quorum; "majority"
    -> majority of the present agents. `smear_mode` in {None, 'lone', 'coord'} with
    `n_smearers` designates the `M` lowest-oid founder speakers as a lying elite that
    fabricates a false quorum (see `_effective_distrust`)."""

    def __init__(self, log, seed=SEED, regime="deceptive", policy=None, focal=None,
                 q_quorum=None, tau_sanction=TAU_SANCTION,
                 smear_mode=None, n_smearers=0):
        self.q_quorum = q_quorum
        self.tau_sanction = tau_sanction
        self.smear_mode = smear_mode
        self._n_smearers = n_smearers
        self._cell_cache = {}
        self._cell_cache_t = -1
        self.exposures = defaultdict(int)     # T -> # remote-claim listener exposures
        self.suppressed = defaultdict(int)    # T -> # of those blocked by a quorum
        super().__init__(log, seed=seed, regime=regime, policy=policy, focal=focal)
        # designate smearers deterministically: the M lowest-oid founder speakers (the
        # lying elite). Empty unless a smear regime is requested.
        m = n_smearers if smear_mode in ("lone", "coord") else 0
        self._smearers = set(sorted(self.speaker)[:m])

    # ---- co-location: the cell membership a quorum is counted over ---------- #
    def _cell_members(self, i, j):
        """Agents currently in cell (i, j). Cached per tick: positions are fixed
        through the whole speak phase (movement is later in the cognition phase), and
        the cache is rebuilt from `self.pop` after the tick's death/birth — so it
        matches the speaking loop's `here` membership exactly. Read-only."""
        if self._cell_cache_t != self.t:
            m = defaultdict(list)
            for a in self.pop:
                m[(a.i, a.j)].append(a)
            self._cell_cache = m
            self._cell_cache_t = self.t
        return self._cell_cache.get((i, j), [])

    # ---- the smear hook (mirrors warn/evidence `_gossip_report`) ------------ #
    def _effective_distrust(self, A, t_oid):
        """How much agent `A` distrusts speaker `T` for quorum counting. Genuine by
        default: `A`'s verified trust in `T` (1.0 if unrated — full benefit of the
        doubt). A designated smearer fabricates total distrust (0.0) toward any rival
        speaker that is not itself a smearer — manufacturing quorum votes it never
        earned. Liars already collect genuine votes, so the smear's marginal target is
        the honest competitor (E2). Deterministic."""
        if (A.oid in self._smearers and t_oid in self.speaker
                and t_oid not in self._smearers):
            return 0.0
        # read-only; a newborn not yet ensured by the trust layer this tick has caught
        # no one -> full trust (1.0), so it never gates.
        return self.trust.get(A.oid, {}).get(t_oid, 1.0)

    def _quorum(self, n_present):
        return n_present // 2 + 1 if self.q_quorum == "majority" else int(self.q_quorum)

    def _sanctioned(self, t_oid, members):
        """True iff at least a quorum of co-located agents (A != T) have effective
        distrust in T below tau_sanction. The count is order-independent."""
        q = self._quorum(len(members))
        w = sum(1 for A in members
                if A.oid != t_oid
                and self._effective_distrust(A, t_oid) < self.tau_sanction)
        return w >= q

    # ---- listener seam: enforcement, then the trust path -------------------- #
    def _absorb_claim(self, L, B, claim, true_B, spk):
        # SANCTION-OFF or self-cell -> delegate verbatim to the trust layer (no-op).
        if self.q_quorum is not None and B != (L.i, L.j):
            self.exposures[spk.oid] += 1
            if self._sanctioned(spk.oid, self._cell_members(L.i, L.j)):
                # collective override: the claim is blocked from entering B's
                # perspective entirely — not recorded, not acted on, not later
                # verified — even if B personally still trusts T.
                self.suppressed[spk.oid] += 1
                return
        super()._absorb_claim(L, B, claim, true_B, spk)

    # ---- measurement helpers (auxiliary: no matter, no RNG) ----------------- #
    def heard_fraction(self, oids):
        """Mean over the given speakers of (1 - suppressed/exposures); a speaker never
        exposed to a quorum is skipped. 1.0 = always heard, 0.0 = fully silenced."""
        fr = []
        for o in sorted(oids):
            e = self.exposures.get(o, 0)
            if e > 0:
                fr.append(1.0 - self.suppressed.get(o, 0) / e)
        return float(np.mean(fr)) if fr else float("nan")

    def speaker_body(self, oids):
        live = [a for a in self.pop if a.oid in oids]
        return float(np.mean([a.body for a in live])) if live else float("nan")


# --------------------------------------------------------------------------- #
#  Running a condition                                                          #
# --------------------------------------------------------------------------- #
def run_coalition(regime, q_quorum=None, smear_mode=None, n_smearers=0,
                  mock=False, days=DAYS, snap_every=SNAP_EVERY):
    """Run a CoalitionWorld. `mock=True` drives speakers with MockStrategicPolicy
    (the self-interested speaker that produces a mix of honest and liar realized
    behaviour — needed so a smear has an honest target); otherwise the regime decides
    claims. Returns (world, log, snapshots), snapshots {oid: body} every snap_every d."""
    log = EventLog()
    kw = dict(q_quorum=q_quorum, smear_mode=smear_mode, n_smearers=n_smearers)
    if mock:
        w = CoalitionWorld(log, seed=SEED, regime="deceptive",
                           policy=MockStrategicPolicy(), focal=None, **kw)
    else:
        w = CoalitionWorld(log, seed=SEED, regime=regime, **kw)
    snaps = []
    for _ in range(days):
        w.step()
        if w.t % snap_every == 0:
            snaps.append({a.oid: a.body for a in sorted(w.pop, key=lambda x: x.oid)})
    return w, log, snaps


# --------------------------------------------------------------------------- #
#  Metric helpers                                                              #
# --------------------------------------------------------------------------- #
def gini(xs):
    """Gini coefficient of a non-negative distribution (0 = equal, ->1 = one holds
    all). Sorted; order-independent and deterministic."""
    xs = sorted(float(x) for x in xs)
    n = len(xs)
    if n == 0:
        return float("nan")
    tot = sum(xs)
    if tot <= 0.0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return (2.0 * cum) / (n * tot) - (n + 1.0) / n


def body_persistence(snaps, frac=TOPK_FRAC):
    """Mean Jaccard overlap of the richest-`frac` (by reserve) oid sets between
    consecutive back-half snapshots. High -> the same individuals stay on top."""
    if len(snaps) < 3:
        return float("nan")
    back = snaps[len(snaps) // 2:]
    sets = []
    for snap in back:
        oids = sorted(snap, key=lambda o: (snap[o], o), reverse=True)
        k = max(1, int(frac * len(oids)))
        sets.append(set(oids[:k]))
    js = [len(a & b) / len(a | b) for a, b in zip(sets, sets[1:]) if (a | b)]
    return float(np.mean(js)) if js else float("nan")


def classify_speakers(log):
    """Each speaker -> True if it lied in the majority of its own claims (a liar),
    False if mostly honest. From the realized claim log."""
    truth, total = defaultdict(int), defaultdict(int)
    for e in log.events:
        if e.kind == "communication":
            total[e.actor] += 1
            truth[e.actor] += int(e.data.get("truthful", True))
    return {s: (truth[s] / total[s] < 0.5) for s in total}


def _world_metrics(w, log, snaps):
    cls = classify_speakers(log)
    liars = {s for s, isliar in cls.items() if isliar}
    honest = {s for s, isliar in cls.items() if not isliar}
    return {
        "gap": elite_gap(w),
        "be": float(w.belief_gap()),
        "liar_heard": w.heard_fraction(liars),
        "honest_heard": w.heard_fraction(honest),
        "honest_body": w.speaker_body(honest),
        "gini": gini([a.body for a in w.pop]),
        "persist": body_persistence(snaps),
        "n_suppressed": int(sum(w.suppressed.values())),
        "n_exposed": int(sum(w.exposures.values())),
    }


# --------------------------------------------------------------------------- #
#  The experiment sweep -> E1/E2/E3                                            #
# --------------------------------------------------------------------------- #
# E1/E3: brazen-liar regime across the quorum gradient (incl. OFF)
E13_CONDS = (("off", None), ("Q2", 2), ("Q3", 3), ("Qmaj", "majority"))
# E2: mock-strategic (has honest targets) at a fixed quorum, no-smear vs lone vs coord
E2_Q = 2
E2_CONDS = (("nosmear", None, 0), ("lone", "lone", 1), ("coord", "coord", E2_Q))


def compute_metrics(days=DAYS):
    out = {}
    # E1 + E3 — deceptive (the brazen / volume liar), quorum gradient
    for tag, q in E13_CONDS:
        w, log, snaps = run_coalition("deceptive", q_quorum=q, days=days)
        out[("e13", tag)] = _world_metrics(w, log, snaps)
    # E2 — mock-strategic at Q=2: does the quorum silence the honest under smear?
    for tag, mode, m in E2_CONDS:
        w, log, snaps = run_coalition("mock-strategic", q_quorum=E2_Q,
                                      smear_mode=mode, n_smearers=m, mock=True, days=days)
        out[("e2", tag)] = _world_metrics(w, log, snaps)
    return out


_FP_FIELDS = ("gap", "be", "liar_heard", "honest_heard", "honest_body", "gini",
              "persist", "n_suppressed", "n_exposed")
_FP_KEYS = ([("e13", t) for t, _ in E13_CONDS] + [("e2", t) for t, _, _ in E2_CONDS])


def fingerprint(res):
    h = hashlib.sha256()
    for key in _FP_KEYS:
        d = res[key]
        for f in _FP_FIELDS:
            h.update(f"{key[0]}.{key[1]}.{f}={float(d[f]):.6f}|".encode())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
#  No-op proof: CoalitionWorld(sanction OFF) === TrustCommWorld                 #
# --------------------------------------------------------------------------- #
def _trust_metrics_via_coalition(days=DAYS):
    """Reproduce sim_trust.compute_metrics, but with CoalitionWorld(sanction OFF)
    standing in for TrustCommWorld on every trust-ON run. If the sanction seam is a
    true no-op when off, this yields sim_trust's exact metric fingerprint
    (`6f31f775912f5e96`)."""
    out = {}
    for r in TRUST_REGIMES:
        wo, _ = run_off(r, days)
        if r == "mock-strategic":
            w = CoalitionWorld(EventLog(), seed=SEED, regime="deceptive",
                               policy=MockStrategicPolicy(), focal=None, q_quorum=None)
        else:
            w = CoalitionWorld(EventLog(), seed=SEED, regime=r, q_quorum=None)
        for _ in range(days):
            w.step()
        liar_t, honest_t = trust_in_speaker_kinds(w, w.log)
        out[r] = {
            "gap_off": elite_gap(wo), "gap_on": elite_gap(w),
            "be_off": float(wo.belief_gap()), "be_on": float(w.belief_gap()),
            "trust_liar": liar_t, "trust_honest": honest_t,
        }
    return out


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
def _fmt(v, fmt="{:.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def main():
    line = "=" * 78
    print(line)
    print("COLLECTIVE SANCTION — the first JOINT political verb (enforcement, not updating)")
    print("A quorum of co-located agents who each caught T lying BLOCKS T's claim from")
    print("every nearby listener's perspective this tick — even listeners who trust T.")
    print("No single agent can; a coalition can. Coalition forms from already-caught liars.")
    print(f"seed {SEED}; {DAYS}d; think every {THINK_EVERY}d; sanction τ={TAU_SANCTION}; "
          f"quorum sweep {Q_SWEEP}")
    print(line)

    res = compute_metrics()

    # E1 / E3 table (deceptive across the quorum gradient)
    e13 = [t for t, _ in E13_CONDS]
    print(f"\n[E1/E3 — brazen liar (deceptive), quorum gradient]")
    print(f"{'metric':<30}" + "".join(f"{t:>12}" for t in e13))
    print("-" * (30 + 12 * len(e13)))
    print(f"{'liar heard fraction':<30}"
          + "".join(f"{_fmt(res[('e13', t)]['liar_heard']):>12}" for t in e13))
    print(f"{'capture gap elite-aud (kg)':<30}"
          + "".join(f"{_fmt(res[('e13', t)]['gap'], '{:+.3f}'):>12}" for t in e13))
    print(f"{'audience belief error (kg)':<30}"
          + "".join(f"{_fmt(res[('e13', t)]['be'], '{:.1f}'):>12}" for t in e13))
    print(f"{'Gini of reserve (capture)':<30}"
          + "".join(f"{_fmt(res[('e13', t)]['gini']):>12}" for t in e13))
    print(f"{'top-stratum persistence':<30}"
          + "".join(f"{_fmt(res[('e13', t)]['persist']):>12}" for t in e13))
    print(f"{'claims suppressed':<30}"
          + "".join(f"{res[('e13', t)]['n_suppressed']:>12d}" for t in e13))

    # E2 table (mock-strategic, smear at Q=2)
    e2 = [t for t, _, _ in E2_CONDS]
    print(f"\n[E2 — censorship under SMEAR (mock-strategic, Q={E2_Q}; coord M=Q)]")
    print(f"{'metric':<30}" + "".join(f"{t:>12}" for t in e2))
    print("-" * (30 + 12 * len(e2)))
    print(f"{'honest heard fraction':<30}"
          + "".join(f"{_fmt(res[('e2', t)]['honest_heard']):>12}" for t in e2))
    print(f"{'honest speaker body (kg)':<30}"
          + "".join(f"{_fmt(res[('e2', t)]['honest_body']):>12}" for t in e2))
    print(f"{'audience belief error (kg)':<30}"
          + "".join(f"{_fmt(res[('e2', t)]['be'], '{:.1f}'):>12}" for t in e2))
    print(f"{'capture gap elite-aud (kg)':<30}"
          + "".join(f"{_fmt(res[('e2', t)]['gap'], '{:+.3f}'):>12}" for t in e2))

    # --- metric fingerprint + self-check ------------------------------------- #
    fp = fingerprint(res)
    print(f"\nmetric fingerprint: {fp}")
    fp2 = fingerprint(compute_metrics())
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp == fp2 else 'MISMATCH ✗'}")
    assert fp == fp2, "coalition metrics are not reproducible across runs"

    # --- OFF = canon, proven a no-op on two configurations ------------------- #
    base = run_comm("deceptive")[0].state_fingerprint()
    print(f"\nno-op #1 base comm canon (deceptive): {base} vs {CANON_COMM} -> "
          f"{'BIT-IDENTICAL ✓' if base == CANON_COMM else 'MISMATCH ✗'}")
    assert base == CANON_COMM, "base comm canon perturbed"
    tfp = trust_fingerprint(_trust_metrics_via_coalition())
    print(f"no-op #2 trust self-check via CoalitionWorld(OFF): {tfp} vs {CANON_TRUST} -> "
          f"{'BIT-IDENTICAL ✓' if tfp == CANON_TRUST else 'MISMATCH ✗'}")
    assert tfp == CANON_TRUST, "sanction seam is not a no-op when off"

    # --- conservation + replay on a SANCTION-ON run -------------------------- #
    wON, lON, _ = run_coalition("deceptive", q_quorum=2)
    drift = wON.matter_drift()
    print(f"\nmatter drift [SANCTION-ON deceptive Q=2] {drift:.2e} kg   "
          f"(silencing a voice moves no matter)")
    assert drift < 1e-9, "SANCTION-ON run leaked matter"
    rerun = run_coalition("deceptive", q_quorum=2)[0]
    ok = wON.state_fingerprint() == rerun.state_fingerprint()
    print(f"replay (rerun) [Q=2]: {wON.state_fingerprint()} vs "
          f"{rerun.state_fingerprint()} -> {'BIT-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
    assert ok, "SANCTION-ON run is not reproducible by rerun"

    # replay FROM LOG on a policy-driven (mock) sanction run
    wM, lM, _ = run_coalition("mock-strategic", q_quorum=2, mock=True)
    wRep = CoalitionWorld(EventLog(), seed=SEED, regime="deceptive",
                          policy=ReplayPolicy(lM.events), focal=None, q_quorum=2)
    for _ in range(DAYS):
        wRep.step()
    okr = wM.state_fingerprint() == wRep.state_fingerprint()
    print(f"replay-FROM-LOG [mock Q=2]: {wM.state_fingerprint()} vs "
          f"{wRep.state_fingerprint()} -> {'BIT-IDENTICAL ✓' if okr else 'MISMATCH ✗'}")
    assert okr, "sanction run does not replay from its own claim log"

    # --- the headline answers it computes (reported, not assumed) ------------ #
    off, q2, q3, qm = (res[("e13", t)] for t in ("off", "Q2", "Q3", "Qmaj"))
    print(f"\n{line}")
    print("E1 — does collective sanction cut the brazen liar where individuals could not?")
    print(f"   liar heard  OFF {_fmt(off['liar_heard'])} -> Q2 {_fmt(q2['liar_heard'])} "
          f"-> Q3 {_fmt(q3['liar_heard'])} -> maj {_fmt(qm['liar_heard'])}")
    print(f"   capture gap OFF {_fmt(off['gap'], '{:+.3f}')} -> Q2 {_fmt(q2['gap'], '{:+.3f}')} "
          f"-> Q3 {_fmt(q3['gap'], '{:+.3f}')} -> maj {_fmt(qm['gap'], '{:+.3f}')} kg")
    dgap = (q2['gap'] - off['gap'])
    cut = (q2['liar_heard'] or 1.0) < 0.99 and dgap < -0.005
    print(f"   -> a quorum {'DOES' if cut else 'does NOT'} cut the liar "
          f"({q2['n_suppressed']} claims silenced at Q2); capture Δ(Q2-OFF) {dgap:+.3f} kg "
          f"— {'the extraction channel is throttled' if cut else 'the liar speaks where no quorum forms (escape)'}.")
    print("E2 — does the sanction misfire and silence the innocent (censorship)?")
    ns, lo, co = (res[("e2", t)] for t in ("nosmear", "lone", "coord"))
    print(f"   honest heard  no-smear {_fmt(ns['honest_heard'])} · "
          f"lone {_fmt(lo['honest_heard'])} · coord(M=Q) {_fmt(co['honest_heard'])}")
    print(f"   honest body   no-smear {_fmt(ns['honest_body'])} · "
          f"lone {_fmt(lo['honest_body'])} · coord {_fmt(co['honest_body'])} kg")
    lone_safe = (lo['honest_heard'] or 0) >= (ns['honest_heard'] or 0) - 0.02
    coord_bites = (co['honest_heard'] or 1) < (ns['honest_heard'] or 1) - 0.02
    print(f"   -> a LONE smearer {'cannot' if lone_safe else 'can'} reach quorum (innocent "
          f"{'protected' if lone_safe else 'silenced'}); a COORDINATED M=Q bloc "
          f"{'de-platforms the honest rival' if coord_bites else 'still does not bite'}.")
    print("E3 — does coordination manufacture a persistent hierarchy (vs module-18 flat)?")
    print(f"   Gini  OFF {_fmt(off['gini'])} -> Q2 {_fmt(q2['gini'])} -> maj {_fmt(qm['gini'])}; "
          f"persistence OFF {_fmt(off['persist'])} -> maj {_fmt(qm['persist'])}")
    dgini = (qm['gini'] - off['gini'])
    print(f"   -> collective enforcement {'GROWS' if dgini > 0.01 else ('shrinks' if dgini < -0.01 else 'does not move')} "
          f"inequality (Δgini OFF->maj {dgini:+.3f}); module 18's individual stake left it flat.")

    print(f"\n{line}")
    print("The collective verb changes the world for a non-consenting third party — it")
    print("controls who is heard. Whether that pins the liar, censors the innocent, or")
    print("builds a stratum is read off the numbers above, not assumed. SANCTION-OFF is")
    print(f"byte-identical to the trust canon; the seam moves no matter. seed {SEED}  ✓")


if __name__ == "__main__":
    main()
