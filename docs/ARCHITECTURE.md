# Project map — where to make changes

## Active structure

```text
GY Project/
├── backend/
│   ├── config/                 Django settings and root URLs
│   │   ├── settings.py         Environment, DB, JWT, CORS and deployment settings
│   │   └── urls.py             /admin, /api, token refresh
│   ├── core/
│   │   ├── api/
│   │   │   ├── auth.py         Login/logout, profile, password and account access
│   │   │   ├── records.py      Record endpoints and independent review
│   │   │   ├── serializers.py  Validation and API response fields
│   │   │   ├── permissions.py  Role matrix
│   │   │   ├── dashboard.py    Festival totals and monthly/category aggregation
│   │   │   ├── exports.py      Authenticated CSV/XLSX files
│   │   │   ├── filters.py      Shared year/search/status/category/plan filtering
│   │   │   └── pagination.py   Page sizes and limits
│   │   ├── services/audit.py   Before/after snapshots in write transactions
│   │   ├── models.py          Database fields, constraints and relationships
│   │   ├── migrations/        Versioned schema changes; never hand-delete
│   │   ├── tests/             Authentication, ledger and export regression tests
│   │   ├── management/commands/
│   │   │   ├── backup_database.py  Consistent local SQLite backups
│   │   │   └── seed_demo.py        Additive, labeled samples
│   │   ├── admin.py           Read-only inspection of business records
│   │   └── urls.py            API route registry
│   ├── .env.example           Copyable environment template
│   ├── requirements.txt       Allowed dependency ranges
│   ├── requirements.lock.txt  Tested exact versions
│   └── manage.py              Backend command entry
├── frontend/
│   ├── src/
│   │   ├── api/               HTTP calls only; shared client handles JWT refresh
│   │   ├── context/           Auth state and selected festival year
│   │   ├── components/
│   │   │   ├── layout/        Sidebar, topbar, mobile navigation and main layout
│   │   │   ├── Feedback.jsx   Loading, empty, error and status components
│   │   │   ├── Modal.jsx      Native accessible dialog
│   │   │   └── ErrorBoundary.jsx
│   │   ├── features/
│   │   │   ├── dashboard/     Chart component
│   │   │   └── records/
│   │   │       ├── config.js      Form fields, columns, labels and defaults
│   │   │       ├── RecordsPage.jsx Filters, table, pagination and exports
│   │   │       ├── RecordForm.jsx  Create/edit forms
│   │   │       └── ReviewDialog.jsx Financial detail and review action
│   │   ├── hooks/useRecords.js Paginated data loading and cancellation
│   │   ├── pages/             Route-level screens
│   │   ├── routes/
│   │   │   ├── AppRouter.jsx      URL definitions and lazy page imports
│   │   │   ├── ProtectedRoute.jsx Server-validated session and role gating
│   │   │   └── DashboardRoute.jsx Shared layout with nested page outlet
│   │   ├── styles/
│   │   │   ├── tokens.css      Colors, base fonts, spacing foundations
│   │   │   ├── layout.css      Sidebar, topbar, responsive shell
│   │   │   ├── components.css  Buttons, tables, forms, dialogs and feedback
│   │   │   └── pages.css       Dashboard, sign-in and profile styling
│   │   ├── utils/format.js     INR/date formatting, categories and UI role lists
│   │   ├── styles.css         Ordered CSS imports
│   │   └── main.jsx           React entry point
│   ├── tests/                 Browser regression flows
│   ├── vite.config.js         Build splitting and development proxy
│   └── playwright.config.js   Isolated browser-test servers
├── scripts/test_server.py     Temporary seeded backend for browser tests only
├── docs/                     Setup, workflow and maintenance notes
├── archive/legacy-django/     Preserved inactive frontend Django scaffold
└── backups/                  Local backups; ignored by Git
```

`frontend/src/App.jsx` is a compatibility re-export. `backend/core/views.py` is a pointer to the split API modules.
Neither contains a second implementation.

## Common edits

| Change wanted | Edit first | Also check |
|---|---|---|
| Theme/color/font | styles/tokens.css | components.css and pages.css |
| Sidebar or mobile navigation | components/layout/DashboardLayout.jsx | routes/AppRouter.jsx |
| A route/page | pages/ + routes/AppRouter.jsx | Backend permission matrix |
| Form label/default/column | features/records/config.js | API serializer fields |
| Validation | backend/core/api/serializers.py | Regression tests |
| A database field | backend/core/models.py | Migration, serializer, UI and exports |
| Role permission | backend/core/api/permissions.py | UI role lists and route gates |
| Financial calculation | backend/core/api/dashboard.py | Plan serializer and export aggregation |
| Approval behavior | backend/core/api/records.py | tests/test_records.py |
| API address | frontend/.env or Vite proxy | CORS settings |
| Auth expiry/refresh | api/client.js + context/AuthContext.jsx | Browser refresh test |

## Data flow

A form calls an API helper → the shared authenticated client sends it → Django checks permissions and serializer validation → the write and audit snapshot commit together → the UI reloads the affected ledger.

Financial retries use a UUID submission key. A retry of the same payload returns the existing entry; a changed payload under an already-used key is rejected. Non-cash transaction references cannot be duplicated among pending/confirmed collections.

UI visibility is convenience. Django is the authorization boundary.

## Deliberate boundaries

- Members in the directory and login accounts are separate concepts. A volunteer need not have login access.
- The year selector is a calendar-year festival edition, January–December in Asia/Kolkata. It is not an April–March fiscal-year setting.
- Audit trail year filtering refers to the year an action happened. Editing an old festival entry today creates an event in today's year.
- `Plan.spent` remains only to preserve old data. The API derives current spending from approved related expenses.
- OTPChallenge remains solely for migration/history compatibility. All public OTP/recovery endpoints return 410.
- Audit events are read-only through the app/admin. Database administrators can still alter the database; independent backups/access controls are required for stronger tamper resistance.
