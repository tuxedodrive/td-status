# Standalone synthetic status service

Python standard library only. These commands run a local experiment, not a live production service. Run from this directory. Ports 8765/8766, collection interval 2 seconds, timeout 1 second and evidence lifetime 10 seconds are changeable demonstration choices. Browser polling defaults to 5 seconds and an abortable 3-second deadline when absent from configuration; the example explicitly selects 1 and 0.5 seconds.

1. Start the synthetic dependency/sink: `python3 demo.py --port 8765`.
2. Collect once: `python3 status.py collect --config example.json --db state.sqlite --output public`.
3. Serve only the public directory: `python3 -m http.server 8766 --bind 127.0.0.1 --directory public`. Open http://127.0.0.1:8766/.
4. Monitor in another terminal: `python3 status.py run --config example.json --db state.sqlite --output public --interval 2`. Add `--iterations 3` for three cycles. Ctrl-C stops the monitor cleanly.
5. In a separate terminal start the independent worker: `while true; do python3 status.py deliver --config example.json --db state.sqlite --max-events 10; sleep 2; done`. Ctrl-C stops this loop. Each invocation attempts at most ten events; transport timeout is a finite implementation choice of 3 seconds per event. Collection never contacts the notification sink, and no database write transaction spans network waiting. Delivery is at least once: real receivers must deduplicate stable event IDs.

Change the first service URL from `/ok` to `/fail`, collect, then change back and collect to demonstrate incident open/recovery. Consecutive failures retain one incident. `/reachability` returns expected 401. An absent keyword produces impairment; stopping the demo produces network failure. Re-export with a later `--now` to demonstrate stale evidence, or leave a page open. Restart commands with the same database to retain history. A new service appears unknown before collecting it. Remove a service from config to hide its observations, incidents and notification events while retaining private database history. No response bodies are stored.

Export without probing: `python3 status.py export --config example.json --db state.sqlite --output public`. Delivery flags become public on the next export/collect. Failed or invalid browser refreshes keep original evidence timestamps; each fetch is aborted at its configured deadline. Static output continues serving when collector/database/dependencies are unavailable. Without JavaScript it is explicitly a snapshot. Public output includes at most the last 100 observations per registered service; private SQLite history remains on disk for the experiment and should be periodically archived by the operator.

For a consistent backup, stop collection and worker, then use Python's SQLite backup API:

```sh
python3 -c "import sqlite3; a=sqlite3.connect('state.sqlite'); b=sqlite3.connect('backup.sqlite'); a.backup(b); b.close(); a.close()"
```

Restore while all database users are stopped: move the old database and any associated `-wal`/`-shm` files aside, copy `backup.sqlite` to `state.sqlite`, then export and restart the operator loops. Preserve configuration separately; it contains private endpoint routes. Publish only `public/`, never the configuration/database. Atomic replacement applies separately to each public file; model polling converges to the latest JSON.

Later production work requires operator validation of real endpoints and support route, suitable timeout/interval/freshness policy, hosting/TLS/DNS/cutover, process supervision, backup/retention policy and approval for actual notification transport. No external endpoint, authenticated integration, notification recipient, deployment, or staff response/ETA policy is activated here. The incident ledger is a generic adapter boundary, not an email or GitHub delivery integration. The configured example.invalid support route demonstrates placement and navigation only.
