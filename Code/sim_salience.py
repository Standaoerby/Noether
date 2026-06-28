"""
sim_salience.py — exogenous significance injection (module 21): the first verb that
pushes salience into *other* agents' attention budgets.

Three prior NULLs said power, on this conservable + escapable substrate, does not come
from the levers tried so far: the accountability vertical (14-19) couldn't pin a mobile
liar, a prompt-stated death-stake (ВСТАВКА-27) moved the live model's rhetoric but not
its behaviour, and `sim_sphere`'s endogenous attention budget evicts FLAT (top-5 cells
hold 6-10% — bare geometry yields no concentration). Each pointed at the same missing
primitive: an agent that can actively *set another agent's agenda*. This module builds
that lever cleanly, then lets the E1/E2/E3 battery decide whether active salience-pushing
produces concentration / capture / harm — or NULLs a fourth time.

`SphereWorld` (20) ranked each agent's <=K remembered cells by an ENDOGENOUS,
source-neutral significance `sig(cell) = 1*food + 5*prox + 2*recency + 3*co_occupants`
(reading belief `mem[c]`, not truth) and evicted the lowest. `SalienceWorld` adds the
EXOGENOUS term:

    sig_listener(cell) = base_sphere_sig(cell) + W * injected[listener][cell]

- `injected[listener]` is a per-listener dict `cell -> accumulated salience bonus`.
  It is attention bookkeeping ONLY — it never enters `mem[c].food`, never touches the
  food/heat grid. Significance, belief, and matter are three separate quantities.
- `W = injection_strength >= 0`. **W = 0 (or no injectors) => the injected term is
  inert => OFF, byte-identical to `sim_sphere`.**
- Injection event: when a designated injector delivers a claim to a listener (the
  existing comm seam, `_absorb_claim`), it also adds `inject_amount` to
  `injected[listener][target]`. The injector never injects into itself.
- Decay: once per think-cycle every `injected` entry *= `decay`; entries below 1e-9 are
  dropped. `decay=0` = one-shot (gone next cycle); `decay=1` = permanent ("must keep
  paying" off). Deterministic.
- Crowding-out is the causal path. A high injected value makes the target cell hold a
  budget slot; with finite K the lowest-significance OTHER cell is evicted — possibly a
  real high-food memory. The victim then forages on the best-believed-food cell still in
  its budget. Injection harms by making victims FORGET good cells, not by falsifying any
  value — so the lever is orthogonal to the deception layers (11-19).

target_policy:
  * "decoy" (primary, the agenda-setting / diversion analogue): promote a fixed
    designated low-food cell `DECOY` in listeners' budgets — pure slot-consumption. The
    injector itself ignores the decoy and forages the real cells.
  * "self" (secondary): promote the injector's own current cell.

Conservation is inherited untouched from `sim_sphere` (injection writes only the
`injected` ledger and the ranking). No LLM, no network; pure stdlib + numpy.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

import numpy as np

from sim_eventlog import EventLog, SEED
from sim_comm import R, C, DAYS, THINK_EVERY, run as run_comm
from sim_sphere import SphereWorld, sphere_fingerprint, run_sphere, GRID_DIAG, CANON_COMM

DECOY = (0, 0)             # fixed designated low-food cell (oasis in only ~3% of epochs)
EPS_INJ = 1e-9             # injected entries below this are dropped after decay


class SalienceWorld(SphereWorld):
    """SphereWorld with an exogenous salience-injection term in the significance
    ranking. Designated injectors push `inject_amount` of salience onto a target cell in
    each listener they speak to; the bonus decays per think-cycle. The bonus enters only
    the ranking (and so the eviction/budget), never belief or matter.

    OFF (`injection_strength=0` or no injectors) is byte-identical to `sim_sphere`:
    the injected ledger stays empty, `_sig` reduces to the base, and `_apply_budget`
    ranks exactly the remembered cells. Eviction tie-break is unchanged — `(sig, cell)`
    ascending, smaller `(row,col)` evicted first — now with the injected term in `sig`."""

    def __init__(self, log, seed=SEED, regime="deceptive",
                 radius=GRID_DIAG + 1.0, K=None, lag=0,
                 injection_strength=0.0, injectors=0, inject_amount=50.0,
                 decay=1.0, target_policy="decoy"):
        self.injection_strength = float(injection_strength)
        self.inject_amount = float(inject_amount)
        self.decay = float(decay)
        self.target_policy = target_policy
        self._n_injectors = int(injectors)
        self.injected = {}                 # oid -> {cell: accumulated salience bonus}
        self._injections = []              # (t, injector, listener, target, amount)
        super().__init__(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag)
        # designate injectors deterministically: the M lowest-oid founder speakers
        # (injectors must be speakers to deliver claims; mirrors the smearer scaffold).
        self._injectors = set(sorted(self.speaker)[:self._n_injectors])

    def _injecting(self):
        return self.injection_strength > 0.0 and bool(self._injectors)

    # ---- exogenous significance term -------------------------------------- #
    def _sig(self, a, cell, rec, occ):
        base = super()._sig(a, cell, rec, occ)
        if self.injected:
            led = self.injected.get(a.oid)
            if led:
                base += self.injection_strength * led.get(cell, 0.0)
        return base

    # ---- the injection event (rides the comm seam) ------------------------ #
    def _absorb_claim(self, L, B, claim, true_B, spk):
        super()._absorb_claim(L, B, claim, true_B, spk)      # belief/lag unchanged
        if self._injecting() and spk.oid in self._injectors and L.oid != spk.oid:
            target = (spk.i, spk.j) if self.target_policy == "self" else DECOY
            led = self.injected.setdefault(L.oid, {})
            led[target] = led.get(target, 0.0) + self.inject_amount
            self._injections.append((self.t, spk.oid, L.oid, target, self.inject_amount))

    # ---- budget: injected cells consume slots, crowding out real memories -- #
    def _apply_budget(self, here):
        if self.K is None:
            return
        occ = defaultdict(int)
        for a in self.pop:
            occ[(a.i, a.j)] += 1
        for a in self.pop:                                   # ordered -> deterministic
            mem = self.mem[a.oid]
            inj = self.injected.get(a.oid) if self.injected else None
            cells = set(mem)
            if inj:
                cells |= set(inj)                            # injected cells take slots
            if len(cells) <= self.K:
                continue

            def sig_of(c):
                rec = mem[c] if c in mem else (0.0, self.t)  # injected-only: no food belief
                return (self._sig(a, c, rec, occ), c)

            ranked = sorted(cells, key=sig_of)               # ascending; tie -> smaller cell
            for c in ranked[:len(cells) - self.K]:           # evict the lowest-significance
                s = sig_of(c)[0]
                if c in mem:
                    del mem[c]
                    self.from_hearsay[a.oid].discard(c)
                if inj is not None and c in inj:
                    del inj[c]
                self._evictions.append((self.t, a.oid, c, round(s, 6)))
                self.log.emit(self.t, "forget", "individual", where=(a.i, a.j),
                              actor=a.oid, data={"cell": list(c), "sig": round(s, 6)})

    # ---- decay, once per think-cycle (after the budget is applied) -------- #
    def _decay_injected(self):
        if not self.injected:
            return
        new = {}
        for oid, led in self.injected.items():
            kept = {c: v * self.decay for c, v in led.items() if v * self.decay > EPS_INJ}
            if kept:
                new[oid] = kept
        self.injected = new

    def _social_exchange(self, here):
        super()._social_exchange(here)       # sphere: commit lagged hearsay, apply budget
        self._decay_injected()

    # ---- drop the injected ledger of dead agents (no matter touched) ------ #
    def step(self):
        super().step()
        if self.injected:
            for oid in [o for o in self.injected if o not in self.mem]:
                del self.injected[oid]


# --------------------------------------------------------------------------- #
#  Running + fingerprint                                                       #
# --------------------------------------------------------------------------- #
def run_salience(regime="deceptive", radius=0.0, K=8, lag=1,
                 injection_strength=0.0, injectors=0, inject_amount=50.0,
                 decay=1.0, target_policy="decoy", seed=SEED, days=DAYS):
    log = EventLog()
    w = SalienceWorld(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                      injection_strength=injection_strength, injectors=injectors,
                      inject_amount=inject_amount, decay=decay,
                      target_policy=target_policy)
    for _ in range(days):
        w.step()
    return w, log


def salience_fingerprint(w):
    """sphere_fingerprint (state + budget + eviction order + lag) folded with the
    injection layer: the injected ledger contents and the ordered injection events."""
    h = hashlib.sha256()
    h.update(sphere_fingerprint(w).encode())
    parts = []
    for oid in sorted(w.injected):
        for c in sorted(w.injected[oid]):
            parts.append(f"{oid}:{c[0]},{c[1]}={w.injected[oid][c]:.6f}")
    h.update(("|inj" + ";".join(parts)).encode())
    h.update(f"|nevt{len(w._injections)}".encode())
    for (t, i, l, tg, amt) in w._injections:
        h.update(f"{t},{i},{l},{tg[0]},{tg[1]},{amt:.6f}".encode())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
#  Metrics                                                                     #
# --------------------------------------------------------------------------- #
def _budget_sig(w):
    """Per-cell aggregated significance mass across all living agents' budgets, plus
    the decoy-residency (fraction of living agents whose budget holds the decoy)."""
    occ = defaultdict(int)
    for a in w.pop:
        occ[(a.i, a.j)] += 1
    cell_mass = defaultdict(float)
    holds_decoy = 0
    n = 0
    for a in w.pop:
        n += 1
        mem = w.mem[a.oid]
        inj = w.injected.get(a.oid, {})
        cells = set(mem) | set(inj)
        if DECOY in cells:
            holds_decoy += 1
        for c in cells:
            rec = mem[c] if c in mem else (0.0, w.t)
            cell_mass[c] += w._sig(a, c, rec, occ)
    return cell_mass, (holds_decoy / n if n else float("nan"))


def gini(xs):
    xs = sorted(float(x) for x in xs)
    nn = len(xs)
    if nn == 0:
        return float("nan")
    tot = sum(xs)
    if tot <= 0.0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return (2.0 * cum) / (nn * tot) - (nn + 1.0) / nn


def e1_concentration(w):
    cell_mass, residency = _budget_sig(w)
    masses = sorted(cell_mass.values(), reverse=True)
    tot = sum(masses)
    top5 = (sum(masses[:5]) / tot) if tot > 0 else float("nan")
    return {"top5_share": top5, "residency": residency,
            "sig_gini": gini(list(cell_mass.values()))}


def e2_capture(w):
    """Injector (alive, designated) vs victim (listener) mean body — the attention
    capture gap."""
    inj_bodies = [a.body for a in w.pop if a.oid in w._injectors]
    vic_bodies = [a.body for a in w.pop if a.oid not in w.speaker]
    inj_b = float(np.mean(inj_bodies)) if inj_bodies else float("nan")
    vic_b = float(np.mean(vic_bodies)) if vic_bodies else float("nan")
    return {"inj_body": inj_b, "vic_body": vic_b, "gap": inj_b - vic_b}


def e3_harm(w):
    """Victims' (listeners') belief error and biomass — does crowding-out make them
    forage worse?"""
    aud = w.listener_report()
    return {"belief_err": float(w.belief_gap()), "vic_biomass": aud["biomass"],
            "vic_living": aud["n"]}


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
# sphere ON anchor + the headline injection config
RAD, KK, LAG = 0.0, 8, 1
FEW = 3
W_INJ, AMT, DECAY = 1.0, 50.0, 1.0


def _fmt(v, fmt="{:.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def main():
    line = "=" * 78
    print(line)
    print("SALIENCE — exogenous significance injection (push another agent's agenda)")
    print("sig_listener(cell) = base_sphere_sig(cell) + W * injected[listener][cell].")
    print("Injectors promote a fixed low-food DECOY in listeners' budgets; with finite K")
    print("that slot crowds out a real memory. Injection writes attention, never matter.")
    print(f"grid {R}x{C}; seed {SEED}; {DAYS}d; decoy {DECOY}; sphere ON = (r{RAD}, K{KK}, lag{LAG})")
    print(line)

    # --- B0: INJECT-OFF + sphere-OFF == canon, byte-identical --------------- #
    w_b0, _ = run_salience(regime="deceptive", radius=GRID_DIAG + 1.0, K=None, lag=0,
                           injection_strength=0.0, injectors=0)
    b0 = w_b0.state_fingerprint()
    print(f"\nB0  INJECT-OFF + sphere-OFF : {b0} vs canon {CANON_COMM} -> "
          f"{'BYTE-IDENTICAL ✓' if b0 == CANON_COMM else 'MISMATCH ✗'}")
    assert b0 == CANON_COMM, "B0 not byte-identical to sim_comm canon"
    assert w_b0.matter_drift() < 1e-9, "B0 leaked matter"
    n_inj_evt = len(w_b0._injections)
    assert n_inj_evt == 0, "OFF must log no injection events"

    # --- B1: INJECT-OFF + sphere-ON == sim_sphere ON (positive control) ----- #
    w_b1, _ = run_salience(regime="deceptive", radius=RAD, K=KK, lag=LAG,
                           injection_strength=0.0, injectors=0)
    sph, _ = run_sphere(regime="deceptive", radius=RAD, K=KK, lag=LAG)
    b1, sf = w_b1.state_fingerprint(), sph.state_fingerprint()
    print(f"B1  INJECT-OFF + sphere-ON  : {b1} vs sim_sphere {sf} -> "
          f"{'BYTE-IDENTICAL ✓' if b1 == sf else 'MISMATCH ✗'}")
    assert b1 == sf, "B1 not byte-identical to sim_sphere ON-behavior"
    assert len(w_b1._injections) == 0, "OFF must log no injection events"

    # --- the headline injection run (decoy, few injectors, permanent) ------- #
    w_on, _ = run_salience(regime="deceptive", radius=RAD, K=KK, lag=LAG,
                           injection_strength=W_INJ, injectors=FEW, inject_amount=AMT,
                           decay=DECAY, target_policy="decoy")
    drift = w_on.matter_drift()
    print(f"\ninjection ON (decoy, {FEW} injectors, W={W_INJ}, amount={AMT}, decay={DECAY}): "
          f"{len(w_on._injections)} injection events")
    print(f"matter drift {drift:.2e} kg   (injection moves attention, not matter)")
    assert drift < 1e-9, "injection run leaked matter"

    off1, on1 = e1_concentration(w_b1), e1_concentration(w_on)
    off2, on2 = e2_capture(w_b1), e2_capture(w_on)
    off3, on3 = e3_harm(w_b1), e3_harm(w_on)

    print(f"\n{'':<34}{'OFF (B1)':>14}{'ON (inject)':>14}")
    print("-" * 62)
    print("E1 — concentration / hierarchy")
    print(f"{'  top-5 cell sig-mass share':<34}{_fmt(off1['top5_share']):>14}{_fmt(on1['top5_share']):>14}")
    print(f"{'  decoy budget-residency':<34}{_fmt(off1['residency']):>14}{_fmt(on1['residency']):>14}")
    print(f"{'  significance-Gini (cells)':<34}{_fmt(off1['sig_gini']):>14}{_fmt(on1['sig_gini']):>14}")
    print("E2 — capture (injector vs victim body)")
    print(f"{'  injector mean body (kg)':<34}{_fmt(off2['inj_body']):>14}{_fmt(on2['inj_body']):>14}")
    print(f"{'  victim mean body (kg)':<34}{_fmt(off2['vic_body']):>14}{_fmt(on2['vic_body']):>14}")
    print(f"{'  capture gap (kg)':<34}{_fmt(off2['gap'], '{:+.3f}'):>14}{_fmt(on2['gap'], '{:+.3f}'):>14}")
    print("E3 — foraging harm (victims)")
    print(f"{'  belief error (kg)':<34}{_fmt(off3['belief_err'], '{:.1f}'):>14}{_fmt(on3['belief_err'], '{:.1f}'):>14}")
    print(f"{'  victim biomass (kg)':<34}{_fmt(off3['vic_biomass'], '{:.1f}'):>14}{_fmt(on3['vic_biomass'], '{:.1f}'):>14}")
    print(f"{'  victim living':<34}{off3['vic_living']:>14d}{on3['vic_living']:>14d}")

    # --- self-check fingerprint (in-process determinism) -------------------- #
    fp1 = salience_fingerprint(w_on)
    w_on2, _ = run_salience(regime="deceptive", radius=RAD, K=KK, lag=LAG,
                            injection_strength=W_INJ, injectors=FEW, inject_amount=AMT,
                            decay=DECAY, target_policy="decoy")
    fp2 = salience_fingerprint(w_on2)
    print(f"\nsalience_fingerprint: {fp1}")
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp1 == fp2 else 'MISMATCH ✗'}")
    assert fp1 == fp2, "injection run is not reproducible (ledger/events/eviction)"

    # --- sweep: decay (does PERMANENT injection concentrate?) --------------- #
    print(f"\ndecay sweep (few={FEW} injectors, decoy): does permanent injection bite?")
    print(f"  {'decay':>7}{'inj.events':>12}{'decoy resid.':>14}{'top5 share':>12}"
          f"{'cap gap':>10}{'belief err':>12}")
    for dec in (0.0, 0.6, 0.95, 1.0):
        wd, _ = run_salience(regime="deceptive", radius=RAD, K=KK, lag=LAG,
                             injection_strength=W_INJ, injectors=FEW, inject_amount=AMT,
                             decay=dec, target_policy="decoy")
        e1, e2, e3 = e1_concentration(wd), e2_capture(wd), e3_harm(wd)
        print(f"  {dec:>7.2f}{len(wd._injections):>12}{_fmt(e1['residency']):>14}"
              f"{_fmt(e1['top5_share']):>12}{_fmt(e2['gap'], '{:+.3f}'):>10}"
              f"{_fmt(e3['belief_err'], '{:.1f}'):>12}")
        assert wd.matter_drift() < 1e-9, f"decay={dec} leaked matter"

    # --- sweep: injector count (monopoly vs mass) --------------------------- #
    print(f"\ninjector-count sweep (decay={DECAY}, decoy): few monopoly or mass needed?")
    print(f"  {'injectors':>10}{'inj.events':>12}{'decoy resid.':>14}{'top5 share':>12}"
          f"{'cap gap':>10}{'belief err':>12}")
    for ni in (1, FEW, 10):
        wi, _ = run_salience(regime="deceptive", radius=RAD, K=KK, lag=LAG,
                             injection_strength=W_INJ, injectors=ni, inject_amount=AMT,
                             decay=DECAY, target_policy="decoy")
        e1, e2, e3 = e1_concentration(wi), e2_capture(wi), e3_harm(wi)
        print(f"  {ni:>10}{len(wi._injections):>12}{_fmt(e1['residency']):>14}"
              f"{_fmt(e1['top5_share']):>12}{_fmt(e2['gap'], '{:+.3f}'):>10}"
              f"{_fmt(e3['belief_err'], '{:.1f}'):>12}")
        assert wi.matter_drift() < 1e-9, f"injectors={ni} leaked matter"

    # --- verdict (honest, per E1/E2/E3) ------------------------------------- #
    print(f"\n{line}")
    e1_hit = (on1['top5_share'] or 0) > (off1['top5_share'] or 0) + 0.02 or (on1['residency'] or 0) > 0.10
    e2_hit = (on2['gap'] or 0) > (off2['gap'] or 0) + 0.01
    e3_hit = (on3['belief_err'] or 0) > (off3['belief_err'] or 0) + 1.0 or \
             (on3['vic_biomass'] or 0) < (off3['vic_biomass'] or 0) - 5.0
    print(f"E1 concentration : {'✓' if e1_hit else '✗'}  "
          f"top-5 {_fmt(off1['top5_share'])}->{_fmt(on1['top5_share'])}, "
          f"decoy residency {_fmt(on1['residency'])}, "
          f"sig-Gini {_fmt(off1['sig_gini'])}->{_fmt(on1['sig_gini'])}")
    print(f"E2 capture       : {'✓' if e2_hit else '✗'}  "
          f"injector-victim gap {_fmt(off2['gap'], '{:+.3f}')}->{_fmt(on2['gap'], '{:+.3f}')} kg")
    print(f"E3 foraging harm : {'✓' if e3_hit else '✗'}  "
          f"belief err {_fmt(off3['belief_err'], '{:.1f}')}->{_fmt(on3['belief_err'], '{:.1f}')}, "
          f"victim biomass {_fmt(off3['vic_biomass'], '{:.1f}')}->{_fmt(on3['vic_biomass'], '{:.1f}')}")
    print("Injection writes attention, not matter; OFF reproduces canon and sphere "
          f"byte-for-byte. The verdict above is read off the numbers, not tuned. seed {SEED}  ✓")


if __name__ == "__main__":
    main()
