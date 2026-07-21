# Provenance

MCIFT 0.1.0a1 is a public, sanitized source snapshot derived from a private
development line. The former private repository and its historical objects remain
private. The public repository intentionally starts with new Git history.

## Public snapshot identity

| Field | Value |
|---|---|
| Package version | `0.1.0a1` |
| Private preparation identifier | `b934db475dc7a63098de890b39b834de7e8b4c1e` |
| Benchmark implementation | `7ae4383fd642f1ab99e64bebdb1e7047b39496dc` |
| Processing profile | `mcift.exchange.vibration.v1` |
| Gate profile | `mcift.gates.ims-six-gate.v1` |
| Serialization schema | 4 |
| Benchmark seed | `20260101` |

The private preparation identifier records the reviewed source snapshot; it is not a
link to the private repository. The benchmark implementation is available at the
immutable
[`MCIFT-Benchmarks` commit](https://github.com/corpobear/MCIFT-Benchmarks/tree/7ae4383fd642f1ab99e64bebdb1e7047b39496dc).

The benchmark repository publicly records historical package source identifier
`27663fab8a9b164fbe8143537af24b988c5e109c`. It is retained here as plain provenance
text only.

## Reproducibility boundaries

The public snapshot contains no NASA recordings, benchmark run directories, model
bundles or private Git metadata. Dataset identity, preprocessing, chronological split,
profile identifiers, random seed, package identifier and benchmark commit must be
reported together for every scientific result.

Schema 4 records package/model version, processing profile, gate profile, calibration
sequence mode, runtime versions, conventional-feature configuration and exact
threshold arrays. Schema 3 loads only through the documented five-gate migration.

The IMS case study is one measured frozen run. Other IMS sets and Exathlon remain
untested. The result does not validate a physical theory or establish production
predictive-maintenance performance.
