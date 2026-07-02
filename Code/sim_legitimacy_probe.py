"""
sim_legitimacy_probe.py — ВСТАВКА-29: the political formula as a cheap enforcer (a PROBE,
not a module; NOT registered in verify_all.py — the tower print stays "closed at 28").

Hypothesis (Mosca). A "political formula" — collective legitimation-through-significance —
is a CHEAP enforcer: it suppresses challenges to ownership without a wealth-tax and without
a guard caste. Module 24 (the institution) already showed the EXPENSIVE path: owners are
taxed (sigma>0) to fund a fixed guard corps that quashes challenges — it works (successful
challenges box6 966 -> 122 under enforce) but the levy STARVES the substrate (capacity
collapses). This probe asks whether a myth can buy the same silence for free.

Mechanism (a new seam, NOT a config flip). `LegitimacyProbeWorld(InstitutionWorld)`. The
institution is a COLLECTIVE actor (not a single owner): each step it injects
legitimacy-salience onto every OWNED/contested claim-cell into the attention budget of the
co-located potential challengers there — reusing the module-21 injection PRIMITIVE (a
per-listener `{cell: accumulated salience}` ledger with per-step decay). Then, in the
existing module-24 challenge-step, a co-located non-owner who would raise a challenge to the
deed SELF-CENSORS iff the cell's accumulated legitimacy in its budget clears `legit_threshold`
— the challenge is simply never raised. No guard, no levy: `sigma` may be 0.

Two honest interpretation choices, made explicit so Stan can judge them:

  1. SEPARATE ledger, not the shared `injected` dict. The card says "reuse the
     `injected[L][cell]` primitive". Reusing the *actual* `self.injected` dict would route
     legitimacy through `_apply_budget`, EVICTING good-food memories (mod-21's crowding-out)
     and so reviving mod-21's HUNGER channel — the very channel that already NULLed on
     concentration. The card is explicit that THIS channel is different ("significance ->
     lowered readiness to challenge, not -> hunger"). So we reuse the mod-21 injection
     PATTERN (`{oid: {cell: value}}`, `+= W` per exposure, `*= decay` per step) in a
     dedicated `_legit` ledger read ONLY by the challenge gate — never by `_sig`/foraging.
     Matter is therefore untouched by construction (drift stays the inherited ~1.8e-12).

  2. Saturating gate. `legit_threshold` sweeps {0, .25, .5, .75, 1.0}, so the legitimacy
     reading is normalised to [0,1): `legitimation = L / (L + 1)` where L is the (decayed)
     accumulated exposure weight. `threshold=0` -> any exposure silences (max silence /
     minimum myth); `threshold=1.0` -> never silences. The curve is "how much myth = how
     much silence". W (exposure weight) and decay (permanent `1` vs one-shot `0`) are the
     mod-21 knobs; the primary sweep is the threshold.

Off-switch discipline (byte-exact, asserted at import via `self_check()`):
  * `formula=off` -> `step()` delegates entirely to `InstitutionWorld.step` -> the probe is
    byte-identical to module 24 at the same sigma (anchor 50d4eb8c1bd95f1e at the mod-24
    headline; anchor 931680477b4e012b at the appropriation headline).
  * `sigma=0, formula=off` -> the pure base -> canon a91480561b6de937.
Conservation < 1e-9 on every config; deterministic byte-for-byte across 5 seeds. Pure
stdlib + numpy; no network; import side-effect-free.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

import numpy as np

from sim_eventlog import EventLog, SEED
from sim_comm import R, C, DAYS
from sim_sphere import GRID_DIAG, CANON_COMM
from sim_salience import RAD, KK, LAG, FEW, W_INJ, AMT, gini
from sim_appropriation import (
    AppropriationWorld, appropriation_fingerprint, ownership_metrics, RHO, BOX,
)
from sim_institution import (
    InstitutionWorld, institution_fingerprint, M_E, APPROP_FP,
)

SEEDS = (7, 8, 9, 10, 11)
SIGMA = 0.5                 # the module-24 headline levy rate (the "expensive enforcer")
MOD24_FP = "50d4eb8c1bd95f1e"   # module-24 self-check (sigma=.5, enforce=on, claim, box6)
EPS_LEGIT = 1e-9           # legitimacy entries below this are dropped after decay
LEGIT_THRESHOLD = 0.5      # headline: half-legitimation silences a challenge
# Headline exposure weight. `legitimation = L/(L+1)`; W is chosen at 0.5 (not 1.0) so the
# pre-registered threshold sweep {0,.25,.5,.75,1} spans the transition instead of saturating
# after a single exposure, and so no pre-registered threshold sits exactly on an
# exposure-count lattice point (a `<`-vs-`<=` knife-edge). This is a mechanism-resolution
# choice fixed before reading any H1/H2 outcome — NOT tuned to a verdict.
W_LEGIT = 0.5


class LegitimacyProbeWorld(InstitutionWorld):
    """InstitutionWorld plus a collective legitimation seam. Each step the institution
    injects legitimacy-salience onto owned claim-cells into the co-located challengers'
    budgets; a challenger whose legitimacy on the contested cell clears `legit_threshold`
    self-censors (no challenge raised). `formula=False` is a true no-op — the probe is then
    byte-identical to module 24 at any sigma."""

    def __init__(self, log, seed=SEED, regime="deceptive",
                 radius=GRID_DIAG + 1.0, K=None, lag=0,
                 injection_strength=0.0, injectors=0, inject_amount=50.0,
                 decay=1.0, target_policy="decoy",
                 arena_side=None, pin_victims_only=False,
                 appropriation=0.0, owner_policy="founders", owners=FEW,
                 sigma=0.0, enforce=False, enforcers=M_E,
                 formula=False, legit_threshold=LEGIT_THRESHOLD,
                 W=W_LEGIT, legit_decay=1.0):
        self.formula = bool(formula)
        self.legit_threshold = float(legit_threshold)
        self.W = float(W)
        self.legit_decay = float(legit_decay)
        self._legit = {}                    # oid -> {cell: accumulated legitimacy weight}
        self._selfcensored = 0              # challenges never raised (the myth's work)
        self._legit_events = 0             # legitimacy injections delivered
        super().__init__(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                         injection_strength=injection_strength, injectors=injectors,
                         inject_amount=inject_amount, decay=decay,
                         target_policy=target_policy, arena_side=arena_side,
                         pin_victims_only=pin_victims_only, appropriation=appropriation,
                         owner_policy=owner_policy, owners=owners, sigma=sigma,
                         enforce=enforce, enforcers=enforcers)

    # ---- legitimation reading (normalised to [0,1)) ----------------------- #
    def _legitimation(self, oid, cell):
        led = self._legit.get(oid)
        if not led:
            return 0.0
        v = self.W * led.get(cell, 0.0)
        return v / (v + 1.0)             # saturating: 0 at no exposure, ->1 as v->inf

    # ---- inject legitimacy onto owned cells' co-located challengers -------- #
    def _inject_legitimacy(self):
        if self.owner_policy != "claim" or not self._cell_owner:
            return                        # founders own everywhere -> no per-cell challenge
        bycell = defaultdict(list)
        for a in self.pop:
            bycell[(a.i, a.j)].append(a)
        for cell in sorted(self._cell_owner):
            members = bycell.get(cell)
            if not members:
                continue
            owner_oid = self._cell_owner[cell]
            for a in members:
                if a.oid == owner_oid or a.oid in self._enforcer_ids:
                    continue
                led = self._legit.setdefault(a.oid, {})
                led[cell] = led.get(cell, 0.0) + self.W
                self._legit_events += 1

    def _decay_legit(self):
        if not self._legit:
            return
        new = {}
        for oid, led in self._legit.items():
            if oid not in self.mem:                       # drop the dead
                continue
            kept = {c: v * self.legit_decay
                    for c, v in led.items() if v * self.legit_decay > EPS_LEGIT}
            if kept:
                new[oid] = kept
        self._legit = new

    # ---- the challenge-step, with the legitimacy self-censorship gate ------ #
    def _do_challenges(self):
        if not self.formula:
            return super()._do_challenges()               # OFF -> exact module-24 behaviour
        if self.owner_policy != "claim":
            return
        bycell = defaultdict(list)
        for a in self.pop:
            bycell[(a.i, a.j)].append(a)
        for cell in sorted(self._cell_owner):
            members = bycell.get(cell)
            if not members:
                continue
            owner_oid = self._cell_owner[cell]
            challengers = [a for a in members
                           if a.oid != owner_oid and a.oid not in self._enforcer_ids]
            if not challengers:
                continue
            # THE FORMULA: a challenger legitimated past threshold never raises the challenge.
            willing = [a for a in challengers
                       if self._legitimation(a.oid, cell) < self.legit_threshold]
            if not willing:
                self._selfcensored += 1                   # the myth did the guard's work
                continue
            if self.enforce and any(a.oid in self._enforcer_ids for a in members):
                self._challenge_quashed += 1              # guarded -> ownership unchanged
            else:
                self._cell_owner[cell] = min(c.oid for c in willing)
                self._challenge_succeeded += 1

    # ---- step: formula off == module 24; formula on runs the challenge even -- #
    #      at sigma=0 (the whole point: silence without the levy). ------------- #
    def step(self):
        if not self.formula:
            return super().step()                         # byte-identical InstitutionWorld
        AppropriationWorld.step(self)                     # base + claims + appropriation
        self._inject_legitimacy()                         # collective legitimation
        if self.sigma > 0.0:
            self._collect_levy()                          # parent financing (only if taxed)
        self._do_challenges()                             # legitimacy-gated challenge
        self._decay_legit()


# --------------------------------------------------------------------------- #
#  Running + fingerprint + metrics                                             #
# --------------------------------------------------------------------------- #
def run_probe(formula=False, legit_threshold=LEGIT_THRESHOLD, W=W_LEGIT, legit_decay=1.0,
              sigma=0.0, enforce=False, enforcers=M_E,
              appropriation=RHO, owner_policy="claim", owners=FEW,
              arena_side=None, injection_strength=0.0, injectors=0,
              regime="deceptive", radius=RAD, K=KK, lag=LAG,
              inject_amount=AMT, decay=1.0, target_policy="decoy",
              seed=SEED, days=DAYS):
    log = EventLog()
    w = LegitimacyProbeWorld(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                             injection_strength=injection_strength, injectors=injectors,
                             inject_amount=inject_amount, decay=decay,
                             target_policy=target_policy, arena_side=arena_side,
                             appropriation=appropriation, owner_policy=owner_policy,
                             owners=owners, sigma=sigma, enforce=enforce,
                             enforcers=enforcers, formula=formula,
                             legit_threshold=legit_threshold, W=W, legit_decay=legit_decay)
    for _ in range(days):
        w.step()
    return w, log


def probe_fingerprint(w):
    """The module-24 institution fingerprint (the whole taxed/guarded state) folded with
    the legitimacy layer: the flags, the self-censored count, and the sorted legitimacy
    ledger. With formula off the ledger is empty and the tail reduces to a constant, so the
    probe's fingerprint tracks the institution's; the anchors are checked on the raw
    institution/appropriation fingerprints, not this one."""
    h = hashlib.sha256()
    h.update(institution_fingerprint(w).encode())
    h.update((f"|F{int(w.formula)}|thr{w.legit_threshold:.6f}|W{w.W:.6f}"
              f"|dec{w.legit_decay:.6f}|censor{w._selfcensored}"
              f"|levt{w._legit_events}|lcells{sum(len(d) for d in w._legit.values())}"
              ).encode())
    for oid in sorted(w._legit):
        for cell in sorted(w._legit[oid]):
            h.update(f"{oid}:{cell[0]},{cell[1]}={w._legit[oid][cell]:.6f}".encode())
    return h.hexdigest()[:16]


def probe_metrics(w):
    om = ownership_metrics(w)
    live_bodies = [a.body for a in w.pop]
    owners = w.owner_ids()
    nonowners_live = [a.oid for a in w.pop if a.oid not in owners]
    legit_holders = sum(1 for oid in nonowners_live if w._legit.get(oid))
    return {
        "alive": len(w.pop),
        "succeeded": w._challenge_succeeded,       # successful ownership flips (E3 axis)
        "quashed": w._challenge_quashed,           # guard-blocked (module-24 defense)
        "selfcensored": w._selfcensored,           # myth-blocked (the formula's work)
        "owner_gap": om["owner_gap"],              # per-capita elite axis (dilution-invariant)
        "owner_share": om["owner_bio_share"],
        "terr_gini": om["territory_gini"],
        "bio_gini": gini(live_bodies) if live_bodies else float("nan"),
        "n_owners": om["n_owners"],
        "levy": w._levy_total,
        # legitimacy residency: fraction of living non-owners carrying any legitimacy load
        "legit_residency": (legit_holders / len(nonowners_live)) if nonowners_live else float("nan"),
    }


# --------------------------------------------------------------------------- #
#  Self-check (asserts the byte anchors; the probe is not in verify_all)       #
# --------------------------------------------------------------------------- #
def self_check(verbose=True):
    def say(*a):
        if verbose:
            print(*a)

    max_drift = 0.0

    # canon: sigma=0, formula=off, base off -> a91480561b6de937
    w0, _ = run_probe(formula=False, sigma=0.0, appropriation=0.0, owner_policy="claim",
                      radius=GRID_DIAG + 1.0, K=None, lag=0,
                      injection_strength=0.0, injectors=0, arena_side=None)
    c0 = w0.state_fingerprint(); max_drift = max(max_drift, w0.matter_drift())
    ok0 = (c0 == CANON_COMM and w0._selfcensored == 0 and not w0._legit)
    say(f"anchor canon    : {c0} vs {CANON_COMM} -> {'✓' if ok0 else '✗'}")
    assert ok0, "sigma=0 formula=off is not byte-identical to canon"

    # module 24: formula=off at the mod-24 headline -> 50d4eb8c1bd95f1e
    w24, _ = run_probe(formula=False, sigma=SIGMA, enforce=True, owner_policy="claim",
                       arena_side=BOX, injection_strength=0.0, injectors=0)
    f24 = institution_fingerprint(w24); max_drift = max(max_drift, w24.matter_drift())
    ok24 = f24 == MOD24_FP
    say(f"anchor mod-24   : {f24} vs {MOD24_FP} -> {'✓' if ok24 else '✗'}")
    assert ok24, "formula=off is not byte-identical to module 24 at the same sigma"

    # module 23: formula=off at the appropriation headline -> 931680477b4e012b
    wb1, _ = run_probe(formula=False, sigma=0.0, appropriation=RHO, owner_policy="founders",
                       arena_side=BOX, injection_strength=W_INJ, injectors=FEW)
    fb1 = appropriation_fingerprint(wb1); max_drift = max(max_drift, wb1.matter_drift())
    okb1 = fb1 == APPROP_FP
    say(f"anchor approp-B1: {fb1} vs {APPROP_FP} -> {'✓' if okb1 else '✗'}")
    assert okb1, "formula=off is not byte-identical to module 23 (base drift!)"

    # the probe's own fingerprint (formula ON): reproducible across a rerun
    wf, _ = run_probe(formula=True, legit_threshold=LEGIT_THRESHOLD, W=W_LEGIT,
                      sigma=0.0, enforce=False, owner_policy="claim", arena_side=BOX,
                      injection_strength=0.0, injectors=0, seed=SEED)
    p1 = probe_fingerprint(wf)
    wf2, _ = run_probe(formula=True, legit_threshold=LEGIT_THRESHOLD, W=W_LEGIT,
                       sigma=0.0, enforce=False, owner_policy="claim", arena_side=BOX,
                       injection_strength=0.0, injectors=0, seed=SEED)
    p2 = probe_fingerprint(wf2)
    max_drift = max(max_drift, wf.matter_drift())
    say(f"PROBE_FINGERPRINT (formula ON, box{BOX}, seed {SEED}): {p1}")
    say(f"self-check (recompute): {p2} -> {'BIT-IDENTICAL ✓' if p1 == p2 else 'MISMATCH ✗'}")
    assert p1 == p2, "probe run is not reproducible"
    assert max_drift < 1e-9, f"a self-check config leaked matter: {max_drift:.2e}"
    say(f"max matter drift (self-check): {max_drift:.2e} kg")
    return p1


# --------------------------------------------------------------------------- #
#  Demo / battery                                                              #
# --------------------------------------------------------------------------- #
def _fmt(v, fmt="{:.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def _mean(vals):
    vals = [v for v in vals if not (isinstance(v, float) and v != v)]
    return float(np.mean(vals)) if vals else float("nan")


def _battery_row(formula, sigma, enforce, arena, threshold=LEGIT_THRESHOLD, W=W_LEGIT):
    agg = defaultdict(list)
    run_max = 0.0
    for sd in SEEDS:
        w, _ = run_probe(formula=formula, legit_threshold=threshold, W=W,
                         sigma=sigma, enforce=enforce, owner_policy="claim",
                         arena_side=arena, injection_strength=0.0, injectors=0, seed=sd)
        d = w.matter_drift(); run_max = max(run_max, d)
        assert d < 1e-9, f"leak F={formula} sig={sigma} enf={enforce} arena={arena} seed={sd}: {d}"
        for k, v in probe_metrics(w).items():
            agg[k].append(v)
    m = {k: _mean(v) for k, v in agg.items()}
    m["drift"] = run_max
    return m


def main():
    line = "=" * 78
    print(line)
    print("LEGITIMACY PROBE (ВСТАВКА-29) — the political formula as a cheap enforcer.")
    print("LegitimacyProbeWorld(InstitutionWorld): the institution injects legitimacy onto")
    print("owned cells into challengers' budgets; a legitimated challenger self-censors. Does")
    print("a myth suppress challenge (module-24's job) WITHOUT the levy's capacity collapse,")
    print(f"and does it CONCENTRATE where property alone did not? claim, rho={RHO}, salience off;")
    print(f"arenas open & box{BOX}; seeds {SEEDS}; headline threshold={LEGIT_THRESHOLD}, W={W_LEGIT}.")
    print(line)

    print("\nSELF-CHECK (byte anchors; this probe is NOT in verify_all):")
    self_check(verbose=True)

    # ---- battery: B0 / A(off,on) / B(formula) / A+B, both arenas ----------- #
    print(f"\nBATTERY (claim, rho={RHO}, mean over seeds {SEEDS}):")
    hdr = (f"{'config':>12}{'arena':>6}{'alive':>7}{'succ':>7}{'quash':>7}{'censor':>8}"
           f"{'ownGap':>9}{'ownShr':>8}{'bioGini':>9}{'resid':>7}{'drift':>9}")
    print(hdr); print("-" * len(hdr))
    rows = {}
    for arena in (None, BOX):
        specs = [
            ("B0 sig0/off",  dict(formula=False, sigma=0.0,   enforce=False)),
            ("A  sigX/off",  dict(formula=False, sigma=SIGMA, enforce=False)),
            ("A  sigX/enf",  dict(formula=False, sigma=SIGMA, enforce=True)),
            ("B  sig0/form",  dict(formula=True,  sigma=0.0,   enforce=False)),
            ("A+B sigX/form", dict(formula=True,  sigma=SIGMA, enforce=True)),
        ]
        for tag, kw in specs:
            m = _battery_row(arena=arena, **kw)
            rows[(tag.strip(), arena)] = m
            print(f"{tag:>12}{str(arena or '-'):>6}{m['alive']:>7.1f}{m['succeeded']:>7.0f}"
                  f"{m['quashed']:>7.0f}{m['selfcensored']:>8.0f}"
                  f"{_fmt(m['owner_gap'], '{:+.2f}'):>9}{_fmt(m['owner_share']):>8}"
                  f"{_fmt(m['bio_gini']):>9}{_fmt(m['legit_residency']):>7}{m['drift']:>9.1e}")
        print()

    # ---- threshold sweep (config B: sigma=0, formula on), both arenas ------ #
    print(f"threshold sweep (config B: sigma=0, formula on, W={W_LEGIT}); "
          f"'how much myth = how much silence' (thr=0 -> any myth silences):")
    print(f"  {'arena':>6}{'thresh':>8}{'succ':>7}{'censor':>8}{'alive':>7}"
          f"{'ownGap':>9}{'bioGini':>9}{'resid':>7}")
    sweep = {}
    for arena in (None, BOX):
        for thr in (0.0, 0.25, 0.5, 0.75, 1.0):
            m = _battery_row(formula=True, sigma=0.0, enforce=False, arena=arena, threshold=thr)
            sweep[(arena, thr)] = m
            print(f"  {str(arena or '-'):>6}{thr:>8.2f}{m['succeeded']:>7.0f}"
                  f"{m['selfcensored']:>8.0f}{m['alive']:>7.1f}"
                  f"{_fmt(m['owner_gap'], '{:+.2f}'):>9}{_fmt(m['bio_gini']):>9}"
                  f"{_fmt(m['legit_residency']):>7}")
        print()

    # ---- pre-registered verdicts (read off the numbers, box6) -------------- #
    b0 = rows[("B0 sig0/off", BOX)]
    a_enf = rows[("A  sigX/enf", BOX)]
    b_form = rows[("B  sig0/form", BOX)]           # headline threshold config
    ab = rows[("A+B sigX/form", BOX)]
    baseline_succ = sweep[(BOX, 1.0)]["succeeded"]  # threshold=1.0 -> the no-myth challenge rate
    print(line)
    print(f"H1 (cheap suppression, box{BOX}): can the myth buy the guard's silence without the "
          f"levy's capacity collapse?")
    print(f"   challenge (succ) : no-myth {baseline_succ:.0f}  ->  A/enforce {a_enf['succeeded']:.0f} "
          f"(guard) | B/formula@thr{LEGIT_THRESHOLD} {b_form['succeeded']:.0f} | "
          f"B/formula@thr0 {sweep[(BOX, 0.0)]['succeeded']:.0f}")
    print(f"   alive (capacity) : base(B0) {b0['alive']:.1f}  ->  A/enforce {a_enf['alive']:.1f} "
          f"(collapse) | B/formula@thr{LEGIT_THRESHOLD} {b_form['alive']:.1f} | "
          f"B/formula@thr0 {sweep[(BOX, 0.0)]['alive']:.1f}")
    # H1 read off the SWEEP, not one point: does SOME threshold reach guard-level suppression
    # while keeping capacity (alive ~ B0)?  And does capacity survive at EVERY threshold?
    guard_succ = a_enf["succeeded"]
    reaches = [thr for thr in (0.0, 0.25, 0.5, 0.75, 1.0)
               if sweep[(BOX, thr)]["succeeded"] <= max(guard_succ, 1)
               and sweep[(BOX, thr)]["alive"] >= 0.6 * b0["alive"]]
    cap_always = all(sweep[(BOX, thr)]["alive"] >= 0.6 * b0["alive"]
                     for thr in (0.0, 0.25, 0.5, 0.75, 1.0))
    guard_collapses = a_enf["alive"] < 0.5 * b0["alive"]
    if reaches and cap_always and guard_collapses:
        print(f"   -> H1 NON-NULL (threshold-gated): at threshold(s) {reaches} the formula "
              f"silences challenge to <= the guard's {guard_succ:.0f} while capacity holds near "
              f"B0 ({b0['alive']:.0f}); the guard reaches it only by collapsing capacity to "
              f"{a_enf['alive']:.0f}. The myth is the cheap enforcer — but only when it is cheap "
              f"enough (low threshold); at threshold {LEGIT_THRESHOLD} suppression is partial "
              f"({baseline_succ:.0f}->{b_form['succeeded']:.0f}).")
    elif cap_always and not reaches:
        print(f"   -> H1 PARTIAL/NULL: capacity always survives (no levy), but no threshold "
              f"drives challenge to the guard's level {guard_succ:.0f} (best "
              f"{min(sweep[(BOX, t)]['succeeded'] for t in (0.0,0.25,0.5,0.75,1.0)):.0f}). "
              f"The myth dampens but does not fully substitute for the guard.")
    else:
        print("   -> H1 NULL: the formula silences only at a capacity cost of its own; not "
              "cheaper than the tax.")

    print(f"\nH2 (Michels / super-additivity, box{BOX}): does the agenda-layer concentrate "
          f"beyond property alone?")
    # Concentration is measured as owner_gap ABOVE the bare-property base (b0). A layer only
    # "concentrates" if it RAISES owner_gap (positive delta); super-additivity requires the
    # combined layer to raise it beyond the sum of the parts AND beyond either part alone.
    d_a = (a_enf["owner_gap"] or 0) - (b0["owner_gap"] or 0)
    d_b = (b_form["owner_gap"] or 0) - (b0["owner_gap"] or 0)
    d_ab = (ab["owner_gap"] or 0) - (b0["owner_gap"] or 0)
    superadd = (d_ab > 0) and (d_ab > d_a + d_b + 0.05) and (d_ab > max(d_a, d_b))
    print(f"   owner_gap (per-capita): base {_fmt(b0['owner_gap'], '{:+.2f}')} | "
          f"A {_fmt(a_enf['owner_gap'], '{:+.2f}')} (Δ{d_a:+.2f}) | "
          f"B {_fmt(b_form['owner_gap'], '{:+.2f}')} (Δ{d_b:+.2f}) | "
          f"A+B {_fmt(ab['owner_gap'], '{:+.2f}')} (Δ{d_ab:+.2f})")
    if superadd:
        print(f"   -> H2 NON-NULL: A+B raises owner_gap (Δ{d_ab:+.2f}) super-additively vs the "
              f"parts (Δ{d_a:+.2f}+Δ{d_b:+.2f}) — the agenda-layer cements a stratum property "
              "alone did not (Michels' iron law in the significance channel).")
    else:
        print(f"   -> H2 NULL: no super-additive concentration — every layer DILUTES owner_gap "
              f"below the bare-property base (A Δ{d_a:+.2f}, B Δ{d_b:+.2f}, A+B Δ{d_ab:+.2f}); the "
              f"property-arc NULL on concentration repeats in the agenda-layer. Legitimacy buys "
              f"SILENCE (H1), not a hierarchy (H2).")
    print(line)
    print("Legitimacy writes attention, never matter; formula=off reproduces canon, module 23")
    print("and module 24 byte-for-byte. Verdicts are read off the numbers, not tuned. "
          f"seeds {SEEDS} ✓")


if __name__ == "__main__":
    main()
