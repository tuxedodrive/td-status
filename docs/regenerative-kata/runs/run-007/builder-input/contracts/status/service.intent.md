# status.service — Groundhog Day standalone status service

## Purpose

A runnable status service that monitors an explicit registry of HTTP
dependencies, keeps durable observation and incident history in SQLite, queues
incident notifications for a separate delivery worker, and publishes a static
public status site that stays serviceable and honest about evidence age while
the monitor, database, dependencies or notification sink are unavailable.

| Rev | Date | Change | Driver |
|---|---|---|---|
| 1 | 2026-10-23 | Collector, SQLite ledger, static export, browser freshness, scoped impact, configured help (run 002 contract) | User expanded the kata from page-only to replacement capability (journal, "Human decision — expand to replacement capability") |
| 2 | 2026-10-23 | Durable outbox notifications and open-page polling (run 003 extension) | Run 002 had no delivered alert transport and an open page never refreshed (journal, "Run 003 hypothesis") |
| 3 | 2026-10-23 | Support must be prominent in the initial phone viewport | Run 003 visual review found support only after ten service cards (journal, "Run 003 results and a real visual finding") |
| 4 | 2026-10-23 | Separate bounded `deliver` worker; finite abortable refresh deadline; `#summary`/`#banner` test interface; publication policy in public JSON (runs 005/006 contract) | Independent audit reproduced alert delivery delaying export by ~6.114 s and one hung fetch blocking all later polls (journal, "Independent artifact audit") |
| 5 | 2026-11-20 | Restated in Covenant heavy form: numbered obligations, superseded text retired as I38, explicit choices moved to decision records, title no longer says "run 005". No requirement added or dropped. | td-meta#176 covenant-form experiment (run 007) |

Regenerator questions from earlier rounds: none were recorded.

## Scope

Owns: the `status.py` command line (`collect`, `export`, `run`, `deliver`),
the config file format, the private SQLite ledger (observations, incidents,
notification outbox), the public export (`index.html`, `status.json`), the
page's browser behaviour, a loopback synthetic dependency/sink demo, and the
operations and readiness instructions.

Does not own: production endpoint activation, hosting, TLS, DNS, cutover,
process supervision or system-service installation, authenticated
notification transports (email, GitHub or any other), real support routing,
and receivers of notifications (which must deduplicate). It sends no
automatic external messages.

## Environment facts

- Python 3 standard library only, including `sqlite3` for storage and
  `http.server` for loopback serving; checked by the evaluator running
  `python3 status.py ...` and `python3 -m http.server` on Priory.
- The public site is plain files served by any static file server; checked by
  the evaluator serving the export with `python3 -m http.server --bind
  127.0.0.1` while the monitor and dependencies are stopped.
- Browser behaviour uses only browser-native APIs (`fetch`, `AbortController`
  or equivalent, `Date.now`); checked by headless-browser cases at phone
  390×844, square 720×720 and tablet 820×1180.
- Test dependencies, sinks and support destinations are synthetic: loopback
  HTTP fixtures and `https://support.example.invalid/...`.

## Public surface

Commands:

- `python3 status.py collect --config CONFIG --db DB --output DIR [--now UTC_ISO]`
- `python3 status.py export --config CONFIG --db DB --output DIR [--now UTC_ISO]`
- `python3 status.py run --config CONFIG --db DB --output DIR --interval SECONDS [--iterations N]`
- `python3 status.py deliver --config CONFIG --db DB --max-events N`

Config JSON (persisted format):

- top level: `title`, `support_url`, `services` (array); optional
  `notification_url`, `refresh_seconds`, `refresh_timeout_seconds`
- each service: `id`, `name`, `url`, `kind` (`first_party` or
  `provider_reachability`), `impact` (customer-readable scope),
  `expected_codes` (integer list), `keywords` (string list),
  `timeout_seconds` (positive), `stale_after_seconds` (positive)

Public `status.json` (persisted format):

