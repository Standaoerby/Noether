# Noether

**A conserved-substrate colony sim — "RimWorld, next level", built bottom-up from the laws of conservation.**

The thesis: lay down an honest substrate first — mass and energy that never appear or vanish — and let everything grow on top of it: ecology → evolution → **information** → mind → **politics**. Named after Noether's theorem: conservation ↔ symmetry. Every emergent phenomenon higher up is only trusted because the layer beneath it forges nothing.

Three promises hold at **every** layer:

1. **Conservation** — mass / energy-across-boundary / body-in-soil / monotone entropy (as appropriate to the layer).
2. **Determinism** — two runs are byte-identical ⇒ the whole history is reproducible and replayable.
3. **Depth = richness-of-consequences per unit representation** — nothing is modelled that has no demonstrable consequence.

The project is also an empirical testbed for a book on elite theory (*Theoria Elitis*): every political claim is pre-registered (both the positive and the NULL outcome written **before** the run), and findings are labelled a **conditional trophy 🔖**, an **informative NULL**, or a **split verdict** — the simulation is allowed to overrule the hypothesis.

## The tower (Code/ — the conserved core, canon)

Ten modules, bottom to top. Each is **self-verifying**: its demo ends in `assert`s on the invariants it owns and prints a success marker. `Code/verify_all.py` runs the whole family twice (conservation + byte-determinism) and prints `ALL MODULES PASS — the tower stands as a whole`.

| # | module | guarantees | key numbers | sec |
|---|--------|------------|-------------|-----|
| 1 | `sim_core` | mass ==, energy == (thermal+chemical) | mass drift 0, energy 2.98e-8 J | 0.1 |
| 2 | `sim_ecology` | boundary flux + entropy (E−E0 == in−out, S↑) | energy err 2.67e-5 J, exported 113 MJ/K | 0.2 |
| 3 | `sim_genetics` | information accrues on a closed matter loop | bits = log2(σ0/σ); matter 9.3e-10 | 0.4 |
| 4 | `sim_world` | full synthesis on one patch (4 invariants) | mass 4.7e-10, energy 0.79 J, body/parcel 0, S 259672 MJ/K | 2.8 |
| 5 | `sim_space` | space: clines, range shift, refugium | E_rel ~1e-14; cline corr → 0.99 | 10.2 |
| 6 | `sim_traits` | two genes: temp_opt + size (Bergmann) | final sCorr −0.669 | 23.4 |
| 7 | `sim_pareto` | explicit Pareto front + domination | mean(H·C)=1.0000±6.7e-17; Bergmann −0.914; 94% scrambled dominated | 18.5 |
| 8 | `sim_portfolio` | portfolio effect (variance-averaging) | indep buffer 3.8×, sync 1.0×; sqrt-law gap ≤2.2% | 1.3 |
| 9 | `sim_eventlog` | universal event log (faithful, queryable) | matter 0.0; log replays the sim exactly; 18510 events | 2.9 |
| 10 | `sim_stage2` | a mind inside a pawn (typed, conserved, replayable) | matter ~1e-12; replay bit-identical; ON/OFF: mismatch 2.21→0.86 K, pop 31→102 | 2.3 |

Beyond the base ten, `Code/` carries the **property arc** (appropriation, institution, inheritance, exclusion, trade, synthesis, legitimacy-probe) — the modules that measured *control through ownership*. The headline of that arc: **there is no super-additive concentration — tyranny is not emergent from summing institutions; power is a gradient, not a phase transition** (`Code/sim_*` + [`docs/module-tower.md`](docs/module-tower.md)). The canon subtree is fingerprint-anchored and never edited by later work.

## The cognition layer

`sim_stage2` seats a *mind* inside a pawn without giving it any power it should not have. The mind only **proposes** a typed action; the substrate **disposes** (validates against a legal menu, executes on the conserved grid). Every decision is logged as a `cognition` event and the world replays **bit-for-bit** from that log alone — so reproducibility survives even a nondeterministic LLM. Same seed, cognition **ON vs OFF**: the focal lineage grows 31 → 102, biomass 10.6 → 41.4 kg, mean thermal mismatch halves 2.21 → 0.86 K, matter drift ~1e-12 kg. The mind is a *measurable delta*. Design: [`docs/cognition-9-principles.md`](docs/cognition-9-principles.md).

