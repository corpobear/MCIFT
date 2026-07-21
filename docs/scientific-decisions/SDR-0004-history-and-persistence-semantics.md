# SDR-0004: History and persistence semantics

Status: Implemented for `mcift.gates.exchange-screening.v1`.

## Behavior

Each caller-owned history entry records separate global and local threshold outcomes.
The base-positive primitive is frozen as:

```text
base_positive = global_positive OR local_positive
```

Persistence operates on `base_positive` and passes only when the current entry is
positive and at least three of the most recent five entries are positive. With fewer
than three entries, persistence is unavailable rather than failed. Directional
consistency is separate corroboration and uses only the most recent five entries. An
entry is eligible only when it is local-positive with an in-range top edge and a
non-zero relationship-change sign.

## Rationale

Global-only history discarded a valid local threshold crossing. A relationship could
remain repeatedly damaged while aggregate RMS deformation stayed below its threshold,
yet never acquire persistence evidence. Retaining both outcomes lets a local-only
anomaly become persistent without pretending the global gate passed.

## Stable warning logic

The preliminary screening profile declares a persistent exchange warning only when:

```text
global and local base thresholds are calibrated
AND base_positive is true
AND persistence passed
AND at least one available corroborating gate passed:
    directional consistency OR robust progression
```

Global and local positives are alternative sources of the same base evidence. They
are reported separately but are not double-counted to satisfy the warning rule.

## Compatibility and versioning

This corrects private-alpha history semantics and changes streaming decisions for
persistent local-only anomalies. History now carries model, processing-profile,
gate-profile, channel-count, sequence-index, and fitted-monitor identity evidence.
Old history objects are incompatible.

The identifier remains `mcift.gates.exchange-screening.v1` because it was not released
as stable and this record freezes its first complete definition. Later changes to
base-positive, persistence, eligibility, or warning combination require a new gate
profile, fixtures, and decision record.

## Scientific limitation

Persistent or directional evidence does not prove causality or physical origin.