- top level: `generated_at`, `title`, `support_url`, `refresh_seconds`,
  `refresh_timeout_seconds`, `services`, `incidents`, `notification_events`
- each service: `id`, `name`, `kind`, `impact`, `state`
  (`healthy`/`impaired`/`unknown`), `observed_at` (null if absent),
  `http_status`, `description`, `stale_after_seconds`, `history` (ordered
  observations, safe fields only)
- each incident: `service_id`, `opened_at`, `resolved_at` (nullable), safe
  description
- each notification event: `id`, `service_id`, `type` (`opened`/`resolved`),
  `observed_at`, `delivered` (boolean)

Notification POST body (persisted format): JSON with stable `id`,
`service_id`, `type` (`opened`/`resolved`), `observed_at` and safe
`description`, sent with `Content-Type: application/json`.

Public `index.html` browser test interface:

- each visible service card carries `data-service-id` and `data-state`
- each card's `.state` element visibly says `Healthy`, `Impaired` or `Unknown`
- observation times in `time[datetime]`
- `#support-link`, `#summary`, `#banner`
- `script#status-data` with `type="application/json"` carrying the safe public model

Private ledger: SQLite holding observations (timestamp, outcome, HTTP code if
available, elapsed milliseconds, safe failure reason), incidents and the
notification outbox. Table layout is the builder's choice.

#### Modules

`status.py` is the required entry point (every command above invokes it).
The demo, example config and README are the builder's to name.

## Invariants

