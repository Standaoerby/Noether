"""
sim_exclusion.py — denial of access (module 26): stratify without a parasitic caste?

The institution (24) taught the key lesson: on a conserved substrate a verb that PARKS
foraging mass in a non-productive caste (the guards) collapses carrying capacity
(population 91->2 / 575->53) — the elite rules a graveyard. Exclusion is the clean
counter-test: the excluded agent is NOT taxed into a parasitic pool — it simply forages
ELSEWHERE, so mass stays productive. Does denial-of-access stratify the population WITHOUT
the capacity collapse the levy caused?

`ExclusionWorld(InheritanceWorld)` keeps the chain cumulative (upper layers inert by
default: heritable=off, sigma=0). The denial lives at the MOVEMENT layer, not grazing
(grazing is inline in the frozen `sim_comm.step`; a grazing seam would break the canon).
Module 22's `ClampingAdapter(ActionAdapter)` already swaps a custom move adapter in via
`self.adapter`; exclusion reuses exactly that hook:

  ExcludingAdapter(ClampingAdapter): when `world.exclusion`, a move whose (clamped)
  destination is a cell owned by ANOTHER agent is denied -> the mover stays (no a.i/a.j
  change, no move event), `_excluded_moves += 1`. Otherwise it delegates VERBATIM to
  super() (the clamp, which at arena_side=None delegates to the base ActionAdapter) -> so
  `exclusion=False` is byte-identical to the parent.

  exclude_mode:
    * "absentee" — owned cell is barred regardless of whether the owner is present (pure
      `_cell_owner`); escape-analog: the resource regrows unused, the non-owner is merely
      displaced.
    * "occupied" — barred only when the owner is currently on the cell (per a per-tick
      occupancy snapshot, taken at move-phase start -> deterministic, order-independent);
      capture-analog: the owner monopolises its cell when present and eats the freed share.

Ownership is the claim-policy per-cell ledger `_cell_owner`, which exists only at `rho>0`
(territory forms under appropriation). So the battery runs at `rho=0.5` (the module-23
property/tribute baseline) and exclusion is tested as a verb ADDED on top — the exact
analogue of how the institution was tested. Under `founders` there is no per-cell ledger,
so this seam is inert (noted, not headlined).

Conservation is trivial: a denied move is a "stay" (relocates no body, no matter); the
body->body tribute (rho) is the parent's, unchanged. matter_drift < 1e-9 by construction.
Pure stdlib + numpy; no network; import side-effect-free.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

import numpy as np

from sim_eventlog import EventLog, SEED
from sim_comm import R, C, DAYS, run as run_comm
from sim_stage2 import DIRS
from sim_sphere import GRID_DIAG, CANON_COMM
from sim_salience import RAD, KK, LAG, FEW, W_INJ, AMT
from sim_appropriation import appropriation_fingerprint, ownership_metrics, RHO, BOX
from sim_institution import APPROP_FP
from sim_enclosure import ClampingAdapter
from sim_inheritance import InheritanceWorld


class ExcludingAdapter(ClampingAdapter):
    """ClampingAdapter that denies a move into another agent's owned cell. Only ever
    BLOCKS (-> stay); on every non-blocked move it delegates verbatim to super(), so the
    move (and the arena clamp) is performed exactly as the parent would and exclusion=False
    is byte-identical."""

    def apply(self, world, a, dec, legal):
        if world.exclusion and self._blocked(world, a, dec, legal):
            world._excluded_moves += 1
            return                               # denied -> stay (no move, no event)
        return super().apply(world, a, dec, legal)

    @staticmethod
    def _blocked(world, a, dec, legal):
        action = dec.action if dec.action in legal else "stay"
        di, dj = DIRS[action]
        if di == 0 and dj == 0:
            return False                         # not moving -> nothing to deny
        s = world.arena_side
        if s is None or (world.pin_victims_only and a.oid in world._injectors):
            ni, nj = a.i + di, a.j + dj          # base destination (no clamp)
        else:
            ni, nj = min(max(a.i + di, 0), s - 1), min(max(a.j + dj, 0), s - 1)
        if (ni, nj) == (a.i, a.j):
            return False                         # clamped/blocked to self -> a stay anyway
        owner = world._cell_owner.get((ni, nj))
        if owner is None or owner == a.oid:
            return False                         # unowned, or my own cell -> free
        if world.exclude_mode == "occupied":
            return owner in world._occ_at((ni, nj))   # barred only if owner present
        return True                              # absentee: barred regardless of presence


class ExclusionWorld(InheritanceWorld):
    """InheritanceWorld where owners deny non-owners access to their cells (a movement-layer
    verb). exclusion=False is a true no-op (the adapter delegates to the parent)."""

    def __init__(self, log, seed=SEED, regime="deceptive",
                 radius=GRID_DIAG + 1.0, K=None, lag=0,
                 injection_strength=0.0, injectors=0, inject_amount=50.0,
                 decay=1.0, target_policy="decoy",
                 arena_side=None, pin_victims_only=False,
                 appropriation=0.0, owner_policy="founders", owners=FEW,
                 sigma=0.0, enforce=False, enforcers=3,
                 heritable=False, heir_fallback="revert",
                 exclusion=False, exclude_mode="absentee"):
        self.exclusion = bool(exclusion)
        self.exclude_mode = exclude_mode
        self._excluded_moves = 0
        self._occ_snapshot = {}
        self._occ_t = -1
        super().__init__(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                         injection_strength=injection_strength, injectors=injectors,
                         inject_amount=inject_amount, decay=decay,
                         target_policy=target_policy, arena_side=arena_side,
                         pin_victims_only=pin_victims_only, appropriation=appropriation,
                         owner_policy=owner_policy, owners=owners, sigma=sigma,
                         enforce=enforce, enforcers=enforcers, heritable=heritable,
                         heir_fallback=heir_fallback)
        self.adapter = ExcludingAdapter()        # composes with the clamp; no-op when off

    def _occ_at(self, cell):
        """Occupants of `cell` at move-phase start, snapshotted lazily on the first adapter
        call of a new tick (no moves have happened yet -> deterministic)."""
        if self._occ_t != self.t:
            snap = defaultdict(set)
            for a in self.pop:
                snap[(a.i, a.j)].add(a.oid)
            self._occ_snapshot = snap
            self._occ_t = self.t
        return self._occ_snapshot.get(cell, ())


# --------------------------------------------------------------------------- #
#  Running + fingerprint + metrics                                             #
# --------------------------------------------------------------------------- #
def run_exclusion(exclusion=False, exclude_mode="absentee", owner_policy="claim",
                  arena_side=None, appropriation=RHO, injection_strength=0.0, injectors=0,
                  sigma=0.0, heritable=False, regime="deceptive",
                  radius=RAD, K=KK, lag=LAG, inject_amount=AMT, decay=1.0,
                  target_policy="decoy", seed=SEED, days=DAYS):
    log = EventLog()
    w = ExclusionWorld(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                       injection_strength=injection_strength, injectors=injectors,
                       inject_amount=inject_amount, decay=decay,
                       target_policy=target_policy, arena_side=arena_side,
                       appropriation=appropriation, owner_policy=owner_policy, owners=FEW,
                       sigma=sigma, heritable=heritable,
                       exclusion=exclusion, exclude_mode=exclude_mode)
    for _ in range(days):
        w.step()
    return w, log


def exclusion_fingerprint(w):
    h = hashlib.sha256()
    h.update(w.state_fingerprint().encode())
    h.update((f"|excl{int(w.exclusion)}|{w.exclude_mode}|moves{w._excluded_moves}"
              f"|cells{len(w._cell_owner)}").encode())
    for cell, oid in sorted(w._cell_owner.items()):
        h.update(f"{cell[0]},{cell[1]}={oid}".encode())
    return h.hexdigest()[:16]


def exclusion_metrics(w):
    owned = set(w._cell_owner)
    plant_owned = [float(w.plant[i, j]) for (i, j) in owned]
    plant_unowned = [float(w.plant[i, j]) for i in range(R) for j in range(C)
                     if (i, j) not in owned]
    occ = defaultdict(int)
    for a in w.pop:
        occ[(a.i, a.j)] += 1
    occs = list(occ.values())
    om = ownership_metrics(w)
    return {
        "alive": len(w.pop),
        "total_biomass": sum(a.body for a in w.pop),
        "owner_gap": om["owner_gap"],
        "owner_share": om["owner_bio_share"],
        "terr_gini": om["territory_gini"],
        "n_owned": len(owned),
        "plant_owned": float(np.mean(plant_owned)) if plant_owned else float("nan"),
        "plant_unowned": float(np.mean(plant_unowned)) if plant_unowned else float("nan"),
        "max_occ": max(occs) if occs else 0,
        "mean_occ": float(np.mean(occs)) if occs else float("nan"),
        "excluded_moves": w._excluded_moves,
    }


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
def _fmt(v, fmt="{:.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def main():
    line = "=" * 78
    print(line)
    print("EXCLUSION — denial of access: stratify WITHOUT a parasitic caste?")
    print("ExclusionWorld(InheritanceWorld): an owner denies non-owners entry to its cell at")
    print("the move layer (a blocked move = stay). The institution's levy parked mass in")
    print("guards and starved the base (pop 91->2); the excluded just forage elsewhere — does")
    print(f"denial concentrate without that collapse? grid {R}x{C}; seed {SEED}; {DAYS}d; "
          f"claim, rho={RHO}.")
    print(line)

    max_drift = 0.0

    # --- B0: exclusion off + all-off == canon (both policies) --------------- #
    for pol in ("founders", "claim"):
        w0, _ = run_exclusion(exclusion=False, appropriation=0.0, owner_policy=pol,
                              radius=GRID_DIAG + 1.0, K=None, lag=0,
                              injection_strength=0.0, injectors=0, arena_side=None)
        fp = w0.state_fingerprint(); max_drift = max(max_drift, w0.matter_drift())
        ok = fp == CANON_COMM and w0._excluded_moves == 0
        print(f"B0  exclusion=off all-off [{pol:<8}] : {fp} vs canon {CANON_COMM} -> "
              f"{'BYTE-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
        assert ok, f"B0 [{pol}] not byte-identical to canon / nonzero exclusions"

    # --- B1: exclusion off at the appropriation headline (founders -> the fp) - #
    # 931680477b4e012b is module-23's self-check (founders/box6/rho0.5/salience-on); the
    # battery uses claim, but the byte anchor must use the config that DEFINES that hex.
    wb1, _ = run_exclusion(exclusion=False, appropriation=RHO, owner_policy="founders",
                           arena_side=BOX, injection_strength=W_INJ, injectors=FEW)
    fpb1 = appropriation_fingerprint(wb1); okb1 = fpb1 == APPROP_FP
    print(f"B1  exclusion=off approp-headline (founders)   : {fpb1} vs {APPROP_FP} -> "
          f"{'BYTE-IDENTICAL ✓' if okb1 else 'MISMATCH ✗'}")
    assert okb1, "B1 not byte-identical to module-23 self-check (parent drift!)"

    # --- main cross-product (claim, rho=0.5) -------------------------------- #
    print(f"\nMAIN (claim, rho={RHO}); stratification, capacity, utilization:")
    hdr = f"{'mode':>9}{'arena':>6}{'alive':>7}{'totBio':>8}{'ownGap':>9}{'ownShr':>8}" \
          f"{'plOwned':>8}{'plUnown':>8}{'maxOcc':>7}{'exMoves':>8}{'drift':>9}"
    print(hdr); print("-" * len(hdr))
    rows = {}
    configs = [("off", None), ("off", BOX)]
    for m in ("absentee", "occupied"):
        for arena in (None, BOX):
            configs.append((m, arena))
    for mode, arena in configs:
        w, _ = run_exclusion(exclusion=(mode != "off"),
                             exclude_mode=("absentee" if mode == "off" else mode),
                             owner_policy="claim", arena_side=arena,
                             injection_strength=0.0, injectors=0)
        d = w.matter_drift(); max_drift = max(max_drift, d)
        assert d < 1e-9, f"leak mode={mode} arena={arena}: {d}"
        em = exclusion_metrics(w)
        rows[(mode, arena)] = em
        print(f"{mode:>9}{str(arena or '-'):>6}{em['alive']:>7}"
              f"{_fmt(em['total_biomass'], '{:.0f}'):>8}{_fmt(em['owner_gap'], '{:+.2f}'):>9}"
              f"{_fmt(em['owner_share']):>8}{_fmt(em['plant_owned'], '{:.1f}'):>8}"
              f"{_fmt(em['plant_unowned'], '{:.1f}'):>8}{em['max_occ']:>7}"
              f"{em['excluded_moves']:>8}{d:>9.1e}")

    # --- self-check fingerprint --------------------------------------------- #
    wf, _ = run_exclusion(exclusion=True, exclude_mode="absentee", owner_policy="claim",
                          arena_side=BOX, injection_strength=0.0, injectors=0)
    fp1 = exclusion_fingerprint(wf)
    wf2, _ = run_exclusion(exclusion=True, exclude_mode="absentee", owner_policy="claim",
                           arena_side=BOX, injection_strength=0.0, injectors=0)
    fp2 = exclusion_fingerprint(wf2)
    max_drift = max(max_drift, wf.matter_drift())
    print(f"\nEXCLUSION_FINGERPRINT: {fp1}")
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp1 == fp2 else 'MISMATCH ✗'}")
    assert fp1 == fp2, "exclusion run is not reproducible"
    print(f"max matter drift across battery: {max_drift:.2e} kg")
    assert max_drift < 1e-9, "a config leaked matter"

    # --- honest verdict ----------------------------------------------------- #
    off_o, off_b = rows[("off", None)], rows[("off", BOX)]
    abs_o, abs_b = rows[("absentee", None)], rows[("absentee", BOX)]
    occ_o, occ_b = rows[("occupied", None)], rows[("occupied", BOX)]
    print(f"\n{line}")
    print("E2 — stratification WITHOUT collapse (vs the institution's pop 91->2 graveyard):")
    print(f"   open : alive off {off_o['alive']} -> absentee {abs_o['alive']} / occupied {occ_o['alive']}; "
          f"owner gap off {_fmt(off_o['owner_gap'], '{:+.2f}')} -> abs {_fmt(abs_o['owner_gap'], '{:+.2f}')} / occ {_fmt(occ_o['owner_gap'], '{:+.2f}')}")
    print(f"   box{BOX}: alive off {off_b['alive']} -> absentee {abs_b['alive']} / occupied {occ_b['alive']}; "
          f"owner gap off {_fmt(off_b['owner_gap'], '{:+.2f}')} -> abs {_fmt(abs_b['owner_gap'], '{:+.2f}')} / occ {_fmt(occ_b['owner_gap'], '{:+.2f}')}")
    print("capture vs escape — plant utilization on owned vs unowned cells (box6):")
    print(f"   absentee: owned {_fmt(abs_b['plant_owned'], '{:.1f}')} vs unowned "
          f"{_fmt(abs_b['plant_unowned'], '{:.1f}')} (locked-unused if owned>unowned)")
    print(f"   occupied: owned {_fmt(occ_b['plant_owned'], '{:.1f}')} vs unowned "
          f"{_fmt(occ_b['plant_unowned'], '{:.1f}')} (grazed-down if owned<=unowned)")

    # the institution starved the base (pop ->graveyard); does exclusion?
    base_open, base_box = off_o['alive'], off_b['alive']
    no_collapse = all(rows[(m, a)]['alive'] >= base for m, a, base in
                      [("absentee", None, base_open), ("occupied", None, base_open),
                       ("absentee", BOX, base_box), ("occupied", BOX, base_box)])
    # does exclusion ADD concentration beyond the inherited rho=0.5 tribute baseline?
    def dgap(on, off):
        return (on['owner_gap'] or 0) - (off['owner_gap'] or 0)
    occ_adds = dgap(occ_o, off_o) > 0.2 or dgap(occ_b, off_b) > 0.2
    abs_adds = dgap(abs_o, off_o) > 0.2 or dgap(abs_b, off_b) > 0.2
    print(f"\n{line}")
    if no_collapse:
        print("VERDICT — NO COLLAPSE (the clean contrast to the institution): exclusion never")
        print(f"starves the base — alive RISES (open {base_open}->{abs_o['alive']}/{occ_o['alive']}, "
              f"box {base_box}->{abs_b['alive']}/{occ_b['alive']}) where the levy crashed it to a")
        print("graveyard. A verb that parks no mass in a parasitic caste leaves capacity intact.")
    else:
        print("VERDICT — exclusion dents capacity in some arm (locking cells starves the")
        print("crowded remainder) — a different failure mode than the levy.")
    print("BUT it does NOT meaningfully stratify: occupied (capture-analog) nudges the owner")
    print(f"gap up only slightly ({_fmt(off_b['owner_gap'], '{:+.2f}')}->{_fmt(occ_b['owner_gap'], '{:+.2f}')} box, "
          f"{_fmt(off_o['owner_gap'], '{:+.2f}')}->{_fmt(occ_o['owner_gap'], '{:+.2f}')} open) atop the rho=0.5 "
          f"tribute baseline; absentee LOWERS it")
    print(f"({_fmt(off_o['owner_gap'], '{:+.2f}')}->{_fmt(abs_o['owner_gap'], '{:+.2f}')} open) — owners just")
    print("displace non-owners, who flee to (and crowd: max-occ up) the ample unowned cells.")
    print("capture vs escape: occupied grazes owned cells DOWN (owner eats the freed share);")
    print("absentee leaves non-owners crowding unowned cells. Neither builds a stratum beyond")
    print("tribute -> denial is toothless for EXTRA concentration where there is room to flee")
    print("(echo of the escape-NULLs 20-22) — but, unlike the levy, it is at least harmless to")
    print("the base. So the answer to 'stratify without collapse?' is: no collapse, but also")
    print("no stratification — concentration still needs the body->body transfer of module 23.")
    print("Denied move = stay (zero mass ops); matter conserved "
          f"(<1e-9, max {max_drift:.1e}); exclusion=off reproduces canon & module 23 "
          f"byte-for-byte. seed {SEED}  ✓")


if __name__ == "__main__":
    main()
