---
name: ai-expense-report
description: >
  Run monthly AI subscription expense reporting (Anthropic, OpenAI, Cursor) to
  Expensify. Claude finds what's outstanding, reads the billing pages, downloads
  and verifies the PDFs, emails everything to Expensify with the gog CLI, and
  builds the report in the Expensify UI. The user downloads the Cursor PDFs,
  gives one confirmation before anything is sent, and hits Submit.
---

# AI Subscription Expense Report

## Role of this skill

The goal is for the user to do as little as possible. Claude does:
- Work out which months are outstanding (step 0, always first)
- Find Anthropic receipts in Gmail and read their amounts
- Read the OpenAI and Cursor billing pages to get the expected invoices
- Find the downloaded PDFs in `~/Downloads` and verify each one (vendor, date, amount)
- Email everything to Expensify with `gog` (forward the Anthropic receipts, send the PDFs as attachments)
- Download the OpenAI receipt PDFs from Stripe (needs the Chrome download setting below)
- Verify the expenses landed, then categorize, tag and build the draft report through claude-in-chrome

The user does only:
- Download the Cursor PDFs (cursor.com "Download"), until Claude has verified it can do this too
- Give **one** confirmation of the invoice list, which authorizes Claude to send those exact emails
- Review and hit **Submit** on the finished report
- Log in to a vendor site if its session has expired (Claude never enters credentials)

## Execution context

- **Subscriptions**: Anthropic (Claude), OpenAI (ChatGPT), Cursor
- **Destination**: Expensify via `receipts@expensify.com` (SmartScan)
- **Expensify workspace**: FilOz (policyID: `9950EB8E3A5E16C2`), NOT PLGO (legacy)
- **Expensify user**: biglep@filoz.org
- **Expense category**: `General Allowance: Software Subscription/Licenses`
- **Expense tag**: `AI Credit Allowance`
- **Gmail**: the `gog` CLI with the account alias `personal` (the personal account that receives vendor receipts). Always pass `-a personal`. If the alias is missing, ask the user for the account and run `gog auth alias set personal <email>`; never write the address into this file.
- **Chrome profile**: Any profile logged into claude.ai, chatgpt.com, cursor.com, and expensify.com with Claude-in-Chrome extension enabled
- **Chrome download setting (REQUIRED)**: Settings → Downloads → **"Ask where to save each file before downloading" must be OFF**, and the download location must be `~/Downloads`. With it on, every download Claude triggers opens a native macOS save dialog that claude-in-chrome cannot see or click, and the download silently never lands (see "Downloads" under Known limitations).

## Tools

| Job | Tool |
|---|---|
| Find outstanding months, verify expenses and report | Expensify MCP `Search` (read-only) |
| Search Gmail, forward receipts, send emails with attachments | `gog -a personal gmail ...` |
| Read an email body (receipt amounts) | Gmail MCP `get_thread` with `PLAIN_TEXT`, or gog |
| Billing pages, Expensify UI edits | claude-in-chrome |
| Verify downloaded PDFs | `Read` on the PDF path |
| Troubleshoot a download that didn't land (look only) | computer use, Google Chrome at read tier |

The Gmail MCP can create drafts but not send, and passing attachments through it costs six figures of tokens per PDF. gog attaches files by path and can send, so prefer gog for anything that writes to Gmail.

## Known limitations

- **Downloads**: Claude can download PDFs itself (verified Sep 2026 on the OpenAI Stripe page) as long as the Chrome download setting above is off. Clicking an OpenAI transaction row opens its Stripe invoice page in the Claude tab group; clicking **Download receipt** there saves `Receipt-<number>.pdf` straight to `~/Downloads`.
  - **After every download click, check `ls -lt ~/Downloads | head` within about 5 seconds.** If no new file appears, don't click again: each extra click queues another save dialog and later produces duplicate `(1)`, `(2)` copies.
  - **Troubleshoot with computer use.** Call `request_access` for Google Chrome (browsers are granted read-only; that is enough) and take a screenshot. A save sheet reading "<host> wants to save" means the setting was turned back on. Claude can't click it (read-only tier, and never work around that with AppleScript or keystrokes). Ask the user to click **Save** and to turn the setting off again.
  - If there's no dialog and no file, ask the user to click the download button themselves and note what happened here.
- **Expensify MCP is read-only**: cannot set category, tag, create reports, or submit. Use claude-in-chrome for changes; only the final Submit is left to the user.
- **Cursor billing page**: must be the active/focused tab to load. The month dropdown does not open when clicked by element ref; click it by screen coordinate from a screenshot.
- **Cursor login redirect**: in Sep 2026 an expired Cursor session redirected to a sign-in page on `accounts.x.ai` ("SpaceXAI Accounts", showing "Log into your Cursor account"). Do not log in; tell the user, suggest they type `cursor.com` themselves, and wait.
- **OpenAI transaction history lags**: on the billing day the plan can already show the next renewal date while the new charge is not yet in the transaction list. Treat an unlisted charge as not billed yet and push it to next month.
- **SmartScan auto-categorizes**: it sets Category to `Software subscription/Licenses`, which is *not* the required `General Allowance: Software Subscription/Licenses`, and leaves Tag empty. Step 6 fixes both; never assume the auto-value is right.
- **Cursor PDFs are invoices, not receipts**: they say "Amount due" rather than "Paid". The billing page shows them as Paid, and approvers have accepted them.

