<!--
Sync Impact Report
- Version change: 2.0.0 → 3.0.0
- Principles modified: I. narrowed to billing import first with optional API support; IV. secrets
  wording simplified (LLM keys removed); VI. narrowed to Timing Web API compliance only
- Principles added: none
- Sections modified: Technology & repository layout; Workflow & operator ergonomics (scope narrowed)
- Removed sections: none
- Templates: plan-template.md ✅ Constitution Check; spec-template.md ✅ project context;
  tasks-template.md ✅ optional API task hints
- README.md ✅ scope paragraph; .env.example ✅ Timing API placeholder
- Follow-up TODOs: none
-->

# FilOz Time Tracking Utils Constitution

## Core Principles

### I. Billing import first; Timing API optional support

The project serves **one primary goal** and one optional support path. Implementations MUST declare
which path they advance; specs MUST NOT silently contradict them.

1. **Billing import (primary):** Ingest **Timing App** time entries from an **Excel export**
   (first worksheet, row 1 headers) and append rows to the configured **Tracking** tab. Required
   export columns remain **Start Date**, **End Date**, **Project**, and **Title**; parsing MUST fail
   clearly if any are missing.

2. **Timing Web API (optional):** Ingest or inspect time-entry and related data via the
   **Timing Web API**
   (`https://web.timingapp.com/api/v1`). API behavior, auth, and agent-oriented documentation are
   defined by the vendor; the canonical machine-oriented reference for this repo is
   **[`llms.txt`](https://web.timingapp.com/llms.txt)** (see also Postman/OpenAPI linked there).

Categorization is intentionally delegated to **Timing App's native UI and rules**. This repository
MUST NOT assume custom categorization logic, LLM suggestion pipelines, or competing categorization
workflows unless the constitution is amended again.

**Rationale:** The maintainer is focused on reliable billing import and may use API access
selectively, while relying on Timing's built-in categorization UX and automation.

### II. Google Sheet owns derived fields

Rows appended to Tracking MUST be five columns: **Day**, **Start**, **End**, empty string for
column D, **Notes**—so the sheet’s Duration and downstream formulas remain authoritative. Appends
MUST use `USER_ENTERED` (or equivalent) so the sheet interprets dates/times like manual entry.
Python MUST NOT duplicate Duration, week number, decimal hours, invoice fields, or other columns
the sheet calculates.

**Rationale:** Operators depend on sheet logic; duplicating it in code risks drift.

### III. Safe operations and observability

Any code path that **writes** to Google Sheets or **mutates** Timing data via the API MUST offer
or preserve **dry-run**, **preview**, **limits**, and/or **explicit confirmation** patterns
consistent with the existing CLI ethos unless a spec documents a narrower, justified exception.
Credential setup for Google and for Timing MUST remain **verifiable without destructive writes**
where the APIs allow (e.g. read-only checks). New bulk or external side effects MUST default to
bounded blast radius.

**Rationale:** API keys and sheet writes can damage months of billing or time records in one run.

### IV. Secrets and PII off-repository

Configuration MUST load from environment (e.g. `FILOZ_SHEET_ID`, `FILOZ_TRACKING_SHEET_NAME`,
`GOOGLE_APPLICATION_CREDENTIALS`, and **Timing API bearer token**) with `.env` for local use;
**`.env.example` MUST list every supported variable name** (values empty or placeholder). Service
account JSON, `.env`, Timing exports, API response dumps, and local caches of time-entry data MUST
remain gitignored or untracked. Commits MUST follow `AGENTS.md`: Conventional Commits and no PII,
credentials, or identifiers that do not belong in history.

**Rationale:** Timing and billing data are sensitive; API and LLM integrations multiply leak
vectors.

### V. Pragmatic quality (personal, single-operator)

The primary user is the maintainer. Code MUST stay readable and dependency changes justified
(`pyproject.toml` / `uv.lock`). Formal automated test suites, coverage gates, and multi-party code
review are OPTIONAL unless a feature specification explicitly requires them. Routine changes SHOULD
be validated with `--dry-run`, credential checks, and spot-checks in Timing or the sheet as
appropriate.

**Rationale:** Keeps delivery friction low while allowing stricter quality when a feature demands
it.

### VI. Timing Web API compliance

Client code MUST send `Authorization: Bearer <token>` per Timing’s documentation. Implementations
MUST honor **documented rate and usage limits** (e.g. hourly quotas and burst behavior described in
[`llms.txt`](https://web.timingapp.com/llms.txt) and related API docs) and SHOULD surface remaining
quota or backoff when practical. API usage SHOULD prefer read-only exploration unless a spec clearly
justifies write behavior with Principle III safety controls.

**Rationale:** Respects vendor constraints while keeping API usage aligned with billing-import needs.

## Technology & repository layout

- **Language:** Python `>=3.9`, package **`filoz-time-tracking-utils`**, installed and run with
  **[uv](https://docs.astral.sh/uv/)** (`uv sync`, `uv run`).
- **Layout:** Python package under `filoz_time_tracking/` — today: `config.py`, `timing_format.py`,
  `sheet_format.py`, `google_sheet.py`, `import_timing_export.py` (CLI). New modules for **Timing
  API clients** or import support SHOULD live under the same package (or subpackages) with clear
  names.
- **Dependencies:** Today: `openpyxl`, `gspread`, `google-auth`, `python-dotenv`. Additional
  libraries for HTTP or parsing **MUST** be recorded in `pyproject.toml` when introduced.
- **Operator docs:** `README.md` is the source for setup, env vars, CLI flags, column mapping, and
  high-level scope (import, API, categorization).

## Workflow & operator ergonomics

- **Billing flow (existing):** Export month from Timing as XLSX → dry-run → append to Tracking →
  sheet pivots/invoicing.
- **API support flow (optional):** Document commands, env vars, and safety flags in `README.md` as
  features land; prefer read-only exploration before write paths.
- **SpecKit:** Feature specs and plans under `/specs/` per templates MUST not contradict principles
  I–VI without a constitution amendment.

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
  template placeholders), **2025-03-23**.

**Version**: 3.0.0 | **Ratified**: 2025-03-23 | **Last Amended**: 2026-04-10
