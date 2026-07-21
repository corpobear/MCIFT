# Security policy

MCIFT `0.1.x` receives security fixes on a best-effort research-software basis. It is
not safety-certified and must not be used as an autonomous control system.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub private
vulnerability reporting for this repository after the owner confirms that it is
enabled. Enabling and testing that route is an explicit owner action in
`PUBLIC_RELEASE_CHECKLIST.md`; no private email address is invented here.

Until that feature is confirmed, contact the repository owner privately through an
already established channel and share only the minimum reproducer. Never include
credentials, customer telemetry, raw private datasets, personal information or
confidential research material in a public report.

Include the affected version/commit, operating system, Python and NumPy versions,
impact, minimal reproduction and suggested mitigation when known. Allow reasonable
time for investigation before public disclosure.

## Security properties

The package is offline at runtime and performs no telemetry or automatic upload.
Models are inspectable directory bundles. Loading rejects pickle-based models, unsafe
paths, unexpected files, invalid shapes and checksum mismatches. Model metadata is not
executed. Checksums detect corruption but do not authenticate a publisher.

See [docs/security-model.md](docs/security-model.md) for trust boundaries and limits.
