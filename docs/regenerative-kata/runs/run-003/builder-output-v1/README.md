# Groundhog Day status experiment

Python 3 standard library only. This is runnable capability, not an activated production service or production support policy. No endpoints, hosting, domains or messaging have been activated. All included destinations are synthetic loopback or example.invalid.

Choose available local ports and policy values. The example uses dependency/sink port 8765, static site port 8766, refresh 2 seconds, timeout 1 second and freshness 20 seconds purely as experiment values. Change example.json if using another dependency port. An omitted refresh_seconds uses the proposed implementation choice of 5 seconds. Notification delivery uses a finite 5-second timeout.

## Repeatable loopback demo

From this directory, start `python3 demo.py --port 8765` in one terminal. In another:

```
python3 status.py export --config example.json --db demo.sqlite --output public
python3 -m http.server 8766 --bind 127.0.0.1 --directory public
```

Open http://127.0.0.1:8766 to see unknown absent evidence. In a third terminal run:

```
python3 status.py collect --config example.json --db demo.sqlite --output public
```

The already-open page polls relative status.json. Change synthetic state and collect after each change:

```
printf '%s' '{"code":502,"body":"synthetic failure"}' > demo-state.json
python3 status.py collect --config example.json --db demo.sqlite --output public
printf '%s' '{"code":200,"body":"Groundhog ready"}' > demo-state.json
python3 status.py collect --config example.json --db demo.sqlite --output public
```

The page recovers automatically; demo-events.jsonl contains opened and resolved events. Repeat failure collections to verify only one opening. Stop/restart the demo sink to exercise pending retry; stopping it also impairs the synthetic dependency. Receiver deduplication must use the stable event id: delivery is at least once, including a crash after receipt but before delivery acknowledgement commits. With notification_url omitted, delivery is disabled. Export never probes or delivers.

For keyword failure use body `missing`; timeout uses `{"code":200,"body":"Groundhog ready","delay":2}`. For expected 401 reachability set expected_codes to [401], keywords to [], kind to provider_reachability and demo code to 401. Restore example policy afterward. Add another service id to demonstrate absent evidence using export before collect. Stop collecting for more than 20 seconds to see the browser turn unknown; reload preserves evidence age. Export with a future timezone-aware `--now` exercises stale server output. Removed services and their incidents/events disappear from subsequent public exports while private history remains.

## Operation

```
python3 status.py run --config example.json --db demo.sqlite --output public --interval 5 --iterations 3
python3 status.py run --config example.json --db demo.sqlite --output public --interval 5
python3 status.py export --config example.json --db demo.sqlite --output public
```

Interval, timeout and staleness are operator choices. Omit iterations for continuous monitoring. Ctrl-C cleanly stops monitor, demo or static server. Dependency failure is a successful observation cycle (exit 0); invalid config/storage/export exits nonzero. HTTP statuses outside expected_codes and missing required keywords impair the check. Only a fresh successful observation recovers it. Stale evidence does not close incidents.

Each output file is replaced atomically; concurrent readers can briefly see adjacent generations between the two replacements. Browser fetching failure retains the previous model and its original timestamps. No-JS pages explicitly describe snapshots. Local file viewing has freshness reassessment but omits HTTP polling. Public files contain safe configured display metadata, safe observation results and incidents; the private config contains endpoint destinations. Never serve the config/database directory. Config display text itself must be public-safe: it is escaped but intentionally shown. Probe response bodies are only checked transiently, never persisted. History exported per service is the latest 100 observations; durable SQLite rows remain available privately, without accumulating process-memory state across cycles.

Back up a stopped monitor with `cp demo.sqlite demo-backup.sqlite`; restore with the monitor stopped using `cp demo-backup.sqlite demo.sqlite`, then export again. For online backups use Python sqlite3.Connection.backup rather than copying an active database. Keep backups/config outside the served public directory. A new DB is initialized automatically; an inaccessible or corrupt DB is an error.

Later deployment requires operator review of actual endpoints, public names/impact, support route, expected codes/keywords, finite timeout/freshness/refresh/interval policy, retention and backup policy, filesystem permissions, hosting/TLS/DNS/cutover, and any external notification transport with applicable approval. No authenticated email or GitHub integration is implemented. The durable outbox and public notification_events are generic adapter boundaries; delivered means the configured sink returned 2xx, not that a person received a message. No staff action or recovery ETA is promised.
