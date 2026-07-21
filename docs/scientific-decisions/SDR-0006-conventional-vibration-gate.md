# SDR-0006: Conventional vibration gate and IMS six-gate profile

Status: Implemented for experimental alpha. Scientific performance claims remain
limited to specifically cited benchmark evidence.

## Feature equations

For each finite `float64` vibration channel `x` in a samples-by-channels window, let
`c = x - mean(x)`. The stable `mcift.vibration-features.centered-v1` features are:

```text
centered_rms   = sqrt(mean(c^2))
crest_factor   = max(abs(c)) / centered_rms
excess_kurtosis = mean(c^4) / centered_rms^4 - 3
```

The implementation rescales intermediate moments by the channel peak to avoid
avoidable overflow while preserving these equations. It does not use SciPy.

## Constant and under-floor channels

The numerical floor is frozen in the fitted monitor. Version 1 uses the vibration
processing profile's `1e-12` robust-scale floor. If centred RMS is at or below that
floor, centred RMS retains its finite computed value and both crest factor and excess
kurtosis use the documented finite fallback `0.0`. Each fallback records its channel,
RMS, and floor in diagnostics. Constant and zero signals therefore never emit NaN or
infinity.

## Healthy calibration protocol

Conventional features are calculated independently for every healthy calibration
window and channel. Each `(feature, channel)` upper threshold is the processing
profile's calibration quantile using its frozen quantile method. For
`mcift.exchange.vibration.v1`, the default is the `0.995` linear quantile. An explicit
caller quantile uses the existing calibration API and is recorded by the fitted
thresholds; evaluation windows and failure labels never participate.

Without calibration, all three threshold arrays are absent by explicit state and G6
is unavailable. A calibrated six-gate model requires all three finite `float64`
arrays with exact shape `(channels,)`.

## Threshold and gate rule

Every comparison is strict:

```text
feature_positive[channel] = value[channel] > healthy_upper_threshold[channel]
G6 = any approved feature is positive on any channel
```

The result also retains triggered feature count, triggered channel count, and whether
one channel triggered at least two features. Those stricter observations do not alter
the version-1 basic gate rule.

## IMS six-gate decisions

`mcift.gates.ims-six-gate.v1` reports G1 global deformation, G2 local relationship
damage, G3 persistence, G4 directional consistency, G5 robust progression, and G6
conventional vibration agreement.

```text
screening_positive = G1 OR G2

persistent_mcift_warning =
    G3 available and passed
    AND (G1 OR G2) passed
    AND (G4 OR G5) available and passed

high_confidence_ims_warning =
    G3 mandatory and passed
    AND G6 mandatory and passed
    AND (G1 OR G2) passed
    AND (G4 OR G5) passed
    AND at least 5 of 6 available gates passed
```

Unavailable gates are excluded from pass counts. High confidence is itself
unavailable until both mandatory individual gates G3 and G6 are available.

## Why spectral bands are excluded

Bearing-speed and bearing-geometry bands require frozen shaft-speed, geometry,
frequency-resolution, and band-construction semantics that this package does not yet
possess. Adding a generic band proxy here would invite dataset-specific tuning and
would not reproduce an approved IMS protocol. Spectral bands require another gate or
feature profile and a new decision record.

## Risks and limitations

RMS may react to benign load changes. Kurtosis and crest factor can react to isolated
noise, clipping, or acquisition artefacts. Conversely, distributed low-amplitude
damage, non-impulsive faults, or calibration contamination can remain below all three
thresholds. Per-channel quantiles do not correct for multiple comparisons and do not
model operating regimes. Persistence and relationship evidence reduce neither risk to
zero. A passing gate is corroborating engineering evidence, not proof of a fault,
causal origin, predictive superiority, or the physical MCIFT hypothesis.

## Compatibility and versioning

The existing `mcift.gates.exchange-screening.v1` path and its five decisions remain
unchanged and default. The six-gate profile is opt-in and requires
`mcift.exchange.vibration.v1`.

Serialization schema 4 stores the gate profile, feature version, numerical floor,
explicit threshold-availability flag, and the three threshold arrays when available.
Schema 3 is migrated only as an exchange-screening model with conventional evidence
explicitly unavailable and a migration diagnostic. Schemas before 3 are rejected and
require external migration. Missing schema-4 thresholds are never inferred.

Changing equations, fallbacks, comparison operators, calibration convention, feature
set, or decision combinations requires a new identifier and scientific decision
record.
