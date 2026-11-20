# Groundhog Day status service (`status.service`), clean-room build

This build follows `contracts/status/service.intent.md` (rev 5). It is a runnable **experiment**. It is not live, not deployed and not
production policy. It needs only `python3` and its standard library. You install nothing, and it contacts no external
service. All example data is synthetic Groundhog Day, and every example endpoint is on loopback.

## Files

| File | Purpose |
|---|---|
| `status.py` | Entry point: `collect`, `export`, `run`, `deliver` |
| `demo.py` | Loopback synthetic dependencies and notification sink (`fixtures`), plus a scripted end-to-end exercise (`scripted`) |
| `example-config.json` | Synthetic config that matches `demo.py fixtures --port 8701 --sink-port 8702` |
| `test_status.py` | The builder's own loopback-only checks (`python3 test_status.py`) |
| `QUESTIONS.md` | Ambiguities found and the choices made for them |

## Commands

```
python3 status.py collect --config CONFIG --db DB --output DIR [--now UTC_ISO]
python3 status.py export  --config CONFIG --db DB --output DIR [--now UTC_ISO]
python3 status.py run     --config CONFIG --db DB --output DIR --interval SECONDS [--iterations N]
python3 status.py deliver --config CONFIG --db DB --max-events N
```

* `collect` makes one HTTP GET per registered service, using that service's `timeout_seconds`. That deadline also covers
  reading the body. Within one SQLite transaction it saves the observations, the incident transitions and their outbox
  events. It then replaces `status.json` and `index.html` atomically (temp file, fsync, rename). With `--now`,
  observations are stamped at that instant and the export renders at it. `collect` never sends notifications.
* `export` renders from the ledger without probing, at `--now` or the current UTC time.
* `run` repeats `collect` every `--interval` seconds, either `--iterations` times or until Ctrl-C/SIGTERM. Either way
  it stops cleanly with exit 0.
* `deliver` is the separate notification worker. It POSTs at most `--max-events` pending outbox events, oldest first,
  to `notification_url` as `application/json`. Each POST has a 5-second deadline. Any 2xx marks the event delivered;
  anything else leaves it pending for a later run. Delivery is at least once, so receivers must deduplicate by `id`
  (also sent as the `Idempotency-Key` header). `deliver` holds no database write lock while it waits on the network,
  never probes, needs no `--output` and does not rewrite public files. The next export shows the updated `delivered`
  flags. With no `notification_url`, it attempts nothing.

Exit codes: 0 means the cycle completed, even when dependencies fail. 2 means invalid arguments or config. 3 means a
database error. 4 means the public files could not be written.

## Classification and state

* **Success:** the HTTP code is in `expected_codes` and every keyword appears in the body (case-insensitive; only the
  first 1 MiB is read). Anything else is a **failure**, with a safe reason: unexpected code, missing content, timeout,
  connection refused or a network error. Redirects are not followed.
* **Published state** at the render time: no observation, or one older than `stale_after_seconds`, is **unknown**. The
  last observation and its time are kept and shown. Evidence exactly at the limit still counts as fresh. A fresh
  success is **healthy** and a fresh failure is **impaired**. A service recovers on the next fresh success; there is no
  debounce.
* **Incidents:** the first failure opens one. Further failures change nothing. The next success resolves it with that
  observation's timestamp. Unknown or stale never resolves an incident. When `notification_url` is configured, each open
  or resolve writes exactly one outbox event with a stable `evt-…` id, in the same transaction.
* A green `provider_reachability` check is labelled on the page as **not** proving account credentials or end-to-end
  business health.
* If a service is removed from the config, it disappears from public output, along with its incidents and events. Its
  private ledger rows remain.

## The public page

`index.html` is self-contained: inline CSS and JS, no external assets, and a CSP that allows only same-origin
`status.json` fetches. It carries the safe model in `<script id="status-data" type="application/json">`. Its test hooks
are `[data-service-id][data-state]` cards with a `.state` badge reading Healthy / Impaired / Unknown on a green / red /
amber background, `time[datetime]`, `#support-link` (in the header, inside the first viewport), `#summary` and
`#banner`.

* The page re-checks freshness against the browser's `Date.now()` at load and every 0.5 s. Evidence that ages past
  `stale_after_seconds` turns Unknown. `#banner` warns that the snapshot may be out of date once `generated_at` is older
  than the smallest `stale_after_seconds` on the page.
* Over http(s), the page fetches the relative `status.json` at load and then every `refresh_seconds`. Each fetch is
  aborted after `refresh_timeout_seconds` (`AbortController`), and the busy flag is released at that deadline. A
  failed, invalid or older model is ignored, so it can never renew evidence.
