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
python viz/capture.py                      # appropriation / headline, every tick
python viz/capture.py appropriation headline 5   # every 5th tick
```

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
