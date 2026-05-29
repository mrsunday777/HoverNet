# Basic Local Loop

This example uses the public HoverTools MCP server.

Suggested flow:

1. Create a workspace with `hover_init`.
2. Send a task with `signal_send`.
3. Read the task with `bus_read`.
4. Ack the cursor with `bus_ack`.
5. Write proof with `completion_write`.

All generated runtime state stays inside your chosen workspace under
`.hovernet/`.
