# Quiet two-day Observation Board trial

**Private deployment verified:** 2026-10-23 19:35:53.528 UTC. Planned observation interval ends 2026-10-25 19:35:53.528 UTC, measured from that verification rather than from preparation. The base is final run-006 revision `f6cd5de26e30264947907aaa64526ba3e2e10c2a`, not the preserved run-003 demo.

## Access and isolation

The board is bound only to loopback under an existing non-root account. For an authorized operator, retain strict SSH host verification and run:

```sh
ssh -N -L 127.0.0.1:18080:127.0.0.1:<trial-port> <existing-ssh-alias>
```

Then open `http://127.0.0.1:18080/` on that client. Obtain the existing alias and trial port through the private operator handoff; no host address, account name or private filesystem path is published here. This is not a phone-accessible public URL. Temporary verification forwards were closed.

There is **no public URL** and no new public listener, firewall rule, domain, TLS setup, credential, Tailscale login, system service or persistent access change. Read-only inspection found no existing web/TLS route; Tailscale is installed but NeedsLogin and has no Serve/Funnel configuration. Public access requires a separate explicit access-route decision. Noindex/unlisted naming is not access control; existing SSH is the access boundary here.

Neutral public content uses Observation Board and Service 01–10. It contains no company/provider names, probe URLs, company support address or infrastructure mapping. The real target configuration/mapping and full comparison logs remain private on Priory outside the served directory. Only index.html, status.json and robots.txt are served; private/config/source paths return 404, POST returns 405. Header and meta noindex/nofollow/noarchive plus robots Disallow are present. They supplement, not replace, access control.

The original evaluated run-006 source is preserved by hash. The trial copy changes only title/notes presentation, a narrowly allowed local trial-notes anchor and noindex metadata. `evidence/presentation-delta.json` and `presentation.diff` record the exact delta; no collection/history/transition/freshness/delivery/polling logic was altered. This is a presentation/configuration delta, not a new clean-room regeneration. Focused export, neutral-content/private-URL, route-isolation/header and actual-browser smoke checks passed. Notes deliberately state this is not a customer support service.

## Observation and comparison

The ten current source-mapped public GET probes run every 900 seconds, with their existing expected codes/keywords and five-second timeouts. No authenticated business workflows, transactions or customer writes are performed. For this reversible trial only, stale evidence becomes unknown after 1800 seconds; browser refresh is 60 seconds with a three-second fetch deadline. These are explicit trial settings, not new production promises. External email/GitHub notification delivery is disabled; the delivery worker sends only to a separate controlled loopback sink.

Two reference views are retained privately:

1. Main-branch per-service history, including recorded observation timestamps. First samples were dated May 16 and therefore not time-aligned with the trial; they are not treated as truth.
2. The exact summary endpoint used by the current public page, identified by reading its linked entry/component assets: `master/history/summary.json` at the existing raw-content source. It responds HTTP 200 with ten services but no per-observation timestamps. The comparison records fetch times, content hashes, coverage/status changes noticed and candidate observation times; fetch time is never substituted for source observation time.

No current discrepancy is scored as a candidate failure merely because an old/undated summary says up. The completion report distinguishes coverage, candidate freshness, transitions seen, unavailable references and unknown reference freshness. The existing implementation is not triggered, repaired or reconfigured during the trial.

## Operation and completion report

The isolated directory is supplied in the private operator handoff. `source/trial.py` owns the loopback board/sink and bounded collection loop. `source/live_reference.py` owns only read-only live-summary comparison at the same cadence/deadline. Current process identities and commands are in private runtime/trial.json and runtime/live-reference-process.json. Existing demo and unrelated services remain untouched. This is not an installed reboot-persistent service; host/process failure is a trial limitation, and raw logs survive for diagnosis.

At the planned end, collection/comparison cease and the scripts write runtime/completion-report.json and completion-report.md, with live-reference-completion.json retained separately and merged when the main report is available. Reports include cycle/failure counts, state transitions, reference coverage and timestamp caveats. No report or alert is posted externally. The report must be read before asserting a successful two-day outcome.

For an early stop, inspect the two recorded commands against their `/proc/<pid>/cmdline` first, then SIGTERM **only matching trial-owned PIDs**; do not signal by generic process name. The supervisor writes a report marked stopped. Do not delete runtime evidence or restart into the same trial record without an explicit continuation decision. A new trial uses a new directory/interval.

## Public access pending

No public exposure is approved at this checkpoint. A separate temporary HTTPS route proposal is pending; no tunnel, DNS, firewall or persistent access change has been made. Running collection remains independent of that decision.
