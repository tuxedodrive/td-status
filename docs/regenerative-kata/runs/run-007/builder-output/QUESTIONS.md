# Questions recorded by this regeneration (run 007)

Where the Contract left something open, I chose the least surprising behaviour consistent with it. Each choice is
listed below.

1. **Outbox events without `notification_url`.** I39 says "with one configured, each … transition creates exactly one
   outbox event". With no `notification_url`, I create no outbox events at all, so `notification_events` is `[]`.
   Turning a sink on later does not replay old transitions. Is that intended, or should events always be queued?
2. **Publication-age threshold for `#banner`.** I29 says to warn "when `generated_at` ages" but gives no threshold. I
   chose the smallest `stale_after_seconds` among the published services, with 300 s when no services are listed.
   Should this be its own policy value?
3. **`export` against a missing database.** `export` creates an empty ledger, so every service is published as
   unknown, rather than failing. An unreadable or non-SQLite file exits nonzero. Should a missing DB be an error for
   `export`?
4. **Redirects.** Probes do not follow redirects; a 3xx is judged against `expected_codes`. They also ignore
   environment proxy settings and connect directly. Are both right for real endpoints?
5. **`deliver` exit code.** `deliver` exits 0 when its pass completes, even if the sink refused events and they stay
   pending. It exits nonzero only for config or DB errors. Should a refused delivery give a nonzero exit?
6. **Delivery timeout.** The Contract asks for a finite POST timeout but sets no value or config key. I used 5 s, fixed
   in code (`DELIVERY_TIMEOUT_SECONDS`).
7. **Probe timestamp.** Without `--now`, an observation is stamped when its probe starts. With `--now`, every
   observation in the cycle is stamped at `--now`.
8. **Browser clock behind `observed_at`.** If the browser's clock is earlier than an observation, the evidence counts as
   fresh. If the exported model already says unknown (stale at export), the browser keeps it unknown.
9. **Retention numbers.** I chose 1000 observations per service in the ledger and 20 shown publicly. These are
   placeholders under `retention-policy-placeholder`.
10. **Extra public fields.** Beyond the listed fields, `status.json` adds these safe fields:
    * per service: `evidence_state`, `evidence_description`, `elapsed_ms`
    * per incident: `service_name`, `resolution`

    The browser uses them to re-assess freshness without inventing text. Are extra fields acceptable to the persisted
    format?
