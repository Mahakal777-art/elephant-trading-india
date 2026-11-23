import os
from concurrent.futures import ThreadPoolExecutor
import pytest

URL=os.getenv("DATABASE_URL", "")
pytestmark=pytest.mark.skipif(not URL.startswith(("postgresql", "postgres://")), reason="PostgreSQL integration test requires DATABASE_URL")

def test_postgres_atomic_rate_limiter_concurrent():
    from app.db import SessionLocal
    from app.models import RateLimit
    from app.rate_limit import allow
    key="pytest-concurrent-rate-limit"
    with SessionLocal() as db:
        db.query(RateLimit).filter(RateLimit.key==key).delete(); db.commit()
    with ThreadPoolExecutor(max_workers=5) as pool:
        results=list(pool.map(lambda _: allow(key,100,60), range(80)))
    assert sum(results)==80
    with SessionLocal() as db:
        row=db.get(RateLimit,key)
        assert row is not None and row.hits==80
        db.delete(row); db.commit()


def test_postgres_active_lead_unique_index_enforces_duplicate_protection():
    from sqlalchemy.exc import IntegrityError
    from app.db import SessionLocal
    from app.models import Lead
    values=dict(kind="buyer",company="PG Duplicate Test",person="Test",email="pg-duplicate@example.invalid",phone="1",city="Pune",state="Maharashtra",product="Test Rice",category="Food")
    with SessionLocal() as db:
        db.query(Lead).filter(Lead.email==values["email"]).delete(synchronize_session=False)
        db.commit()
        db.add(Lead(**values)); db.commit()
        db.add(Lead(**values))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("PostgreSQL accepted duplicate active lead")
        db.query(Lead).filter(Lead.email==values["email"]).delete(synchronize_session=False)
        db.commit()
