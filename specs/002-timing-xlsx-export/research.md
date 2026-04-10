# Research: Timing XLSX export automation

**Feature**: `002-timing-xlsx-export`  
**Date**: 2026-04-10

## 1. AppleScript / JavaScript for Automation (TimingHelper) vs Timing Web API

### Decision

Use **TimingHelper via JXA (JavaScript for Automation)** or **AppleScript**, invoked from the existing **Python + uv** CLI (`osascript` subprocess), as the **primary** integration for generating the FilOz XLSX export. Treat the **Timing Web API** as an optional **future** path if headless/off-Mac or scripting reliability becomes problematic.

### Rationale

1. **Parity with the operator’s UI**  
   The manual workflow uses **Reports → Advanced → Group by “Raw Data (for Export)”**, **Time entries on**, **App usage off**, **Excel** format, **duration XX:YY:ZZ**, **include short entries**, **Group activities in export off**, and project scope **FilOz & subprojects**.  
   Official examples show the same dimensions via scripting: `ReportSettings` (`firstGroupingMode = "raw"`, `timeEntriesIncluded`, `appUsageIncluded`) and `ExportSettings` (`fileFormat`, `durationFormat`, `shortEntriesIncluded`), then `saveReport(… between: … and: … to: …)` — see [Exporting and Importing Timing Time Entries (JavaScript)](https://timingapp.com/help/javascript-time-entries) and [Exporting Data via AppleScript](https://timingapp.com/help/applescript-export).

2. **Drop-in compatibility with billing import**  
   This repo’s `parse_timing_export` expects Timing’s Excel layout with **Start Date**, **End Date**, **Project**, **Title** (constitution Principle I). A native Timing-generated XLSX maximizes column stability versus hand-building a workbook from API JSON.

3. **Local data and no API quota**  
   Automation runs on the Mac where Timing already has the database; no bearer token, network dependency, or hourly rate limits described in [`llms.txt`](https://web.timingapp.com/llms.txt).

4. **Subscription gate (accepted)**  
   Timing’s samples require **Timing Connect / advanced scripting** (`advancedScriptingSupportAvailable`). The operator already uses Reports export; we document this prerequisite and fail fast with the vendor message if unsupported.

### Alternatives considered

| Approach | Pros | Cons |
|----------|------|------|
| **Timing Web API** (`GET /time-entries`, filters, `include_child_projects`) | No GUI automation; works off-machine if data is synced; aligns with constitution “optional API” | Requires **token** (`.env`), **pagination**, careful **date/time zone** alignment; must **build XLSX** (openpyxl) and match column semantics; subject to **rate limits** and sync latency |
| **Web API report endpoint** (`GET /report`) | Aggregated/report-shaped JSON | Not a drop-in replacement for Raw Data Excel; still custom formatting |
| **Pure AppleScript from shell** (no Python) | No Python bridge | Duplicates CLI patterns (invoice shorthand, paths), inconsistent with repo |

### Implementation notes (verify during build)

- Map UI **“Excel”** and **“XX:YY:ZZ”** to the exact `fileFormat` / `durationFormat` strings TimingHelper expects (vendor samples use `CSV` + `seconds`; Excel enums differ — validate against [AppleScript reference](https://timingapp.com/help/applescript) / Script Editor dictionary).
- **Project scoping**: AppleScript sample uses `for projects (projects whose name is "ProjextXYZ")`; confirm subtree behavior matches **FilOz & N subprojects** or pass the correct project filter API from TimingHelper.

## 2. uv / CLI entry style

### Decision

Add a new module (e.g. `filoz_time_tracking.export_timing_report`) and document **`uv run python -m filoz_time_tracking.export_timing_report`** mirroring [`README.md`](../../README.md) usage for `import_timing_export`.

### Rationale

Matches existing operator workflow and constitution “`uv sync`, `uv run`”.

## 3. Conflicting inputs (spec FR-005)

### Decision

**Reject** the run if both **invoice shorthand** and **explicit `--start` / `--end`** are provided, with a clear error and usage hint (safest for invoicing).

### Rationale

Avoid silent wrong billing periods; spec allows “rejection with a clear reason.”
