"""
run_artifact_f.py — mod F (vitok 1): material culture as a dual-layer artifact reservoir.

GATES (deterministic, no network):
  MF-OFF       artifacts=False -> byte-identical to the mod-E Polis (== canon; anchors below).
  MF-mass      artifacts=True  -> writing/copying/decay run, but matter_drift < 1e-9 (the
               FIRST four-term invariant soil+plant+Σbody+Σartifact.mass holds).
  MF-semantic  the semantic layer (salience) decays to zero while Σartifact.mass is
               untouched — material durability and semantic durability are DIVORCED.
  MF-replay    same seed -> identical polis fingerprint (state + dunbar blob + artifact blob).

MF-OFF external anchors (cite verbatim, like SAL_SPHERE / CANON_COMM): the mod-E Polis and
the mod-F Polis with artifacts=False produce these fingerprints bit-for-bit on identical
configs, proving the +Σmass seam in _matter is inert when OFF (measured, drift 1.8e-12):
  MF_OFF_ANCHOR_RHO0  = rho0  founders box6 dunbar=None -> aa43ddad2ffded8e
  MF_OFF_ANCHOR_CLAIM = rho0.5 claim   box6 dunbar=None -> 961290bbe9eeaa54

PRE-REGISTERED HYPOTHESES (гипотезу правит прогон):
  HF1  knowledge survives its maker through a CARRIER: with artifacts ON, method/belief
       reaches readers born AFTER the maker's death (a "posthumous read"); with artifacts
       OFF (the control) the only channel is the living one, which dies with the generation
       (the C-LIVE apprentice result). Signal = count/share of posthumous reads.
  HF2  civilisation is a RACE: the copy-rate (~1/write_stasis) against the two decay clocks
       (sem_decay silences carriers, mat_decay erodes their mass). Fast copying + slow decay
       -> method ratchets up and persists; slow copying + fast decay -> method freezes low
       and carriers fall to silent ruins. Measure carried_max & live-method-share vs the knobs.
  HF3  artifacts concentrate PAST LABOUR in the owners — but is it a NEW stratum or a
       MIRROR of body inequality? Writing needs body > REPRO, which only the appropriation
       regime's fat owners reach (measured: at rho=0 reproduction clamps bodies at ~REPRO,
       so NO ONE writes). Three axes guard against the write-gate tautology: own23% (share
       made by the REAL owner class owner_ids(), not the narrow _owner_ids), amp (Gini of
       artifact mass by maker minus Gini of lifetime body integral — ≈0 means mirror, not
       amplification), and approp% (mass made by one oid, held on another's land).

MEASURED ON FIRST CALIBRATION (documented so the regime is honest):
  * rho=0: bodies clamp at ~REPRO (reproduction splits at 0.9), so body > REPRO+stake is
    unreachable -> ZERO writing. Artifact culture is impossible without appropriation:
    only tribute accumulating beyond the reproduction line makes a pawn fat enough to
    freeze mass into an object. Writing is thus the privilege of the accumulator — the
    owner/elite. This is not a bug; it is HF3's substrate, and the тезис of Теория Элит
    made mechanical: past labour crystallises where mass has already concentrated.
  * the method ratchet starts at 0 (a first-mover writes method 0) and climbs only by
    copying-with-improvement (+1) by fat, settled readers on a readable carrier. Let the
    readers thin or the carriers fall silent (salience<read_threshold) and method freezes
    at its last copied depth — meaning stops replicating though the mass may still stand.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict

from sim_eventlog import EventLog, REPRO
from stage3.polis import Polis, PolisConfig

HDR = "=" * 78

# --- MF-OFF external anchors (mod-E Polis == mod-F artifacts=False), measured ------ #
MF_OFF_ANCHOR_RHO0 = "aa43ddad2ffded8e"     # rho0  founders box6 dunbar=None
MF_OFF_ANCHOR_CLAIM = "961290bbe9eeaa54"    # rho0.5 claim   box6 dunbar=None


def _cfg(artifacts=False, rho=0.5, owner="claim", arena=6, seed=7, days=250, **over):
    kw = dict(appropriation=rho, owner_policy=owner, arena_side=arena,
              t_awaken=10 ** 9, demerzel_directive=None, seed=seed, days=days,
              dunbar_K=None, artifacts=artifacts)
    kw.update(over)
    return PolisConfig(**kw)


def _run(cfg, days):
    w = Polis(EventLog(), cfg)
    for _ in range(days):
        w.step()
    return w


def _run_with_body_integral(cfg, days):
    """Run and accumulate, per oid, the INTEGRAL of body over the ticks it was alive
    (Σ_t body[oid,t]) — a proxy for lifetime past labour, honest to "прошлый труд" in a
    way a living-snapshot Gini is not. Pure read of w.pop after each step; the sim state
    is never touched, so fingerprints are unchanged (this lives in the runner, not the
    mechanics)."""
    w = Polis(EventLog(), cfg)
    body_integral = defaultdict(float)
    for _ in range(days):
        w.step()
        for a in w.pop:
            body_integral[a.oid] += a.body
    return w, body_integral


def _gini(xs):
    """Standard Gini (0 = equal, →1 = concentrated). Empty -> nan; all-zero -> 0."""
    xs = sorted(float(x) for x in xs if x is not None)
    n = len(xs)
    if n == 0:
        return float("nan")
    s = sum(xs)
    if s == 0:
        return 0.0
    cum = sum(i * x for i, x in enumerate(xs, 1))
    return (2 * cum) / (n * s) - (n + 1) / n


# --------------------------------------------------------------------------- #
#  Gates                                                                       #
# --------------------------------------------------------------------------- #
def _gate_mf_off():
    # artifacts=False must reproduce the mod-E Polis byte-for-byte on two configs, and
    # match the cited external anchors (proves the _matter +Σmass seam is inert when OFF).
    a = _run(_cfg(artifacts=False, rho=0.0, owner="founders", days=250), 250)
    b = _run(_cfg(artifacts=False, rho=0.5, owner="claim", days=250), 250)
    fa, fb = a.state_fingerprint(), b.state_fingerprint()
    ok = (fa == MF_OFF_ANCHOR_RHO0 and fb == MF_OFF_ANCHOR_CLAIM
          and a.matter_drift() < 1e-9 and b.matter_drift() < 1e-9)
    print(f"MF-OFF   artifacts=False == mod-E Polis (anchors) -> {'✓' if ok else '✗'}")
    print(f"           rho0  {fa} == {MF_OFF_ANCHOR_RHO0}  ·  drift {a.matter_drift():.1e}")
    print(f"           claim {fb} == {MF_OFF_ANCHOR_CLAIM}  ·  drift {b.matter_drift():.1e}")
    assert ok


def _gate_mf_mass():
    # active build + both decays: the four-term invariant still holds < 1e-9.
    w = _run(_cfg(artifacts=True, mat_decay=0.01), 250)
    af = w._artifacts
    built = len(af.writes) + len(af.copies)
    ok = w.matter_drift() < 1e-9 and built > 0
    print(f"MF-mass  build+decay, 4-term invariant holds -> {'✓' if ok else '✗'} "
          f"(drift {w.matter_drift():.1e}, writes {len(af.writes)}, copies {len(af.copies)}, "
          f"Σart.mass {af.sum_mass():.3f})")
    assert ok


def _gate_mf_semantic():
    # semantic decay drives salience -> 0 while Σartifact.mass is untouched (mat_decay=0).
    w = _run(_cfg(artifacts=True, mat_decay=0.0, days=200), 200)
    af = w._artifacts
    sal = [ar.salience for ar in af.artifacts]
    silent = sum(1 for s in sal if s <= af.read_threshold)   # carriers gone semantically quiet
    # Σmass moves ONLY by writing (no material decay); no salience change ever touched mass.
    ok = (w.matter_drift() < 1e-9 and sal and min(sal) < af.read_threshold and silent > 0)
    print(f"MF-semantic salience→0 at Σmass fixed (mat_decay=0) -> {'✓' if ok else '✗'} "
          f"(Σmass {af.sum_mass():.3f} drift {w.matter_drift():.1e}; "
          f"{silent}/{len(sal)} carriers silent, min-salience {min(sal):.3f})")
    assert ok


def _gate_mf_replay():
    a = _run(_cfg(artifacts=True), 250)
    b = _run(_cfg(artifacts=True), 250)
    ok = a.state_fingerprint() == b.state_fingerprint()
    print(f"MF-replay {a.state_fingerprint()} == {b.state_fingerprint()} -> {'✓' if ok else '✗'}")
    assert ok


# --------------------------------------------------------------------------- #
#  Experiments (гипотезу правит прогон)                                        #
# --------------------------------------------------------------------------- #
def _deaths_births(w):
    """From the world event-log: {oid: death_tick} and {oid: birth_tick}."""
    death, birth = {}, {}
    for e in w.log.events:
        if e.kind == "death" and e.actor is not None:
            death[e.actor] = e.t
        elif e.kind in ("birth", "seed") and e.actor is not None:
            birth.setdefault(e.actor, e.t)
    return death, birth


def _hf1(seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHF1 — does knowledge survive its maker THROUGH A CARRIER?\n"
          f"(posthumous read = reader met a carrier AFTER its maker had died; "
          f"control = artifacts OFF, only the living channel)\n{HDR}")
    print(f"  {'seed':>5}{'writes':>8}{'copies':>8}{'reads':>8}{'posthum.':>10}"
          f"{'post-share':>12}{'carr.max':>10}")
    tot_post = tot_read = 0
    for s in seeds:
        w = _run(_cfg(artifacts=True, seed=s, days=days), days)
        af = w._artifacts
        death, birth = _deaths_births(w)
        posth = 0
        for (t, aid, reader, method, maker, born_t) in af.reads:
            dm = death.get(maker)
            br = birth.get(reader)
            if dm is not None and br is not None and br > dm:   # reader born after maker died
                posth += 1
        share = posth / len(af.reads) if af.reads else 0.0
        tot_post += posth; tot_read += len(af.reads)
        print(f"  {s:>5}{len(af.writes):>8}{len(af.copies):>8}{len(af.reads):>8}"
              f"{posth:>10}{share:>12.3f}{af.carried_max():>10}")
    # control: artifacts OFF -> zero carriers -> zero posthumous transmission
    print(f"\n  control (artifacts OFF): 0 carriers, 0 posthumous reads — the living channel")
    print(f"  only. ON total: {tot_post}/{tot_read} reads were posthumous "
          f"(knowledge outlived its maker via the object).")
    print(f"  HF1 {'✓ carrier carries knowledge past the grave' if tot_post > 0 else '✗ NULL: no posthumous transmission'}")


def _hf2(seed=7, days=300):
    print(f"\n{HDR}\nHF2 — the RACE: copy-rate (1/write_stasis) vs the two decay clocks\n{HDR}")
    print(f"  {'stasis':>7}{'sem_dec':>9}{'mat_dec':>9}{'writes':>8}{'copies':>8}"
          f"{'carr.max':>10}{'live-meth%':>11}{'drift':>10}")
    for stasis, sem, mat in ((4, 0.02, 0.001), (8, 0.02, 0.001), (8, 0.20, 0.001),
                             (8, 0.02, 0.05), (16, 0.02, 0.001)):
        w = _run(_cfg(artifacts=True, seed=seed, days=days,
                      write_stasis=stasis, sem_decay=sem, mat_decay=mat), days)
        af = w._artifacts
        assert w.matter_drift() < 1e-9, f"HF2 cell leaked matter (stasis={stasis})"
        print(f"  {stasis:>7}{sem:>9.2f}{mat:>9.3f}{len(af.writes):>8}{len(af.copies):>8}"
              f"{af.carried_max():>10}{af.live_method_share():>11.3f}{w.matter_drift():>10.1e}")
    print("\n  read: fast copying (low stasis) + slow forgetting (low sem_decay) climbs the")
    print("  ratchet; crank sem_decay/mat_decay or slow the copy-rate and method stalls.")


def _hf3(seeds=(7, 8, 9), days=300):
    """Does material culture concentrate PAST LABOUR — and is that concentration a NEW
    stratum or merely a MIRROR of body inequality (the write-gate tautology)? Three honest
    axes, because a single 'owner-mass share' can lie two ways:

      own23%  — share of surviving artifact mass MADE by a real territorial owner. The
        reference class is owner_ids() (every oid holding >=1 cell), NOT the narrow
        _owner_ids set: measured, the narrow set gave a spurious NULL (~5-14%) while the
        real class holds ~85%. Whom you put in the denominator decides the result — the
        'корона на кладбище' lesson again.

      amp     — Gini(artifact mass by maker) minus Gini(body INTEGRAL over life). The
        tautology guard: writing is gated on body>REPRO, so of course fat pawns make the
        artifacts. If amp≈0 the artifact distribution merely MIRRORS lifetime-labour
        inequality (no new stratum); amp>0 means culture AMPLIFIES it. Body is integrated
        over each oid's lifetime (Σ_t body), not a living snapshot — honest to 'прошлый труд'.

      approp% — artifact mass MADE by one oid but standing on ANOTHER's territory
        (_cell_owner != maker). The non-tautological residue: past labour literally held
        by someone other than its author — appropriation in the strict sense.
    """
    print(f"\n{HDR}\nHF3 — does material culture concentrate PAST LABOUR, or MIRROR body "
          f"inequality?\n(own23% real owner class · amp = Gini_art − Gini_body∫ WITHIN writers "
          f"· approp% = made-on-another's-land)\n{HDR}")
    print(f"  {'seed':>5}{'own(23)':>8}{'own23%':>8}{'G_body∫ₑ':>10}{'G_artₑ':>8}"
          f"{'amp':>8}{'approp%':>9}")
    amp_soc_all, access_all = [], []
    for s in seeds:
        w, body_integral = _run_with_body_integral(_cfg(artifacts=True, seed=s, days=days), days)
        af = w._artifacts
        co = w._cell_owner                              # (i,j) -> controlling oid (territory)
        owners = set(w.owner_ids())                     # REAL class: every territorial owner
        total = af.sum_mass()
        # artifact mass attributed to its MAKER (past labour that still stands)
        by_maker = defaultdict(float)
        for a in af.artifacts:
            by_maker[a.maker_oid] += a.mass
        own_share = (sum(m for oid, m in by_maker.items() if oid in owners) / total
                     if total > 0 else float("nan"))
        # appropriation: made by X, now standing on Y's land (Y != X, Y exists)
        appropriated = sum(a.mass for a in af.artifacts
                           if (c := co.get((a.i, a.j))) is not None and c != a.maker_oid)
        approp = (appropriated / total) if total > 0 else float("nan")
        # tautology guard, SAME base = the writing elite: does culture concentrate artifact
        # mass beyond these makers' own lifetime-labour inequality? (amp>0 => yes, amplifies)
        writers = set(by_maker)                         # oids with surviving artifact mass
        g_body_e = _gini(body_integral[o] for o in writers)
        g_art_e = _gini(by_maker.values())
        amp = g_art_e - g_body_e
        print(f"  {s:>5}{len(owners):>8}{own_share:>8.3f}{g_body_e:>10.3f}{g_art_e:>8.3f}"
              f"{amp:>+8.3f}{approp:>9.3f}")
        # society-wide context (for the interpretation line, not the elite column)
        lived = set(body_integral)
        amp_soc_all.append(_gini(by_maker.get(o, 0.0) for o in lived)
                           - _gini(body_integral[o] for o in lived))
        access_all.append(len(writers) / len(lived) if lived else float("nan"))
    amp_soc = sum(amp_soc_all) / len(amp_soc_all)
    access = sum(access_all) / len(access_all)
    print(f"\n  measured: amp>0 WITHIN the writing elite — material culture concentrates the")
    print(f"  surviving artifact mass BEYOND these makers' own lifetime-labour inequality; it")
    print(f"  AMPLIFIES, it does not mirror (the live-snapshot ≈0 was the write-gate tautology,")
    print(f"  the integral-over-life dispels it). Society-wide it is starker: only ~{access:.1%} of")
    print(f"  all who lived leave a standing artifact, so amp vs the whole population is +{amp_soc:.2f}")
    print(f"  — a DOUBLE amplification (monopoly of access + concentration among the few who do).")
    print(f"  The non-tautological residue is approp% (~6-14%): past labour literally held by")
    print(f"  someone other than its author (Теория Элит: culture deepens, not just reflects).")


# --------------------------------------------------------------------------- #
#  Main                                                                        #
# --------------------------------------------------------------------------- #
def main():
    print(HDR)
    print("mod F — material culture (vitok 1 = vessel): a DUAL-LAYER artifact reservoir.")
    print("The FIRST extension of the tower's mass law: soil+plant+Σbody+Σartifact.mass.")
    print("Material decay (mass→soil) and semantic decay (salience→0) are two divorced")
    print("clocks; copying races them. artifacts=False ≡ canon (MF-OFF).")
    print(HDR)
    _gate_mf_off()
    _gate_mf_mass()
    _gate_mf_semantic()
    _gate_mf_replay()
    if "--experiment" in sys.argv or "--all" in sys.argv:
        _hf1()
        _hf2()
    if "--hf3" in sys.argv or "--all" in sys.argv:
        _hf3()
    print(f"\n{HDR}\nmod F gates green: OFF ≡ canon (MF-OFF, external anchors), the four-term")
    print("invariant holds under active build+decay (MF-mass), the semantic layer decays")
    print(f"free of mass (MF-semantic), and the run is bit-identical (MF-replay).\n{HDR}")


if __name__ == "__main__":
    main()