---

## Workflow

### 0. Determine which months are actually outstanding (do this FIRST)

**Never assume the user only needs the current month.** They miss months, and the ask ("expense my AI subscriptions") usually won't mention it. Find the newest AI subscription expense already in Expensify with a narrow keyword search (small enough to read inline):

```json
{"type":"expense","status":"all","sortBy":"date","sortOrder":"desc","shouldCalculateTotals":true,
 "filters":{"operator":"and",
   "left":{"operator":"gte","left":"date","right":"<about 4 months ago, YYYY-MM-DD>"},
   "right":{"operator":"eq","left":"keyword","right":["Anthropic","OpenAI","Cursor","Claude","ChatGPT"]}}}
```

Use `modifiedCreated` / `modifiedMerchant` / `modifiedAmount` (cents, negative). The report names and states tell you what's already submitted or approved. Everything after the newest Anthropic/OpenAI/Cursor row is outstanding, including anything unreported that the user already emailed in.

Work out which invoices should exist from the billing cycles (Cursor 16th, Anthropic ~27th, OpenAI ~29th). If more than one month is outstanding, ask whether they want one combined report or one per month. If an invoice is due today or tomorrow, ask whether to include it if it's already billed or leave it for next month.

### 1. Gather the expected invoices (Claude, no user action)

Do all three before involving the user.

**Anthropic** (email receipts, PDFs attached):
```
gog -a personal gmail search 'from:invoice+statements@mail.anthropic.com subject:receipt after:<YYYY/MM/DD after last expensed>' --plain
```
Read each receipt's amount, date and receipt number from the body. Flag multiple receipts in one period (plan change, proration). Alternative source: `https://claude.ai/new#settings/billing`.

