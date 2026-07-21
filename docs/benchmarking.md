# Benchmarking protocol

Benchmark work must freeze dataset identity, hashes, preprocessing, channel order,
splits, seeds, profiles, thresholds, and package version before evaluation.

Reference data fits channel scales and healthy relationships. Calibration data fits
thresholds. Evaluation labels must not affect either stage. Report all runs, failed
runs, negative controls, warning lead time, false alarms, precision, recall, F1,
event-level metrics, localization metrics, runtime, and peak memory.

Start with deterministic synthetic amplitude, frequency, phase, relationship,
propagation, and false-alarm controls. Compare simple baselines before larger datasets.
Dataset download and extraction remain explicit external operations.

Progression calibration is disabled by default. Pass
`sequence_order="chronological"` only when calibration windows are in true time order.
Regular spacing is assumed unless explicit coordinates are provided to the progression
primitive. Shuffled data must use `unordered` and cannot produce a progression
threshold.

Golden tests demonstrate synthetic compatibility with the historical adapter. One
frozen full NASA IMS Test Set 2 protocol has also been executed; see
`docs/ims-set2-case-study.md`. That run does not establish reproduction of other IMS
sets, Exathlon compatibility, generalization or superiority.

## IMS six-gate protocol

Select `mcift.exchange.vibration.v1` and `mcift.gates.ims-six-gate.v1` before fitting.
Fit centred RMS, excess-kurtosis, and crest-factor thresholds only on healthy
calibration windows. Preserve their per-channel triggers separately from G1-G5 so a
benchmark runner can compare the basic any-feature G6 rule with stricter predeclared
policies without rewriting evidence.

Use chronological calibration for progression and caller-owned `MCIFTHistory` during
evaluation. Report screening, persistent MCIFT, and high-confidence IMS decisions
separately. Report the conventional G6 component separately from full decisions.
Required follow-up includes independent IMS runs, other operating conditions, simple
baseline comparisons, additional negative controls, event metrics and localization
analysis. The first run failed to localize the documented bearing and does not provide
evidence of predictive superiority.

## Cross-platform numerical policy

Golden assertions are classified rather than given one broad tolerance. Algebraic
outputs such as channel scales and information use relative tolerance `1e-13`.
Identifiers, shared bins, decisions, first-positive indices, and score ordering are
exact. FFT-sensitive spectral centroid, circular phase difference, and downstream
exchange values use relative tolerance `5e-12` and absolute tolerance `1e-12`.
Phase uses `angle(exp(1j * (actual - expected)))`, so the `-pi/pi` branch cut cannot
create a false failure.

The FFT fixture covers 16-sample/64 Hz and 15-sample/75 Hz windows. These tolerances
cover observed final-bit differences between NumPy FFT builds on Ubuntu, Windows, and
macOS while remaining below material score or threshold drift. Hosted runs print OS,
Python, and NumPy versions. A change is acceptable only when decisions,
first-positive index, and score ordering remain frozen.
