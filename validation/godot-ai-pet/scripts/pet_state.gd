extends Node
## PetState — autoload singleton that holds pet data and persists to user://
## Persistence: Godot ConfigFile at user://pet_state.cfg (per ARCH-001)

const SAVE_PATH := "user://pet_state.cfg"
const MAX_STAT := 100
const MIN_STAT := 0

# Stats
var pet_name: String = ""
var mood: int = 60
var hunger: int = 50  # higher = hungrier
var energy: int = 70
var interaction_count: int = 0
var session_count: int = 0
var first_meeting_complete: bool = false
var last_seen_utc: String = ""

# Personality history (feeds AIConversation)
var interaction_log: Array = []  # Array[Dictionary]: {ts, action, reaction}

# Derived personality traits (computed lazily, not persisted — recomputed from log)
var traits: Dictionary = {"playful": 0, "calm": 0, "attached": 0}

signal state_changed
signal first_meeting_done


func _ready() -> void:
	load_state()
	session_count += 1
	_recompute_traits()
	# Apply time-away decay (gentle)
	_apply_away_decay()
	save_state()


func load_state() -> void:
	var cfg := ConfigFile.new()
	var err := cfg.load(SAVE_PATH)
	if err != OK:
		return  # fresh start
	pet_name = cfg.get_value("pet", "name", "")
	mood = cfg.get_value("pet", "mood", 60)
	hunger = cfg.get_value("pet", "hunger", 50)
	energy = cfg.get_value("pet", "energy", 70)
	interaction_count = cfg.get_value("pet", "interaction_count", 0)
	session_count = cfg.get_value("pet", "session_count", 0)
	first_meeting_complete = cfg.get_value("pet", "first_meeting_complete", false)
	last_seen_utc = cfg.get_value("pet", "last_seen_utc", "")
	interaction_log = cfg.get_value("pet", "interaction_log", [])


func save_state() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("pet", "name", pet_name)
	cfg.set_value("pet", "mood", mood)
	cfg.set_value("pet", "hunger", hunger)
	cfg.set_value("pet", "energy", energy)
	cfg.set_value("pet", "interaction_count", interaction_count)
	cfg.set_value("pet", "session_count", session_count)
	cfg.set_value("pet", "first_meeting_complete", first_meeting_complete)
	cfg.set_value("pet", "last_seen_utc", Time.get_datetime_string_from_system(true))
	cfg.set_value("pet", "interaction_log", interaction_log)
	cfg.save(SAVE_PATH)


func set_pet_name(new_name: String) -> void:
	pet_name = new_name.strip_edges()
	state_changed.emit()
	save_state()


func complete_first_meeting() -> void:
	first_meeting_complete = true
	first_meeting_done.emit()
	save_state()


func apply_action(action: String) -> Dictionary:
	## Mutates state based on user action. Returns {reaction_kind, delta}
	var result := {"kind": "", "delta": {}}
	match action:
		"feed":
			var d := _clamp_delta("hunger", -30)
			hunger += d
			result.delta["hunger"] = d
			var m := _clamp_delta("mood", 10)
			mood += m
			result.delta["mood"] = m
			result.kind = "ate_happily" if hunger < 30 else "ate_politely"
		"pet":
			var m := _clamp_delta("mood", 15)
			mood += m
			result.delta["mood"] = m
			var e := _clamp_delta("energy", -3)
			energy += e
			result.delta["energy"] = e
			result.kind = "purred" if mood > 70 else "tolerated"
		"play":
			var e := _clamp_delta("energy", -20)
			energy += e
			result.delta["energy"] = e
			var m := _clamp_delta("mood", 20)
			mood += m
			result.delta["mood"] = m
			var h := _clamp_delta("hunger", 8)
			hunger += h
			result.delta["hunger"] = h
			result.kind = "played_energetically" if energy > 40 else "played_tired"
		"chat":
			result.kind = "chatted"
		_:
			result.kind = "confused"

	interaction_count += 1
	var entry := {
		"ts": Time.get_unix_time_from_system(),
		"action": action,
		"reaction": result.kind,
	}
	interaction_log.append(entry)
	# Keep log bounded
	if interaction_log.size() > 100:
		interaction_log = interaction_log.slice(interaction_log.size() - 100)

	_recompute_traits()
	state_changed.emit()
	save_state()
	return result


func _clamp_delta(stat: String, requested: int) -> int:
	var curr: int = get(stat)
	var target: int = clampi(curr + requested, MIN_STAT, MAX_STAT)
	return target - curr


func _recompute_traits() -> void:
	traits = {"playful": 0, "calm": 0, "attached": 0}
	for entry in interaction_log:
		match entry.action:
			"play": traits.playful += 1
			"pet": traits.calm += 1; traits.attached += 1
			"feed": traits.attached += 1
			"chat": traits.attached += 1


func _apply_away_decay() -> void:
	if last_seen_utc.is_empty():
		return
	# Cheap estimate: each session away, +5 hunger, -3 mood (misses you)
	hunger = clampi(hunger + 5, MIN_STAT, MAX_STAT)
	mood = clampi(mood - 3, MIN_STAT, MAX_STAT)


func personality_summary() -> String:
	var top_trait := ""
	var top_val := 0
	for key in traits:
		if traits[key] > top_val:
			top_val = traits[key]
			top_trait = key
	if top_val == 0:
		return "新来的，还在观察你"
	return top_trait
