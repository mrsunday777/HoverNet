# Research Monitor Runtime

Monitor runtime lets each agent keep a scanner armed for new work.

## Contract

1. Scanner watches the bus, inbox, and active thread artifacts.
2. On work, scanner emits the next actionable event.
3. Agent processes exactly one task.
4. Agent writes proof before cursor advance.
5. Agent re-arms the monitor after completion.

## When To Use

Use monitor when the harness supports persistent background watch tasks and the
loop benefits from quiet self-sustain.

## Public Watcher

Run one scan:

```bash
hover-loop-watch --root <workspace-root> --loop-name research --loop-type research --agent proposer --once --json
```

Run continuously:

```bash
hover-loop-watch --root <workspace-root> --loop-name research --loop-type research --agent proposer --watch --poll-sec 30 --json --quiet-idle
```

The same one-shot scanner is exposed through MCP as `loop_watch_once`.

Claude Code users can also use the packaged public skill:

```text
.claude/skills/RepoLoopWatch/skill.md
```

## Rule

Monitor detects work. It does not replace the role's reasoning or proof.
