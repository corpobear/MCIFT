# NASA IMS Test Set 2 case study

## Scope and evidence

This is an initial, single-run case study of implemented software behavior. It is not
evidence that MCIFT is production-ready, superior to established methods, causally
localizing faults or validating a physical theory.

The protocol implementation is frozen at benchmark commit
[`7ae4383fd642f1ab99e64bebdb1e7047b39496dc`](https://github.com/corpobear/MCIFT-Benchmarks/tree/7ae4383fd642f1ab99e64bebdb1e7047b39496dc).
The exact protocol file is
[`benchmarks/configs/ims-set2-v1.yaml`](https://github.com/corpobear/MCIFT-Benchmarks/blob/7ae4383fd642f1ab99e64bebdb1e7047b39496dc/benchmarks/configs/ims-set2-v1.yaml).
Measured run evidence is recorded in
[MCIFT-Benchmarks PR #2](https://github.com/corpobear/MCIFT-Benchmarks/pull/2), whose
head is that commit. The benchmark records MCIFT package source identifier
`27663fab8a9b164fbe8143537af24b988c5e109c`.

The source recordings are not redistributed. The benchmark repository directs users
to the [NASA IMS Bearings catalog](https://data.nasa.gov/dataset/ims-bearings) and the
[NASA NTRS technical report](https://ntrs.nasa.gov/citations/20205001055).

## Dataset and frozen protocol

| Field | Frozen value |
|---|---|
| Dataset | NASA IMS Bearings, Test Set 2 |
| Total recordings | 984 |
| Sampling rate | 20 kHz |
| Samples per recording | 20,480 |
| Channels | 4 (`bearing_1` through `bearing_4`) |
| Documented terminal failure | Bearing 1 outer race |
| Reference | `[0, 96)` |
| Calibration | `[96, 352)` |
| Healthy holdout | `[352, 448)` |
| Evaluation | `[448, 984)` |
| Processing profile | `mcift.exchange.vibration.v1` |
| Gate profile | `mcift.gates.ims-six-gate.v1` |
| History length | 32 |
| Random seed | `20260101` |
| MCIFT package version used | `0.1.0.dev3` |
| MCIFT source commit | `27663fab8a9b164fbe8143537af24b988c5e109c` |
| Benchmark implementation commit | `7ae4383fd642f1ab99e64bebdb1e7047b39496dc` |

Reference windows fit scales and healthy relationships. Calibration windows fit
thresholds with chronological ordering. The healthy holdout and evaluation recordings
do not fit or select thresholds.

## Measured warning behavior

The evaluation contained 536 recordings:

| Decision | Positive recordings |
|---|---:|
| Screening positive | 438 |
| Persistent MCIFT warning | 5 |
| High-confidence IMS warning | 3 |

The first persistent and high-confidence warnings occurred 49 recordings, 29,400
seconds, or 8 hours 10 minutes before the terminal recording.

> Time before the terminal recording is not necessarily lead time before physical
> fault onset.

The result is an observation under one frozen protocol. It does not establish a fault
onset time, event-level predictive performance on other runs or superiority over
conventional methods.

## Healthy holdout

Full MCIFT decisions and the conventional G6 component must not be conflated:

| Measure | Positive recordings |
|---|---:|
| Full MCIFT screening positives | 0 / 96 |
| Full MCIFT persistent warnings | 0 / 96 |
| Full MCIFT high-confidence warnings | 0 / 96 |
| Basic G6 any-feature/any-channel positives | 8 / 96 |
| Same-channel two-feature exploratory positives | 1 / 96 |

The basic G6 rule tests three features across four channels and can be sensitive to
multiple comparisons. Its positives are corroboration evidence, not full MCIFT
warnings.

## Disrupted controls

The run evaluated shuffled chronology, a fixed channel permutation and independent
per-channel time permutation. Each produced zero persistent warnings and zero
high-confidence warnings.

The absence of strong warnings in the disrupted controls suggests that chronology and
cross-channel structure contributed to the observed warning pattern under this
protocol. It does not prove causality.

## Failed localization

The IMS run demonstrated anomaly-warning behavior under the frozen protocol, but it
did not correctly localize the documented failed bearing.

| Localization field | Result |
|---|---|
| Documented failed bearing | Bearing 1 |
| Top-1 localization accuracy | 0.0 |
| Top-2 localization coverage | 0.0 |

The run did not correctly localize the documented bearing 1 outer-race failure.
Top-1 localization accuracy and top-2 localization coverage were both 0.0. Candidate
nodes and edges must be treated as associations rather than causal localization.

## Resource use

The complete run used approximately 31 minutes 44 seconds of wall-clock time. Peak
resident memory was 468,983,808 bytes, approximately 447 MiB. These measurements are
machine- and workload-specific, not resource guarantees.

## Interpretation boundaries

The implemented software, the measured counts above, exploratory interpretations and
theoretical MCIFT ideas are separate. This case study supports only a reproducible
description of one run. Generalization to other IMS sets, operating regimes,
datasets, fault types and platforms remains unestablished.
