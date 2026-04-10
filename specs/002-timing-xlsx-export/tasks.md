# Tasks: Timing FilOz XLSX export automation

**Input**: Design documents from `/specs/002-timing-xlsx-export/`
**Prerequisites**: `plan.md` (required), `spec.md` (required), `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: No test tasks were generated because the feature spec does not explicitly request TDD or automated test coverage for this feature.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story label (`[US1]`, `[US2]`, `[US3]`) for story-phase tasks only
- Every task includes an exact file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add CLI entrypoint scaffolding and operator documentation anchors.

- [X] T001 Create new CLI module scaffold in `filoz_time_tracking/export_timing_report.py`
- [X] T002 [P] Add module-level usage section for export command in `README.md`
- [X] T003 [P] Add optional script entry for export command in `pyproject.toml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build shared range parsing, invoice resolution, and TimingHelper bridge used by all stories.

**⚠️ CRITICAL**: No user story work should start until this phase is complete.

- [X] T004 Implement date parsing and validation helpers in `filoz_time_tracking/export_timing_report.py`
- [X] T005 Implement invoice shorthand resolver (`YYYY-M` / `YYYY-MM` -> prior-month-10 to month-9) in `filoz_time_tracking/export_timing_report.py`
- [X] T006 Implement argument conflict rules (`--invoice` vs `--start/--end`) in `filoz_time_tracking/export_timing_report.py`
- [X] T007 Implement `osascript` JXA bridge for TimingHelper report export in `filoz_time_tracking/export_timing_report.py`
- [X] T008 Implement common error mapping and exit codes (0/1/2) in `filoz_time_tracking/export_timing_report.py`

**Checkpoint**: Foundation ready for independent user story implementation.

---

## Phase 3: User Story 1 - Export FilOz entries for a chosen date range (Priority: P1) 🎯 MVP

**Goal**: Export FilOz subtree entries to XLSX for explicit inclusive start/end dates.

**Independent Test**: Run CLI with `--start` and `--end`; confirm XLSX opens and includes only FilOz subtree entries in range.

- [X] T009 [US1] Implement explicit `--start` / `--end` CLI flow and required argument checks in `filoz_time_tracking/export_timing_report.py`
- [X] T010 [US1] Implement project-root filtering argument (`--project`, default `FilOz`) in `filoz_time_tracking/export_timing_report.py`
- [X] T011 [US1] Implement report/export settings parity for Raw Data + Time Entries + Excel in JXA payload in `filoz_time_tracking/export_timing_report.py`
- [X] T012 [US1] Add success output summary (effective range, project, output path) in `filoz_time_tracking/export_timing_report.py`
- [X] T013 [US1] Document explicit date-range usage and expected output in `README.md`

**Checkpoint**: User Story 1 is independently functional and demoable (MVP).

---

## Phase 4: User Story 2 - Invoice-period shorthand for billing windows (Priority: P2)

**Goal**: Accept invoice shorthand and resolve deterministic billing window dates.

**Independent Test**: Run CLI with `--invoice 2026-3`; verify effective range resolves to `2026-02-10` through `2026-03-09`.

- [X] T014 [US2] Implement `--invoice` CLI argument and normalization in `filoz_time_tracking/export_timing_report.py`
- [X] T015 [US2] Wire invoice-resolved dates into export execution path in `filoz_time_tracking/export_timing_report.py`
- [X] T016 [US2] Add January rollover and leap-year handling messages/examples in `README.md`

**Checkpoint**: User Story 2 is independently functional and testable.

---

## Phase 5: User Story 3 - Clear handling of conflicts and empty results (Priority: P3)

**Goal**: Provide safe, deterministic behavior for conflicting inputs and no-data results.

**Independent Test**: Run conflicting flag combinations and empty-result ranges; verify clear error/no-data behavior.

- [X] T017 [US3] Enforce hard-fail behavior for conflicting input combinations with actionable stderr in `filoz_time_tracking/export_timing_report.py`
- [X] T018 [US3] Implement no-matching-entries handling and user-facing outcome text in `filoz_time_tracking/export_timing_report.py`
- [X] T019 [US3] Document conflict and empty-result behavior in `README.md`

**Checkpoint**: User Story 3 is independently functional and testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final quality and operator-readiness checks across all stories.

- [X] T020 [P] Run end-to-end quickstart validation steps and align any command/output wording in `specs/002-timing-xlsx-export/quickstart.md`
- [X] T021 [P] Update implementation notes and troubleshooting guidance in `README.md`
- [X] T022 Verify export compatibility with importer expectations and adjust docs if needed in `filoz_time_tracking/timing_format.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies; can start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1; blocks all user story phases.
- **Phase 3 (US1)**: Depends on Phase 2; recommended MVP delivery point.
- **Phase 4 (US2)**: Depends on Phase 2; can run after US1 or in parallel once foundation is done.
- **Phase 5 (US3)**: Depends on Phase 2; can run after US1 or in parallel once foundation is done.
- **Phase 6 (Polish)**: Depends on completion of all desired user stories.

### User Story Dependencies

- **US1 (P1)**: No dependency on other stories after foundational phase.
- **US2 (P2)**: Uses shared range logic from foundational phase; functionally independent from US1.
- **US3 (P3)**: Uses shared CLI/error scaffolding from foundational phase; functionally independent from US1/US2.

### Parallel Opportunities

- Setup tasks `T002` and `T003` can run in parallel.
- After `T004`-`T008`, US2 (`T014`-`T016`) and US3 (`T017`-`T019`) can proceed in parallel.
- Polish tasks `T020` and `T021` can run in parallel.

---

## Parallel Example: User Story 1

```bash
Task: "Implement project-root filtering argument (--project, default FilOz) in filoz_time_tracking/export_timing_report.py"
Task: "Add success output summary (effective range, project, output path) in filoz_time_tracking/export_timing_report.py"
Task: "Document explicit date-range usage and expected output in README.md"
```

## Parallel Example: User Story 2

```bash
Task: "Implement --invoice CLI argument and normalization in filoz_time_tracking/export_timing_report.py"
Task: "Add January rollover and leap-year handling messages/examples in README.md"
```

## Parallel Example: User Story 3

```bash
Task: "Implement no-matching-entries handling and user-facing outcome text in filoz_time_tracking/export_timing_report.py"
Task: "Document conflict and empty-result behavior in README.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Validate independently with explicit date-range exports.
4. Demo or use for real monthly export.

### Incremental Delivery

1. Deliver US1 (explicit ranges).
2. Add US2 (invoice shorthand).
3. Add US3 (conflict/no-data safety).
4. Run polish tasks for operator readiness.