**OpenAI** (no email receipts, [known gap](https://community.openai.com/t/email-receipts-to-billing-email-address/731689/67)):
Navigate to `https://chatgpt.com/codex/cloud#settings/Billing`, wait for "Transaction history" to load, and read the rows (date, status, amount). Click "View all" if needed. The user may not have been subscribed continuously; trust the history, not the calendar.

**Cursor** (no email receipts, [feature request](https://forum.cursor.com/t/ability-to-get-invoice-via-additional-email-address-es/112720)):
Navigate to `https://cursor.com/dashboard/billing` (must be the active tab). In the **Invoices** section, use the month dropdown to read each target month's row (date, status, amount). Invoice #0001 is a $0.00 setup invoice; skip it.

### 2. One confirmation from the user

Present a single table of every expected invoice (vendor, date, amount, source) with the total, and in the same message ask the user to:
1. OpenAI PDFs are Claude's job: click each OpenAI row, then **Download receipt** on the Stripe page it opens (see "Downloads" under Known limitations). Only ask the user if that fails.
2. Download the Cursor PDFs (until Claude has verified it can do this too): **Download** dropdown → a single month (e.g. "August 2026") per month, or **All invoices** for a zip of everything.
3. Confirm the list. Their yes authorizes Claude to send the forwards and the PDF email listed in the table, and nothing else.

The user does not need to give file paths.

### 3. Find and verify the PDFs (Claude)

Look in `~/Downloads` for the newest files:
- OpenAI: `Receipt-*.pdf` (and `Invoice-*.pdf`)
- Cursor: folders `cursor-invoices-personal-<from>-to-<to>/` containing `cursor-invoice-<YYYY-MM-DD>-*.pdf`, or an extracted "All invoices" zip

`Read` each candidate PDF and match it to the table by vendor, date and amount. Use only PDFs that match; if one is missing or doesn't match, ask the user rather than guessing.

### 4. Email everything to Expensify (Claude, with gog)

Dry run first (`-n`), check the output, then run for real.

**Anthropic**: forward each receipt email. The original PDFs go along by default.
```
gog -a personal gmail forward <messageId> --to receipts@expensify.com --note "Anthropic Max plan, <date>, <amount>"
```

**OpenAI and Cursor**: one email with all the PDFs attached.
```
gog -a personal gmail send --to receipts@expensify.com \
  --subject "AI subscription invoices: <vendors and months>" \
  --body "<one line per invoice: vendor, date, amount>" \
  --attach <pdf1> --attach <pdf2> ...
```

Write subjects as plain text (use "and", not `&`). Confirm with `gog -a personal gmail search 'in:sent to:receipts@expensify.com newer_than:1d' --plain`.

If the user prefers to send themselves, create drafts instead (`gog gmail drafts create ... --attach`, or `gog gmail drafts forward`) and let them hit send.

### 5. Verify receipts landed (Claude)

SmartScan takes a few minutes. Search Expensify for `status:["unreported","drafts"]` expenses and confirm every expected receipt arrived with the right amount and merchant. Flag missing or duplicate entries. If one is still missing after about 5 minutes, re-send it.

Re-check the OpenAI billing page here if a charge was pending in step 1.

### 6. Categorize and build the report (Claude via claude-in-chrome; user submits)

Navigate to the unreported/drafts search:

`https://new.expensify.com/search?q=type%3Aexpense+status%3Aunreported%2Cdrafts+sortBy%3Adate+sortOrder%3Adesc`

1. Dismiss any promo modal (a "Concierge AI" popup appears over the list).
2. Tick the checkbox on **only** the AI subscription rows. Old unrelated unreported expenses live here too (stale Lyft/Uber/Alaska rows); never use the select-all header checkbox. Confirm the footer reads the expected count and total before continuing.
3. **"N selected" dropdown → "Edit multiple"** → set both fields at once:
   - **Category**: the list is hierarchical. Pick `Software Subscription/Licenses` **nested under the `General Allowance` header**, not the top-level `Software subscription/Licenses` (lowercase "s") that SmartScan auto-assigns. The panel then reads `General Allowance: Software Subscription/Lic…`; verify this before saving.
   - **Tag**: `AI Credit Allowance`
   - Click **Save**.
4. Re-select the same rows → **"N selected" → "Move to report" → "Create report"**. Open the "N selected" menu, wait a second, and click "Move to report" by its `find` ref: a coordinate click sent before the menu renders lands on a row and opens that expense's details instead (Escape closes it, and the selection survives) under the **FilOz** workspace. Check the workspace label; an unrelated draft report may also be listed.
5. Open the new draft (sidebar **Drafts**), click the **pencil** next to the auto-generated title, and rename it (e.g. `August-September 2026 AI Subscriptions`). The default title ends in "(CHOOSE ONE)" and must be replaced.
6. Verify the report: correct count, total, category and tag on every row, workspace = FilOz.

**Expected violation:** expenses older than 30 days show a red "Date older than 30 days" flag and the report header says "Waiting for you to fix the issues". This is normal for any backfill and does not block submission; tell the user rather than trying to clear it.

**User action:** Review and hit **Submit**.

### 7. Final verification (Claude)

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
| Anthropic receipt not found in Gmail | Check if the billing date has passed. Search with a broader date range. Check the claude.ai billing page. |
| OpenAI/Cursor billing page changed | Pause and describe the current UI. Update these instructions after resolving. |
| Vendor site logged out | Stop and ask the user to log in. Never enter credentials. |
| gog account alias missing or auth expired | Ask the user; they may need `gog auth add` (interactive, suggest `! gog auth add ...`). |
| Downloaded PDF doesn't match the expected invoice | Ask the user; don't send it. |
| Receipt not appearing in Expensify | SmartScan can take a few minutes. Re-check. If still missing after 5 min, re-send. |
| Multiple receipts for one vendor | Flag to user: may be a plan change, proration, or API usage on top of the subscription. |
| Duplicate expense | Flag to user to delete in Expensify. Can happen if a receipt was sent twice. |

---

## Upstream feature requests to monitor

If either lands, the user's last download step for that vendor goes away: switch it to Gmail search plus `gog gmail forward`, like Anthropic.

| Vendor | Request | URL |
|--------|---------|-----|
| OpenAI | Email receipts to billing email | https://community.openai.com/t/email-receipts-to-billing-email-address/731689/67 |
| Cursor | Email invoices to additional address | https://forum.cursor.com/t/ability-to-get-invoice-via-additional-email-address-es/112720 |

---

## Default posture: always improve

Every run should remove some manual effort. Don't just execute the steps; question whether each manual step is still necessary.

### After every run

1. **Identify friction**: tell the user what took the most effort and what could be better next time.
2. **Test assumptions** that could remove a user step:
   - Can Claude trigger Cursor's **Download** menu (single month) itself now that downloads go straight to `~/Downloads`?
   - Can Claude trigger Cursor's **Download** itself and find the file in `~/Downloads`?
   - Does the Expensify MCP have write access now (check the tool list)?
   - Has either vendor started sending email receipts (search Gmail)?
3. **Update this skill** directly when something changed. Don't just suggest it.
4. **Suggest improvements**, e.g. a monthly reminder so months don't pile up, or new AI subscriptions spotted on the card or in Expensify.

### Aspirational goal

The user says "expense my AI tools" and Claude handles everything end to end, with one confirmation before sending and the user's Submit at the end.
