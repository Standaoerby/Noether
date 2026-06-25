# Changelog

## 2026-06-24 — communication-events layer

Added `sim_comm` — communication events: belief spreads, and can be shaped. The tower is now **11 modules**, all green under `verify_all.py` (conservation + byte-determinism). Realizes cognition principle 7 (communication is events too).

- **`sim_comm.py`** (new): standalone `CommWorld` on its own `14×14` grid with **moving oases** (food relocates every 40 days; capacity-only relocation never teleports biomass; fade capped by `DECAY_FRAC` so an oasis decays rather than collapses). A tagged ~1/4 of pawns are **speakers** who broadcast a claim about a *remote* cell to co-located **listeners**; everyone navigates by belief via `ForagerMind`. Claims are `communication` events; moves are `cognition` events. Three regimes on one seed — `none` / `honest` (point to a real oasis) / `deceptive` (lure to a known-poor decoy claimed maximally rich). A message moves no matter and exerts no force: it only reshapes receivers' beliefs.
  - Result (seed 7, 300 days): **deception is strongly extractive.** Audience (listeners) collapses none→deceptive 2332→1080, biomass 799→267 kg, mean body 0.343→0.247 (starving), belief-error 0.0→142.7 kg; the informed **elite** (speakers) captures the spoils 544→830, biomass 154→287 kg, mean body 0.282→0.345 (well-fed). **Honest ≈ none** in aggregate (food is rivalrous, `eat ≤ avail/n`, so truth relocates the crowd but does not raise the aggregate harvest — a public good competed away). Matter drift ~1e-12 kg per regime; deceptive run replay bit-identical across 9447 communication events.
  - **Determinism fix**: oasis placement now seeds its RNG from a pure-integer expression, not Python's process-salted `hash()` of a string/tuple, so two separate processes agree — required for `verify_all`'s cross-process byte-determinism check (verified identical under `PYTHONHASHSEED` 0/1/999).
- **`verify_all.py`**: extended to 11 modules; `sim_comm` registered (conservation + cross-process determinism). Reuses `Animal`/`EventLog` from `sim_eventlog` and `DIRS`/`Decision`/`ActionAdapter` from `sim_stage2`; defines its own grid-sized `legal_dirs` (the tower's 5×5 modules are untouched).
- **Docs**: new [`docs/communication-events.md`](docs/communication-events.md) (design + the asymmetric finding); [`docs/theoria-elitis-threads.md`](docs/theoria-elitis-threads.md) updated — the rhetoric/capture thread is now empirical: honest signal about a shared resource is a public good competed away; a lie is an extraction technology that transfers rivalrous resources to whoever controls the narrative. 🔖

## 2026-06-24 — stage-2 cognition layer

Added `sim_stage2` — a mind inside a pawn, on the conserved world. The tower is now **10 modules**, all green under `verify_all.py` (conservation + byte-determinism).

- **`sim_stage2.py`** (new): `MindWorld(MicroWorld)` routes the focal lineage's migration through a `Mind`. Classes `Mind` / `RuleMind` / `MockMind` / `ReplayMind` / `LLMMind` (inert in CI), plus `ActionAdapter` (mind proposes, physics disposes) and `Scheduler` (tiers + slow clock). All nine cognition principles realized; action space = migration direction only. Every decision logged as a `cognition` event; `ReplayMind` rebuilds the world bit-for-bit from the log.
  - Result (seed 7, 360 days, think-every 10): cognition ON vs OFF on the same seed — focal lineage 31 → 102, biomass 10.6 → 41.4 kg, mean thermal mismatch 2.21 → 0.86 K; matter drift ~1e-12 kg; replay fingerprint bit-identical across 2858 cognition events.
- **`verify_all.py`**: extended to 10 modules; `sim_stage2` registered with conservation + replay asserts.
- **Portability fix**: `sim_eventlog`, `sim_pareto`, `sim_portfolio` now write their artifact next to the script (`os.path.dirname(__file__)`) instead of a hardcoded sandbox path, so `verify_all` is green on any machine. Regenerated `*.png` / `*.jsonl` are git-ignored.
- **Docs**: model recommendation for the cognition layer updated to **Qwen3.6-35B-A3B** (MoE, local/cohort tier via vLLM) from the earlier Qwen3-30B-A3B; focal tier unchanged (Claude Sonnet/Opus). See `docs/llm-tiers-and-model-choice.md`.

## Baseline — the tower (prior work)

`sim_core` → `sim_ecology` → `sim_genetics` → `sim_world` → `sim_space` → `sim_traits` → `sim_pareto` → `sim_portfolio` → `sim_eventlog`: conservation kernel up through a faithful, queryable universal event log, with figures for the Pareto front and the portfolio (variance-averaging) effect. All self-verifying. See `docs/module-tower.md`.
