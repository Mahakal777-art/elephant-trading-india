# Elephant Trading v1.3 — Audit Response & Delivery Status

**CI LOGS NOT PROVIDED.** No pasted v1.2 CI log was supplied. No GitHub CI execution is claimed. Status labels are item-scoped.

## P0 — release blockers

| ID | Requirement | Status | Evidence / remaining gate |
|---|---|---|---|
| P0-A1 | Verify `onboarding@resend.dev` to owner inbox | DONE-REVIEWED | Official Resend examples pair it with `delivered@resend.dev`; do not rely on it for arbitrary owner inbox delivery. Owner notifications require a verified sending domain/sender. |
| P0-A2 | Enable admin alerts without domain if possible | BLOCKED(Resend test sender is not documented as a general owner-recipient sender) | No fake enablement. Admin alerts remain configurable; no verified sender means no real owner email. |
| P0-A3 | Customer emails flag-gated off | DONE-REVIEWED | `CUSTOMER_EMAILS_ENABLED=false` default; customer delivery not enabled. |
| P0-A4 | Alert failure must not fail form submit; async/try-except/log | DONE-VERIFIED | Background task, exception logging and Activity event; local test `test_admin_alert_failure_is_logged_without_raising` passes. |
| P0-A5 | Admin can see alert failure | DONE-VERIFIED | Dashboard renders Admin notification status; failure Activity persisted by test. |
| P0-B1 | `SMOKE_ADMIN_*` mandatory | DONE-REVIEWED | Smoke workflow explicitly fails if either secret missing. |
| P0-B2 | Smoke lead marker | DONE-VERIFIED | Smoke identifier format and marker cleanup path; local fixture creates `SMOKE-TEST` lead. |
| P0-B3 | Cleanup authenticated endpoint / CLI and deletion proof | DONE-VERIFIED | `/admin/smoke-cleanup` requires admin session + CSRF; local test proves deleted=1 and row no longer exists. |
| P0-B4 | Smoke rows excluded from dashboard counts/export | DONE-VERIFIED | Dashboard and CSV filters exclude marker rows; local test asserts marker absent in dashboard. |
| P0-B5 | Smoke health + 8 category pages | DONE-REVIEWED | Script includes `/health`, 8 category pages and core public pages; no live production run. |
| P0-B6 | Successful buyer submit → row → dashboard | PARTIAL | Local application test verifies buyer insert and duplicate 409, but production smoke script intentionally stops at fail-closed Turnstile without a live valid challenge. |
| P0-B7 | Duplicate 409 in production smoke | PARTIAL | Duplicate 409 is covered by local test; production smoke does not execute successful submit/duplicate cycle. |
| P0-B8 | Turnstile fail-closed | DONE-VERIFIED | Local tests plus smoke script missing-token rejection; no live Cloudflare challenge run. |
| P0-B9 | Lockout in production smoke | PARTIAL | Existing local lockout test covers rate-limit lockout behavior; production smoke avoids locking an account and has no disposable admin lifecycle. |
| P0-B10 | Logout in smoke | DONE-REVIEWED | Script logs in, checks dashboard/export, then logs out; not run against production. |
| P0-C1 | PostgreSQL service primary in CI | DONE-REVIEWED | CI Postgres 16 service and `DATABASE_URL` are configured. No GitHub CI logs. |
| P0-C2 | Postgres concurrent atomic limiter test | DONE-REVIEWED | `tests/test_postgres.py` executes 80 concurrent increments and asserts final count. Skipped locally because no Postgres server. |
| P0-C3 | Postgres lockout test | DONE-REVIEWED | Existing lockout integration test now uses CI `DATABASE_URL`; local run used SQLite. |
| P0-C4 | Alembic upgrade/downgrade/upgrade round trip | DONE-REVIEWED | CI workflow has `upgrade head`, `downgrade 0001_initial`, `upgrade head`. Offline SQL generation locally passes; live Postgres round trip not run. |
| P0-D1 | Match pg_dump major to Neon server | DONE-REVIEWED | Workflow queries Neon `server_version_num`, installs PGDG matching client major, prints both, fails on mismatch. |
| P0-D2 | Encrypted artifact | DONE-REVIEWED | AES-256 GPG encryption configured. Not executed against Neon. |
| P0-D3 | Restore test, matching temporary Postgres major | DONE-REVIEWED | Workflow launches `postgres:$PG_MAJOR`, restores, and runs leads/admins/deals/Alembic sanity queries. Not executed. |
| P0-D4 | Retention and storage documented | DONE-REVIEWED | GitHub Actions artifact, 30-day retention; off-site storage explicitly deferred. |
| P0-E1 | Website URL server validation | DONE-VERIFIED | HTTP/HTTPS only, length cap, IDNA lowercase normalization, rejects credentials, localhost/private IP, malformed schemes; local tests pass. |
| P0-E2 | Link rel/target attributes | DONE-REVIEWED | Admin website anchor uses `target=_blank` and `rel=nofollow noopener noreferrer`; Jinja autoescape applies. |
| P0-E3 | Confirm supplier URL never fetched server-side | DONE-REVIEWED | Search found no supplier URL fetch path. Only fixed Resend and Cloudflare URLs are fetched. |
| P0-E4 | XSS tests / script payload in fields | PARTIAL | Jinja autoescape test and unsafe URL tests pass; not every text field has a route-level payload matrix. |
| P0-E5 | A10 SSRF outbound HTTP inventory | DONE-REVIEWED | Listed in `KNOWN_RISKS_OWASP.md`; supplier URLs are stored only, never fetched. |
| P0-F1 | Enumerate `/admin*` and `/internal*` routes | DONE-VERIFIED | `scripts/audit_routes.py` executed; route list included in sandbox logs. |
| P0-F2 | Unauthenticated access tests per protected route | DONE-VERIFIED | Route-enumeration test checks each protected route; `/admin/login` is intentionally public. |
| P0-F3 | Wrong/missing CRON_TOKEN → 401 | DONE-VERIFIED | Local tests assert wrong and missing bearer token return 401. |
| P0-F4 | CSRF on every state-changing admin POST | DONE-REVIEWED | All admin mutating handlers call `check_csrf`; no generalized automatic middleware enforcement. |

