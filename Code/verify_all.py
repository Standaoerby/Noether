"""
verify_all.py — double-check the whole family at once.

Each module in the tower is self-verifying: its demo ends in `assert`s on the
conservation laws it is responsible for, and prints a success marker. This
harness runs every module end-to-end and confirms, uniformly:

  1. CONSERVATION  — the module exits 0, i.e. all of its invariant asserts held
     (mass / energy-across-boundary / body-parcel / monotone entropy, as
     appropriate to that layer).
  2. DETERMINISM   — two independent runs produce byte-identical output, so the
     whole history is reproducible and replayable (the property the reversibility
     and multiplayer arguments rest on).

It then prints the key invariant line(s) each module reported, so the actual
drift numbers are visible in one place.

The tower, bottom to top:
  sim_core      conservation kernel        : mass ==, energy == (thermal+chemical)
  sim_ecology   boundary flux + entropy    : E-E0 == in-out ; entropy >= 0
  sim_genetics  information                 : bits accumulate on a closed matter loop
  sim_world     full synthesis (1 patch)    : all four invariants at once
  sim_space     space: clines/refugia       : + conservative numpy heat field
  sim_traits    two genes: Bergmann         : + a second adaptive axis
  sim_pareto    the Pareto front explicit   : multi-objective selection + domination
  sim_portfolio the portfolio effect        : variance-averaging across demes
  sim_eventlog  a universal event log        : faithful, queryable, narratable history
  sim_stage2    a mind inside a pawn          : typed action, conserved, replayable cognition
  sim_comm      communication events          : claims (true/false) reshape belief; rivalrous-resource capture
  sim_comm_llm  focal LLM speakers            : pluggable speaker policy; deception emerges as equilibrium
  sim_polariz   polarization & factions        : empirical elite-theory metrics on divergent beliefs
  sim_trust     trust-weighting               : accountable listeners; does reputation break the lie equilibrium
  sim_gossip    shared reputation / gossip    : pooled reputation captured by the credulous majority; reputation capture
  sim_warn      warnings-dominate gossip      : propagating distrust pins the liar — and weaponizes slander
  sim_evidence  evidence-count gossip (K-witness): K dials conviction↔slander; K=1 ≡ sim_warn
  sim_stake     existential stake             : death as a motive — survival pressure modulates the lie
  sim_coalition collective sanction           : a quorum silences a target's voice — the first joint political verb
  sim_sphere    the observer                  : local materialization + attention budget + info lag (embodied substrate)
  sim_salience  exogenous salience injection  : push another agent's agenda — crowd-out harm, mass-not-few concentration
  sim_enclosure the bounded arena              : close spatial escape — confinement concentrates geometrically, capture still NULLs
  sim_appropriation the appropriable resource  : owner takes rent — the first transfer that builds a wealth stratum (hierarchy at last)
  sim_institution the protector institution    : tax owners to fund a guard caste — challenge suppressed, but the guards capture the surplus
  sim_inheritance heritable property            : ownership passes to a bloodline heir — land concentrates into fewer, older houses (dynasties)
  sim_exclusion denial of access                : owner bars non-owners from its cell — no capacity collapse, but no extra stratification either
  sim_trade ownership traded between living     : richest buyer buys a deed from its holder — market vs gift: does liquidity concentrate or equalize?
  sim_synthesis the keystone                     : inheritance x exclusion x trade at once — do the three property verbs compound, or interfere?

PROBES (ВСТАВКА-29-class, read-only forensics over the closed tower; NOT modules):
  sim_gradient_probe gradient revision           : tail-shape (mod-23) + K-window (mod-20) — Pareto 80/20 does not emerge; attention scarcity is a dose curve with a finite window

Run:  python3 verify_all.py
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time

MODULES = [
    ("sim_core",      "conservation kernel (mass ==, energy ==)"),
    ("sim_ecology",   "boundary flux + entropy (E-E0 == in-out)"),
    ("sim_genetics",  "information accrues on a closed matter loop"),
    ("sim_world",     "full synthesis on one patch (4 invariants)"),
    ("sim_space",     "space: clines, range shift, refugium"),
    ("sim_traits",    "two genes: temp_opt + size (Bergmann)"),
    ("sim_pareto",    "Pareto front + domination (multi-objective)"),
    ("sim_portfolio", "portfolio effect: variance-averaging law"),
    ("sim_eventlog",  "universal event log: faithful, queryable history"),
    ("sim_stage2",    "a mind inside a pawn: typed, conserved, replayable"),
    ("sim_comm",      "communication events: belief spreads, can be shaped"),
    ("sim_comm_llm",  "focal LLM speakers: pluggable policy; deception as equilibrium"),
    ("sim_polariz",   "polarization, factions, propagation: empirical elite-theory metrics"),
    ("sim_trust",     "trust-weighting: accountable listeners vs the lie equilibrium"),
    ("sim_gossip",    "shared reputation: pooled gossip captured by the credulous majority"),
    ("sim_warn",      "warnings-dominate gossip: pins the liar, but weaponizes slander"),
    ("sim_evidence",  "evidence-count gossip (K-witness): K dials conviction vs slander"),
    ("sim_stake",     "existential stake: death as a motive — survival pressure modulates the lie"),
    ("sim_coalition", "collective sanction: a quorum silences a target's voice (the first joint political verb)"),
    ("sim_sphere",    "the observer: local materialization + attention budget + information lag"),
    ("sim_salience",  "exogenous salience injection: push another agent's agenda (crowd-out harm)"),
    ("sim_enclosure", "the bounded arena: close spatial escape — confinement concentrates, capture NULLs"),
    ("sim_appropriation", "the appropriable resource: owner takes rent — first transfer to build a wealth stratum"),
    ("sim_institution", "the protector institution: tax owners to fund a guard caste — challenge suppressed, guards capture the surplus"),
    ("sim_inheritance", "heritable property: ownership passes to a bloodline heir — land concentrates into fewer, older houses (dynasties)"),
    ("sim_exclusion", "denial of access: owner bars non-owners from its cell — no collapse, but no extra stratification"),
    ("sim_trade", "ownership traded between the living: richest buyer buys a deed — market vs gift, does liquidity concentrate or equalize?"),
    ("sim_synthesis", "the keystone: inheritance x exclusion x trade at once — do the three property verbs compound, or interfere?"),
    # ВСТАВКА-29-class PROBES — read-only forensics over existing worlds (NOT tower modules;
    # the tower stays closed at 28). Included so the book's numbers stand on verify_all.
    ("sim_gradient_probe", "gradient revision (PROBE, read-only): tail-shape (mod-23, no Pareto 80/20) + K-window (mod-20, dose curve not zero)"),
    # STAGE-3 COLUMN — the subject layer above the closed tower (NOT a tower module,
    # NOT a probe). Polis(AppropriationWorld) + thick pawn + Demerzel (deterministic voice
    # of god via salience). Asleep (t_awaken=inf, no directive) it is byte-identical to the
    # tower canon; the voice never touches mass. Lives in ../stage3 (like viz/).
    ("../stage3/run_polis", "STAGE-3 mod A (COLUMN): Polis + thick pawn + Demerzel voice — sleeping≡canon, voice propagates & is attributed on the living window, mass-neutral"),
    ("../stage3/run_polis_llm", "STAGE-3 mod B (COLUMN): living mind (Claude API) — world deterministic-from-log, mind pluggable, inert without key"),
]

# --------------------------------------------------------------------------- #
#  S1 (WO_consolidation-sprint) — the test-suite registry. `--suite NAME` runs a
#  named set of runners; with NO argument the modules AND the output are the prior
#  default (this MODULES list), byte-for-byte. "canonical" == that prior default —
#  the honest fix for "verify_all green != Noether green": the whole claim is
#  `--suite all` (canon tower + stage3 column), not the tower alone.
# --------------------------------------------------------------------------- #
# stage3 column GATE runners (assert-based, deterministic; invoked relative to Code/
# like run_polis). Heavier than the tower — they live in `stage3`/`all`, not `fast`.
_STAGE3 = [
    ("../stage3/run_artifact_f",   "mod F vitok 1 (vessel): MF-* reservoir gates"),
    ("../stage3/run_artifact_f2",  "mod F vitok 2 (store+capital): MFv2-* gates"),
    ("../stage3/run_artifact_f3",  "mod F vitok 3 (settle+vision): MFv3-* gates"),
    ("../stage3/run_artifact_g",   "mod G (intent vitok 1): MG-* gates"),
    ("../stage3/run_artifact_g2",  "mod G2 (EXTORT): MG2-* gates"),
    ("../stage3/run_artifact_g2d", "mod G2 (DELEGATE/REVOKE): MG2D-* gates"),
    ("../stage3/run_artifact_g2v2","mod G2 vitok 2: MG2V-* gates (incl. reputation anchor)"),
    ("../stage3/run_glass_v3",     "viz β-3: V3-FP/OLD/AGG/NUM gates"),
    ("../stage3/run_mark_gc_ident","MG2V-GC-IDENT: dead-oid mark-ledger GC digest"),
    ("../stage3/run_dunbar_e",     "mod E (Dunbar): ME-* gates"),
    ("../stage3/run_archipelago_d","mod D (archipelago): MD-* gates"),
    ("../stage3/run_artifact_h",   "mod H vitok 1 (DEBT): MH-* gates"),
    ("../stage3/run_artifact_h2",  "mod H vitok 2 (4 confounds): MH2-* gates"),
    ("../stage3/run_artifact_h2bis","mod H2-bis (K5 + credit channel): MH2B-* gates"),
    ("../stage3/run_artifact_h3",  "mod H3 (public good + punishment + enforcer): MH3-* gates"),
]


# the laboratory twin — OUTSIDE the tower (WO_pg-lab.md): no canon, no polis, and NON-
# conserving BY DESIGN (the bank creates money, the fine burns it). It carries its own gates
# (LAB-640 cooperation math, LAB-CONS accounting, LAB-DET determinism) and joins `lab`/`all`,
# never the conservation-oriented tower suites.
_LAB = [
    ("../lab/pg_lab", "pg-lab: LAB-640/CONS/DET (letter's conditions; non-conserving by design)"),
]


def _by_names(names):
    """Pull (module, desc) tuples out of MODULES by name, preserving the given order."""
    idx = {m: (m, d) for m, d in MODULES}
    return [idx[n] for n in names if n in idx]


# fast = the tower's conservation core + one stage3 smoke; tuned for CI (<~5 min).
_FAST_NAMES = ["sim_core", "sim_ecology", "sim_genetics", "sim_world", "sim_eventlog",
               "sim_stage2", "../stage3/run_polis"]

SUITES = {
    "canonical":   MODULES,                                  # the prior default, unchanged
    "fast":        _by_names(_FAST_NAMES),
    "stage3":      _by_names(["../stage3/run_polis", "../stage3/run_polis_llm"]) + _STAGE3,
    "longrun":     [("../stage3/run_longrun", "long-horizon degeneracy audit (heavy; local-only)")],
    "llm-offline": _by_names(["sim_comm_llm", "../stage3/run_polis_llm"]),
    "lab":         _LAB,                                     # the laboratory twin (outside the tower)
    "all":         MODULES + _STAGE3 + _LAB,                 # the full Noether claim + the lab twin
}

# lines worth surfacing: anything about drift/energy/entropy or the success marker
KEY = re.compile(r"(drift|energy|entropy|invariant|conserv|cline|Bergmann|"
                 r"frontier|dominated|portfolio|buffer|law|faithful|"
                 r"reconstruct|deterministic|✓)", re.IGNORECASE)
TIMEOUT = 600


def run_once(module):
    t0 = time.time()
    # Force UTF-8 in the child so its ✓ / arrows / Cyrillic don't crash on the Windows
    # console codepage (cp1251), which would otherwise fail the child before it prints.
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    proc = subprocess.run([sys.executable, f"{module}.py"],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env=env, timeout=TIMEOUT)
    return proc.returncode, proc.stdout, proc.stderr, time.time() - t0


def key_lines(stdout):
    out = []
    for ln in stdout.splitlines():
        s = ln.strip()
        if s and KEY.search(s) and not s.startswith(("=", "-")) and "Phase" not in s:
            out.append(s)
    # keep the most informative tail (drift numbers + the ✓ marker live there)
    return out[-4:]


def main():
    ap = argparse.ArgumentParser(description="run a named suite of Noether runners twice and "
                                             "check conservation + determinism")
    ap.add_argument("--suite", choices=sorted(SUITES), default=None,
                    help="named runner set (default: the canonical set — prior behaviour). "
                         "'all' is the full Noether claim (canon tower + stage3 column).")
    args = ap.parse_args()
    modules = MODULES if args.suite is None else SUITES[args.suite]

    print("=" * 78)
    print("DOUBLE-CHECK: running the whole simulation family")
    print("=" * 78)
    if args.suite is not None:                               # no-arg output stays byte-identical
        print(f"suite: {args.suite} ({len(modules)} runners)")

    rows = []
    all_ok = True
    for module, what in modules:
        try:
            rc1, out1, err1, dt1 = run_once(module)
            rc2, out2, err2, _ = run_once(module)
        except subprocess.TimeoutExpired:
            rows.append((module, "TIMEOUT", "—", 0.0, what, []))
            all_ok = False
            continue

        conserved = (rc1 == 0 and rc2 == 0)
        h1 = hashlib.sha256(out1.encode()).hexdigest()
        h2 = hashlib.sha256(out2.encode()).hexdigest()
        deterministic = (h1 == h2)
        ok = conserved and deterministic
        all_ok = all_ok and ok

        status = "PASS" if conserved else "FAIL"
        det = "yes" if deterministic else "NO"
        note = "" if conserved else (err1.strip().splitlines()[-1:] or [""])[0]
        rows.append((module, status, det, dt1, what, key_lines(out1) if conserved else [note]))

    # summary table
    print(f"\n{'module':<14}{'conserved':>11}{'deterministic':>15}{'sec':>7}   what it guards")
    print("-" * 78)
    for module, status, det, dt, what, _ in rows:
        mark = "✓" if status == "PASS" else "✗"
        print(f"{module:<14}{status:>9} {mark}{det:>14}{dt:>7.1f}   {what}")

    # the actual invariant numbers each module reported
    print("\n" + "=" * 78)
    print("invariant lines reported by each module")
    print("=" * 78)
    for module, status, det, dt, what, lines in rows:
        print(f"\n[{module}]")
        for ln in lines:
            print(f"    {ln}")

    print("\n" + "=" * 78)
    if all_ok:
        print("ALL MODULES PASS — every layer conserves what it must, and every run")
        print("is byte-for-byte reproducible. The tower stands as a whole. ✓")
    else:
        print("SOME MODULES FAILED — see above.")
    print("=" * 78)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
