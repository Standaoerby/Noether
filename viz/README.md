# viz/ — provable snapshot capture (PR-1, β-core)

A **read-only** visual layer over the Noether canon. It never touches `Code/`: it imports the
world classes, runs them unchanged, and reads state off a live world into JSON-round-trippable
frames. A snapshot is only written after four gates prove it reflects the *measured* run.

## Files

- **`schema.py`** — `SnapFrame` + `frame_from_world` / `frames_to_jsonl` / `frames_from_jsonl` /
  `meta`. `frame_from_world` is pure (mutates nothing). `body`/`gene` are stored in the canon's
  `.9f` format so the snapshot is byte-compatible with what `state_fingerprint` hashes; no numpy
  types reach JSON (everything cast to `float`/`int`).
- **`capture.py`** — the `WORLDS` registry (one line per world) + `capture()`.

## Run

```bash
python viz/capture.py appropriation headline     # rho=0.5 claim, box6 — the stratum
python viz/capture.py appropriation baseline     # rho=0   claim, box6 — the control
python viz/capture.py appropriation headline 5   # every 5th tick
```

Frames are labelled by the **true sim-day** (`ws.t`, 1…300), not a loop index. `headline`
(ρ=0.5) and `baseline` (ρ=0) share arena/seed — a born-together pair the Phase-3 front can
overlay synchronously (stratum vs no-stratum on identical geometry).

## Serve (PR-2 — read-only run registry)

```bash
cd viz
uvicorn server:app --port 8000     # scans runs/*.snap.jsonl at startup
```

The backend is **fully decoupled**: it does not import `Code/` and never calls the sim — it
works only over `runs/*.snap.jsonl` + paired `*.meta.json`. `final_ownership` is recomputed
from the last frame by arithmetic (owner_ids + agent bodies), never via `ownership_metrics`.

Endpoints: `GET /health` · `GET /runs` · `GET /{run}/meta` · `GET /{run}/frame/{t}` (404 out
of range) · `GET /{run}/frames?t0=&t1=&stride=` · `GET /` (stub for the PR-3 viewer). CORS is
open to `localhost:*`. Regenerate `runs/` with `capture.py` before serving (runs/ is
git-ignored).

Note: `baseline` (claim, ρ=0) forms **no** ownership ledger at all (`_do_claims` runs only
when ρ>0), so its `owner_share` is `0.0` and `owner_gap` is `null` — a cleaner "no stratum"
control than a fair-share baseline, and the sharp contrast against headline's 0.463.

## Acceptance (what you see before merge — any ✗ ⇒ do not merge)

```
B0 gate       : <fp> vs a91480561b6de937  -> BYTE-IDENTICAL ✓   (appropriated_total==0.0)
reproducibility: <fp> == <fp>              -> BIT-IDENTICAL ✓
snapshot-safe : <fp_snap> == <fp_clean>    -> BIT-IDENTICAL ✓    <- snapshot did not perturb the run
captured      : N frames -> viz/runs/appropriation_headline.snap.jsonl
```

The **snapshot-safe** gate is the load-bearing one: `appropriation_fingerprint` of the snapped
world equals that of a clean headline run, so reading frames mid-run changed nothing. The viewer
therefore renders exactly the trajectory the conservation kernel signed.

## Output

`runs/` (git-ignored — snapshots are reproducible artifacts):
- `<name>_<config>.snap.jsonl` — one JSON frame per line.
- `<name>_<config>.meta.json` — grid, horizon, oases, seed (for the PR-2 viewer).

## Extending

Add a world by appending one entry to `WORLDS` in `capture.py`: its `run` function, its
`fp` (fingerprint), a `B0` off-config + `B0_anchor`, and a `headline` config.

## Deps

`fastapi`, `uvicorn` (for the PR-2 web viewer only). `numpy` is already a canon dependency.
Capture itself needs nothing beyond the canon.
