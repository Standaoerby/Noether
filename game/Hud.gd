class_name Hud
extends CanvasLayer
## Control-node UI built in code: status/tick/pace/pop readouts, the time-control
## buttons, and the minimal pawn inspector. Emits pace_requested; all wiring
## lives in Main. No game logic here.

signal pace_requested(tps: int)

var _status: Label
var _tick: Label
var _pace: Label
var _pop: Label
var _inspector: Panel
var _inspector_body: Label

const SPEEDS := [                    # label -> tps (docs/game-architecture WO §2.3)
	{"label": "‖ Pause", "tps": 0},
	{"label": "1x", "tps": 2},
	{"label": "4x", "tps": 10},
	{"label": "20x", "tps": 40},
]


func _ready() -> void:
	var top := VBoxContainer.new()
	top.position = Vector2(16, 12)
	add_child(top)
	_status = _mk_label(top, "connecting…")
	_tick = _mk_label(top, "tick —")
	_pace = _mk_label(top, "pace ‖ Pause")
	_pop = _mk_label(top, "pop —")

	var bar := HBoxContainer.new()
	bar.position = Vector2(16, 620)
	bar.add_theme_constant_override("separation", 8)
	add_child(bar)
	for s in SPEEDS:
		var b := Button.new()
		b.text = s["label"]
		b.focus_mode = Control.FOCUS_NONE   # keep hotkeys working after a click
		var tps: int = s["tps"]
		b.pressed.connect(func() -> void: pace_requested.emit(tps))
		bar.add_child(b)
	var hint := _mk_label(bar, "   [Space]=pause  [1]1x [2]4x [3]20x  click=inspect")

	_build_inspector()


func set_status(text: String) -> void:
	_status.text = text


func set_tick(t: int) -> void:
	_tick.text = "tick %d" % t


func set_pace_label(label: String) -> void:
	_pace.text = "pace %s" % label


func set_pop(n: int) -> void:
	_pop.text = "pop %d" % n


func show_inspector(info: Dictionary) -> void:
	var lines := PackedStringArray()
	lines.append("oid   %d" % int(info.get("oid", -1)))
	lines.append("body  %.3f" % float(info.get("body", 0.0)))
	lines.append("deme  %d" % int(info.get("deme", -1)))
	var flags: Array = info.get("flags", [])
	lines.append("flags %s" % ("—" if flags.is_empty() else ", ".join(flags)))
	lines.append("")
	var events: Array = info.get("events", [])
	lines.append("last %d events:" % events.size())
	if events.is_empty():
		lines.append("  (none seen)")
	for e in events:
		lines.append("  t%d  %s" % [int(e.get("t", 0)), String(e.get("kind", "?"))])
	_inspector_body.text = "\n".join(lines)
	_inspector.visible = true


func hide_inspector() -> void:
	_inspector.visible = false


func _build_inspector() -> void:
	_inspector = Panel.new()
	_inspector.position = Vector2(920, 12)
	_inspector.size = Vector2(340, 260)
	_inspector.visible = false
	add_child(_inspector)
	var title := Label.new()
	title.text = "pawn"
	title.position = Vector2(12, 8)
	_inspector.add_child(title)
	_inspector_body = Label.new()
	_inspector_body.position = Vector2(12, 32)
	_inspector_body.size = Vector2(316, 220)
	_inspector.add_child(_inspector_body)


func _mk_label(parent: Node, text: String) -> Label:
	var l := Label.new()
	l.text = text
	parent.add_child(l)
	return l
