---
name: ai-expense-report
description: >
  Guide the user through monthly AI subscription expense reporting (Anthropic,
  OpenAI, Cursor) to Expensify. This is a human-in-the-loop process — Claude
  navigates billing pages, finds receipts, creates drafts, and verifies results,
  but the user must download PDFs, send emails, categorize, and submit.
---

# AI Subscription Expense Report

## Role of this skill

This is a **guided, human-in-the-loop workflow**. Claude can:
- Check Expensify for which months are actually outstanding (step 0 — always do this first)
- Search Gmail for Anthropic receipts and create forwarding drafts
- Navigate to billing pages and identify the correct invoices
- Verify expenses landed in Expensify via the read-only MCP
- **Categorize, tag, and build the draft report in the Expensify UI via claude-in-chrome** (the read-only MCP can't, but the browser can)

The user must:
- Download invoice PDFs (Cursor: one zip via "Download all"; OpenAI: from Stripe)
- Send Gmail drafts and attach PDFs to emails
- Review and hit **Submit** on the finished report

## Execution context

- **Subscriptions**: Anthropic (Claude), OpenAI (ChatGPT), Cursor
- **Destination**: Expensify via `receipts@expensify.com` (SmartScan)
- **Expensify workspace**: FilOz (policyID: `9950EB8E3A5E16C2`) — NOT PLGO (legacy)
- **Expensify user**: biglep@filoz.org
- **Expense category**: `General Allowance: Software Subscription/Licenses`
- **Expense tag**: `AI Credit Allowance`
- **Chrome profile**: Any profile logged into claude.ai, chatgpt.com, cursor.com, and expensify.com with Claude-in-Chrome extension enabled

## Known limitations

- **Chrome extension blocks Stripe invoice pages** — Confirmed still true as of Aug 2026: clicking an OpenAI invoice row silently fails to open a tab. User must download from Stripe manually. **Cursor now has a way around this — see step 3.**
- **Gmail MCP cannot send** — Can only create drafts. User must hit send.
- **Gmail MCP attachments** — The API *does* accept attachments (base64, 25MB combined), so this is not a hard limit. It is impractical anyway: a ~400KB PDF is six figures of tokens to pass through context. Create the draft body, user attaches files.
- **Expensify MCP is read-only** — Cannot set category, tag, create reports, or submit. **Use claude-in-chrome to drive the Expensify web UI instead** (see step 6); only the final Submit is left to the user. Use the MCP for verification, the browser for changes.
- **Expensify search via MCP can blow the token limit** — An unfiltered `Search` returns ~100k characters and gets spilled to a file. Filter narrowly (`status:["unreported","drafts"]`) or post-process the spill file with jq.
- **Cursor billing page** — Must be the active/focused tab to load.
- **SmartScan auto-categorizes** — It sets Category to `Software subscription/Licenses`, which is *not* the required `General Allowance: Software Subscription/Licenses`, and leaves Tag empty. Always tell the user to set both explicitly; do not assume the auto-value is correct.

---

## Workflow

### 0. Determine which months are actually outstanding (do this FIRST)

**Never assume the user only needs the current month.** They miss months, and the ask ("expense my AI subscriptions") usually won't mention it. Before touching any vendor, find the last AI subscription expense already in Expensify:

```json
{"type":"expense","status":"all","sortBy":"date","sortOrder":"desc","shouldCalculateTotals":true,"filters":null}
```

An unfiltered search can exceed the token limit and get written to a file — extract just what you need with jq rather than reading it whole:

```
jq -r '[.data | to_entries[] | select(.key|startswith("transactions_")) | .value
        | {date:(.modifiedCreated // .created), merchant:(.modifiedMerchant // .merchant), amount:(.modifiedAmount // .amount)}]
       | sort_by(.date) | reverse | .[:25][] | "\(.date)  \(.amount)  \(.merchant)"' <file>
```

Amounts are in cents and negative. Everything after the newest Anthropic/OpenAI/Cursor row is outstanding.

Then work out which invoices should exist in that span from the billing cycles (Cursor 16th, Anthropic ~27th, OpenAI ~29th) and confirm each against the vendor. If more than one month is outstanding, tell the user and ask whether they want one combined report or one per month before creating any drafts.

Ask the user for the expense month only if step 0 is ambiguous.

### 1. Anthropic receipts (Claude assists, user sends)

**Alternative source:** Invoices also at `https://claude.ai/new#settings/billing` (Stripe links).

Search Gmail for receipts:
```
from:invoice+statements@mail.anthropic.com subject:receipt newer_than:45d
```

Show the user each receipt number, amount, and date. If they confirm, create a forwarding draft to `receipts@expensify.com` using `replyToMessageId` to include the original receipt content.

If there are multiple receipts in the period (e.g. mid-cycle plan change), flag all of them.

**User action:** Send the draft(s).

### 2. OpenAI invoice (Claude navigates, user downloads)

1. Navigate to `https://chatgpt.com/codex/cloud#settings/Billing`
2. Locate the invoice for the target month (click "View all" if needed)
3. Point user to the correct invoice link

**Note:** OpenAI does not send email receipts ([known gap](https://community.openai.com/t/email-receipts-to-billing-email-address/731689/67)). The user may not have been subscribed continuously — check billing history rather than assuming monthly invoices exist.

**User action:** Click the invoice link, download the PDF from the Stripe page.

### 3. Cursor invoice (Claude navigates, user downloads)

1. Navigate to `https://cursor.com/dashboard/billing` — **must be the active tab to load**
2. Scroll to the **Invoices** section at the bottom. It has three controls: a `UTC` badge, a **month dropdown**, and a **Download** dropdown.
3. **Preferred path — "Download all".** Open the **Download** dropdown and point the user at **"All invoices"**. This downloads a **zip of every Cursor invoice PDF**, straight from cursor.com, bypassing the blocked Stripe page entirely. One click covers any number of months, so it is strictly better than the per-month path when more than one month is outstanding.
   - The user extracts the zip and picks out the invoices for the target month(s). Give them the **exact dates and amounts to look for** (from the month dropdown, see below) so they know which files to pull.
   - The Download dropdown also offers a single-month option (e.g. "June 2026") if only one month is needed.
4. **Confirm the expected invoices first.** Use the month dropdown to select each target month and read off the invoice row (date, status, amount). Do this *before* telling the user to download, so they can match files to expected values.
5. Fallback: the per-row "View" link goes to Stripe and requires a manual download there.

**Note:** Cursor does not send email receipts ([feature request](https://forum.cursor.com/t/ability-to-get-invoice-via-additional-email-address-es/112720)). Cursor bills on the 16th of each month. Invoice #0001 is a $0.00 setup invoice — skip it.

**User action:** Download the zip via "All invoices", extract, and pull out the invoices for the target month(s).

### 4. Get PDFs to Expensify (user emails)

Create a Gmail draft to `receipts@expensify.com` with a subject describing the invoices, and list every expected invoice (vendor, date, amount) in the body so the user can check the attachments against it. The user attaches the downloaded OpenAI and Cursor PDFs and sends.

**Write the subject as literal text — never HTML-escape it.** `create_draft` takes the subject raw, so passing `&amp;` produces a literal "&amp;" in the sent subject line. Use `&` (and `<`, `>`, `"`) directly. Simplest fix: avoid `&` in subjects and write "and".

**User action:** Attach PDFs to draft, send.

### 5. Verify receipts landed (Claude checks)

Use the Expensify MCP to search for recent unreported expenses. Confirm all expected receipts arrived with correct amounts and merchants. Flag any missing or duplicate entries.

### 6. Categorize and build the report (Claude does via claude-in-chrome; user submits)

The Expensify MCP is read-only, but **the Chrome extension can drive the Expensify web UI** — Claude does everything up to Submit. Navigate to the unreported/drafts search:

`https://new.expensify.com/search?q=type%3Aexpense+status%3Aunreported%2Cdrafts+sortBy%3Adate+sortOrder%3Adesc`

1. Dismiss any promo modal (a "Concierge AI" popup appears over the list).
2. Tick the checkbox on **only** the AI subscription rows. Old unrelated unreported expenses live here too (stale Lyft/Uber/Alaska rows) — never use the select-all header checkbox. Confirm the footer reads the expected count and total before continuing.
3. **"N selected" dropdown → "Edit multiple"** → set both fields at once:
   - **Category**: the list is hierarchical. Pick `Software Subscription/Licenses` **nested under the `General Allowance` header**, not the top-level `Software subscription/Licenses` (lowercase "s") that SmartScan auto-assigns. The panel then reads `General Allowance: Software Subscription/Lic…` — verify this before saving.
   - **Tag**: `AI Credit Allowance`
   - Click **Save**.
4. Re-select the same rows → **"N selected" → "Move to report" → "Create report"** under the **FilOz** workspace. Check the workspace label; an unrelated draft report may also be listed.
5. Open the new draft (sidebar **Drafts**), click the **pencil** next to the auto-generated title, and rename it (e.g. `June-July 2026 AI Subscriptions`). The default title ends in "(CHOOSE ONE)" and must be replaced.
6. Verify the report: correct count, total, category and tag on every row, workspace = FilOz.

**Expected violation:** expenses older than 30 days show a red "Date older than 30 days" flag and the report header says "Waiting for you to fix the issues". This is normal for any backfill and does not block submission — flag it to the user rather than trying to clear it.

**User action:** Review and hit **Submit**.

**User action:** All of step 6.

### 7. Final verification (Claude checks)

Use the Expensify MCP to confirm the report was submitted with the correct total, expense count, and workspace.

---

## Billing page URLs

| Vendor | URL | Billing cycle |
|--------|-----|---------------|
| Anthropic | `https://claude.ai/new#settings/billing` | ~27th of month (Max plan) |
| OpenAI | `https://chatgpt.com/codex/cloud#settings/Billing` | ~29th of month (Plus plan) |
| Cursor | `https://cursor.com/dashboard/billing` | 16th of month (Pro plan) |

---

## Error handling

| Error | What to do |
|---|---|
| Anthropic receipt not found in Gmail | Check if the billing date has passed. Search with broader date range. Check claude.ai billing page. |
| OpenAI/Cursor billing page changed | Pause and describe the current UI. Update these instructions after resolving. |
| Chrome not logged in | Remind user to log in via the dedicated Chrome profile. |
| Receipt not appearing in Expensify | SmartScan can take a few minutes. Wait and re-check. If still missing after 5 min, try re-sending. |
| Multiple receipts for one vendor | Flag to user — may indicate plan change, prorated charges, or API usage on top of subscription. |
| Duplicate expense | Flag to user to delete in Expensify. Can happen if a receipt was forwarded twice. |

---

## Upstream feature requests to monitor

These vendor feature requests would eliminate the manual PDF download steps if implemented. Check periodically.

| Vendor | Request | URL | Impact if resolved |
|--------|---------|-----|-------------------|
| OpenAI | Email receipts to billing email | https://community.openai.com/t/email-receipts-to-billing-email-address/731689/67 | Switch to Gmail forwarding like Anthropic — no browser needed |
| Cursor | Email invoices to additional address | https://forum.cursor.com/t/ability-to-get-invoice-via-additional-email-address-es/112720 | Switch to Gmail forwarding like Anthropic — no browser needed |

If either vendor starts sending email receipts, update the workflow to use Gmail search + forwarding (same as Anthropic) and remove the browser download steps.

---

## Default posture: always improve

This workflow has significant manual friction. Every run should actively look for ways to reduce it. Don't just execute the steps — question whether each manual step is still necessary.

### After every run

1. **Identify friction** — What took the most user effort? What felt clunky? Call it out explicitly to the user at the end of the session: "Here's what I think we could improve next time..."

2. **Test assumptions** — Re-check each known limitation. Things change:
   - Does the Chrome extension still block `invoice.stripe.com`? Try it.
   - Does the Expensify MCP still lack write access? Check the tool list.
   - Has any vendor started sending email receipts? Search Gmail.
   - Can Gmail MCP send now (not just draft)?
   - Has the attachment size limit changed?

3. **Update this skill** — If anything changed, edit this file directly. Don't suggest changes — make them. If a limitation was resolved, remove it and update the workflow to use the new capability.

4. **Suggest improvements to the user** — Proactively recommend things like:
   - "Should we set up a monthly reminder/schedule so these don't pile up?"
   - "Vendor X now offers email receipts — want me to switch to that?"
   - "I noticed a new AI subscription on your credit card — should we add it?"
   - "The Expensify MCP can do X now — next time I can handle that step."

5. **Watch for new subscriptions** — Check the credit card spreadsheet or Expensify for new AI/software vendors not yet in this workflow.

### Aspirational goal

The ideal end state is: user says "expense my AI tools for June" and Claude handles everything end-to-end with a single confirmation before submit. Each run should move closer to that.
