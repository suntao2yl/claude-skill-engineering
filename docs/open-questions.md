# Open Questions

Decisions to make before or during implementation. Not all need answers
upfront — some will become obvious once we start building.

## Scope & positioning

1. **Is this a general framework or an opinionated workflow?**
   - General: users define their own phases and schemas.
   - Opinionated: we ship 7 phases with fixed schemas.
   - **Leaning opinionated**, with phase schemas as escape hatches.

2. **How does this relate to `harness`?**
   - Does `harness-engineering` replace `.harness/` with
     `.engineering/implementation/`?
   - Or does it keep `.harness/` intact and just reference it?
   - **Leaning: keep `.harness/` intact, reference it from
     `lifecycle.json`. Avoid forcing users to migrate.**

3. **Do we need a `harness-engineering` command surface, or reuse `/harness`?**
   - Separate `/harness-engineering` command seems cleaner.
   - Subcommands: `/harness-engineering init`, `/harness-engineering phase discovery`, etc.

## State model

4. **Single master file vs distributed state?**
   - Single `lifecycle.json` is simpler to read.
   - Distributed per-phase files are easier to evolve.
   - **Hybrid: thin `lifecycle.json` index + phase-owned sub-files.**

5. **How do we version schemas?**
   - Phases will evolve. Old projects should not break.
   - Idea: each JSON artifact carries `schema_version`; orchestrator migrates
     on read if safe, refuses if unsafe.

6. **Should phases be user-extensible?**
   - Can users add a custom `compliance` phase between test and release?
   - If yes, we need a phase-registration mechanism.

## Transitions

7. **What triggers a forward transition?**
   - Auto-advance when the previous phase's artifact passes validation?
   - Explicit user command (`/harness-engineering advance`)?
   - **Leaning: auto-advance with user confirmation for destructive or
     cross-phase-blocking transitions** (mirrors `harness` v2 auto-advance).

8. **How do we handle backward transitions cleanly?**
   - Design flags requirements as incomplete → discovery reopens → downstream
     phases go stale.
   - Need a "stale" status on artifacts and a rule that downstream phases
     refuse to execute on stale inputs.

9. **Do we support parallel phases?**
   - Can design and architecture run in parallel for the same requirement?
   - **Leaning: yes, with explicit declaration in requirements.json.**

## Phase executors

10. **Are phase executors subagents, skills, or scripts?**
    - Implementation uses the existing `harness` skill.
    - Discovery might be a subagent with a specific prompt.
    - Test might be script-driven.
    - **Likely a mix — orchestrator abstracts the executor type.**

11. **How does the orchestrator invoke `harness` cleanly?**
    - `harness` currently expects to own `.harness/` at project root.
    - Options: (a) symlink, (b) env var pointing harness at a subdir,
      (c) fork/adapt harness to accept a base path.
    - **Probably (c) — `harness` already supports `--project-root`.**

## UX

12. **What does a user see at each phase entry?**
    - A summary of upstream artifacts?
    - A checklist of this phase's expected outputs?
    - An auto-generated starter template?

13. **How do we handle "I don't want a phase"?**
    - Bug fix doesn't need discovery or design.
    - Idea: lifecycle can declare a "minimal" mode that only requires
      implementation + test.

14. **How do we avoid overwhelming users with artifacts?**
    - 7 phases × many JSON files × schemas = a lot.
    - Need a `/harness-engineering status` that condenses all to one readable view
      (like `harness_summary.py` does for a campaign).

## Not yet thought through

15. **Integration with external tools** (Jira, Figma, GitHub Issues) — do we
    import from them, export to them, ignore them?
16. **Team mode** — multiple humans working on different phases concurrently.
17. **Multi-project workspaces** — one `harness-engineering` session
    managing several related projects.
