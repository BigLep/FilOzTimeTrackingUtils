# Implementation Plan: Timing FilOz XLSX export automation

**Branch**: `002-timing-xlsx-export` | **Date**: 2026-04-10 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification plus operator preference for **uv-run Python CLI**, **UI parity** (screenshot: Reports Advanced / Raw Data / Excel / FilOz subtree), and question **AppleScript vs Web API**.

## Summary

Automate the manual Timing **Reports** export for **FilOz and all subprojects** into an **Excel (.xlsx)** file for a given **inclusive date range** or **`--invoice YYYY-M`** billing window (10th of prior month → 9th of invoice month). **Primary approach**: drive **TimingHelper** via **JXA/AppleScript** from Python (`osascript`) so output matches Timing’s native workbook and stays compatible with `parse_timing_export` / billing import. **Timing Web API** remains a valid **later alternative** (fetch JSON + build XLSX) if off-Mac or scripting constraints require it — see [research.md](./research.md).

## Technical Context

**Language/Version**: Python `>=3.9` (repo standard via uv)  
**Primary Dependencies**: Existing `openpyxl`, `python-dotenv`; **no new HTTP client required** for the primary path. Optional future API path would add an HTTP library per constitution.  
**Storage**: Output `.xlsx` file on local filesystem only.  
**Testing**: Pragmatic (constitution Principle V): manual compare against Timing UI + `import_timing_export --dry-run`; automated tests optional unless spec tightens.  
**Target Platform**: **macOS** (Timing + TimingHelper present).  
**Project Type**: CLI utility (`uv run python -m …`).  
**Performance Goals**: Human-scale; completion within spec SC-001 (~3 minutes end-to-end after setup).  
**Constraints**: **Read-only** vs Timing data (spec FR-008); **Timing Connect / advanced scripting** required for Helper automation; subprocess / Apple Events sandbox as on typical Mac dev setup.  
**Scale/Scope**: Single-operator, single project subtree (`FilOz`), monthly-or-custom ranges.

## Constitution Check

*GATE: Passed Phase 0. Re-checked after Phase 1 design.*

Verify against `.specify/memory/constitution.md`:

- **Charter (Principle I):** Advances **billing import** by producing the same **XLSX** shape the importer already consumes. Optional **Timing Web API** not required for MVP; documented as alternative in `research.md`.
- **Sheet formulas (Principle II):** Export feature does **not** append to Sheets; no change to Tracking append shape.
- **Safe ops (Principle III):** Export-only; no sheet writes, no Timing mutations. Surface Timing/OS errors clearly; no destructive defaults.
- **Secrets (Principle IV):** Primary path uses **no** Timing API token; if API fallback is implemented later, use `.env` and `.env.example` per constitution.
- **Quality (Principle V):** Pragmatic validation; dry-run of **downstream** import is the strongest integration check.
- **API (Principle VI):** N/A for primary path. Any future API usage MUST use bearer auth, respect [Timing limits](https://web.timingapp.com/llms.txt), default read-only.

## Project Structure

### Documentation (this feature)

```text
specs/002-timing-xlsx-export/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── cli-export-timing.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
filoz_time_tracking/
├── config.py
├── timing_format.py       # Parses XLSX produced by Timing (consumer of this feature)
├── export_timing_report.py  # NEW: CLI + date/invoice resolution + osascript bridge
└── …

pyproject.toml             # Optional: [project.scripts] entry for convenience
README.md                  # Document new uv invocation
```

**Structure Decision**: Single package `filoz_time_tracking`; one new module for export CLI. Reuse `timing_format.parse_timing_export` optionally for post-export validation (row count / headers), not for generation.

## Complexity Tracking

> No constitution violations requiring justification.

## Phase 0 → Phase 1 status

| Artifact | Path | Status |
|----------|------|--------|
| Research | [research.md](./research.md) | **AppleScript/JXA (TimingHelper) recommended** over Web API for UI parity and importer compatibility; API documented as alternative |
| Data model | [data-model.md](./data-model.md) | Complete |
| Contracts | [contracts/cli-export-timing.md](./contracts/cli-export-timing.md) | Complete |
| Quickstart | [quickstart.md](./quickstart.md) | Complete |

## Post-design Constitution Check

Unchanged: design stays read-only, XLSX-first, uv CLI, no sheet formula duplication.

## Operator UI parity (reference)

Target equivalence with Timing **Reports** Advanced mode:

- **Group by**: Raw Data (for Export) → scripting `firstGroupingMode = "raw"`.
- **Include**: Time entries ✓, App usage ✗, short entries ✓; activity grouping in export ✗.
- **Format**: Excel; duration **XX:YY:ZZ** (confirm enum names in TimingHelper dictionary).
- **Scope**: FilOz root project including **all subprojects** (verify Timing scripting API covers subtree).

Screenshot reference (Reports UI parity): `/Users/sal/.cursor/projects/Users-sal-Documents-Code-Personal-Projects-FilOzTimeTrackingUtils/assets/image-972e6009-eff7-495d-9e19-fd60ef627c1e.png`.

## Next step

Run **`/speckit.tasks`** to break implementation into tracked tasks.
