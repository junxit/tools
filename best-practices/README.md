# Overview

Write-ups on engineering practice — the reasoning behind how I like to work, rather than code.

Unlike the other folders here, nothing in this one is executable. These are documents meant to be read,
argued with, and linked to during a code review when it is easier to point at a written argument than to
make it from scratch again.

## Small pull requests

[`Small-PRs.md`](Small-PRs.md) — why review quality and merge latency degrade as a pull request grows, and
the specific patterns for splitting work that *feels* atomic: refactor-before-behavior, vertical slices,
expand / migrate / contract, stacked PRs, and dark launching. Ends with a pre-flight checklist.
