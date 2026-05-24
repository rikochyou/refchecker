# Changelog

## v1.1.0+2 - 2026-05-24

### Added

- Card-based API configuration panel.
- Per-source enable switch for API-backed and custom sources.
- JSON editor for Custom REST API Profile.
- Custom REST Profile backend adapter and CLI support via `--custom-rest-profiles`.
- Per-card API connectivity testing.
- Custom REST Profile connectivity test support.
- App version badge in the desktop title bar.
- Safe minimum request delay (`0.50s`) in both UI and backend.

### Changed

- Disabled custom REST sources are hidden from the data-source search chain and are not searched.
- API test results are shown inside the relevant API card instead of the main panel.
- CLI `--delay` default/minimum is now `0.5` seconds.

### Fixed

- Fixed custom source deselect/visibility behavior.
- Fixed several Chinese label display issues.
- Fixed bundled backend JSONL output for API key/API connectivity tests.

## v1.0.0

- Initial public GitHub release.
