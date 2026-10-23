# Status app contract kata

Draft for discussion, first checkpoint 2026-10-22; bounded kata decisions added 2026-10-23. Not an approved complete specification, executable test suite, or implementation authorization. Checkpoint on a branch in tuxedodrive/td-status, not main. This document separates desired behavior from source observations so regeneration does not accidentally preserve defects or pretend proposed behavior already exists.

## Purpose and boundary

Help a car-wash owner answer: “If I cannot operate my wash, is it because of a problem outside my four walls or within my four walls?” Report what is known about TuxedoDrive's components and dependencies without claiming to diagnose every local fault. Remain useful when the rest of the platform is unavailable. The app and its status information are public by design.

This is a small characterization-and-regeneration kata, not a redesign of the monitoring platform. Repairing washes, changing infrastructure, compensating unhappy customers, and doing support work are outside the app. The page helps people choose their next action; it need not perform those actions.

## Bounded kata decisions — 2026-10-23

The immediate exercise is a page-only experience driven by fixed observations. It does not implement live probes, scheduling infrastructure, or a replacement for production Upptime. The user expects to continue using an off-the-shelf status service; this proof of concept teaches regeneration for original TD Edge/Core software later. The original journeys and obligations below remain inception context, not an expanded implementation checklist for this first slice. No app build or deployment is authorized by this checkpoint.

### Observable sequence

| Supplied observation | Expected page outcome |
| --- | --- |
| Healthy success | The service is shown healthy and green. |
| Received HTTP 502 | The service is shown red, with a clear description of the failure and its timestamp. Showing the numeric code 502 is optional. |
| Fresh success after the failure | The service returns to green. |

Downtime duration and incident logging are possible future details, not requirements now. No debounce, sampling, or freshness threshold is selected. The broader uncertainty obligation remains; its policy is an open question, not an invented timing rule.

### Historical research background and provenance

Superseded as a fixture plan by the later explicit choice below: the first kata is fully synthetic. Earlier research considered April 5–11 observations for the current ten-service subset. Real record shape and cadence may inform synthetic data, but historical records are background, not fixture truth; no history harvesting is needed.

