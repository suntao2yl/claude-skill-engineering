# harness-engineering

[![Release](https://img.shields.io/github/v/release/suntao2yl/claude-skill-engineering)](https://github.com/suntao2yl/claude-skill-engineering/releases)
[![License](https://img.shields.io/github/license/suntao2yl/claude-skill-engineering)](./LICENSE)

**AI 原生软件开发的全生命周期编排器（Claude Code skill）。**

一个顶层 Claude Code skill，用 harness-plan 理论（紧凑的机器状态、结构化 artifact、确定性状态转换）在**相位级别**而非任务级别协调整个软件开发生命周期——从需求捕获到发布上线。

[English](./README.md) · 中文

---

## 这是什么

`harness-engineering` 不是 `harness-plan` 的替代品。它高一层：

```
harness-engineering  ← 生命周期编排器（本项目）
        │
        └── 调用 harness-plan 作为 implementation 相位的执行器
                 │
                 └── harness-plan 驱动 feature 级的编码
```

### 7 个相位（锁定不可扩展）

```
discovery → design → architecture → implementation → test → release → ops
                  │                ▲
                  │                │
                  └────────────────┘
                 （upstream 允许时可并行）
```

每个相位拥有一个 schema 校验的 JSON artifact。转换由脚本强制执行，不是仪式感。校验失败就阻塞 advance。上游修改会传播 stale 状态到下游。

---

## 依赖：需要 `harness-plan` skill

本 skill **把 implementation 相位委托给** [`harness-plan`](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) skill。没有 harness-plan，相位 1-3 和 5-7 能跑，但相位 4（implementation）会卡住。

**为什么不合并？**
- harness-plan 本身就是独立有用的编码工具
- 合并会强制所有 harness-plan-only 用户每次都加载 engineering 的 3500 token lifecycle 正文
- "Compose, do not embed" 是第 8 条原则

**harness-plan 应该安装在：**
- `~/.claude/skills/harness-plan/SKILL.md`，或
- 任何已安装插件提供的 `harness-plan/skills/harness-plan/SKILL.md`

---

## 安装

### 方式 A：手动（克隆仓库）

```bash
git clone https://github.com/suntao2yl/claude-skill-engineering.git && cd claude-skill-engineering

# 只装 engineering（会检查 harness-plan，缺失时 warning）：
./install.sh

# 从本地路径同时装 engineering + harness-plan：
./install.sh --with-harness-plan /path/to/harness-plan-skill

# 自定义 skills 目录：
./install.sh --prefix /custom/skills/path
```

### 方式 B：Claude Code skill 系统

如果通过 Claude 的 skill 管理器/marketplace 安装 `engineering`，**先用同样的机制安装 `harness-plan`**。engineering 的 `SKILL.md` 里有 preflight 检查，首次 `init` 会验证 harness-plan 是否存在。

---

## 快速开始

```bash
# 两个 skill 都装好之后：

# 在 Claude Code 里：
/harness-engineering init "构建一个 Python CLI 统计文件行数，输出 JSON，发布 v0.1"

# Claude 会：
# 1. 创建 .engineering/ 含 7 个相位子目录 + 种子 REQ-001
# 2. auto-drive：填 discovery → advance → 到 risk gate 暂停 → 等 --confirm
# 3. 并行填 design + architecture → 各自 advance → architecture gate 暂停
# 4. 进入 implementation → 委托给 harness-plan → 驱动 features 到 done
# 5. advance implementation（live 执行 verification commands）
# 6. 填 test-report → advance（live 执行 test commands）
# 7. 创建 git tag → advance release → release gate 暂停
# 8. 填 ops metrics → 终态
```

用户只在 **risk gate**（discovery / architecture / release 批准点）确认。其他全自动。

---

## 7 个相位

| # | 相位 | 单位 | Artifact | 验证规则 |
|---|---|---|---|---|
| 1 | `discovery` | 问题陈述 | `requirements.json` | users ≥3 字符、metrics ≥5 字符、statement ≥20 字符 |
| 2 | `design` | 设计规范 | `design-spec.json` | 每个 flow ≥2 非空步骤、components spec ≥10 字符 |
| 3 | `architecture` | ADR + 技术栈 | `stack.json` + `adrs/ADR-NNN.json` | ≥1 个 ADR 文件、声明与文件匹配 |
| 4 | `implementation` | harness-plan campaign | `campaign-ref.json` | harness-plan done==total、**live 执行**每个 verification.command |
| 5 | `test` | 测试计划 | `test-report.json` | ≥1 pass、0 fail、**live 执行** plan commands |
| 6 | `release` | 发布候选 | `release-checklist.json` | git tag 可解析、无 pending 项 |
| 7 | `ops` | 指标/事件 | `metrics.json` + `incidents/` + `postmortems/` | 最小要求 |

**Minimal 模式**（`--mode minimal`）跳过相位 1/2/3/6/7，只保留 `implementation + test`——适合 bug 修复和小功能。

---

## 关键行为

- **Live 验证**：`implementation` 和 `test` 相位 advance 时真的执行声明的命令，检查 exit code、扫描 stderr 的 `ERROR:`/`FATAL:`、校验 stdout 匹配 `expected` 模式。填假 JSON 过不了。
- **风险门**：`discovery.approved`、`architecture.approved`、`release.approved` 需要 `--confirm` 标志。到 gate 时 `advance` exit 42。
- **Stale 传播**：`revise <phase>` 把下游 artifact 标为 stale；`advance` 拒绝 stale artifact，除非加 `--refresh-stale`。
- **并行相位**：design 和 architecture 都只依赖 discovery，可以并发执行。
- **可恢复**：新 Claude 会话读 `.engineering/lifecycle.json` 就知道从哪恢复。
- **跨阶段 Lint**（v0.5.0）：`lint` 执行 7 项跨阶段一致性检查——需求覆盖、设计-测试对齐、ADR 漂移、stale 链完整性、决策密度、孤立引用、insight 积压。生命周期完成时自动运行。
- **Insight 捕获**（v0.5.0）：轻量级跨阶段反馈，不触发 stale 传播。下游阶段可记录对上游的观察、矛盾、缺口和建议。
- **原始输入保留**（v0.5.0）：`requirements.json` 中的 `raw_goal` 字段保留用户原始目标的不可变副本，与精炼后的 `problem_statement` 分离。

---

## 项目结构

```
harness-engineering/
├── SKILL.md                          # skill 入口 + auto-drive 协议
├── README.md                         # 英文
├── README.zh-CN.md                   # 中文（本文件）
├── USAGE.md                          # 操作指引
├── install.sh                        # 安装器，带 --with-harness-plan 选项
├── scripts/
│   ├── engineering_lib.py            # 共享工具
│   ├── engineering_init.py           # 创建 .engineering/
│   ├── engineering_status.py         # 单屏生命周期视图
│   ├── engineering_phase.py          # 进入相位
│   ├── engineering_advance.py        # 验证 + 推进（含 live 验证）
│   ├── engineering_revise.py         # 回退 upstream，传播 stale
│   ├── engineering_lint.py           # 跨阶段一致性检查（v0.5.0）
│   ├── engineering_insight.py        # 跨阶段反馈捕获（v0.5.0）
│   ├── engineering_learn.py          # 跨生命周期提取 learnings
│   ├── engineering_reset.py          # 归档 + 重新开始
│   └── engineering_validate.py       # 状态完整性检查
├── resources/
│   └── phase-executor-briefs.md      # 每个相位的 subagent prompt 模板
└── docs/
    ├── architecture.md               # 设计理由
    ├── phases.md                     # 相位规范
    ├── principles.md                 # 10 条指导原则
    └── open-questions.md             # 已决/延后的问题
```

---

## 状态

**v0.5.0 当前版本** — lint、insight 捕获、原始输入保留。

在两个项目上完成端到端 dogfood：
- `validation/lc-cli/` — 真实 Python CLI，11 个 pytest 通过，完整 auto-drive 闭环
- `validation/godot-ai-pet/` — Godot 4.3 AI 宠物伴侣，standard 7 相位走完

架构理由和未决问题见 `docs/`。

---

## 相关阅读

受 [awesome-harness-engineering](https://github.com/walkinglabs/awesome-harness-engineering) 启发，特别是：
- Anthropic 的 [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Anthropic 的 [effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Thoughtworks 的 [humans and agents in software engineering loops](https://martinfowler.com/articles/exploring-gen-ai/humans-and-agents.html)

---

## 许可

MIT © 2026 — 见 [LICENSE](./LICENSE)。
