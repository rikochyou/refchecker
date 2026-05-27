# Flutter + Python Desktop Build

This repository now contains two pieces:

- `check_bib_crossref.py`: the Python verification backend.
- `lib/main.dart`: the Flutter desktop UI.

The current machine did not have `flutter` on `PATH` when the UI was added, so the generated Windows/macOS runner folders are intentionally bootstrapped with Flutter's official generator.

## Development Setup

1. Install Flutter and enable desktop support.

```powershell
flutter config --enable-windows-desktop
flutter config --enable-macos-desktop
```

2. Generate platform runner files.

```powershell
.\tool\bootstrap_flutter.ps1
```

3. Install Python dependencies.

```powershell
python -m pip install -r requirements.txt
```

4. Run the Flutter app.

```powershell
flutter run -d windows
```

During development, the app calls `python check_bib_crossref.py ...`.

## Backend Contract

The Flutter app calls the backend with:

```text
check_bib_crossref.py input.bib --jsonl-progress --output-dir output-folder
```

The backend writes human logs to stderr and JSONL events to stdout:

- `started`
- `entry_started`
- `entry_finished`
- `summary`
- `error`

When the desktop UI tests API keys or a custom REST profile, it calls the backend for the selected source only, for example:

```text
check_bib_crossref.py --test-api-keys --jsonl-progress --sources springer
check_bib_crossref.py --test-api-keys --jsonl-progress --sources custom:my-api --custom-rest-profiles custom_rest_profiles.json
```

The backend then emits:

- `api_key_test_started`
- `api_key_test_source_started`
- `api_key_test_result`
- `api_key_test_summary`

`--output-dir` creates:

- `report.md`
- `result.csv`

The old CLI options still work, including `--output`, `--csv`, `--threshold`, `--delay`, `--email`, `--sources`, `--no-openalex`, `--no-semantic-scholar`, `--no-arxiv`, `--no-pubmed`, `--springer-api-key`, `--ieee-api-key`, `--core-api-key`, `--test-api-keys`, and `--no-dblp`. New verification options are `--search-mode strict|parallel` (default `strict`) and `--doi-check auto|off` (default `auto`). Optional LLM-assisted parsing is controlled by `--llm-parse-mode off|auto|always`, `--llm-provider`, `--llm-model`, `--llm-base-url`, and `REFCHECKER_LLM_API_KEY`; any non-off mode is LLM-first and falls back to local rules only for missing fields/rows. It only extracts explicit reference fields and does not judge authenticity. `--delay` is clamped to a safe minimum of `0.5` seconds. Custom REST sources can be supplied with `--custom-rest-profiles`; Brave/Search-style profiles marked as web evidence are rendered as auxiliary clickable links instead of structured bibliographic metadata.

## Custom REST / Brave Web Evidence

Desktop data-source cards support API-key visibility toggles so users can verify a copied key without retyping it. For Brave Search/Research API, use a Custom REST Profile with `evidenceType: "web"` and `apiKeyHeader: "X-Subscription-Token"`.

Implementation expectation:

- The backend returns `web_evidence`, `evidence_kind`, `web_evidence_note`, `web_evidence_results`, `web_evidence_links`, and `snippet` fields for web evidence profiles.
- The desktop result panel and browser extension display these results as auxiliary evidence with clickable URLs.
- Web evidence must not be used to fabricate standard citation metadata.

See `CUSTOM_REST_BRAVE_SEARCH.md`.

## Packaging

Recommended one-command Windows package:

```powershell
.\tool\package_windows.ps1
```

Packaging now creates a short incremental build version automatically. The
format is:

```text
<base-version>.<build-number>
```

For example: `1.2.0.1`, then `1.2.0.2`,
`1.2.0.3`, and so on. The local counter is stored in
`.refchecker_build_state.json` and the script also scans `dist_portable/` to
avoid reusing an existing package number.

Use `-Version` to choose the base release line while still getting a unique
package version:

```powershell
.\tool\package_windows.ps1 -Version 1.3.0
```

If you need to reproduce an exact version string, pass `-ExactVersion`:

```powershell
.\tool\package_windows.ps1 -Version 1.3.0 -ExactVersion
```

The script will:

1. install/confirm Python backend dependencies,
2. rebuild `backend/refchecker_backend.exe` with PyInstaller,
3. run `flutter build windows --release --dart-define APP_VERSION=...`,
4. assemble a portable directory under `dist_portable/`,
5. create a matching `.zip`,
6. run a backend smoke test against the packaged executable.

The app header, backend report, JSONL summary, HTTP bridge `/health` response,
package manifest, `VERSION.txt`, and packaged browser extension `version_name`
should use the same unique package version string.

### Update notifications

On startup, the desktop app checks GitHub Releases:

```text
https://api.github.com/repos/rikochyou/refchecker/releases?per_page=20
```

If the newest release tag is greater than the local app version, the app shows a
banner with the latest version, release notes, and buttons for viewing the
release or downloading the portable `.zip`. This is a notification-only update
flow: users still download and replace the portable package manually.

### Manual packaging

Build the Python backend first:

```powershell
.\tool\build_backend.ps1 -Platform windows
```

This creates `backend/refchecker_backend.exe`. For macOS, run the same script on macOS with:

```powershell
./tool/build_backend.ps1 -Platform macos
```

Then build Flutter:

```powershell
flutter build windows --release --dart-define APP_VERSION=1.2.0
```

For release packaging, copy the `backend` folder next to the built app executable so the runtime layout is:

```text
RefChecker.exe
backend/
  refchecker_backend.exe
```

On macOS, copy `backend/refchecker_backend` next to the resolved app executable path used by Flutter's desktop runner. Internal unsigned builds may trigger OS security prompts.

## Quick Backend Smoke Test

```powershell
python check_bib_crossref.py smoke_missing_title.bib --jsonl-progress --output-dir smoke_output --delay 0
```

Expected output includes JSONL `started`, `entry_started`, `entry_finished`, and `summary` events, plus `smoke_output/report.md` and `smoke_output/result.csv`.

## Release Notes

For the current stable release copy, see `RELEASE_NOTES_v1.2.0.md`.
