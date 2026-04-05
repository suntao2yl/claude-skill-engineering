extends Control
## Main — builds the full scene programmatically.
## Composes CatActor + StateBar + ChatBubble + InteractionPanel + NamingModal.

const BG_TOP := Color("#F7E8D3")    # cream
const BG_BOTTOM := Color("#E8C9A8")  # warm sand

var cat_actor: CatActor
var state_bar: StateBar
var chat_bubble: ChatBubble
var interaction_panel: InteractionPanel
var naming_modal: NamingModal
var bg_rect: ColorRect


func _ready() -> void:
	randomize()
	_build_background()
	_build_cat()
	_build_state_bar()
	_build_chat_bubble()
	_build_interaction_panel()
	_build_naming_modal()
	PetState.state_changed.connect(_on_state_changed)
	_greet_on_launch()


func _build_background() -> void:
	bg_rect = ColorRect.new()
	bg_rect.anchor_right = 1.0
	bg_rect.anchor_bottom = 1.0
	bg_rect.color = BG_TOP
	add_child(bg_rect)
	bg_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE

	# Warm gradient via second rect at bottom
	var bot := ColorRect.new()
	bot.anchor_left = 0.0
	bot.anchor_right = 1.0
	bot.anchor_top = 0.55
	bot.anchor_bottom = 1.0
	bot.color = BG_BOTTOM
	bot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bot)


func _build_cat() -> void:
	cat_actor = CatActor.new()
	cat_actor.position = Vector2(480, 380)
	cat_actor.pet_clicked.connect(_on_cat_clicked)
	add_child(cat_actor)


func _build_state_bar() -> void:
	state_bar = StateBar.new()
	state_bar.anchor_right = 1.0
	state_bar.offset_left = 16
	state_bar.offset_top = 12
	state_bar.offset_right = -16
	state_bar.offset_bottom = 60
	state_bar.refresh()
	add_child(state_bar)


func _build_chat_bubble() -> void:
	chat_bubble = ChatBubble.new()
	chat_bubble.position = Vector2(480, 220)
	add_child(chat_bubble)


func _build_interaction_panel() -> void:
	interaction_panel = InteractionPanel.new()
	interaction_panel.anchor_left = 0.0
	interaction_panel.anchor_right = 1.0
	interaction_panel.anchor_top = 1.0
	interaction_panel.anchor_bottom = 1.0
	interaction_panel.offset_top = -88
	interaction_panel.offset_left = 16
	interaction_panel.offset_right = -16
	interaction_panel.offset_bottom = -16
	interaction_panel.action_requested.connect(_on_action)
	add_child(interaction_panel)


func _build_naming_modal() -> void:
	naming_modal = NamingModal.new()
	naming_modal.anchor_right = 1.0
	naming_modal.anchor_bottom = 1.0
	naming_modal.name_submitted.connect(_on_name_submitted)
	add_child(naming_modal)
	if not PetState.first_meeting_complete:
		# Small delay so the user sees the cat first
		await get_tree().create_timer(1.8).timeout
		naming_modal.show_modal()


func _greet_on_launch() -> void:
	if not PetState.first_meeting_complete:
		return  # naming modal will handle first greeting
	var personality: String = PetState.personality_summary()
	var line: String = AIConversation.react_to("greeting", personality, PetState.pet_name)
	chat_bubble.say(line)


func _on_cat_clicked() -> void:
	cat_actor.play_tilt()
	if not PetState.first_meeting_complete:
		# During first meeting, clicking the cat shows curiosity, no modal trigger
		chat_bubble.say("（歪头）")
		return
	# Tap = gentle pet
	_on_action("pet")


func _on_action(action: String) -> void:
	var result := PetState.apply_action(action)
	var reaction_kind: String = result.kind
	var personality: String = PetState.personality_summary()
	var line: String = ""
	if action == "chat":
		line = AIConversation.react_to("chatted", personality, PetState.pet_name)
	else:
		line = AIConversation.react_to(reaction_kind, personality, PetState.pet_name)
	chat_bubble.say(line)
	cat_actor.react_visually(action)


func _on_name_submitted(new_name: String) -> void:
	if new_name.is_empty():
		new_name = "咪咪"
	PetState.set_pet_name(new_name)
	PetState.complete_first_meeting()
	state_bar.refresh()
	await get_tree().create_timer(0.3).timeout
	chat_bubble.say("%s...我喜欢这个名字。" % new_name)


func _on_state_changed() -> void:
	state_bar.refresh()


