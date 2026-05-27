Replicate my Claude Code statusline. Before making any changes, do a safety pass:

- If `~/.claude/settings.json` exists and contains a `statusLine` key, print its current value verbatim so I can see what's being replaced.
- If `~/.claude/statusline-command.sh` already exists, copy it to `~/.claude/statusline-command.sh.bak` (overwriting any prior `.bak`) before writing the new version.
- If the existing `statusLine.command` points to a different script path, mention that path explicitly — that file will be left on disk but no longer invoked.

Then do two things:

**1. Create `~/.claude/statusline-command.sh`** with exactly these contents, then `chmod +x` it:

```bash
#!/bin/bash

# Read JSON input from stdin
input=$(cat)

# Extract basic info
current_dir=$(echo "$input" | jq -r '.workspace.current_dir')
model_name=$(echo "$input" | jq -r '.model.display_name // .model.id')
session_name=$(echo "$input" | jq -r '.session_name // empty')

# Token usage statistics
total_input=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
total_output=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // 0')
remaining_pct=$(echo "$input" | jq -r '.context_window.remaining_percentage // 100')

# Calculate costs (Anthropic pricing)
# Claude Opus 4.6: $15/MTok input, $75/MTok output
# Claude Sonnet 4.5: $3/MTok input, $15/MTok output
model_id=$(echo "$input" | jq -r '.model.id')
if [[ "$model_id" == *"opus"* ]]; then
    input_cost_per_mtok=15
    output_cost_per_mtok=75
else
    input_cost_per_mtok=3
    output_cost_per_mtok=15
fi

# Calculate total cost
input_cost=$(echo "scale=4; $total_input * $input_cost_per_mtok / 1000000" | bc)
output_cost=$(echo "scale=4; $total_output * $output_cost_per_mtok / 1000000" | bc)
total_cost=$(echo "scale=4; $input_cost + $output_cost" | bc)

# Format costs with leading zero if needed
if [[ "$total_cost" == .* ]]; then total_cost="0$total_cost"; fi

# User, host, and directory info
user=$(whoami)
host=$(hostname -s)
dir_display="${current_dir/#$HOME/~}"

# Git branch
git_branch=""
if [ -d "$current_dir/.git" ] || git -C "$current_dir" rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git -C "$current_dir" --no-optional-locks branch --show-current 2>/dev/null)
    [ -n "$branch" ] && git_branch=" (${branch})"
fi

# Format token counts with commas
format_number() {
    printf "%'d" "$1" 2>/dev/null || echo "$1"
}

total_input_fmt=$(format_number "$total_input")
total_output_fmt=$(format_number "$total_output")

# Build status line
# Format: user@host:path (branch) | Model | Tokens: in/out | Context: X% | Cost: $X.XX
printf "\033[1;32m%s@%s\033[0m:\033[1;34m%s\033[0m%s \033[0;90m|\033[0m " \
    "$user" "$host" "$dir_display" "$git_branch"

printf "\033[1;35m%s\033[0m \033[0;90m|\033[0m " "$model_name"

printf "\033[1;33mTokens:\033[0m \033[0;36m%s\033[0m/\033[0;36m%s\033[0m \033[0;90m|\033[0m " \
    "$total_input_fmt" "$total_output_fmt"

if [ "$used_pct" != "null" ] && [ -n "$used_pct" ]; then
    printf "\033[1;33mContext:\033[0m \033[0;36m%.1f%%\033[0m \033[0;90m|\033[0m " "$remaining_pct"
fi

printf "\033[1;33mCost:\033[0m \033[1;32m\$%s\033[0m" "$total_cost"

if [ -n "$session_name" ]; then
    printf " \033[0;90m[%s]\033[0m" "$session_name"
fi

echo
```

**2. Merge this `statusLine` block into `~/.claude/settings.json`** (preserve all other existing keys; create the file with just this object if it doesn't exist). Use the actual `$HOME` path on this machine, not a hardcoded `/Users/Jade`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "<absolute path to ~/.claude/statusline-command.sh on this machine>"
  }
}
```

Verify `jq` and `bc` are installed (the script depends on them); install via Homebrew if missing. Confirm the script is executable when done.

Note on cost persistence across resumed sessions: the script is stateless. Cost survives session interruption + `--resume` because Claude Code itself accumulates per-turn `usage` records in the session transcript at `~/.claude/projects/<slug>/<session-id>.jsonl` and feeds the running totals to the script as `.context_window.total_input_tokens` / `.total_output_tokens`. No extra setup is required for that behavior — it works as long as you resume the same session ID on the same machine.
