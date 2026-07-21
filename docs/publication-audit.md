# Publication audit

Audit date: 2026-07-21

## Scope

This audit covers the exact source tree exported for the clean-history public
repository. The export was produced with `git archive` from reviewed private
preparation identifier `b934db475dc7a63098de890b39b834de7e8b4c1e`. No private
`.git` directory, branch, tag, pull-request ref or unreachable object was copied.

The former repository remains private because GitHub may retain historical objects
referenced by old commits or pull requests. This conclusion does not claim that those
objects were purged.

## Content and secret scan

- Gitleaks 8.30.1 tree scan: zero findings.
- Former private-only contributor instructions: absent.
- Private upstream paths, local user paths and private contact data: absent.
- Credentials, tokens, connection strings and private keys: absent.
- NASA recordings, datasets, run outputs and model bundles: absent.
- Public `AGENTS.md`: contributor guidance only.
- Unsupported specific candidate-bearing claim: removed.

Reserved experimental source files contain only empty namespace placeholders. They
contain no unpublished equations, topology specification or remediation logic and are
excluded from release artifacts.

## Package and licensing audit

`LICENSE`, package metadata, source SPDX headers, `COMMERCIAL-LICENSE.md`, README
and `CITATION.cff` consistently identify `AGPL-3.0-only`. NumPy is the only runtime
dependency.

| Artifact | Files | Result |
|---|---:|---|
| Wheel | 28 | Stable package, adapters, typing marker, metadata and AGPL licence only |
| Sdist | 34 | Build metadata, README, AGPL licence and stable source only |

Neither artifact contains `AGENTS.md`, tests, datasets, benchmark output, Git
metadata, caches, local paths, secrets, private documentation,
`mcift.experimental`, model bundles or NASA recordings.

Clean wheel and sdist installations report `0.1.0a1`. The installed wheel passes a
six-gate chronological calibration/evaluation and schema-4 save/load round trip.

## Validation

Local Windows Python 3.11 validation passed Ruff, strict mypy, 119 tests with 3
symlink-only skips, 80% branch-aware coverage, Bandit, pip-audit after upgrading
environment build tooling, build, Twine, Markdown links and artifact inspection.
Python 3.11 with NumPy 1.26.4 passed the same 119 tests with 3 skips.

Private hosted CI and CodeQL run 12 passed for the exact preparation identifier before
export. Public CI and CodeQL passed on the new repository, CodeQL uploaded its SARIF
results, and the manual non-publishing release check passed. Its downloaded wheel,
sdist, audit summary and SHA-256 checksums were independently inspected.

## Verdict

**Existing private repository visibility change: BLOCKED — DO NOT MAKE THE PRIVATE
ARCHIVE PUBLIC**

**Clean new-history public repository: READY FOR PUBLIC GITHUB ALPHA**

The public repository started from a new root commit and passed public validation. The
private archive must remain private. This audit authorizes no PyPI upload, tag or
GitHub release.
