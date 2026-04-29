# Autodrive 教程:端到端自动化推进项目

本教程演示如何把一个项目从「我有个想法」一路自动推到「上线 + 回归基线
冻结」,中间不需要在阶段之间介入。所用组件:`harness-engineering` +
`harness-plan`(autodrive 模式)+ `harness-discipline`。

人工介入只发生在 3 个 risk gate(共约 5 分钟),其余全程自动 — 但代价
是大量 Anthropic API token,请预算好。

## 前置

```bash
# 三个插件全部已装且版本兼容
claude plugin list | grep -E "harness-(engineering|plan|discipline)"
# 期望:
#   harness-discipline@harness-discipline-marketplace   ≥ 0.1.0
#   harness-engineering@harness-engineering-marketplace ≥ 1.0.0
#   harness-plan@suntao-skills                          ≥ 0.5.0
```

缺哪个就装哪个:

```bash
/plugin marketplace add suntao2yl/claude-skill-engineering
/plugin marketplace add suntao2yl/claude-skill-harness
/plugin marketplace add suntao2yl/harness-discipline
/plugin install harness-engineering@harness-engineering-marketplace
/plugin install harness-plan@suntao-skills
/plugin install harness-discipline@harness-discipline-marketplace
```

另需:
- 干净的 git 仓库(autodrive 每个 feature 完成后会自动 commit)
- `claude` 二进制在 `PATH` 里(Stop hook spawn headless session 需要)
- 单 campaign 大约要花 ~20 次完整 Claude session 的 token(可用
  `--max-iterations` 调节上限)

## 整体流水线

```
   ┌────────────────── 人工 risk gate ─────────────────┐
   │                                                    │
   ▼                                                    ▼

discovery → design → architecture → implementation → test → release → ops
              ▲                            │                            │
              │                            │ 委托给                      │
              │                            ▼                            │
              │                       harness-plan                      │
              │                            │                            │
              │                            │ autodrive on               │
              │                            ▼                            │
              │                  ┌─────────────────────┐                │
              │                  │ F001 → commit → 退出 │                │
              │                  │   ↓ (Stop hook)     │                │
              │                  │ F002 → commit → 退出 │                │
              │                  │   ↓                 │                │
              │                  │  ...                │                │
              │                  │   ↓                 │                │
              │                  │ Final review session │                │
              │                  └─────────────────────┘                │
              │                                                         │
              └────── 触发 insight 时 revise(任意阶段 → 上游)────────┘

   /harness-engineering         confirm gate          eval baseline
                                (discovery.approved、
                                 architecture.approved、
                                 release.approved)
```

## 第 1 步:init lifecycle

在一个空(或近乎空)的 git 仓库里:

```bash
mkdir my-project && cd my-project && git init && touch README.md
git add . && git commit -m "init"

claude
```

进 Claude session:

```
/harness-engineering "build a CLI tool that exports a Postgres table to CSV with optional column filtering and quoted strings"
```

engineering 创建 `.engineering/` 与项目根 `AGENTS.md`,跑完 discovery 阶段,
停在 `discovery.approved` risk gate。

产物:

```
.engineering/
├── lifecycle.json
├── discovery/requirements.json
├── design/、architecture/、implementation/、test/、release/、ops/   (空)
├── decisions.jsonl
└── insights.jsonl
AGENTS.md
```

读一下 `requirements.json`,确认 discovery 抓出来的 users / metrics /
problem statement 与你的本意吻合,然后:

```
/harness-engineering advance --confirm
```

engineering 自动跑 design → architecture,停在 `architecture.approved`。
读 `.engineering/architecture/adrs/` 下的 ADR,再 `--confirm` 一次放行。

## 第 2 步:启动实现 + 开 autodrive

`architecture.approved` 后,engineering 进 implementation 阶段,按 brief
委托给 harness-plan。

同一个 Claude session 里,harness-plan 在
`.engineering/implementation/.harness/` 下跑 INIT(用 discipline 的
`/tdd-plan` 给每个 feature 种 verification command)。当它把 feature 计划
摆出来时,确认通过。

然后开 autodrive:

```
/harness-plan autodrive on
```

这写入 `.harness/autodrive.json`(默认 `enabled: true,
max_iterations: 20`)。feature 多就调大上限:

```bash
python3 ~/.claude/plugins/cache/suntao-skills/harness-plan/*/skills/harness-plan/scripts/harness_autodrive.py \
    --project-root .engineering/implementation \
    --enable --max-iterations 30
```

现在结束当前 Claude session(`/exit` 或关掉终端)。Stop hook 触发:

1. 读 `.engineering/implementation/.harness/autodrive.json`
2. 确认 campaign 还没 done
3. spawn `claude -p "/harness-plan"` 作为 detached 进程
4. 日志写到 `.engineering/implementation/.harness/autodrive.log`