# -------------------------------------------------------------
# Inner classes (inline for single-file-per-responsibility layout)
# -------------------------------------------------------------

class CatActor extends Node2D:
	signal pet_clicked

	const BODY_COLOR := Color("#E8A87C")
	const BODY_SHADOW := Color("#C38D6A")
	const EYE_COLOR := Color("#2A2A2A")
	const NOSE_COLOR := Color("#D47A7A")
	const INNER_EAR := Color("#F7CDB0")

	var blink_scale: float = 1.0
	var breath_scale: float = 1.0
	var tail_angle: float = 0.0
	var tilt: float = 0.0
	var hover: bool = false
	var click_area_radius: float = 90.0

	func _ready() -> void:
		_schedule_next_blink()
		_start_breath()
		_start_tail_sway()
		set_process(true)

	func _process(delta: float) -> void:
		queue_redraw()

	func _input(event: InputEvent) -> void:
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			var local_pos: Vector2 = to_local(event.position)
			if local_pos.length() < click_area_radius:
				pet_clicked.emit()

	func _draw() -> void:
		var b_s := breath_scale
		# Tail (behind body)
		var tail_start := Vector2(40, 10).rotated(tilt)
		var tail_mid := Vector2(80, -10).rotated(tilt + tail_angle)
		var tail_end := Vector2(100, -50).rotated(tilt + tail_angle * 1.5)
		draw_polyline(
			_bezier_points(tail_start, tail_mid, tail_end, 16),
			BODY_COLOR, 10.0, true
		)

		# Body (ellipse)
		draw_colored_polygon(_ellipse_points(Vector2(0, 20), 65 * b_s, 48 * b_s, 32, tilt), BODY_COLOR)
		draw_colored_polygon(_ellipse_points(Vector2(0, 40), 58 * b_s, 18 * b_s, 24, tilt), BODY_SHADOW)

		# Head
		var head_center := Vector2(0, -30).rotated(tilt)
		draw_colored_polygon(_ellipse_points(head_center, 42, 38, 32, tilt), BODY_COLOR)

		# Ears
		var ear_l := [Vector2(-32, -58), Vector2(-20, -90), Vector2(-8, -60)]
		var ear_r := [Vector2(8, -60), Vector2(20, -90), Vector2(32, -58)]
		draw_colored_polygon(_rotate_points(ear_l, tilt), BODY_COLOR)
		draw_colored_polygon(_rotate_points(ear_r, tilt), BODY_COLOR)
		var inner_l := [Vector2(-26, -62), Vector2(-20, -82), Vector2(-14, -62)]
		var inner_r := [Vector2(14, -62), Vector2(20, -82), Vector2(26, -62)]
		draw_colored_polygon(_rotate_points(inner_l, tilt), INNER_EAR)
		draw_colored_polygon(_rotate_points(inner_r, tilt), INNER_EAR)

		# Eyes
		var eye_l := Vector2(-14, -30).rotated(tilt)
		var eye_r := Vector2(14, -30).rotated(tilt)
		draw_colored_polygon(_ellipse_points(eye_l, 4, 6 * blink_scale, 16, 0), EYE_COLOR)
		draw_colored_polygon(_ellipse_points(eye_r, 4, 6 * blink_scale, 16, 0), EYE_COLOR)
		if blink_scale > 0.5:
			draw_circle(eye_l + Vector2(1.5, -1.5), 1.5, Color("#FFFFFF"))
			draw_circle(eye_r + Vector2(1.5, -1.5), 1.5, Color("#FFFFFF"))

		# Nose
		var nose := Vector2(0, -15).rotated(tilt)
		draw_colored_polygon([
			nose + Vector2(-4, 0), nose + Vector2(4, 0), nose + Vector2(0, 4)
		], NOSE_COLOR)

		# Mouth
		var mouth := Vector2(0, -10).rotated(tilt)
		draw_arc(mouth + Vector2(-5, 0), 5, 0.2, PI - 0.2, 8, EYE_COLOR, 2.0)
		draw_arc(mouth + Vector2(5, 0), 5, 0.2, PI - 0.2, 8, EYE_COLOR, 2.0)

		# Front paws
		draw_colored_polygon(_ellipse_points(Vector2(-22, 62), 12, 8, 16, tilt), BODY_SHADOW)
		draw_colored_polygon(_ellipse_points(Vector2(22, 62), 12, 8, 16, tilt), BODY_SHADOW)

	func _ellipse_points(center: Vector2, rx: float, ry: float, segments: int, rotation_rad: float) -> PackedVector2Array:
		var pts := PackedVector2Array()
		for i in segments:
			var a := TAU * i / segments
			var p := Vector2(cos(a) * rx, sin(a) * ry).rotated(rotation_rad) + center
			pts.append(p)
		return pts

	func _rotate_points(points: Array, rotation_rad: float) -> PackedVector2Array:
		var out := PackedVector2Array()
		for p in points:
			out.append((p as Vector2).rotated(rotation_rad))
		return out

	func _bezier_points(a: Vector2, b: Vector2, c: Vector2, steps: int) -> PackedVector2Array:
		var pts := PackedVector2Array()
		for i in steps + 1:
			var t := float(i) / steps
			var p := a.lerp(b, t).lerp(b.lerp(c, t), t)
			pts.append(p)
		return pts

	# ── Animations ─────────────────────────────────────────────
	func _schedule_next_blink() -> void:
		var wait := randf_range(2.5, 5.0)
		get_tree().create_timer(wait).timeout.connect(_do_blink)

	func _do_blink() -> void:
		var tw := create_tween()
		tw.tween_property(self, "blink_scale", 0.1, 0.08)
		tw.tween_property(self, "blink_scale", 1.0, 0.12)
		tw.finished.connect(_schedule_next_blink)

	func _start_breath() -> void:
		var tw := create_tween().set_loops()
		tw.tween_property(self, "breath_scale", 1.03, 1.4).set_trans(Tween.TRANS_SINE)
		tw.tween_property(self, "breath_scale", 1.0, 1.4).set_trans(Tween.TRANS_SINE)

	func _start_tail_sway() -> void:
		var tw := create_tween().set_loops()
		tw.tween_property(self, "tail_angle", 0.25, 2.0).set_trans(Tween.TRANS_SINE)
		tw.tween_property(self, "tail_angle", -0.25, 2.0).set_trans(Tween.TRANS_SINE)

	func play_tilt() -> void:
		var tw := create_tween()
		tw.tween_property(self, "tilt", 0.2, 0.15).set_trans(Tween.TRANS_BACK)
		tw.tween_property(self, "tilt", 0.0, 0.3).set_trans(Tween.TRANS_BACK)

	func react_visually(action: String) -> void:
		match action:
			"play":
				var tw := create_tween()
				tw.tween_property(self, "position:y", position.y - 24, 0.15)
				tw.tween_property(self, "position:y", position.y, 0.25)
			"feed":
				var tw := create_tween()
				tw.tween_property(self, "tilt", -0.15, 0.2)
				tw.tween_property(self, "tilt", 0.0, 0.3)
			"pet":
				play_tilt()
			_:
				play_tilt()


