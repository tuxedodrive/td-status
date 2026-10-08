# AGENTS.md

This file provides context for AI assistants working on the TuxedoDrive status page.

## Never

1. **Never build before checking what already exists.** Search the repo (tasks, services, jobs, routes) first. If it exists, use it or fix it.
2. **Never guess when you should ask, and never ask when you should look.** Look first. If it's still unclear, ask one specific question.
3. **Never assume human error before investigating software error.** When an operator and the system disagree, the system is the suspect.
4. **Never ask permission to do your job.** If a message cites an issue, read it. If something needs routing, decide and dispatch. If you feel blocked, check what *you* can do before asking.
5. **Never ask for help before exhausting your own cheap resources.** That doesn't mean disappearing down a rathole. It means respecting other people's time.
6. **Never pass along another seat's output unchecked.** A seat's plan is a proposal until you've verified it.
7. **Never paraphrase without need.** Quote when fidelity matters. Condense only when it's worth the loss.
8. **Omit needless words.**

## What This Repo Does

This is an [Upptime](https://upptime.js.org) status page that monitors 10 critical checks TuxedoDrive depends on. GitHub Actions run checks every 15 minutes and auto-commit results.

Two checks are first-party health endpoints. The remaining external checks are provider reachability checks unless explicitly documented otherwise. A green provider reachability check does not prove TuxedoDrive credentials, account permissions, or end-to-end business workflows are healthy.

## Key Files

- `.upptimerc.yml` - Service definitions and configuration (the main file you'll edit)
- `history/*.yml` - Per-service status history (auto-generated, but must be cleaned up manually when removing services)
- `api/` - JSON data for the status page API
- `graphs/` - Response time graphs (PNG files)
- `scripts/validate-upptime-config.py` - Local/CI drift check for service counts, schedules, and generated artifacts

## Maintenance Rules

### When Removing a Service

Delete ALL artifacts in the same commit:
1. Remove the service from `.upptimerc.yml`
2. Delete `history/<service-slug>.yml`
3. Delete `api/<service-slug>/` directory
4. Delete `graphs/<service-slug>/` directory

Failure to do this causes spurious "down" alerts from stale history files.

### When Adding External APIs

1. Test the URL manually first: `curl -s -o /dev/null -w "%{http_code}" <url>`
2. Decide whether this is provider reachability or authenticated business health
3. For unauthenticated provider reachability checks, accept any expected non-5xx response and document that the check does not validate credentials
4. For authenticated business health checks, use scoped credentials and test a real low-risk workflow
5. Document the URL source in a comment if it's not obvious
6. Run `python3 scripts/validate-upptime-config.py` before committing

### When Modifying expectedStatusCodes

If you're updating expected codes because a check is failing:
1. Verify the service is actually up (not a real outage)
2. Test the actual response: `curl -s -o /dev/null -w "%{http_code}" <url>`
3. Update both `.upptimerc.yml` AND reset `history/<service>.yml` status to `up`
4. Close any spurious GitHub issues with an explanation

### Authenticated Synthetic Checks

Authenticated business-flow checks are not currently implemented in this repo. Add them as separate checks from provider reachability so the status page can distinguish "provider is online" from "TuxedoDrive integration is usable."

## Slug Naming

Upptime converts service names to slugs for file/directory names. The conversion lowercases and replaces spaces/special chars with hyphens. Examples:
- "Cloud APIs" -> `cloud-ap-is` (note: "APIs" becomes "ap-is")
- "Code Repository" -> `code-repository`
- "SMS Notifications" -> `sms-notifications`

## Common Issues

### "Service is down" but it's actually up
Usually means `expectedStatusCodes` doesn't include the actual response code. Check with curl, update config, reset history.

### Stale incidents after removing a service
History file wasn't deleted. Remove `history/`, `api/`, and `graphs/` directories for that service.

### Merge conflicts in history files
Upptime bot commits frequently. When rebasing, keep your URL/status fixes but take the bot's timestamps.

---

## Search & Retrieval

For doc lookups across td-* repos, **prefer `qmd query` over grep.** qmd indexes all six tuxedodrive repos (~939 markdown files) with BM25 + vector embeddings + LLM rerank, returning cross-repo semantic matches that grep misses.

- `qmd search "exact phrase"` — BM25 keyword, no LLM
- `qmd query "how does X work"` — hybrid semantic with rerank
- `qmd query "..." -c td-edge` — scope to a single repo
- `qmd multi-get "#docid1,#docid2"` — fetch full sources after a search

Always retrieve full source via `qmd get` or `qmd multi-get` before answering. Snippets aren't enough. See `~/cities/td-city/docs/plans/2026-05-27-qmd-librarian-benchmark.md` for the broader context on how we measure qmd's value.
