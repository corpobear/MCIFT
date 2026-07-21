# AGENTS.md — MCIFT contributor instructions

## Project scope

MCIFT is experimental public research software for deterministic multichannel anomaly
detection and condition monitoring. It is CPU-first, NumPy-only at runtime, offline
and designed around explicit reference fitting, calibration, chronological evaluation
and evidence inspection.

Do not describe MCIFT as production-ready, safety-certified, generally validated,
scientifically proven, superior to established methods, capable of reliable causal
fault localization or proof of a physical theory. Use terms such as “candidate node,”
“candidate edge,” “association” and “engineering evidence.”

## Stable behavior and versioning

- Preserve the public `fit -> calibrate -> evaluate -> explain -> save/load` lifecycle.
- Inputs are finite `float64` arrays shaped `(samples, channels)` with explicit sampling
  rate, stable channel order and caller-supplied units.
- Keep reference, calibration and evaluation data separate. Evaluation labels must not
  influence preprocessing, thresholds, features, profiles or model selection.
- Do not change frozen mathematics, preprocessing, gate rules or decision combinations
  under an existing profile identifier.
- A mathematical or gate change requires a new profile identifier, a numbered
  scientific decision record, updated golden fixtures and an appropriate version bump.
- Preserve `mcift.gates.exchange-screening.v1` compatibility unless a documented
  migration explicitly says otherwise.
- Stable modules must not import from `mcift.experimental`. Experimental modules are
  excluded from release artifacts.

The source-of-truth order is: approved scientific decision records, golden numerical
fixtures, frozen benchmark configurations, current code, then general documentation.

## Scientific and benchmark rules

- Freeze dataset identity, file hashes, preprocessing, channel order, split, seed,
  package commit, benchmark commit and profile identifiers before evaluation.
- Preserve failed runs, negative controls and localization failures in reports.
- Compare simple baselines before making performance claims.
- Never report time before a terminal recording as physical-fault-onset lead time
  unless onset is independently documented.
- Every scientific claim must cite a dataset hash, protocol version, package commit,
  benchmark commit, split and random seed.
- Keep implemented software, measured results, exploratory interpretation and theory
  clearly separated.

## Security and privacy

Treat arrays, archives, model bundles, configurations and datasets as untrusted.

- Reject non-finite or object arrays and enforce bounded dimensions before pairwise
  allocation.
- Keep model loading non-executable: no pickle, dynamic imports, `eval`, `exec`, unsafe
  YAML or shell commands assembled from data.
- Preserve schema, checksum, safe-path, member-count, size, compression-ratio, dtype
  and exact-shape validation.
- Keep saves atomic and refuse overwrite by default.
- Do not add runtime telemetry, analytics, automatic upload, download or actuation.
- Never commit credentials, `.env` files, customer data, proprietary datasets, raw NASA
  recordings, local benchmark outputs, model bundles or personal correspondence.
- Do not weaken GitHub Actions permissions or replace immutable action SHAs with tags.

## Licensing and source files

The implementation is `AGPL-3.0-only`, copyright Martin Kasala. The AGPL covers the
implementation; it does not by itself establish ownership or patentability of
mathematical ideas. Do not make patent claims.

Prefer permissively licensed dependencies. Do not copy incompatible third-party code.
Every new Python source file must contain:

```text
Copyright (C) 2026 Martin Kasala
SPDX-License-Identifier: AGPL-3.0-only
```

Substantial external contributors must complete the repository’s commercial
relicensing agreement or copyright-assignment process before merge.

## Required checks

Run checks proportional to the change and, for release preparation, run all of:

```text
ruff check .
mypy src
pytest -q
pytest -q --cov=mcift --cov-report=term-missing
bandit -q -r src/mcift
pip-audit
python -m build
twine check dist/*
```

Also verify Python 3.11 with NumPy 1.26, the supported Python/OS matrix, clean wheel and
sdist installs, installed-artifact imports, schema-4 save/load and package contents.

## Publication and release safety

Repository visibility, tags, GitHub releases and PyPI publication are owner actions.
Do not perform them unless explicitly requested. A release-preparation change must not
hide failed checks or unresolved publication-audit risks. Follow
`PUBLIC_RELEASE_CHECKLIST.md`, `docs/publication-audit.md` and
`docs/public-readiness-report.md`.