新的 headless session 自动 resume campaign,挑第一个 feature,实现,跑
`/completion-verify`,标 done,git commit,退出。Stop hook 再触发,spawn
F002 的 session。如此循环。

## 第 3 步:监控

实时看 autodrive 日志:

```bash
tail -f .engineering/implementation/.harness/autodrive.log
```

每个 feature 一段:

```
[2026-04-29T10:00:00Z] decide: continuing — iteration 1/20, counts=0/8, current=F001
[2026-04-29T10:00:00Z] decide: continuation session spawned
[2026-04-29T10:14:23Z] decide: continuing — iteration 2/20, counts=1/8, current=F002
...
```

git 历史:

```bash
git log --oneline | head
# feat(harness): complete F008 - Add CSV column-selector flag
# feat(harness): complete F007 - Quote strings with embedded commas
# feat(harness): complete F006 - ...
```

状态快照:

```bash
python3 ~/.claude/plugins/cache/suntao-skills/harness-plan/*/skills/harness-plan/scripts/harness_autodrive.py \
    --project-root .engineering/implementation --status
```

## 第 4 步:最后的 review session

所有 feature 都 `done` 后,Stop hook 检测到「all features terminal」,把
`phase` 从 `feature` 翻到 `review`,再 spawn 一个 headless session,prompt
专门写给 reviewer:

1. 跑 `/security-review`,对比 campaign 起始与当前的 diff
2. 用 Agent tool 起 4 个并行 general-purpose subagent:
   - Testability reviewer
   - Maintainability reviewer
   - Performance reviewer
   - Design-consistency reviewer
3. 把结果拼成 `.engineering/implementation/.harness/review-report.md`
4. commit 这份 report
5. 标 `phase: done`,退出

链到此停止。打开 review report 看:

```bash
$EDITOR .engineering/implementation/.harness/review-report.md
```

## 第 5 步:继续 engineering 生命周期

开一个全新 Claude session。SessionStart hook 注入 autodrive 摘要;engineering
skill 从 implementation 阶段往后走:

```
/harness-engineering advance
```

implementation gate 再跑一次验证(若装了 discipline,通过 `/completion-verify`),
进 test 阶段。test 阶段跑 multi-persona review。release 阶段在
`release.approved` 上等你最后一次 `--confirm`。然后 ops 阶段。

## 第 6 步:冻结 eval 基线

ops 阶段的 brief 会指引 executor 跑:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root . --create
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root . --run --mark-baseline
```

这会把 `test-report.json` 通过的测试抽成 `EVAL-NNN`,在 `lifecycle.json`
里记下 baseline run id。

几个月后,代码或模型变了,任何人在 PR 里都能跑:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root . --run
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root . --compare baseline
```

任何 EVAL 从 pass 翻到 fail,exit 1 并打印每条回归的 id。

## 中途中断

随时可以:

```bash
# 软停 — 下一次 Stop tick 会退出
touch .engineering/implementation/.harness/autodrive.fail

# 或彻底删配置(以后 Stop tick 都是 no-op)
rm .engineering/implementation/.harness/autodrive.json
```

或在 Claude session 内:

```
/harness-plan autodrive off
```

## 常见故障与对策

| 现象 | 原因 | 修复 |
|---|---|---|
| autodrive 日志出现 "ERROR: cannot find `claude` binary" | Stop hook 子进程的 `PATH` 里没有 `claude` | 在 shell init 里 `export CLAUDE_BINARY=...` 或软链到 `/usr/local/bin` |
| 链跑到第 N 轮停了,`phase=done` 但 feature 没全完 | 撞到 `max_iterations` 上限 | `harness_autodrive.py --enable --max-iterations 50`,清掉 fail marker(如有) |
| session 结束后 autodrive log 没新增 | Stop hook 没触发(多半是 Ctrl-C 杀的,不是自然退出) | 重开 Claude,`/exit` 让会话自然结束;或跑一次 `/harness-plan` 推下一个 feature |
| feature 的 `git commit` 报 "nothing to commit" | feature 实现没真正改 tracked 文件 | 看该 feature 的 checkpoint 知道做了什么;考虑 feature scope 是否合理 |
| Stop hook exit 0 但没 spawn | 之前失败留下了 `.harness/autodrive.fail` | `rm .harness/autodrive.fail` 后 `/harness-plan autodrive on` 续跑 |

## 成本模型

- 每个 feature 大约 1 个 Claude session
- implementation 末尾 1 个 review session
- 3 个 risk gate 各 1 次
- ops + eval baseline 1 次

10-feature 的 campaign 大约 14 次完整 Claude session,每次 10–20 分钟
(看 feature 复杂度)。token 预算按此估。

## 第一次跑请用小例子

不要直接拿真项目当首测。挑个玩具:

```
/harness-engineering "build a CLI that prints fibonacci(N)"
```

3 个 feature 上下,~30 分钟跑完,大约 $5 token。先看清楚链怎么走,再正式
上手大 campaign。
