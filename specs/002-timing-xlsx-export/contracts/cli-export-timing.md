# Contract: `export_timing_report` CLI

**Feature**: `002-timing-xlsx-export`  
**Consumer**: Operator (shell)  
**Producer**: `filoz_time_tracking.export_timing_report` (Python, `uv run`)

## Invocation

```bash
uv run python -m filoz_time_tracking.export_timing_report [OPTIONS]
```

## Arguments and flags

| Name | Required | Description |
|------|----------|-------------|
| `--output`, `-o` | Recommended | Output `.xlsx` path. If omitted, behavior defined in implementation (e.g. derive from range or cwd). |
| `--start` | One of: both `--start`+`--end`, or `--invoice` | Inclusive start date `YYYY-MM-DD`. |
| `--end` | Paired with `--start` | Inclusive end date `YYYY-MM-DD`. |
| `--invoice` | One of: `--invoice`, or `--start`+`--end` | Invoice shorthand `YYYY-M` or `YYYY-MM`. |
| `--project` | No | Timing root project name (default `FilOz`). |
| `--timeout` | No | Apple Event timeout in seconds for the wrapped `osascript` run (default `900`). |

**Precondition**: `--invoice` MUST NOT be combined with `--start` / `--end`. Violation → **exit code non-zero** + stderr message.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success; XLSX written (may be empty sheet if Timing returns no rows — see spec FR-007). |
| `1` | User error (bad dates, conflicting flags, missing TimingHelper, scripting unavailable). |
| `2` | Runtime failure (osascript/Timing error, disk write failure). |

*(Exact numeric split may fold into 1/2 only; document final mapping in README.)*

## Side effects

- **Read-only** regarding Timing’s stored time data: local **TimingHelper** `save report` only (no **Timing Web API**, no POST/PATCH/DELETE to time entries or projects).
- **Writes** only: target XLSX file (and a short-lived temp `.js` file for JXA during the export).

## Observability

- Stdout: concise summary (path, row count if cheap to obtain, effective date range).
- Stderr: errors only.

## Compatibility

Output MUST remain ingestible by `parse_timing_export` without column renames, per constitution Principle I.
