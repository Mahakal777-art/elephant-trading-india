# Elephant Trading — India Domestic B2B Marketplace

Commission intermediary only. Buyer and supplier contract, invoice, deliver and settle directly. Elephant Trading does not hold, manufacture, buy or resell goods.

## Local run
1. Python 3.12+
2. `python -m venv .venv && source .venv/bin/activate` (Windows: `.venv\\Scripts\\activate`)
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env`; set `SECRET_KEY` to `python -c "import secrets; print(secrets.token_urlsafe(48))"`
5. Set `DATABASE_URL=sqlite:///./data/elephant_dev.db` for local only.
6. `python scripts/create_admin.py`
7. `uvicorn app.main:app --reload`
8. Open `http://127.0.0.1:8000`; admin `/admin/login`.

## Production architecture
- Render web service (free tier for preview only) + Neon PostgreSQL.
- Neon Free (checked Nov 2026): 1 GB/project, 100 CU-hours/project/month, 5 GB public transfer; scale-to-zero after 5 minutes. Free compute can suspend at quota. It is not a high-availability production SLA.
- Render Free web service sleeps after 15 minutes idle, cold starts about 1 minute, ephemeral filesystem; Free Postgres expires after 30 days. Do not use Render Postgres for durable production data.
- Cloudflare Turnstile Free: up to 20 widgets, unlimited challenge requests (subject to current plan terms).
- For reliable business use, budget for always-on app hosting, managed DB backups, object storage and monitoring; free tiers are launch/testing only.

## Deploy (preview)
1. Push this folder to a private GitHub repo.
2. Create Neon project, copy pooled PostgreSQL connection string; set `DATABASE_URL` secret on Render.
3. Render Dashboard → New → Blueprint → connect repo → review `render.yaml`.
4. Set secrets: `DATABASE_URL`, `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `GMAIL_*` if configured. Render will generate `SECRET_KEY`.
5. Add Turnstile hostname for the Render subdomain; use its keys.
6. Deploy. Visit `/health`, `/`, `/admin/login`.
7. Run `python scripts/create_admin.py` via a secure one-off shell/SSH job. Render Free does not provide shell; use a local trusted machine with `DATABASE_URL` and run it once.
8. Never expose admin endpoints until bootstrap admin exists and auth tested.

## Gmail
Use Gmail API OAuth, not SMTP app passwords. Create Google Cloud project → enable Gmail API → configure OAuth consent → create Web application OAuth client → redirect URI must be implemented and registered before use. The current Gmail send module is a library helper; OAuth callback/token persistence and automatic sending remain UNTESTED/not wired. Do not grant Gmail access until this is implemented and reviewed.

## Legal and privacy
Draft pages are DPDP-aware but not legal advice. Indian lawyer review is mandatory before accepting public enquiries. Publish verified legal entity details, grievance contact, retention/deletion workflow and lawful processing basis. Supplier documents are private; configure durable private object storage before relying on uploads.

## Tests / known limitations
See `TEST_REPORT.md`. No live deployment, DNS, Gmail OAuth, Turnstile, real Neon database or third-party email delivery has been performed in this environment.

## Backups
`bash scripts/backup_postgres.sh` creates a custom-format `pg_dump` file. This is a manual helper, not automated off-site backup. Encrypt and upload backups to a separate storage account; schedule it and test restore before production launch.

## Operational limitations
Admin login lockout is stored in PostgreSQL, but public form rate limiting is process-local and should be moved to a shared Redis-compatible store before horizontal scaling. Uploads are local/private and must be migrated to malware-scanned private object storage before production.

## Updated provider decisions (checked 19 Nov 2026)
- Database: Neon Free for test/initial low-volume stage (0.5 GB/project, 100 CU-hours/project, 5 GB egress). It can suspend at quota; keep DB external to web host.
- App hosting: no verified always-on free tier suitable for production found. Render/Koyeb free plans sleep/scale to zero; Fly Machines are metered (shared-cpu-1x 256MB about $2.19/month before storage/egress). A reliable always-on deployment needs a paid host and account credentials.
- Private documents: Cloudflare R2 free allowance 10 GB-month, 1m Class A, 10m Class B requests, no egress. Upload scanning still required before showing files.
- Bot protection: Cloudflare Turnstile Free supports up to 20 widgets and unlimited challenge verifications.
- Transactional mail: Resend Free 3,000 emails/month, 100/day. Verify sending domain; include opt-out for non-transactional reminders and suppress bounces/unsubscribes. Avoid Gmail OAuth Testing mode for scheduled automated sends.
- CI: GitHub Actions workflow included; execution waits for repo push and GitHub Actions enabled.

## v1.2 architecture changes
- Public supplier document uploads are disabled by default (`UPLOADS_ENABLED=false`); documents are collected manually outside the application. Do not enable upload routes in v1.2.
- Admin-only enquiry alerts use Resend. Customer-facing email and follow-up delivery remain disabled (`CUSTOMER_EMAILS_ENABLED=false`). Resend's `onboarding@resend.dev` is a test sender for `delivered@resend.dev`, not a general owner inbox sender; verify a domain for real admin alerts.
- Postgres-backed shared rate-limit table added. Neon runtime should use pooled URL; Alembic migrations and backups use direct URL.
- GitHub Actions are the executor. CI, deploy, smoke and encrypted backup/restore workflows are included. They are UNTESTED until pushed and executed in GitHub.
- Koyeb Free web services scale to zero after one hour idle and are not recommended for production; paid Eco-Micro is listed at $2.68/month in Singapore (before taxes/additional usage). See official docs in the final report.

## Verified current pricing snapshot (19 Nov 2026)
- Neon Free: 100 projects; 100 CU-hours/project/month; 1 GB storage/project; 5 GB public network transfer/project/month; compute scales to zero after 5 minutes. Appropriate for low-volume pilot, not an always-on database guarantee.
- Koyeb Eco Micro: $2.68/month published rate, 0.25 vCPU, 512 MB RAM, 4 GB SSD; Eco regions include Singapore. Free Koyeb web instance sleeps after 1 hour idle and Koyeb explicitly says free instances are for hobby/testing, not production.
- Resend Free: 3,000 emails/month, 100/day. `onboarding@resend.dev` sample sender is documented for `delivered@resend.dev` test recipient; real owner notifications require a verified sending domain.


## Security/configuration notes (v1.3.1 review patch)

- Set `SECRET_KEY`, `APP_ENV`, and `COOKIE_SECURE` before the ASGI application receives its first request. Session middleware reads these settings lazily at first ASGI invocation, rather than at Python module import. Do not mutate these settings after startup.
- The active-lead duplicate key is enforced by a partial unique database index on `(kind, email, product)` for rows whose status is not `Closed-Lost`. Migration `0003_active_lead_dedup` intentionally fails if legacy active duplicates exist; reconcile those records manually before retrying.
- Privacy-request activity notes store a keyed requester reference, not the raw email address. Activity records currently have no automated erasure job; proposed operational retention is 365 days, subject to legal/accounting holds and lawyer approval. Until a retention job is deployed, operators must review and purge eligible records through an approved maintenance process.
- City matching is an alternative to state matching (not additive) to avoid double-counting the location factor. Null legacy category/product values are treated as empty strings.

- The production backup workflow also normalizes SQLAlchemy driver-qualified PostgreSQL URLs and supplies the GPG passphrase through stdin rather than exposing it in process arguments.
