# Groundhog Day status experiment

Python 3 standard library only. This is a runnable standalone collector and static exporter, not an activated production service. All example settings below are synthetic experiment choices; operators must select their own interval, timeouts, staleness and support policy.

Create `config.json` outside the public output directory:

```json
{
  "title": "Groundhog Day status",
  "support_url": "https://example.invalid/support",
  "services": [
    {
      "id": "booking",
      "name": "Booking check",
      "url": "http://127.0.0.1:8091/health",
      "kind": "first_party",
      "impact": "New bookings may be delayed; existing washes can continue.",
      "expected_codes": [200],
      "keywords": ["ready"],
      "timeout_seconds": 2,
      "stale_after_seconds": 30
    }
  ]
}
```

Only test against loopback synthetic endpoints. A fixture returning `ready` with 200 succeeds; change it to 502 and then back to 200 for the failure/recovery sequence. A reachability service can use `kind: "provider_reachability"`, `expected_codes: [401]`, and `keywords: []`. Missing required keywords and network timeouts are failures. Add a new service then export without collecting to see unknown evidence. Use `--now 2026-10-23T12:00:00Z` on collect/export for deterministic evidence and later timestamps for stale presentation. Explicit UTC offsets of +00:00 also work.

```sh
python3 status.py collect --config config.json --db status.sqlite --output public
python3 status.py export --config config.json --db status.sqlite --output public
python3 status.py run --config config.json --db status.sqlite --output public --interval 10 --iterations 3
python3 status.py run --config config.json --db status.sqlite --output public --interval 10
```

The final command continues until Ctrl-C; Ctrl-C exits cleanly. Each cycle probes registered services sequentially, commits all observations and transitions in one SQLite transaction, then exports. Dependency failures still give exit 0; configuration, database and export failures give exit 1. Sleep occurs between cycles, so cycle duration adds to the selected interval. Do not run multiple collectors against the same ledger. Restart the same command with the same DB to retain incidents and history. Export performs no HTTP probes and can run separately from the monitor.

Serve **only** the generated public directory. Choose an unused local port, for example:

```sh
python3 -m http.server 8092 --bind 127.0.0.1 --directory public
```

Visit `http://127.0.0.1:8092/`. Stop serving with Ctrl-C. The HTML embeds safe evidence and uses no remote assets or runtime requests, so a separately served copy continues loading when the monitor/database is offline. JavaScript rechecks evidence age every second; reload does not renew evidence. Without JavaScript all states are explicitly snapshot observations. Provider reachability has limited scope and cannot establish credentials or complete business workflow health.

`index.html` and `status.json` are each replaced atomically. A reader requesting both files during export can see adjacent generations; use their generated timestamp to correlate. A disk/export failure may leave the prior complete file, whose evidence still ages visibly. Avoid publishing config or the private database. Public history includes at most 200 observations and 200 incidents per active service; the private SQLite ledger retains all observations for this modest experiment. Archive/rotate it under an operator-selected retention policy for longer operation. Responses are transient, bounded to 2 MiB and are never stored; only generic safe reasons, timing and status codes are saved. Removing a service from config excludes its evidence and incidents from subsequent public exports while retaining the private ledger.

For backup, stop the collector with Ctrl-C and use SQLite's backup facility (includes committed WAL evidence):

```sh
python3 -c "import sqlite3; a=sqlite3.connect('status.sqlite'); b=sqlite3.connect('status-backup.sqlite'); a.backup(b); b.close(); a.close()"
```

Keep config and the backup private. To restore, stop all processes using the DB, choose a fresh DB filename, copy the backup there, and point `--db` at that file. Export again before resuming monitoring. Do not copy only a live main DB while omitting its WAL. Collectors and exports require writable DB/output locations.

Later deployment requires operator review of actual endpoints, permissions, evidence policies and customer impact text; endpoint activation, hosting, TLS, DNS and cutover remain operator work with applicable approval. Publish only the two generated public files to independent static hosting and establish supervised monitoring, backups, retention and operational ownership. No existing workload or public server is installed here. A future notification adapter can poll the incident ledger or `status.json`; no messaging transport is configured and no delivery is claimed. There are no promises of staff action or recovery time.
