# Entry boundaries come from a script; project labels are verified by the drafter and the user

Time entry boundaries determine billed minutes, so they are computed mechanically by `filoz_time_tracking/segment_activity.py` from second-level activity, applying the ADR 0001 rules (detours over 2 minutes and silence over 5 minutes end an entry). The alternative, an agent estimating boundaries from 15-minute summaries, produced rounded edges that silently absorbed personal detours, and applies the rules inconsistently from day to day. The script, however, labels activity by app alone and can be wrong about which project a stretch belongs to, so its output is a starting point that passes through the gates below before anything is billed.

## Known accuracy concerns and the gate that catches each

| Concern | Gate |
|---|---|
| Eyeballed boundaries drift and round | The segmenter computes boundaries from second-level activity with fixed rules; results are reproducible by rerunning it. |
| App-only labels are wrong for some activity: Brave Plannotator on a Madison repo, WhatsApp chats, Messages contacts, Orca (no window titles) | Content check: every FilOz candidate is checked against titles, domains, and the repo's location on disk before it enters a proposal. |
| Many sub-2-minute glances add up inside a billed entry | Absorbed time is totalled per entry; over 10% of a FilOz entry is flagged for the user. |
| The calendar says what was scheduled, not what was attended | Meetings use the real Zoom/Meet span; declined or unattended events are listed, not entered. |
| Uncertain project or title | Every entry carries a Confidence; Med or Low requires a precedent lookup and visible reasoning. |
| Any drafting error | The user reviews and annotates the day proposal before apply (ADR 0003). |
| Apply diverges from what was approved | Entries are created with the proposal's exact values, tagged `[claude-draft]`, with their IDs recorded in the proposal; existing entries are never overwritten. |
| Errors that survive review | Reconciliation at the start of the next run compares Timing with the applied proposal; fixes become playbook lessons or segmenter app-list changes. |
| Month-level anomalies | The monthly invoice workflow's anomaly review and audit steps. |

## Consequences

Errors lean toward under-billing by design: off-computer time and FilOz stretches under 5 minutes are not billed unless the user adds them. A recurring mislabel should be fixed at its source (the segmenter's app lists or the playbook), not corrected by hand each day.