class StateBar extends Control:
	func _ready() -> void:
		refresh()

	func refresh() -> void:
		for child in get_children():
			child.queue_free()
		var hb := HBoxContainer.new()
		hb.anchor_right = 1.0
		hb.anchor_bottom = 1.0
		hb.add_theme_constant_override("separation", 18)
		add_child(hb)

		var name_label := Label.new()
		var name_text: String = PetState.pet_name if PetState.pet_name != "" else "（未命名）"
		name_label.text = name_text
		name_label.add_theme_font_size_override("font_size", 22)
		name_label.add_theme_color_override("font_color", Color("#3A2A1A"))
		hb.add_child(name_label)

		var personality := Label.new()
		personality.text = "· " + PetState.personality_summary()
		personality.add_theme_font_size_override("font_size", 14)
		personality.add_theme_color_override("font_color", Color("#7A5A3A"))
		hb.add_child(personality)

		var spacer := Control.new()
		spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		hb.add_child(spacer)

		hb.add_child(_stat_chip("心情", PetState.mood, Color("#D47A7A")))
		hb.add_child(_stat_chip("饱腹", 100 - PetState.hunger, Color("#E8A87C")))
		hb.add_child(_stat_chip("精力", PetState.energy, Color("#7AA87A")))

	func _stat_chip(label: String, value: int, color: Color) -> Control:
		var v := VBoxContainer.new()
		v.custom_minimum_size = Vector2(80, 40)
		var l := Label.new()
		l.text = label
		l.add_theme_font_size_override("font_size", 12)
		l.add_theme_color_override("font_color", Color("#7A5A3A"))
		v.add_child(l)
		var bar := ProgressBar.new()
		bar.custom_minimum_size = Vector2(80, 8)
		bar.max_value = 100
		bar.value = value
		bar.show_percentage = false
		var sb := StyleBoxFlat.new()
		sb.bg_color = color
		sb.corner_radius_top_left = 4
		sb.corner_radius_top_right = 4
		sb.corner_radius_bottom_left = 4
		sb.corner_radius_bottom_right = 4
		bar.add_theme_stylebox_override("fill", sb)
		var sb_bg := StyleBoxFlat.new()
		sb_bg.bg_color = Color("#FFFFFF", 0.5)
		sb_bg.corner_radius_top_left = 4
		sb_bg.corner_radius_top_right = 4
		sb_bg.corner_radius_bottom_left = 4
		sb_bg.corner_radius_bottom_right = 4
		bar.add_theme_stylebox_override("background", sb_bg)
		v.add_child(bar)
		return v


