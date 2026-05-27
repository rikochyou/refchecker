# Changelog

## Unreleased

- No changes yet.

## v1.2.0 - 2026-05-27

### Added

- Added an independent DOI exact-check stage before the database search chain.
- Added `--search-mode strict|parallel` and `--doi-check auto|off` for CLI/MCP/HTTP.
- Added optional LLM-assisted reference-field parsing (`off|auto|always`) for messy pasted/TXT/DOCX references. `auto` is LLM-first and falls back to rule-parsed fields when the LLM cannot extract a field.
- Added Brave/web-search custom REST evidence handling: web results are shown as auxiliary evidence with clickable links instead of pretending to be bibliographic metadata.
- Added API-key visibility toggles for custom data-source cards.
- Added a dedicated Brave Search/Research custom REST guide and example profile.
- Added desktop startup update notifications that check GitHub Releases and show a download banner when a newer RefChecker package is available.
- Added Windows single-instance behavior: launching RefChecker again focuses/restores the existing window instead of opening a second copy.

### Changed

- Browser extension and desktop UI now share strict/parallel search mode semantics and show DOI status, actual query path, adopted source, and LLM parsing mode consistently.
- CSV/Markdown reports include DOI exact-check and query trace fields.
- Browser extension Brave/web-search results now render as auxiliary web evidence with clickable result links.
- Windows packaging now keeps secrets out of portable packages and includes a package manifest, package version metadata, and privacy note.

### Fixed

- Hardened the browser-extension HTTP bridge lifecycle. The desktop app now starts it with a parent PID and heartbeat file, and the helper exits when the desktop app exits or the heartbeat becomes stale.
- Fixed stale HTTP bridge processes that could remain after the desktop app exited and lock the packaged executable.

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

