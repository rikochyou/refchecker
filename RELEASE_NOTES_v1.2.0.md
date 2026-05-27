# RefChecker v1.2.0 Release Notes

Release date: 2026-05-27

This is the stable v1.2.0 release. It promotes the v1.2.0 beta work to a formal release and includes the latest desktop, browser-extension, custom REST, and HTTP bridge lifecycle fixes.

## Highlights

- Desktop app, CLI, MCP server, and browser extension now share the same DOI exact-check and search-chain semantics.
- Browser extension checks can use the local HTTP bridge started by the desktop app.
- Optional LLM parsing is available for messy references. `auto` is LLM-first and falls back to local rule fields when the LLM cannot extract a field.
- Custom REST sources can be used for auxiliary web evidence such as Brave Search/Research API results.
- Brave/web evidence is displayed as auxiliary evidence with clickable links, not as fabricated bibliographic metadata.
- API key fields in custom data-source cards can be shown/hidden with an eye button.
- Browser extension Brave/web evidence cards also use clickable links so users can open result pages directly.
- The local HTTP bridge now exits when the desktop app exits, using both parent-PID and heartbeat-file checks.

## Security / privacy

- The portable package does not include local `settings.json`, `.env`, API-key files, `custom_rest_profiles.json`, run logs, or generated reports.
- API keys remain in the user's local settings or process environment and are not copied into the release package.
- Packaging runs a secret guard before creating the final ZIP.
- The Brave example profile keeps `apiKey` empty; users should only enter real keys in local settings or untracked local profile files.

## Included docs

- `README.md`
- `BROWSER_EXTENSION_CLAUDE_WEB.md`
- `CUSTOM_REST_BRAVE_SEARCH.md`
- `MCP_CLAUDE_DESKTOP.md`
- `CHANGELOG.md`
- `RELEASE_NOTES_v1.2.0.md`
- `examples/brave_search_custom_rest_profile.example.json`

## Packaging / verification

The Windows portable package is generated with an exact stable version:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tool\package_windows.ps1 -Version 1.2.0 -ExactVersion
```

Expected release artifacts:

- `dist_portable\RefChecker_portable_v1.2.0`
- `dist_portable\RefChecker_portable_v1.2.0.zip`
