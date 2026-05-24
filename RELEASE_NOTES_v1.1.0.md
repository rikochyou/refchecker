# RefChecker v1.1.0 Release Notes

> App build: `1.1.0+2`  
> Release assets: `RefChecker_portable.zip` (Windows) / `RefChecker-v1.1.0-macOS.dmg` (macOS)

## Highlights

RefChecker v1.1.0 focuses on a more usable desktop workflow and advanced data-source extensibility.

### New / Improved

- Redesigned API configuration panel with card-based management.
- Added per-card **Enable** switch for API-backed and custom data sources.
- Added **Custom REST API Profile (JSON)** editor for advanced users.
- Custom REST Profile supports:
  - `endpoint`
  - `GET` / `POST`
  - `none` / `query` / `header` / `bearer` auth
  - query/body templates
  - custom headers
  - JSON result list path and field mappings
- Enabled custom REST sources now appear in the data-source search chain; disabled custom sources are hidden and not searched.
- Moved API connectivity testing into each API card.
- Added backend support for testing custom REST Profile connectivity.
- Added app version display in the desktop title bar.
- Locked request delay to a safe minimum of `0.50s` in both UI and backend.

### Fixed

- Fixed "deselect all" behavior so disabled custom sources are no longer left in the active search chain.
- Fixed mojibake/question-mark display issues in several UI labels.
- Fixed JSONL output for API connectivity tests in the bundled backend executable.
- Fixed garbled Chinese characters in "not found" reason messages (corrupted `????` literals in verifier.py).
- Fixed `PathAccessException` on macOS caused by sandbox entitlements conflicting with AppleScript file picker.

### CLI changes

- `--delay` now has a safe minimum of `0.5`; lower values are automatically clamped.
- Added/continued support for:

```bash
--custom-rest-profiles custom_rest_profiles.json
```

- Custom REST Profile connectivity can be tested with:

```bash
python check_bib_crossref.py \
  --test-api-keys \
  --sources custom:my-api \
  --custom-rest-profiles custom_rest_profiles.json
```

## Example Custom REST Profile

```json
{
  "id": "my-api",
  "name": "My Literature API",
  "endpoint": "https://api.example.com/search",
  "method": "GET",
  "authType": "bearer",
  "queryParams": {
    "q": "{title}",
    "year": "{year}"
  },
  "headers": {
    "Accept": "application/json"
  },
  "resultsPath": "results",
  "titlePath": "title",
  "authorsPath": "authors",
  "yearPath": "year",
  "doiPath": "doi",
  "urlPath": "url",
  "venuePath": "venue",
  "typePath": "type"
}
```

## Installation

### Windows

Download and unzip:

```text
RefChecker_portable.zip
```

Then run:

```text
refchecker_desktop.exe
```

The Windows portable package includes the Python backend executable:

```text
backend/refchecker_backend.exe
```

### macOS

Download the DMG:

```text
RefChecker-v1.1.0-macOS.dmg
```

Open the DMG and drag `refchecker_desktop.app` to Applications. The Python backend is bundled inside the app.

> macOS 首次运行时可能出现"已损坏"提示（未公证的应用），在终端执行以下命令即可：
> ```bash
> xattr -cr /Applications/refchecker_desktop.app
> ```

## Verification performed before packaging

- `flutter analyze`
- `flutter test`
- Python `py_compile`
- PyInstaller backend rebuild (macOS arm64)
- Flutter Windows release build
- Flutter macOS release build
- Backend API connectivity JSONL smoke test
- macOS sandbox/permission smoke test

## Notes

RefChecker is an assistant for screening suspicious references. A failed match does not prove that a reference is fabricated, and a successful match does not prove the citation is fully correct. Final decisions should still rely on DOI pages, publisher pages, the original paper, and human academic judgment.
