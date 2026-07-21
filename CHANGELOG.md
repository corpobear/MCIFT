# Changelog

All notable changes are documented here. MCIFT remains experimental research software.

## 0.1.0a1 - 2026-07-21

- Prepared the first experimental public research alpha.
- Included the deterministic NumPy exchange core and versioned telemetry and vibration
  processing profiles.
- Included the six-gate IMS profile with centred RMS, excess kurtosis, and crest-factor
  corroboration.
- Preserved explicit chronological history, calibration/evaluation separation, and
  schema-4 inspectable serialization.
- Added cross-platform Python 3.11-3.13 and NumPy 1.26 compatibility checks, installed
  wheel/sdist tests, and security hardening.
- Documented the initial frozen NASA IMS Test Set 2 case study, including its warning
  behavior, disrupted controls, resource use, and failed bearing localization.
- Exathlon execution remains pending; this release does not establish generalization,
  production readiness, causal localization, or a physical theory.

## 0.1.0.dev3

- Added deterministic centred RMS, excess-kurtosis, and crest-factor vibration features.
- Added healthy per-channel conventional-feature calibration without evaluation leakage.
- Added structured conventional evidence and `mcift.gates.ims-six-gate.v1`.
- Added serialization schema 4 with explicit schema-3 five-gate migration.
- Preserved `mcift.gates.exchange-screening.v1` as the default compatibility profile.

## 0.1.0.dev2

- Added immutable telemetry and vibration processing profiles.
- Added historical and current-main golden compatibility fixtures.
- Corrected global/local history and persistence semantics for explicit caller-owned streaming history.
- Restricted directional-gate eligibility to recent qualifying local relationship evidence.
- Added explicit chronological progression calibration while leaving progression unavailable for unordered calibration data.
- Renamed node output to `node_incident_damage_ratio` without changing its values.
- Enforced meaningful fitting sample sizes with visible research overrides.
- Hardened aggregate validation and atomic, bounded, non-executable serialization schema 3 model loading.
- Added deterministic offline IMS file and array adapters with bounded two-pass parsing.
- Expanded scientific, security, provenance, and benchmarking documentation.
- Added cross-platform Python and NumPy compatibility fixes.
- Added cross-platform CI and CodeQL configuration, with 95 passing tests and green hosted CI.

No PyPI upload occurred for the development versions.
