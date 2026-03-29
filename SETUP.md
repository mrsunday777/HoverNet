# HoverNet Setup — Instructions for Your Agent

**You are reading this because your user asked you to set up HoverNet.**

Follow these steps exactly. Do not skip any step. Do not improvise.

---

## Step 1: Determine Paths

Set these variables based on where HoverNet was cloned:

```
HOVERNET_DIR = <the directory containing this file>
AGENTS_ROOT = <where the user's agents should live>
```

If the user specified a custom agents root, use that instead. Otherwise use the default that `setup.sh` applies on their machine.

---

## Step 2: Create Agent Directories

For each of the default agents (`orchestrator`, `builder`, `proposer`, `critic`, `synth`), create the full directory structure:

```
AGENTS_ROOT/<agent_name>/
├── CLAUDE.md                                    # Copy from HOVERNET_DIR/agents/<role>/CLAUDE.md
├── .claude/
│   └── commands/
│       ├── hover.md                             # Copy from HOVERNET_DIR/.claude/commands/hover.md
│       ├── hoveroff.md                          # Copy from HOVERNET_DIR/.claude/commands/hoveroff.md
│       └── autohover.md                         # Copy from HOVERNET_DIR/.claude/commands/autohover.md
├── shared_intel/
│   └── signal_bus/
│       ├── signals.jsonl                        # Empty file (touch)
│       ├── cursors/
│       │   └── <agent_name>_ran_hover.cursor    # Contains "0"
│       └── completions/                         # Empty directory
└── runtime/                                     # Empty directory (hover.json goes here)
```

Create these 5 agents by default:
- `orchestrator` — copy CLAUDE.md from `agents/orchestrator/CLAUDE.md`
- `builder` — copy CLAUDE.md from `agents/builder/CLAUDE.md`
- `proposer` — copy CLAUDE.md from `agents/proposer/CLAUDE.md`
- `critic` — copy CLAUDE.md from `agents/critic/CLAUDE.md`
- `synth` — copy CLAUDE.md from `agents/synth/CLAUDE.md`

**Important:** The cursor file must contain exactly `0` (the character zero, followed by a newline). Not empty. Not `1`.
**Important:** Copy the slash commands into each workspace. `/hover` is used by workers. `/autohover` is used by the orchestrator.

---

## Step 3: Install Statusline

Copy the statusline configuration so agents show clean identity in their status bar:

1. Copy `HOVERNET_DIR/.claude/statusline.sh` to `~/.claude/statusline.sh`
2. Make it executable: `chmod +x ~/.claude/statusline.sh`
3. If `~/.claude/settings.json` does NOT already have a `statusLine` entry, add:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh"
  }
}
```

If the file already has a `statusLine` entry, do NOT overwrite it — the user has their own config.

---

## Step 4: Create Launcher Aliases

Add these shell aliases so the user can type agent names directly to launch sessions:

For **bash** (`~/.bashrc`) or **zsh** (`~/.zshrc`):

```bash
# HoverNet agent launchers
hovernet-orchestrator() {
    local dir="${AGENTS_ROOT}/orchestrator"
    cd "$dir" && claude
}

hovernet-builder() {
    local name="${1:-builder}"
    local dir="${AGENTS_ROOT}/$name"
    mkdir -p "$dir/shared_intel/signal_bus/"{cursors,completions} "$dir/runtime"
    [ -f "$dir/shared_intel/signal_bus/signals.jsonl" ] || touch "$dir/shared_intel/signal_bus/signals.jsonl"
    [ -f "$dir/shared_intel/signal_bus/cursors/${name}_ran_hover.cursor" ] || echo "0" > "$dir/shared_intel/signal_bus/cursors/${name}_ran_hover.cursor"
    [ -f "$dir/CLAUDE.md" ] || cp "HOVERNET_DIR/agents/builder/CLAUDE.md" "$dir/CLAUDE.md"
    cd "$dir" && claude
}

