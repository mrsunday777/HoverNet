---
description: Stop the hover loop cleanly without losing state.
---

# Hover Off

Stop the active hover runtime:

1. **Cancel the cron job** — use CronDelete to remove the hover tick
2. **Preserve state** — do NOT reset cursor, do NOT delete completions
3. **Write final state** — update `runtime/hover.json` with `"last_result": "stopped"`
4. **Report** — confirm hover is stopped, show final cursor position

The agent can be restarted later with `/hover` — it will resume from the current cursor position.
