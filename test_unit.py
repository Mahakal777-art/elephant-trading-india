from pathlib import Path
from app.security import hash_password, verify_password, safe_gstin, check_csrf
from fastapi import HTTPException

def test_argon2_password_roundtrip():
    h=hash_password('test-password-strong-123')
    assert h!='test-password-strong-123'
    assert verify_password(h,'test-password-strong-123')
    assert not verify_password(h,'wrong')

def test_gstin_format():
    assert safe_gstin('27ABCDE1234F1Z5')
    assert not safe_gstin('INVALID')

def test_csrf_rejects_missing_token():
    class Req: session={'csrf':'expected'}
    try: check_csrf(Req(),None)
    except HTTPException as exc: assert exc.status_code==403
    else: raise AssertionError('CSRF missing token accepted')

def test_quantity_normalization():
    from app.matching import normalize_quantity
    assert normalize_quantity('2 MT')==2000
    assert normalize_quantity('5 quintal')==500
    assert normalize_quantity('250 kg')==250

def test_postgres_shared_limiter_counter_on_sqlite_fallback():
    from app.db import Base,engine
    from app import models
    from app.rate_limit import allow
    Base.metadata.create_all(engine)
    import uuid
    key='pytest:'+uuid.uuid4().hex
    assert allow(key,2,60) is True
    assert allow(key,2,60) is True
    assert allow(key,2,60) is False

