<!--
Sync Impact Report
- Version change: unversioned template (placeholders) → 1.0.0
- Principles: (all new) I. Single pipeline — Timing → Tracking; II. Sheet owns derived fields;
  III. Safe operations; IV. Secrets and PII off-repo; V. Pragmatic quality (personal use)
- Added sections: Technology & repository layout; Workflow & operator ergonomics
- Removed sections: none (template placeholders only)
- Templates: .specify/templates/plan-template.md ✅ Constitution Check updated;
  .specify/templates/tasks-template.md ✅ path conventions for filoz_time_tracking/;
  .specify/templates/spec-template.md ✅ project-context note for single-operator scope
- Commands: .cursor/commands/*.md — verified; no agent-specific names requiring change
- Follow-up TODOs: none
-->

# FilOz Time Tracking Utils Constitution

## Core Principles

### I. Single pipeline — Timing → Tracking

The project MUST preserve one primary job: read a **Timing App** Excel export (first worksheet,
headers in row 1) and append matching rows to the configured **Tracking** tab of the target Google
Sheet. The Timing export MUST expose columns **Start Date**, **End Date**, **Project**, and
**Title**; parsing MUST fail clearly if any are missing. New features MUST extend this pipeline,
replace it only with an explicit spec and migration note, or be justified in the plan’s
Constitution Check.

**Rationale:** The repo is a brownfield bridge between two systems; scope creep without a named
contract breaks the monthly workflow.

### II. Google Sheet owns derived fields

Rows appended to Tracking MUST be five columns: **Day**, **Start**, **End**, empty string for
column D, **Notes**—so the sheet’s Duration and downstream formulas remain authoritative. Appends
MUST use `USER_ENTERED` (or equivalent) so the sheet interprets dates/times like manual entry.
Python MUST NOT duplicate Duration, week number, decimal hours, invoice fields, or other columns
the sheet calculates.

**Rationale:** README and operators depend on sheet logic; duplicating it in code risks drift.

### III. Safe operations and observability

Any code path that writes to Google Sheets MUST support or preserve **dry-run** or equivalent
preview before bulk write. Credential setup MUST remain verifiable without writes (e.g. read-only
check). Operators MUST be able to limit how many rows are applied in one run when the CLI
supports it. New bulk or external side effects SHOULD follow the same pattern: preview first,
bounded blast radius.

**Rationale:** Personal tooling still needs guardrails against bad exports or wrong sheet targets.

### IV. Secrets and PII off-repository

Configuration MUST load from environment (e.g. `FILOZ_SHEET_ID`, `FILOZ_TRACKING_SHEET_NAME`,
`GOOGLE_APPLICATION_CREDENTIALS`) with `.env` for local use; `.env.example` MUST stay in sync
when variables change. Service account JSON, `.env`, and Timing exports MUST remain gitignored or
untracked. Commits MUST follow `AGENTS.md`: Conventional Commits and no PII, credentials, or
identifiers that do not belong in history.

**Rationale:** The tool touches real work data and Google APIs; leakage is the main operational
risk.

### V. Pragmatic quality (personal, single-operator)

The primary user is the maintainer. Code MUST stay readable and dependency changes justified
(`pyproject.toml` / `uv.lock`). Formal automated test suites, coverage gates, and multi-party code
review are OPTIONAL unless a feature specification explicitly requires them. Routine changes SHOULD
be validated with `--dry-run`, `--test-credentials`, and spot-checks in the sheet.

**Rationale:** Keeps delivery friction low while leaving the door open to stricter quality when a
feature demands it.

## Technology & repository layout

- **Language:** Python `>=3.9`, package **`filoz-time-tracking-utils`**, installed and run with
  **[uv](https://docs.astral.sh/uv/)** (`uv sync`, `uv run`).
- **Layout:** Python package under `filoz_time_tracking/` — `config.py` (env), `timing_format.py`
  (XLSX parse), `sheet_format.py` (row shape and Notes), `google_sheet.py` (gspread client and
  append), `import_timing_export.py` (CLI via `python -m`).
- **Dependencies:** `openpyxl`, `gspread`, `google-auth`, `python-dotenv` (see `pyproject.toml`).
- **Operator docs:** `README.md` is the source for setup, env vars, CLI flags, and column mapping.

## Workflow & operator ergonomics

- **Monthly flow:** Export month from Timing as XLSX → run with dry-run → append to Tracking → use
  sheet pivots/invoicing as today.
- **CLI:** Document new flags or arguments in `README.md` when behavior is user-visible.
- **SpecKit:** Feature specs and plans live under `/specs/` per templates; they MUST not contradict
  principles I–IV without a constitution amendment.

## Governance

This constitution is the authoritative checklist for SpecKit planning commands in this
repository. It does not replace `README.md` or `AGENTS.md`; it constrains what “done” means for
planned features.

- **Amendments:** Edit `.specify/memory/constitution.md`, bump **Version** per semantic versioning
  (MAJOR: incompatible principle or removal; MINOR: new principle or material new section;
  PATCH: clarification or wording only), update **Last Amended** to ISO date, and refresh the Sync
  Impact Report comment at the top of this file.
- **Compliance:** For personal use, the author verifies alignment before merge; `/speckit.plan`
  MUST fill the Constitution Check from this file.
- **Ratification:** First adoption of this document as the project constitution (replacing
  template placeholders).

**Version**: 1.0.0 | **Ratified**: 2025-03-23 | **Last Amended**: 2025-03-23
