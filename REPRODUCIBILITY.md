# Reproducibility

## Environment

MCIFT supports Python 3.11 through 3.13 and NumPy 1.26 or newer. Record the operating
system, architecture, Python and NumPy versions. Report any platform-specific numerical
difference with the exact inputs, profile identifiers, observed values, tolerances and
whether gate decisions or first-positive indices changed.

For a source checkout:

```bash
git clone https://github.com/corpobear/MCIFT.git
cd MCIFT
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev,security]"
ruff check .
mypy src
pytest -q
python -m build
twine check dist/*
```

For an exact package commit:

```bash
python -m pip install "git+https://github.com/corpobear/MCIFT.git@<full-commit-sha>"
```

Replace the placeholder with a reviewed full SHA. Do not cite an unpinned branch when
reporting scientific results.

## Frozen identities and separation

Record both profile identifiers. The initial vibration protocol uses:

```text
processing profile: mcift.exchange.vibration.v1
gate profile:       mcift.gates.ims-six-gate.v1
```

Freeze deterministic seeds before evaluation. Keep reference, calibration, healthy
holdout and evaluation partitions disjoint. Reference fits scales and healthy
relationships; calibration fits thresholds; evaluation only scores. Labels from the
evaluation region must never influence preprocessing, thresholds, features, profiles
or model selection.

Chronological analyses must pass `sequence_order="chronological"` during calibration
and use a fresh caller-owned `MCIFTHistory` for each independent run or control.

## Model persistence

```python
monitor.save("monitor.mcift")
loaded = MCIFTMonitor.load("monitor.mcift")
```

Record the schema version and configuration fingerprint. Schema 4 stores inspectable
JSON metadata, non-object NumPy arrays and checksums. A checksum detects corruption; it
does not authenticate the publisher.

## Benchmark repository

The exact IMS implementation is
[`corpobear/MCIFT-Benchmarks` at `7ae4383fd642f1ab99e64bebdb1e7047b39496dc`](https://github.com/corpobear/MCIFT-Benchmarks/tree/7ae4383fd642f1ab99e64bebdb1e7047b39496dc).
The run recorded package source commit
`27663fab8a9b164fbe8143537af24b988c5e109c`. This identifier is retained as
benchmark provenance text and is not a link into private development history.

NASA recordings are not committed because they are large third-party research data.
Obtain them from the official catalog, preserve the bundled metadata, hash every input
recording and keep local run directories outside the package repository.

## Citing a benchmark

Include:

- dataset name, variant, source and manifest hash;
- protocol version and configuration hash;
- package version and full commit;
- benchmark full commit;
- reference, calibration, holdout and evaluation split;
- random seed and history length;
- operating system, Python and NumPy versions;
- all reported failures, controls and limitations.

Do not report only the best run or silently omit failed localization, false positives
or negative controls.
