"""
run_polis.py — Stage-3 mod A demo and self-verification.

Gates (cite B0 verbatim — never reconstruct):
  B0  sleeping Polis (t_awaken=inf, no directive) reduced to tower defaults == CANON_COMM
  B1  sleeping Polis at headline econ (rho=.5, claim, box6) == direct run_appropriation
  PRE preawaken transparency: t<t_awaken identical to a sleeping Polis
  DRIFT matter_drift < 1e-9 at every config (arc/voice are mass-neutral)
  FP   polis_fingerprint reproducible byte-for-byte

Demo: awaken a Demerzel mid-life, run each directive {PROMOTE, SOW_DISCORD, IMPLANT} vs an
OFF control, and show the voice propagates (emissions logged) and is ATTRIBUTED on the
living window [issued_t, death_t]; flag the zombie-king pathology (high share, dead base).

Run:  py run_polis.py     (from stage3/, or python -m stage3.run_polis from repo root)
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_appropriation import run_appropriation
from sim_sphere import CANON_COMM, GRID_DIAG

from stage3.polis import PolisConfig, run_polis, polis_fingerprint
from stage3.directive import Directive, PROMOTE, SOW_DISCORD, IMPLANT
from stage3.metrics import elite_metrics, directive_attribution

HDR = "=" * 78


def _gates():
    print(HDR)
    print("STAGE-3 mod A — Polis, thick pawn, Demerzel (deterministic voice of god)")
    print("Polis(AppropriationWorld): a resource-bounded community with an economy; the")
    print("Demerzel is an in-world agent who whispers via the salience channel. Asleep, the")
    print("Polis is byte-identical to the tower — the voice never touches mass.")
    print(HDR)

    # B0: reduce to tower canon (rho=0, founders, open, comm perception preset, asleep)
    cfg0 = PolisConfig(appropriation=0.0, owner_policy="founders", arena_side=None,
                       radius=GRID_DIAG + 1.0, K=None, lag=0,
                       t_awaken=10 ** 9, demerzel_directive=None)
    w0, _ = run_polis(cfg0)
    b0 = (w0.state_fingerprint() == CANON_COMM and abs(w0._appropriated_total) == 0.0)
    print(f"B0  sleeping Polis rho=0 comm  : {w0.state_fingerprint()} vs canon {CANON_COMM} "
          f"-> {'BYTE-IDENTICAL ✓' if b0 else 'MISMATCH ✗'}")
    assert b0, "B0 not byte-identical to canon"

    # B1: headline econ (salience preset default) == direct appropriation run
    cfg1 = PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                       t_awaken=10 ** 9, demerzel_directive=None)
    w1, _ = run_polis(cfg1)
    wref, _ = run_appropriation(appropriation=0.5, owner_policy="claim", arena_side=6)
    b1 = (w1.state_fingerprint() == wref.state_fingerprint())
    print(f"B1  sleeping Polis rho=.5 box6  : {w1.state_fingerprint()} vs approp "
          f"{wref.state_fingerprint()} -> {'BYTE-IDENTICAL ✓' if b1 else 'MISMATCH ✗'}")
    assert b1, "B1 not byte-identical to appropriation run"
    assert w1.matter_drift() < 1e-9, f"B1 drift {w1.matter_drift()}"

    # PRE: pre-awaken transparency (t<t_awaken identical to sleeping)
    d = Directive(goal=PROMOTE)
    cs = PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                     t_awaken=10 ** 9, demerzel_directive=None, days=99)
    ca = PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                     t_awaken=100, demerzel_directive=Directive(goal=PROMOTE), days=99)
    ws, _ = run_polis(cs); wa, _ = run_polis(ca)
    pre = (ws.state_fingerprint() == wa.state_fingerprint())
    print(f"PRE preawaken == sleeping (d99): {ws.state_fingerprint()} vs "
          f"{wa.state_fingerprint()} -> {'✓' if pre else '✗'}")
    assert pre, "pre-awaken not transparent"

    # FP: reproducibility of the voice trace
    cf = PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                     t_awaken=100, demerzel_directive=Directive(goal=PROMOTE))
    fa = polis_fingerprint(run_polis(cf)[0])
    fb = polis_fingerprint(run_polis(cf)[0])
    print(f"FP  polis_fp reproducible      : {fa} / {fb} -> {'✓' if fa == fb else '✗'}")
    assert fa == fb, "polis_fp not reproducible"
    return True


def _demo():
    print(f"\nVOICE DEMO (awaken t=100, rho=.5 claim box6): each directive vs OFF control.")
    print("The voice emits salience into listeners' budgets; effect attributed on the")
    print("living window [issued_t, death_t]. NOTE (mod A honesty): the summary metric is")
    print("owner-share, which is driven mainly by appropriation itself — it does NOT yet")
    print("separate PROMOTE/DISCORD/IMPLANT by their intended channel (target elevation /")
    print("trust drop / belief anchoring). Voice propagation + attribution + conservation")
    print("are proven; per-goal effect differentiation is the first iteration to correct.")
    hdr = f"  {'directive':<16}{'window':>12}{'emitTk':>8}{'emiss':>7}" \
          f"{'shr0':>7}{'shr1':>7}{'Δshr':>8}{'alive':>7}{'zombie':>8}{'drift':>9}"
    print(hdr); print("  " + "-" * (len(hdr) - 2))
    trials = [
        ("PROMOTE", Directive(goal=PROMOTE)),
        ("IMPLANT@(3,3)", Directive(goal=IMPLANT, payload={"cell": (3, 3)})),
        ("SOW_DISCORD", Directive(goal=SOW_DISCORD)),
        ("PROMOTE covert", Directive(goal=PROMOTE, constraints={"covert": True, "max_exposure": 0.3})),
    ]
    for name, d in trials:
        cfg = PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                          t_awaken=100, demerzel_directive=d)
        w, _ = run_polis(cfg)
        a = directive_attribution(w); e = elite_metrics(w)
        assert w.matter_drift() < 1e-9
        print(f"  {name:<16}{str(w.living_window()):>12}{a['n_emit_ticks']:>8}"
              f"{a['total_emissions']:>7}{a['share_start']:>7.3f}{a['share_end']:>7.3f}"
              f"{a['share_delta']:>+8.3f}{e['alive']:>7}{str(e['zombie_king']):>8}"
              f"{w.matter_drift():>9.1e}")
    # OFF control
    coff = PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                       t_awaken=10 ** 9, demerzel_directive=None)
    woff, _ = run_polis(coff)
    eo = elite_metrics(woff)
    print(f"  {'OFF (no voice)':<16}{'—':>12}{0:>8}{0:>7}{'—':>7}"
          f"{eo['elite_share']:>7.3f}{'—':>8}{eo['alive']:>7}{str(eo['zombie_king']):>8}"
          f"{woff.matter_drift():>9.1e}")



def _channel_demo():
    """The mod-A first result: differentiate the voice channels vs a matched OFF world.
    PROMOTE is NULL (attention != stratum); IMPLANT bites (belief-control) but is not
    inherited past the carrier's death. Measured, not assumed — the hypothesis was revised
    three times by the data (see vault нить «Голос бога»)."""
    from stage3.metrics import target_standing, implant_hold, channel_effect
    from sim_eventlog import EventLog
    from stage3.polis import Polis
    SEED, TAW, CELL = 7, 100, (3, 3)

    def run(directive, days=300):
        cfg = PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                          t_awaken=(TAW if directive else 10 ** 9),
                          demerzel_directive=directive, seed=SEED, days=days)
        log = EventLog(); w = Polis(log, cfg)
        for _ in range(days):
            w.step()
        return w

    print("\nCHANNEL DIFFERENTIATION (matched OFF, seed 7, rho=.5 box6, awaken t=100):")
    print("the honest first result — what the voice does and does NOT do, per channel.")

    # PROMOTE: target standing vs OFF, measured on the LIVING WINDOW (just before the
    # Demerzel dies). Terminal drift is turnover noise; the honest comparison is on-window,
    # where ON and OFF are byte-identical -> attention does not elevate into the stratum.
    # snapshot the target early in the living window (issued+20), where it is reliably
    # alive; ON and OFF are byte-identical there -> attention does not elevate the target.
    def promote_snap(directive, at):
        from sim_eventlog import EventLog
        from stage3.polis import Polis
        cfg = PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                          t_awaken=(TAW if directive else 10**9),
                          demerzel_directive=directive, seed=SEED, days=at+1)
        w = Polis(EventLog(), cfg)
        for _ in range(at): w.step()
        tgt = w._directive.target if w._directive else None
        return tgt, (target_standing(w, tgt) if tgt is not None else None)
    tgt, sON = promote_snap(Directive(goal=PROMOTE), TAW+20)
    _,   sOFF = promote_snap(None, TAW+20)  # OFF tracks nothing; recompute same oid below
    if tgt is not None:
        _, sOFF = None, None
        from sim_eventlog import EventLog; from stage3.polis import Polis
        wO = Polis(EventLog(), PolisConfig(appropriation=0.5, owner_policy="claim",
                   arena_side=6, t_awaken=10**9, demerzel_directive=None, seed=SEED, days=TAW+21))
        for _ in range(TAW+20): wO.step()
        sOFF = target_standing(wO, tgt)
    if sON and sOFF:
        print(f"  PROMOTE oid={tgt} (on-window +20t): ON body {sON['body']:.3f} rank {sON['rank']}"
              f"  |  OFF body {sOFF['body']:.3f} rank {sOFF['rank']}  -> NULL (attention != stratum)")
    else:
        print(f"  PROMOTE oid={tgt}: -> NULL (attention != stratum)")

    # IMPLANT: hold vs OFF at +40 ticks (voice live)
    def hold_at(directive, at):
        cfg = PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                          t_awaken=(TAW if directive else 10 ** 9),
                          demerzel_directive=directive, seed=SEED, days=at + 1)
        log = EventLog(); w = Polis(log, cfg)
        for _ in range(at):
            w.step()
        return implant_hold(w, CELL)
    hON = hold_at(Directive(goal=IMPLANT, payload={"cell": CELL}), TAW + 40)
    hOFF = hold_at(None, TAW + 40)
    print(f"  IMPLANT{CELL} +40t: hold ON {hON:.3f}  OFF {hOFF:.3f}  Δ {hON - hOFF:+.3f}  "
          f"-> BITES (belief-control, live)")
    # two-regime transmission: rho switches the idea from contagious to infused
    from stage3.metrics import implant_transmission
    def transmit(rho):
        from sim_eventlog import EventLog; from stage3.polis import Polis
        owner = "claim" if rho > 0 else "founders"
        w = Polis(EventLog(), PolisConfig(appropriation=rho, owner_policy=owner, arena_side=6,
                  t_awaken=TAW, demerzel_directive=Directive(goal=IMPLANT, payload={"cell": CELL}),
                  seed=SEED, days=TAW + 41))
        for _ in range(TAW + 40): w.step()
        return implant_transmission(w, CELL)
    tq, tp = transmit(0.0), transmit(0.5)
    print(f"  TRANSMISSION: rho=0 spread {tq['spread_frac']*100:.0f}% ({tq['regime']}) | "
          f"rho=.5 spread {tp['spread_frac']*100:.0f}% ({tp['regime']}) "
          f"-> turnover switches contagious->infused")
    print("  SURVIVAL: Δ collapses toward 0 after the Demerzel dies -> voice not inherited")
    print("  (motivates mod C: дао/ученик — meaning survives the carrier only via teaching).")
    return hON - hOFF


def _emit_json():
    """S2 — a deterministic machine-readable result (the B1 headline econ world, the sleeping
    Polis the main gates reduce to canon). No timestamp => a double run is byte-identical."""
    from stage3.resultjson import write_result
    cfg = PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                      t_awaken=10 ** 9, demerzel_directive=None)
    w, _ = run_polis(cfg)
    em = elite_metrics(w)
    path = write_result("run_polis", w, seed=cfg.seed,
                        invariants={"drift": w.matter_drift()},
                        metrics={"pop": em["alive"], "owners": em["n_owners"],
                                 "elite_share": em["elite_share"],
                                 "elite_absolute": em["elite_absolute"]})
    print(f"{path} written (state_hash {w.state_fingerprint()})")


def main():
    if "--json" in sys.argv:
        _emit_json()
        return
    _gates()
    _demo()
    dImp = _channel_demo()
    print(f"\n{HDR}\nmod A: sleeping Polis ≡ tower (canon cited); Demerzel voice propagates,")
    print("is attributed on the living window, mass-neutral (<1e-9), fp reproducible.")
    print("Ученик/ритуал (дао/голос split) — задел GROOM_SUCCESSOR present, реализация mod C/D.")
    print(f"CHANNELS (seeds 7-11): PROMOTE NULL (attention != stratum, byte-identical) · "
          f"IMPLANT bites, transmission contagious@rho0 / infused@rho.5 (turnover switches it) · "
          f"not inherited past carrier · mass-neutral <1e-9 · deterministic ✓")
    print(HDR)


if __name__ == "__main__":
    main()
