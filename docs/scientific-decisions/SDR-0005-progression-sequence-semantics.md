# SDR-0005: Progression sequence semantics

Status: Implemented for the experimental alpha.

## Behavior

Calibration requires an explicit `sequence_order` declaration:

- `unordered` is the default. No progression threshold is fitted and progression is
  unavailable.
- `chronological` interprets windows in supplied order and fits the slope threshold
  from calibration data only.

Without timestamps, chronological windows use uniformly spaced integer coordinates.
Runtime progression accepts explicit finite, strictly increasing coordinates and uses
the supplied time difference for every pairwise slope.

## Rationale

A robust slope still depends on order. Treating shuffled calibration data as a time
series fabricates progression evidence. Defaulting to unordered makes temporal
authority explicit and prevents arbitrary array positions from becoming time.

## Availability

Progression is unavailable when chronological calibration has not produced a frozen
threshold or when fewer than three recent entries exist. Unavailability is separate
from failure and does not increase the available-gate denominator.

## Serialization and compatibility

Manifest schema 3 stores `calibration_sequence_mode` and the optional progression
threshold. Loading rejects unknown modes and never infers a missing mode. Prior private
schemas require explicit migration and are not silently reinterpreted.

Changing assumed spacing, slope estimator, history window, or sequence modes requires
a new versioned decision and compatibility fixtures.
