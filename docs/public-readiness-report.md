# Public readiness report

Report date: 2026-07-21

## Verdict

**Existing private repository visibility change: BLOCKED — DO NOT MAKE THE PRIVATE
ARCHIVE PUBLIC**

**Clean new-history public repository: READY FOR PUBLIC GITHUB ALPHA**

This public release is created in a new repository history. The former private
repository remains private because GitHub may retain historical objects referenced by
old commits or pull requests.

## Identity

| Field | Value |
|---|---|
| Private preparation identifier | `b934db475dc7a63098de890b39b834de7e8b4c1e` |
| Package version | `0.1.0a1` |
| Processing profile | `mcift.exchange.vibration.v1` |
| Gate profile | `mcift.gates.ims-six-gate.v1` |
| Serialization schema | 4 |

## Validation

| Check | Result |
|---|---|
| Ruff | Passed |
| Strict mypy | Passed, 27 source files |
| Pytest | 119 passed, 3 Windows symlink-only skips |
| Branch-aware coverage | 80% locally; 81% on hosted Linux |
| Bandit | Passed |
| pip-audit | No known vulnerabilities after current build-tool upgrade |
| Python 3.11 + NumPy 1.26.4 | 119 passed, 3 Windows symlink-only skips |
| Build and Twine | Wheel and sdist passed |
| Clean wheel and sdist install | Passed |
| Six-gate/schema-4 round trip | Passed |
| Markdown links | Passed |
| Gitleaks public-tree scan | Zero findings |

The final public validation results for commit
`8c553ef5ddfb7de537d0be7198261b9e0e4aaddb` are:

| Workflow | Result | Run | Evidence |
|---|---|---:|---|
| CI | Passed | 5 | [Run 29834066885](https://github.com/corpobear/MCIFT/actions/runs/29834066885) |
| CodeQL | Passed | 5 | [Run 29834067105](https://github.com/corpobear/MCIFT/actions/runs/29834067105) |
| Public release check | Passed | 2 | [Run 29834086668](https://github.com/corpobear/MCIFT/actions/runs/29834086668) |

The CI matrix covered Python 3.11-3.13 on Linux, Python 3.11/3.13 on Windows, Python
3.11 on macOS and Python 3.11 with NumPy 1.26.4. The hosted Linux coverage job
reported 122 passing tests and 81% branch-aware coverage. The public CodeQL job's
`Analyze and upload` step passed, while its private-repository no-upload alternative
was skipped; SARIF therefore uploaded successfully.

The manual non-publishing release check produced artifact
[`mcift-0.1.0a1-release-check-8c553ef5ddfb7de537d0be7198261b9e0e4aaddb`](https://github.com/corpobear/MCIFT/actions/runs/29834086668/artifacts/8496568824).
The artifact contained the wheel, sdist, audit summary and SHA-256 checksums. Its
GitHub artifact digest is
`sha256:2c063e7d5fca684e835d30ecf6ce1784b870765859a0744e66224fd44d5f3343`.

The audited wheel contains 28 files and the sdist contains 34 files. Neither contains
tests, datasets, benchmark outputs, Git metadata, caches, private paths, secrets,
private documentation, experimental modules, model bundles or NASA recordings.

## Scientific claim boundary

Allowed claims are limited to implemented deterministic behavior and measurements
from the exact frozen IMS Set 2 run. The documentation prominently reports failed
localization: top-1 accuracy and top-2 coverage were both 0.0. The unsupported
specific candidate-bearing detail has been removed.

Production readiness, safety certification, general validation, superiority, causal
localization, Exathlon compatibility and validation of a physical theory are not
established.

The public-repository creation performed no PyPI upload, stable release or tag. PyPI
publication is a separate, owner-confirmed operation using the dedicated OIDC Trusted
Publishing workflow and the protected `pypi` environment.