- Historical source pin: [a126bb25eeb7add750d0f3bf1a3174527347484c](https://github.com/tuxedodrive/td-status/commit/a126bb25eeb7add750d0f3bf1a3174527347484c).
- Production Application down record: [096191b954fe35f416793f8c0a76e196d0e65005](https://github.com/tuxedodrive/td-status/commit/096191b954fe35f416793f8c0a76e196d0e65005), April 8 at 16:30:37.239Z.
- Recovery record: [468eba536e3e8509e041a9b67153d482780e0bad](https://github.com/tuxedodrive/td-status/commit/468eba536e3e8509e041a9b67153d482780e0bad), April 8 at 17:09:44.913Z.

These are sampled records, not exact outage boundaries. They do not by themselves establish the HTTP 502 narrative; keep any synthetic 502 event labeled accordingly. Later extraction must preserve source commit and blob provenance, plus explicit labels and derivations for synthetic/interpolated events. No extraction is needed for this checkpoint.

Groundhog Day is the proposed canonical fake namespace. The user offered Groundhog Day or staging names; an exclusive naming choice is not settled. Exact fixture shape, final names, and the independent outcome oracle remain open. A narrative timeline with expected observable outcomes, or harvested brownfield history with an independently specified oracle, is sufficient to start evaluation authoring.

## User-desired journeys and outcomes

1. Technically sophisticated wash owner: something fails; they check the page, identify whether one component or a broader failure plausibly explains their symptoms, and decide whether to work around it, seek repairs, or wait. Credible recovery information helps when available; no invented or guaranteed ETA. Once service returns, they can resume operations and address downstream customer/business damage outside the app.
2. Nontechnical wash owner: something is broken and they need help. Whether the page shows one failure, a broad failure, or everything green, it makes the next useful action or route to support clear. A green page does not strand them or imply their problem is imaginary. A phone number, contact page, or escalation path are possible implementations, not three required features.
3. TuxedoDrive technical staff: prompted by one wash's support call, broad failures/telemetry, or an external provider/region outage, they consult the page to understand affected components. They coordinate with stakeholders and repair infrastructure elsewhere. Once the underlying reported problem is resolved and fresh observations establish recovery, the page reflects recovery rather than remaining erroneously red.

## Desired obligations / derived invariants

- Independence: failure of the monitored platform must not by itself prevent access to the status information. This is a failure-boundary goal, not a prescribed hosting stack.
- Explicit coverage: components/dependencies intended to be monitored are explicitly registered. The displayed coverage is understandable; absence from the registry is not evidence of health.
- Honest evidence: distinguish known healthy, known impaired, and uncertain observations. Freshness is observable; missing/stale evidence must not masquerade as a fresh healthy result. Exact timing policies are implementation decisions unless they materially change the promise.
- Appropriate meaning: status explains actual customer impact and scope. Minor/noncritical failures must not imply that all wash operations are unavailable, while genuine failures must not be concealed to improve appearances. This shared constraint applies once across the journeys.
- Actionability: help is easy to find even when the page is green but the wash is not working. Communicate in terms usable by both technical and nontechnical readers.
- Responsive usability: the same essential status and help tasks work on an ordinary phone, a folded-open roughly square phone, and a tablet. No particular layout framework is required.

These are derived from the user's inception, not claims that the current app satisfies them. Public operation does not require publishing credentials or private operational data.

## Observed source baseline (not runtime verification)

Repository: https://github.com/tuxedodrive/td-status
Inspected main commit: f1fb70ab713bc649a13f30784da3132757edd9d5, dated 2026-10-08.

- [README](https://github.com/tuxedodrive/td-status/blob/f1fb70ab713bc649a13f30784da3132757edd9d5/README.md) describes an Upptime app, ten checks, automated status updates, GitHub issues/email notifications, 15-minute checks, and five failed checks before down (approximately 75 minutes). These existing mechanisms/timings are observations, not new contract requirements or proof that scheduled jobs currently work.
- [Configuration](https://github.com/tuxedodrive/td-status/blob/f1fb70ab713bc649a13f30784da3132757edd9d5/.upptimerc.yml) explicitly lists Production Application, Edge API, Payments, Email Delivery, SMS Notifications, Authentication, Weather Service, Pollen Service, Hosting Platform, and Secrets Management. Weather and pollen are already present. Most provider checks are unauthenticated reachability, not authenticated business transactions. Green does not prove TuxedoDrive credentials or end-to-end operations work.
- The same configuration includes a Support mail link to engineering@tuxedodrive.com. It also says “Everything green? You're good to go” and “We're already on it” for orange/red. Those blanket claims are not supported merely by reachability results or configured notifications. They require review against honest uncertainty and the green-but-broken journey; do not preserve them as invariants.
- [Site workflow](https://github.com/tuxedodrive/td-status/blob/f1fb70ab713bc649a13f30784da3132757edd9d5/.github/workflows/site.yml) generates a static site with Upptime v1.41.3 and publishes to GitHub Pages. This supports a distinct hosting boundary from the monitored services, but does not prove complete failure independence or current deployment health.
- [Configuration validator](https://github.com/tuxedodrive/td-status/blob/f1fb70ab713bc649a13f30784da3132757edd9d5/scripts/validate-upptime-config.py) compares registered names/count, workflow schedule, and generated history/api/graph slugs. It does not discover unregistered dependencies in other repositories and is not a user-journey contract test suite.
- Main's complete tree has no existing regenerative contract. The rescue branch inspected likewise has no contract/docs paths. No tests were executed and no production UI was observed; responsive behavior, uncertainty presentation, recovery transitions, runtime schedules, and impact comprehension remain unverified.

## Illustrative evaluations: DRAFT, not yet executable or approved

```gherkin
Scenario: A green page does not strand an owner whose wash is broken
  Given the monitored checks report healthy
  And the owner cannot operate their wash
  When they consult the status page
  Then the limits of those checks do not imply every wash workflow is healthy
  And an obvious way to seek help is available

Scenario: Missing evidence is not a healthy result
  Given a registered component's last observation is no longer current
  When a visitor checks its status
  Then the page communicates uncertainty and observation freshness
  And it does not present the old observation as fresh proof of health

Scenario: A minor failure has a proportionate explanation
  Given a component is impaired but core wash operations are unaffected
  When a visitor reads the status page
  Then the impairment is visible
  And its stated impact does not imply that all wash operations are down

Scenario: Recovery follows evidence of recovery
  Given a component was reported impaired
  When fresh observations establish that the reported problem has resolved
  Then the status reflects that recovery
```

These examples leave sampling cadence, thresholds, UI components, and test harness open. Before using them to judge regeneration, supply representative fixtures and a clear outcome oracle; do not count prose as passing tests.

## Open characterization gaps

- Inspect the actual rendered app against these journeys, including phone/foldable/tablet views, missing data, recovery, and an all-green page with an unresolved customer problem.
- Establish what each current probe can legitimately say about customer impact; reachability alone cannot identify whether a particular wash's problem is inside or outside its four walls.
- Determine whether the configured support destination remains the right one and whether status copy promises human response it cannot establish. No new support workflow is selected here.
- Agree the minimum evaluator inputs and pass/fail observations for the kata before regeneration. No requirement to solve the general contract format first.

## Follow-up, not first-kata requirements

- A periodic dependency-gap check may compare observed/configured dependencies with explicit registration and flag omissions for review. Nightly timing, automatic registration, scan technique, and implementation are not decided.
- Investigate how the status app itself is monitored without creating a circular dependency. No new watchdog architecture selected.
- Reusable questions about contract placement, format, and lifecycle belong in td-meta discovery notes; this app's desired behavior belongs here. Keep regular Git checkpoints and distinguish checkpointed drafts from approved requirements and running tests.

## Latest fixture decision — fully synthetic

The user's later explicit choice is to use fully synthetic observations for the first kata, with real record shape and cadence as reference only. No adherence to historical events is required. [synthetic-timeline.json](synthetic-timeline.json) is a draft fixture and independent expected-outcome oracle for the concrete agreed scenario.

The fixture's Groundhog Day namespace, single component, arbitrary date, 15-minute spacing, field names, and explanatory text are proposed authoring choices, not user-specified values or operational thresholds. Groundhog Day remains the proposed namespace; staging names were also offered. The agreed outcomes are green, then red with a clear 502 failure description and timestamp, then green on fresh success. Numeric code display remains optional.

The minimal proposed input boundary is an ordered list of fixed observations: component identifier, observation timestamp, and success or HTTP failure result. The fixture separates those inputs from expected visible outcomes. Later clean builders receive the contract and input boundary/inputs, not the old implementation; evaluation expectations remain independently specified. Fixture version and Git revision supply provenance. No parser, framework, live monitoring, or generated app is introduced.

All original uncertainty/freshness, proportionate-impact, help, and responsive-usability obligations remain recorded above. This small fixture does not claim to evaluate them or settle their open policies.