* Opened as a local file, the page does not poll, but it still re-checks age.
* Without JavaScript, the page is a labelled snapshot of past observations.

### Proposed defaults (implementation choices, not customer obligations)

* `refresh_seconds` defaults to **5** when absent (record `refresh-seconds-default`). `refresh_timeout_seconds` defaults
  to **3** (record `refresh-timeout-default`). Both are configurable.
* There is **no** default for `--interval`, `timeout_seconds` or `stale_after_seconds`. They are explicit operator
  settings (record `operator-selected-timing`), and the values in `example-config.json` are synthetic.
* Retention is a placeholder (record `retention-policy-placeholder`). The ledger keeps the newest 1000 observations per
  service, 200 resolved incidents per service, and the newest 1000 delivered events. Open incidents and pending events
  are never pruned. Public output shows the last 20 observations per service, 50 incidents and 50 events.

## Operations (loopback only)

The `PORT` values below are your choice; the examples use 8080, 8701 and 8702.

1. **Synthetic dependencies and sink** (terminal 1):
   `python3 demo.py fixtures --port 8701 --sink-port 8702`.
   To break a dependency: `curl -s 'http://127.0.0.1:8701/_control?service=booking&mode=502'`. Other modes are `ok`,
   `503`, `nokeyword`, `slow` and `401`.
   To change the sink: `curl -s 'http://127.0.0.1:8702/_control?mode=503'` (`ok`, `503` or `slow`).
2. **One collection:**
   `python3 status.py collect --config example-config.json --db ledger.sqlite3 --output public`
3. **Monitor loop** (terminal 2):
   `python3 status.py run --config example-config.json --db ledger.sqlite3 --output public --interval 30`.
   **Clean stop:** press Ctrl-C, or send SIGTERM. Nothing is installed as a system service.
4. **Delivery worker** (terminal 3), as a separate operator loop. **Start** it with:
   `while true; do python3 status.py deliver --config example-config.json --db ledger.sqlite3 --max-events 20; sleep 10; done`.
   **Stop** it with Ctrl-C. Stopping it never affects collection or publication; pending events wait in the ledger.
5. **Serve the public site** (terminal 4):
   `python3 -m http.server 8080 --bind 127.0.0.1 --directory public`, then open `http://127.0.0.1:8080/`. The site
   keeps working with the monitor, ledger and dependencies all stopped. The page then shows the evidence ageing to
   Unknown, and the out-of-date banner.
6. **Export without the monitor:**
   `python3 status.py export --config example-config.json --db ledger.sqlite3 --output public`. This makes no probes.
7. **Backup** (safe while running; uses SQLite's online backup API):
   `python3 -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close()" ledger.sqlite3 backup.sqlite3`.
   **Restore:** stop `run` and `deliver`. Then copy `backup.sqlite3` over `ledger.sqlite3`, delete any
   `ledger.sqlite3-wal` and `ledger.sqlite3-shm` files, and run `export` to republish. Copying `public/` is enough to
   back up the published site.
8. **Scripted exercise:** `python3 demo.py scripted --workdir demo-run`. It runs healthy → HTTP 502 → recovery, has a
   failing sink leave events pending, then drains them. It also checks that no private body or probe URL reaches the
   public files.
9. **Builder checks:** `python3 test_status.py`. These are loopback only and write scratch files under
   `./.test-scratch`, or under `$STATUS_TEST_TMP` if set.

## Readiness: what is proven, and what is not

**Shown here, on loopback with synthetic data:**
* collection, classification and incidents
* the durable outbox and at-least-once delivery to a generic sink
* atomic static export
* the page's freshness, polling and hung-fetch recovery logic

The page script was exercised by the builder under a stub DOM with a virtual clock, not in a real browser.

**Not done, and remaining operator work that needs applicable approval:**
* activating real endpoints (probe routes, codes, keywords and the `.dev`/`.com` host question)
* production cadence, timeouts, freshness and retention policy
* the real support destination
* any authenticated notification transport (SMTP or GitHub) and its credentials
* public hosting, TLS, DNS, process supervision, scheduled backups, and cutover/rollback

The help text, support URL and all config values in this directory are **experiment values, not production support
policy**. A 2xx from the generic sink does not prove anyone received the notification.

**Steps for a later deployment** (do not perform them without approval):
1. Choose and approve the timing and retention values.
2. Write a production config with the approved endpoints and support route.
3. Run `run` under an approved supervisor.
4. Run `deliver` against an approved transport adapter.
5. Publish `public/` through any static host with TLS and DNS.
6. Schedule ledger backups.
7. Rehearse rollback by repointing DNS or the host to the previous site.