def test_turnstile_fails_closed_without_secret(monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.delenv('TURNSTILE_SECRET_KEY',raising=False)
    from app.main import turnstile_ok
    assert turnstile_ok('', '127.0.0.1') is False

def test_pdf_agreement_generates(tmp_path):
    from app.agreements import make_agreement
    p=tmp_path/'agreement.pdf'
    make_agreement(p,'Test Buyer','buyer','Green Banana Powder',100000,2,'Advance','Maharashtra, India')
    assert p.exists() and p.stat().st_size>500 and p.read_bytes().startswith(b'%PDF')

def test_match_only_verified_suppliers(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db import Base
    from app.models import Lead
    from app.matching import score_matches
    e=create_engine(f"sqlite:///{tmp_path/'match.db'}")
    Base.metadata.create_all(e); S=sessionmaker(bind=e)
    with S() as db:
        buyer=Lead(kind='buyer',company='B',person='P',email='b@x.com',phone='1',city='Pune',state='Maharashtra',product='Green Banana Powder',category='Food Ingredients',quantity='1 MT')
        pending=Lead(kind='supplier',company='S1',person='P',email='s1@x.com',phone='1',city='Pune',state='Maharashtra',product='Green Banana Powder',category='Food Ingredients',verification='Pending')
        verified=Lead(kind='supplier',company='S2',person='P',email='s2@x.com',phone='1',city='Pune',state='Maharashtra',product='Green Banana Powder',category='Food Ingredients',capacity='2 MT',moq='100 kg',verification='Verified')
        db.add_all([buyer,pending,verified]); db.commit()
        found=score_matches(db,buyer)
        assert len(found)==1 and found[0]['supplier'].company=='S2'


def test_business_url_validation_and_reject_unsafe():
    from app.main import validate_business_url
    from fastapi import HTTPException
    assert validate_business_url("HTTPS://Example.COM/path") == "https://example.com/path"
    for value in ["javascript:alert(1)", "data:text/html,<script>", "http://127.0.0.1", "http://localhost", "https://user:pass@example.com"]:
        try: validate_business_url(value)
        except HTTPException as exc: assert exc.status_code == 422
        else: raise AssertionError(f"unsafe URL accepted: {value}")


def test_pooled_url_detection_uses_selected_env_variable():
    from app.db import database_configuration
    url, args, pooled = database_configuration({
        "DATABASE_URL_POOLED": "postgresql://user:pass@host/db?sslmode=require",
        "DATABASE_URL": "postgresql://direct/db",
    })
    assert url.startswith("postgresql+psycopg://")
    assert pooled is True
    assert args["prepare_threshold"] is None
    direct_url, direct_args, direct_pooled = database_configuration({"DATABASE_URL": "postgresql://direct/db"})
    assert direct_url.startswith("postgresql+psycopg://")
    assert direct_pooled is False
    assert "prepare_threshold" not in direct_args


def test_agreement_escapes_untrusted_reportlab_text(tmp_path):
    from app.agreements import make_agreement
    path=tmp_path/"escaped.pdf"
    make_agreement(path, "Buyer <script>& Co", "buyer & supplier", "<b>Unsafe</b> & product", 1000, 2, "<img src='x'/> & advance", "Maharashtra <India>")
    assert path.read_bytes().startswith(b"%PDF")


def test_legacy_naive_locked_until_does_not_500(monkeypatch):
    import re
    from fastapi.testclient import TestClient
    from app.db import Base, engine, SessionLocal
    from app.models import Admin
    from app.security import hash_password
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Admin(username="legacy-naive",password_hash=hash_password("pw-strong-123456"),locked_until="2026-01-01T00:00:00"))
        db.commit()
    from app.main import app
    with TestClient(app) as client:
        csrf=re.search(r'name="csrf" value="([^"]+)"',client.get("/admin/login").text).group(1)
        response=client.post("/admin/login",data={"username":"legacy-naive","password":"wrong","csrf":csrf})
        assert response.status_code in (401,429)


def test_lead_active_duplicate_is_database_unique(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.exc import IntegrityError
    from app.db import Base
    from app.models import Lead
    engine=create_engine(f"sqlite:///{tmp_path/'unique-leads.db'}")
    Base.metadata.create_all(engine)
    S=sessionmaker(bind=engine)
    values=dict(kind="buyer",company="Buyer",person="Person",email="dupe@example.com",phone="1",city="Pune",state="MH",product="Rice",category="Food")
    with S() as db:
        db.add(Lead(**values)); db.commit()
        db.add(Lead(**values))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("database accepted duplicate active lead")
    engine.dispose()


def test_backup_script_strips_sqlalchemy_driver_and_uses_passphrase_fd(tmp_path):
    import os, subprocess
    bindir=tmp_path/"bin"; bindir.mkdir()
    pg_args=tmp_path/"pg-args"; gpg_args=tmp_path/"gpg-args"
    (bindir/"pg_dump").write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$PG_DUMP_ARGS_FILE\"\nfor arg in \"$@\"; do case \"$arg\" in --file=*) touch \"${arg#--file=}\";; esac; done\n")
    (bindir/"gpg").write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$GPG_ARGS_FILE\"\nwhile [ $# -gt 0 ]; do case \"$1\" in --output) shift; touch \"$1\";; esac; shift; done\n")
    (bindir/"shred").write_text("#!/bin/sh\nrm -f \"$2\"\n")
    for item in bindir.iterdir(): item.chmod(0o755)
    env=os.environ.copy(); env.update({"PATH":f"{bindir}:{env['PATH']}","DATABASE_URL":"postgresql+psycopg://user:pass@db.example/test","BACKUP_ENCRYPTION_PASSPHRASE":"not-in-process-args","PG_DUMP_ARGS_FILE":str(pg_args),"GPG_ARGS_FILE":str(gpg_args)})
    subprocess.run(["bash",str(Path(__file__).resolve().parents[1]/"scripts/backup_postgres.sh")],env=env,cwd=tmp_path,check=True,capture_output=True,text=True)
    pg_text=pg_args.read_text()
    assert "postgresql://user:pass@db.example/test" in pg_text
    assert "postgresql+psycopg://" not in pg_text
    gpg_text=gpg_args.read_text()
    assert "--passphrase-fd" in gpg_text
    assert "not-in-process-args" not in gpg_text


def test_verify_password_does_not_swallow_unexpected_programming_error(monkeypatch):
    import app.security as security
    def explode(self,*args): raise RuntimeError("unexpected bug")
    monkeypatch.setattr(type(security.ph),"verify",explode)
    try:
        security.verify_password("hash","password")
    except RuntimeError as exc:
        assert str(exc)=="unexpected bug"
    else:
        raise AssertionError("unexpected verifier error was swallowed")



def test_matching_tolerates_legacy_null_category_product_and_city_fallback():
    from types import SimpleNamespace
    from app.matching import score_matches
    buyer=SimpleNamespace(kind="buyer",quantity="",category="Food",product="Rice",state="Maharashtra",city="Pune")
    supplier=SimpleNamespace(kind="supplier",verification="Verified",category=None,product=None,state="Gujarat",city="Pune",capacity="",moq="",indicative_price="")
    class Result:
        def all(self): return [supplier]
    class DB:
        def scalars(self, statement): return Result()
    results=score_matches(DB(),buyer)
    assert len(results)==1
    assert results[0]["score"]==15
    assert "same city +15" in results[0]["reasons"]
