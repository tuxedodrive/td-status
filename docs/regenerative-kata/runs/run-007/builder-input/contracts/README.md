# The contract convention

This directory is the Contract for one replaceable component. Its format is
borrowed from the Impatient Programming (IMP) Covenant convention
(tools4imps/covenant, `docs/contract-convention.md`, MIT licence, commit
82daa23). Only the file format is borrowed: no Covenant tool runs here, and the
component is Python, not Elixir.

The Contract is the versioned description of what the component must do,
including the non-functional obligations nobody writes down. Code is
regenerable from it: if the component could not be deleted and rebuilt from
this Contract alone, the Contract is missing something.

## Layout

```
contracts/
  README.md                      # this convention
  system/
    intent.md                    # whole-product intent: scope, environment facts, cross-cutting invariants
    decisions.yml                # cross-cutting decision records
  status/
    service.intent.md            # heavy form for component status.service
    service.decisions.yml        # records for that component
```

Component ids are `<app>.<component>` (`status.service`). Obligation ids are
`<component id>.I<n>` (`status.service.I3`). Ids are never reused; a retired
obligation keeps its number with status `retired` and says what replaced it.

## Heavy form: `<component>.intent.md`

Sections, in this order: Purpose (with a revision log), Scope, Environment
facts, Public surface, Invariants, Decisions, Orderings, Known limits,
Regeneration brief.

### Obligation block

```markdown
### status.service.I3 — Title
- **scope:** what the obligation applies to
- **must:** the behaviour that must hold
- **why:** the learning or incident it protects
- **kind:** functional | non-functional | persisted-format | ordering | security | exception
- **record:** id of a decision record (optional)
- **status:** active | retired
```

`must` is the requirement. `why` explains it and never adds to it. A retired
obligation is history only: it must not be implemented.

## Decision records: `<component>.decisions.yml`

Each record has `id`, `date`, `decision`, `driver`, `alternatives` (each with
`option` and `rejected`), `evidence`, `invariant`, `approved_by`,
`conditions`, `expires` and `source`, and optionally `kind` (`fact`,
`cross-system`, `known-gap`), `superseded_by` and `notes`. A record earns its
place when a value looks arbitrary to a competent stranger, a choice is
expensive to reverse, or another component quietly depends on it. Records are
never deleted; they are superseded.

`approved_by: pending JPB` means the record states the experiment's working
choice and has not been signed off as product policy. Implement the value the
record states; do not treat it as a production commitment.

## Contract tests

Covenant normally ships the contract tests to the regenerator. This kata
withholds them: the evaluator is independent and the builder never sees it.
Each evaluator check is tagged with the obligation ids it proves; coverage is
reported per obligation by the evaluator, not by the builder.
