# Public alpha release checklist

The existing private repository must never be made public. Export the reviewed tree
without Git metadata into a new public repository with a new root commit.

- [x] Remove the unsupported specific candidate-bearing claim.
- [x] Confirm private PR CI and CodeQL are green.
- [x] Create and verify a complete private backup.
- [x] Rename the former repository to `MCIFT-private-archive` and verify it remains private.
- [x] Export only the reviewed tree without `.git`.
- [x] Create the new public `MCIFT` repository from one new root commit.
- [x] Review `docs/publication-audit.md`.
- [x] Confirm benchmark commit links.
- [x] Confirm no dataset or private artifacts are included.
- [x] Run the manual `release-check` workflow.
- [x] Confirm public CI and CodeQL are green and CodeQL uploads results.
- [x] Enable GitHub private vulnerability reporting.
- [x] Verify public clone without authentication.
- [x] Verify README links and badges.
- [x] Verify CodeQL upload after visibility change.
- [x] Close private PR #4 without merging after public validation succeeds.

Do not create a tag, GitHub release or PyPI publication as part of this operation.

## Accidental-exposure rollback

1. Change repository visibility back to private immediately.
2. Revoke or rotate any credential if later analysis identifies one; do not paste it
   into an issue or chat.
3. Preserve an audit record of the exposure window and affected refs.
4. Disable public Pages, Actions artifacts, forks and releases where applicable.
5. Ask GitHub Support about cached or forked copies when sensitive history was exposed.
6. Prepare a reviewed history rewrite or a new clean public repository offline; do not
   force-push remediation without owner approval and a coordinated migration plan.
7. Re-run full-history and package audits before considering visibility again.
