#!/usr/bin/env zsh
# ── Claude Code: telemetry / non-essential network traffic ──────────────
#
# Verified against Claude Code v2.1.251. Each variable below was confirmed
# present in the shipped binary; presence proves the build reads the name,
# not the exact semantics behind it.
#
# Scope note: none of this stops prompts, file contents, or command output
# reaching Anthropic — that is the model API itself. Whether conversations
# are used for training is an account-level Privacy setting, not an env var.
# Per the docs, the master switch also leaves the WebFetch domain safety
# check in place.
#
# Side effects: Claude Code stops updating itself (`claude update` still
# works), and with feature flags off, Remote Control is unavailable.
#
# Undoing: unset the variables. Setting CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC,
# DISABLE_TELEMETRY, or DISABLE_ERROR_REPORTING to 0 or false still opts out.

# Master switch. Suppresses all traffic Anthropic classifies as
# non-essential: the auto-updater, error reporting, usage telemetry, and
# feature-flag fetches. The individual flags below are redundant with this
# but explicit, and stay correct if the definition of "non-essential" ever
# narrows.
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

# Statsig usage analytics — the product-metrics pipeline (which commands
# you run, session counts, feature adoption). This is the main "telemetry".
export DISABLE_TELEMETRY=1

# Sentry crash and error reporting. The binary ships a DSN pointing at
# o1158394.ingest.us.sentry.io; this stops stack traces being uploaded.
export DISABLE_ERROR_REPORTING=1

# GrowthBook feature-flag fetches from cdn.growthbook.io. Outbound
# config pulls that carry an identifier for flag bucketing.
export DISABLE_GROWTHBOOK=1

# OpenTelemetry metrics/logs exporter. Off by default; pinned to 0 so an
# inherited OTEL_* env or a future default flip cannot switch it on.
export CLAUDE_CODE_ENABLE_TELEMETRY=0

# Performance "vitals" emitter — latency and render-timing samples,
# separate from the Statsig pipeline above.
export CLAUDE_CODE_DISABLE_VITALS_EMITTER=1

# Auto-update version checks. Largely moot under a Homebrew-managed
# install, but it removes the startup ping to the release endpoint.
# Manual `claude update` still works.
export DISABLE_AUTOUPDATER=1

# Removes /feedback, which uploads your conversation transcript to
# Anthropic. Disabling it means the transcript can't be sent by accident.
export DISABLE_FEEDBACK_COMMAND=1

# Older name of DISABLE_FEEDBACK_COMMAND, which Claude Code still accepts;
# kept so versions that only know the old name are covered too.
export DISABLE_BUG_COMMAND=1

# Suppresses in-product feedback surveys and their responses.
export CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1
