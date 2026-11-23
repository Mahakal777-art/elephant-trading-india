# v1.3 Known Risks and OWASP Top 10 Review

Statuses are scoped per control. `DONE-VERIFIED` means a command/test was executed in the local sandbox; GitHub CI has not been run because CI logs/repository access were not provided.

## Known risks

1. **Resend test sender cannot be treated as an owner alert channel.** Official examples pair `onboarding@resend.dev` with `delivered@resend.dev`. Owner inbox alerts require a verified sending domain. Customer email remains disabled by default.
2. **Smoke is incomplete.** It checks health, core pages, all eight category pages, Turnstile fail-closed, dedicated admin login/dashboard/export/logout. It does not yet complete a successful buyer form submit, verify its row, duplicate 409, cleanup of that successful production row, or dedicated-account lockout. A live Turnstile token fixture and disposable admin lifecycle are still required.
3. **PostgreSQL CI not executed locally.** CI is configured to use PostgreSQL 16, but the local sandbox had no PostgreSQL server/client or Docker. The concurrent Postgres upsert test is skipped locally and must pass in GitHub CI.
4. **Coverage CI threshold is 85%.** Local SQLite coverage was 91%; Postgres-only integration coverage is not locally measured. CI threshold is configured at 85%.
5. **Backup artifact is not independent off-site storage.** Encrypted backup is stored as a GitHub Actions artifact with 30-day retention. Off-site object storage/immutable retention is deferred.
6. **Follow-up email delivery is not implemented.** Existing scheduler trigger/endpoint and unique lead+step key are present, but 3/7/14-day delivery, retry/backoff, unsubscribe and opt-out enforcement are incomplete. `CUSTOMER_EMAILS_ENABLED=false` remains the safe default.
7. **Matching remains partial.** Category/product/state/city/capacity/MOQ/indicative-price triage exists. Certification matching, proper location tiers/proximity, normalized price bands and full admin explainability remain incomplete.
8. **Agreements remain partial.** Current PDF is a combined draft. Separate buyer/supplier PDFs, version table/hash, signature-ready fields and complete audit history are not implemented.
9. **Invoice/ledger remains partial.** Deal commission ledger exists; GST invoice logic, SAC validation, interstate/intrastate tax calculations and overdue alerts are not implemented.
10. **Verification workflow, CSV, dashboard filters and privacy intake exist in limited form.** Automated evidence verification, privacy erasure execution and complete immutable audit are not implemented.
11. **Docker base image is version-tag pinned, not digest pinned.** Runtime Python dependencies are exact-version pinned; base image digest pinning remains recommended.
12. **Framework deprecation warnings remain.** FastAPI `on_event` and older Jinja `TemplateResponse` call style emit warnings; functionality passes local tests but needs migration to lifespan/new signature.
13. **No live deploy, Turnstile, Resend delivery, Neon migration, Koyeb health check or backup restore was executed.**

## Outbound HTTP call inventory (SSRF review)

| Call | Destination | User-controlled URL? | Reason / control |
|---|---|---:|---|
| Cloudflare Turnstile verification | `https://challenges.cloudflare.com/turnstile/v0/siteverify` | No | Fixed provider endpoint; server validates challenge token. Timeout 8s; exceptions fail closed. |
| Resend email API | `https://api.resend.com/emails` | No | Fixed provider endpoint; API key in environment; timeout 12s. |
| Supplier website / IndiaMART URL | No outbound request | No | Stored only after scheme/host validation. Never fetched, crawled, previewed or redirected server-side. |
| WhatsApp link | Browser navigation to `https://wa.me/…` | No server fetch | Client-side external link only. |
| Umami script | Configured analytics script URL | Config-controlled | Browser-side script only; administrator-controlled URL; analytics notice displayed when configured. |

## OWASP Top 10 (2021) mapping

| OWASP | Review | Status |
|---|---|---|
| A01 Broken Access Control | Admin/internal route inventory script; session auth; CSRF on mutating admin routes; smoke cleanup is admin+CSRF protected. Public login is intentionally unauthenticated. | DONE-REVIEWED; route auth tests DONE-VERIFIED locally |
| A02 Cryptographic Failures | Argon2 password hashes; signed sessions; secret key minimum length; HTTPS-only production cookie. Key rotation remains operator action. | DONE-REVIEWED |
| A03 Injection | SQLAlchemy parameterized queries; Jinja autoescape; supplier URL rejected unless public http/https. XSS template test local. | PARTIAL / XSS test DONE-VERIFIED locally |
| A04 Insecure Design | Consent, manual verification, no direct goods handling, uploads disabled, customer mail disabled. Abuse controls are not fully load-tested. | PARTIAL |
| A05 Security Misconfiguration | Security headers, CSP, HSTS production, non-root container, runtime-only pinned dependencies. CSP still permits inline scripts/styles. | DONE-REVIEWED |
| A06 Vulnerable and Outdated Components | `pip-audit`, Dependabot and Bandit configured in CI; not run in sandbox because tools unavailable. | DONE-REVIEWED; CI NOT VERIFIED |
| A07 Identification and Authentication Failures | Argon2, login rate limit, account lockout, session reset after login. Dedicated smoke lockout test incomplete. | PARTIAL |
| A08 Software and Data Integrity Failures | CI, migrations, coverage gate, encrypted backup/restore workflow defined. No signed build provenance or external restore proof. | PARTIAL |
| A09 Security Logging and Monitoring Failures | Admin alert failure/success stored in Activity and failure logged; broader alerting/retention/PII-safe log review remains incomplete. | PARTIAL |
| A10 Server-Side Request Forgery | Supplier URLs are not fetched; only fixed Turnstile and Resend endpoints make outbound HTTP calls. | DONE-REVIEWED; URL rejection tests DONE-VERIFIED locally |


## Static review follow-up (v1.3.1 patch)

- `DATABASE_URL_POOLED` selection is tracked before URL scheme normalization; Psycopg 3 `prepare_threshold=None` is therefore applied to the pooled engine. Local helper regression test passes; live Neon/PgBouncer verification still requires CI/runtime.
- Active duplicate leads are protected by partial unique index migration `0003_active_lead_dedup`. If legacy active duplicates exist, migration intentionally fails rather than deleting/merging customer records; reconcile manually before deployment.
- Agreement text is XML-escaped before ReportLab Paragraph parsing.
- Backup scripts/workflow normalize SQLAlchemy `+psycopg` URLs and pass GPG passphrases over file descriptor/stdin, not command-line arguments. Live backup/restore remains unverified until CI.
- Login rate limits count failed attempts only; successful login does not consume the failure budget. Legacy naive lockout timestamps are interpreted as UTC. Cron authentication occurs before rate limiting.
- `/privacy/request` now requires session CSRF. Activity notes store a keyed requester reference, not raw email. This is pseudonymization, not anonymization. Activity retention is proposed as 365 days, but no automatic purge job exists; manual retention review remains required.
- Lazy session middleware reads `SECRET_KEY` and `COOKIE_SECURE` on first ASGI invocation. Set them before starting the app and do not change them while running.
- Matching treats legacy NULL category/product values as empty strings. City score remains an alternative to state score (not additive) to avoid double-counting location.
- Existing FastAPI startup-event and Starlette TemplateResponse deprecation warnings remain; they do not fail current tests.
- `scripts/migrate_sqlite_to_postgres.py` remains a one-time migration utility with one final commit and no per-row checkpoints. If it fails mid-run, inspect/rollback the target transaction before retrying; do not assume partial progress is safely resumable.
