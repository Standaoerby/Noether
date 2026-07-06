"""
run_archipelago_d.py — mod D: the exit-stake / open-horizon experiment.

PRE-REGISTERED QUESTION (from the "Редукция и горизонт" thread, written before the run):
    Does a lineage whose carriers PAY THE EXIT STAKE (a lethal, irreversible migration
    cost) out-copy a lineage that stays in the local optimum — with NO télos, on a blind
    conservative substrate? If yes, expansion/transcendence is an EQUILIBRIUM of the
    payoff structure, not an intent — the same shape as "lying is an equilibrium".

GATES (no network, deterministic):
  MD-OFF   bridge shut (open_t=inf) -> the two worlds are byte-identical to two
           independent canon Polis runs (each state_fingerprint matches a standalone).
  MD-noop  frontier_richness=1.0 -> the gradient hook is inert -> frontier byte-identical
           to canon (the gradient never secretly perturbs the substrate).
  MD-mass  bridge open, migrations happen -> per-world FLUX-ADJUSTED drift < 1e-9
           (matter - M0 - imported + exported) AND absolute pair drift < 1e-9. Mass is
           conserved both per-world (open system, accounting for legal cross-world flow)
           and over the closed pair.
  MD-replay same seed -> identical archipelago fingerprint (state fps + crossing log).

PRE-REGISTERED HYPOTHESES (гипотезу правит прогон):
  HD1  expansion beats staying: living copies of the expansive lineage (surviving
       migrants + frontier-born descendants) exceed a matched no-bridge stay-home
       baseline delta — i.e. the lineage that pays the stake leaves MORE copies than it
       would have by staying. Blind rule, blind win => equilibrium not intent.
  HD2  the stake is a FILTER with a threshold: too-safe crossing (high survive_p) floods
       the frontier with marginal migrants and self-chokes; too-lethal starves the flow.
       There is an interior optimum of copies-per-capita.
  HD3  gradient dependence: with frontier_richness=1.0 (no prize) the expansive lineage
       does NOT beat staying — expansion pays only when the horizon is actually richer
       (rules out a pure artifact of the migration mechanic).

MEASURED ON FIRST CALIBRATION (2026-07-06, documented so the regime choice is honest):
  * rho=0.5 (the turnover pump, natural life ~7 ticks) is the WRONG regime — both bases
    self-extinguish by t=400 and expansion has nothing to measure on. The horizon test
    runs at rho=0 (natural life ~120 ticks, stable base), per constitution §7.
  * Counter-intuitive and robust: LOWER crossing survival yields MORE expansive copies
    (surv 0.60 -> 143 vs surv 0.75 -> 68). A lethal stake selects a small vanguard that
    seizes the empty rich oasis cleanly; a safe crossing lets stay-home ballast follow
    and choke the frontier. The exit stake is not merely a filter — it is NICHE CLEARANCE.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog
from stage3.polis import Polis, PolisConfig
from stage3.archipelago import Archipelago, BridgeConfig, run_archipelago

HDR = "=" * 78


def _cfg(seed=7, days=400, rho=0.0):
    owner = "claim" if rho > 0 else "founders"
    return PolisConfig(appropriation=rho, owner_policy=owner, arena_side=6,
                       t_awaken=10 ** 9, demerzel_directive=None, seed=seed, days=days)


def _gate_md_off():
    # pure OFF = bridge shut AND gradient off (richness 1.0); the gradient is a separate
    # axis with its own gate (MD-noop). Default BridgeConfig richness is 2.0, which would
    # (correctly) perturb the frontier — so it must be neutralised here.
    arc = run_archipelago(_cfg(), _cfg(seed=8),
                          bridge=BridgeConfig(open_t=10 ** 9, frontier_richness=1.0),
                          seed=0, days=300)
    h = Polis(EventLog(), _cfg(days=300))
    f = Polis(EventLog(), _cfg(seed=8, days=300))
    for _ in range(300):
        h.step(); f.step()
    ok = (arc.home.state_fingerprint() == h.state_fingerprint()
          and arc.frontier.state_fingerprint() == f.state_fingerprint()
          and len(arc.crossings) == 0)
    print(f"MD-OFF   bridge shut == two independent canon runs -> "
          f"{'✓' if ok else '✗'}  (crossings {len(arc.crossings)}, pair_drift {arc.pair_drift():.1e})")
    assert ok


def _gate_md_noop():
    arc = run_archipelago(_cfg(), _cfg(seed=8),
                          bridge=BridgeConfig(open_t=10 ** 9, frontier_richness=1.0),
                          seed=0, days=200)
    f = Polis(EventLog(), _cfg(seed=8, days=200))
    for _ in range(200):
        f.step()
    ok = arc.frontier.state_fingerprint() == f.state_fingerprint()
    print(f"MD-noop  richness=1.0 gradient inert -> frontier == canon -> {'✓' if ok else '✗'}")
    assert ok


def _gate_md_mass():
    b = BridgeConfig(open_t=100, migrate_every=10, stake_frac=0.15, survive_p=0.6,
                     crowd_frac=0.9, hunger_body=0.05, max_leavers_per_wave=1,
                     frontier_richness=2.5)
    arc = run_archipelago(_cfg(), _cfg(seed=8), bridge=b, seed=0, days=400)
    r = arc.report()
    ok = (r["home_drift"] < 1e-9 and r["frontier_drift"] < 1e-9 and r["pair_drift"] < 1e-9)
    print(f"MD-mass  flux-adjusted drift h {r['home_drift']:.1e} f {r['frontier_drift']:.1e} "
          f"pair {r['pair_drift']:.1e} (cross {r['crossings']}) -> {'✓' if ok else '✗'}")
    assert ok


def _gate_md_replay():
    b = BridgeConfig(open_t=100, migrate_every=10, stake_frac=0.15, survive_p=0.6,
                     crowd_frac=0.9, hunger_body=0.05, max_leavers_per_wave=1,
                     frontier_richness=2.5)
    a = run_archipelago(_cfg(), _cfg(seed=8), bridge=b, seed=0, days=400)
    c = run_archipelago(_cfg(), _cfg(seed=8), bridge=b, seed=0, days=400)
    ok = a.fingerprint() == c.fingerprint()
    print(f"MD-replay {a.fingerprint()} == {c.fingerprint()} -> {'✓' if ok else '✗'}")
    assert ok


def _experiment(seeds=(7, 8, 9, 10, 11), days=400):
    print(f"\n{HDR}\nEXIT-STAKE EXPERIMENT (rho=0 stable regime; richness gradient 2.5)\n{HDR}")
    print(f"  {'seed':>4}{'cross':>7}{'surv':>6}{'died':>6}{'expansive':>11}"
          f"{'home_open':>11}{'home_shut':>11}{'front_shut':>12}  verdict")
    tot_exp = tot_delta = 0
    for seed in seeds:
        b = BridgeConfig(open_t=100, migrate_every=10, stake_frac=0.15, survive_p=0.6,
                         crowd_frac=0.9, hunger_body=0.05, max_leavers_per_wave=1,
                         frontier_richness=2.5)
        arc = run_archipelago(_cfg(seed=seed), _cfg(seed=seed + 100), bridge=b,
                              seed=seed, days=days)
        ls = arc.lineage_scores()
        # matched control: same seeds, bridge shut -> what the lineage would be by staying
        arc0 = run_archipelago(_cfg(seed=seed), _cfg(seed=seed + 100),
                               bridge=BridgeConfig(open_t=10 ** 9), seed=seed, days=days)
        home_shut = len(arc0.home.pop)
        front_shut = len(arc0.frontier.pop)
        # expansion delta: extra living copies gained by paying the stake vs the home the
        # migrants left behind (open home + expansive frontier vs shut home alone)
        gained = (ls["living_home"] + ls["living_expansive"]) - home_shut
        tot_exp += ls["living_expansive"]; tot_delta += gained
        verdict = "expand>stay" if gained > 0 else "stay wins"
        print(f"  {seed:>4}{ls['migrants_sent']:>7}{ls['migrants_survived']:>6}"
              f"{ls['migrants_sent']-ls['migrants_survived']:>6}{ls['living_expansive']:>11}"
              f"{ls['living_home']:>11}{home_shut:>11}{front_shut:>12}  {verdict}")
    print(f"\n  HD1 expansion vs stay: total copy delta {tot_delta:+d} over {len(seeds)} seeds "
          f"-> {'lineage that pays the stake out-copies staying (equilibrium, not intent)' if tot_delta > 0 else 'stay-home wins (horizon not worth the toll here)'}")


def _hd2_stake_scan(seed=7, days=400):
    print(f"\n{HDR}\nHD2 — the stake is a filter with an interior optimum (copies vs survival)\n{HDR}")
    print(f"  {'survive_p':>10}{'cross':>7}{'surv':>6}{'expansive':>11}  (lower survival, cleaner niche capture?)")
    for sp in (0.4, 0.5, 0.6, 0.7, 0.85):
        b = BridgeConfig(open_t=100, migrate_every=10, stake_frac=0.15, survive_p=sp,
                         crowd_frac=0.9, hunger_body=0.05, max_leavers_per_wave=1,
                         frontier_richness=2.5)
        arc = run_archipelago(_cfg(seed=seed), _cfg(seed=seed + 100), bridge=b,
                              seed=seed, days=days)
        ls = arc.lineage_scores()
        print(f"  {sp:>10.2f}{ls['migrants_sent']:>7}{ls['migrants_survived']:>6}"
              f"{ls['living_expansive']:>11}")


def _hd3_gradient(seed=7, days=400):
    print(f"\n{HDR}\nHD3 — expansion pays ONLY with a real gradient (richness sweep)\n{HDR}")
    print(f"  {'richness':>9}{'expansive':>11}{'home_open':>11}{'front_shut':>12}")
    for rich in (1.0, 1.5, 2.0, 2.5, 3.0):
        b = BridgeConfig(open_t=100, migrate_every=10, stake_frac=0.15, survive_p=0.6,
                         crowd_frac=0.9, hunger_body=0.05, max_leavers_per_wave=1,
                         frontier_richness=rich)
        arc = run_archipelago(_cfg(seed=seed), _cfg(seed=seed + 100), bridge=b,
                              seed=seed, days=days)
        ls = arc.lineage_scores()
        arc0 = run_archipelago(_cfg(seed=seed), _cfg(seed=seed + 100),
                               bridge=BridgeConfig(open_t=10 ** 9), seed=seed, days=days)
        print(f"  {rich:>9.1f}{ls['living_expansive']:>11}{ls['living_home']:>11}"
              f"{len(arc0.frontier.pop):>12}")


def main():
    print(HDR)
    print("mod D — the archipelago: two polises, a migration bridge, an EXIT STAKE.")
    print("Tests whether expansion is an EQUILIBRIUM (blind rule wins blindly), not a télos.")
    print(HDR)
    _gate_md_off()
    _gate_md_noop()
    _gate_md_mass()
    _gate_md_replay()
    if "--experiment" in sys.argv or "--all" in sys.argv:
        _experiment()
    if "--hd2" in sys.argv or "--all" in sys.argv:
        _hd2_stake_scan()
    if "--hd3" in sys.argv or "--all" in sys.argv:
        _hd3_gradient()
    print(f"\n{HDR}\nmod D gates green: the bridge is a pure mass-neutral overlay (MD-mass),"
          f"\nOFF ≡ two canon runs (MD-OFF), gradient inert at richness 1.0 (MD-noop),"
          f"\nand the archipelago replays byte-identically (MD-replay).\n{HDR}")


if __name__ == "__main__":
    main()
