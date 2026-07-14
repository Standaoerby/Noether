class_name Arena
extends Node2D
## Draws the arena tilemap and living-agent markers, interpolating positions
## between the two most recent snapshots (alpha driven by Main). Pure
## presentation: it renders what the core sent and never invents state.
## Marker jitter uses a COSMETIC rng (seeded per-oid) that never leaves the
## client — no client randomness ever flows back into commands.

# Arena is fitted into a viewport box each frame (the substrate is 14x14, too
# big for a fixed 110px cell). Margins leave room for the top readout, the
# bottom time-control bar, and the right-side inspector panel.
const BOX_LEFT := 32.0
const BOX_TOP := 96.0
const BOX_RIGHT_FRAC := 0.68        # reserve the right ~third for the inspector
const BOX_BOTTOM_PAD := 110.0       # clear the button bar
const JITTER_FRAC := 0.28           # keep co-located agents visually apart

var _cell_px := 36.0                # computed to fit (see _recompute_layout)
var _origin := Vector2(BOX_LEFT, BOX_TOP)
var _marker_r := 6.0

# marker colours by role (priority high -> low)
const C_DEMERZEL := Color("d17bff")
const C_SPEAKER := Color("46d0e6")
const C_OWNER := Color("e8c34a")
const C_BONDED := Color("e8613a")
const C_PLAIN := Color("8fe38f")
const C_GRID := Color(1, 1, 1, 0.10)
const C_GRID_EDGE := Color(1, 1, 1, 0.22)
const C_SELECT := Color(1, 1, 1, 0.95)

var rows := 5
var cols := 5
var alpha := 1.0                    # 0..1 interp factor from Main (no extrapolation)
var selected_oid := -1

var _prev: Dictionary = {}          # oid -> agent dict (previous snapshot)
var _curr: Dictionary = {}          # oid -> agent dict (latest snapshot)
var _rng := RandomNumberGenerator.new()


func ingest_snapshot(snap: Dictionary) -> void:
	var meta: Dictionary = snap.get("meta", {})
	rows = int(meta.get("rows", rows))
	cols = int(meta.get("cols", cols))
	var m: Dictionary = {}
	for a in snap.get("agents", []):
		m[int(a["oid"])] = a
	# On the first snapshot prev==curr so nothing tweens from the origin.
	_prev = _curr if not _curr.is_empty() else m
	_curr = m
	alpha = 0.0
	queue_redraw()


func _process(_delta: float) -> void:
	_recompute_layout()
	queue_redraw()                  # redraw every frame so interpolation animates


## Fit a rows x cols grid into the viewport box; keep cells square, centred.
func _recompute_layout() -> void:
	var vp := get_viewport_rect().size
	var box_right: float = vp.x * BOX_RIGHT_FRAC
	var box_bottom: float = vp.y - BOX_BOTTOM_PAD
	var avail_w: float = maxf(40.0, box_right - BOX_LEFT)
	var avail_h: float = maxf(40.0, box_bottom - BOX_TOP)
	_cell_px = maxf(6.0, minf(avail_w / float(cols), avail_h / float(rows)))
	_marker_r = clampf(_cell_px * 0.18, 2.5, 9.0)
	var arena_w := _cell_px * cols
	var arena_h := _cell_px * rows
	_origin = Vector2(BOX_LEFT + (avail_w - arena_w) * 0.5,
					  BOX_TOP + (avail_h - arena_h) * 0.5)


func agent_data(oid: int) -> Dictionary:
	return _curr.get(oid, {})


## Nearest living marker to a local-space point, within grab radius; -1 if none.
func pick(local_pos: Vector2) -> int:
	var best := -1
	var best_d := _cell_px * 0.5
	for oid in _curr.keys():
		var d := _marker_pos(_curr[oid]).distance_to(local_pos)
		if d < best_d:
			best_d = d
			best = oid
	return best


func _draw() -> void:
	_draw_grid()
	for oid in _curr.keys():
		var pos := _interp_pos(int(oid))
		if selected_oid == int(oid):
			draw_circle(pos, _marker_r + 4.0, C_SELECT)
		draw_circle(pos, _marker_r, _colour_for(_curr[oid].get("flags", [])))


func _draw_grid() -> void:
	var w := cols * _cell_px
	var h := rows * _cell_px
	for c in range(cols + 1):
		var x := _origin.x + c * _cell_px
		var edge := (c == 0 or c == cols)
		draw_line(Vector2(x, _origin.y), Vector2(x, _origin.y + h),
			C_GRID_EDGE if edge else C_GRID, 1.0)
	for r in range(rows + 1):
		var y := _origin.y + r * _cell_px
		var edge := (r == 0 or r == rows)
		draw_line(Vector2(_origin.x, y), Vector2(_origin.x + w, y),
			C_GRID_EDGE if edge else C_GRID, 1.0)


func _interp_pos(oid: int) -> Vector2:
	var cur := _marker_pos(_curr[oid])
	if _prev.has(oid):
		return _marker_pos(_prev[oid]).lerp(cur, alpha)
	return cur                      # newly spawned: no history to tween from


func _marker_pos(a: Dictionary) -> Vector2:
	var base := _origin + Vector2((float(a["x"]) + 0.5) * _cell_px,
								  (float(a["y"]) + 0.5) * _cell_px)
	return base + _jitter(int(a["oid"]))


func _jitter(oid: int) -> Vector2:
	# Deterministic per-agent cosmetic offset — stable frame to frame, and it
	# stays on the client. Reseed from the oid, not from any core state.
	_rng.seed = oid
	var r := _cell_px * JITTER_FRAC
	return Vector2(_rng.randf_range(-r, r), _rng.randf_range(-r, r))


func _colour_for(flags: Array) -> Color:
	if "demerzel" in flags:
		return C_DEMERZEL
	if "speaker" in flags:
		return C_SPEAKER
	if "owner" in flags:
		return C_OWNER
	if "bonded" in flags:
		return C_BONDED
	return C_PLAIN
