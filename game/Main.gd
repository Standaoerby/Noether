extends Node2D
## Orchestrator: builds Net/Arena/Hud, wires signals, owns the fixed-timestep
## accumulator that drives interpolation alpha, routes hotkeys and selection.
## It never touches game state beyond presentation bookkeeping.

const HOST := "127.0.0.1"
const PORT := 42017
const START_TPS := 2                # begin at 1x on connect (Space to pause)

var net: NetClient
var arena: Arena
var hud: Hud

var _tps := 0
var _last_speed_tps := START_TPS    # remembered for the Space toggle
var _accum := 0.0
var _agent_events: Dictionary = {}  # oid -> Array (last 5 events, from the stream)
var _selected_inspect: Dictionary = {}   # last inspect_result for the selected pawn
var _ping_nonce := 0


func _ready() -> void:
	arena = Arena.new()
	add_child(arena)
	net = NetClient.new()
	add_child(net)
	hud = Hud.new()
	add_child(hud)

	net.handshaked.connect(_on_handshaked)
	net.snapshot_received.connect(_on_snapshot)
	net.events_received.connect(_on_events)
	net.inspect_received.connect(_on_inspect_result)
	net.error_received.connect(_on_error)
	net.closed.connect(_on_closed)
	hud.pace_requested.connect(_set_pace)

	hud.set_status("connecting %s:%d…" % [HOST, PORT])
	net.connect_to_server(HOST, PORT)


func _process(delta: float) -> void:
	if _tps > 0:
		var dt := 1.0 / float(_tps)
		_accum += delta
		arena.alpha = clampf(_accum / dt, 0.0, 1.0)   # clamp = no extrapolation
	else:
		arena.alpha = 1.0                              # paused: rest on latest snapshot


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		var oid := arena.pick(arena.get_local_mouse_position())
		arena.selected_oid = oid
		if oid == -1:
			_selected_inspect = {}
			hud.hide_inspector()
		else:
			net.send_inspect(oid)        # rich card comes back as inspect_result
	elif event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_SPACE:
				_set_pace(0 if _tps > 0 else _last_speed_tps)
			KEY_1:
				_set_pace(2)
			KEY_2:
				_set_pace(10)
			KEY_3:
				_set_pace(40)


func _set_pace(tps: int) -> void:
	_tps = tps
	if tps > 0:
		_last_speed_tps = tps
	net.send_pace(tps)
	hud.set_pace_label(_speed_label(tps))


func _on_handshaked(info: Dictionary) -> void:
	hud.set_status("connected · seed %d · core %s" % [
		int(info.get("seed", -1)), String(info.get("core_commit", "?"))])
	_set_pace(START_TPS)
	_ping_nonce += 1
	net.send_ping(_ping_nonce)


func _on_snapshot(snap: Dictionary) -> void:
	arena.ingest_snapshot(snap)
	_accum = 0.0
	hud.set_tick(int(snap.get("tick", 0)))
	hud.set_pop(int(snap.get("meta", {}).get("pop", 0)))
	if arena.selected_oid != -1:
		net.send_inspect(arena.selected_oid)   # live-refresh the open card


func _on_events(ev: Dictionary) -> void:
	for it in ev.get("items", []):
		var actor = it.get("actor", null)
		if actor == null:
			continue
		var oid := int(actor)
		var arr: Array = _agent_events.get(oid, [])
		arr.append(it)
		while arr.size() > 5:
			arr.pop_front()
		_agent_events[oid] = arr
	if arena.selected_oid != -1:
		_render_card()                         # refresh the events line


func _on_inspect_result(r: Dictionary) -> void:
	if int(r.get("oid", -1)) != arena.selected_oid:
		return                                 # stale (selection changed)
	if not bool(r.get("alive", false)):
		return                                 # pawn died; keep the last card
	_selected_inspect = r
	_render_card()


func _on_error(err: Dictionary) -> void:
	hud.set_status("error: %s — %s" % [
		String(err.get("code", "?")), String(err.get("message", ""))])
	push_warning("server error: %s" % err)


func _on_closed() -> void:
	hud.set_status("disconnected")


func _render_card() -> void:
	if _selected_inspect.is_empty():
		return
	var card := _selected_inspect.duplicate(true)
	card["events"] = _agent_events.get(arena.selected_oid, [])
	hud.show_inspector(card)


func _speed_label(tps: int) -> String:
	match tps:
		0: return "‖ Pause"
		2: return "1x"
		10: return "4x"
		40: return "20x"
		_: return "%dtps" % tps
