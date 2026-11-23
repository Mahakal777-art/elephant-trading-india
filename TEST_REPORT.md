# Elephant Trading v1.2 — Local test report

Date: 2026-11-19 (environment date supplied to session)

## DONE-VERIFIED — executed in the local sandbox

### Python compilation and AST
```
python -m compileall -q app scripts migrations tests
COMPILEALL_EXIT:0
AST PASS: 20 Python files parsed
```

### Pytest + coverage (SQLite test database)
```
pytest -q --cov=app --cov-report=term --cov-report=xml
........... [100%]
TOTAL 396 statements, 81 missed, 80% coverage
11 passed
Coverage XML written to file coverage.xml
```
Warnings: FastAPI `on_event` and Starlette `TemplateResponse` deprecations; SQLite ResourceWarning during teardown. Fix before framework upgrade.

Covered locally: public pages/health, duplicate buyer enquiry (409), CSRF missing token, Argon2 password roundtrip, IP shared limiter counter on SQLite fallback, admin login IP lockout (429), GSTIN format, Turnstile fail-closed without secret in production mode, quantity normalization, verified-only supplier matching, agreement PDF generation, DPDP request intake.

Important: local test environment used SQLite. This is not PostgreSQL integration proof.

### Alembic offline SQL generation
```
DATABASE_URL_DIRECT='postgresql+psycopg://u:p@localhost/db' alembic upgrade head --sql
ALEMBIC_OFFLINE_SQL_EXIT:0
```
Generated PostgreSQL SQL includes initial tables, v1.2 ALTER TABLE statements, `rate_limits`, `followups`, and alembic version update to `0002_v12_hardening`.

## DONE-UNTESTED — GitHub Actions only

- GitHub CI with PostgreSQL service container, Ruff, Alembic online upgrade, pytest-cov.
- Koyeb deployment after direct-URL migration success.
- Scheduled encrypted backup artifact and restore job.
- Public URL smoke workflow.

## BLOCKED / not executed

- Live Neon migration, actual PostgreSQL contention/upsert test.
- Koyeb deployment and HTTPS smoke.
- Real Turnstile Siteverify challenge.
- Resend real owner inbox delivery (requires verified sender domain).
- Backup from real Neon and recovery to a separate temporary PostgreSQL service.
- Real admin bootstrap against production database.
- Production buyer POST -> row -> admin dashboard end-to-end.
- Production duplicate 409 and lockout with shared Postgres limiter.

Do not treat local SQLite test results as proof of production readiness.
