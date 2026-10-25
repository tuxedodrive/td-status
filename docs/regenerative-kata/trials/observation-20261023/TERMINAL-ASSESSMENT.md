# Observation trial terminal assessment

Verified 2026-10-25 19:36:41 UTC through the existing strictly verified SSH route. No changed host key was accepted.

**PASS: the bounded private 48-hour observation and scheduled shutdown completed. Comparative correctness and full production replacement readiness remain inconclusive.**

The verified observation window was October 23 19:35:53.528 UTC through October 25 19:35:53.528 UTC (172800 seconds). Final collection completed at 19:35:53.774840; bounded local delivery and comparison finished before the supervisor recorded shutdown at 19:35:55.575210, 2.047 seconds after the deadline. There was no extension or restart. The terminal sample began at 19:35:49.686059, just before the deadline, giving 193 collections including the initial and final boundary samples.

Both recorded process IDs are absent; board and controlled local-sink listeners are closed. The supervisor manifest says `two-day interval completed`. The comparator's launch manifest has no terminal fields: its actual process absence and independently written completion report establish termination. No residual trial process was found in this bounded check; no whole-machine census is claimed.

## Results and evidence

- 193 successful collection cycles; zero collection failures. Longest completed-cycle gap: 908.272299 seconds.
- 193 successful local delivery worker invocations; zero delivery-worker failures. This does not mean 193 notifications were generated: every invocation checks the outbox. No external alerts were sent.
- Ten registered checks throughout; final state nine accepted responses and one impaired, client-sensitive denied probe. Zero observed state transitions, so no natural outage/recovery demonstration resulted from the trial. The prior controlled synthetic evaluations remain separate evidence.
- 192 successful incumbent live-summary fetches, ten records each, zero errors and one unchanged content hash. Summary fetch times cannot establish its underlying observation freshness.
- 1930 dated-history comparison samples; zero time-aligned. All reference dates remained stale/unaligned; no comparative correctness score is justified.
- Completion JSON and Markdown agree; nested live-reference report exactly equals its standalone report; raw record counts match report counts.

The impaired probe was previously reproduced as a redirect plus client-signature denial (403/error 1010), while a descriptive diagnostic client reached a login page. Neither response establishes business health or a service outage. The collector's expected-code interpretation was accurate for its received response; the probe's suitability as a customer-impact signal remains unresolved. It was not silently reconfigured.

[Machine-readable terminal evidence](evidence/terminal-reports.json) includes sanitized reports, exact terminal timestamps, reconciliation assertions and SHA256 hashes of the retained private artifacts. The original completion JSON/Markdown, standalone comparator report, final process manifest, cycle/delivery/comparison logs and database remain in the existing private trial runtime directory. No deletion or replacement occurred. Private host/account/path, target mapping, raw observations and customer information are excluded from this publication.

## Acceptance limits

This is successful operational evidence for a quiet, bounded private run and automatic shutdown. It does not establish full contract conformance, public HTTPS/phone usability, natural incident transitions, authenticated transaction health, external-alert delivery, or superiority to the incumbent. Public tunnel approval was never supplied; no public exposure, credentials, DNS, firewall, production cutover or new trial occurred. The remaining probe-policy and exposure decisions are not resolved by declaring this run complete.
