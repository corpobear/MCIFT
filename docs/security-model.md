# Security model

The core package is offline and has no telemetry, downloader, dynamic import, or model
code-execution path. NumPy is the only runtime dependency.

## Trust boundaries

Windows, IMS files, model directories, JSON, and NPZ members are untrusted. Validation
enforces aggregate element and byte limits before complete `float64` copies where
possible. Pairwise allocations are bounded by the channel limit.

Model loading rejects top-level and component symlinks, non-regular components,
unexpected files, duplicate ZIP members, excessive compressed or uncompressed sizes,
excessive compression ratios, object arrays, oversized shapes, unknown schemas, and
checksum mismatches. NPZ loading always uses `allow_pickle=False`.

Schema 4 validates profile-specific NPZ membership. A calibrated IMS six-gate model
must contain all three finite `float64` threshold arrays with exact `(channels,)`
shapes; a fit-only model declares threshold unavailability explicitly. Missing arrays
are never inferred. Schema 3 is accepted only as the known five-gate profile and gains
an explicit migration diagnostic. Older schemas are rejected.

Saving writes a private temporary sibling, flushes components where practical,
calculates checksums, and atomically renames into a destination that must not exist.
Failures remove the temporary directory.

SHA-256 checks detect corruption and unintentional modification. They do not
authenticate the publisher. Obtain models through an authenticated distribution
channel and verify publisher identity separately.

## Out of scope

The package does not actuate machinery or infrastructure. Experimental namespaces are
disabled placeholders and are not exported. Operating-system compromise and malicious
code already executing as the current user are outside this model.
## CodeQL availability

The CodeQL workflow scans Python and supported GitHub Actions content. While the
repository is private without GitHub Code Security, it analyzes with `upload: never`
and does not claim that SARIF was accepted. It switches to `upload: always` when the
repository is public or the owner sets `CODEQL_ENABLED=true` after enabling Code
Security. The owner must verify accepted code-scanning results after any visibility
change. The workflow has only read access to repository/workflow metadata plus the
`security-events: write` permission needed for public SARIF upload.
