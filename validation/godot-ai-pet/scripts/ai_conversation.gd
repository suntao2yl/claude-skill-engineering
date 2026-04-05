extends Node
## AIConversation — autoload for pet dialog.
## Per ARCH-001: wraps Claude Haiku calls. Offline fallback uses scripted
## reactions keyed by personality + action. This demo ships with the
## scripted bank only; LLM integration is left as a stub.

# Scripted reaction bank — keyed by (personality_trait, action, mood_band)
const REACTIONS := {
	"ate_happily": [
		"呼噜呼噜，这个正好。",
		"嗯，谢谢你，{name}。",
		"（幸福地眯起眼）",
	],
	"ate_politely": [
		"好吧，我收下了。",
		"（慢吞吞吃了两口）",
	],
	"purred": [
		"呼噜呼噜～",
		"（蹭了蹭你的手）",
		"{name}今天闻起来很安心。",
	],
	"tolerated": [
		"（耳朵动了一下）",
		"嗯。",
	],
	"played_energetically": [
		"再来！再来！",
		"（追着逗猫棒左扑右跳）",
	],
	"played_tired": [
		"（懒洋洋躺下）累了。",
		"下次吧。",
	],
	"greeting_playful": [
		"等你好久了！我们玩什么？",
		"（尾巴高高竖起）",
	],
	"greeting_calm": [
		"嗨，你来了。",
		"（慢慢眨眼）",
	],
	"greeting_attached": [
		"想{name}了。",
		"（蹭过来）",
	],
	"greeting_new": [
		"......（远远看着你）",
		"（耳朵转向你）",
	],
	"confused": ["?", "（歪头）"],
	"chatted_playful": [
		"今天怎么样？我追到了三只（假想的）蝴蝶！",
		"猜猜我藏在哪儿？",
	],
	"chatted_calm": [
		"今天的窗外有鸟。",
		"（安静地坐在你身边）",
	],
	"chatted_attached": [
		"你手上有淡淡的洗衣液味。",
		"我等你一整天。",
	],
	"chatted_new": [
		"......我还在想怎么跟你说话。",
		"（舔了舔爪子）",
	],
}


func react_to(kind: String, personality: String = "new", pet_name: String = "") -> String:
	# Composite keys for greeting + chat
	var key := kind
	if kind == "greeting" or kind == "chatted":
		var suffix := personality
		if personality == "" or personality == "新来的，还在观察你":
			suffix = "new"
		key = "%s_%s" % [kind, suffix]
	if not REACTIONS.has(key):
		key = "confused"
	var bank: Array = REACTIONS[key]
	var line: String = bank[randi() % bank.size()]
	if pet_name != "":
		line = line.replace("{name}", pet_name)
	else:
		line = line.replace("{name}", "你")
	return line


func build_prompt_payload(personality: String, action: String, state: Dictionary) -> Dictionary:
	## For future LLM integration. Returns Anthropic messages API payload shape.
	var sys_prompt: String = "You are a cat named %s. Personality: %s. Respond in 1-2 short sentences, in character, in Chinese. Current stats: mood=%d hunger=%d energy=%d." % [
		state.get("name", "猫"), personality,
		state.get("mood", 0), state.get("hunger", 0), state.get("energy", 0)
	]
	return {
		"model": "claude-haiku-4-5",
		"max_tokens": 60,
		"system": sys_prompt,
		"messages": [
			{"role": "user", "content": "Owner did: %s" % action}
		]
	}
