# Festival operations guide

## Role matrix

| Capability | Administrator | Treasurer | Secretary | Coordinator | Member |
|---|---|---|---|---|---|
| Aggregate overview | Yes | Yes | Yes | Yes | Yes |
| View ledgers, contacts and audit | Yes | Yes | Yes | Yes | No |
| Create/edit budgets | Yes | Yes | No | No | No |
| Submit expense/collection | Yes | Yes | Yes | Yes | No |
| Review someone else's financial entry | Yes | Yes | No | No | No |
| Manage member directory | Yes | No | Yes | No | No |
| Create accounts/change access | Yes | No | No | No | No |
| Export management records | Yes | Yes | Yes | Yes | No |
| Edit own profile/change password | Yes | Yes | Yes | Yes | Yes |

Django staff/superusers are treated as administrators. Staff privileges are managed through Django administration, not the application role form.

## Starting the festival year

1. Select the festival year.
2. Create budgets for decoration, pooja, prasadam, programs, lighting, procession and safety.
3. Add committee members and their responsibilities.
4. Create login accounts only for people who need access.
5. Assign a second administrator or treasurer so each entry has an independent reviewer.

Budget changes are audited. A budget with linked expenses cannot move to another year.

## Expense flow

1. Add description, amount, date, vendor, voucher number and optional receipt URL.
2. Link the appropriate same-year budget, or leave the entry unallocated.
3. Submit. The record begins as **pending** and does not count toward approved spending.
4. Another administrator/treasurer checks evidence and approves or rejects it, with a reason.
5. An approved expense affects the dashboard and that budget's actual spending.

The UI asks for a voucher number. The review desk highlights historical entries without a receipt reference or evidence link.
Evidence is a URL to your own document storage; the app does not upload or independently authenticate those documents.

## Collection flow

1. Record a contribution actually received.
2. Select Cash, UPI, Bank transfer or Cheque.
3. Non-cash entries require the corresponding transaction reference.
4. A second reviewer matches cash receipt/bank evidence and confirms it.

The app does not charge donors, create payable QR codes or automatically verify bank payments.
A pending collection does not increase confirmed funds.

## Corrections and reversals

Submitted financial amounts and descriptions cannot be edited or deleted.
Reject an incorrect pending entry and submit a replacement. Void an approved/confirmed entry with a reason and submit a corrected replacement referencing the original.
The entry and its audit snapshots remain available.

A submitter cannot review their own entry, including voiding it. Use a second authorized reviewer.

## Understanding totals

- Confirmed collections: sum of collections with status `confirmed`.
- Approved expenses: sum of expenses with status `approved`.
- Recorded fund balance: confirmed collections minus approved expenses.
- Festival budget: non-cancelled budgets targeting the selected year.
- Budget remaining: festival budget minus approved expenses.

Negative balances are shown honestly. These figures are not a bank reconciliation and do not include opening balances, liabilities, tax calculations or inventory accounting.
Pending/rejected/void records and historical dummy payments are excluded from posted totals.

## Exports and review

CSV/XLSX exports use the active year, search, category and status filters and include all matching pages.
Directory exports include the full current directory, regardless of year.
Audit exports include before/after values and the actor. Monetary XLSX cells are numeric.
Formula-like user text is escaped so it is treated as text by spreadsheet software.

## Account recovery

OTP access is intentionally unavailable. An authorized operator can reset a password:

```powershell
.\.venv\Scripts\python.exe backend/manage.py changepassword USERNAME
```

Verify the person's identity before resetting access. This operator command is outside the application audit stream; retain an administrative record separately.
Users can change their own password through My profile; existing access tokens are then rejected.
