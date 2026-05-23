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

`--output-dir` creates:

- `report.md`
- `result.csv`

The old CLI options still work, including `--output`, `--csv`, `--threshold`, `--delay`, `--email`, `--no-openalex`, and `--no-dblp`.

## Packaging

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
flutter build windows
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
