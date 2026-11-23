# Elephant Trading v1.3 Manifest

File count: **59** (including this manifest)

Compared with v1.2 ZIP (51 files): 8 added, 14 modified, 0 removed.

## Added
- `.github/dependabot.yml`
- `KNOWN_RISKS_OWASP.md`
- `SANDBOX_TEST_LOGS.txt`
- `V1_3_STATUS_REPORT.md`
- `requirements-runtime.txt`
- `scripts/audit_routes.py`
- `tests/test_postgres.py`
- `V1_3_MANIFEST.md` (this file)

## Modified
- `.github/workflows/backup.yml`
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`
- `.github/workflows/smoke.yml`
- `Dockerfile`
- `SETUP_SECRETS.md`
- `app/mailer.py`
- `app/main.py`
- `app/templates/admin.html`
- `app/templates/base.html`
- `app/templates/form.html`
- `scripts/smoke_test.py`
- `tests/test_app.py`
- `tests/test_unit.py`

## Removed
- None

## Complete file tree
- `.env.example`
- `.github/dependabot.yml`
- `.github/workflows/backup.yml`
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`
- `.github/workflows/followups.yml`
- `.github/workflows/smoke.yml`
- `.gitignore`
- `BLOCKED_AND_HUMAN_GATES.md`
- `Dockerfile`
- `GO_TO_MARKET_14_DAYS.md`
- `KNOWN_RISKS_OWASP.md`
- `OUTREACH_TEMPLATES.md`
- `README.md`
- `SANDBOX_TEST_LOGS.txt`
- `SETUP_SECRETS.md`
- `TEST_REPORT.md`
- `V1_3_MANIFEST.md`
- `V1_3_STATUS_REPORT.md`
- `alembic.ini`
- `app/__init__.py`
- `app/agreements.py`
- `app/db.py`
- `app/mailer.py`
- `app/main.py`
- `app/matching.py`
- `app/models.py`
- `app/rate_limit.py`
- `app/security.py`
- `app/static/site.css`
- `app/templates/admin.html`
- `app/templates/base.html`
- `app/templates/form.html`
- `app/templates/login.html`
- `app/templates/matches.html`
- `app/templates/page.html`
- `app/templates/success.html`
- `data/.gitkeep`
- `migrations/README.md`
- `migrations/env.py`
- `migrations/versions/0001_initial.py`
- `migrations/versions/0002_v12_hardening.py`
- `private_uploads/.gitkeep`
- `pyproject.toml`
- `pytest.ini`
- `render.yaml`
- `requirements-runtime.txt`
- `requirements.txt`
- `scripts/__init__.py`
- `scripts/audit_routes.py`
- `scripts/backup_postgres.sh`
- `scripts/create_admin.py`
- `scripts/migrate_sqlite_to_postgres.py`
- `scripts/rotate_admin.py`
- `scripts/send_due_followups.py`
- `scripts/smoke_test.py`
- `tests/test_app.py`
- `tests/test_postgres.py`
- `tests/test_unit.py`

## v1.1/offline pack 52 → v1.2 51 reconciliation

The 52-file offline pack contained 7 Python bytecode cache files and 4 SQLite test databases. All 11 were removed. v1.2 added 10 source/config/workflow files, yielding 52 - 11 + 10 = 51 files. No application source file was removed in that reconciliation.

## Package exclusions

The v1.3 ZIP excludes generated `.db`, `.sqlite*`, `__pycache__`, `.pyc`, `.pytest_cache`, `.env`, `coverage.xml`, `.coverage`, generated PDFs, and dump artifacts. `.env.example` is retained because it contains placeholders only.
