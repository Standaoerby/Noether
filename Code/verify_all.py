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

Run:  python3 verify_all.py
"""

import hashlib
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
]

# lines worth surfacing: anything about drift/energy/entropy or the success marker
KEY = re.compile(r"(drift|energy|entropy|invariant|conserv|cline|Bergmann|"
                 r"frontier|dominated|portfolio|buffer|law|faithful|"
                 r"reconstruct|deterministic|✓)", re.IGNORECASE)
TIMEOUT = 600


def run_once(module):
    t0 = time.time()
    proc = subprocess.run([sys.executable, f"{module}.py"],
                          capture_output=True, text=True, timeout=TIMEOUT)
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
    print("=" * 78)
    print("DOUBLE-CHECK: running the whole simulation family")
    print("=" * 78)

    rows = []
    all_ok = True
    for module, what in MODULES:
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