## P1 — product completion

| Requirement | Status | Evidence / remaining work |
|---|---|---|
| 3/7/14-day follow-up scheduling | PARTIAL | Followup table/cron trigger exists; delivery scheduling logic not complete. |
| Follow-up idempotency unique `lead_id+step` | DONE-REVIEWED | Unique constraint `uq_followup_lead_offset` exists. |
| Follow-up retry/backoff/max attempts/failure state | NOT STARTED | `attempts`/`last_error` fields exist but worker/retry policy not implemented. |
| Signed one-click unsubscribe without login | NOT STARTED | No public signed unsubscribe route. |
| `followup_optout` enforcement | NOT STARTED | Field exists; worker does not enforce it. |
| DPDP data-deletion link | PARTIAL | Privacy request intake exists; no signed deletion link or automated identity-verified deletion. |
| Buyer confirmation email | NOT STARTED | Customer email feature remains disabled. |
| Supplier confirmation email | NOT STARTED | Customer email feature remains disabled. |
| `CUSTOMER_EMAILS_ENABLED` flag gate | DONE-REVIEWED | Flag default false; no customer sends. |
| Certification matching | NOT STARTED | No certification data model/scoring. |
| City/state proximity tiers | PARTIAL | Same-city/state match exists but scoring tiers are simplistic and city/state ordering needs correction. |
| MOQ and price band scoring | PARTIAL | MOQ/price presence contributes points; no normalized MOQ fit or numeric price-band comparison. |
| Matching explainability in admin UI | PARTIAL | Existing reasons shown; no full factor-by-factor score breakdown for all dimensions. |
| Separate buyer PDF | NOT STARTED | One combined agreement draft remains. |
| Separate supplier PDF | NOT STARTED | One combined agreement draft remains. |
| `agreement_versions` table | NOT STARTED | No version table. |
| Agreement audit trail | PARTIAL | Basic Activity entries exist; no complete agreement-version audit. |
| E-sign-ready signature fields | PARTIAL | Combined PDF contains signature lines; no structured signature block/hash metadata. |
| Version hash | NOT STARTED | Not implemented. |
| Lawyer-review watermark | PARTIAL | Legal draft warning in PDF text/site banner; not a dedicated visual watermark. |
| GST-aware commission invoice | NOT STARTED | No invoice generation. |
| GSTIN, HSN/SAC placeholder | PARTIAL | GSTIN field exists; HSN/SAC invoice field absent. |
| CGST/SGST/IGST state logic | NOT STARTED | Not implemented. |
| `CA REVIEW REQUIRED` flag | NOT STARTED | Not implemented. |
| Overdue admin reminders | NOT STARTED | Not implemented. |
| Verification workflow | PARTIAL | Admin can change Pending/Verified/Rejected; no evidence checklist/workflow. |
| Commission ledger | PARTIAL | Expected/received commission tracked on deals; no full ledger/reconciliation. |
| CSV export | DONE-VERIFIED | Authenticated CSV endpoint exercised in local admin workflow test. |
| Dashboard filters | DONE-VERIFIED | Search/kind/status filters are present and rendered; filter matrix not exhaustive. |
| Privacy request intake | DONE-VERIFIED | Local access request endpoint test passes. |
| Verified data deletion workflow | NOT STARTED | Request is logged for manual identity verification; no deletion engine. |

