Replicate my Claude Code statusline. Before making any changes, do a safety pass:

- If `~/.claude/settings.json` exists and contains a `statusLine` key, print its current value verbatim so I can see what's being replaced.
- If `~/.claude/statusline.sh` already exists, copy it to `~/.claude/statusline.sh.bak` (overwriting any prior `.bak`) before writing the new version.
- If the existing `statusLine.command` points to a different script path, mention that path explicitly — that file will be left on disk but no longer invoked.

Then do two things:

**1. Create `~/.claude/statusline.sh`** with exactly these contents, then `chmod +x` it:

```bash
#!/bin/bash

# Read JSON input from stdin
input=$(cat)

# Extract basic info
current_dir=$(echo "$input" | jq -r '.workspace.current_dir')
model_name=$(echo "$input" | jq -r '.model.display_name // .model.id')
session_name=$(echo "$input" | jq -r '.session_name // empty')
pr_number=$(echo "$input" | jq -r '.pr.number // empty')
pr_review_state=$(echo "$input" | jq -r '.pr.review_state // empty')

# Token usage statistics
total_input=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
total_output=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // 0')

# Cost and session activity (provided directly by Claude Code)
total_cost=$(echo "$input" | jq -r '.cost.total_cost_usd // 0')
total_cost_fmt=$(printf "%.2f" "$total_cost" 2>/dev/null || echo "$total_cost")
lines_added=$(echo "$input" | jq -r '.cost.total_lines_added // 0')
lines_removed=$(echo "$input" | jq -r '.cost.total_lines_removed // 0')
duration_ms=$(echo "$input" | jq -r '.cost.total_api_duration_ms // 0')

# Human-readable API (active) time
format_duration() {
    local ms="$1"
    local total_sec=$(( ms / 1000 ))
    local h=$(( total_sec / 3600 ))
    local m=$(( (total_sec % 3600) / 60 ))
    local s=$(( total_sec % 60 ))
    if [ "$h" -gt 0 ]; then
        printf "%dh %dm" "$h" "$m"
    elif [ "$m" -gt 0 ]; then
        printf "%dm %ds" "$m" "$s"
    else
        printf "%ds" "$s"
    fi
}
duration_fmt=$(format_duration "$duration_ms")

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
# Format: user@host:path (branch) | Model | Tokens: in/out | Context: X% | Cost: $X.XX | Lines: +N/-N | PR #N (state) | Time: Xm Ys [session]
printf "\033[1;32m%s@%s\033[0m:\033[1;34m%s\033[0m%s \033[0;90m|\033[0m " \
    "$user" "$host" "$dir_display" "$git_branch"

printf "\033[1;35m%s\033[0m \033[0;90m|\033[0m " "$model_name"

printf "\033[1;33mTokens:\033[0m \033[0;36m%s\033[0m/\033[0;36m%s\033[0m \033[0;90m|\033[0m " \
    "$total_input_fmt" "$total_output_fmt"

if [ "$used_pct" != "null" ] && [ -n "$used_pct" ]; then
    printf "\033[1;33mContext:\033[0m \033[0;36m%.1f%%\033[0m \033[0;90m|\033[0m " "$used_pct"
fi

printf "\033[1;33mCost:\033[0m \033[1;32m\$%s\033[0m \033[0;90m|\033[0m " "$total_cost_fmt"

printf "\033[1;33mLines:\033[0m \033[0;32m+%s\033[0m/\033[0;31m-%s\033[0m \033[0;90m|\033[0m " \
    "$lines_added" "$lines_removed"

if [ -n "$pr_number" ]; then
    if [ -n "$pr_review_state" ]; then
        case "$pr_review_state" in
            approved) state_color="0;32" ;;
            changes_requested) state_color="0;31" ;;
            pending) state_color="0;33" ;;
            *) state_color="0;90" ;;
        esac
        printf "\033[1;33mPR:\033[0m \033[0;36m#%s\033[0m \033[%sm%s\033[0m \033[0;90m|\033[0m " \
            "$pr_number" "$state_color" "$pr_review_state"
    else
        printf "\033[1;33mPR:\033[0m \033[0;36m#%s\033[0m \033[0;90m|\033[0m " "$pr_number"
    fi
fi

printf "\033[1;33mTime:\033[0m \033[0;36m%s\033[0m" "$duration_fmt"

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
    "command": "<absolute path to ~/.claude/statusline.sh on this machine>"
  }
}
```

Verify `jq` is installed (the script depends on it); install via Homebrew if missing. Confirm the script is executable when done.

Note on cost/usage across resumed sessions: the script is stateless — every figure it shows (`cost.total_cost_usd`, `cost.total_lines_added`/`removed`, `cost.total_api_duration_ms`, and the `context_window.*` token counts) is supplied directly by Claude Code in the status-line JSON payload on each render. Claude Code derives those running totals from the session transcript at `~/.claude/projects/<slug>/<session-id>.jsonl`, so they survive interruption + `--resume` as long as you resume the same session ID on the same machine. No extra setup is required.