### status.service.I1 — Standard library and browser-native code only
- **scope:** the whole component
- **must:** use the Python standard library plus browser-native HTML, CSS and JavaScript only; no package installation, external services, authentication or deployment
- **why:** the spike forbids a new framework and deployment, and Priory work runs without installs (td-meta#176, "First experiment")
- **kind:** non-functional
- **record:** stdlib-only
- **status:** active

### status.service.I2 — An explicit registry monitored, a static public site published
- **scope:** `collect`, `run`, `export`
- **must:** monitor the explicit registry of HTTP dependencies in the config and publish an independently serveable static public site
- **why:** run 002 selected an explicit registry and a static public page independent of monitor and dependency uptime as essential replacement capabilities (journal, "Run 002 — next hypothesis")
- **kind:** functional
- **record:** static-public-export
- **status:** active

### status.service.I3 — The published site outlives the monitor, database and dependencies
- **scope:** the public export, the browser page
- **must:** the published site still loads and reveals aging evidence while the monitor and its SQLite database are offline; neither assets nor page requests depend on monitored services; both HTML and model are independent of monitored dependencies; collector and sink failures leave the published static files serviceable
- **why:** run 002 selected a public page independent of monitor and dependency uptime; its operations exercise served the site with monitor and dependencies stopped (journal, "Run 002 results")
- **kind:** non-functional
- **record:** static-public-export
- **status:** active

### status.service.I4 — Public output exposes nothing private
- **scope:** `index.html`, `status.json`, the embedded model
- **must:** public output never exposes probe URLs, response bodies, private headers, filesystem paths, stack traces or credentials
- **why:** the public site is world-readable; every functional evaluator since run 002 plants a private body sentinel and checks it never appears
- **kind:** security
- **status:** active

### status.service.I5 — No automatic external messaging
- **scope:** the whole component
- **must:** send no automatic external messages; activate no authenticated messaging transport or real destination; never fabricate delivery
- **why:** no external integration or notification delivery is authorised; a durable feed is not delivered-notification parity (journal, "Run 003 hypothesis")
- **kind:** security
- **record:** synthetic-loopback-only
- **status:** active

### status.service.I6 — collect observes every service once and publishes atomically
- **scope:** `status.py collect`
- **must:** make one observation per registered service by HTTP GET with that service's finite configured timeout; save observations transactionally; export public files atomically; render at `--now` when supplied
- **why:** no recorded failure; carried unchanged from the run 002 contract's collect boundary
- **kind:** functional
- **status:** active

### status.service.I7 — A completed cycle exits 0; invalid input exits nonzero
- **scope:** `collect`, and `run` (same behaviour as collect)
- **must:** exit 0 for a completed observation cycle even when dependencies fail; treat non-2xx HTTP responses as observations, not a process crash; exit nonzero for invalid config, DB or export errors
- **why:** no recorded failure; carried from the run 002 contract ("a completed observation cycle"); run 002 tested timeout without crashing the cycle and duplicate-registry rejection
- **kind:** functional
- **status:** active

### status.service.I8 — Outcome classification
- **scope:** `collect`, `run`
- **must:** an observation is a success if and only if its HTTP code is in `expected_codes` and every configured keyword is present (keyword comparison may be case-insensitive); an HTTP failure or a missing keyword is impaired; a network or timeout failure is impaired with safe explanatory text, never healthy
- **why:** the agreed sequence is healthy → received 502 shown red with a clear failure description → fresh success green (td-meta#176, "First experiment"); provider checks expect an unauthenticated 401 (run 002)
- **kind:** functional
- **status:** active

### status.service.I9 — Persisted observation fields, never bodies or secrets
- **scope:** the private ledger
- **must:** persist each observation's timestamp, outcome, HTTP code if available, elapsed milliseconds and safe failure reason; never retain response bodies or secrets
- **why:** no recorded failure; carried from the run 002 contract; the private-body sentinel check covers the public side
- **kind:** persisted-format
- **status:** active

### status.service.I10 — export renders without probing
- **scope:** `status.py export`
- **must:** perform no probes and render state at the supplied `--now` or the current UTC time
- **why:** an operator can republish or restore a site while the monitor is stopped (run 002 operations: export without monitor, backup/restore)
- **kind:** functional
- **status:** active

### status.service.I11 — Absent or stale evidence is unknown
- **scope:** `export` and every export performed by `collect`/`run`
- **must:** a newly registered service with no observations is unknown; missing evidence, or evidence older than `stale_after_seconds`, is unknown, retaining the last known observation and its timestamp without presenting it as current health; fresh success is healthy; fresh failure is impaired; evidence exactly at the freshness limit may remain fresh
- **why:** the original uncertainty/freshness obligation; run 001 did not exercise missing or stale data and that limit was preserved, not upgraded (journal, "Run 001 — browser follow-up")
- **kind:** functional
- **record:** stale-evidence-is-unknown
- **status:** active

### status.service.I12 — Recovery on the next fresh success, no debounce
- **scope:** `collect`, `run`, `export`
- **must:** a service recovers to healthy on the next fresh success, with no debounce
- **why:** the agreed green → red → green sequence; the incumbent's five-failure debounce was deliberately not copied (journal, "Run 002 — next hypothesis")
- **kind:** functional
- **record:** no-debounce
- **status:** active

### status.service.I13 — run loops collect, bounded or until Ctrl-C
- **scope:** `status.py run`
- **must:** perform N cycles with `--interval` seconds of sleep between them, each with the same behaviour as `collect`; with `--iterations` omitted, loop continuously under operator control and stop cleanly on Ctrl-C; install no system service
- **why:** run 002 tested a bounded monitoring loop; the run 002 contract forbids system-service installation
- **kind:** functional
- **status:** active

### status.service.I14 — Interval, timeout and staleness are explicit operator settings
- **scope:** `run --interval`, `timeout_seconds`, `stale_after_seconds`
- **must:** treat the collection interval, probe timeout and staleness horizon as explicit operator-selected settings, not user-prescribed defaults
- **why:** run 002 labelled cadence, stale horizon and timeout as operator values with synthetic proposals; no production policy has been chosen
- **kind:** non-functional
- **record:** operator-selected-timing
- **status:** active

### status.service.I15 — Config file format
- **scope:** `--config`
- **must:** read the config JSON exactly as listed in the Public surface, including optional `notification_url`, `refresh_seconds` and `refresh_timeout_seconds`
- **why:** no recorded failure; run 002 contract plus the run 003 and runs 005/006 optional keys
- **kind:** persisted-format
- **status:** active

### status.service.I16 — Config validation
- **scope:** `--config` on every command
- **must:** reject duplicate or empty service ids, an empty registry, URL schemes other than http/https, URLs with userinfo, and invalid status or policy values; `notification_url` must be http/https with no userinfo; `refresh_seconds` and `refresh_timeout_seconds` must be positive and finite; real public endpoint configuration is supported (tests never contact providers)
- **why:** no recorded failure; carried from the run 002 contract ("Treat config strings as untrusted"); run 002 tested duplicate-registry rejection only
- **kind:** security
- **status:** active

### status.service.I17 — Config and model strings are untrusted
- **scope:** `index.html`, `#status-data`, browser rendering
- **must:** treat config strings as untrusted and HTML-escape them; accept a `support_url` only with https or mailto, never script or file; never inject untrusted model strings with `innerHTML`; escape HTML script terminators in the embedded model
- **why:** no recorded failure; carried from the run 002 and run 003 contracts; the public page renders operator-supplied text
- **kind:** security
- **status:** active

### status.service.I18 — Durable observations and transition incidents
- **scope:** the private ledger, `collect`, `run`
- **must:** keep durable observations and transition incidents in SQLite; the first failure opens an incident; the next success resolves it with evidence timestamps; consecutive failures do not create duplicate incidents
- **why:** run 002 selected durable observation and transition history as an essential replacement capability
- **kind:** functional
- **record:** sqlite-ledger
- **status:** active

### status.service.I19 — History survives restart; unknown never resolves an incident
- **scope:** the private ledger, `export`
- **must:** restarting or re-exporting preserves history; unknown or stale presentation does not mark an incident resolved
- **why:** run 002 tested persisted restart/history; the run 002 contract states that unknown/stale presentation must not falsely resolve an incident
- **kind:** functional
- **status:** active

### status.service.I20 — Removing a service removes it from public output
- **scope:** `export`, `status.json`, `index.html`
- **must:** a service safely removed from config is no longer displayed, nor are its incidents or notification events, in public output; private historical DB retention may remain
- **why:** run 002 tested safe registry removal; a retired check must not keep reporting
- **kind:** functional
- **status:** active

### status.service.I21 — Modest, bounded history
- **scope:** the private ledger, public history, process memory
- **must:** keep modest historical data for the experiment; hold no unbounded process-memory state
- **why:** no recorded failure; carried from the run 002 contract; retention policy itself is unresolved (td-meta#176, "Remaining choices include freshness/retention policy")
- **kind:** non-functional
- **record:** retention-policy-placeholder
- **status:** active

### status.service.I22 — Self-contained public files
- **scope:** the public export
- **must:** export `index.html` plus `status.json`, self-contained, fetching no network or external assets
- **why:** run 002 selected a page independent of monitored-platform assets (run 003 readiness matrix, "no monitored-platform assets required")
- **kind:** non-functional
- **record:** static-public-export
- **status:** active

### status.service.I23 — Public status.json format
- **scope:** `status.json`, `#status-data`
- **must:** publish the fields listed in the Public surface, with `history` ordered and holding safe fields enough for the test sequence (success → received 502 → success, expected 401 reachability, keyword failure, timeout, absent service evidence, stale evidence, restart/history, and minor-impact impairment); carry `title`, `support_url`, `refresh_seconds` and `refresh_timeout_seconds` so the browser reuses the explicit publication policy when new models arrive; require no environment-specific JS constants outside this model; include no probe URL or body
- **why:** the open page re-renders from new models, so policy must travel with the model (runs 005/006 contract)
- **kind:** persisted-format
- **status:** active

### status.service.I24 — The page shows state, time, impact, limits and history
- **scope:** `index.html`
- **must:** render current services with meaningful healthy/impaired/unknown text and a green/red/amber distinction, the time of each observation, per-service impact and evidence limits, incident history, and a visible support link even when all checks are green
- **why:** the agreed first experiment: a failure is shown red with a clear description and timestamp (td-meta#176)
- **kind:** functional
- **status:** active

### status.service.I25 — Impact is scoped, never "everything is down"
- **scope:** `index.html`, `#summary`
- **must:** a noncritical outage must not announce that every wash is down; the scoped summary says, for example, that some listed checks are impaired or unknown, not that all operations are unavailable
- **why:** the original proportionate-impact obligation (td-meta#176); run 002 tested minor-impact impairment
- **kind:** functional
- **status:** active

### status.service.I26 — Provider reachability is not business health
- **scope:** `index.html`, services of kind `provider_reachability`
- **must:** a green provider reachability check explicitly does not prove account credentials or end-to-end business health
- **why:** an expected unauthenticated 401 proves only reachability (run 002 selected clear provider limitations)
- **kind:** functional
- **status:** active

### status.service.I27 — No promises of staff action or recovery time
- **scope:** `index.html`
- **must:** make no promises of staff action or a recovery ETA
- **why:** no recorded failure; carried from the run 002 contract; generated help text is an experiment value, not production support policy
- **kind:** functional
- **status:** active

### status.service.I28 — Browser test interface
- **scope:** `index.html`
- **must:** give each visible service card `data-service-id` and `data-state`; have its `.state` element visibly say Healthy, Impaired or Unknown with a computed green, red or amber colour or corresponding background, so state is not conveyed by colour alone; show each timestamp in `time[datetime]`; link support with `id="support-link"`; put the scoped summary text in `#summary` and the publication-age warning in `#banner`; embed only the safe public model in `script id="status-data" type="application/json"`
- **why:** the frozen independent browser evaluator reads exactly these hooks; they are test-interface choices, not a prescribed visual design
- **kind:** persisted-format
- **record:** browser-test-interface
- **status:** active

### status.service.I29 — The browser re-assesses freshness itself
- **scope:** page JavaScript
- **must:** reassess freshness using `Date.now` at load and at least every second; change a service to unknown when its evidence ages; show a `#banner` warning that the snapshot may be out of date when `generated_at` ages; never reset data age merely by reloading
- **why:** run 002's first browser oracle conflated old observations with an old publication; both must be shown (journal, "Run 002 results and evaluator corrections")
- **kind:** functional
- **record:** stale-evidence-is-unknown
- **status:** active

### status.service.I30 — Without JavaScript the page is a labelled snapshot
- **scope:** `index.html` without JavaScript
- **must:** clearly label statuses as snapshot observations and never claim current live health
- **why:** no recorded failure; carried from the run 002 contract's honest-uncertainty obligation
- **kind:** functional
- **status:** active

### status.service.I31 — Readable, accessible, responsive, no horizontal overflow
- **scope:** `index.html` at phone, square and tablet sizes
- **must:** follow an accessible, readable phone/square/tablet layout with no horizontal overflow
- **why:** the original responsive obligation (td-meta#176); run 001 checked nine viewport cases
- **kind:** non-functional
- **status:** active

### status.service.I32 — Support is a real configured destination
- **scope:** `#support-link`, `support_url`
- **must:** support is the actual configured navigable destination (tests use a safe example.invalid URL), not a fake message saying help is available without a route
- **why:** run 001's illustrative help was not a real support route, and that limit was recorded (journal, "Run 001 — browser follow-up")
- **kind:** functional
- **status:** active

### status.service.I33 — Support is prominent in the initial viewport
- **scope:** `#support-link` at phone, square and tablet viewports
- **must:** the configured support route is prominent near the page heading or persistently available, inside the initial phone, square and tablet viewport, even when all checks are healthy; requiring users to scroll past the service cards to find it does not satisfy easy-to-find help
- **why:** run 003 visual review found support only after ten service cards, far below the initial phone viewport, which the earlier link-exists check missed (journal, "Run 003 results and a real visual finding")
- **kind:** functional
- **record:** support-prominence
- **status:** active

### status.service.I34 — Synthetic Groundhog Day examples on loopback
- **scope:** example config, demo, tests the builder supplies
- **must:** all example data is synthetic Groundhog Day; synthetic test config URLs are loopback only; tests never contact providers
- **why:** no real integration is authorised (td-meta#176, "Expanded completion criterion")
- **kind:** security
- **record:** synthetic-loopback-only
- **status:** active

### status.service.I35 — Operations instructions
- **scope:** the builder's README or equivalent
- **must:** provide local loopback-only public-site serving instructions (`python3 -m http.server --bind 127.0.0.1` with an operator-selected port), the monitor loop, clean stop, start/stop of the separate delivery worker, backup/restore, export without the monitor, and the steps needed for a later deployment
- **why:** reproducible operations are part of replacement capability (td-meta#176, "Expanded completion criterion")
- **kind:** functional
- **status:** active

### status.service.I36 — Readiness notes do not claim it is live
- **scope:** the builder's README or equivalent
- **must:** state that generated help text and configuration are experiment values, not production support policy, and that actual endpoint activation, hosting/TLS/DNS/cutover and notification transport remain operator work with applicable approval; demonstrate runnable capability without claiming it is already live
- **why:** each run's readiness claim must distinguish proven behaviour from activation (run 003 readiness matrix)
- **kind:** non-functional
- **status:** active

### status.service.I37 — A loopback synthetic dependency and sink demo
- **scope:** builder-supplied demo
- **must:** provide a minimal repeatable loopback synthetic dependency/sink demo with operations instructions
- **why:** run 003 introduced the notification boundary and needed a repeatable local exercise of it
- **kind:** functional
- **status:** active

### status.service.I38 — Pending notifications are posted after each collect and monitor cycle
- **scope:** `collect`, `run`
- **must:** (retired) after collect and on each monitor cycle, POST pending events to `notification_url`; non-2xx or network error leaves them pending for a later collect retry
- **why:** run 003 introduced it; the independent audit then reproduced three two-second deliveries holding back the public export: the old healthy page stayed visible ~6.114 s before showing impairment (journal, "Independent artifact audit")
- **kind:** ordering
- **status:** retired — superseded by I40 (delivery worker) and I41 (collection never waits on delivery); do not implement

### status.service.I39 — One durable outbox event per incident transition
- **scope:** the private outbox, `collect`, `run`, `deliver`
- **must:** with no `notification_url`, attempt no delivery; with one configured, each opened or resolved incident transaction creates exactly one durable outbox event with a stable id, `service_id`, `type` (opened/resolved), `observed_at` and safe description; consecutive failures do not duplicate events
- **why:** run 002 had no alert transport; a durable outbox lets a later adapter deliver without losing or repeating transitions (journal, "Run 003 hypothesis")
- **kind:** functional
- **record:** at-least-once-delivery
- **status:** active

### status.service.I40 — deliver is a separate, bounded, at-least-once worker
- **scope:** `status.py deliver`
- **must:** attempt at most `--max-events` pending events, POSTing each as JSON to `notification_url` with a finite timeout and `Content-Type: application/json`; any 2xx marks the event delivered; non-2xx or transport failure leaves it pending for a later retry and loses no event; never resend delivered events; do not collect, probe or need `--output`; need not rewrite public files (a later export may expose updated `delivered` flags); a separate operator loop may invoke it; install no automatic worker; delivery is at least once, so receivers must deduplicate by stable id
- **why:** replaces I38 after the run 003 audit showed in-line delivery delaying publication by ~6.114 s
- **kind:** functional
- **record:** delivery-separate-worker
- **status:** active

### status.service.I41 — Collection and publication never wait on delivery
- **scope:** `collect`, `run`, `deliver`, the private ledger
- **must:** `collect` and `run` only commit observations, incidents and outbox events and publish; they never POST notifications or wait on a sink; network waiting in `deliver` must not hold a write transaction or lock that prevents collection; sink latency or backlog must not extend collection or publication cadence; sink failure never loses committed observations or export; the private ledger is the durable queue shared by collector and delivery worker
- **why:** the run 003 audit: delivery coupled to collection delayed the public export ~6.114 s (journal, "Independent artifact audit")
- **kind:** ordering
- **record:** delivery-separate-worker
- **status:** active

### status.service.I42 — Notification payloads are safe
- **scope:** POST bodies, `notification_events`
- **must:** contain no URLs, response bodies or private details; `status.json` `notification_events` exclude events of removed services
- **why:** no recorded failure; carried from the run 003 extension; run 003's alert evaluator checks the payload for the private probe URL
- **kind:** security
- **status:** active

### status.service.I43 — An open page polls and recovers without reload
- **scope:** page JavaScript when served over HTTP(S)
- **must:** an already-open page fetches the relative `status.json` every `refresh_seconds` (default when absent: record `refresh-seconds-default`), replaces the safely rendered component and incident data on a successful valid fetch, and re-evaluates observation freshness; it recovers impaired→healthy from a new successful observation without manual reload; help and provider/scope text are preserved; the default is documented as an explicitly proposed implementation choice; static local-file rendering may omit polling but still re-evaluates freshness; `refresh_seconds` remains configurable
- **why:** run 002's open page never showed new observations (journal, "Run 003 hypothesis")
- **kind:** functional
- **record:** refresh-seconds-default
- **status:** active

### status.service.I44 — A failed refresh never renews evidence
- **scope:** page JavaScript
- **must:** a failed, timed-out or invalid fetch cannot renew timestamps or fabricate recovery; old evidence becomes unknown on its existing deadline
- **why:** run 003's failed-refresh browser cases established that a failed refresh must not renew old evidence (run 003 README)
- **kind:** functional
- **record:** stale-evidence-is-unknown
- **status:** active

### status.service.I45 — Each poll has a finite, abortable deadline
- **scope:** page JavaScript
- **must:** each poll uses the finite configured `refresh_timeout_seconds` (positive finite; default when absent: record `refresh-timeout-default`) with `AbortController` or equivalent cancellation; a single hung fetch releases the busy state and permits later polls, so the page can recover from a newer successful observation; in the synthetic 1-second refresh / 0.5-second deadline scenario, a stalled first fetch followed by available recovery recovers within 4 seconds
- **why:** the run 003 audit reproduced one unresolved fetch keeping the page busy forever: one call only, the service stayed impaired while recovery was available (journal, "Independent artifact audit")
- **kind:** non-functional
- **record:** hung-fetch-recovery-budget
- **status:** active

## Decisions

| Decision | Value | Reason | Record |
|---|---|---|---|
| Toolchain | Python 3 stdlib + browser-native HTML/CSS/JS | no framework, no installs | stdlib-only (system) |
| Data and endpoints in examples/tests | synthetic Groundhog Day, loopback | no approved integrations | synthetic-loopback-only (system) |
| Public site | static `index.html` + `status.json` | survives monitor/DB/dependency outage | static-public-export |
| Storage | SQLite private ledger | durable history and outbox queue | sqlite-ledger |
| Recovery | next fresh success, no debounce | agreed green→red→green sequence | no-debounce |
| Stale/absent evidence | unknown, last observation kept | honest uncertainty | stale-evidence-is-unknown |
| Interval, probe timeout, stale horizon | explicit operator settings; no user-prescribed default | no production policy chosen | operator-selected-timing |
| Retention | modest, bounded; policy unset | placeholder for a JPB decision | retention-policy-placeholder |
| Notification delivery | separate `deliver` worker over the ledger | in-line delivery delayed export | delivery-separate-worker |
| Delivery semantics | generic JSON POST, at least once, 2xx = delivered | receivers dedupe by stable id | at-least-once-delivery |
| Page refresh interval | 5 s when `refresh_seconds` absent | proposed implementation choice | refresh-seconds-default |
| Page refresh deadline | 3 s when `refresh_timeout_seconds` absent | proposed implementation choice | refresh-timeout-default |
| Hung-fetch recovery budget | 1 s refresh / 0.5 s deadline → recovered within 4 s | evaluation policy for the failure boundary | hung-fetch-recovery-budget |
| Support placement | inside initial phone/square/tablet viewport | run 003 finding | support-prominence |
| Browser hooks | `data-service-id`, `data-state`, `.state`, `#support-link`, `#summary`, `#banner`, `#status-data` | frozen evaluator interface | browser-test-interface |

Worked example the decisions must reproduce exactly. A model whose
`refresh_seconds` is 1 and `refresh_timeout_seconds` is 0.5 is loaded over
HTTP while its first `status.json` fetch never resolves and later fetches
return all services healthy: the first fetch is aborted at about 0.5 s, a
later poll succeeds, and every service card shows `data-state="healthy"` by
4 s after load.

## Orderings

- `collect`: save each cycle's observations, incident transitions and their
  outbox events transactionally, then export public files atomically. No notification POST occurs anywhere in this sequence
  (I41). An incident transition and its outbox event belong to the same
  transaction (I39), so a crash cannot leave one without the other.
- `deliver`: read pending events, POST outside any write transaction or lock
  that would block collection, then mark only 2xx-acknowledged events
  delivered (I40, I41). An event is never marked delivered before a 2xx.
- Public files: each public file is replaced atomically; a reader never sees
  a partially written file (I6).
- Page: render the embedded model at load, reassess freshness at load and at
  least every second (I29), poll on `refresh_seconds` (I43); replace rendered
  data only after a successful valid fetch, and release the busy state when
  the deadline aborts a fetch (I44, I45).
- Incidents: the first failure opens; consecutive failures change nothing;
  the next fresh success resolves; unknown never resolves (I18, I19).

## Known limits

- **Experiment placeholders, not policy.** The following are unresolved
  operator choices. Values used here are synthetic test values only:
  freshness horizon and retention policy (a dormant production draft
  deliberately carries null freshness); production collection cadence and
  probe timeouts; whether `.com` denotes a different canonical host from the
  configured `.dev`; the real support destination; SMTP server, From address
  and authentication; any GitHub issue credential and destination; public
  hosting, TLS and DNS; process supervision; backups; and cutover/rollback.
  Records `operator-selected-timing`, `retention-policy-placeholder` and
  `production-activation-placeholders` hold them.
- A generic sink's 2xx acknowledgement does not prove authenticated delivery
  or human receipt. A separate SMTP/GitHub adapter (run 004) is not part of
  this component.
- Support tests establish link presence, destination and placement only, not
  successful contact with an actual support service.
- Browser evaluation is desktop headless emulation at three viewports, not
  physical-device, cross-browser, full accessibility or user-comprehension
  validation.
- Long-running, load and real-provider semantics are not exercised.
- Downtime duration and incident logging beyond the ledger are not
  requirements.

## Regeneration brief

The regenerator receives only this `contracts/` directory: this intent, its
records, the system intent and records, and the convention README. It does
not receive contract tests, the evaluator, any previous implementation, any
other run, project history or the web.

Implement fresh from this Contract only. Do not look for or read another run,
old source, history, evaluator or web content. Use the Python standard
library plus browser-native HTML/CSS/JS only; install nothing; contact no
external service; do not deploy. Write the implementation and run
instructions in `builder-output/`, with `status.py` as the entry point. It
will be executed on Priory later; it must not alter any existing workloads.

Implement active obligations only. I38 is retired history. Where a record is
`approved_by: pending JPB`, implement the value it states as the experiment's
working choice.

Questions previous regenerations asked: none were recorded in runs 001–006.
If this Contract leaves something ambiguous, choose the least surprising
behaviour consistent with it and write the question in
`builder-output/QUESTIONS.md`.
