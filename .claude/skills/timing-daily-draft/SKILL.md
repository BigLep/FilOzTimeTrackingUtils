---
name: timing-daily-draft
description: >
  Draft a day's Timing time entries from auto-tracked activity, as a day proposal the user reviews before anything is
  written. Use whenever the user says "draft yesterday", "do my timing entries", "time entries for <date>", "apply the
  proposal", "reconcile", or asks to backfill time entries for a range of days. Also covers applying an approved day
  proposal to Timing and reconciling what the user changed afterward.
---

# Timing daily draft

Turn one day of auto-tracked activity into a **day proposal**, get it reviewed, **apply** it to Timing, and learn from **reconciliation**. Vocabulary is defined in [CONTEXT.md](../../../CONTEXT.md); use those terms. Decisions and their reasons are in [docs/adr/](../../../docs/adr/), especially ADR 0001 (billing integrity), ADR 0002 (private playbook), ADR 0003 (human-reviewed proposals), and ADR 0004 (mechanical segmentation and the accuracy gates below).

## Before anything

1. Call `mcp__timing-local__start_here`. Timing's `AGENTS.md` points at the playbook.
2. Read `local/playbook.md` in full. It holds the settled conventions, learned signals, title vocabulary, and the lessons log. It is private (gitignored) and may contain names; never copy its contents into committed files.
3. `local/` holds everything private: `playbook.md` and `proposals/YYYY-MM-DD.md`. Create the folder if missing.

## The daily loop

One day at a time. Never write to Timing without an explicit "apply" from the user for that day.

Keep the user informed: before each step below, print a one-line progress note (for example "Gathering Sep 14: 3 calendar events, running the segmenter" or "Content-checking 7 FilOz candidates"). A long silent stretch of thinking looks like a hang.

### 1. Reconcile the last applied day (if any)

Find the most recent proposal marked `Status: applied` in `local/proposals/`. Compare it with `time_entries_list` for that day, and only look at entries with `via=mac-mcp` or notes containing `[claude-draft]`, plus any entries the user added in the gaps. For every difference (deleted, moved, retitled, re-projected, added), show it to the user and ask: mistake, or lesson? Write each lesson into the playbook, both as a convention or signal update and as a row in the lessons log. Mark the proposal `Status: reconciled`.

### 2. Gather the day

- `time_entries_list` for the day: existing entries are fixed. Only fill around them.
- Google Calendar `list_events` on the FilOz work calendar for the day (its calendar ID is in the playbook): meetings, with who declined what.
- Get the day's boundaries mechanically: call `activity_slice` for the whole day (`includePaths: false`, a high `limit`). The result is too large to show inline, so Claude Code saves it to a file and reports the path. Run `uv run python -m filoz_time_tracking.segment_activity --detail --min-span 5 <saved files...>` on it. The output lists candidate entries per class (F FilOz, M Madison, P personal) with the ADR 0001 detour and gap rules applied, absorbed glance totals, and `FLAG>10%` where absorbed time is over 10% of a FilOz entry. With `--detail`, each candidate lists its top app / context / Timing-project lines by time. That is the main input for the content check; do not write ad-hoc scripts or `awk` passes over the raw rows to get the same thing. It classifies mostly by app (Brave `localhost` rows Timing filed under Madison count as Madison, and WhatsApp counts as Madison), so Messages contacts, Orca, and other Brave pages still need checking against the playbook; treat its output as a starting point. The Timing-project column is only a hint: it reflects Timing's auto-categorization rules, which can be wrong (for example, `github.com` routes Solstice issues to FOC).
- Page titles are not in the raw activity (only domains). When a candidate's `--detail` is not enough to pick the subproject or title (typically `github.com`, `docs.google.com`, `localhost`, or Slack with no title), call `activity_hierarchy` scoped to that candidate's own time range (`dateRange: "YYYY-MM-DDTHH:MM – YYYY-MM-DDTHH:MM"`, `groupByProject: false`, `includeTimeEntries: false`, `maxDepth: 4`). Do not pull a full-day 15-minute breakdown; it is large and repeats what the segmenter already gives. WhatsApp defaults to Madison; add `--whatsapp-personal` only when the user says a day's WhatsApp was not Madison.
- For Med or Low confidence calls, look up precedents, keeping the result small: `time_entry_stats_total_time` with a `searchQuery` on the title (it returns one figure, answering "has this title been used, and how much"), `time_entries_list` narrowed to a short date range or one project and a low `limit` (entry notes often carry long meeting boilerplate, so a whole-project listing can be tens of kilobytes), or `activity_hierarchy` over a past range with a `regexFilter` on the signal, `includeTimeEntries: true`, and a low `limit`, which shows which of the user's entries covered similar activity.

