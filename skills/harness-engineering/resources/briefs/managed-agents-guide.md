# Managed Agents Guide

Reference for using Claude Managed Agents as the implementation backend.

## When to Use

- Deep scope projects with > 8 features
- Long-running campaigns that benefit from autonomous execution
- When sandboxed code execution is needed
- When you want checkpoint/resume across disconnections

## When NOT to Use

- Lightweight/standard scope (local harness-plan is simpler and free)
- Offline environments (Managed Agents requires API access)
- When you need fine-grained control over each implementation step

## Session Lifecycle

```
create → pending → running → checkpointed → running → completed
                     ↓                                    ↓
                   failed                              (advance)
```

## Scripts

```bash
# Create a new session
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_managed.py \
  --create --project-root <path> --goal "..." --features-total 10

# Check status
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_managed.py \
  --status --project-root <path>

# Save checkpoint
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_managed.py \
  --checkpoint --project-root <path> --features-completed 5

# Resume from checkpoint
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_managed.py \
  --resume --project-root <path>
```

## Integration with engineering_advance.py

When `campaign-ref.json` has `"backend": "managed_agents"`:
- advance reads `managed-session.json` instead of local harness files
- Validates session status is "completed"
- Validates features_completed == features_total
- Error codes: IMPL-MA-001 (session not completed), IMPL-MA-002 (features incomplete)

## Pricing

- Standard Claude Platform token rates apply
- Plus $0.08 per session-hour for active runtime
- Sessions can run for hours autonomously

## State File

`managed-session.json` in `.engineering/implementation/`:
```json
{
  "session_id": "abc12345",
  "status": "running",
  "started_at": "2026-04-10T12:00:00Z",
  "last_checkpoint": "2026-04-10T14:30:00Z",
  "features_completed": 5,
  "features_total": 10
}
```
