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
- **Run commands via**: `mcp__Control_your_Mac__osascript` → `do shell script`
- **Command prefix**: `cd '/Users/sal/Documents/Code/PersonalProjects/FilOzTimeTrackingUtils' && /opt/homebrew/bin/uv run python -m filoz_time_tracking.<module> <args> 2>&1`
- **Billing period**: 10th of previous month through 9th of invoice month. `2026-6` → `2026-05-10` to `2026-06-09`.
- **Contract**: Travel days bill at 8 hrs/day regardless of actual hours worked.
- **Toku upload**: Manual — always the final action. https://app.toku.com/myinfo/invoices

---

## Workflow

Ask the user for the invoice period (e.g. `2026-6`) if not provided. Run steps in order; the README has full command documentation.

| # | Command | Notes |
|---|---------|-------|
| 1 | `export_timing_report --invoice YYYY-N` | Timing app must be running. Note the output filename for step 2. |
| 2 | `import_timing_export <file>.xlsx --dry-run` | Verify row count, date range, Notes look like `"FilOz: <task>"`. Stop if anything looks wrong. |
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
- **Travel days**: Entries with travel keywords (flight, airport, driving to, colo + travel) must bill 8 hrs/day per contract.
- **Unusual hours**: Entries >8 hrs may be a forgotten timer stop. Entries <5 min are likely noise.
- **Overlapping entries**: Flag clearly.

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
