# SDR-0002: Vibration profile v1

Status: implemented for experimental alpha.

## Equation or behavior

`mcift.exchange.vibration.v1` fits each channel scale as the median of the centred RMS
from each reference window. Degenerate values fall back to robust MAD, then standard
deviation, then `1.0`. Its historical mismatch-scale floor is `1e-12`. Calibration
uses the historical `0.995` linear quantile unless the caller explicitly supplies a
different probability.

## Source

`corpobear/MCIFT-Benchmarks` commit
`c7f332254d97d3bac61e76473587dae00a33cacc`, `runner.py`, computes IMS reference
scales from the median centred channel RMS, uses a `1e-12` robust-scale floor, and a
`0.995` NumPy quantile.

## Engineering assumptions

The same sample rate and channel order apply to every reference, calibration, and
evaluation window. Units are caller-supplied and never inferred. The fallback chain
extends the historical implementation to fail safely on degenerate channels.

## Alternatives considered

- Raw, uncentred window RMS was rejected because offsets would affect scaling and it
  does not reproduce the historical IMS runner.
- Stacked-observation MAD remains available under the separate telemetry profile.
- Label-driven scaling was rejected because evaluation labels must not influence fit.

## Compatibility impact

The vibration golden fixture matches the historical adapter and runner on synthetic
data. The telemetry profile retains PR #1 behavior, including machine-epsilon robust
scale handling and its prior calibration quantile convention.

## Versioning impact

Any change to scale fitting, the `1e-12` floor, or default quantile behavior requires a
new vibration profile identifier.

## Approval status

Behavior is implemented and tested for the experimental alpha. One frozen NASA IMS
Test Set 2 run is documented; general IMS compatibility has not been established.
