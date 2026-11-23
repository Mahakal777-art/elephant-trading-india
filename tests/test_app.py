import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test_suite.db")
from fastapi.testclient import TestClient

import pytest

@pytest.fixture(autouse=True)
def reset_test_database():
    from app.db import Base, engine
    from app import models
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_public_pages_and_health(monkeypatch,tmp_path):
    monkeypatch.setenv('SECRET_KEY','unit-test-secret-key-that-is-at-least-32-characters')
    monkeypatch.setenv('APP_ENV','test')
    monkeypatch.setenv('COOKIE_SECURE','false')
    from app.db import Base,engine
    from app import models
    Base.metadata.create_all(engine)
    from app.main import app
    with TestClient(app) as c:
        assert c.get('/health').status_code==200
        for path in ['/','/how-it-works','/about','/contact','/privacy','/terms','/commission-terms','/buyer','/supplier','/robots.txt','/sitemap.xml']:
            assert c.get(path).status_code==200
        assert c.get('/admin/document/1').status_code==401

def test_buyer_duplicate_and_dpdp_request(monkeypatch,tmp_path):
    monkeypatch.setenv('SECRET_KEY','unit-test-secret-key-that-is-at-least-32-characters')
    monkeypatch.setenv('APP_ENV','test')
    monkeypatch.setenv('COOKIE_SECURE','false')
    from app.main import app
    import app.main as main
    monkeypatch.setattr(main,'turnstile_ok',lambda token,ip: True)
    with TestClient(app) as c:
        page=c.get('/buyer'); import re
        token=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
        payload={'csrf':token,'company':'Buyer Co','person':'Test Person','email':'buyer-test@example.com','phone':'9999999999','city':'Pune','state':'Maharashtra','product':'Green Banana Powder','category':'Food Ingredients','quantity':'1 MT','details':'Test enquiry','consent':'yes'}
        assert c.post('/submit/buyer',data=payload).status_code==200
        assert c.post('/submit/buyer',data=payload).status_code==409
        privacy_page=c.get('/privacy')
        privacy_csrf=re.search(r'name=\"csrf\" value=\"([^\"]+)\"',privacy_page.text).group(1)
        assert c.post('/privacy/request',data={'csrf':privacy_csrf,'email':'privacy@example.com','request_type':'access'}).status_code==200

def test_admin_ip_lockout_uses_shared_limiter(tmp_path,monkeypatch):
    monkeypatch.setenv('SECRET_KEY','unit-test-secret-key-that-is-at-least-32-characters')
    monkeypatch.setenv('APP_ENV','test')
    monkeypatch.setenv('COOKIE_SECURE','false')
    from app.db import Base,engine,SessionLocal
    from app.models import Admin
    from app.security import hash_password
    from app.main import app
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        row=db.query(Admin).filter_by(username='lockout-ci').first()
        if not row: db.add(Admin(username='lockout-ci',password_hash=hash_password('correct-password-123'))); db.commit()
    with TestClient(app) as c:
        import re
        csrf=re.search(r'name="csrf" value="([^"]+)"',c.get('/admin/login').text).group(1)
        for _ in range(5):
            assert c.post('/admin/login',data={'username':'lockout-ci','password':'wrong','csrf':csrf}).status_code==401
        assert c.post('/admin/login',data={'username':'lockout-ci','password':'wrong','csrf':csrf}).status_code==429


