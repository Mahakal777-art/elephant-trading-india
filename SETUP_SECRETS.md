# Elephant Trading v1.2 — GitHub Actions executor setup

Do not paste any credential into ChatGPT or commit it. Use GitHub repository Settings → Secrets and variables → Actions. Use an Environment named `production` for deploy secrets.

## Required repository secrets

| Secret | Source / purpose |
|---|---|
| `DATABASE_URL_DIRECT` | Neon Console → Project → Connect → Direct connection (not pooled); migrations and backup |
| `DATABASE_URL_POOLED` | Neon Console → Connect → Pooled connection; application runtime |
| `SECRET_KEY` | Generate locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `TURNSTILE_SITE_KEY` | Cloudflare Dashboard → Turnstile → widget hostname |
| `TURNSTILE_SECRET_KEY` | Same widget → secret key; server-side Siteverify |
| `RESEND_API_KEY` | Resend Dashboard → API Keys; admin alert only |
| `ADMIN_ALERT_EMAIL` | Owner-controlled inbox address to receive admin notifications |
| `RESEND_FROM` | Verified sender such as `Elephant Trading <alerts@your-domain>` |
| `KOYEB_TOKEN` (or `KOYEB_API_TOKEN`) | Koyeb Control Panel → Account → API access tokens |
| `BACKUP_ENCRYPTION_KEY` | Generate a long random passphrase locally; retain separately for restore |
| `CRON_TOKEN` | Generate a separate random secret; reserve for authenticated cron endpoint |
| `GRIEVANCE_EMAIL` | Public grievance contact address configured in the app |
| `SMOKE_ADMIN_USERNAME` | Dedicated temporary smoke-test admin (mandatory for production smoke workflow) |
| `SMOKE_ADMIN_PASSWORD` | Dedicated smoke-test admin password (mandatory for production smoke workflow) |

## GitHub repository variables

`KOYEB_APP`, `KOYEB_SERVICE`, and `PRODUCTION_BASE_URL` are GitHub Actions variables. `GRIEVANCE_EMAIL` is a repository secret used as the public grievance contact.

## Click-by-click

1. Create a private GitHub repository and upload the project root contents (not the parent folder).
2. GitHub → Settings → Secrets and variables → Actions → New repository secret. Add the names above individually.
3. Add `KOYEB_APP` and `KOYEB_SERVICE` as Actions variables.
4. Neon → create a project. Copy both Direct and Pooled connection strings; use Direct only for migrations/backup.
5. **Koyeb first service — archive-only CLI model (no Git connection):**
   - In Koyeb Dashboard, create an API token: Account → API access tokens. Do not connect a GitHub repository.
   - In GitHub Actions variables set `KOYEB_APP=elephant-trading` and `KOYEB_SERVICE=web` (or your chosen names).
   - The first successful `Deploy Koyeb` workflow runs after Neon migration and executes `koyeb deploy . APP/SERVICE --archive-builder docker --archive-docker-dockerfile Dockerfile`. Koyeb documents that this bundles the local project directory, uploads an archive, and creates or deploys the named App/Service. No Git source is configured, so Koyeb Git auto-deploy does not apply.
   - In Koyeb Dashboard, open the created App → Service → Settings. Confirm Source is an archive/CLI deployment and not a GitHub repository. Set HTTP port `8000`, public route `/`, and health check path `/health` on port `8000`. The workflow supplies runtime variables (production mode, pooled Neon URL, Turnstile, secret key, alert settings, and explicit safety flags) during each archive deploy.
   - Runtime safety values are forced by workflow: `APP_ENV=production`, `COOKIE_SECURE=true`, `TRUST_KOYEB_PROXY=true`, `SMOKE_CLEANUP_ENABLED=false`, `CUSTOMER_EMAILS_ENABLED=false`, and `FOLLOWUPS_ENABLED=false`. The first deployment creates the named service; subsequent workflow runs upload a new archive and update that service.
   - Koyeb documents `koyeb deploy <path> <app>/<service>` and `--archive-builder docker` / `--archive-docker-dockerfile Dockerfile`; CLI reference: https://www.koyeb.com/docs/build-and-deploy/deploy-project-directory and https://www.koyeb.com/docs/build-and-deploy/cli/reference.
