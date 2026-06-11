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
- Search Gmail for Anthropic receipts and create forwarding drafts
- Navigate to billing pages and identify the correct invoices
- Verify expenses landed in Expensify via the read-only MCP

The user must:
- Download invoice PDFs from Stripe (blocked by Chrome extension)
- Send Gmail drafts and attach PDFs to emails
- Set category and tag on expenses in Expensify
- Create the expense report and submit it

## Execution context

- **Subscriptions**: Anthropic (Claude), OpenAI (ChatGPT), Cursor
- **Destination**: Expensify via `receipts@expensify.com` (SmartScan)
- **Expensify workspace**: FilOz (policyID: `9950EB8E3A5E16C2`) — NOT PLGO (legacy)
- **Expensify user**: biglep@filoz.org
- **Expense category**: `General Allowance: Software Subscription/Licenses`
- **Expense tag**: `AI Credit Allowance`
- **Chrome profile**: Any profile logged into claude.ai, chatgpt.com, cursor.com, and expensify.com with Claude-in-Chrome extension enabled

## Known limitations

- **Chrome extension blocks `invoice.stripe.com`** — User must manually download PDFs from Stripe invoice pages.
- **Gmail MCP cannot send** — Can only create drafts. User must hit send.
- **Gmail MCP attachment size** — Cannot programmatically attach invoice PDFs (~400KB base64 each). Create the draft body, user attaches files.
- **Expensify MCP is read-only** — Cannot set category, tag, create reports, or submit. User does these in the Expensify UI.
- **Cursor billing page** — Must be the active/focused tab to load.

---

## Workflow

Ask the user for the expense month (e.g. "June 2026") if not provided.

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
2. Use the month dropdown in the Invoices section to select the target month
3. Point user to the "View" link

**Note:** Cursor does not send email receipts ([feature request](https://forum.cursor.com/t/ability-to-get-invoice-via-additional-email-address-es/112720)). Cursor bills on the 16th of each month. Invoice #0001 is a $0.00 setup invoice — skip it.

**User action:** Click "View", download the PDF from the Stripe page.

### 4. Get PDFs to Expensify (user emails)

Create a Gmail draft to `receipts@expensify.com` with a subject describing the invoices. The user attaches the downloaded OpenAI and Cursor PDFs and sends.

**User action:** Attach PDFs to draft, send.

### 5. Verify receipts landed (Claude checks)

Use the Expensify MCP to search for recent unreported expenses. Confirm all expected receipts arrived with correct amounts and merchants. Flag any missing or duplicate entries.

### 6. Categorize and submit (user does in Expensify)

Tell the user to:
1. Select all the AI subscription expenses
2. Set **Category** to `General Allowance: Software Subscription/Licenses`
3. Set **Tag** to `AI Credit Allowance`
4. Create a report (e.g. "June 2026 AI Subscriptions") and add the expenses
5. Submit

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