## Stage-3 — the political column (`stage3/`)

A Polis layer built **on top of** the frozen tower (canon `Code/` is never touched; every seam lives in `stage3/`, gated OFF by default so anchors hold). It carries the **intent layer** (mod G — a mind proposes typed verbs over the artifact physics) and **G2: control *without* ownership** — the verbs a property model cannot express. Each finding is pre-registered and independently git-audited (trees + blobs read straight from `.git`, "verify, don't trust").

**Measured so far (control without ownership):**

- **EXTORT** (illegitimate seizure in a guard's shadow): a stratum is built by **selection, not by right** — under predator-selection the extortionist class holds ~1.5× its share; presence still rules the shadow (rare guards never suppress recidivism).
- **DELEGATE / REVOKE** (power as a meta-resource — control of a flow you don't own): the "iron law" hole **opens through reputation** — a mark-ledger conducts ~92% of the god-tier flow with no substrate cheat. But the hole is **bounded**: from below by the body (a conserved substrate has no off-body vault, so flow re-condenses into a reserve — a body-poor apex fills up to a rich owner's level), and from above by depth (a chain past one link manufactures a **middle-management stratum** rather than enriching the apex; the root's take decays ~m per level). *Conductivity of power exists; super-conductivity does not.*
- **Compliance & the Laffer curve**: reputational conductivity scales with the compliant base, and extraction has an **optimal, not maximal, rate** — full god-tier draining strangles the pie ~11×; the apparatus starves productivity, not people.
- **Reputation × EXTORT — a split verdict**: victim testimony drives individual recidivism to **exactly 1.00** offence per extortionist (perfect, guard-independent deterrence), yet aggregate crime does **not** fall — the offender pool triples. Crime is **structural**: an unguarded cell is an opportunity someone always takes; reputation individualises the offence without abolishing it.

Long-horizon audit (`stage3/run_longrun.py`, T=3000, all worlds): **no heat-death** — the recycle substrate (dead body → soil → plant) keeps every world alive to the horizon; numerical drift is flat (7.28e-12). The audit is read-only and catalogs degeneracies in [`stage3/LONGRUN_AUDIT.md`](stage3/LONGRUN_AUDIT.md).

## Visualization — "Glass Polis" (`viz/`)

A read-only lens over the sim (the canon is never touched; fingerprint-gated). It renders the **layers of power** that the ownership axis is blind to — meta-tribute pulsing toward an absent root, extortion flashes, the reputation mark, the guard's shadow, denied-intent loci — plus event **aggregation** (~47× compression) and a **split-screen** for side-by-side runs. The cover figure: two worlds, one substrate, one tick — **Gini nearly equal (0.452 vs 0.494) while population diverges 639 vs 212 and power 0.00 vs 0.74**. Inequality-of-stock and conductivity-of-power are different axes; looking only at the first misses the hole entirely. See [`viz/glass/README.md`](viz/glass/README.md).

## Figures

![Pareto front](figures/pareto_front.png)

![Portfolio effect](figures/portfolio_effect.png)

## Quickstart

```bash
pip install -r requirements.txt          # numpy, matplotlib (dev); reproducible env: requirements-lock.txt

python3 Code/verify_all.py               # default = the canonical set (the tower + the stage3 smoke)
python3 Code/verify_all.py --suite all   # the WHOLE Noether claim: canon tower + the stage3 column
python3 Code/sim_stage2.py               # cognition layer: ON/OFF, conservation, replay
```

### Test suites (`--suite`)

`verify_all.py` runs a named set of runners twice and checks conservation + determinism. **`--suite all` is the real green light — "the tower is green" is not "Noether is green".**

| suite | what it runs | when |
|---|---|---|
| *(no arg)* / `canonical` | the closed tower + probes + the `run_polis` / `run_polis_llm` smoke | the prior default; byte-identical output |
| `fast` | tower conservation core + a `run_polis` smoke (<~5 min) | CI on every PR/push |
| `stage3` | the stage3 column gate runners (F/G/G2 vitki, H/H2/H2bis/H3, glass, GC-identity, D/E) | before merging stage3 work |
| `all` | `canonical` + `stage3` — **the whole claim** | nightly / before a release |
| `longrun` | the T=3000 degeneracy audit | heavy, local-only, on demand |
| `llm-offline` | the LLM-tier modules (inert without a key) | when touching the mind layer |

Stage-3 experiments also run standalone, e.g. `python3 stage3/run_artifact_g2v2.py`. The Glass Polis viewer: build a data pack with `stage3/viz_export.py` (see [`viz/glass/README.md`](viz/glass/README.md) for presets — the exporter defaults to a 6×6 arena; pass `--arena none` for the full field), then serve `viz/glass/`. Each module writes its artifact next to itself; regenerated files and data packs are git-ignored.

## Reproducibility — semantic vs bitwise

Two levels, and they are not the same promise:

- **Bitwise (bit-for-bit):** the `state_fingerprint` anchors and byte-identical stdout hold **only inside the locked environment** — **Python 3.13.4, NumPy 2.2.6, Windows 11** ([`requirements-lock.txt`](requirements-lock.txt)). This is what the `MG*/MH*/anchor` gates assert.
- **Semantic:** on any other Python / NumPy / OS, the **conservation invariants and the scientific findings** still hold; the exact fingerprints may drift by float rounding. `requirements.txt` keeps `numpy>=1.26` for convenience, but the anchors are recorded against the exact pin above — so `>=` never contradicts the bit-for-bit claim: the claim is simply scoped to the lock.

**Two levels of proof (S2).** Editable stage3 runners emit a machine-readable result with `--json` → `results/<runner>.result.json` (deterministic on a commit; git-ignored): a **`state_hash`** (the world's `state_fingerprint()` — the substrate is identical) and an **`event_hash`** (the same history was produced). Canon `sim_*` modules are not editable and keep the legacy **stdout-SHA256**, which only proves *"the program printed the same bytes twice"* — strictly weaker. `nightly.yml` uploads `results/*.json` as a build artifact.

## Repository layout

```
Code/        the conserved tower + property arc + verify_all.py  (canon — fingerprint-anchored)
stage3/      the Polis political column: intent layer, G2 verbs, runners, longrun audit
viz/         Glass Polis — read-only visualization, aggregation, split-screen
docs/        design notes (module tower, the 9 cognition principles, reversibility,
             conservation invariants, LLM tiers, Theoria Elitis threads, artifacts)
figures/     committed documentation figures (regenerable from Code/)
WO_*.md      work orders — the historical record of each session's task
CLAUDE.md    primer for Claude Code (the executor) — read this before working
STAGE3_constitution.md   the Polis-layer design contract
CHANGELOG.md
```

## Working canon

- Code lives here; the long-form thinking / working memory lives in an Obsidian vault (`Noether/`). When in doubt: **code → this repo, design notes → both** (this repo's `docs/` is the published mirror).
- Workflow: **Claude Code opens PRs, Stan merges.** Feature branch → PR → review → merge. `verify_all.py` is the gate — never merge red. New modules must be self-verifying and added to `verify_all.py`. Post-merge cleanup is scripted (`post-merge.ps1`): pull only on `main`, and a branch is deleted only once its **tree** is found in `main`'s history (a squash-safe delivery test).
- The canon `Code/sim_*.py` is immutable; all new work lives in `stage3/` or `viz/`, defaults OFF, guarded by fingerprint anchors so no prior result silently regresses.
- See [`CLAUDE.md`](CLAUDE.md) for conventions and [`STAGE3_constitution.md`](STAGE3_constitution.md) for the Polis-layer contract.

## License

TBD. (No license file yet — set one before any external use.)
