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

The old CLI options still work, including `--output`, `--csv`, `--threshold`, `--delay`, `--email`, `--sources`, `--no-openalex`, `--no-semantic-scholar`, `--no-arxiv`, `--no-pubmed`, `--springer-api-key`, `--ieee-api-key`, `--core-api-key`, `--test-api-keys`, and `--no-dblp`. `--delay` is clamped to a safe minimum of `0.5` seconds. Custom REST sources can be supplied with `--custom-rest-profiles`.

## Packaging

Recommended one-command Windows package:

```powershell
.\tool\package_windows.ps1 -Version 1.2.0-beta.1
```

The script will:

1. install/confirm Python backend dependencies,
2. rebuild `backend/refchecker_backend.exe` with PyInstaller,
3. run `flutter build windows --release --dart-define APP_VERSION=...`,
4. assemble a portable directory under `dist_portable/`,
5. create a matching `.zip`,
6. run a backend smoke test against the packaged executable.

The app header, backend report, JSONL summary, and package manifest should use the same version string.

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
flutter build windows --release --dart-define APP_VERSION=1.2.0-beta.1
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

For v1.1.0 release copy, see `RELEASE_NOTES_v1.1.0.md`.
