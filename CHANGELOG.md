# Changelog

## [Unreleased]

### Added
- GitHub Actions `ci` workflow (test + smoke + docker-test) matching the other
  `urirun-connector-*` repositories.
- Add follow-up tasks for IFURI-016 safe matrix coverage, sandbox API testing
  and richer connector contract documentation.
- Expose `urirun_bindings()` through the `urirun.bindings` entry-point group
  and document `urirun discover` / `urirun list --entry-points`.

### Changed
- Keep active runtime dependency and docs links on `github.com/if-uri/urirun`.

## [0.1.0] - 2026-06-20

### Added
- Initial Namecheap DNS connector package.
- URI bindings for current, expected, plan, backup and apply DNS operations.
- CLI command `urirun-namecheap-dns`.
- Local tests and Docker smoke test for CLI, registry compile, `urirun run`,
  MCP tools and A2A card projection.
