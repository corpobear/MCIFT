# SDR-0001: Stable exchange v1

Status: implemented for experimental alpha.

## Equation or behavior

Stable exchange v1 mean-centres each channel, divides it by a positive scale frozen
from reference data, derives log-RMS information, a power-weighted angular-frequency
centroid, and phase at one shared strongest non-DC FFT bin, then evaluates:

```text
Gamma_ij = g
  * exp(-(I_i - I_j)^2 / (2 sigma_i^2))
  * exp(-(omega_i - omega_j)^2 / (2 sigma_omega^2))
  * cos(phi_i - phi_j)^2
```

The healthy reference is the edge-wise median. The global deformation is the RMS
difference over unique edges. All calculations use NumPy `float64`.

## Source

- An internal speculative research note supplied the pairwise exchange toy equation;
  it is not redistributed. This SDR contains the complete public engineering equation
  required to reproduce the package behavior.
- `corpobear/MCIFT-Benchmarks`, commit
  `c7f332254d97d3bac61e76473587dae00a33cacc`,
  `benchmarks/src/mcift_benchmarks/features/mcift_adapter.py` supplies the historical
  engineering map from windows to observables.
- The same benchmark commit's `runner.py` supplies robust mismatch fitting, healthy
  median reference, and unique-edge RMS scoring.

## Engineering assumptions

Sensor channels are treated as information points. Log RMS, spectral centroid,
shared-bin phase, frozen channel scaling, and plain unique-edge aggregation are
engineering choices rather than statements from the speculative theory note.

## Alternatives considered

- Per-channel dominant phase bins were rejected because the historical adapter uses
  one shared bin.
- Post-construction matrix normalization was rejected because it changes the frozen
  equation's output.
- A full Frobenius norm was rejected because the approved score is unique-edge RMS.

## Compatibility impact

`tests/golden/current_main_telemetry_v1.json` freezes PR #1 behavior.
`tests/golden/historical_vibration_v1.json` freezes the historical benchmark adapter.
Both fixtures use explicit tolerances and synthetic arrays only.

## Versioning impact

Any change to these observables, the exchange equation, or global score requires a
new exchange profile identifier, updated golden fixtures, a numbered SDR, and an
appropriate package version change.

## Approval status

This record does not claim that the equation is established physics or that benchmark
success validates it.
