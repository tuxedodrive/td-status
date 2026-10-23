# Run 003 — replacement-capable status service candidate

Working software is running on Priory in an isolated non-root stig workspace, with a fully synthetic loopback dependency, durable database, collector and independently served public page. No production endpoint, email/GitHub transport, DNS/TLS, external hosting or cutover was activated. No packages or credentials installed.

## What was demonstrated

- 20 independent functional checks: ten configured check roles, healthy and expected unauthenticated 401, 502/recovery, keyword mismatch, timeout, absent/stale evidence, persisted observations/incident history and deduplication, removed services, bounded monitoring loop, safe public data and stopped dependencies.
- Independent operations check: HTTP 200 public serving with monitor/dependencies stopped; backup/restore preserves history/incidents; temporary evaluation server stopped.
- Eight alert-boundary checks: no alert on initial health, one durable pending opening after sink 503, stable event-id retry after restart, 2xx acknowledgement, no resending delivered events, one recovery event, no duplicate success event, safe payload. Sink delivery is at least once and requires receiver deduplication. Acknowledgement does not prove a person received a message.
- 21 browser state/layout cases across phone 390×844, square 720×720 and tablet 820×1180: seven states including absent/stale evidence and client-aged publication; readable non-color status, scoped impact/provider limitations, no horizontal overflow, prominent real configured support destination.
- Six loopback HTTP browser cases: already-open page recovers from new status.json without reload; failed refresh does not renew old evidence and the page becomes unknown with an aging warning.
- A deliberately impaired recovery response was rejected as a negative control; correct response passed afterward.
- The actual continuously running Priory synthetic demo completed healthy → received 502 → healthy with opened/resolved local sink events delivered. Actual page was rendered in existing Mini Chrome via a temporary localhost-only SSH tunnel; tunnel then stopped.

## Clean-builder and iteration record

Fresh run-003 builder received only the source-free contract, not incumbent implementation/history/baseline or run-002 code. Contract, functional evaluator, operations evaluator and alert evaluator hashes were frozen first on Priory. Code was authored in the fresh Mini context, transferred, compiled and executed on Priory. Isolation is context/read-instruction based, not OS-enforced. The full independent evaluator is separate from implementation, invokes CLI/HTTP/DOM boundaries, and does not import application code.

Initial visual review discovered support only after ten cards, despite prior tests merely checking link existence. The stronger initial-viewport assertion failed; original implementation/contract and failure evidence are retained under builder-output-v1, builder-input/CONTRACT-v1.md and evidence/help-visibility-v1.*. Builder corrected only its own generated support location/style. Independent functional/alert/operations and all 27 browser cases then passed. No results from v1 are retroactively claimed as stronger conformance.

`evidence/frozen-inputs.sha256` is the historical pre-build manifest; its original CONTRACT.md content is retained as CONTRACT-v1.md. The later help clarification and browser evaluator are hashed in `evidence/revision-v2-inputs.sha256`. `evidence/output.sha256` identifies the corrected generated artifacts. Original output hash/evaluation records have v1 suffixes. File hashes, rather than merely prose, distinguish versions.

## Runnable operations

See builder-output/README.md for configuration and collect/export/run/backup/restore commands. Python standard library only. Serve only generated public/, never config/database directories. The generated demo.py provides a safe loopback HTTP dependency and notification sink.

The running isolated demonstration uses `/home/stig/experiments/td-meta-176/run-003/demo-runtime`. Public port **44167** and dependency/sink port **56597** are bound to 127.0.0.1 only; dynamically selected to avoid pre-existing services. Monitor interval/refresh 2 seconds, timeout 1 second and freshness horizon 20 seconds are explicit synthetic demo choices, not user-prescribed production policies. Actual recorded process identities/commands are in evidence/live-demo.json and evidence/demo-monitor-update.json; current process record on Priory is demo-runtime/processes.json.

For viewing from an authorized SSH client, choose a free local port and forward it to Priory's loopback public port, e.g. `ssh -N -L 127.0.0.1:18080:127.0.0.1:44167 stig@159.195.18.142`, preserving normal host verification, then open http://127.0.0.1:18080. This is not public deployment.

To stop only the recorded owned demo processes, from the Priory run directory run `python3 evaluation/live_demo.py stop`; it checks /proc command identity before signalling, refusing reused PIDs. No daemon/service installer or shared configuration was introduced. Stopping does not delete data. For a new run use a new isolated directory or explicitly archive the old runtime record/data after stopping.

## Replacement-readiness assessment

The application demonstrates the essential technical capability to replace the status service against controlled dependency boundaries. It is a working replacement candidate, not a claim that the production service has been switched or every incidental incumbent feature reproduced.

| Capability | Evidence / readiness |
| --- | --- |
| Explicit monitoring registry and actual HTTP observations | Ten-role synthetic HTTP evaluation; configurable expected codes, keywords, timeout and interval |
| Durable state/history and recovery | SQLite restart, incident open/resolve/dedup, backup/restore; public history preserved |
| Public status/help, scoped impact and provider limits | Browser cases and actual demo; support config is a safe test destination, not a production route |
| Honest absent/stale evidence | Server unknown state; browser aging and failed-refresh exercises; observation time never renewed by reload |
| Alerts | Durable outbox/POST/retry demonstrated with synthetic sink; no authenticated email/GitHub transport or human receipt claimed |
| Operational independence | Public static export served while monitor/dependencies stopped; no monitored-platform assets required; independent hosting still must be selected/activated |
| Responsive presentation | 27 bounded browser cases plus inspected screenshots; physical devices, accessibility/user studies and cross-browser certification remain unperformed |
| Reproducibility | Frozen spec/interface/eval versions, commands/results, hashes, generated source, fixture servers and operations docs |

Before actual replacement: review the intended canonical domain (user named .com; read-only .com request returned 404 while source-linked .dev returned 200), configure/authorize actual probes, real support destination and impact text, agree timing/retention/backup policies, choose and approve actual alert transport, and activate/supervise independent public hosting/TLS/DNS. These are explicit production activation items; no secret, external integration, spending or cutover is authorized here. Generic sink functionality is not a claim of existing email/GitHub notification parity.

Incidental incumbent implementation choices were not copied as obligations: exact framework, commit-per-check storage, graphs/response-time chart UI, RSS shape, five-failure debounce and branding. The one-502-red/fresh-success-green behavior follows the user's desired contract instead of preserving the incumbent debounce. No general brownfield characterization work started; that curiosity remains pinned.

The method has evidence from these concrete iterations, not universal validation. Long-running operations/retention/load, actual-provider semantics and real-user help/impact comprehension still require appropriate operational review; do not describe synthetic success as production assurance.
