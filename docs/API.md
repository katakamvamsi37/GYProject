# API contract

Base URL: /api. Protected endpoints require `Authorization: Bearer <access>`.
Frontend calls live in src/api, not inside UI components.

## Sessions and accounts

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /login/ | Username/email + password; returns access, refresh, user |
| POST | /auth/token/refresh/ | Rotate a refresh token |
| GET | /me/ | Server-validated current user and role |
| POST | /logout/ | Blacklist the supplied refresh token |
| POST | /auth/password/change/ | Current and new password; invalidates old access |
| GET/PATCH | /profiles/:id/ | Own profile; administrators may access another profile |
| GET | /users/ | Paginated administrator-only account list |
| POST | /signup/ | Administrator creates an active account |
| PATCH | /users/:id/access/ | Administrator changes role and is_active |
| POST | /auth/otp/request/, /auth/otp/verify/, /auth/password/reset/ | Disabled; returns 410 |

User creation requires name, email, password, role. Passwords must pass Django validation, including at least ten characters.
Profile patch accepts name/email/phone/avatar_url. Role is never changed by profile patch.
Django staff privileges and self-demotion are not editable via the access API.

## Operational records

| Resource | Supported operations |
|---|---|
| /dashboard/?year=2026 | GET aggregate figures |
| /plans/ | GET list, POST create |
| /plans/:id/?year=2026 | GET detail, PATCH update |
| /members/ | GET list, POST create |
| /members/:id/ | GET detail, PATCH update |
| /expenses/ | GET list, POST submit |
| /expenses/:id/?year=2026 | GET detail |
| /expenses/:id/review/?year=2026 | POST approve/reject/void |
| /payments/ | GET list, POST submit |
| /payments/:id/?year=2026 | GET detail |
| /payments/:id/review/?year=2026 | POST approve/reject/void |
| /audit/ | GET list |
| /audit/:id/?year=2026 | GET detail |
| /export/:resource/?year=2026&file_format=csv | GET CSV or XLSX |

Supported exports: plans, expenses, payments, members, audit.
Permissions are in WORKFLOWS.md and core/api/permissions.py.

## Lists and filters

Paginated response:

```json
{
  "count": 51,
  "next": "http://localhost:8000/api/expenses/?page=2",
  "previous": null,
  "results": []
}
```

Use page (default 1), page_size (default 25, maximum 100), year (2000-2100), search, and applicable status/category/plan filters.
Member directory is current and not year-scoped. Audit dates refer to the action date.
Exports return all matching records rather than a single page.
A missing year defaults to the current calendar year.

## Review payload

```json
{
  "action": "approve",
  "note": "Matched voucher GY-014 with supplier receipt."
}
```

A reviewer must be an administrator or treasurer and must be different from created_by.
Pending entries can be approved or rejected. Posted entries can be voided. Repeated or invalid transitions return 400.

## Retry-safe submission

Send `Idempotency-Key: <UUID>` when posting an expense or collection.
The frontend creates one key per open entry form and reuses it if the request is retried.
The same payload/key returns the original entry. A changed payload or another actor using that key is rejected.
This prevents a lost response from creating a duplicate entry on retry.

Without a key, each POST is a new submission. Non-cash collections additionally enforce uniqueness of method + transaction_reference among pending/confirmed records.

## Error handling

Validation errors return 400 with field messages; unauthenticated requests return 401; unauthorized roles return 403.
Financial records do not expose update or delete endpoints (405).
A disconnected server is a failure, never a simulated success.