6. Cloudflare → Turnstile → create widget for the final Koyeb hostname; copy site/secret keys into GitHub and Koyeb runtime settings.
7. Resend → create API key. **No verified domain does not mean owner-email delivery is enabled.** Resend's official examples pair `onboarding@resend.dev` with `delivered@resend.dev`; the test-send page describes the latter as the test delivery recipient. Do not set `ADMIN_ALERT_EMAIL` to the owner's mailbox expecting the test sender to deliver there. Admin alerts to a real owner inbox require a verified sending domain and sender identity. Until then, failures are recorded as `Activity` rows in the admin dashboard. Customer emails remain `CUSTOMER_EMAILS_ENABLED=false`. Sources: https://resend.com/ and https://resend.com/changelog/sending-test-emails.
8. Domain is optional for first preview. Buy/connect a domain only when ready; set DNS as Koyeb shows and add that hostname to Turnstile and Resend.
9. Push to `main`. CI runs first; Deploy workflow migrates using `DATABASE_URL_DIRECT`, and only then invokes Koyeb CLI. Deploy will fail if migration fails.
10. Run Smoke workflow manually after deploy. `SMOKE_ADMIN_USERNAME` and `SMOKE_ADMIN_PASSWORD` are mandatory secrets; the workflow fails if either is missing. Use a dedicated least-privilege temporary admin and rotate/delete it after smoke. Current script checks public pages, Turnstile fail-closed, admin login/dashboard/logout, and attempts cleanup only for records explicitly marked `SMOKE-TEST`. Full successful buyer-submit/duplicate flow still requires a valid interactive Turnstile token and is not claimed as automated until that fixture is supplied.

## Workflow caveats

- `backup.yml` stores encrypted pg_dump as a GitHub Actions artifact for 30 days, then downloads/decrypts/restores it into an ephemeral PostgreSQL service container and checks the `leads` row count. This is an operational restore drill, not independent off-site object storage. Download and retain an encrypted copy separately for disaster recovery.
- The scheduled `/internal/run-followups` endpoint is guarded by `CRON_TOKEN`, but customer emails are disabled by default and no outbound follow-up delivery is activated in v1.2.
- Resend's test recipient is for simulation/delivery tests, not actual owner notification.

## Current migration notes

`0002_v12_hardening` is a forward-only compatibility migration for existing v1.1 PostgreSQL deployments: it adds supplier business URL and follow-up opt-out columns and creates shared rate-limit/follow-up tables idempotently. The deployment workflow uses the DIRECT connection string and stops before Koyeb deploy if Alembic fails.

## CI failure / troubleshooting

- **CI red at `pip-audit`**: inspect the named advisory and upgrade the affected pinned runtime/dev dependency; do not suppress without a documented risk acceptance.
- **CI red at `bandit`/`ruff`**: fix the source finding; do not add blanket `# nosec` or ignore rules.
- **Alembic upgrade/downgrade fails**: check `DATABASE_URL` points to the CI Postgres service, not Neon; run `alembic history` and inspect migration dependency/SQL.
- **Coverage below 85%**: CI intentionally fails. Add tests for uncovered branches; do not lower the threshold to hide missing coverage.
- **Deploy red before Koyeb step**: Neon direct URL, SSL/connectivity, or migration failed. Koyeb deploy is deliberately gated after migration.
- **Koyeb build red**: confirm Dockerfile path `Dockerfile`, port `8000`, app binds `0.0.0.0`, health path `/health`, runtime env includes pooled DB URL and 32+ character `SECRET_KEY`.
- **Smoke red**: verify HTTPS `PRODUCTION_BASE_URL`, mandatory smoke admin credentials, Turnstile widget hostname, and DB health. Do not run lockout against the owner admin account.
- **Backup red**: workflow prints `pg_dump` and server major versions and intentionally stops on mismatch. The restore job needs the matching PG client package for the archive's source major.

## Backup retention

Encrypted backup is a GitHub Actions artifact with 30-day retention. It is stored in the repository's Actions artifact storage, not independent off-site object storage. Off-site immutable storage is deferred to v1.3+ follow-on operations; this is a disaster-recovery gap.


## v1.3.1 targeted patch notes (archive-only Koyeb deployment)

Koyeb is **not Git-connected**. Do not connect a Git repository in Koyeb. GitHub Actions is only the executor: it installs the official Koyeb CLI, uploads the checked-out project directory as an archive, and deploys it with `koyeb deploy . APP/SERVICE --archive-builder docker --archive-docker-dockerfile Dockerfile`. Koyeb documents the project-directory archive workflow and says the named App/Service can be created or updated by this command. The first successful deployment creates the App/Service; later runs replace it with a new archive. The workflow passes runtime variables explicitly.