## P2 — SEO, analytics and supply-chain security

| Requirement | Status | Evidence / remaining work |
|---|---|---|
| JSON-LD FAQ | DONE-REVIEWED | FAQPage schema added; no Google rich-result validation. |
| JSON-LD BreadcrumbList | DONE-REVIEWED | BreadcrumbList added; no schema validator run. |
| Form-submit Umami event | DONE-REVIEWED | Event listener added when analytics is configured; no live Umami event verified. |
| Dynamic sitemap | DONE-REVIEWED | Generated from configured base URL and route/category list at request time; no crawler validation. |
| pip-audit in CI | DONE-REVIEWED | Workflow configured; unavailable locally and CI not run. |
| Dependabot config | DONE-REVIEWED | pip and GitHub Actions weekly updates configured. |
| Ruff in CI | DONE-REVIEWED | Workflow configured; Ruff unavailable locally. |
| Bandit in CI | DONE-REVIEWED | Workflow configured; Bandit unavailable locally. |

## Koyeb / Docker

| Requirement | Status | Evidence / remaining work |
|---|---|---|
| Current CLI syntax verified | DONE-REVIEWED | Koyeb CLI docs checked; deploy command uses `koyeb deploy PATH APP/SERVICE`. |
| First-time service creation | DONE-REVIEWED | Click-by-click Dashboard steps in `SETUP_SECRETS.md`; app/service creation still requires owner action. |
| Runtime environment variables | DONE-REVIEWED | Runtime env and GitHub secrets/variables documented. |
| Health path and port | DONE-REVIEWED | `/health`, port 8000, HTTP route documented/configured. |
| Dockerfile non-root | DONE-REVIEWED | Runtime user `app`. |
| Pinned base image | PARTIAL | Version tag `python:3.12.8-slim-bookworm`, not immutable digest. |
| Runtime-only dependencies | DONE-REVIEWED | Separate exact-version `requirements-runtime.txt`; test/lint/security tools excluded from image. |
| Docker build | BLOCKED(Docker executable unavailable in sandbox) | No Docker daemon/CLI locally. |

## Legal / privacy

| Requirement | Status | Evidence / remaining work |
|---|---|---|
| Privacy lawyer-review banner | DONE-REVIEWED | Shared legal banner states lawyer review pending. |
| Terms lawyer-review banner | DONE-REVIEWED | Shared legal banner states lawyer review pending. |
| Commission & Non-Circumvention lawyer-review banner | DONE-REVIEWED | Shared legal banner states lawyer review pending. |
| Grievance officer/contact field | DONE-REVIEWED | `GRIEVANCE_EMAIL` runtime variable shown in shared footer banner. Owner must configure actual contact. |
| Cookie/analytics notice | DONE-REVIEWED | Notice appears when Umami analytics is configured. Legal adequacy requires counsel review. |

## Local versus CI execution

**Locally executed:** Python compileall; pytest suite on SQLite; coverage threshold; Alembic PostgreSQL offline SQL generation; YAML parse; route inventory script. Exact raw output is in `SANDBOX_TEST_LOGS.txt`.

**CI-only / not executed here:** PostgreSQL service tests, concurrent Postgres limiter, Postgres migration round trip, ruff, bandit, pip-audit, Neon backup version match, encrypted backup, restore container, Koyeb deployment and production smoke. **CI LOGS NOT PROVIDED.**
