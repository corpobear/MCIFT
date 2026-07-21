# Claims and limitations

Public statements about MCIFT must distinguish implemented behavior, measured results,
exploratory interpretation and theoretical ideas.

| Claim | Status |
|---|---|
| Deterministic NumPy implementation | Implemented |
| Cross-platform package tests | Implemented |
| Schema-4 safe serialization | Implemented |
| IMS Set 2 frozen protocol executed | Measured once |
| Healthy-holdout full MCIFT false positives | 0/96 in this run |
| Disrupted-control strong warnings | 0 under tested controls |
| Early warning before terminal recording | Observed |
| Lead time before physical fault onset | Not established |
| Correct fault localization | Failed |
| Generalization to other IMS sets | Not established |
| Exathlon compatibility | Not yet executed |
| Production predictive maintenance | Not established |
| Safety certification | Not established |
| Superiority over established methods | Not established |
| Causal fault localization | Not established |
| MCIFT physical theory | Not validated |

Every future scientific claim must reference a dataset hash, protocol version, package
commit, benchmark commit, split and random seed.

Warnings and candidate locations are engineering evidence. They are not proof of a
fault, causal origin or physical mechanism. Negative and disrupted controls can expose
failure modes but cannot prove causality. A result from one dataset split does not
establish general performance.
