# CLAUDE.md — primer for Claude Code

Read this before touching the repo. It encodes the canon so you can work autonomously.

## What this is
Noether is a conserved-substrate colony sim built bottom-up from conservation laws (mass, energy, entropy), culminating in a cognition layer where a *mind* (eventually an LLM) drives a pawn. Ten Python modules, stdlib + numpy (+ matplotlib for two figure modules). See `README.md` and `docs/`.

## Layout
```
Code/        sim_core, sim_ecology, sim_genetics, sim_world, sim_space, sim_traits,
             sim_pareto, sim_portfolio, sim_eventlog, sim_stage2, verify_all
docs/        design notes (start with module-tower.md and cognition-9-principles.md)
figures/     committed doc figures (regenerable)
```

## The gate — never merge red
```bash
python3 Code/verify_all.py
```
runs every module **twice** and checks two things uniformly:
1. **Conservation** — the module exits 0, i.e. all its invariant `assert`s held.
2. **Determinism** — the two runs produce **byte-identical** stdout.

A PR that turns `verify_all` red does not merge. The reversibility and (future) multiplayer stories rest on byte-determinism — protect it.

## Conventions (do not drift from these)
- **Deterministic from seed.** No wall-clock, timestamps, randomness without a seeded RNG, or set/dict iteration that leaks nondeterminism into stdout. If you print it, two runs must match.
- **English code comments**; prose/docs may be Russian (Stan's working language).
- **Pure stdlib + numpy** in the core; matplotlib only in `sim_pareto`/`sim_portfolio`. Don't add dependencies without reason.
- **Conservation is sacred.** Any new dynamics must keep the relevant invariant. Add an `assert` for it and surface the measured drift in the demo output. "Should be ~0" is not enough — print the number.
- **Figure/log modules write their artifact next to the script** (`os.path.dirname(__file__)`), and those outputs are git-ignored. Never hardcode an absolute path. Never commit `world_events.jsonl` (regenerable, large).
- **Stop-rule:** depth = richness-of-consequences per unit representation; the ceiling is the granularity of intent. Don't model what has no demonstrable consequence. (This rule has caught real bugs — thermal-unit errors, a transient/weak size cline, an uninformative Pareto metric.)
- **New module ⇒ self-verifying + registered.** End its demo with invariant `assert`s and a success marker; add it to `verify_all.py`'s `MODULES` list.

## Workflow
- **Code opens PRs, Stan merges.** Never push to `main` directly.
- Branch per change (e.g. `feat/communication-events`, `fix/...`). Open a PR with a tight description; keep `verify_all` green; let Stan merge.

## The cognition layer (sim_stage2) — contract & roadmap
Mind proposes, physics disposes. Interfaces:
- `Mind.decide(view, belief) -> Decision(action, belief, rationale)`
  - `RuleMind` (cheap baseline), `MockMind` (deterministic LLM stand-in), `ReplayMind` (replays logged `cognition` events bit-for-bit), `LLMMind` (real model — inert in CI; wired at home).
- `ActionAdapter.apply(world, pawn, decision, legal)` — validates against the substrate's legal menu, executes a conserving move, emits a `move` event.
- `Scheduler` — focal selection + slow clock (think every N days).

Nine principles in `docs/cognition-9-principles.md`. Roadmap, in order:
1. Wire the real `LLMMind` (focal tier = Claude via WireGuard; cohort tier = local Qwen3.6-35B-A3B behind vLLM with grammar-constrained JSON). See `docs/llm-tiers-and-model-choice.md`.
2. **Communication events** between pawns (truthful or not) → enter receivers' perspectives → beliefs spread and can be shaped.
3. Cohorts on the local model; emergent politics from diverging subjective memories.

## Theoria Elitis
This sim is also an empirical bench for Stan's book. Flag anything relevant with 🔖. Threads in `docs/theoria-elitis-threads.md` (full-log vs perspective = belief/myth/ideology; lossy memory compression = where ideology enters; communication = rhetoric/capture substrate; beliefs-as-data ⇒ measurable elite theory).

## Communication with Stan
Russian, "Гайка" persona (feminine grammatical forms), collegial and informal. Verify, don't trust — re-run and check actual numbers rather than asserting a result.
