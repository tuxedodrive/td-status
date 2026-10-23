# Exact production configuration and remaining readiness gaps

Source: td-status `.upptimerc.yml`, blob `17d26f6800ce80753e3a8fe30de6f0607150cf92`, re-read from main; same content as pinned `f1fb70ab713bc649a13f30784da3132757edd9d5`. This is configured intent, not proof that each scheduled check or notification currently works. No live provider probes or message sends performed for this review.

## Directly carryable configuration — no invented product replacement

| Check | Exact configured GET URL | Expected codes | Required content |
| --- | --- | --- | --- |
| Production Application | https://tuxedodrive.com/health | 200 | status; healthy |
| Edge API | https://api.tuxedodrive.com/health | 200 | status |
| Payments | https://api.stripe.com/v1/charges | 400, 401 | none |
| Email Delivery | https://api.postmarkapp.com/deliverystats | 401, 422 | none |
| SMS Notifications | https://api.twilio.com/ | 200, 401, 403 | none |
| Authentication | https://accounts.google.com/.well-known/openid-configuration | 200 | none |
| Weather Service | https://api.openweathermap.org/data/2.5/weather | 401 | none |
| Pollen Service | https://pollen.googleapis.com/v1/forecast:lookup | 403 | none |
| Hosting Platform | https://status.render.com/ | 200 | none |
| Secrets Management | https://api.doppler.com/ | 200, 302, 400, 401 | none |

Every configured timeout is 5000ms, directly mapped to 5 seconds. Existing checks cadence is 15 minutes, directly reusable as an operator runner setting; no need to ask for a cadence from scratch. The desired one-502-red rule explicitly supersedes the incumbent five-failure debounce for this kata. The two application endpoints are first-party health checks; the others are provider/public endpoint reachability. New precise impact wording is draft explanatory copy grounded in those probe limits, not a claim to know a particular customer's wash impact.

Support is explicitly `mailto:engineering@tuxedodrive.com`, repeated in the live source-linked public page. This is carryable as the current configured route without inventing a replacement mailbox. This audit did not send email or establish response effectiveness; prior browser tests only establish a configured navigable href and visibility, not successful navigation/contact with a support service. No blanket new support-workflow decision is needed just to preserve that route.

The existing configured canonical status host and README link are `status.tuxedodrive.dev`; read-only `.dev` returned 200, `.com` returned 404 from this environment. Preserve `.dev` if replacing the documented current service; only a literal requirement to serve `.com` needs clarification before any domain action. No DNS/TLS/cutover authorized here.

`production-config.draft.json` carries these exact URLs/codes/keywords/timeouts and support route. It is dormant and was never run. `stale_after_seconds: null` intentionally fails validation until a freshness horizon is selected, preventing accidental activation. The extra activation_enabled marker is documentation, not a security enforcement mechanism. Proposed browser refresh 5 seconds is the candidate's declared implementation default, not a recovered production setting.

## Precise remaining decisions / activation inputs

1. **Freshness horizon:** the old config has no stale/missing-observation policy to translate. Choose an explicit horizon consistent with the existing 900-second check cadence; the synthetic 20/60-second values are not production defaults.
2. **Real alert transport credentials/configuration:** destination mailbox and GitHub repository are known; SMTP host/port, verified From address, auth environment variable names/values and TLS configuration are not supplied by this public config. They must be supplied through an approved existing sending account, never guessed or provisioned here. GitHub activation needs an approved environment-supplied credential with issues read/write scoped to tuxedodrive/td-status. No credential lookup/creation or external delivery authorized.
3. **Hosting activation:** static export is ready to serve separately; choose/authorize the actual publishing route to the existing independent hosting, plus supervising/backup ownership. This is activation work, not a missing application framework. Existing source comments describe 90 days while `history.lines: 90` is not a direct SQLite retention implementation; define archive/pruning behavior before long-running production, rather than claiming the candidate already enforces 90 days.

## Actual notification software support

The incumbent describes both GitHub issue creation and email to engineering@tuxedodrive.com. Run-003 only supports generic unauthenticated JSON POST with durable retry, not SMTP or authenticated GitHub API. A 2xx synthetic sink acknowledgement is not email/GitHub feature parity. No exact production webhook destination exists in the inspected source; do not pretend this is configuration-only.

Run-004 specifies a separate adapter component: loopback event receiver, per-event/per-transport durable delivery ledger, SMTP accepted-recipient delivery and authenticated GitHub issue open/close. Testing uses only local SMTP/HTTP fakes and fake credentials. Real activation still requires the exact inputs above. Existing `assignees: [tuxedodrive]` is not silently copied: it appears to name the organization, not a verified assignable user; issue assignment is unnecessary to deliver the alert and remains omitted unless deliberately resolved.

An independent audit also identified a possible slow-sink/publication coupling in run-003. A bounded local test confirmed the coupling: three events at two seconds each left the old healthy public generation visible until delivery completed (~6.114s). A separate browser boundary test confirmed an unresolved first fetch prevented any later poll/recovery (one call, affected service still impaired at 3.5s). These are software defects, not DNS/policy activation items. Final run-005 contract separates collector/export from a bounded delivery worker and requires finite abortable refreshes. Final contract/regeneration and evidence must distinguish any confirmed repair from the earlier generic-sink passes.

## Process accuracy

Run-003 was fresh relative to run-002, then its same builder made an in-context support **placement/visibility** repair. It is not evidence of an independent fresh regeneration from the final repaired contract. A final fresh-context rebuild using the final frozen contract and frozen independent evaluations is the planned regeneration proof. Do not rewrite the original attempt or call its context isolation OS-enforced.