class ChatBubble extends Node2D:
	var text: String = ""
	var alpha: float = 0.0
	var timer: SceneTreeTimer = null

	func _ready() -> void:
		z_index = 10
		set_process(true)

	func say(line: String) -> void:
		text = line
		alpha = 0.0
		queue_redraw()
		var tw := create_tween()
		tw.tween_property(self, "alpha", 1.0, 0.2)
		if timer:
			timer = null
		timer = get_tree().create_timer(3.2)
		timer.timeout.connect(_fade_out)

	func _fade_out() -> void:
		var tw := create_tween()
		tw.tween_property(self, "alpha", 0.0, 0.35)

	func _process(_delta: float) -> void:
		queue_redraw()

	func _draw() -> void:
		if alpha < 0.01 or text.is_empty():
			return
		var font := ThemeDB.fallback_font
		var font_size := 18
		var padding := 14.0
		var text_size := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
		var bubble_w: float = min(text_size.x + padding * 2, 420.0)
		var bubble_h: float = text_size.y + padding * 2
		var rect := Rect2(-bubble_w / 2, -bubble_h - 10, bubble_w, bubble_h)
		var bg_color := Color("#FFFFFF", alpha * 0.95)
		var border := Color("#D4A574", alpha)
		_draw_rounded_rect(rect, 14.0, bg_color, border, 2.0)
		var tail := PackedVector2Array([
			Vector2(-8, -10),
			Vector2(8, -10),
			Vector2(0, 2)
		])
		draw_colored_polygon(tail, bg_color)
		draw_string(
			font, rect.position + Vector2(padding, padding + font_size * 0.8),
			text, HORIZONTAL_ALIGNMENT_LEFT, bubble_w - padding * 2, font_size,
			Color("#3A2A1A", alpha)
		)

	func _draw_rounded_rect(rect: Rect2, r: float, fill: Color, border: Color, border_width: float) -> void:
		draw_rect(Rect2(rect.position + Vector2(r, 0), Vector2(rect.size.x - 2 * r, rect.size.y)), fill)
		draw_rect(Rect2(rect.position + Vector2(0, r), Vector2(rect.size.x, rect.size.y - 2 * r)), fill)
		draw_circle(rect.position + Vector2(r, r), r, fill)
		draw_circle(rect.position + Vector2(rect.size.x - r, r), r, fill)
		draw_circle(rect.position + Vector2(r, rect.size.y - r), r, fill)
		draw_circle(rect.position + Vector2(rect.size.x - r, rect.size.y - r), r, fill)
		draw_arc(rect.position + Vector2(r, r), r, PI, 3 * PI / 2, 12, border, border_width)
		draw_arc(rect.position + Vector2(rect.size.x - r, r), r, 3 * PI / 2, TAU, 12, border, border_width)
		draw_arc(rect.position + Vector2(r, rect.size.y - r), r, PI / 2, PI, 12, border, border_width)
		draw_arc(rect.position + Vector2(rect.size.x - r, rect.size.y - r), r, 0, PI / 2, 12, border, border_width)
		draw_line(rect.position + Vector2(r, 0), rect.position + Vector2(rect.size.x - r, 0), border, border_width)
		draw_line(rect.position + Vector2(r, rect.size.y), rect.position + Vector2(rect.size.x - r, rect.size.y), border, border_width)
		draw_line(rect.position + Vector2(0, r), rect.position + Vector2(0, rect.size.y - r), border, border_width)
		draw_line(rect.position + Vector2(rect.size.x, r), rect.position + Vector2(rect.size.x, rect.size.y - r), border, border_width)


