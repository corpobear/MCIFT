# Stable mathematics

MCIFT stable exchange v1 accepts finite `float64` windows shaped
`(samples, channels)`. Reference fitting, calibration, and evaluation are separate.

## Pipeline

1. Mean-centre each channel and divide by its frozen profile-specific scale.
2. Compute log RMS information, angular-frequency centroid, and phase at the shared
   strongest aggregate non-DC FFT bin.
3. Evaluate the frozen pairwise exchange equation documented in SDR-0001.
4. Fit robust mismatch scales and an edge-wise median healthy relationship matrix from
   reference windows only.
5. Fit global and local-edge thresholds from calibration windows only. Fit progression
   only when calibration order is explicitly declared chronological; otherwise it is
   unavailable.
6. During evaluation, compute unique-edge RMS deformation, standardized edge damage,
   and node incident damage ratios without modifying the monitor.

## Conventional vibration agreement

The opt-in IMS six-gate profile also computes per-channel centred RMS, excess
kurtosis, and crest factor:

```text
c = x - mean(x)
RMS = sqrt(mean(c^2))
crest = max(abs(c)) / RMS
excess kurtosis = mean(c^4) / RMS^4 - 3
```

When RMS is at or below the frozen numerical floor, crest factor and excess kurtosis
use finite `0.0` fallbacks with diagnostics. Healthy calibration fits an independent
strict upper threshold for every feature and channel with the vibration profile's
quantile and method. See SDR-0006 for the exact G6 and six-gate decisions.

The telemetry and vibration profiles differ only in explicitly versioned preprocessing
and calibration conventions. Stable code never imports experimental modules.

## Numerical interpretation

The global exchange score is an RMS over unique edges, not an unnormalised Frobenius
norm. Node incident damage ratios sum to approximately two when damage is non-zero and
are not probabilities. Densification is auxiliary and does not replace anomaly score.

## Limitations

These equations are a deterministic engineering implementation of a speculative
toy-model mapping. Detection performance does not establish the underlying physics,
and candidate localization does not prove causality.
