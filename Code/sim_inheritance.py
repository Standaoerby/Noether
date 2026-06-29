"""
sim_inheritance.py — heritable property -> dynasties (module 25).

The institution (24) suppressed challenges but could not make the elite *hereditary*: its
E2 ossification was unmeasurable — the owner class went extinct, turnover nan. The missing
verb is **temporal persistence**: ownership that SURVIVES the owner's death and passes to an
heir of the same bloodline, instead of reverting to the commons. This module tests whether
dynasties form and hold across generations on a live, reproducing population.

`InheritanceWorld(InstitutionWorld)` keeps the chain cumulative (World25(World24)) but runs
the CLEAN test with the institution inert (`sigma=0` == AppropriationWorld byte-for-byte) —
inheritance WITHOUT the capacity-killing levy that collapsed module 24. A secondary arm
(`sigma=0.5, enforce=on`) then asks whether heritability rescues the dynasty the institution
killed, or merely inherits a graveyard.

One off-switchable seam, no base edits:
  * `_house[oid]` lineage map — reconstructed by OBSERVING birth events (each birth logs
    actor=child, parent=parent; founders are gen 0 with no birth event). A child joins its
    parent's house; `house(oid) = _house.get(oid, oid)` returns the root founder. Built only
    when `heritable` (gated -> OFF reads no log, touches no RNG).
  * Override `_do_claims`: when heritable, `_inherit_dead()` reassigns each dead owner's cell
    to a LIVING bloodline heir (lowest-oid living agent in the same house) BEFORE the parent
    prune; cells reassigned to a living heir survive the prune, reverted cells are gone.
    `heir_fallback` for an extinct line: "revert" (estate -> commons) | "escheat" (estate ->
    nearest living owner of any house; land consolidates into surviving houses).

Inheritance is a PURE LEDGER operation (reassign `_cell_owner` entries) — it adds zero
mass-moving operations. The only mass that moves is the inherited appropriation tribute
(rho), unchanged; default sigma=0 so no levy. matter_drift < 1e-9 by construction (asserted
at every config). `heritable=False` -> `_do_claims` delegates straight to super(), no `_house`,
no log read -> byte-identical to InstitutionWorld. Pure stdlib + numpy; no network.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

from sim_eventlog import EventLog, SEED
from sim_comm import R, C, DAYS, run as run_comm
from sim_sphere import GRID_DIAG, CANON_COMM
from sim_salience import gini, RAD, KK, LAG, FEW, W_INJ, AMT
from sim_appropriation import appropriation_fingerprint, RHO, BOX
from sim_institution import InstitutionWorld, M_E, APPROP_FP


class InheritanceWorld(InstitutionWorld):
    """InstitutionWorld where a dead owner's cells pass to a living bloodline heir instead
    of reverting. heritable=False is a true no-op (byte-identical parent at any config)."""

    def __init__(self, log, seed=SEED, regime="deceptive",
                 radius=GRID_DIAG + 1.0, K=None, lag=0,
                 injection_strength=0.0, injectors=0, inject_amount=50.0,
                 decay=1.0, target_policy="decoy",
                 arena_side=None, pin_victims_only=False,
                 appropriation=0.0, owner_policy="founders", owners=FEW,
                 sigma=0.0, enforce=False, enforcers=M_E,
                 heritable=False, heir_fallback="revert"):
        self.heritable = bool(heritable)
        self.heir_fallback = heir_fallback
        self._house = {}                 # oid -> parent's house root (founders absent -> self)
        self._house_cursor = 0           # log-event cursor for lineage reconstruction
        super().__init__(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                         injection_strength=injection_strength, injectors=injectors,
                         inject_amount=inject_amount, decay=decay,
                         target_policy=target_policy, arena_side=arena_side,
                         pin_victims_only=pin_victims_only, appropriation=appropriation,
                         owner_policy=owner_policy, owners=owners,
                         sigma=sigma, enforce=enforce, enforcers=enforcers)

    # ---- lineage (observation only, gated on heritable) -------------------- #
    def house(self, oid):
        return self._house.get(oid, oid)

    def _update_houses(self):
        ev = self.log.events
        for i in range(self._house_cursor, len(ev)):
            e = ev[i]
            if e.kind == "birth" and e.actor is not None:
                self._house[e.actor] = self._house.get(e.parent, e.parent)
        self._house_cursor = len(ev)

    # ---- the reversion-on-death seam --------------------------------------- #
    def _inherit_dead(self):
        if not self._cell_owner:
            return
        live = {a.oid for a in self.pop}
        heir_of = {}                     # house root -> lowest-oid living member
        for a in sorted(self.pop, key=lambda x: x.oid):
            heir_of.setdefault(self.house(a.oid), a.oid)
        dead_cells = sorted((c, o) for c, o in self._cell_owner.items() if o not in live)
        living_owned = None
        if self.heir_fallback == "escheat":
            living_owned = sorted((c, o) for c, o in self._cell_owner.items() if o in live)
        for cell, owner in dead_cells:
            heir = heir_of.get(self.house(owner))
            if heir is not None:                          # living bloodline kin
                self._cell_owner[cell] = heir
            elif self.heir_fallback == "escheat" and living_owned:
                # nearest living-owned cell; tie-break (owner oid, cell). Snapshot fixed
                # within the step, so reassignments don't chain non-deterministically.
                best = min(living_owned,
                           key=lambda co: (abs(co[0][0] - cell[0]) + abs(co[0][1] - cell[1]),
                                           co[1], co[0]))
                self._cell_owner[cell] = best[1]
            else:                                         # extinct line -> commons
                del self._cell_owner[cell]

    def _do_claims(self):
        if not self.heritable:
            return super()._do_claims()                   # OFF -> byte-identical parent
        self._inherit_dead()                              # reassign before the parent prune
        super()._do_claims()

    def step(self):
        if self.heritable:
            self._update_houses()                         # fold in births through last step
        super().step()


# --------------------------------------------------------------------------- #
#  Running + fingerprint + metrics                                             #
# --------------------------------------------------------------------------- #
SNAP_DAYS = (50, 150, 300)


def _snapshot(w):
    counts = w.territory_counts()
    ranked = [oid for oid, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    top5 = ranked[:5]
    per_house = defaultdict(int)
    for _c, oid in w._cell_owner.items():
        per_house[w.house(oid)] += 1
    owners_alive = w.owner_ids()
    ob = [a.body for a in w.pop if a.oid in owners_alive]
    nb = [a.body for a in w.pop if a.oid not in owners_alive]
    import numpy as np
    return {
        "t": w.t,
        "alive": len(w.pop),
        "n_owners": len(owners_alive),
        "owning_houses": frozenset(per_house),
        "top5": top5,
        "top5_houses": frozenset(w.house(o) for o in top5),
        "n_owned_cells": len(w._cell_owner),
        "terr_gini": gini(list(counts.values())) if counts else float("nan"),
        "house_gini": gini(list(per_house.values())) if per_house else float("nan"),
        "top_house_share": (max(per_house.values()) / sum(per_house.values()))
                           if per_house else float("nan"),
        "bio_gini": gini([a.body for a in w.pop]) if w.pop else float("nan"),
        "owner_gap": (float(np.mean(ob)) - float(np.mean(nb))) if (ob and nb) else float("nan"),
        "max_gen": max((w.gen.get(o, 0) for o in top5), default=0),
        "mean_gen": (sum(w.gen.get(o, 0) for o in top5) / len(top5)) if top5 else float("nan"),
    }


def run_inheritance(heritable=False, heir_fallback="revert", sigma=0.0, enforce=False,
                    owner_policy="claim", arena_side=None, appropriation=RHO,
                    injection_strength=0.0, injectors=0, enforcers=M_E,
                    regime="deceptive", radius=RAD, K=KK, lag=LAG,
                    inject_amount=AMT, decay=1.0, target_policy="decoy",
                    seed=SEED, days=DAYS):
    log = EventLog()
    w = InheritanceWorld(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                         injection_strength=injection_strength, injectors=injectors,
                         inject_amount=inject_amount, decay=decay,
                         target_policy=target_policy, arena_side=arena_side,
                         appropriation=appropriation, owner_policy=owner_policy,
                         owners=FEW, sigma=sigma, enforce=enforce, enforcers=enforcers,
                         heritable=heritable, heir_fallback=heir_fallback)
    snaps = {}
    for _ in range(days):
        w.step()
        if w.t in SNAP_DAYS:
            snaps[w.t] = _snapshot(w)
    w._snaps = snaps
    return w, log


def inheritance_fingerprint(w):
    h = hashlib.sha256()
    h.update(appropriation_fingerprint(w).encode())
    owners = sorted(w._cell_owner.items())
    h.update((f"|herit{int(w.heritable)}|{w.heir_fallback}|sigma{w.sigma:.6f}"
              f"|cells{len(w._cell_owner)}|houses{sorted({w.house(o) for o in w._cell_owner.values()})}"
              ).encode())
    for cell, oid in owners:
        h.update(f"{cell[0]},{cell[1]}={oid}".encode())
    return h.hexdigest()[:16]


def e2_dynasty(w):
    """Dynasty persistence from the snapshots (claim arm)."""
    sn = w._snaps
    if not sn or 300 not in sn:
        return {}
    end = sn[300]
    early_houses = sn[50]["owning_houses"] if 50 in sn else frozenset()
    distinct_top = set()
    for d in SNAP_DAYS:
        if d in sn:
            distinct_top |= sn[d]["top5_houses"]
    top5 = end["top5"]
    from_founding = (sum(1 for o in top5 if w.house(o) in early_houses) / len(top5)) \
        if top5 else float("nan")
    return {
        "distinct_top_houses": len(distinct_top),     # fewer -> more dynastic
        "end_distinct_owner_houses": len(end["owning_houses"]),
        "top5_from_early": from_founding,             # frac of end top-5 from an early house
        "end_max_gen": end["max_gen"],
        "end_mean_gen": end["mean_gen"],
        "end_top_house_share": end["top_house_share"],
        "end_house_gini": end["house_gini"],
    }


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
def _fmt(v, fmt="{:.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def main():
    line = "=" * 78
    print(line)
    print("INHERITANCE — heritable property -> dynasties (does the stratum persist in time?)")
    print("InheritanceWorld(InstitutionWorld): a dead owner's cells pass to a LIVING bloodline")
    print("heir (lowest-oid living kin) instead of reverting; extinct lines revert or escheat.")
    print("Clean test runs the institution inert (sigma=0). Pure ledger op -> matter untouched.")
    print(f"grid {R}x{C}; seed {SEED}; {DAYS}d; claim, rho={RHO}; snapshots {SNAP_DAYS}")
    print(line)

    max_drift = 0.0

    # --- B0: heritable=False + sigma=0 + all-off == canon (both policies) --- #
    for pol in ("founders", "claim"):
        w0, _ = run_inheritance(heritable=False, sigma=0.0, appropriation=0.0,
                                owner_policy=pol, radius=GRID_DIAG + 1.0, K=None, lag=0,
                                injection_strength=0.0, injectors=0, arena_side=None)
        fp = w0.state_fingerprint(); max_drift = max(max_drift, w0.matter_drift())
        ok = fp == CANON_COMM and not w0._house
        print(f"B0  heritable=off sigma=0 all-off [{pol:<8}] : {fp} vs canon {CANON_COMM} -> "
              f"{'BYTE-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
        assert ok, f"B0 [{pol}] not byte-identical to canon / house map built when off"

    # --- B1: heritable=False + sigma=0 at appropriation headline ------------ #
    wb1, _ = run_inheritance(heritable=False, sigma=0.0, appropriation=RHO,
                             owner_policy="founders", arena_side=BOX,
                             injection_strength=W_INJ, injectors=FEW)
    fpb1 = appropriation_fingerprint(wb1); okb1 = fpb1 == APPROP_FP
    print(f"B1  heritable=off sigma=0 approp-headline       : {fpb1} vs {APPROP_FP} -> "
          f"{'BYTE-IDENTICAL ✓' if okb1 else 'MISMATCH ✗'}")
    assert okb1, "B1 not byte-identical to module-23 self-check (base drift!)"

    # --- main cross-product (claim, sigma=0, rho=0.5) ----------------------- #
    print(f"\nMAIN (claim, sigma=0, rho={RHO}); dynasty persistence + lineage concentration:")
    hdr = f"{'herit':>6}{'fallbk':>8}{'arena':>6}{'distTopH':>9}{'endOwnH':>8}" \
          f"{'top5_earl':>10}{'maxGen':>7}{'houseGini':>10}{'topHshr':>8}{'drift':>9}"
    print(hdr); print("-" * len(hdr))
    rows = {}
    configs = [("off", "revert", None), ("off", "revert", BOX)]
    for fb in ("revert", "escheat"):
        for arena in (None, BOX):
            configs.append(("on", fb, arena))
    for herit, fb, arena in configs:
        w, _ = run_inheritance(heritable=(herit == "on"), heir_fallback=fb, sigma=0.0,
                               owner_policy="claim", arena_side=arena,
                               injection_strength=0.0, injectors=0)
        d = w.matter_drift(); max_drift = max(max_drift, d)
        assert d < 1e-9, f"leak herit={herit} fb={fb} arena={arena}: {d}"
        e2 = e2_dynasty(w)
        rows[(herit, fb, arena)] = (w, e2)
        print(f"{herit:>6}{(fb if herit == 'on' else '-'):>8}{str(arena or '-'):>6}"
              f"{e2.get('distinct_top_houses', 0):>9}{e2.get('end_distinct_owner_houses', 0):>8}"
              f"{_fmt(e2.get('top5_from_early')):>10}{e2.get('end_max_gen', 0):>7}"
              f"{_fmt(e2.get('end_house_gini')):>10}{_fmt(e2.get('end_top_house_share')):>8}"
              f"{d:>9.1e}")

    # --- inequality trajectory: heritable off vs on (revert), box6 ---------- #
    print(f"\nINEQUALITY TRAJECTORY (claim, box{BOX}, revert): does inheritance ratchet up?")
    print(f"  {'config':>14}" + "".join(f"{f'd{d}':>22}" for d in SNAP_DAYS))
    print(f"  {'':>14}" + "".join(f"{'bioGini/terrGini':>22}" for _ in SNAP_DAYS))
    for herit in ("off", "on"):
        w = rows[(herit, "revert", BOX)][0]
        line_cells = "".join(
            f"{(_fmt(w._snaps[d]['bio_gini']) + '/' + _fmt(w._snaps[d]['terr_gini'])):>22}"
            for d in SNAP_DAYS)
        print(f"  {('heritable ' + herit):>14}{line_cells}")

    # --- E3 body-gap trajectory: off vs on (revert, box6) ------------------- #
    print(f"\nE3 owner-nonowner body gap trajectory (claim, box{BOX}, revert):")
    print(f"  {'config':>14}" + "".join(f"{f'd{d}':>10}" for d in SNAP_DAYS))
    for herit in ("off", "on"):
        w = rows[(herit, "revert", BOX)][0]
        print(f"  {('heritable '+herit):>14}"
              + "".join(f"{_fmt(w._snaps[d]['owner_gap'], '{:+.2f}'):>10}" for d in SNAP_DAYS))

    # --- secondary arm: inheritance UNDER the institution (sigma=0.5) ------- #
    print(f"\nSECONDARY ARM — inheritance UNDER the institution (sigma=0.5, enforce=on):")
    print(f"  {'fallbk':>8}{'arena':>6}{'alive(end)':>11}{'endOwnH':>8}{'maxGen':>7}"
          f"{'ownGap':>9}{'drift':>9}")
    for fb in ("revert", "escheat"):
        for arena in (None, BOX):
            w, _ = run_inheritance(heritable=True, heir_fallback=fb, sigma=0.5, enforce=True,
                                   owner_policy="claim", arena_side=arena,
                                   injection_strength=0.0, injectors=0)
            d = w.matter_drift(); max_drift = max(max_drift, d)
            assert d < 1e-9, f"leak secondary fb={fb} arena={arena}: {d}"
            e2 = e2_dynasty(w)
            print(f"  {fb:>8}{str(arena or '-'):>6}{len(w.pop):>11}"
                  f"{e2.get('end_distinct_owner_houses', 0):>8}{e2.get('end_max_gen', 0):>7}"
                  f"{_fmt(w._snaps[300]['owner_gap'], '{:+.2f}'):>9}{d:>9.1e}")

    # --- self-check fingerprint --------------------------------------------- #
    wf, _ = run_inheritance(heritable=True, heir_fallback="revert", sigma=0.0,
                            owner_policy="claim", arena_side=BOX,
                            injection_strength=0.0, injectors=0)
    fp1 = inheritance_fingerprint(wf)
    wf2, _ = run_inheritance(heritable=True, heir_fallback="revert", sigma=0.0,
                             owner_policy="claim", arena_side=BOX,
                             injection_strength=0.0, injectors=0)
    fp2 = inheritance_fingerprint(wf2)
    max_drift = max(max_drift, wf.matter_drift())
    print(f"\nINHERITANCE_FINGERPRINT: {fp1}")
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp1 == fp2 else 'MISMATCH ✗'}")
    assert fp1 == fp2, "inheritance run is not reproducible"
    print(f"max matter drift across battery: {max_drift:.2e} kg")
    assert max_drift < 1e-9, "a config leaked matter"

    # --- honest verdict (box6, revert: off vs on) --------------------------- #
    off_e2 = rows[("off", "revert", BOX)][1]
    on_e2 = rows[("on", "revert", BOX)][1]
    esc_e2 = rows[("on", "escheat", BOX)][1]
    print(f"\n{line}")
    fewer_houses = on_e2.get("distinct_top_houses", 99) < off_e2.get("distinct_top_houses", 0)
    deeper = (on_e2.get("end_max_gen", 0) or 0) > (off_e2.get("end_max_gen", 0) or 0)
    dynastic = fewer_houses and (on_e2.get("top5_from_early", 0) or 0) >= 0.4
    print(f"E2 dynasty (claim, box{BOX}, revert): distinct top-houses over run  "
          f"off {off_e2.get('distinct_top_houses')} -> on {on_e2.get('distinct_top_houses')}; "
          f"end top-5 from an early house off {_fmt(off_e2.get('top5_from_early'))} -> "
          f"on {_fmt(on_e2.get('top5_from_early'))}; max gen-depth at top "
          f"off {off_e2.get('end_max_gen')} -> on {on_e2.get('end_max_gen')}")
    print(f"E1 lineage concentration: end top-house land share off "
          f"{_fmt(off_e2.get('end_top_house_share'))} -> on {_fmt(on_e2.get('end_top_house_share'))}; "
          f"house-Gini off {_fmt(off_e2.get('end_house_gini'))} -> on {_fmt(on_e2.get('end_house_gini'))}")
    print(f"revert vs escheat (end top-house share): revert {_fmt(on_e2.get('end_top_house_share'))} "
          f"vs escheat {_fmt(esc_e2.get('end_top_house_share'))}; escheat house-Gini "
          f"{_fmt(esc_e2.get('end_house_gini'))}")
    if dynastic or deeper:
        print("VERDICT — DYNASTIES FORM: heritability concentrates land into fewer, older")
        print("houses than the death-reset churn (deeper gen-depth at the top, end land traces")
        print("to early-owning founding houses) — the hereditary-elite link of ВСТАВКА 13-14,")
        print("on a live reproducing population, that the institution alone could not produce.")
    else:
        print("VERDICT — heritability does NOT durably ossify here: owners die faster than they")
        print("breed available heirs (or churn dominates), so dynasties do not pull ahead of the")
        print("death-reset baseline. Heritability needs reproduction headroom to bite.")
    print("Inheritance is pure ledger (zero mass ops); matter conserved "
          f"(<1e-9, max {max_drift:.1e}); heritable=off reproduces canon & module 23 "
          f"byte-for-byte. seed {SEED}  ✓")


if __name__ == "__main__":
    main()
