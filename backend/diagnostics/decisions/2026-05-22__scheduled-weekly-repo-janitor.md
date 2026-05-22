# 2026-05-22 — Tier 4c: Scheduled weekly repo-janitor routine

## Headline
Created remote Claude Code routine `snipersight-weekly-janitor` (id `trig_01FReLSK5jSsyP5PTQejCzHM`) that runs the repo-janitor agent every Monday at 09:00 UTC via the Sniper environment. Read-only manifest pass; never deletes; output reviewed by operator on the routines page.

## Context
Tier 4c of the workflow enhancement queue. Pattern follows §19 decisions-log discipline: drift caught weekly before it compounds is cheaper than drift discovered six months later. Operator memory notes (now archived) flagged this in the 2026-05-20 janitor manifest.

The repo-janitor agent is defined at `.claude/agents/repo-janitor.md` — read-only inventory pass that categorizes clutter / dead code / orphan tests / build artifacts / stale docs with reason codes + recommended disposition. The agent explicitly never deletes; operator approves tranches.

## Resolution

### Routine config
- **Name:** `snipersight-weekly-janitor`
- **Id:** `trig_01FReLSK5jSsyP5PTQejCzHM`
- **URL:** https://claude.ai/code/routines/trig_01FReLSK5jSsyP5PTQejCzHM
- **Cron:** `0 9 * * 1` (every Monday at 09:00 UTC)
- **Next run:** 2026-05-25T09:00 UTC
- **Environment:** Sniper (`env_01PezKjjz46oQTQPCZdQZHAu`)
- **Model:** `claude-sonnet-4-6`
- **Repo source:** `https://github.com/NobleWolf412/snipersight-trading`
- **Allowed tools:** `Bash`, `Read`, `Glob`, `Grep` — deliberately excluding `Write`, `Edit`, and Agent delegation. Read-only by construction.
- **MCP connections:** Google Calendar / Drive / Gmail attached by default (operator-side connected set); none used by the routine.

### Prompt design
Self-contained — the remote session starts with zero conversation context. Prompt explicitly:
- Cites `.claude/agents/repo-janitor.md` as the operating protocol
- Cross-references CLAUDE.md §10 standing-fix surface as a KEEP-regardless allowlist
- Instructs §12 paste-friendly output (short summary first, structured detail, raw evidence last)
- Lists hard constraints: no delete / modify / commit / push / branch
- Routes manifest to the routine page for operator review

### Notification model
No email/Slack push at this round — operator reviews the routine page weekly. If the weekly-review pattern doesn't stick (forgotten runs, drift accumulation), Tier 4d add: attach Gmail MCP + prompt-side instruction to email the summary. Deferred for now to keep this round minimal.

## Why it matters next time
Manual janitor passes happen sporadically and the gap between "I should clean this up" and "I have a quiet hour" was historically the dominant driver of compound clutter (the 2026-05-20 janitor manifest had ~30 unused frontend deps + 4 stale docs + a dozen one-shot diagnostic scripts left over from prior conversations). A weekly automated inventory pass makes the latest snapshot always available — operator's review effort becomes "scan the latest manifest, approve a tranche" instead of "where do I even start."

The routine is intentionally read-only. The slippery-slope of "let it auto-delete cruft" is exactly the failure mode §15 + §16 are designed to prevent — silent deletions of files that turned out to be load-bearing. Manual disposition is the friction that catches that.

## Carry-forward
- Re-baseline / update prompt content over time as the standing-fix surface evolves (currently hard-coded to the §10 file list from CLAUDE.md as of 2026-05-22)
- Consider adding Gmail MCP attachment for weekly digest if operator misses runs
- Consider second routine on a different cadence (monthly?) that does a deeper analysis with full backend imports — current weekly is lightweight Bash/grep only

## Affected files (commit boundary)
NEW:
- `backend/diagnostics/decisions/2026-05-22__scheduled-weekly-repo-janitor.md` (this file)

The routine itself lives in Anthropic's remote-trigger registry (not in this repo). The routine survives even if this decisions entry is removed — and vice versa — so this entry is the operator-side record of when/why it was set up.

Cross-ref: commits 6f2bad0 (Tier 3 followup + docs rewrite); CLAUDE.md §19 decisions log discipline; `.claude/agents/repo-janitor.md` (operating protocol).
