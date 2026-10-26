"""run_soma_l0.py — layer-0 gate runner (style: stage3/run_artifact_f2).

    py soma/run_soma_l0.py               # every gate (default == --all)
    py soma/run_soma_l0.py --gate MS-iso # one named gate

Each gate prints `NAME  desc -> ✓/✗` and ASSERTS, so any failure exits non-zero (self-verifying).

Present (infrastructure + invariants — independent of the pending shrink rate and pending mass):
  MS-iso    import-graph isolation (static AST)
  MS-lit    no parameter literals in the flux code (AST)
  MS-range  e, l in [0,1] every tick
  MS-prio   growth never happens on unpaid somatic maintenance
  MS-replay two runs, same seed, byte-identical anchor stream
  MS-stake  MUTATIONAL: null the body deltas -> the growth invariant MUST fail (positive control)
  MS-cons   the maturity-clamp leak is measured and is ZERO when the clamp never fires; reserve
            balance exact. (Full DEB energy closure needs [E_G] alone, unavailable in the compound
            set — so MS-cons is the leak-accounting form, WO review.)
  MS-ns     the soma anchor carries the `soma:` prefix AND is domain-separated by construction

Deferred (need the pending shrink rate / mass / repro event): MS-vb·MS-f (one transcription test),
MS-starve, MS-daphnia, MS-reserve-id, MS-reserve-lag, MS-vector(shape), MS-step-conv.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SOMA_DIR = Path(__file__).resolve().parent
REPO_ROOT = SOMA_DIR.parent
TOWER_DIRS = ["Code", "stage3", "lab", "scripts"]
_ALLOWED_ROOTS = set(sys.stdlib_module_names) | {"numpy", "soma"}
HDR = "=" * 78


# --------------------------------------------------------------------------------------------
# MS-iso — pure static import-graph check (no runtime import; valid even before physics exists).
# --------------------------------------------------------------------------------------------
def _import_roots(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0], node
        elif isinstance(node, ast.ImportFrom):
            yield (None if (node.level and node.level > 0) else (node.module or "").split(".")[0]), node


def _py_files(root: Path):
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" not in p.parts:
            yield p


def _gate_ms_iso():
    forward, n_soma = [], 0
    for p in _py_files(SOMA_DIR):
        n_soma += 1
        for root, node in _import_roots(ast.parse(p.read_text(encoding="utf-8"), filename=str(p))):
            if root is not None and root not in _ALLOWED_ROOTS:
                forward.append(f"{p.relative_to(REPO_ROOT)}:{node.lineno} imports '{root}'")
    reverse, n_tower = [], 0
    for d in TOWER_DIRS:
        base = REPO_ROOT / d
        if not base.exists():
            continue
        for p in _py_files(base):
            n_tower += 1
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for root, node in _import_roots(tree):
                if root == "soma":
                    reverse.append(f"{p.relative_to(REPO_ROOT)}:{node.lineno} imports 'soma'")
    ok = not forward and not reverse
    print(f"MS-iso    soma/({n_soma}f) <-> tower({n_tower}f): zero cross-imports -> {'✓' if ok else '✗'}")
    for lbl, seams in (("FORWARD", forward), ("REVERSE", reverse)):
        for s in seams:
            print(f"   seam {lbl}: {s}")
    assert ok, "MS-iso: import seam between soma/ and the tower"


# --------------------------------------------------------------------------------------------
# Runtime gates — lazy import so MS-iso stays a pure static check.
# --------------------------------------------------------------------------------------------
def _rt():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import numpy as np
    from random import Random
    from soma.config import DAPHNIA_MAGNA, load
    from soma import soma as S
    from soma import trace as T
    return np, Random, DAPHNIA_MAGNA, load, S, T


def _run(f, T, dt=0.002, seed=7, collect=False):
    np, Random, entry, load, S, TR = _rt()
    p = load(entry)
    org = S.Organism(soma=S.birth_state(p, f=f, L0=0.5), params=p, rng=Random(seed))
    trace, ext = [], {"e_max": 0.0, "l_max": 0.0, "assim": 0.0, "mob": 0.0, "prio_ok": True, "n_ticks": 0}
    n = int(T / dt)
    for _ in range(n):
        ext["n_ticks"] += 1
        s = org.soma
        e = S.scaled_reserve_density(s, p); l = S.scaled_length(s, p)
        dUE, dUH, dUR, dL, starving, leak = S._fluxes(s, p, f, p.kap)
        SA = (f if s.U_H > p.U_Hb else 0.0) * s.L ** 2
        ext["assim"] += float(np.sum(SA)) * dt
        ext["mob"] += float(np.sum(SA - dUE)) * dt          # mobilization = SA - dU_E
        ext["e_max"] = max(ext["e_max"], float(np.max(e)));  ext["l_max"] = max(ext["l_max"], float(np.max(l)))
        if bool(np.any(dL > 0)) and starving:               # MS-prio: no growth while starving
            ext["prio_ok"] = False
        org = S.step(org, f, dt)
        if collect:
            trace.append(TR.state_digest(org))
        if not org.alive:
            break
    return org, trace, ext, (np, S, TR, p)


def _gate_ms_lit():
    np, _, entry, load, S, _ = _rt()
    p = entry                                               # the printed DebParams (canon values)
    smells = {p.kap, p.kap_R, p.k_M, p.k_J, p.U_Hb, p.U_Hp, p.v, p.g, p.h_a, p.s_G,
              p.J_XAm, p.K, p.molt, p.V_crit, p.starv_mortality, 0.75}

    def scan(src):
        out = []
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                if any(abs(node.value - v) < 1e-12 for v in smells):
                    out.append((node.lineno, node.value))
        return out

    # TOOTH (teeth-rule): a scanner that scans the wrong nodes/files passes everything. Plant a
    # parameter literal and require the scanner to catch it — else the green is meaningless.
    assert scan("x = 0.678\n"), "MS-lit tooth: a planted parameter literal was NOT detected"

    hits = scan((SOMA_DIR / "soma.py").read_text(encoding="utf-8"))
    ok = not hits
    print(f"MS-lit    no parameter literals in flux code (soma.py) -> {'✓' if ok else '✗'}")
    for ln, val in hits:
        print(f"   soma.py:{ln} literal {val}")
    assert ok, "MS-lit: a parameter value is hard-coded in the flux code (must come from config)"


def _gate_ms_range():
    _, _, _, _, _, _ = _rt()
    org, _, ext, _ = _run(0.8, 90.0)
    # detector includes an EXECUTION guard: an empty vector or an unrun loop must NOT pass green.
    detect = lambda emax, lmax, n: (n > 0) and (emax <= 1.0 + 1e-9) and (lmax <= 1.0 + 1e-9)
    assert not detect(1.5, 0.5, ext["n_ticks"]), "MS-range tooth: an out-of-range e was not caught"
    assert not detect(0.5, 0.5, 0), "MS-range tooth: an empty/unrun loop passed"
    ok = detect(ext["e_max"], ext["l_max"], ext["n_ticks"])
    print(f"MS-range  e,l in [0,1] over {ext['n_ticks']} ticks (max e={ext['e_max']:.4f}, l={ext['l_max']:.4f}) -> {'✓' if ok else '✗'}")
    assert ok, "MS-range: e or l left [0,1], or the run did not execute"


def _gate_ms_prio():
    org, _, ext, _ = _run(0.8, 40.0)                        # grow, then verify no growth-while-starving
    org2, _, ext2, _ = _run(0.0, 30.0)                      # starving regime
    ok = ext["prio_ok"] and ext2["prio_ok"]
    print(f"MS-prio   no growth on unpaid somatic maintenance -> {'✓' if ok else '✗'}")
    assert ok, "MS-prio: growth (dL>0) occurred while starving (e<l)"


def _gate_ms_replay():
    _, t1, _, _ = _run(0.8, 30.0, seed=7, collect=True)
    _, t2, _, _ = _run(0.8, 30.0, seed=7, collect=True)
    ok = t1 == t2 and len(t1) > 0
    print(f"MS-replay two runs same seed byte-identical ({len(t1)} ticks) -> {'✓' if ok else '✗'}")
    assert ok, "MS-replay: same-seed runs diverged"


def _gate_ms_stake():
    """MUTATIONAL positive control on the stand: null the body deltas -> the growth invariant MUST
    fail. If a frozen body still 'grows', the growth gate is not actually reading the body."""
    np, Random, entry, load, S, TR = _rt()
    p = load(entry)
    grew = lambda o: float(o.soma.L[0]) > 0.55              # the 'vitok-1 grows' invariant (L0=0.5)
    live, _, _, _ = _run(0.8, 30.0)
    orig = S._fluxes
    S._fluxes = lambda s, pr, f, kap: (np.zeros_like(s.U_E), 0.0, 0.0, np.zeros_like(s.L), False, 0.0)
    try:
        frozen = S.Organism(soma=S.birth_state(p, f=0.8, L0=0.5), params=p, rng=Random(7))
        for _ in range(int(30.0 / 0.002)):
            frozen = S.step(frozen, 0.8, 0.002)
    finally:
        S._fluxes = orig
    ok = grew(live) and not grew(frozen)                   # invariant true on live, FALSE on frozen
    print(f"MS-stake  null body deltas -> growth invariant fails (live grew={grew(live)}, "
          f"frozen grew={grew(frozen)}) -> {'✓' if ok else '✗'}")
    assert ok, "MS-stake: the growth invariant does not actually depend on the body (dead stand)"


def _gate_ms_cons():
    """Reserve balance closes AND the maturity-clamp leak counter is 0 when the clamp is silent.
    This is NOT full energy conservation: the soma-branch closure needs [E_G] alone, which the
    compound set cannot give (the option-B wall). The verdict says exactly that — reserve balance +
    leak counter, not 'energy conserved' (so it can't be miscited a vitok later)."""
    np, _, _, _, S, _ = _rt()
    org, _, ext, (np_, S_, TR_, p) = _run(0.8, 90.0)
    dUE_total = float(np.sum(org.soma.U_E)) - float(np.sum(S.birth_state(p, f=0.8, L0=0.5).U_E))
    reserve_drift = abs(dUE_total - (ext["assim"] - ext["mob"]))

    detect = lambda leak, drift: (leak == 0.0) and (drift < 1e-9)
    # TOOTH (teeth-rule): the classic silent pass is a residual x-x that always converges. Inject a
    # KNOWN leak and require red — else a broken balance would sail through the most diagnostic gate.
    assert not detect(1e-6, reserve_drift), "MS-cons tooth: an injected leak was not detected"

    ok = detect(org.maturity_leak, reserve_drift)
    print(f"MS-cons   reserve balance + leak counter converge (leak={org.maturity_leak:.2e}, "
          f"0 at f=0.8; drift={reserve_drift:.1e}) [NOT full energy closure — compound wall] -> {'✓' if ok else '✗'}")
    assert ok, "MS-cons: leak nonzero without clamp, or reserve balance drifted"


def _gate_ms_step_conv():
    """Euler-step convergence at MINIMUM L (stiffest: reserve relaxation rate v̇/L is largest,
    f-independent). Start OFF the manifold (e0<f) to excite the stiff reserve mode; integrate at
    h, h/2, h/4; require the trajectory to CONVERGE and the error to be FIRST ORDER (~halves per
    halving — Euler is O(h)). First-order distinguishes convergence from a coincidental plateau.
    A pass turns 'Euler step not matched' into a MEASURED bound — Martin's exact step stops
    mattering, no ODD Appendix A needed."""
    np, Random, entry, load, S, TR = _rt()
    p = load(entry)

    def L_at(dt, T=20.0, f=0.8, L0=0.5, e0=0.5):
        s = S.Soma(U_E=np.array([e0 * L0 ** 3 / p.v]), L=np.array([L0]),
                   U_H=p.U_Hb * 1.5, U_R=0.0, q=0.0, h=0.0, age=0.0)
        org = S.Organism(soma=s, params=p, rng=Random(0))
        for _ in range(int(T / dt)):
            org = S.step(org, f, dt)
        return float(org.soma.L[0])

    h = 0.004
    Ls = [L_at(h / 2 ** k) for k in range(4)]              # h, h/2, h/4, h/8 (4 points, not 3)
    d = [abs(Ls[i] - Ls[i + 1]) for i in range(3)]         # successive Richardson differences
    r = [d[i] / d[i + 1] if d[i + 1] > 0 else float("inf") for i in range(2)]
    geometric = d[0] > d[1] > d[2] > 0                     # absolute error shrinks geometrically
    # error-RATIO ~2 means 2^p with p=1 (Euler is first ORDER); it is NOT itself the order. Requiring
    # BOTH successive ratios ~2 (held across two halvings) is the law, not one point that could coincide.
    held = all(1.6 < ri < 2.4 for ri in r)
    ok = geometric and held
    print(f"MS-step-conv min-L: |ΔL| {d[0]:.2e}->{d[1]:.2e}->{d[2]:.2e}  err-ratio {r[0]:.2f},{r[1]:.2f} "
          f"(=2^p, p=1 => Euler first-order) -> {'✓' if ok else '✗'}")
    assert ok, "MS-step-conv: error not shrinking geometrically at a held first-order ratio"


def _gate_ms_ns():
    np, Random, entry, load, S, TR = _rt()
    p = load(entry)
    org = S.Organism(soma=S.birth_state(p, f=0.8, L0=0.5), params=p)
    d = TR.state_digest(org)
    prefix_ok = d.startswith("soma:")
    domain_ok = d[len("soma:"):] != TR.raw_digest(org)     # domain tag actually changes the digest
    ok = prefix_ok and domain_ok
    print(f"MS-ns     soma anchor prefixed + domain-separated by construction -> {'✓' if ok else '✗'}")
    assert ok, "MS-ns: anchor missing 'soma:' prefix or domain tag not separating"


GATES = {
    "MS-iso": _gate_ms_iso, "MS-lit": _gate_ms_lit, "MS-range": _gate_ms_range,
    "MS-prio": _gate_ms_prio, "MS-replay": _gate_ms_replay, "MS-stake": _gate_ms_stake,
    "MS-cons": _gate_ms_cons, "MS-ns": _gate_ms_ns, "MS-step-conv": _gate_ms_step_conv,
}


def main():
    argv = sys.argv[1:]
    print(HDR)
    print("soma — layer 0 (metabolic core). vitok 1: isolation + invariants (shrink/mass-independent).")
    print(HDR)
    if "--gate" in argv:
        i = argv.index("--gate")
        names = [argv[i + 1]] if i + 1 < len(argv) else []
    else:
        names = list(GATES)
    if not names:
        print("usage: --gate NAME   (have: " + ", ".join(GATES) + ")")
        sys.exit(2)
    for name in names:
        if name not in GATES:
            print(f"unknown gate: {name}   (have: {', '.join(GATES)})")
            sys.exit(2)
        GATES[name]()
    print(f"\n{HDR}")
    print("soma vitok-1: infrastructure + invariant + step-convergence gates green. The physics")
    print("gates (MS-vb/f as ONE transcription test, MS-starve, MS-daphnia, MS-reserve-id/lag,")
    print("MS-vector-shape) await the repro event, Fig.2 data, the shrink rate, and the mass PENDING.")
    print(HDR)


if __name__ == "__main__":
    main()
