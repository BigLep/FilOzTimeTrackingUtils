# Feature Specification: Timing FilOz time export to Excel

**Feature Branch**: `002-timing-xlsx-export`  
**Created**: 2026-04-10  
**Status**: Draft  
**Input**: User description: "Automate the step of exporting Timing App monthly time entries as Excel (XLSX) for the FilOz project tree. Specify a date range to include all entries in that range. Support invoice shorthand (e.g. `2026-3` → 2026-02-10 through 2026-03-09, billing from the 10th of the previous calendar month through the 9th of the invoice month)."

<!--
  Project context: Time entry data may be sensitive. Exported outputs MUST remain under the operator’s control; scope stays read-only relative to Timing source data unless otherwise specified.
-->

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Export FilOz entries for a chosen date range (Priority: P1)

An operator needs the same outcome as manually exporting from Timing App to Excel for a month or arbitrary period: a spreadsheet of time entries limited to the FilOz project and all of its subprojects, without selecting rows by hand.

**Why this priority**: This replaces the core manual step and delivers immediate value on first use.

**Independent Test**: Run an export for a known date range where Timing already shows counted time under FilOz; confirm the output contains those entries (and only FilOz-tree entries) for that range.

**Acceptance Scenarios**:

1. **Given** a defined start date and end date inclusive, **When** the operator requests an export, **Then** they receive an Excel workbook that lists every time entry that falls in that range and belongs to the FilOz project or any of its subprojects.
2. **Given** entries exist outside FilOz or outside the requested range, **When** the operator opens the export, **Then** those entries are not present in the file.

---

### User Story 2 - Invoice-period shorthand for billing windows (Priority: P2)

An operator invoices using periods that run from the 10th of one calendar month through the 9th of the next. They want to type an invoice identifier (for example `2026-3` meaning “March cycle”) and have the export use the correct date span automatically.

**Why this priority**: Reduces date math errors and matches an established billing convention.

**Independent Test**: Request an export using only the invoice shorthand `2026-3` and verify the effective range is 2026-02-10 through 2026-03-09 inclusive (including leap-year February when applicable).

**Acceptance Scenarios**:

1. **Given** invoice shorthand in the form year-month (for example `2026-3` or `2026-03`), **When** the operator runs an export with that shorthand and no conflicting manual dates, **Then** the export uses the start date on the 10th of the prior calendar month and the end date on the 9th of the month named in the shorthand, both inclusive.
2. **Given** invoice shorthand for January (for example `2027-1`), **When** the operator runs the export, **Then** the range spans the 10th of the previous December through the 9th of January, inclusive.

---

### User Story 3 - Clear handling of conflicts and empty results (Priority: P3)

When inputs are ambiguous or nothing matches, the operator gets a clear result instead of a silent wrong file.

**Why this priority**: Prevents incorrect invoicing and lost trust in the automation.

**Independent Test**: Run exports with overlapping or contradictory inputs and with a range that has no FilOz entries; observe explicit outcomes (resolution rules or messages), not a misleading workbook.

**Acceptance Scenarios**:

1. **Given** the operator supplies both an invoice shorthand and an explicit date range, **When** they request an export, **Then** the behavior is defined (either one source wins with explicit documentation, or the run fails with an explanation).
2. **Given** no time entries match FilOz in the resolved range, **When** the export completes, **Then** the operator receives an empty result or an explicit “no entries” outcome rather than unrelated data.

---

### Edge Cases

- **Invoice month January**: Previous-month start must use the prior calendar year (for example `2027-1` → 2026-12-10 through 2027-01-09).
- **Leap day**: February in a leap year must not shift the 9th/10th boundaries incorrectly.
- **Day-boundary interpretation**: Entries logged very close to midnight are included or excluded consistently with how dates are chosen for the range (see Assumptions).
- **Sensitive data**: The export may contain client or task details; the operator is responsible for storing and sharing the file appropriately (same as a manual Timing export).
- **No duplicate or partial projects**: If FilOz naming in Timing changes or duplicates exist, inclusion rules MUST still match the intended project tree (see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST produce an Excel (`.xlsx`) workbook suitable for opening in common spreadsheet software, containing tabular time-entry data equivalent in intent to Timing’s manual “export time entries” output for the same scope.
- **FR-002**: The operator MUST be able to specify an inclusive start date and inclusive end date for the export; all included entries MUST have recorded time overlapping or falling within that span per the rules in Assumptions.
- **FR-003**: The system MUST include every time entry that belongs to the FilOz **project and all nested subprojects** (entire subtree), and MUST exclude entries that are only under unrelated projects.
- **FR-004**: The operator MUST be able to provide invoice shorthand: `YYYY-M` or `YYYY-MM` (year and month, month being the invoice “end” month), resolving to the inclusive date range from the **10th of the previous calendar month** through the **9th of that invoice month**.
- **FR-005**: When invoice shorthand is used alone, it MUST fully determine the export date range; when both shorthand and explicit dates are provided, behavior MUST be deterministic and documented (single precedence rule or rejection with a clear reason).
- **FR-006**: For a non-empty set of matching entries, the export MUST contain enough fields to support invoicing workflows (at minimum: identifiable date (or start/end), duration or hours, project or task path, and free-text notes or titles as available from the source data).
- **FR-007**: When no entries match, the system MUST not fabricate rows; it MUST yield an empty table, an empty workbook, or an explicit no-data indication consistent with the product’s UX conventions.
- **FR-008**: The automation MUST be read-only with respect to Timing’s stored time data: it MUST NOT create, edit, or delete time entries as part of generating an export.

### Key Entities *(include if feature involves data)*

- **Time entry**: A single logged block of work (start/end or duration), date of occurrence, associated title or notes, and linkage to a project node in a hierarchy.
- **Project node / subproject**: A node in Timing’s project tree; FilOz is the root of the subtree whose entries MUST be exported.
- **Export range**: A pair of calendar bounds (inclusive) either set explicitly or derived from invoice shorthand.
- **Invoice period label**: A shorthand encoding the billing month whose window ends on the 9th and begins on the 10th of the prior month.

### Assumptions

- **Source availability**: The operator can access the same Timing App data they would use for a manual export (account, device, or sync state unchanged).
- **FilOz identification**: The FilOz root in Timing is unambiguous for this operator (fixed name or configuration); nested items are determined by Timing’s hierarchy under that root.
- **Calendar boundaries**: Inclusive dates use the operator’s normal calendar interpretation consistent with how they would pick the same range in Timing manually; entries are attributed to days/time zones in the same way Timing displays them for export purposes.
- **Equivalence**: “Automate the manual Excel export” means parity of *included* entries and essential columns for invoicing, not necessarily byte-identical files or identical column order versus Timing’s UI.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a known two-week or one-month window, an operator completes an export (from launch to saved file) in under **3 minutes** excluding first-time setup.
- **SC-002**: For sample data checked against Timing’s own view of FilOz for the same range, **100%** of FilOz-subtree entries in that range appear in the export, and **0** entries from outside that subtree appear.
- **SC-003**: For invoice shorthand `2026-3`, **100%** of trial runs resolve to the inclusive range **2026-02-10** through **2026-03-09** without operator date entry.
- **SC-004**: At least **90%** of intended monthly invoicing runs succeed on first attempt without manual spreadsheet cleanup beyond what the operator already accepted for manual Timing exports (column trim, formatting), measured over the first **10** billing cycles of use.
