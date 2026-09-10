---
name: implementation-skill
kind: skill
stage: implementation
---

# Implement one task, step by step

1. Read the handoff; confirm the task id you were given matches one row in
   the plan's Tasks table.
2. Read that row's `files`, `criteria`, `validation_recipe`,
   `validation_args`, and `no_behaviour_change` flag.
3. Use the `codegraph-lookup` shared skill to find every existing call
   site or near-duplicate before adding new code.
4. Make the change, touching only what the Scope table permits for this
   task.
5. If you must go beyond the task's listed files or the plan's stated
   approach, note it as you go — you will record it as a deviation, not
   fold it in silently.
6. Do not run the task's validation recipes yourself; the runner runs them
   after you hand back.
7. Write the hand-back: `branch`, `head_sha`, `worktree_path`, and the
   deviation set (possibly empty, but always present) in the schema the
   handoff names.
8. Stop. One task, one invocation.