hovernet-proposer() {
    local dir="${AGENTS_ROOT}/proposer"
    cd "$dir" && claude
}

hovernet-critic() {
    local dir="${AGENTS_ROOT}/critic"
    cd "$dir" && claude
}

hovernet-synth() {
    local dir="${AGENTS_ROOT}/synth"
    cd "$dir" && claude
}
```

**Important:** Replace `HOVERNET_DIR` in the alias with the actual absolute path to the HoverNet repo.
**Important:** Replace `AGENTS_ROOT` in the alias with the actual agents root chosen during setup.

**Important:** The `hovernet-builder` alias accepts an optional name. `hovernet-builder` creates a builder named "builder". `hovernet-builder worker-5` creates one named "worker-5". This is how users scale — just open another terminal and give it a new name.

After adding aliases, remind the user to run `source ~/.zshrc` (or `source ~/.bashrc`).

---

## Step 5: Verify Setup

Run these checks and report results to the user:

1. **Directories exist:**
   - `ls AGENTS_ROOT/orchestrator/shared_intel/signal_bus/signals.jsonl`
   - `ls AGENTS_ROOT/builder/shared_intel/signal_bus/signals.jsonl`
   - `ls AGENTS_ROOT/proposer/shared_intel/signal_bus/signals.jsonl`
   - `ls AGENTS_ROOT/critic/shared_intel/signal_bus/signals.jsonl`
   - `ls AGENTS_ROOT/synth/shared_intel/signal_bus/signals.jsonl`

2. **Cursors initialized:**
   - Each cursor file contains `0`

3. **CLAUDE.md copied:**
   - Each agent directory has a CLAUDE.md

4. **Slash commands copied:**
   - `AGENTS_ROOT/orchestrator/.claude/commands/autohover.md` exists
   - `AGENTS_ROOT/builder/.claude/commands/hover.md` exists

5. **Statusline installed:**
   - `~/.claude/statusline.sh` exists and is executable

6. **Aliases installed:**
   - The shell rc file contains `hovernet-orchestrator`
   - The shell rc file contains `hovernet-builder`

---

## Step 6: Tell the User What to Do Next

Print this message:

```
HoverNet is set up. Here's how to use it:

LAUNCH THE ORCHESTRATOR:
  Terminal 1:  hovernet-orchestrator
  In that session, type:  /autohover

LAUNCH A BUILDER:
  Terminal 2:  hovernet-builder
  For more builders:            hovernet-builder worker-2
                                hovernet-builder worker-3

LAUNCH THE RESEARCH LOOP:
  Terminal 3:  hovernet-proposer
  Terminal 4:  hovernet-critic
  Terminal 5:  hovernet-synth

START HOVERING:
  In worker sessions, type:  /hover

RUN THE RESEARCH BRIDGE:
  From <HOVERNET_DIR>:
  python3 scripts/queue_daemon.py --agents-root <AGENTS_ROOT> --interval 30

  This bridge handles synth -> builders and next-round proposer dispatch.
  The research loop keeps healing forward until the synth marks the thread CLOSED.

DISPATCH WORK:
  From any session:  python3 <HOVERNET_DIR>/examples/dispatch_example.py --agent builder --task "your task here"

CHECK STATUS:
  python3 <HOVERNET_DIR>/examples/check_status.py

READ THE RULES:
  <HOVERNET_DIR>/RULES.md — 10 non-negotiables that will break your fleet if violated.
```

---

## Notes for the Setup Agent

- Do NOT modify the user's existing Claude Code settings beyond adding the statusline
- Do NOT install anything globally (no npm -g, no pip install)
- Do NOT create agents the user didn't ask for
- If something fails, report the error clearly and suggest a manual fix
- The user may already have agents at AGENTS_ROOT — do not overwrite existing CLAUDE.md files
- If `.claude/commands/` already exists in an agent workspace, merge the HoverNet command files without deleting the user's other commands
