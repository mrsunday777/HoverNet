# Council Monitor Runtime

Monitor runtime lets chairman and advisors self-detect work through scanners.

## Contract

1. Chairman monitor detects new briefs.
2. Chairman creates the council thread and dispatches round work.
3. Advisor monitors detect their round signals.
4. Advisors write artifacts, proof, cursor advance, and ack.
5. Chairman monitor detects round completion and advances the council.

## When To Use

Use monitor when the harness supports persistent background scan tasks and the
council should keep moving without manual terminal wake.

## Public Watcher

Run one scan:

```bash
hover-loop-watch --root <workspace-root> --loop-name council --loop-type council --agent chairman --once --json
```

Run continuously:

```bash
hover-loop-watch --root <workspace-root> --loop-name council --loop-type council --agent chairman --watch --poll-sec 30 --json --quiet-idle
```

The same one-shot scanner is exposed through MCP as `loop_watch_once`.

Claude Code users can also use the packaged public skill:

```text
.claude/skills/CouncilLoopWatch/skill.md
```

## Rule

The scanner reports readiness. It does not manufacture missing advisor work.