class InteractionPanel extends PanelContainer:
	signal action_requested(action: String)

	func _ready() -> void:
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color("#FFFFFF", 0.85)
		sb.corner_radius_top_left = 18
		sb.corner_radius_top_right = 18
		sb.corner_radius_bottom_left = 18
		sb.corner_radius_bottom_right = 18
		sb.content_margin_left = 16
		sb.content_margin_right = 16
		sb.content_margin_top = 12
		sb.content_margin_bottom = 12
		add_theme_stylebox_override("panel", sb)

		var hb := HBoxContainer.new()
		hb.add_theme_constant_override("separation", 12)
		add_child(hb)
		for spec in [
			{"label": "喂食 🍚", "action": "feed"},
			{"label": "摸摸 🤲", "action": "pet"},
			{"label": "玩耍 🧶", "action": "play"},
			{"label": "聊天 💬", "action": "chat"},
		]:
			var b := Button.new()
			b.text = spec.label
			b.custom_minimum_size = Vector2(0, 52)
			b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			b.add_theme_font_size_override("font_size", 18)
			var btn_sb := StyleBoxFlat.new()
			btn_sb.bg_color = Color("#F2D4A7")
			btn_sb.corner_radius_top_left = 12
			btn_sb.corner_radius_top_right = 12
			btn_sb.corner_radius_bottom_left = 12
			btn_sb.corner_radius_bottom_right = 12
			btn_sb.content_margin_left = 12
			btn_sb.content_margin_right = 12
			b.add_theme_stylebox_override("normal", btn_sb)
			var btn_hover := btn_sb.duplicate()
			btn_hover.bg_color = Color("#E8C38F")
			b.add_theme_stylebox_override("hover", btn_hover)
			b.add_theme_color_override("font_color", Color("#3A2A1A"))
			b.pressed.connect(func(): action_requested.emit(spec.action))
			hb.add_child(b)


class NamingModal extends Control:
	signal name_submitted(new_name: String)
	var input: LineEdit
	var overlay: ColorRect

	func _ready() -> void:
		visible = false
		overlay = ColorRect.new()
		overlay.anchor_right = 1.0
		overlay.anchor_bottom = 1.0
		overlay.color = Color("#000000", 0.45)
		add_child(overlay)

		var card := PanelContainer.new()
		card.anchor_left = 0.5
		card.anchor_right = 0.5
		card.anchor_top = 0.5
		card.anchor_bottom = 0.5
		card.offset_left = -200
		card.offset_right = 200
		card.offset_top = -110
		card.offset_bottom = 110
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color("#FFFFFF")
		sb.corner_radius_top_left = 20
		sb.corner_radius_top_right = 20
		sb.corner_radius_bottom_left = 20
		sb.corner_radius_bottom_right = 20
		sb.content_margin_left = 28
		sb.content_margin_right = 28
		sb.content_margin_top = 24
		sb.content_margin_bottom = 24
		card.add_theme_stylebox_override("panel", sb)
		add_child(card)

		var vb := VBoxContainer.new()
		vb.add_theme_constant_override("separation", 14)
		card.add_child(vb)

		var title := Label.new()
		title.text = "这只小猫需要一个名字"
		title.add_theme_font_size_override("font_size", 22)
		title.add_theme_color_override("font_color", Color("#3A2A1A"))
		title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		vb.add_child(title)

		var sub := Label.new()
		sub.text = "起一个你喜欢的，之后它就靠这个认你。"
		sub.add_theme_font_size_override("font_size", 14)
		sub.add_theme_color_override("font_color", Color("#7A5A3A"))
		sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		vb.add_child(sub)

		input = LineEdit.new()
		input.placeholder_text = "比如：咪咪"
		input.custom_minimum_size = Vector2(0, 44)
		input.add_theme_font_size_override("font_size", 20)
		vb.add_child(input)

		var submit := Button.new()
		submit.text = "就叫这个了"
		submit.custom_minimum_size = Vector2(0, 48)
		submit.add_theme_font_size_override("font_size", 18)
		var btn_sb := StyleBoxFlat.new()
		btn_sb.bg_color = Color("#E8A87C")
		btn_sb.corner_radius_top_left = 12
		btn_sb.corner_radius_top_right = 12
		btn_sb.corner_radius_bottom_left = 12
		btn_sb.corner_radius_bottom_right = 12
		submit.add_theme_stylebox_override("normal", btn_sb)
		submit.add_theme_color_override("font_color", Color("#FFFFFF"))
		submit.pressed.connect(_on_submit)
		vb.add_child(submit)

	func show_modal() -> void:
		visible = true
		input.grab_focus()

	func _on_submit() -> void:
		var txt: String = input.text.strip_edges()
		name_submitted.emit(txt)
		visible = false