def test_all_admin_and_internal_routes_require_auth(monkeypatch,tmp_path):
    monkeypatch.setenv("SECRET_KEY","unit-test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setenv("APP_ENV","test")
    monkeypatch.setenv("COOKIE_SECURE","false")
    from app.db import Base,engine
    from app import models
    Base.metadata.create_all(engine)
    from app.main import app
    protected=[]
    for route in app.routes:
        path=getattr(route,"path","")
        if (path.startswith("/admin") and path not in {"/admin/login"}) or path.startswith("/internal"):
            for method in (getattr(route,"methods",set()) or set()) - {"HEAD","OPTIONS"}: protected.append((method,path))
    assert protected
    with TestClient(app) as c:
        for method,path in protected:
            if "{" in path: path=path.replace("{lead_id}","999999").replace("{buyer_id}","999999").replace("{deal_id}","999999")
            if method=="GET": r=c.get(path,follow_redirects=False)
            else: r=c.post(path,follow_redirects=False)
            assert r.status_code in (302,303,401,403,404,422,429), (method,path,r.status_code)
        assert c.post("/internal/run-followups",headers={"Authorization":"Bearer wrong"}).status_code==401
        assert c.post("/internal/run-followups").status_code==401


def test_jinja_autoescape_and_script_text_escaped():
    from app.main import templates
    rendered=templates.env.from_string("{{ value }}").render(value="<script>alert(1)</script>")
    assert "&lt;script&gt;" in rendered and "<script>" not in rendered

def test_admin_workflow_export_match_agreement_and_cleanup(monkeypatch):
    monkeypatch.setenv("SMOKE_CLEANUP_ENABLED", "true")
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    from app.db import Base, engine, SessionLocal
    from app.models import Admin, Lead
    from app.security import hash_password
    from app.main import app
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        admin_row=db.query(Admin).filter_by(username="workflow-admin").first()
        if not admin_row:
            db.add(Admin(username="workflow-admin", password_hash=hash_password("Good-password-123!"))); db.commit()
        buyer=Lead(kind="buyer",company="Workflow Buyer",person="Buyer",email="workflow-buyer@example.com",phone="1",city="Pune",state="Maharashtra",product="Turmeric",category="Spices & Agro Products",quantity="1 MT",details="Need turmeric",consent=True)
        supplier=Lead(kind="supplier",company="Workflow Supplier",person="Seller",email="workflow-supplier@example.com",phone="2",city="Pune",state="Maharashtra",product="Turmeric",category="Spices & Agro Products",gstin="27ABCDE1234F1Z5",capacity="2 MT",moq="100 kg",indicative_price="100 INR/kg",verification="Verified",consent=True)
        smoke=Lead(kind="buyer",company="SMOKE-TEST",person="Smoke",email="smoke+12345678-abcd@invalid.test",phone="0",city="Pune",state="Maharashtra",product="Smoke",category="Food Ingredients",consent=True)
        db.add_all([buyer,supplier,smoke]); db.commit(); buyer_id=buyer.id; supplier_id=supplier.id
    import re
    with TestClient(app) as c:
        csrf=re.search(r'name="csrf" value="([^"]+)"',c.get("/admin/login").text).group(1)
        assert c.post("/admin/login",data={"username":"workflow-admin","password":"Good-password-123!","csrf":csrf},follow_redirects=False).status_code==303
        page=c.get("/admin"); assert page.status_code==200
        assert "SMOKE-TEST" not in page.text
        csrf=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
        assert c.get("/admin/export.csv").status_code==200
        assert c.get(f"/admin/matches/{buyer_id}").status_code==200
        assert c.post(f"/admin/lead/{supplier_id}/status",data={"csrf":csrf,"status":"Verified","verification":"Verified"},follow_redirects=False).status_code==303
        deal=c.post("/admin/deal",data={"csrf":csrf,"buyer_id":buyer_id,"supplier_id":supplier_id,"product":"Turmeric","deal_value":"10000","commission_pct":"5","payment_terms":"On delivery","jurisdiction":"Maharashtra, India"},follow_redirects=False)
        assert deal.status_code==303
        from app.models import Deal
        with SessionLocal() as db: deal_id=db.query(Deal).order_by(Deal.id.desc()).first().id
        assert c.get(f"/admin/agreement/{deal_id}").status_code==200
        cleanup=c.post("/admin/smoke-cleanup",data={"csrf":csrf,"run_id":"12345678-abcd"})
        assert cleanup.status_code==200 and cleanup.json()=={"deleted":1,"remaining":False}
        with SessionLocal() as db: assert db.query(Lead).filter_by(email="smoke+12345678-abcd@invalid.test").count()==0
        assert c.post("/admin/logout",data={"csrf":csrf},follow_redirects=False).status_code==303

def test_admin_alert_failure_is_logged_without_raising(monkeypatch):
    from app.db import SessionLocal
    from app.models import Activity
    import app.main as main
    def fail(*args, **kwargs): raise RuntimeError("simulated Resend outage")
    monkeypatch.setattr(main, "send_admin_alert", fail)
    main.deliver_admin_alert(123, "buyer", "Company", "Product", "Pune", "Maharashtra", "x@example.com", "")
    with SessionLocal() as db:
        event=db.query(Activity).filter_by(lead_id=123,event="Admin alert failed").first()
        assert event is not None and "RuntimeError" in event.note


def test_csv_export_neutralizes_formula_payloads(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    from app.db import Base, engine, SessionLocal
    from app.models import Admin, Lead
    from app.security import hash_password
    from app.main import app
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.query(Admin).filter_by(username="csv-admin").first():
            db.add(Admin(username="csv-admin", password_hash=hash_password("Csv-password-123!")))
        db.add(Lead(kind="buyer", company="=HYPERLINK(\"https://evil.test\")", person="+cmd|' /C calc'!A0", email="csv-test@example.com", phone="-1+2", city="Pune", state="Maharashtra", product="@SUM(1,1)", category="Food Ingredients", consent=True))
        db.commit()
    import re, csv, io
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        token=re.search(r'name="csrf" value="([^"]+)"',c.get("/admin/login").text).group(1)
        assert c.post("/admin/login",data={"username":"csv-admin","password":"Csv-password-123!","csrf":token},follow_redirects=False).status_code==303
        body=c.get("/admin/export.csv").text
        rows=list(csv.DictReader(io.StringIO(body)))
        row=next(x for x in rows if x["email"]=="csv-test@example.com")
        assert row["company"].startswith("'=")
        assert row["person"].startswith("'+")
        assert row["phone"].startswith("'-")
        assert row["product"].startswith("'@")


def test_login_rate_limit_is_scoped_by_ip_and_username(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    from fastapi.testclient import TestClient
    from app.main import app
    import re
    with TestClient(app) as c:
        token=re.search(r'name="csrf" value="([^"]+)"',c.get("/admin/login").text).group(1)
        for _ in range(5):
            assert c.post("/admin/login",data={"username":"nonexistent-a","password":"wrong","csrf":token}).status_code==401
        assert c.post("/admin/login",data={"username":"nonexistent-a","password":"wrong","csrf":token}).status_code==429
        # A different username from the same source IP gets its own counter.
        assert c.post("/admin/login",data={"username":"nonexistent-b","password":"wrong","csrf":token}).status_code==401


def test_smoke_cleanup_requires_admin_csrf_and_exact_marker(monkeypatch):
    monkeypatch.setenv("SMOKE_CLEANUP_ENABLED", "true")
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import Base, engine, SessionLocal
    from app.models import Admin, Lead
    from app.security import hash_password
    import re
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.query(Admin).filter_by(username="cleanup-admin").first():
            db.add(Admin(username="cleanup-admin",password_hash=hash_password("Cleanup-password-123!")))
        db.add_all([
            Lead(kind="buyer",company="SMOKE-TEST",person="Smoke",email="smoke+negative-runid@invalid.test",phone="1",city="Pune",state="Maharashtra",product="Smoke",category="Food Ingredients",consent=True),
            Lead(kind="buyer",company="REAL-COMPANY",person="Real",email="smoke+negative-runid@invalid.test",phone="2",city="Pune",state="Maharashtra",product="Real Product",category="Food Ingredients",consent=True),
        ])
        db.commit()
    with TestClient(app) as c:
        assert c.post("/admin/smoke-cleanup",data={"run_id":"negative-runid"}).status_code==401
        token=re.search(r'name="csrf" value="([^"]+)"',c.get("/admin/login").text).group(1)
        assert c.post("/admin/login",data={"username":"cleanup-admin","password":"Cleanup-password-123!","csrf":token},follow_redirects=False).status_code==303
        assert c.post("/admin/smoke-cleanup",data={"run_id":"negative-runid"}).status_code==403
        page=c.get("/admin"); token=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
        assert c.post("/admin/smoke-cleanup",data={"csrf":token,"run_id":"negative-runid"}).json()=={"deleted":1,"remaining":False}
        with SessionLocal() as db:
            assert db.query(Lead).filter_by(company="SMOKE-TEST",email="smoke+negative-runid@invalid.test").count()==0
            assert db.query(Lead).filter_by(company="REAL-COMPANY",email="smoke+negative-runid@invalid.test").count()==1


def test_followup_scheduler_disabled_by_default(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CRON_TOKEN", "cron-test-token")
    monkeypatch.delenv("FOLLOWUPS_ENABLED", raising=False)
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        response=c.post("/internal/run-followups",headers={"Authorization":"Bearer cron-test-token"})
        assert response.status_code==503


def test_all_admin_post_routes_reject_missing_csrf(monkeypatch):
    """Enumerate every admin POST route and prove missing CSRF is rejected."""
    monkeypatch.setenv("SMOKE_CLEANUP_ENABLED", "true")
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    from fastapi.testclient import TestClient
    from app.main import app
    import re
    from app.db import Base, engine, SessionLocal
    from app.models import Admin
    from app.security import hash_password
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.query(Admin).filter_by(username="csrf-admin").first():
            db.add(Admin(username="csrf-admin",password_hash=hash_password("Csrf-password-123!"))); db.commit()
    routes=[]
    for route in app.routes:
        path=getattr(route,"path","")
        methods=getattr(route,"methods",set()) or set()
        if path.startswith("/admin") and "POST" in methods:
            routes.append(route)
    assert routes
    defaults={"username":"csrf-admin","password":"Csrf-password-123!","status":"New","verification":"Pending","buyer_id":"999999","supplier_id":"999999","product":"test","deal_value":"1","commission_pct":"1","payment_terms":"test","received":"1","run_id":"12345678","jurisdiction":"Maharashtra, India"}
    with TestClient(app) as c:
        login_page=c.get("/admin/login")
        token=re.search(r'name="csrf" value="([^"]+)"',login_page.text).group(1)
        assert c.post("/admin/login",data={"username":"csrf-admin","password":"Csrf-password-123!"}).status_code==403
        assert c.post("/admin/login",data={"username":"csrf-admin","password":"Csrf-password-123!","csrf":token},follow_redirects=False).status_code==303
        checked=[]
        for route in routes:
            path=route.path
            for name in re.findall(r"{([^}:]+)(?::[^}]+)?}",path):
                path=path.replace("{"+name+"}","999999")
            data={}
            for field in getattr(route.dependant,"body_params",[]):
                if field.name=="csrf":
                    continue
                data[field.name]=defaults.get(field.name,"1")
            response=c.post(path,data=data,follow_redirects=False)
            assert response.status_code==403,(route.path,response.status_code,response.text)
            checked.append(route.path)
        assert len(checked)==len(routes), (checked,len(routes))


def test_smoke_cleanup_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SMOKE_CLEANUP_ENABLED", raising=False)
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setenv("APP_ENV", "test")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        assert c.post("/admin/smoke-cleanup", data={"run_id":"12345678"}).status_code==404


@pytest.mark.parametrize(("site_key", "secret_key"), [
    ("1x00000000000000000000AA", "real-looking-not-dummy-secret"),
    ("real-looking-site-key", "1x0000000000000000000000000000000AA"),
])
def test_production_startup_rejects_either_cloudflare_dummy_turnstile_key(monkeypatch,site_key,secret_key):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setenv("TURNSTILE_SITE_KEY", site_key)
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", secret_key)
    from app.main import startup
    with pytest.raises(RuntimeError, match="dummy Turnstile keys"):
        startup()


def test_koyeb_xff_uses_only_rightmost_appended_client_ip_and_ignores_spoof(monkeypatch):
    monkeypatch.setenv("TRUST_KOYEB_PROXY", "true")
    from starlette.requests import Request
    from app.main import client_ip
    scope={"type":"http","method":"GET","path":"/","headers":[(b"x-forwarded-for",b"198.51.100.77, 203.0.113.25")],"client":("10.0.0.8",1234),"server":("test",80),"scheme":"http","query_string":b""}
    assert client_ip(Request(scope))=="203.0.113.25"
    scope["headers"]=[(b"x-forwarded-for",b"198.51.100.77, forged-value")]
    assert client_ip(Request(scope))=="10.0.0.8"


def test_shared_koyeb_proxy_ip_lockout_isolated_by_username(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("TRUST_KOYEB_PROXY", "true")
    from fastapi.testclient import TestClient
    from app.main import app
    import re
    with TestClient(app) as c:
        token=re.search(r'name="csrf" value="([^\"]+)"',c.get('/admin/login').text).group(1)
        for i in range(5):
            r=c.post('/admin/login',headers={"X-Forwarded-For":f"198.51.100.{i}, 203.0.113.25"},data={"username":"missing-one","password":"bad","csrf":token})
            assert r.status_code==401
        r=c.post('/admin/login',headers={"X-Forwarded-For":"192.0.2.44, 203.0.113.25"},data={"username":"missing-one","password":"bad","csrf":token})
        assert r.status_code==429
        r=c.post('/admin/login',headers={"X-Forwarded-For":"198.51.100.77, 203.0.113.25"},data={"username":"missing-two","password":"bad","csrf":token})
        assert r.status_code==401


def test_privacy_request_requires_csrf_and_does_not_store_raw_email(monkeypatch):
    import re
    from fastapi.testclient import TestClient
    from app.db import Base, engine, SessionLocal
    from app.models import Activity
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    Base.metadata.create_all(engine)
    from app.main import app
    with TestClient(app) as client:
        assert client.post("/privacy/request", data={"email":"private@example.com", "request_type":"access"}).status_code == 403
        token=re.search(r'name="csrf" value="([^"]+)"', client.get("/privacy").text).group(1)
        assert client.post("/privacy/request", data={"csrf":token,"email":"private@example.com", "request_type":"access"}).status_code == 200
    with SessionLocal() as db:
        row=db.query(Activity).filter_by(event="Privacy request").order_by(Activity.id.desc()).first()
        assert row is not None
        assert "private@example.com" not in row.note
        assert "requester_ref=" in row.note


def test_successful_login_does_not_consume_failed_attempt_budget(monkeypatch):
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
        db.add(Admin(username="success-budget",password_hash=hash_password("Correct-Password-123!")))
        db.commit()
    from app.main import app
    with TestClient(app) as client:
        csrf=re.search(r'name="csrf" value="([^"]+)"',client.get("/admin/login").text).group(1)
        for _ in range(4):
            assert client.post("/admin/login",data={"username":"success-budget","password":"bad","csrf":csrf}).status_code == 401
        assert client.post("/admin/login",data={"username":"success-budget","password":"Correct-Password-123!","csrf":csrf},follow_redirects=False).status_code == 303
        admin_page=client.get("/admin")
        csrf=re.search(r'name="csrf" value="([^"]+)"',admin_page.text).group(1)
        client.post("/admin/logout",data={"csrf":csrf},follow_redirects=False)
        csrf=re.search(r'name="csrf" value="([^"]+)"',client.get("/admin/login").text).group(1)
        assert client.post("/admin/login",data={"username":"success-budget","password":"bad","csrf":csrf}).status_code == 401


def test_invalid_cron_tokens_do_not_consume_authenticated_rate_budget(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CRON_TOKEN", "valid-cron-token-for-test")
    monkeypatch.setenv("FOLLOWUPS_ENABLED", "false")
    from app.main import app
    with TestClient(app) as client:
        for _ in range(12):
            assert client.post("/internal/run-followups",headers={"Authorization":"Bearer wrong"}).status_code == 401
        assert client.post("/internal/run-followups",headers={"Authorization":"Bearer valid-cron-token-for-test"}).status_code == 503
