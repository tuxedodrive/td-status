# Run 002 — monitoring, durable evidence and independent static serving

Fresh build from `builder-input/CONTRACT.md`; no run-001 implementation or incumbent source given to builder. Authoring occurred in a fresh Mini agent context; compilation, collection and functional/operations evaluation ran on Priory as non-root stig. Context/read restrictions provide information isolation, not OS-enforced file access isolation. No packages installed, external providers contacted, real notifications sent or production changes made.

## Result

- 20 independent functional checks passed on synthetic ten-service loopback dependencies: success, expected unauthenticated 401, 502/recovery, keyword mismatch, timeout, open/resolve incident deduplication, persisted restart/history, missing/stale evidence, registry removal, monitoring loop and safe public data.
- Separate operations check served public output with monitor/dependencies stopped (HTTP 200), verified backup/restore retained observations/incidents, and stopped its temporary loopback server.
- 21 independent browser cases passed: seven states (healthy, failed, minor impairment, recovered, stale export, client-aged publication, absent observations) × phone 390×844, square 720×720 and tablet 820×1180. Checked state/text, computed green/red/amber, provider scope/help, no horizontal overflow and client-aged warning. Existing Mini Chrome 147 local preview used; no browser installed on Priory. Three representative screenshots were visually inspected and committed; all 21 remain in the task/Priory evidence workspace.

## Reproduction and evidence

`builder-output/README.md` describes collector/export/monitor/serve/backup operations. `evaluation/evaluate.py` starts local synthetic HTTP fixtures and drives the executable CLI; `evaluation/operations.py` checks independent serving and restore. Commands/results are in `evidence/`. `evaluation/browser.py <existing-chrome-headless-shell>` renders the synthetic snapshots with evaluator-only fixed Date.now and DOM probes; results in `browser-review/results.json`.

Both original and corrected independent evaluator versions are preserved. Before any functional run, synthetic clock was corrected from a future fixed date to current-minus-140 seconds so the real-time monitor loop did not move backward; original v1 was not executed. Browser v1 failed an overbroad banner assertion: stale observation evidence is not the same as a stale publication. Browser v2 checks unknown stale cards and separately checks an aged-publication warning; no implementation modification was needed. See `evidence/browser-evaluator-correction.json`.

## Coverage and next iteration

Run-002 supports working observations, durable state/history, useful scoped public status/help, unknown/freshness behavior, tested responsive viewports and static serving while monitor/dependencies are stopped. Support is a configured safe synthetic destination; effectiveness with real users is not established. Physical devices/accessibility, actual endpoints, real alert delivery and production hosting/TLS/DNS are not verified or activated.

Identified functional gaps for replacement capability: durable incidents alone are not delivered alerts; an already-open page ages evidence but does not poll fresh generations. Run-003 revises the contract for an optional durable HTTP notification outbox and safe relative status-model polling, then regenerates in another fresh context. Preserve this run as evidence rather than patching it or claiming full replacement readiness.
