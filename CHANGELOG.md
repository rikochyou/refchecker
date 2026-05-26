# Changelog

## v1.2.0-beta.1 - 2026-05-26

### Changed

- Removed the optional generated-explanation workflow from the desktop UI, CLI, backend, reports, CSV fields, and documentation.
- Removed the desktop top menu bar while keeping the compact header actions for file selection and running checks.
- Reports now focus on database verification facts, rule-based explanations, repair evidence, and final human judgment warnings.
- Added a local MCP server so Claude Desktop can call RefChecker without switching apps.
- Added a local HTTP bridge and Chrome/Edge extension for checking references inside Claude web and other regular web pages.
- Added pasted full URL/DOI link checking in the browser extension for detecting links that point to a different paper.
- Removed short-label/hidden-link auto-detection from selected-text checking. Links are now checked only after users paste a complete URL/DOI into the extension panel.
- Added a browser-extension floating button switch, side panel hardening, source-priority chips, and auto-close behavior after starting a popup check.
- Updated the browser extension icon to use the same RefChecker app logo.
- Set test build version metadata to `1.2.0-beta.1`.

### Fixed

- Fixed selected-text floating-button requests so they send plain selected reference text only.
- Fixed extension documentation and user guidance for `arXiv` / `PNAS` short labels and pasted-link checking.

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

