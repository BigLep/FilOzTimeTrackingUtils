---
name: filoz-monthly-invoice
description: >
  Run the complete monthly invoicing workflow for FilOz. Use this skill whenever
  the user mentions their FilOz invoice, monthly billing, or says it's time to
  submit their invoice — even if they don't say "skill" or "workflow". Covers
  all 9 steps: export from Timing, import to Google Sheet, anomaly review,
  create invoice tab, download XLSX, audit against history, and Toku upload prep.
---

# FilOz Monthly Invoice Workflow

## Execution context

- **Project**: `/Users/sal/Documents/Code/PersonalProjects/FilOzTimeTrackingUtils`
- **Run commands via**: the `Bash` tool directly. (Older runs used `mcp__Control_your_Mac__osascript` → `do shell script`; that MCP is often not connected, and plain Bash works fine.)
- **Command prefix**: `cd '/Users/sal/Documents/Code/PersonalProjects/FilOzTimeTrackingUtils' && /opt/homebrew/bin/uv run python -m filoz_time_tracking.<module> <args> 2>&1`
- **Billing period**: 10th of previous month through 9th of invoice month. `2026-6` → `2026-05-10` to `2026-06-09`.
- **Contract**: Travel days bill at 8 hrs/day regardless of actual hours worked.
- **Toku upload**: Manual — always the final action. https://app.toku.com/myinfo/invoices

---

## Workflow

Ask the user for the invoice period (e.g. `2026-6`) if not provided. Run steps in order; the **[README](../../../README.md)** is the authoritative reference for command details, flags, column mappings, and troubleshooting — this skill file covers orchestration and reasoning guidance only.

| # | Command | Notes |
|---|---------|-------|
| 1 | `export_timing_report --invoice YYYY-N` | Timing app must be running. Note the output filename for step 2. |
| 2 | `import_timing_export <file>.xlsx --dry-run` | Verify row count, date range, Notes look like `"<Child Project>: <task>"` (e.g. `"Filecoin Onchain Cloud: PR review"`, `"Communication: Morning comms"`). Stop if anything looks wrong. |
| 3 | `import_timing_export <file>.xlsx` | Confirm import count matches dry-run. |
| 4 | `analyze_tracking --invoice YYYY-N` | **Pause here** — see reasoning guidance below. |
| 5 | `create_invoice_tab --invoice YYYY-N --dry-run` | Verify week count, days/week, total hours before proceeding. |
| 6 | `create_invoice_tab --invoice YYYY-N` | Confirm totals match the dry-run. |
| 7 | `download_invoice_sheet --invoice YYYY-N` | Saves `biglep invoice - YYYY-N.xlsx` in the project directory. |
| 8 | `audit_invoice --invoice YYYY-N` | **Pause here** — see audit reasoning below. |
| 9 | Manual Toku upload | Tell user to upload `biglep invoice - YYYY-N.xlsx` at https://app.toku.com/myinfo/invoices |

---

## Step 4 — Anomaly review reasoning

Read the output and present a summary to the user before continuing. Things to check:

- **Missing weekdays**: Check the user's calendar before flagging — vacation gaps are expected.
- **Travel days**: Entries with travel keywords (flight, airport, driving to, colo + travel) must bill 8 hrs/day per contract. **Only work travel qualifies.** Personal trips found on the calendar explain absences but bill nothing; check whether the FilOz project actually has travel entries before applying the 8 hr/day rule.
- **Unusual hours**: Entries >8 hrs may be a forgotten timer stop. Entries <5 min are likely noise.
- **Overlapping entries**: Usually **false positives from after-midnight work**. The analyzer attributes a post-midnight entry (e.g. `0:54-1:43`) to the prior workday, then reports it as overlapping that day's morning entries. Confirm via `mcp__timing__list_time_entries` for the day before flagging to the user: if the raw entries are contiguous and non-overlapping, say so rather than passing the warning through.

Don't proceed to step 5 until the user confirms.

---

## Step 8 — Audit reasoning

**Reason over the output yourself** — don't just relay it. Check:

1. **Hours cross-check** — invoice total vs tracking sheet should differ by <0.05 hrs.
2. **Rates** — USD and FIL rates should match all recent invoices. Any change is significant.
3. **Totals vs history** — compare to recent months. Drops are fine if there was vacation; jumps deserve a comment.
4. **Week breakdown** — weeks starting Sunday or with 6+ days include weekend work. Flag for user confirmation.
5. **Dates** — period must be exactly 10th-of-prev-month through 9th-of-invoice-month. Due date = last day of invoice month.
6. **Addresses** — any diff from previous invoice is a red flag.
7. **Bank details** — any diff from previous invoice is a red flag.

### Timing MCP spot-checks (if available)

If the Timing MCP server is connected (see [setup](https://timingapp.com/help/mcp)), use `mcp__timing__list_time_entries` to corroborate the audit data against the raw timer source of truth:

- **High-hour days** — For any day flagged with unusually high hours (e.g. >10 hrs), query that day's entries by project (FilOz parent project with `include_child_projects: true`) and verify there are multiple distinct entries with reasonable durations. A single entry spanning many hours suggests a stuck timer.
- **Low-hour / weekend days** — For days with very few hours (e.g. <1 hr on a weekend), confirm the entries look like a quick check-in rather than missing data.
- **Search by project, not text** — Many entries have no "FilOz" in their title/notes. Always query using the FilOz parent project ID `3777560271585728256` with `include_child_projects: true` rather than `search_query`.

Report spot-check findings alongside the audit summary.

Summarise what looks clean and what deserves a second look. Pause and ask the user to confirm before step 9.

---

## Error handling

| Error | What to do |
|---|---|
| `Tab 'YYYY-N' already exists` | Ask user: re-run after partial failure, or intentional? |
| `No tracking data found for 'YYYY-MM'` | Import (step 3) may not have run, or Toku Invoice column isn't filled. |
| `Template tab 'YYYY-N-1' not found` | Previous month's tab is missing from the invoices workbook. Ask the user. |
| `AppleEvent timed out (-1712)` | Retry with `--timeout 1800`. |
| Drive API 403 | Enable the Google Drive API in Google Cloud Console for the service account's project. |

---

## After every run — continuous improvement

Each invoice run is an opportunity to improve the workflow. Before closing out, review the session for:

- **Friction or manual workarounds** — Did any step require extra flags, retries, or manual intervention not covered here? Update the error handling table or add notes to the relevant step.
- **New spot-check patterns** — Did the Timing MCP or audit reveal a new class of anomaly worth checking routinely? Add it to the Step 4 or Step 8 guidance.
- **Stale examples or defaults** — Do invoice month examples, project IDs, or other hardcoded values need updating?
- **README drift** — If you changed this skill file, check whether the README's workflow section or setup steps need a matching update (and vice versa). The README is the source of truth for command documentation; this skill is the source of truth for orchestration and reasoning.

Make the edits directly — don't just suggest them. Small improvements compound over time.
