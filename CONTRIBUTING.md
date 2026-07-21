# Contributing

MCIFT welcomes carefully scoped contributions to its experimental research software.
Open an issue before large changes so profile, compatibility and evidence consequences
can be discussed. Follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Required practice

- Add tests for every behavior change.
- Create a new profile identifier when frozen mathematics or preprocessing behavior changes.
- Add a numbered scientific decision record for gate, equation or decision-policy changes.
- Never tune preprocessing, thresholds, gates or models against evaluation labels.
- Do not commit proprietary datasets, customer data, benchmark run directories or credentials.
- Do not make unqualified performance, localization, causality or physics claims.
- Do not weaken serialization checks, input validation or resource limits.
- Preserve deterministic `float64` behavior and reference/calibration/evaluation separation.
- Update documentation, compatibility fixtures and version metadata when behavior changes.

Run before submitting:

```bash
ruff check .
mypy src
pytest -q
pytest -q --cov=mcift --cov-report=term-missing
bandit -q -r src/mcift
pip-audit
python -m build
twine check dist/*
```

Substantial external contributions require an agreement that permits commercial
relicensing or a copyright assignment before merge. Discuss this with the copyright
holder before investing significant work.

All new Python source files must contain:

```text
Copyright (C) 2026 Martin Kasala
SPDX-License-Identifier: AGPL-3.0-only
```
