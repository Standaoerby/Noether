# Changelog

## 2026-06-24 — stage-2 cognition layer

Added `sim_stage2` — a mind inside a pawn, on the conserved world. The tower is now **10 modules**, all green under `verify_all.py` (conservation + byte-determinism).

- **`sim_stage2.py`** (new): `MindWorld(MicroWorld)` routes the focal lineage's migration through a `Mind`. Classes `Mind` / `RuleMind` / `MockMind` / `ReplayMind` / `LLMMind` (inert in CI), plus `ActionAdapter` (mind proposes, physics disposes) and `Scheduler` (tiers + slow clock). All nine cognition principles realized; action space = migration direction only. Every decision logged as a `cognition` event; `ReplayMind` rebuilds the world bit-for-bit from the log.
  - Result (seed 7, 360 days, think-every 10): cognition ON vs OFF on the same seed — focal lineage 31 → 102, biomass 10.6 → 41.4 kg, mean thermal mismatch 2.21 → 0.86 K; matter drift ~1e-12 kg; replay fingerprint bit-identical across 2858 cognition events.
- **`verify_all.py`**: extended to 10 modules; `sim_stage2` registered with conservation + replay asserts.
- **Portability fix**: `sim_eventlog`, `sim_pareto`, `sim_portfolio` now write their artifact next to the script (`os.path.dirname(__file__)`) instead of a hardcoded sandbox path, so `verify_all` is green on any machine. Regenerated `*.png` / `*.jsonl` are git-ignored.
- **Docs**: model recommendation for the cognition layer updated to **Qwen3.6-35B-A3B** (MoE, local/cohort tier via vLLM) from the earlier Qwen3-30B-A3B; focal tier unchanged (Claude Sonnet/Opus). See `docs/llm-tiers-and-model-choice.md`.

## Baseline — the tower (prior work)

`sim_core` → `sim_ecology` → `sim_genetics` → `sim_world` → `sim_space` → `sim_traits` → `sim_pareto` → `sim_portfolio` → `sim_eventlog`: conservation kernel up through a faithful, queryable universal event log, with figures for the Pareto front and the portfolio (variance-averaging) effect. All self-verifying. See `docs/module-tower.md`.
