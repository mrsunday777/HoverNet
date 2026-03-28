# Hover Foundation

The proven hover product is exactly 3 things:

1. Continuous polling
- hover is cron-backed
- the worker returns to idle after every tick
- no manual re-priming between tasks

2. Fresh explicit unlocks
- every release/resend gets a fresh signal id
- the signal is targeted to one consumer
- the signal type must match the consumer contract

3. Execute, prove, return
- consume the unread signal
- do the bounded work
- write proof of what happened
- advance the cursor
- return to hover

Anything outside those 3 things is support code, not the product.

## Architecture Notes: Hover Lifecycle Distinctions

### Builder Hover (Long-Lived Cron)
- Runs continuously as a daemon process (cron-backed)
- Designed for indefinite operation with daily restarts
- Workers (builders) remain online persistently
- Expected to remain responsive across multiple tasks
- Offline detection and reassignment required (>600s grace period)
- F002/F003 risks: cascading failures when offline, stale markers requiring GC

### CP Agent Hover (Session-Bounded)
- Runs for bounded session duration with explicit exit
- Designed to return to IDE after session completion
- Workers (CP agents) expected to go offline when session ends
- Offline cycling is **by design, not a bug**
- No reassignment needed (session-scoped work)
- When in persistent hover mode, CP agents face same F002/F003 risks as builders
- GC thresholds (900s) apply equally to both patterns

### Risk Parity
CP agents entering persistent hover mode inherit builder constraints:
- Invalid dispatch cycling without all-tried detection
- Stale hover markers blocking new work
- Cascade-fail deadlocks when dependencies fail
- Requires same monitoring, GC, and recovery mechanisms as builder queues