First-time setup exact steps:
1. Koyeb Dashboard → Account → API access tokens → Create token. Store it as GitHub Actions secret `KOYEB_TOKEN`.
2. GitHub repository → Settings → Secrets and variables → Actions → Variables → add `KOYEB_APP=elephant-trading`, `KOYEB_SERVICE=web`, and `PRODUCTION_BASE_URL` (use the eventual `https://<service>.koyeb.app` URL).
3. GitHub Actions Secrets → add `DATABASE_URL_DIRECT`, `DATABASE_URL_POOLED`, `SECRET_KEY`, `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `CRON_TOKEN`, `RESEND_API_KEY`, `RESEND_FROM`, `ADMIN_ALERT_EMAIL`, `GRIEVANCE_EMAIL`, and `KOYEB_TOKEN`. Never put these in source or chat.
4. First deploy is triggered by pushing `main` or selecting Actions → Deploy Koyeb → Run workflow. It runs Neon migrations first. If migrations pass, the CLI archive upload creates/deploys `elephant-trading/web` from the Dockerfile.
5. Koyeb Dashboard → Apps → `elephant-trading` → Service `web` → Settings. Confirm no Git repository is connected. Confirm exposed HTTP port `8000`, route `/`, and health check `/health` on port `8000`. No Autodeploy checkbox is relevant because this service has no Git source.
6. Koyeb Dashboard → service → Deployments/Logs; verify the deployment becomes healthy and `/health` returns HTTP 200.

CLI docs: https://www.koyeb.com/docs/build-and-deploy/deploy-project-directory and https://www.koyeb.com/docs/build-and-deploy/cli/reference.

### Neon pooled URL and Psycopg 3

Use the Neon pooled connection string only for application runtime (`DATABASE_URL_POOLED`). The app sets Psycopg 3 `prepare_threshold=None` on this pooled engine. Psycopg 3 defaults to preparing a statement after five executions. Neon documents PgBouncer 1.22 protocol-level prepared-statement support; Psycopg documents that pooled prepared statements require a compatible PgBouncer (1.22+), `max_prepared_statements > 0`, and compatible libpq (17+ for full deallocation support). This deployment pins Psycopg 3.2.3 and does not assert the remote pooler/libpq capability, so it conservatively disables automatic preparation on the pooled application engine. The direct Neon URL remains for Alembic migrations and backup tasks.

### Follow-up scheduler freeze

The GitHub scheduled trigger is removed. The internal endpoint returns HTTP 503 unless `FOLLOWUPS_ENABLED=true`; the deployment workflow explicitly sets it to false until unsubscribe, opt-out enforcement, retry/backoff and idempotency are fully implemented and tested. Keep `CUSTOMER_EMAILS_ENABLED=false`.

### Smoke modes

- CI: `compose.ci.yml` starts PostgreSQL and the app; Cloudflare's published dummy sitekey/secret pair validates the dummy token for the complete disposable buyer-submit/duplicate/dashboard/cleanup/lockout/login/logout cycle. Never use these keys in production.
- Production: read-only smoke checks health, public pages, missing-token fail-closed, admin login/dashboard/logout. It does not create or delete production leads. `SMOKE_ADMIN_USERNAME` and `SMOKE_ADMIN_PASSWORD` are mandatory.


## v1.3.1 targeted hardening

- **Koyeb client IP:** Koyeb documents that it appends the IP address that connected to Koyeb to the right end of `X-Forwarded-For`; it states the last IP is the only one it can certify. With `TRUST_KOYEB_PROXY=true` (set only by the archive deployment workflow), the app parses all XFF values and uses only the rightmost valid IP. All preceding values are treated as untrusted and ignored. If the rightmost value is malformed, the app falls back to the ASGI peer. Without the explicit trust flag, all XFF headers are ignored. Source: https://www.koyeb.com/docs/reference/edge-network.
- **Lockout:** the rate-limit key is `login:<trusted-client-ip>:<normalized-username>`. Users behind a shared proxy are separated by username; forged left-side XFF values cannot change the IP bucket.
- **Smoke cleanup:** `SMOKE_CLEANUP_ENABLED=false` is the production default and is set false on every deployment. The production smoke script is read-only. Enable cleanup only in a disposable CI/test environment; endpoint still requires admin session, CSRF, valid run ID and exact `SMOKE-TEST` plus run-specific email marker.
- **Turnstile startup guard:** production startup rejects either Cloudflare dummy test key. Never copy dummy keys to Koyeb runtime settings.
- **No Git-connected Koyeb service:** GitHub Actions uploads the project directory as a Koyeb archive using the official CLI; the service is created/updated by `koyeb deploy`, not connected to a Git provider.
