# Groundhog Day status kata — system intent

## Purpose

A clean-room kata (td-meta#176) asks whether a small behavioural Contract can
produce a replaceable status service through a fresh build and independent
evaluation. The product is one component, `status.service`: a standalone
service that monitors registered HTTP dependencies and publishes a public
status site. Everything in this experiment is synthetic Groundhog Day data on
loopback interfaces.

## Scope

Owns: the `status.service` component described in
`status/service.intent.md` and its records.

Does not own: production activation of any kind. Actual endpoint activation,
hosting, TLS, DNS, cutover and notification transport are operator work that
needs applicable approval; this experiment does not perform them.

## Environment facts

- The component runs with an existing `python3` and its standard library on
  the Priory host, under a non-root experiment directory; checked by the
  evaluator invoking `python3 status.py` there. This Contract does not pin a
  Python version.
- The public page runs in a browser using only browser-native HTML, CSS and
  JavaScript; checked by the evaluator's headless-browser cases.
- Priory carries other workloads that this experiment must not alter.

## Cross-cutting invariants

- No package installation, external services, authentication or deployment
  (`status.service.I1`, record `stdlib-only`).
- No automatic external messaging, credentials or real destinations
  (`status.service.I5`, record `synthetic-loopback-only`).
- All example data is synthetic Groundhog Day, and test endpoints are loopback
  only (`status.service.I34`, record `synthetic-loopback-only`).
