"""game_gates.py — Этап 0 gate harness for the game bridge.

Verifies the two gates that DON'T need Godot or a live башня run:

  GAME-DET   (seed + commands.jsonl) replays the core bit-for-bit. We drive a
             GameSession headless for N ticks, capture the per-tick state_hash
             sequence, then replay from the recorded seed + commands.jsonl and
             assert an identical sequence. Uses the same GameSession code path
             the socket server uses, so what the player saw is what replays.

  GAME-PROTO the handshake rejects a mismatched MAJOR protocol version. We spin
             up a real GameServer on an ephemeral port, send a bad hello, and
             assert the server answers `error/protocol_mismatch` and closes.

GAME-OFF is verified separately by the untouched `py Code/verify_all.py`
(башня byte-identical whether or not this server ever runs).

Run:  py stage3/game_gates.py        (from repo root; exits non-zero on failure)
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import socket
import tempfile
import threading

from stage3.gameserver import (GameSession, GameServer, PROTOCOL_VERSION,
                               DEFAULT_HOST)

N_TICKS = 200
SEED = 7


def _read_seed(session_dir: str) -> int:
    with open(os.path.join(session_dir, "manifest.json"), encoding="utf-8") as f:
        return int(json.load(f)["seed"])


def _read_commands(session_dir: str) -> list[dict]:
    path = os.path.join(session_dir, "commands.jsonl")
    out: list[dict] = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _hash_seq(session: GameSession, n: int, commands_by_tick: dict) -> list[str]:
    """Run n ticks, applying any world-commands scheduled at each boundary,
    returning the per-tick state_hash sequence."""
    seq: list[str] = []
    for _ in range(n):
        boundary = commands_by_tick.get(session.world.t, [])
        snap, _ev = session.step(boundary)
        seq.append(snap["meta"]["state_hash"])
    return seq


def gate_det() -> bool:
    root = tempfile.mkdtemp(prefix="game_det_")
    # --- live run: record seed + commands.jsonl + hash sequence -------------- #
    live = GameSession(seed=SEED, session_id="live", runs_dir=root)
    live_seq = _hash_seq(live, N_TICKS, {})     # Stage 0: no world commands sent
    live.close()

    # --- replay: reconstruct purely from recorded artifacts ------------------ #
    live_dir = live.dir
    seed = _read_seed(live_dir)
    cmds = _read_commands(live_dir)
    by_tick: dict = {}
    for entry in cmds:
        by_tick.setdefault(int(entry["tick"]), []).append(entry["cmd"])

    replay = GameSession(seed=seed, session_id="replay", runs_dir=root)
    replay_seq = _hash_seq(replay, N_TICKS, by_tick)
    replay.close()

    ok = live_seq == replay_seq
    print(f"[GAME-DET] {'PASS' if ok else 'FAIL'} — {N_TICKS} ticks, "
          f"seed={seed}, commands={len(cmds)}, "
          f"final_hash={live_seq[-1]}")
    if not ok:
        first = next(i for i in range(len(live_seq))
                     if live_seq[i] != replay_seq[i])
        print(f"           first divergence at tick index {first}: "
              f"{live_seq[first]} != {replay_seq[first]}")
    return ok


def gate_proto() -> bool:
    session = GameSession(seed=SEED, session_id="proto",
                          runs_dir=tempfile.mkdtemp(prefix="game_proto_"))
    server = GameServer(session, host=DEFAULT_HOST, port=0)

    # bind to an ephemeral port ourselves so the client knows where to dial
    srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv_sock.bind((DEFAULT_HOST, 0))
    srv_sock.listen(1)
    port = srv_sock.getsockname()[1]

    result: dict = {}

    def _run_server() -> None:
        conn, _addr = srv_sock.accept()
        try:
            ok = server._handshake(conn)      # exercises the real handshake path
            result["accepted"] = ok
        finally:
            conn.close()
            srv_sock.close()
            session.close()

    t = threading.Thread(target=_run_server, daemon=True)
    t.start()

    client = socket.create_connection((DEFAULT_HOST, port), timeout=5.0)
    bad_version = PROTOCOL_VERSION + 1
    client.sendall((json.dumps({
        "type": "hello", "protocol_version": bad_version,
        "client": "godot", "client_version": "test",
    }) + "\n").encode("utf-8"))
    reply_raw = client.recv(4096).decode("utf-8").strip()
    client.close()
    t.join(timeout=5.0)

    reply = json.loads(reply_raw) if reply_raw else {}
    ok = (reply.get("type") == "error"
          and reply.get("code") == "protocol_mismatch"
          and result.get("accepted") is False)
    print(f"[GAME-PROTO] {'PASS' if ok else 'FAIL'} — sent pv={bad_version}, "
          f"server replied {reply.get('type')}/{reply.get('code')}, "
          f"accepted={result.get('accepted')}")
    return ok


def gate_geom() -> bool:
    """GEOM (Stage 1, task 1.0): every living agent's (x,y) falls inside the
    reported grid, and deme == y*cols + x with no aliasing. Guards against the
    Stage-0 5x5 hardcode regressing (real substrate is 14x14)."""
    session = GameSession(seed=SEED, session_id="geom",
                          runs_dir=tempfile.mkdtemp(prefix="game_geom_"))
    out_of_grid = 0
    deme_bad = 0
    max_i = max_j = 0
    for _ in range(400):
        snap, _ev = session.step([])
        rows, cols = snap["meta"]["rows"], snap["meta"]["cols"]
        for a in snap["agents"]:
            max_i, max_j = max(max_i, a["y"]), max(max_j, a["x"])
            if not (0 <= a["x"] < cols and 0 <= a["y"] < rows):
                out_of_grid += 1
            if a["deme"] != a["y"] * cols + a["x"]:
                deme_bad += 1
    session.close()
    ok = out_of_grid == 0 and deme_bad == 0
    print(f"[GEOM] {'PASS' if ok else 'FAIL'} — grid {rows}x{cols}, "
          f"400 ticks, max(y,x)=({max_i},{max_j}), "
          f"out_of_grid={out_of_grid}, deme_mismatch={deme_bad}")
    return ok


def main() -> int:
    print("=" * 60)
    results = {"GAME-DET": gate_det(), "GAME-PROTO": gate_proto(),
               "GEOM": gate_geom()}
    print("=" * 60)
    all_ok = all(results.values())
    print(f"gates: {'ALL PASS' if all_ok else 'FAIL'} "
          f"({sum(results.values())}/{len(results)})")
    print("note: GAME-OFF is gated by `py Code/verify_all.py` (unchanged башня).")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
