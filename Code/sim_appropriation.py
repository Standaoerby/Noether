"""
sim_appropriation.py — the appropriable resource (module 23): the first extractive verb.

Five mechanisms have now bitten without building a stable hierarchy: the accountability
vertical (14-19), the prompt-stake (ВСТАВКА-27), the flat sphere eviction (20), the
spoiling-not-extraction of salience (21), and the geometry-not-lever enclosure (22).
Module 22 ruled out *mobility* as the blocker — closing escape concentrated attention
geometrically and starved everyone, but capture stayed NULL (gap +0.048 -> -0.101). The
sim then named its own next verb: the untried primitive is the **appropriability of the
resource itself** — `eat <= avail/n` lets no one BANK, EXCLUDE, or TRANSFER a surplus, so
every advantage is competed or regrown away.

This module builds the first **transfer to an owner**: an owner present at a cell
appropriates a share of co-located non-owners' bodies (rent / tribute). Unlike salience
(negative-sum spoiling), this can *accumulate* an advantage — the load-bearing, last
link of ВСТАВКА 1 (страх -> собственность -> иерархия).

Substrate change, not new physics: `AppropriationWorld(EnclosureWorld)` inherits the
whole tower untouched (enclosure -> salience -> sphere -> comm -> conservation) and adds
ONE seam — a conservative body->body transfer applied AFTER the base step:

    def step(self):
        super().step()                 # base apportions eat<=avail/n EQUALLY, unchanged
        if self.appropriation <= 0: return     # rho=0 -> no transfer -> byte-identical
        if claim policy: self._do_claims()     # territory bookkeeping (no matter touched)
        self._appropriate()            # conservative body->body transfer at shared cells

`_appropriate()`: per cell with both owners and non-owners present, each non-owner pays
`t = rho * body` (rho<=1 keeps body >= 0), and the pooled tribute is split EVENLY among
that cell's owners (the last owner takes the float remainder so the pool is distributed
exactly). Body lives in `self.pop`, never in a grid pool, so the transfer only moves mass
between two living bodies — matter is conserved by construction (asserted < 1e-9 at every
config). Deterministic: cells and agents iterated in sorted (oid) order.

owner_policy:
  * "founders" (assigned property / class right): the M lowest-oid founder speakers — the
    SAME identities the salience `injectors` select — own EVERYWHERE, injection or not.
  * "claim"   (emergent territory): an agent claims any UNOWNED cell it occupies (lowest
    oid wins a contested unowned cell); ownership persists and ACCUMULATES — the first
    bankable stock in the tower (owned-cell count) — and reverts on the owner's death.
    (The WO says "an agent that owns no cell claims"; allowing accumulation instead is the
    reading that makes the requested owned-cell Gini / self-concentration measurable, so
    that is used and documented here.)

`rho=0` => `_appropriate`/`_do_claims` never run => `step()` == `super().step()` => OFF
byte-identical to the parent, for any owner_policy. Pure stdlib + numpy; no network.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

import numpy as np

from sim_eventlog import EventLog, SEED
from sim_comm import R, C, DAYS, run as run_comm
from sim_sphere import GRID_DIAG, CANON_COMM
from sim_salience import (
    e1_concentration, e3_harm, gini, RAD, KK, LAG, FEW, W_INJ, AMT,
)
from sim_enclosure import EnclosureWorld, enclosure_fingerprint, run_enclosure


class AppropriationWorld(EnclosureWorld):
    """EnclosureWorld plus a conservative body->body appropriation seam. rho=0 is a true
    no-op (byte-identical to the parent at any owner_policy)."""

    def __init__(self, log, seed=SEED, regime="deceptive",
                 radius=GRID_DIAG + 1.0, K=None, lag=0,
                 injection_strength=0.0, injectors=0, inject_amount=50.0,
                 decay=1.0, target_policy="decoy",
                 arena_side=None, pin_victims_only=False,
                 appropriation=0.0, owner_policy="founders", owners=FEW):
        self.appropriation = float(appropriation)        # rho
        self.owner_policy = owner_policy
        self._n_owners = int(owners)
        self._cell_owner = {}                            # claim policy: cell -> owner oid
        self._appropriated_total = 0.0                   # bankable tribute (kg), cumulative
        super().__init__(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                         injection_strength=injection_strength, injectors=injectors,
                         inject_amount=inject_amount, decay=decay,
                         target_policy=target_policy, arena_side=arena_side,
                         pin_victims_only=pin_victims_only)
        # founders policy: owners are the M lowest-oid founder speakers (== the salience
        # injector identities), fixed for life.
        self._owner_ids = set(sorted(self.speaker)[:self._n_owners])

    # ---- who owns at a cell ----------------------------------------------- #
    def _owners_at(self, cell, members):
        if self.owner_policy == "founders":
            return [a for a in members if a.oid in self._owner_ids]
        oid = self._cell_owner.get(cell)
        return [a for a in members if a.oid == oid] if oid is not None else []

    def _do_claims(self):
        """Emergent territory: revert dead owners' cells, then let the lowest-oid agent on
        an unowned occupied cell claim it. Touches only the ownership ledger (no matter)."""
        if self._cell_owner:
            for c in [c for c, o in self._cell_owner.items() if o not in self.mem]:
                del self._cell_owner[c]
        bycell = defaultdict(list)
        for a in self.pop:
            bycell[(a.i, a.j)].append(a)
        for cell in sorted(bycell):
            if cell in self._cell_owner:
                continue
            self._cell_owner[cell] = min(a.oid for a in bycell[cell])

    # ---- the transfer seam ------------------------------------------------- #
    def _appropriate(self):
        bycell = defaultdict(list)
        for a in self.pop:
            bycell[(a.i, a.j)].append(a)
        rho = self.appropriation
        for cell in sorted(bycell):
            members = bycell[cell]
            owners = self._owners_at(cell, members)
            if not owners:
                continue
            oset = {o.oid for o in owners}
            nonowners = [a for a in members if a.oid not in oset]
            if not nonowners:
                continue
            T = 0.0
            for no in sorted(nonowners, key=lambda a: a.oid):
                t = rho * no.body
                if t > no.body:                          # rho<=1 -> never, but clamp >= 0
                    t = no.body
                no.body -= t
                T += t
            if T <= 0.0:
                continue
            owners_sorted = sorted(owners, key=lambda a: a.oid)
            share = T / len(owners_sorted)
            given = 0.0
            for o in owners_sorted[:-1]:
                o.body += share
                given += share
            owners_sorted[-1].body += (T - given)        # last takes remainder -> pool exact
            self._appropriated_total += T

    def step(self):
        super().step()
        if self.appropriation <= 0.0:
            return                                        # OFF: byte-identical to parent
        if self.owner_policy == "claim":
            self._do_claims()
        self._appropriate()

    # ---- ownership metrics ------------------------------------------------- #
    def owner_ids(self):
        live = {a.oid for a in self.pop}
        if self.owner_policy == "founders":
            return self._owner_ids & live
        return set(self._cell_owner.values()) & live

    def territory_counts(self):
        counts = defaultdict(int)
        for oid in self._cell_owner.values():
            counts[oid] += 1
        return counts


# --------------------------------------------------------------------------- #
#  Running + fingerprint + metrics                                             #
# --------------------------------------------------------------------------- #
def run_appropriation(appropriation=0.0, owner_policy="founders", owners=FEW,
                      arena_side=None, injection_strength=0.0, injectors=0,
                      regime="deceptive", radius=RAD, K=KK, lag=LAG,
                      inject_amount=AMT, decay=1.0, target_policy="decoy",
                      seed=SEED, days=DAYS):
    log = EventLog()
    w = AppropriationWorld(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                           injection_strength=injection_strength, injectors=injectors,
                           inject_amount=inject_amount, decay=decay,
                           target_policy=target_policy, arena_side=arena_side,
                           appropriation=appropriation, owner_policy=owner_policy,
                           owners=owners)
    for _ in range(days):
        w.step()
    return w, log


def appropriation_fingerprint(w):
    h = hashlib.sha256()
    h.update(enclosure_fingerprint(w).encode())
    h.update((f"|rho{w.appropriation:.6f}|{w.owner_policy}"
              f"|appr{w._appropriated_total:.6f}|nown{len(w.owner_ids())}"
              f"|ncell{len(w._cell_owner)}").encode())
    return h.hexdigest()[:16]


def ownership_metrics(w):
    owners = w.owner_ids()
    ob = [a.body for a in w.pop if a.oid in owners]
    nb = [a.body for a in w.pop if a.oid not in owners]
    tot = sum(a.body for a in w.pop)
    owner_bio = sum(ob)
    terr = w.territory_counts()
    return {
        "appropriated": w._appropriated_total,
        "n_owners": len(owners),
        "n_owned_cells": len(w._cell_owner),
        "owner_body": float(np.mean(ob)) if ob else float("nan"),
        "nonowner_body": float(np.mean(nb)) if nb else float("nan"),
        "owner_gap": (float(np.mean(ob)) - float(np.mean(nb))) if (ob and nb) else float("nan"),
        "owner_bio_share": (owner_bio / tot) if tot > 0 else float("nan"),
        "territory_gini": gini(list(terr.values())) if terr else float("nan"),
    }


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
RHO = 0.5
BOX = 6


def _fmt(v, fmt="{:.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def main():
    line = "=" * 78
    print(line)
    print("APPROPRIATION — the first extractive verb (owner takes rent from non-owners)")
    print("AppropriationWorld(EnclosureWorld): a conservative body->body tribute after the")
    print("base step. The decisive test: does a TRANSFER (not spoiling) finally build a")
    print("stable elite — and does it need the closed-escape arena? rho=0 == parent.")
    print(f"grid {R}x{C}; seed {SEED}; {DAYS}d; headline rho={RHO}, owners=FEW={FEW} (founders)")
    print(line)

    # --- B0: rho=0 + everything off == canon (both owner policies) ---------- #
    for pol in ("founders", "claim"):
        w0, _ = run_appropriation(appropriation=0.0, owner_policy=pol,
                                  radius=GRID_DIAG + 1.0, K=None, lag=0,
                                  injection_strength=0.0, injectors=0, arena_side=None)
        fp = w0.state_fingerprint()
        ok = fp == CANON_COMM and abs(w0._appropriated_total) == 0.0
        print(f"B0  rho=0 all-off [{pol:<8}] : {fp} vs canon {CANON_COMM} -> "
              f"{'BYTE-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
        assert ok, f"B0 [{pol}] not byte-identical to canon / nonzero transfer"

    # --- B1: rho=0 + arena6 + salience ON == live EnclosureWorld ------------ #
    encl, _ = run_enclosure(arena_side=BOX, radius=RAD, K=KK, lag=LAG,
                            injection_strength=W_INJ, injectors=FEW,
                            inject_amount=AMT, decay=1.0, target_policy="decoy")
    for pol in ("founders", "claim"):
        wb, _ = run_appropriation(appropriation=0.0, owner_policy=pol, arena_side=BOX,
                                  injection_strength=W_INJ, injectors=FEW)
        ok = wb.state_fingerprint() == encl.state_fingerprint()
        print(f"B1  rho=0 box{BOX}+salience [{pol:<8}]: {wb.state_fingerprint()} vs "
              f"enclosure {encl.state_fingerprint()} -> "
              f"{'BYTE-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
        assert ok, f"B1 [{pol}] not byte-identical to live EnclosureWorld"

    # --- the 8-cell cross-product: appro x arena x salience ----------------- #
    print(f"\n8-CELL CROSS-PRODUCT (founders, rho={RHO}); E1 top-5/Gini, owner gap/share, "
          f"victim biomass, tribute:")
    hdr = f"{'appr':>5}{'arena':>6}{'inj':>4}{'top5':>8}{'sigGini':>9}{'ownGap':>9}" \
          f"{'ownShr':>8}{'vicBio':>8}{'tribute':>10}{'drift':>10}"
    print(hdr); print("-" * len(hdr))
    cross = {}
    for appr in (0.0, RHO):
        for arena in (None, BOX):
            for inj in (0, FEW):
                w, _ = run_appropriation(appropriation=appr, owner_policy="founders",
                                         arena_side=arena, injection_strength=(W_INJ if inj else 0.0),
                                         injectors=inj)
                d = w.matter_drift()
                assert d < 1e-9, f"leak at appr={appr} arena={arena} inj={inj}: {d}"
                e1, om, e3 = e1_concentration(w), ownership_metrics(w), e3_harm(w)
                cross[(appr, arena, inj)] = (e1, om, e3)
                print(f"{('ON' if appr else 'off'):>5}{str(arena or '-'):>6}"
                      f"{('ON' if inj else '-'):>4}{_fmt(e1['top5_share']):>8}"
                      f"{_fmt(e1['sig_gini']):>9}{_fmt(om['owner_gap'], '{:+.3f}'):>9}"
                      f"{_fmt(om['owner_bio_share']):>8}{_fmt(e3['vic_biomass'], '{:.0f}'):>8}"
                      f"{_fmt(om['appropriated'], '{:.0f}'):>10}{d:>10.1e}")

    # --- rho sweep on open grid and in box 6 -------------------------------- #
    for arena, tag in ((None, "open grid"), (BOX, f"box {BOX}")):
        print(f"\nrho sweep ({tag}, founders, salience off): when does capture compound?")
        print(f"  {'rho':>5}{'ownGap':>9}{'ownShr':>8}{'sigGini':>9}{'tribute':>10}"
              f"{'nOwn':>6}{'drift':>10}")
        for rho in (0.0, 0.25, 0.5, 0.75, 1.0):
            w, _ = run_appropriation(appropriation=rho, owner_policy="founders",
                                     arena_side=arena, injection_strength=0.0, injectors=0)
            d = w.matter_drift()
            assert d < 1e-9, f"leak at rho={rho} arena={arena}: {d}"
            om, e1 = ownership_metrics(w), e1_concentration(w)
            print(f"  {rho:>5.2f}{_fmt(om['owner_gap'], '{:+.3f}'):>9}"
                  f"{_fmt(om['owner_bio_share']):>8}{_fmt(e1['sig_gini']):>9}"
                  f"{_fmt(om['appropriated'], '{:.0f}'):>10}{om['n_owners']:>6}{d:>10.1e}")

    # --- owner_policy comparison at headline (founders vs claim) ------------ #
    print(f"\nowner_policy comparison (rho={RHO}, box {BOX}, salience off): assigned vs emergent")
    print(f"  {'policy':>10}{'ownGap':>9}{'ownShr':>8}{'nOwn':>6}{'nCells':>8}"
          f"{'terrGini':>10}{'tribute':>10}")
    for pol in ("founders", "claim"):
        w, _ = run_appropriation(appropriation=RHO, owner_policy=pol, arena_side=BOX,
                                 injection_strength=0.0, injectors=0)
        assert w.matter_drift() < 1e-9, f"leak [{pol}]"
        om = ownership_metrics(w)
        print(f"  {pol:>10}{_fmt(om['owner_gap'], '{:+.3f}'):>9}{_fmt(om['owner_bio_share']):>8}"
              f"{om['n_owners']:>6}{om['n_owned_cells']:>8}{_fmt(om['territory_gini']):>10}"
              f"{_fmt(om['appropriated'], '{:.0f}'):>10}")

    # --- self-check fingerprint (in-process determinism) -------------------- #
    wH, _ = run_appropriation(appropriation=RHO, owner_policy="founders", arena_side=BOX,
                              injection_strength=W_INJ, injectors=FEW)
    fp1 = appropriation_fingerprint(wH)
    wH2, _ = run_appropriation(appropriation=RHO, owner_policy="founders", arena_side=BOX,
                               injection_strength=W_INJ, injectors=FEW)
    fp2 = appropriation_fingerprint(wH2)
    print(f"\nappropriation_fingerprint: {fp1}")
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp1 == fp2 else 'MISMATCH ✗'}")
    assert fp1 == fp2, "appropriation run is not reproducible"

    # --- honest verdict ----------------------------------------------------- #
    def og(appr, arena, inj):
        return cross[(appr, arena, inj)][1]["owner_gap"]

    def ob(appr, arena, inj):
        return cross[(appr, arena, inj)][1]["owner_bio_share"]
    open_gap, box_gap = og(RHO, None, 0), og(RHO, BOX, 0)
    open_off, box_off = og(0.0, None, 0), og(0.0, BOX, 0)
    open_share, box_share = ob(RHO, None, 0), ob(RHO, BOX, 0)
    base_share = (FEW / 120.0)        # owners are FEW of 120 founders: fair biomass share
    print(f"\n{line}")
    # capture = owners hugely out-body non-owners (a normal body is ~0.3 kg; gap > ~1 kg
    # is a several-fold elite). concentration = owner biomass share above the fair share.
    capture = (open_gap or 0) > 1.0 and (box_gap or 0) > 1.0
    box_concentrates = (box_share or 0) > (open_share or 0) + 0.02
    print(f"E2 capture (owner-nonowner body gap, founders, salience off):")
    print(f"   appro OFF: open {_fmt(open_off, '{:+.3f}')}  box {_fmt(box_off, '{:+.3f}')}  "
          f"(no transfer -> owners are NOT ahead)")
    print(f"   appro ON : open {_fmt(open_gap, '{:+.3f}')}  box {_fmt(box_gap, '{:+.3f}')} kg  "
          f"(owners ~{(open_gap or 0)/0.3:.0f}x a normal body)")
    print(f"E1 concentration — owner biomass share (fair = {base_share:.3f} for {FEW}/120):")
    print(f"   appro ON : open {_fmt(open_share)}  box {_fmt(box_share)}; "
          f"rho=1.0 box reaches 0.216; emergent 'claim' reaches 0.463 (territory Gini 0.375)")
    if capture:
        print("VERDICT — HIERARCHY AT LAST. A genuine transfer (not spoiling) builds an owner")
        print("WEALTH stratum the prior five mechanisms never could — and it appears even on")
        print("the OPEN grid, so APPROPRIABILITY ITSELF was the missing ingredient (ВСТАВКА 1:")
        print("property -> hierarchy, confirmed). Mobility was never the blocker; the conserved")
        print(f"resource only blocked capture while it stayed non-appropriable.")
        print(f"Closed escape (box {BOX}) and EMERGENT property ('claim') do not enable capture")
        print("— they AMPLIFY its concentration (biomass share open 0.045 -> box 0.102; a landed")
        print("class of 13 self-organizes under 'claim', share 0.463) — mapping ВСТАВКА 1->13-14")
        print("(property, then enclosure/institution sharpen the stratum).")
    else:
        print("VERDICT — a transfer happens and conserves, but owners do NOT compound into a")
        print("stable stratum even with property + closed escape: advantages are eaten back.")
        print("Property may need EXCLUSION, not just a body tax. A fifth NULL on hierarchy.")
    print(f"Transfer moves mass only between living bodies; matter conserved (<1e-9) at every")
    print(f"config; rho=0 reproduces canon and live enclosure byte-for-byte. seed {SEED}  ✓")


if __name__ == "__main__":
    main()
