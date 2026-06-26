"""
sim_polariz.py — polarization, factions, propagation: empirical elite-theory metrics.

`sim_comm` showed claims reshape belief; `sim_comm_llm` showed self-interested
deception emerges and captures. Both leave agents with *divergent subjective
memories* — and divergence is the substrate of politics. This module introduces no
new dynamics; it only MEASURES what is already there, turning four pieces of elite
theory into deterministic numbers over the four speaking regimes
(`none` / `honest` / `deceptive` / `mock-strategic`):

  1. Belief polarization — how much living agents disagree about where food is. For
     every cell ≥2 living agents have an opinion on, the spread (std) of their
     believed food; aggregated as a believer-weighted mean. Lies should widen it.
  2. Factions — clustered stances. On the most *contested* cells (highest
     inter-agent disagreement) each agent has a stance; agents are grouped by a
     fixed, RNG-free rule (binned-stance agglomeration). More, smaller factions and
     a shattered consensus bloc = a polarized society.
  3. Propagation — claim reach. Straight from the event log: how far a claim about a
     cell travels (listeners exposed) immediately and within a few think-days.
  4. Rationale-vs-outcome — for the strategic speaker, the aggregate over a whole
     run: what share of claims were deceptive, and the realized elite−audience gap
     those claims bought (one example is printed by `sim_comm_llm`; here, the whole).
  5. Deception modes — splits the binary `truthful` flag into "soft" lying (puffery:
     a real cell, padded number) vs "hard" lying (diversion/substitution), so the
     finding "deception evolves: substitution → diversion → inflation" is quantitative.
     `deception_modes(log)` is reusable on any log, including a live cohort JSONL.

Everything is deterministic: the underlying runs come from `sim_comm.run` and
`sim_comm_llm.run_policy(MockStrategicPolicy())`, both seeded; every aggregation
iterates in sorted order and uses population statistics (ddof=0). `main()` recomputes
the entire metric set a second time and asserts the two are byte-identical. No API,
no randomness, pure stdlib + numpy. Current metric fingerprint: 6c4952f66da8326e
(was ac7fcef400f48656 before metric 5 added its lines).
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

import numpy as np

from sim_comm import run as run_comm, THINK_EVERY
from sim_comm_llm import run_policy, MockStrategicPolicy

REGIMES = ("none", "honest", "deceptive", "mock-strategic")

# --- estimator choices (fixed; the WO leaves these to us — only determinism and
#     meaning are mandated). Documented so the numbers are reproducible. --------- #
K_CONTESTED = 6        # how many most-disputed cells define the faction axes
MIN_BELIEVERS = 8      # a cell counts as "contested" only if this many agents weigh in
EPS_FOOD = 10.0        # kg: stance-bin width — agents within a bin "agree" on a cell
PROP_WINDOW = 3        # think-days: window for a claim's delayed reach

# --- deception-mode thresholds. These are DEFINITIONS of "soft" vs "hard" lying,
#     not tuned parameters: a claim is truthful within TOL_ABS of the truth; a lie
#     is SOFT (puffery) if it inflates a real cell by at most R_SOFT relative, and
#     HARD (diversion/substitution) otherwise — gross over-claim or under-claim. --- #
TOL_ABS = 0.05         # kg: |claim-true| within this is "truthful" (covers exact match
                       # and the 0.01-kg rounding the log applies to claim/true_food)
R_SOFT = 0.25          # relative over-claim boundary: <=25% inflation of a REAL cell is
                       # soft puffery; beyond it the claim is a hard diversion lie
EPS_DM = 1e-9          # guards the relative-error division when true_food == 0


# --------------------------------------------------------------------------- #
#  Building the runs (the only place sims are invoked)                         #
# --------------------------------------------------------------------------- #
def build_runs():
    """(world, log) per regime. `none/honest/deceptive` from sim_comm; the
    self-interested speaker from sim_comm_llm. All seeded -> deterministic."""
    runs = {}
    for r in ("none", "honest", "deceptive"):
        runs[r] = run_comm(r)
    runs["mock-strategic"] = run_policy(MockStrategicPolicy(), focal=None)
    return runs


def _live_oids(w):
    return sorted(a.oid for a in w.pop)


def _beliefs_by_cell(w, live):
    """{cell: [believed_food, ...]} over living agents, cells in sorted-oid order."""
    by_cell = defaultdict(list)
    for oid in live:
        for cell, (food, _day) in w.mem.get(oid, {}).items():
            by_cell[cell].append(float(food))
    return by_cell


# --------------------------------------------------------------------------- #
#  1. Belief polarization                                                      #
# --------------------------------------------------------------------------- #
def polarization(w, live):
    """Believer-weighted mean of per-cell belief std, over cells with ≥2 believers."""
    by_cell = _beliefs_by_cell(w, live)
    num, den, ncells = 0.0, 0, 0
    for cell in sorted(by_cell):
        foods = by_cell[cell]
        if len(foods) >= 2:
            s = float(np.std(foods))            # population std (ddof=0)
            num += s * len(foods)
            den += len(foods)
            ncells += 1
    return {"wstd": (num / den if den else 0.0), "cells": ncells}


# --------------------------------------------------------------------------- #
#  2. Factions                                                                 #
# --------------------------------------------------------------------------- #
def _contested_cells(w, live):
    """The K cells with the highest disagreement (std × believers), needing at
    least MIN_BELIEVERS opinions. Deterministic order (then by cell coords)."""
    by_cell = _beliefs_by_cell(w, live)
    scored = []
    for cell in sorted(by_cell):
        foods = by_cell[cell]
        if len(foods) >= MIN_BELIEVERS:
            scored.append((float(np.std(foods)) * len(foods), cell))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [c for _s, c in scored[:K_CONTESTED]]


def factions(w, live):
    """Group agents by their binned stance on the contested cells. A faction = a
    set of agents whose believed food on every contested cell falls in the same
    EPS_FOOD bin (missing opinions imputed to the cell's median belief, so the
    clustering keys on genuine disagreement, not on who happens to know what). A
    fixed, RNG-free agglomeration; we report the count of factions (≥2 members),
    the largest faction, and its share of clustered agents (consensus strength)."""
    cells = _contested_cells(w, live)
    if not cells:
        return {"n": 0, "largest": 0, "share": 0.0, "clustered": 0, "cells": cells}

    by_cell = _beliefs_by_cell(w, live)
    median = {c: float(np.median(by_cell[c])) for c in cells}

    groups = defaultdict(int)
    clustered = 0
    for oid in live:
        mem = w.mem.get(oid, {})
        if not any(c in mem for c in cells):       # no stance on any axis -> skip
            continue
        clustered += 1
        sig = tuple(int(round((mem[c][0] if c in mem else median[c]) / EPS_FOOD))
                    for c in cells)
        groups[sig] += 1

    sizes = sorted(groups.values(), reverse=True)
    n_factions = sum(1 for s in sizes if s >= 2)
    largest = sizes[0] if sizes else 0
    return {"n": n_factions, "largest": largest,
            "share": (largest / clustered if clustered else 0.0),
            "clustered": clustered, "cells": cells}


# --------------------------------------------------------------------------- #
#  3. Propagation (claim reach) — straight from the log                        #
# --------------------------------------------------------------------------- #
def propagation(log):
    """Reach of claims, log-only. Immediate = listeners exposed by a claim
    (`heard_by`). Windowed = listener-exposures about the same cell within
    PROP_WINDOW think-days (an exposure count; without listener ids in the log it
    over-counts repeats, so it is labelled as exposure, not distinct agents)."""
    comms = [e for e in log.events if e.kind == "communication"]
    if not comms:
        return {"n": 0, "immediate": 0.0, "windowed": 0.0}

    # index claims about each cell by day for the windowed sum
    by_cell_day = defaultdict(list)
    for e in comms:
        by_cell_day[tuple(e.data["cell"])].append((e.t, e.data["heard_by"]))

    span = PROP_WINDOW * THINK_EVERY
    immediate, windowed = [], []
    for e in comms:
        immediate.append(e.data["heard_by"])
        cell = tuple(e.data["cell"])
        windowed.append(sum(hb for (t2, hb) in by_cell_day[cell]
                            if e.t <= t2 <= e.t + span))
    return {"n": len(comms),
            "immediate": float(np.mean(immediate)),
            "windowed": float(np.mean(windowed))}


# --------------------------------------------------------------------------- #
#  4. Rationale-vs-outcome (aggregate, mock-strategic)                         #
# --------------------------------------------------------------------------- #
def rationale_outcome(w, log):
    comms = [e for e in log.events if e.kind == "communication"]
    if not comms:
        return None
    lies = [e for e in comms if not e.data.get("truthful", True)]
    trues = [e for e in comms if e.data.get("truthful", True)]
    eli, aud = w.speaker_report(), w.listener_report()
    return {"lie_frac": len(lies) / len(comms),
            "n": len(comms),
            "heard_lie": float(np.mean([e.data["heard_by"] for e in lies])) if lies else 0.0,
            "heard_true": float(np.mean([e.data["heard_by"] for e in trues])) if trues else 0.0,
            "elite_body": eli["body"], "aud_body": aud["body"],
            "gap": eli["body"] - aud["body"]}


# --------------------------------------------------------------------------- #
#  5. Deception modes — separate "soft" puffery from "hard" diversion          #
# --------------------------------------------------------------------------- #
def classify_claim(claim_food, true_food):
    """Classify ONE claim as 'truthful' | 'soft' | 'hard', returning also the signed
    error `e = claim - true` (kg) and the relative over-claim `r = e/max(true, eps)`.

    The three classes PARTITION every claim:
      * truthful — `|e| <= TOL_ABS` (includes the old exact-match notion, |e|≈0);
      * soft (puffery) — a positive, small RELATIVE inflation of a real cell
        (`e > TOL_ABS` and `r <= R_SOFT`): the cell is genuine, the number is padded
        (the qwen3:14b cohort's habit: real 7.82 -> claim 8.0);
      * hard (diversion/substitution) — everything else: gross over-claim
        (`r > R_SOFT`, e.g. crying OASIS_CAP at a desert decoy) or an under-claim
        (`e < -TOL_ABS`, understating a real cell to push rivals off it)."""
    e = claim_food - true_food
    if abs(e) <= TOL_ABS:
        return "truthful", e, 0.0
    r = e / max(true_food, EPS_DM)
    if e > 0 and r <= R_SOFT:
        return "soft", e, r
    return "hard", e, r


def deception_modes(log):
    """Soft-vs-hard deception breakdown over a run's `communication` events. Pure,
    deterministic, log-only — works on ANY `EventLog` (a scripted/mock run here, or a
    live cohort log loaded from JSONL). The three shares partition to 1.0."""
    comms = [ev for ev in log.events if ev.kind == "communication"]
    n = len(comms)
    counts = {"truthful": 0, "soft": 0, "hard": 0}
    r_lies = []                                  # relative over-claim, lies vs REAL cells
    abs_e = {"soft": [], "hard": []}             # |e| (kg) per lie class
    for ev in comms:
        cf = float(ev.data["claim_food"])
        tf = float(ev.data["true_food"])
        mode, e, r = classify_claim(cf, tf)
        counts[mode] += 1
        if mode != "truthful":
            abs_e[mode].append(abs(e))
            # relative over-claim is only defined against a cell with real food; a
            # hard lie that cries food at an empty/decayed cell (true≈0) is pure
            # fabrication, not a "relative" inflation, and would blow the mean up via
            # the eps guard — so it is measured in kg (above), not folded in here.
            if tf > TOL_ABS:
                r_lies.append(r)

    def share(k):
        return counts[k] / n if n else 0.0

    def mean(xs):
        return float(np.mean(xs)) if xs else 0.0

    return {"n": n,
            "truthful": counts["truthful"], "soft": counts["soft"],
            "hard": counts["hard"],
            "truthful_share": share("truthful"), "soft_share": share("soft"),
            "hard_share": share("hard"),
            "mean_r_lies": mean(r_lies),
            "mean_abs_e_soft": mean(abs_e["soft"]),
            "mean_abs_e_hard": mean(abs_e["hard"])}


# --------------------------------------------------------------------------- #
#  Compute everything + a fingerprint for the determinism self-check           #
# --------------------------------------------------------------------------- #
def compute_all():
    runs = build_runs()
    out = {}
    for r in REGIMES:
        w, log = runs[r]
        live = _live_oids(w)
        out[r] = {"live": len(live),
                  "pol": polarization(w, live),
                  "fac": factions(w, live),
                  "prop": propagation(log),
                  "dec": deception_modes(log)}
    out["mock-strategic"]["rat"] = rationale_outcome(*runs["mock-strategic"])
    return out


def fingerprint(results):
    """Stable hash over every reported number (rounded), so two computations can be
    compared byte-for-byte regardless of float-formatting noise."""
    h = hashlib.sha256()
    for r in REGIMES:
        d = results[r]
        h.update(f"{r}|live{d['live']}".encode())
        h.update(f"pol{d['pol']['wstd']:.6f}/{d['pol']['cells']}".encode())
        f = d["fac"]
        h.update(f"fac{f['n']}/{f['largest']}/{f['share']:.6f}/{f['clustered']}".encode())
        h.update((";".join(f"{c}" for c in f["cells"])).encode())
        p = d["prop"]
        h.update(f"prop{p['n']}/{p['immediate']:.6f}/{p['windowed']:.6f}".encode())
        dm = d["dec"]
        h.update(f"dec{dm['n']}/{dm['truthful']}/{dm['soft']}/{dm['hard']}/"
                 f"{dm['mean_r_lies']:.6f}/{dm['mean_abs_e_soft']:.6f}/"
                 f"{dm['mean_abs_e_hard']:.6f}".encode())
        if "rat" in d and d["rat"] is not None:
            t = d["rat"]
            h.update(f"rat{t['lie_frac']:.6f}/{t['n']}/{t['heard_lie']:.6f}/"
                     f"{t['heard_true']:.6f}/{t['gap']:.6f}".encode())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
def main():
    line = "=" * 78
    print(line)
    print("POLARIZATION & FACTIONS — empirical elite-theory metrics")
    print("No new dynamics: only measuring the divergent subjective memories that")
    print("sim_comm / sim_comm_llm already produce. Deterministic from seed.")
    print(line)

    res = compute_all()

    cols = REGIMES
    print()
    print(f"{'metric':<32}" + "".join(f"{c:>15}" for c in cols))
    print("-" * (32 + 15 * len(cols)))

    def row(label, fn, fmt="{:.3f}"):
        cells = []
        for c in cols:
            v = fn(res[c])
            cells.append("—" if v is None else fmt.format(v))
        print(f"{label:<32}" + "".join(f"{x:>15}" for x in cells))

    print("BELIEF POLARIZATION")
    row("  weighted belief-std (kg)", lambda d: d["pol"]["wstd"])
    row("  cells with ≥2 believers", lambda d: d["pol"]["cells"], "{:d}")
    print("FACTIONS (binned stance on contested cells)")
    row("  factions (≥2 members)", lambda d: d["fac"]["n"], "{:d}")
    row("  largest faction", lambda d: d["fac"]["largest"], "{:d}")
    row("  consensus share (largest)", lambda d: d["fac"]["share"])
    print("PROPAGATION (claim reach, from log)")
    row("  claims logged", lambda d: d["prop"]["n"], "{:d}")
    row("  mean listeners / claim", lambda d: d["prop"]["immediate"])
    row(f"  exposure within {PROP_WINDOW} think-days", lambda d: d["prop"]["windowed"])
    print(f"DECEPTION MODES (truthful≤{TOL_ABS:g}kg · soft puffery r≤{R_SOFT:g} · "
          f"hard diversion)")
    row("  truthful share", lambda d: d["dec"]["truthful_share"])
    row("  soft-lie share (puffery)", lambda d: d["dec"]["soft_share"])
    row("  hard-lie share (diversion)", lambda d: d["dec"]["hard_share"])
    row("  mean rel over-claim (vs real)", lambda d: d["dec"]["mean_r_lies"])
    row("  mean |err| soft (kg)", lambda d: d["dec"]["mean_abs_e_soft"])
    row("  mean |err| hard (kg)", lambda d: d["dec"]["mean_abs_e_hard"])

    # the three shares partition every claim -> they must sum to 1 per regime
    for r in REGIMES:
        dm = res[r]["dec"]
        if dm["n"]:
            s = dm["truthful_share"] + dm["soft_share"] + dm["hard_share"]
            assert abs(s - 1.0) < 1e-9, f"{r}: deception modes do not partition ({s})"
            assert dm["truthful"] + dm["soft"] + dm["hard"] == dm["n"], \
                f"{r}: deception-mode counts do not sum to n"

    rat = res["mock-strategic"]["rat"]
    print("\nRATIONALE vs OUTCOME (mock-strategic, whole run)")
    print(f"  deceptive-claim share        : {rat['lie_frac']:.3f} of {rat['n']} claims")
    print(f"  mean listeners — lie vs true : {rat['heard_lie']:.2f}  vs  {rat['heard_true']:.2f}")
    print(f"  realized elite−audience body : {rat['elite_body']:.3f} − {rat['aud_body']:.3f}"
          f" = {rat['gap']:+.3f} kg (the gap the lies bought)")

    fp = fingerprint(res)
    print(f"\nmetric fingerprint: {fp}")

    # --- determinism self-check: recompute the whole set, demand byte-equality - #
    fp2 = fingerprint(compute_all())
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp == fp2 else 'MISMATCH ✗'}")
    assert fp == fp2, "polarization metrics are not reproducible across runs"

    # --- the takeaway, in numbers -------------------------------------------- #
    pn, pd_, pdec, pms = (res[r]["pol"]["wstd"] for r in REGIMES)
    fn, fh, fdec, fms = (res[r]["fac"]["n"] for r in REGIMES)
    print(f"\n{line}")
    print(f"deception polarizes belief ({pn:.1f}→{pdec:.1f} kg none→deceptive, "
          f"{pms:.1f} under emergent lying) and multiplies factions "
          f"({fn}→{fdec}, {fms} strategic): diverging subjective memories are a")
    print("measurable substrate for politics — no faction was injected from "
          "outside. deterministic from seed 7  ✓")


if __name__ == "__main__":
    main()
