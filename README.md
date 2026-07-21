# MCIFT

[![CI](https://github.com/corpobear/MCIFT/actions/workflows/ci.yml/badge.svg)](https://github.com/corpobear/MCIFT/actions/workflows/ci.yml)
[![CodeQL](https://github.com/corpobear/MCIFT/actions/workflows/codeql.yml/badge.svg)](https://github.com/corpobear/MCIFT/actions/workflows/codeql.yml)
![Python 3.11-3.13](https://img.shields.io/badge/python-3.11%E2%80%933.13-blue)
![License: AGPL-3.0-only](https://img.shields.io/badge/license-AGPL--3.0--only-blue)
![Status: experimental alpha](https://img.shields.io/badge/status-experimental%20alpha-orange)

MCIFT is experimental public research software for deterministic multichannel anomaly
detection and condition monitoring. The package is CPU-first, NumPy-only at runtime,
offline, and designed for explicit reference fitting, calibration, chronological
evaluation and evidence inspection.

MCIFT does not establish a physical theory. An anomaly, warning, candidate node or
candidate edge is engineering evidence, not proof of fault, causal origin or physical
mechanism.

## Status and scope

Version `0.1.0a1` is an experimental public research alpha. It implements a
deterministic exchange pipeline, versioned telemetry and vibration processing
profiles, caller-owned chronological history, structured evidence gates and safe
schema-4 serialization. It includes an initial reproducible NASA IMS Test Set 2 case
study.

It is not production-ready, safety-certified, generally validated, scientifically
proven, or evidence of superiority over established predictive-maintenance methods.
It does not reliably localize causal faults. The initial IMS run produced warning
behavior but failed to identify the documented failed bearing. Exathlon execution is
still pending. The package performs no automatic actuation.

See [claims and limitations](docs/claims-and-limitations.md) before citing results.

## Installation

Use Python 3.11 through 3.13. NumPy 1.26 is the minimum supported runtime version.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install .
```

For a source checkout with development tools:

```bash
python -m pip install -e ".[dev,security]"
```

Install the public alpha from PyPI:

```bash
python -m pip install "mcift==0.1.0a1"
```

See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for commit-pinned source installation and
validation checks.

## Five-minute example

```python
import numpy as np

from mcift import MCIFTHistory, MCIFTMonitor
from mcift.profiles import TELEMETRY_PROFILE_ID

rng = np.random.default_rng(2026)
reference = rng.normal(size=(8, 128, 3))
calibration = rng.normal(size=(20, 128, 3))

monitor = MCIFTMonitor.fit(
    reference,
    sampling_rate_hz=1_000.0,
    channel_names=["input", "shaft", "output"],
    channel_units=["V", "m/s2", "V"],
    profile=TELEMETRY_PROFILE_ID,
).calibrate(calibration)

history = MCIFTHistory(maxlen=32)
result, history = monitor.evaluate_with_history(calibration[-1], history=history)
print(monitor.explain(result))
```

Normal fitting requires at least eight reference windows and twenty calibration
windows. `allow_small_sample=True` is an explicit research override that adds visible
warnings and diagnostics.

## Six-gate vibration example

```python
from mcift import MCIFTHistory, MCIFTMonitor
from mcift.profiles import IMS_SIX_GATE_PROFILE_ID, VIBRATION_PROFILE_ID

monitor = MCIFTMonitor.fit(
    reference,
    sampling_rate_hz=20_000.0,
    channel_names=channel_names,
    profile=VIBRATION_PROFILE_ID,
    gate_profile=IMS_SIX_GATE_PROFILE_ID,
)

monitor = monitor.calibrate(
    calibration,
    sequence_order="chronological",
)

history = MCIFTHistory(maxlen=32)
for index, window in enumerate(test_windows):
    result, history = monitor.evaluate_with_history(
        window,
        history=history,
        sequence_index=index,
    )
```

Reference data fit channel scales and healthy relationships. Calibration data fit
thresholds. Evaluation data only score and never update the monitor. Evaluation labels
must not influence preprocessing, thresholds, profiles or model selection.

## Gate overview

- G1 — global deformation.
- G2 — local relationship damage.
- G3 — persistence.
- G4 — directional consistency.
- G5 — robust progression.
- G6 — conventional vibration agreement.

The `mcift.gates.ims-six-gate.v1` decision policy is:

```text
screening_positive =
    G1 OR G2

persistent_mcift_warning =
    G3 passed
    AND (G1 OR G2) passed
    AND (G4 OR G5) passed

high_confidence_ims_warning =
    G3 passed
    AND G6 passed
    AND (G1 OR G2) passed
    AND (G4 OR G5) passed
    AND at least 5 of 6 available gates passed
```

G6 uses centred RMS, excess kurtosis and crest factor. It is an engineering
corroboration gate. Its basic any-feature/any-channel rule can be sensitive to
multiple comparisons. Unavailable gates are reported separately from failed gates.
The compatibility profile `mcift.gates.exchange-screening.v1` remains available.

See the [stable mathematics](docs/mathematics.md) and
[scientific decision records](docs/scientific-decisions/SDR-0001-stable-exchange-v1.md).

## Initial IMS Set 2 case study

The frozen NASA IMS Test Set 2 run evaluated all 536 evaluation recordings. It
produced 438 screening positives, five persistent warnings and three high-confidence
warnings. The first persistent and high-confidence warnings occurred 49 recordings,
or 8 hours 10 minutes, before the terminal recording. Time before the terminal
recording is not necessarily lead time before physical fault onset.

The full MCIFT decisions produced no positives on the 96-recording healthy holdout.
The basic G6 component alone produced 8/96 positives. Disrupted controls produced no
persistent or high-confidence warnings under the tested protocol. The run did not
correctly localize the documented bearing 1 outer-race failure: top-1 accuracy and
top-2 coverage were both 0.0.

Read the complete [IMS Set 2 case study](docs/ims-set2-case-study.md), including the
frozen split, resource use, controls, provenance, multiple-comparison caveat and
failed-localization disclosure.

## Reproducibility

Profiles are immutable identifiers. Model bundles record package/runtime provenance,
processing and gate profiles, calibration ordering, thresholds and schema version.
Use caller-owned `MCIFTHistory` for deterministic streams and cite the exact package
and benchmark commits, dataset hash, split and seed.

The benchmark implementation is maintained separately in
[`corpobear/MCIFT-Benchmarks`](https://github.com/corpobear/MCIFT-Benchmarks). NASA
recordings and local run directories are not committed. See
[REPRODUCIBILITY.md](REPRODUCIBILITY.md) and [benchmarking](docs/benchmarking.md).

## Security model

The core package performs no network requests, telemetry, analytics, downloads or
actuation. Model bundles use JSON, non-object NumPy arrays, SHA-256 checksums and
bounded validation; loading uses `allow_pickle=False`. Checksums detect corruption but
do not authenticate a publisher. Treat arrays, datasets and model bundles as
untrusted. See [SECURITY.md](SECURITY.md) and the
[security model](docs/security-model.md).

## Scientific limitations

The implemented software, measurements from one frozen IMS run, exploratory
interpretations and theoretical MCIFT ideas are distinct. One case study does not
establish generalization, production reliability, fault-onset lead time, causal
localization, predictive superiority or physical validity. Negative controls do not
prove causality. Bearing-speed and geometry-specific spectral bands are not part of
the v1 six-gate profile. Exathlon has not yet been executed.

## Licensing

The implementation is licensed under `AGPL-3.0-only`. The AGPL covers the
implementation. It does not by itself establish ownership or patentability of
mathematical ideas. Separate commercial licensing may be offered by the copyright
holder; see [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md). No patent claim is made.

## Citation

Use [CITATION.cff](CITATION.cff). A benchmark citation must identify the dataset hash,
protocol version, package commit, benchmark commit, split and random seed. No DOI has
been assigned.

## Contributing

Contributions are welcome subject to the research, testing, licensing and scientific
claim rules in [CONTRIBUTING.md](CONTRIBUTING.md). Participants must follow the
[Code of Conduct](CODE_OF_CONDUCT.md).
