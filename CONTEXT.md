# FilOz Time Tracking

Turning a day of auto-tracked computer activity into honest time entries, and turning FilOz time entries into a monthly invoice.

## Language

### Time data

**Activity**:
A record Timing captures automatically: which app, window title, URL, or file was in front, and for how long.
_Avoid_: screen time entry, tracked entry

**Time entry**:
A deliberately authored block of time with a project, a title, and a billing status. Time entries, not activities, are what get invoiced.
_Avoid_: activity, timer, log

**Billable work**:
Time actually spent working for FilOz. Only time entries under the FilOz project tree are billable; everything else is not.
_Avoid_: work (unqualified), paid time

### Drafting

**Day proposal**:
A reviewable document of the time entries drafted for one day, each with its evidence and confidence, plus the stretches left uncovered.
_Avoid_: plan, draft, suggestion list

**Apply**:
Writing an approved day proposal into Timing as time entries.
_Avoid_: sync, import, push

**Reconciliation**:
Comparing the time entries in Timing, after the user has reviewed and edited them, against the day proposal that was applied, to find mistakes and lessons.
_Avoid_: audit, diff

**Signal**:
A piece of activity evidence that points to a project, such as a browser profile, an editor workspace, an app, or a Slack channel.
_Avoid_: hint, heuristic

**Detour**:
A stretch of non-FilOz activity inside an otherwise FilOz stretch of work.
_Avoid_: interruption, distraction

**Bridge**:
A short gap in activity that is absorbed into the surrounding time entry instead of ending it.
_Avoid_: idle time, pause

**Confidence**:
How sure the drafter is that a proposed time entry's range and project are right: High, Med, or Low. Med and Low always carry the reasoning behind them.
_Avoid_: certainty, score

**Playbook**:
The private, accumulated record of the user's conventions and signals, learned from calibration and reconciliation, that the drafter consults when proposing time entries.
_Avoid_: rules (those are Timing's auto-categorization rules), memory, model

**Precedent**:
A past time entry, with the activity under it, that shows how the user handled a similar situation before.
_Avoid_: example, history

**Uncovered stretch**:
Tracked activity deliberately left without a time entry, either because it is personal or because its project could not be settled with confidence.
_Avoid_: gap, unassigned time
