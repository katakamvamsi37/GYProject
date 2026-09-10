# API contract

Base URL: /api. Protected endpoints require `Authorization: Bearer <access>`.
Frontend calls live in src/api, not inside UI components.

## Sessions and accounts

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /login/ | Email/mobile/legacy username + matching password; returns access, refresh, user |
| POST | /auth/token/refresh/ | Rotate a refresh token |
| GET | /me/ | Server-validated current user and role |
| POST | /logout/ | Blacklist the supplied refresh token |
| POST | /auth/password/change/ | Current and new password; invalidates old access |
| GET/PATCH | /profiles/:id/ | Own profile; administrators may access another profile |
| GET | /users/ | Paginated administrator-only account list |
| POST | /signup/ | Administrator creates an active account |
| PATCH | /users/:id/access/ | Administrator changes role and is_active |
| POST | /users/:id/password/ | Administrator sets a new password for a member or another administrator |
| GET | /profiles/:id/avatar/:version/ | Retrieve the current uploaded profile image |
| POST | /auth/otp/request/, /auth/otp/verify/, /auth/password/reset/ | Disabled; returns 410 |

User creation requires name, email, password, role; optional phone enables mobile login. Passwords must pass Django validation, including at least ten characters.
Profile patch accepts name/email/phone/avatar_url, or a local image file in avatar. Role is never changed by profile patch.
Django staff privileges and self-demotion are not editable via the access API.

### Email or mobile login

```http
POST /api/login/
Content-Type: application/json

{"identifier": "9876543210", "password": "the-account-password"}
```

Use the account's email address or saved mobile number in `identifier`. Existing clients may instead send `email`, `phone`, or `username` as the identifier field. Send one identifier, not conflicting email and phone values. A wrong password, inactive account, missing account, or identifier shared by multiple accounts returns 401 without tokens.

Indian mobile numbers are stored with `+91`; `9876543210`, `919876543210`, and `+91 98765-43210` match the same number. Outside India, include the `+` country code. New profile and signup requests reject numbers already in use. The migration normalizes existing valid numbers without deleting legacy data. If existing accounts share a number, an admin must correct their profiles before that number can be used to log in. Email sign-in remains available. Updating the profile email retires the old email as a login identifier.

### Password reset from Access management

```http
POST /api/users/42/password/
Authorization: Bearer <admin-access>
Content-Type: application/json

{"new_password": "NewFestivalPassword!445"}
```

Only administrators may call this endpoint. It accepts member and administrator targets, including Django staff accounts. The target's current password is not required. Success returns `{"detail": "Password updated. This user must sign in again."}`. Existing access and refresh sessions are invalidated. Password values and hashes are excluded from the audit event. The existing self-service `/auth/password/change/` endpoint still requires the current password.

### Upload a local profile photo

Send `PATCH /api/profiles/:id/` as multipart form data with an `avatar` file. The user may update their own profile; admins may update other profiles. Text fields such as `name` and `phone` may be included in the same request. Do not send `avatar_url` alongside `avatar`.

```javascript
const form = new FormData();
form.append("avatar", fileInput.files[0]);
form.append("name", displayName);
const response = await fetch(`${apiBase}/profiles/${userId}/`, {
  method: "PATCH",
  headers: { Authorization: `Bearer ${accessToken}` },
  body: form,
});
const result = await response.json();
// On success, use result.user.avatar_url as the image src.
```

Here `apiBase` includes `/api`. Let the browser set the multipart Content-Type and boundary; do not force JSON headers for this request. This uses DRF's [multipart upload support](https://www.django-rest-framework.org/api-guide/parsers/#multipartparser).

Uploads accept JPEG, PNG, and WebP, up to 5 MB and 20 megapixels. The backend decodes the image, removes metadata, resizes it to fit 512 × 512, and stores a WebP image in PostgreSQL/SQLite. No separate media disk or storage credentials are needed; images are included in database backups. Login, `/me/`, profile, and account-list responses return an absolute `avatar_url`.

The returned image URL can be displayed without an Authorization header. Uploading or replacing it requires authentication. Replacing an image changes its URL and retires the old URL. Send `{"avatar_url": ""}` as a JSON profile patch to remove the image. Existing external avatar URLs remain supported. Deactivated accounts' uploaded images return 404.

Deployment requires installing the updated requirements and running `python manage.py migrate` to apply `0006_profile_images_and_phone_login`. The frontend must connect its password-reset form, email/mobile login input, and local file picker to these API contracts.

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