### 3. Draft the entries

Apply the playbook's settled conventions first, then its learned signals. The non-negotiables from ADR 0001:

- Only FilOz work is billable (`billable`); everything else gets `not_billable`. Personal time gets no entry at all.
- A detour longer than 2 minutes ends a FilOz entry. Detours of 2 minutes or less are absorbed, but their total goes in the entry's notes; flag the entry if absorbed time is over 10% of it.
- Gaps of 5 minutes or less are bridged; longer gaps end the entry. Off-computer time is never billed.
- Meetings: calendar title, real attended span from Zoom/Meet activity, notes with the agenda or doc link and no join boilerplate. Declined events or events with no activity are listed, not entered.

Every entry gets a Confidence. Med and Low entries carry the reasoning, the precedent or signal relied on, and what would change the call. Ambiguous stretches stay uncovered and are listed with a best guess.

### 4. Write the day proposal

Write `local/proposals/YYYY-MM-DD.md` using the template below, then tell the user it is ready to annotate (they use Plannotator). Revise until they say to apply.

### 5. Apply

Only after the user says to apply that day's proposal: `time_entry_create` one entry at a time with the proposal's exact start, end, project, title, billing status, and notes. Every entry's notes end with `[claude-draft]`. Never pass `overwriteOverlapping`. Record each created entry's ID on its entry's header line in the proposal, set `Status: applied`, and report any failures.

## Accuracy gates

Entries drive a real invoice. ADR 0004 explains why each gate exists. Do not present a proposal until the pre-proposal gates pass, and do not apply until the pre-apply gates pass. If a gate cannot be satisfied, say which one in the proposal instead of skipping it.

**Before presenting a proposal:**

- [ ] **Boundaries from the segmenter.** Every entry's start and end come from `segment_activity` output (or `activity_slice` for a mid-row edge), never from eyeballing 15-minute blocks.
- [ ] **Content check on every FilOz candidate.** Check the titles and domains under each F stretch. Confirm Brave Plannotator and localhost pages, Cursor/Orca/terminal repos (by where they live on disk), WhatsApp chats, and Messages contacts against the playbook. Relabel anything the app-only classifier got wrong, and note it.
- [ ] **Absorbed time totalled and flagged.** Each FilOz entry's notes carry its absorbed glance total; anything with `FLAG>10%` is flagged with a proposed handling.
- [ ] **Meetings reconciled with activity.** Every calendar event is either entered with its real attended span or listed under "Calendar events not entered" with the reason.
- [ ] **Confidence on every entry.** Med and Low entries show a precedent lookup or the signal relied on, and what would change the call.
- [ ] **Existing entries untouched.** Nothing proposed overlaps an existing entry.
- [ ] **FilOz total stated** at the top, so the billed impact of the day is visible at a glance.

**Before applying:**

- [ ] **Explicit go-ahead** from the user for that specific day.
- [ ] **Exact values.** Create entries with the proposal's start, end, project, title, billing status, and notes; notes end with `[claude-draft]`; never `overwriteOverlapping`.
- [ ] **Record and verify.** Write each created ID into the proposal, then `time_entries_list` the day and confirm the FilOz total matches the proposal.

**After:** reconciliation at the start of the next run (step 1) is the last gate. A mislabel that repeats is fixed at its source: the segmenter's app lists or the playbook.

## Day proposal template

Write the day as ONE chronological timeline, with evidence, flags, and questions inline under each entry. Do not split entries and their reasoning into separate sections: the reviewer wants to read each entry with its evidence in one place. Label entries E1, E2, ... (never `#1`, which markdown renderers auto-link to GitHub issues). Uncovered stretches sit in time order between entries as italic one-liners.

```markdown
# Day proposal: YYYY-MM-DD (Weekday)

Status: draft | applied | reconciled

**FilOz billable: Xh Ym across N entries.** Other (not billable): ... Existing entries: ...

## Morning

### E1 · 08:05–08:39 · Morning comms
**FilOz ▸ Communication** · billable · 34m · Confidence: High · Entry ID: (filled on apply)

One or two lines of evidence. Absorbed glances total.

> ⚠️ **Flag:** anything over a threshold, with the proposed handling.
> ❓ **Question:** a decision for the reviewer, with the default being proposed.

*Uncovered 08:39–08:43: what was there, best guess, why not entered.*

## Midday / Afternoon / Evening
...

## Calendar events not entered
```

## After a batch of days

When a backfill finishes, or every few days in the daily cadence, re-read the lessons log and fold repeated lessons into the playbook's conventions so the next proposals start smarter.
