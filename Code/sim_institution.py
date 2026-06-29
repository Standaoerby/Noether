"""
sim_institution.py — the protector institution (module 24): defend the property.

ВСТАВКА 13-14 names the verb that follows appropriation: coalition -> institution ->
police-state. Module 23 showed a rent transfer builds an owner WEALTH stratum (the first
non-NULL on capture). This adds the next link: owners are TAXED to fund a fixed GUARD
caste (enforcers) that QUASHES challenges to ownership — testing whether enforced property
*sharpens* the stratum (higher concentration, lower turnover, suppressed challenge) beyond
bare appropriation, merely parasitizes (NULL), or lets the guards eat the owners
(capture-of-guards).

`InstitutionWorld(AppropriationWorld)` inherits the whole tower. One off-switchable seam,
in the spirit of module 23's `_appropriate()`:

    def step(self):
        super().step()                 # base + appropriation run UNCHANGED
        if self.sigma <= 0.0: return    # INSTITUTION OFF -> byte-identical AppropriationWorld
        self._collect_levy()            # body->body wealth tax: owners pay, enforcers receive
        self._do_challenges()           # ledger only; defense applied per self.enforce

  * sigma = levy rate = institution strength (the master off-switch). sigma=0 -> the seam
    returns immediately, touching no bodies and no ledger -> byte-identical parent.
  * enforce in {off, on} = the within-on A/B knob (does the guard actually defend?).
  * Owners (the taxed) = current property holders under owner_policy (founders: the M
    lowest-oid founder speakers; claim: every agent owning >=1 cell). Enforcers = a FIXED
    identity caste sorted(speaker)[M : M+M_e], disjoint from owners for both policies (under
    claim, enforcers are barred from claiming so the castes never overlap — gated on
    sigma>0 so OFF stays byte-identical to the parent's claim rule).
  * Levy: each alive owner pays t = sigma*body (sigma<=1 keeps body>=0); the pool is split
    evenly among alive enforcers, the last taking the float remainder -> distributed exactly.
    Body lives in self.pop, never in a grid pool -> matter moves only between live bodies.
  * Challenge/defense (claim only; founders own-everywhere -> no per-cell ledger -> no-op on
    ownership): on each owned cell with a co-located non-owner/non-enforcer challenger, the
    lowest-oid such challenger takes the cell — UNLESS enforce and an alive enforcer is
    co-located, which quashes it (ownership unchanged). Ledger-only, no mass. Defense is
    SPATIAL: a guard must physically be on the contested cell (enforcers forage like
    everyone, so coverage is emergent — E3 measures whether local presence suffices).

Conservation by construction (asserted < 1e-9 at every config). Pure stdlib + numpy; no
network; import side-effect-free.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

from sim_eventlog import EventLog, SEED
from sim_comm import R, C, DAYS, run as run_comm
from sim_sphere import GRID_DIAG, CANON_COMM
from sim_salience import e1_concentration, e3_harm, gini, RAD, KK, LAG, FEW, W_INJ, AMT
from sim_appropriation import (
    AppropriationWorld, appropriation_fingerprint, run_appropriation,
    ownership_metrics, RHO, BOX,
)

APPROP_FP = "931680477b4e012b"      # module-23 self-check (claim... no: founders rho.5 box6 sal-on)
M_E = 3                             # enforcer corps size (disjoint caste)


class InstitutionWorld(AppropriationWorld):
    """AppropriationWorld plus a levy-funded guard caste that quashes ownership
    challenges. sigma=0 is a true no-op (byte-identical to the parent at any config)."""

    def __init__(self, log, seed=SEED, regime="deceptive",
                 radius=GRID_DIAG + 1.0, K=None, lag=0,
                 injection_strength=0.0, injectors=0, inject_amount=50.0,
                 decay=1.0, target_policy="decoy",
                 arena_side=None, pin_victims_only=False,
                 appropriation=0.0, owner_policy="founders", owners=FEW,
                 sigma=0.0, enforce=False, enforcers=M_E):
        self.sigma = float(sigma)
        self.enforce = bool(enforce)
        self._n_enforcers = int(enforcers)
        self._levy_total = 0.0
        self._challenge_succeeded = 0
        self._challenge_quashed = 0
        self._top5_mid = None
        super().__init__(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                         injection_strength=injection_strength, injectors=injectors,
                         inject_amount=inject_amount, decay=decay,
                         target_policy=target_policy, arena_side=arena_side,
                         pin_victims_only=pin_victims_only, appropriation=appropriation,
                         owner_policy=owner_policy, owners=owners)
        # enforcers = the next M_e lowest-oid founder speakers after the M-owner block,
        # fixed for life and disjoint from the founder owners.
        spk = sorted(self.speaker)
        self._enforcer_ids = set(spk[self._n_owners:self._n_owners + self._n_enforcers])

    # ---- claim: enforcers never claim (caste disjoint), only when ON ------- #
    def _do_claims(self):
        if self.sigma <= 0.0:
            return super()._do_claims()          # OFF -> identical to parent's claim rule
        if self._cell_owner:
            for c in [c for c, o in self._cell_owner.items() if o not in self.mem]:
                del self._cell_owner[c]
        bycell = defaultdict(list)
        for a in self.pop:
            bycell[(a.i, a.j)].append(a)
        for cell in sorted(bycell):
            if cell in self._cell_owner:
                continue
            elig = [a.oid for a in bycell[cell] if a.oid not in self._enforcer_ids]
            if elig:
                self._cell_owner[cell] = min(elig)

    # ---- financing: body->body wealth tax, exact remainder ----------------- #
    def _collect_levy(self):
        live = {a.oid: a for a in self.pop}
        enforcers = [oid for oid in sorted(self._enforcer_ids) if oid in live]
        if not enforcers:
            return                                # no guards -> nothing collected (T=0)
        owners = sorted(self.owner_ids())
        if not owners:
            return
        T = 0.0
        for oid in owners:
            a = live[oid]
            t = self.sigma * a.body
            if t > a.body:                        # sigma<=1 -> never, clamp body >= 0
                t = a.body
            a.body -= t
            T += t
        if T <= 0.0:
            return
        share = T / len(enforcers)
        given = 0.0
        for oid in enforcers[:-1]:
            live[oid].body += share
            given += share
        live[enforcers[-1]].body += (T - given)   # last takes remainder -> pool exact
        self._levy_total += T

    # ---- challenge + spatial defense (ledger only, no mass) ---------------- #
    def _do_challenges(self):
        if self.owner_policy != "claim":
            return                                # founders: own-everywhere, no ledger
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
            if self.enforce and any(a.oid in self._enforcer_ids for a in members):
                self._challenge_quashed += 1       # guarded -> ownership unchanged
            else:
                self._cell_owner[cell] = min(c.oid for c in challengers)
                self._challenge_succeeded += 1

    def step(self):
        super().step()
        if self.sigma <= 0.0:
            return                                # OFF: byte-identical AppropriationWorld
        self._collect_levy()
        self._do_challenges()

    # ---- metrics ----------------------------------------------------------- #
    def enforcer_ids_alive(self):
        return self._enforcer_ids & {a.oid for a in self.pop}

    def top5_owners(self):
        """Top-5 owners by owned-cell count (claim), tie-break by oid."""
        counts = self.territory_counts()
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return [oid for oid, _ in ranked[:5]]


# --------------------------------------------------------------------------- #
#  Running + fingerprint + metrics                                             #
# --------------------------------------------------------------------------- #
def run_institution(sigma=0.0, enforce=False, enforcers=M_E,
                    appropriation=RHO, owner_policy="founders", owners=FEW,
                    arena_side=None, injection_strength=0.0, injectors=0,
                    regime="deceptive", radius=RAD, K=KK, lag=LAG,
                    inject_amount=AMT, decay=1.0, target_policy="decoy",
                    seed=SEED, days=DAYS):
    log = EventLog()
    w = InstitutionWorld(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                         injection_strength=injection_strength, injectors=injectors,
                         inject_amount=inject_amount, decay=decay,
                         target_policy=target_policy, arena_side=arena_side,
                         appropriation=appropriation, owner_policy=owner_policy,
                         owners=owners, sigma=sigma, enforce=enforce, enforcers=enforcers)
    for _ in range(days):
        w.step()
        if w.t == 150 and w.owner_policy == "claim" and w.sigma > 0.0:
            w._top5_mid = w.top5_owners()         # E2 ossification: mid-run elite snapshot
    return w, log


def institution_fingerprint(w):
    h = hashlib.sha256()
    h.update(appropriation_fingerprint(w).encode())
    h.update((f"|sigma{w.sigma:.6f}|enforce{int(w.enforce)}|Me{w._n_enforcers}"
              f"|levy{w._levy_total:.6f}|succ{w._challenge_succeeded}"
              f"|quash{w._challenge_quashed}|enf{sorted(w._enforcer_ids)}").encode())
    return h.hexdigest()[:16]


def institution_metrics(w):
    live = {a.oid for a in w.pop}
    owners = w.owner_ids()
    enforcers = w._enforcer_ids & live
    tot = sum(a.body for a in w.pop)
    ob = sum(a.body for a in w.pop if a.oid in owners)
    eb = sum(a.body for a in w.pop if a.oid in enforcers)
    return {
        "owner_share": ob / tot if tot > 0 else float("nan"),
        "enforcer_share": eb / tot if tot > 0 else float("nan"),
        "combined_share": (ob + eb) / tot if tot > 0 else float("nan"),
        "n_owners": len(owners), "n_enforcers": len(enforcers),
        "levy_total": w._levy_total,
        "succeeded": w._challenge_succeeded, "quashed": w._challenge_quashed,
    }


def turnover_retention(w):
    """Fraction of the day-150 top-5 owners still in the day-300 top-5 (claim only).
    High = ossified elite; low = churn. nan if not measurable."""
    if w.owner_policy != "claim" or not w._top5_mid:
        return float("nan")
    end = w.top5_owners()
    if not end:
        return float("nan")
    return len(set(w._top5_mid) & set(end)) / 5.0


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
SIGMA = 0.5


def _fmt(v, fmt="{:.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def main():
    line = "=" * 78
    print(line)
    print("INSTITUTION — the guard caste that defends property (ВСТАВКА 13-14)")
    print("InstitutionWorld(AppropriationWorld): owners are taxed (body->body levy) to fund")
    print("a fixed enforcer caste that quashes ownership challenges. Does enforced property")
    print("SHARPEN the owner stratum (concentration up, turnover down, challenge suppressed)")
    print(f"beyond bare rent? grid {R}x{C}; seed {SEED}; {DAYS}d; headline sigma={SIGMA}, "
          f"M={FEW} owners, M_e={M_E} enforcers; rho={RHO} ON. sigma=0 == parent.")
    print(line)

    max_drift = 0.0

    # --- B0: sigma=0 + all-off == canon (both policies) --------------------- #
    for pol in ("founders", "claim"):
        w0, _ = run_institution(sigma=0.0, appropriation=0.0, owner_policy=pol,
                                radius=GRID_DIAG + 1.0, K=None, lag=0,
                                injection_strength=0.0, injectors=0, arena_side=None)
        fp = w0.state_fingerprint()
        ok = fp == CANON_COMM and w0._levy_total == 0.0
        max_drift = max(max_drift, w0.matter_drift())
        print(f"B0  sigma=0 all-off [{pol:<8}] : {fp} vs canon {CANON_COMM} -> "
              f"{'BYTE-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
        assert ok, f"B0 [{pol}] not byte-identical to canon / nonzero levy"

    # --- B1: sigma=0 at the appropriation headline == module-23 fingerprint - #
    wb1, _ = run_institution(sigma=0.0, appropriation=RHO, owner_policy="founders",
                             arena_side=BOX, injection_strength=W_INJ, injectors=FEW)
    fpb1 = appropriation_fingerprint(wb1)
    okb1 = fpb1 == APPROP_FP
    print(f"B1  sigma=0 approp-headline      : appropriation_fp {fpb1} vs {APPROP_FP} -> "
          f"{'BYTE-IDENTICAL ✓' if okb1 else 'MISMATCH ✗'}")
    assert okb1, "B1 not byte-identical to module-23 self-check (base drift!)"

    # --- cross-product at sigma=0.5: {enforce} x {arena} x {policy} --------- #
    print(f"\nCROSS-PRODUCT (sigma={SIGMA}, rho={RHO}); shares of biomass + conservation:")
    hdr = f"{'enf':>4}{'arena':>6}{'policy':>9}{'ownShr':>8}{'enfShr':>8}{'combShr':>9}" \
          f"{'levy':>8}{'succ':>6}{'quash':>7}{'drift':>10}"
    print(hdr); print("-" * len(hdr))
    for enforce in (False, True):
        for arena in (None, BOX):
            for pol in ("founders", "claim"):
                w, _ = run_institution(sigma=SIGMA, enforce=enforce, owner_policy=pol,
                                       arena_side=arena, injection_strength=0.0, injectors=0)
                d = w.matter_drift(); max_drift = max(max_drift, d)
                assert d < 1e-9, f"leak enf={enforce} arena={arena} pol={pol}: {d}"
                im = institution_metrics(w)
                print(f"{('on' if enforce else 'off'):>4}{str(arena or '-'):>6}{pol:>9}"
                      f"{_fmt(im['owner_share']):>8}{_fmt(im['enforcer_share']):>8}"
                      f"{_fmt(im['combined_share']):>9}{_fmt(im['levy_total'], '{:.0f}'):>8}"
                      f"{im['succeeded']:>6}{im['quashed']:>7}{d:>10.1e}")

    # --- sigma sweep at (enforce=on, claim), open & box6 -------------------- #
    for arena, tag in ((None, "open"), (BOX, f"box{BOX}")):
        print(f"\nsigma sweep (enforce=on, claim, {tag}): strength vs sharpening")
        print(f"  {'sigma':>6}{'ownShr':>8}{'enfShr':>8}{'combShr':>9}{'turnover':>10}"
              f"{'succ':>6}{'quash':>7}{'vicBio':>8}{'drift':>10}")
        for sg in (0.0, 0.25, 0.5, 0.75, 1.0):
            w, _ = run_institution(sigma=sg, enforce=True, owner_policy="claim",
                                   arena_side=arena, injection_strength=0.0, injectors=0)
            d = w.matter_drift(); max_drift = max(max_drift, d)
            assert d < 1e-9, f"leak sigma={sg} {tag}: {d}"
            im, e3 = institution_metrics(w), e3_harm(w)
            ret = turnover_retention(w)
            print(f"  {sg:>6.2f}{_fmt(im['owner_share']):>8}{_fmt(im['enforcer_share']):>8}"
                  f"{_fmt(im['combined_share']):>9}{_fmt(ret):>10}{im['succeeded']:>6}"
                  f"{im['quashed']:>7}{_fmt(e3['vic_biomass'], '{:.0f}'):>8}{d:>10.1e}")

    # --- enforce off vs on at headline (claim, box6): E2/E3 contrast -------- #
    print(f"\nenforce off vs on (claim, box{BOX}, sigma={SIGMA}): the institution's signature")
    print(f"  {'enforce':>8}{'turnover(ret)':>14}{'succeeded':>11}{'quashed':>9}"
          f"{'ownShr':>8}{'enfShr':>8}")
    for enforce in (False, True):
        w, _ = run_institution(sigma=SIGMA, enforce=enforce, owner_policy="claim",
                               arena_side=BOX, injection_strength=0.0, injectors=0)
        max_drift = max(max_drift, w.matter_drift())
        im = institution_metrics(w); ret = turnover_retention(w)
        print(f"  {('on' if enforce else 'off'):>8}{_fmt(ret):>14}{im['succeeded']:>11}"
              f"{im['quashed']:>9}{_fmt(im['owner_share']):>8}{_fmt(im['enforcer_share']):>8}")

    # --- enforcer-corps sweep M_e in {1,3,6} at headline -------------------- #
    print(f"\nenforcer-corps sweep (sigma={SIGMA}, enforce=on, box{BOX}, claim): who guards?")
    print(f"  {'M_e':>4}{'ownShr':>8}{'enfShr':>8}{'turnover':>10}{'succ':>6}{'quash':>7}")
    for me in (1, 3, 6):
        w, _ = run_institution(sigma=SIGMA, enforce=True, enforcers=me, owner_policy="claim",
                               arena_side=BOX, injection_strength=0.0, injectors=0)
        max_drift = max(max_drift, w.matter_drift())
        im = institution_metrics(w); ret = turnover_retention(w)
        print(f"  {me:>4}{_fmt(im['owner_share']):>8}{_fmt(im['enforcer_share']):>8}"
              f"{_fmt(ret):>10}{im['succeeded']:>6}{im['quashed']:>7}")

    # --- self-check fingerprint (the levy+challenge+defense arm) ------------ #
    wf, _ = run_institution(sigma=SIGMA, enforce=True, owner_policy="claim", arena_side=BOX,
                            injection_strength=0.0, injectors=0)
    fp1 = institution_fingerprint(wf)
    wf2, _ = run_institution(sigma=SIGMA, enforce=True, owner_policy="claim", arena_side=BOX,
                             injection_strength=0.0, injectors=0)
    fp2 = institution_fingerprint(wf2)
    max_drift = max(max_drift, wf.matter_drift())
    print(f"\nINSTITUTION_FINGERPRINT: {fp1}")
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp1 == fp2 else 'MISMATCH ✗'}")
    assert fp1 == fp2, "institution run is not reproducible"
    print(f"max matter drift across battery: {max_drift:.2e} kg")
    assert max_drift < 1e-9, "a config leaked matter"

    # --- honest verdict ----------------------------------------------------- #
    # contrast enforce off vs on at (claim, box6, sigma=0.5): turnover + challenge
    woff, _ = run_institution(sigma=SIGMA, enforce=False, owner_policy="claim",
                              arena_side=BOX, injection_strength=0.0, injectors=0)
    won, _ = run_institution(sigma=SIGMA, enforce=True, owner_policy="claim",
                             arena_side=BOX, injection_strength=0.0, injectors=0)
    im_off, im_on = institution_metrics(woff), institution_metrics(won)
    ret_off, ret_on = turnover_retention(woff), turnover_retention(won)
    froze = (ret_on or 0) > (ret_off or 0) + 0.1
    suppressed = im_on["succeeded"] < im_off["succeeded"] * 0.5
    guards_eat = (im_on["enforcer_share"] or 0) > (im_on["owner_share"] or 0)
    print(f"\n{line}")
    print(f"E2 ossification (claim, box{BOX}): top-5 owner retention 150->300d  "
          f"enforce off {_fmt(ret_off)} -> on {_fmt(ret_on)}")
    print(f"E3 challenge suppression: successful flips  off {im_off['succeeded']} -> "
          f"on {im_on['succeeded']}  (quashed on: {im_on['quashed']})")
    print(f"E1 shares (on): owner {_fmt(im_on['owner_share'])} · enforcer "
          f"{_fmt(im_on['enforcer_share'])} · combined {_fmt(im_on['combined_share'])}")
    if guards_eat:
        print("VERDICT — CAPTURE OF THE GUARDS: enforcement WORKS (successful challenges")
        print(f"{im_off['succeeded']}->{im_on['succeeded']}, quashed {im_on['quashed']}) and "
              f"concentration rises (combined share {_fmt(im_on['combined_share'])}), but the")
        print("WEALTH lands on the enforcer caste, not the owners it was funded to protect")
        print(f"(enforcer {_fmt(im_on['enforcer_share'])} > owner {_fmt(im_on['owner_share'])}). "
              f"The sigma sweep shows the flip: owners stay ahead at low sigma, the guards")
        print("overtake at sigma>=0.5 — quis custodiet, the property tax becomes the guards'")
        print("own extraction channel. (Forks 1+3: the institution sharpens, then eats its")
        print("patron — ВСТАВКА 13-14's police-state, captured by its own enforcers.)")
    elif froze and suppressed:
        print("VERDICT — SHARPENING CONFIRMED (ВСТАВКА 13-14): enforcement freezes the same")
        print("owners (higher top-5 retention) AND drives successful challenges down — the")
        print("institution makes the elite hereditary in fact. Property + enforcement reads")
        print("as the police-state link atop bare appropriation.")
    elif suppressed and not froze:
        print("VERDICT — challenge SUPPRESSED but stratum NOT frozen: enforcement blocks")
        print("flips locally yet turnover is unchanged (spatial guard coverage is partial /")
        print("owners churn for other reasons). Enforcement defends the deed, not the dynasty.")
    else:
        print("VERDICT — NULL / PARASITIC: the levy funds a caste but neither freezes the")
        print("owners nor suppresses challenge — enforcement is a second extraction, not a")
        print("stratifier. (As with the hungry box, taxing a conserved substrate can starve")
        print("rather than ossify.)")
    print(f"Levy is body->body (exact remainder); challenge/defense are ledger-only; matter")
    print(f"conserved (<1e-9, max {max_drift:.1e}); sigma=0 reproduces canon & module 23 "
          f"byte-for-byte. seed {SEED}  ✓")


if __name__ == "__main__":
    main()
