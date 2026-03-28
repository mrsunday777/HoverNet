# HoverNet Setup — Instructions for Your Agent

**You are reading this because your user asked you to set up HoverNet.**

Follow these steps exactly. Do not skip any step. Do not improvise.

---

## Step 1: Determine Paths

Set these variables based on where HoverNet was cloned:

```
HOVERNET_DIR = <the directory containing this file>
AGENTS_ROOT = ~/Desktop/Vessel/agents    (default — user can override)
```

If the user specified a custom agents root, use that instead.

---

## Step 2: Create Agent Directories

For each of the default agents (builder, proposer, critic, synth), create the full directory structure:

```
AGENTS_ROOT/<agent_name>/
├── CLAUDE.md                                    # Copy from HOVERNET_DIR/agents/<role>/CLAUDE.md
├── shared_intel/
│   └── signal_bus/
│       ├── signals.jsonl                        # Empty file (touch)
│       ├── cursors/
│       │   └── <agent_name>_ran_hover.cursor    # Contains "0"
│       └── completions/                         # Empty directory
└── runtime/                                     # Empty directory (hover.json goes here)
```

Create these 4 agents by default:
- `builder` — copy CLAUDE.md from `agents/builder/CLAUDE.md`
- `proposer` — copy CLAUDE.md from `agents/proposer/CLAUDE.md`
- `critic` — copy CLAUDE.md from `agents/critic/CLAUDE.md`
- `synth` — copy CLAUDE.md from `agents/synth/CLAUDE.md`

**Important:** The cursor file must contain exactly `0` (the character zero, followed by a newline). Not empty. Not `1`.

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
hovernet-builder() {
    local name="${1:-builder}"
    local dir="${AGENTS_ROOT:-$HOME/Desktop/Vessel/agents}/$name"
    mkdir -p "$dir/shared_intel/signal_bus/"{cursors,completions} "$dir/runtime"
    [ -f "$dir/shared_intel/signal_bus/signals.jsonl" ] || touch "$dir/shared_intel/signal_bus/signals.jsonl"
    [ -f "$dir/shared_intel/signal_bus/cursors/${name}_ran_hover.cursor" ] || echo "0" > "$dir/shared_intel/signal_bus/cursors/${name}_ran_hover.cursor"
    [ -f "$dir/CLAUDE.md" ] || cp "HOVERNET_DIR/agents/builder/CLAUDE.md" "$dir/CLAUDE.md"
    cd "$dir" && claude
}

hovernet-proposer() {
    local dir="${AGENTS_ROOT:-$HOME/Desktop/Vessel/agents}/proposer"
    cd "$dir" && claude
}

hovernet-critic() {
    local dir="${AGENTS_ROOT:-$HOME/Desktop/Vessel/agents}/critic"
    cd "$dir" && claude
}

hovernet-synth() {
    local dir="${AGENTS_ROOT:-$HOME/Desktop/Vessel/agents}/synth"
    cd "$dir" && claude
}
```

**Important:** Replace `HOVERNET_DIR` in the alias with the actual absolute path to the HoverNet repo.

**Important:** The `hovernet-builder` alias accepts an optional name. `hovernet-builder` creates a builder named "builder". `hovernet-builder worker-5` creates one named "worker-5". This is how users scale — just open another terminal and give it a new name.

After adding aliases, remind the user to run `source ~/.zshrc` (or `source ~/.bashrc`).

---

## Step 5: Verify Setup

Run these checks and report results to the user:

1. **Directories exist:**
   - `ls AGENTS_ROOT/builder/shared_intel/signal_bus/signals.jsonl`
   - `ls AGENTS_ROOT/proposer/shared_intel/signal_bus/signals.jsonl`
   - `ls AGENTS_ROOT/critic/shared_intel/signal_bus/signals.jsonl`
   - `ls AGENTS_ROOT/synth/shared_intel/signal_bus/signals.jsonl`

2. **Cursors initialized:**
   - Each cursor file contains `0`

3. **CLAUDE.md copied:**
   - Each agent directory has a CLAUDE.md

4. **Statusline installed:**
   - `~/.claude/statusline.sh` exists and is executable

5. **Aliases installed:**
   - The shell rc file contains `hovernet-builder`

---

## Step 6: Tell the User What to Do Next

Print this message:

```
HoverNet is set up. Here's how to use it:

LAUNCH A BUILDER:
  Open a new terminal and run:  hovernet-builder
  For more builders:            hovernet-builder worker-2
                                hovernet-builder worker-3

LAUNCH THE RESEARCH LOOP:
  Terminal 1:  hovernet-proposer
  Terminal 2:  hovernet-critic
  Terminal 3:  hovernet-synth

START HOVERING:
  In each agent's session, type:  /hover

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
