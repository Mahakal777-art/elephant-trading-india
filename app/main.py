import os,re,secrets,time,logging,ipaddress,hashlib,hmac
from pathlib import Path
from datetime import datetime,timedelta,timezone
from urllib.parse import urlsplit, urlunsplit
from fastapi import FastAPI,Request,Depends,Form,HTTPException,BackgroundTasks
from fastapi.responses import HTMLResponse,RedirectResponse,FileResponse,StreamingResponse,PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from .security import LazySessionMiddleware
from sqlalchemy import select,or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from functools import wraps
import inspect
from .rate_limit import allow
from .mailer import send_admin_alert
from .db import Base,engine,get_db,SessionLocal
from .models import Admin,Lead,Deal,Activity,Followup
from .security import hash_password,verify_password,csrf_token,check_csrf,safe_gstin,signed_serializer
from .matching import score_matches
from .agreements import make_agreement

log=logging.getLogger("elephant.app")
APP=Path(__file__).resolve().parent
UPLOAD=Path(os.getenv("UPLOAD_DIR","./private_uploads")); UPLOAD.mkdir(parents=True,exist_ok=True)
UPLOADS_ENABLED=False  # v1.2 hard-disable; reintroduce only with private object storage + malware scanning
app=FastAPI(title="Elephant Trading India B2B")
app.mount("/static",StaticFiles(directory=str(Path(__file__).resolve().parent/"static")),name="static")
app.add_middleware(LazySessionMiddleware,session_cookie="et_session",max_age=8*3600,same_site="lax")
@app.middleware("http")
async def security_headers(request,call_next):
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"; response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"; response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self' https://challenges.cloudflare.com 'unsafe-inline'; frame-src https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; form-action 'self'; base-uri 'self'; frame-ancestors 'none'"
    if os.getenv("APP_ENV","production")=="production": response.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
    return response
def client_ip(request):
    """Return the security-relevant client IP.

    Koyeb documents that it appends the IP connecting to its edge to the
    rightmost end of X-Forwarded-For. Ignore all client-supplied left-side
    entries and use only that rightmost address when the Koyeb trust switch
    is enabled. Otherwise trust only the ASGI peer address.
    """
    peer=request.client.host if request and request.client else "unknown"
    if os.getenv("TRUST_KOYEB_PROXY", "false").lower() != "true":
        return peer
    values=request.headers.getlist("x-forwarded-for") if request else []
    candidates=[]
    for value in values:
        candidates.extend(part.strip() for part in value.split(","))
    if not candidates:
        return peer
    try:
        return str(ipaddress.ip_address(candidates[-1]))
    except ValueError:
        log.warning("Ignoring malformed rightmost Koyeb X-Forwarded-For value")
        return peer

def rate_limit(rule):
    count,period=rule.split("/"); limit=int(count)
    seconds={"hour":3600,"10minutes":600,"minute":60}.get(period,3600)
    def decorate(fn):
        @wraps(fn)
        async def wrapped(*args,**kwargs):
            bound=inspect.signature(fn).bind_partial(*args,**kwargs); req=bound.arguments.get("request")
            ip=client_ip(req) if req else "unknown"
            identity=bound.arguments.get("username", "") if fn.__name__ == "login" else ""
            identity=re.sub(r"[^a-zA-Z0-9_.@-]", "", str(identity).strip().lower())[:80]
            key=f"{fn.__name__}:{ip}:{identity}" if identity else f"{fn.__name__}:{ip}"
            if not allow(key,limit,seconds): raise HTTPException(429,"Rate limit exceeded; try later")
            result=fn(*args,**kwargs)
            if inspect.isawaitable(result): return await result
            return result
        return wrapped
    return decorate
templates=Jinja2Templates(directory=str(APP/"templates"))
CATEGORIES=["Food Ingredients","Dehydrated Products","Spices & Agro Products","Millets & Grains","Natural Sweeteners","Agricultural Commodities","Packaging Materials","Industrial Raw Materials"]
STATUSES=["New","Verified","Matched","Quoted","Agreement Sent","Closed-Won","Closed-Lost"]
@app.on_event("startup")
def startup():
    if len(os.getenv("SECRET_KEY",""))<32: raise RuntimeError("Set a random SECRET_KEY (>=32 chars)")
    if os.getenv("APP_ENV","production").lower()=="production":
        dummy_site="1x00000000000000000000AA"
        dummy_secret="1x0000000000000000000000000000000AA"
        if os.getenv("TURNSTILE_SITE_KEY","")==dummy_site or os.getenv("TURNSTILE_SECRET_KEY","")==dummy_secret:
            raise RuntimeError("Cloudflare dummy Turnstile keys are forbidden in production")
    from .db import ping_with_retry
    ping_with_retry()
def ctx(request,**kw): return {"request":request,"csrf":csrf_token(request),"categories":CATEGORIES,"config":{"TURNSTILE_SITE_KEY":os.getenv("TURNSTILE_SITE_KEY","")},"whatsapp":os.getenv("WHATSAPP_NUMBER",""),"umami_script":os.getenv("UMAMI_SCRIPT_URL",""),"umami_website_id":os.getenv("UMAMI_WEBSITE_ID",""),"grievance_email":os.getenv("GRIEVANCE_EMAIL","Set GRIEVANCE_EMAIL"),**kw}
def admin(request):
    if not request.session.get("admin_id"): raise HTTPException(401,"Admin login required")
def clean(s,n=180): return (s or "").strip()[:n]
def validate_business_url(value):
    value=clean(value,500)
    if not value: return ""
    if any(ord(c)<32 for c in value) or "\\" in value: raise HTTPException(422,"Invalid supplier website URL")
    try:
        parts=urlsplit(value)
        if parts.scheme.lower() not in {"http","https"} or not parts.hostname or parts.username or parts.password: raise ValueError()
        host=parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        if host in {"localhost","localhost.localdomain"} or host.endswith((".localhost",".local")): raise ValueError()
        try:
            ip=ipaddress.ip_address(host)
            if not ip.is_global: raise ValueError()
        except ValueError:
            if re.fullmatch(r"[0-9.]+",host): raise ValueError()
        netloc=host + (f":{parts.port}" if parts.port else "")
        return urlunsplit((parts.scheme.lower(),netloc,parts.path or "/",parts.query,""))
    except Exception:
        raise HTTPException(422,"Website must be a public http:// or https:// URL") from None

def turnstile_ok(token,ip):
    secret=os.getenv("TURNSTILE_SECRET_KEY","")
    if not secret: return False if os.getenv("APP_ENV","production")=="production" else os.getenv("APP_ENV")=="development"
    import httpx
    try:
        r=httpx.post("https://challenges.cloudflare.com/turnstile/v0/siteverify",data={"secret":secret,"response":token,"remoteip":ip},timeout=8)
        return r.json().get("success",False)
    except Exception: return False

@app.get("/",response_class=HTMLResponse)
def home(request:Request): return templates.TemplateResponse("page.html",ctx(request,title="Elephant Trading | India B2B",page="home"))
@app.get("/category/{slug}",response_class=HTMLResponse)
def category(slug,request:Request):
    idx={"food-ingredients":0,"dehydrated-products":1,"spices-agro":2,"millets-grains":3,"natural-sweeteners":4,"agri-commodities":5,"packaging-materials":6,"industrial-raw-materials":7}
    if slug not in idx: raise HTTPException(404)
    return templates.TemplateResponse("page.html",ctx(request,title=CATEGORIES[idx[slug]],page="category",category=CATEGORIES[idx[slug]]))
@app.get("/how-it-works",response_class=HTMLResponse)
def how(request:Request): return templates.TemplateResponse("page.html",ctx(request,title="How It Works",page="how"))
@app.get("/about",response_class=HTMLResponse)
def about(request:Request): return templates.TemplateResponse("page.html",ctx(request,title="About Elephant Trading",page="about"))
@app.get("/contact",response_class=HTMLResponse)
def contact(request:Request): return templates.TemplateResponse("page.html",ctx(request,title="Contact",page="contact"))
@app.get("/privacy",response_class=HTMLResponse)
def privacy(request:Request): return templates.TemplateResponse("page.html",ctx(request,title="Privacy Policy",page="privacy"))
@app.get("/terms",response_class=HTMLResponse)
def terms(request:Request): return templates.TemplateResponse("page.html",ctx(request,title="Terms of Use",page="terms"))
@app.get("/commission-terms",response_class=HTMLResponse)
def comm_terms(request:Request): return templates.TemplateResponse("page.html",ctx(request,title="Commission & Non-Circumvention",page="commission"))

def deliver_admin_alert(lead_id, kind, company, product, city, state, email, gstin):
    try:
        send_admin_alert(f"New {kind} registration #{lead_id}",f"Company: {company}\nProduct: {product}\nLocation: {city}, {state}\nEmail: {email}\nGSTIN: {gstin or 'not supplied'}\nReview the admin dashboard.")
        event="Admin alert sent"; note="Resend accepted admin alert"
    except Exception as exc:
        log.exception("Admin alert failed for lead_id=%s",lead_id)
        event="Admin alert failed"; note=f"{type(exc).__name__}: provider/configuration failure"
    with SessionLocal() as session:
        session.add(Activity(lead_id=lead_id,event=event,note=note)); session.commit()

@app.get("/buyer",response_class=HTMLResponse)
def buyer_form(request:Request): return templates.TemplateResponse("form.html",ctx(request,title="Buyer Requirement",kind="buyer"))
@app.get("/supplier",response_class=HTMLResponse)
def supplier_form(request:Request): return templates.TemplateResponse("form.html",ctx(request,title="Supplier Registration",kind="supplier"))
@app.post("/submit/{kind}")
@rate_limit("5/hour")
async def submit(kind:str,request:Request,background_tasks:BackgroundTasks,db:Session=Depends(get_db)):
    if kind not in ("buyer","supplier"): raise HTTPException(404)
    f=await request.form()
    check_csrf(request,f.get("csrf"))
    if f.get("website"): return {"status":"received"} # honeypot
    if not turnstile_ok(f.get("cf-turnstile-response",""),client_ip(request)): raise HTTPException(400,"Bot verification failed")
    required=["company","person","email","phone","city","state","product","category"]
    if kind=="buyer": required += ["quantity","details"]
    else: required += ["capacity","moq","gstin"]
    missing=[k for k in required if not clean(f.get(k),500)]
    if missing: raise HTTPException(422,"Missing: "+", ".join(missing))
    email=clean(f.get("email"),180).lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email): raise HTTPException(422,"Invalid email")
    if kind=="supplier" and not safe_gstin(clean(f.get("gstin"),15).upper()): raise HTTPException(422,"GSTIN format invalid")
    if f.get("consent")!="yes": raise HTTPException(400,"Consent required")
    product=clean(f.get("product"))
    exists=db.scalar(select(Lead).where(Lead.kind==kind,Lead.email==email,Lead.product==product,Lead.status!="Closed-Lost"))
    if exists: raise HTTPException(409,"Possible duplicate submission")
    if f.get("document"): raise HTTPException(404,"Document uploads are disabled in v1.2")
    lead=Lead(kind=kind,company=clean(f.get("company")),person=clean(f.get("person")),email=email,phone=clean(f.get("phone"),30),city=clean(f.get("city"),100),state=clean(f.get("state"),100),product=product,category=clean(f.get("category"),100),quantity=clean(f.get("quantity"),100),details=clean(f.get("details"),4000),gstin=clean(f.get("gstin"),15).upper(),capacity=clean(f.get("capacity"),100),moq=clean(f.get("moq"),100),indicative_price=clean(f.get("price"),100),website=validate_business_url(f.get("business_url")),consent=True)
    try:
        db.add(lead)
        db.flush()
        db.add(Activity(lead_id=lead.id,event="Lead submitted",note=f"{kind} form"))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"Possible duplicate submission") from None
    background_tasks.add_task(deliver_admin_alert,lead.id,kind,lead.company,lead.product,lead.city,lead.state,lead.email,lead.gstin)
    return templates.TemplateResponse("success.html",{"request":request,"lead_id":lead.id,"kind":kind})

@app.get("/admin/login",response_class=HTMLResponse)
def login_page(request:Request): return templates.TemplateResponse("login.html",ctx(request,title="Admin Login"))
@app.post("/admin/login")
def login(request:Request,username:str=Form(...),password:str=Form(...),csrf:str=Form(None),db:Session=Depends(get_db)):
    check_csrf(request,csrf)
    a=db.scalar(select(Admin).where(Admin.username==username))
    now=datetime.now(timezone.utc)
    normalized_username=re.sub(r"[^a-zA-Z0-9_.@-]", "", str(username).strip().lower())[:80]
    failure_key=f"login:{client_ip(request)}:{normalized_username}"
    if not a or not a.active:
        if not allow(failure_key,5,600): raise HTTPException(429,"Rate limit exceeded; try later")
        raise HTTPException(401,"Invalid credentials")
    if a.locked_until:
        try:
            locked=datetime.fromisoformat(a.locked_until)
            if locked.tzinfo is None: locked=locked.replace(tzinfo=timezone.utc)
            if locked>now: raise HTTPException(429,"Account temporarily locked")
        except (ValueError,TypeError):
            # Legacy malformed timestamps are ignored safely; new values are UTC ISO-8601.
            pass
    if not verify_password(a.password_hash,password):
        a.failed_attempts+=1
        if a.failed_attempts>=5: a.locked_until=(now+timedelta(minutes=15)).isoformat()
        db.commit()
        if not allow(failure_key,5,600): raise HTTPException(429,"Rate limit exceeded; try later")
        raise HTTPException(401,"Invalid credentials")
    # Successful logins do not consume the failed-attempt rate-limit budget.
    a.failed_attempts=0; a.locked_until=None; db.commit()
    request.session.clear(); request.session["admin_id"]=a.id; request.session["csrf"]=secrets.token_urlsafe(32)
    return RedirectResponse("/admin",303)
@app.post("/admin/logout")
def logout(request:Request,csrf:str=Form(None)):
    admin(request); check_csrf(request,csrf); request.session.clear(); return RedirectResponse("/",303)
@app.get("/admin",response_class=HTMLResponse)
def dashboard(request:Request,q:str="",kind:str="",status:str="",db:Session=Depends(get_db)):
    admin(request); stmt=select(Lead).where(~Lead.company.like("SMOKE-TEST%"),~Lead.email.like("smoke+%@invalid.test"))
    if q: stmt=stmt.where(or_(Lead.company.ilike(f"%{q}%"),Lead.product.ilike(f"%{q}%"),Lead.email.ilike(f"%{q}%"),Lead.city.ilike(f"%{q}%")))
    if kind: stmt=stmt.where(Lead.kind==kind)
    if status: stmt=stmt.where(Lead.status==status)
    leads=db.scalars(stmt.order_by(Lead.created_at.desc()).limit(500)).all()
    deals=db.scalars(select(Deal).order_by(Deal.created_at.desc()).limit(200)).all()
    alerts=db.scalars(select(Activity).where(Activity.event.in_(["Admin alert sent","Admin alert failed"])).order_by(Activity.created_at.desc()).limit(30)).all()
    return templates.TemplateResponse("admin.html",ctx(request,title="Admin Dashboard",leads=leads,deals=deals,alerts=alerts,statuses=STATUSES,q=q,kind=kind,status=status))
@app.post("/admin/lead/{lead_id}/status")
def update_status(lead_id:int,request:Request,csrf:str=Form(None),status:str=Form(...),verification:str=Form("Pending"),db:Session=Depends(get_db)):
    admin(request); check_csrf(request,csrf)
    if status not in STATUSES or verification not in ["Pending","Verified","Rejected"]: raise HTTPException(422)
    lead=db.get(Lead,lead_id)
    if not lead: raise HTTPException(404)
    if lead.kind=="supplier" and verification=="Verified" and not safe_gstin(lead.gstin): raise HTTPException(400,"Invalid GSTIN format")
    lead.status=status; lead.verification=verification; db.add(Activity(lead_id=lead.id,event="Status updated",note=f"{status}; verification={verification}")); db.commit()
    return RedirectResponse("/admin",303)
def csv_safe(value):
    """Neutralize spreadsheet formulas in untrusted text fields."""
    if value is None: return ""
    value=str(value)
    probe=value.lstrip(" \t\r\n")
    if probe.startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    return value

@app.get("/admin/export.csv")
def export(request:Request,db:Session=Depends(get_db)):
    admin(request); rows=db.scalars(select(Lead).where(~Lead.company.like("SMOKE-TEST%"),~Lead.email.like("smoke+%@invalid.test")).order_by(Lead.created_at.desc())).all()
    import csv,io
    s=io.StringIO(newline=""); w=csv.writer(s); w.writerow(["id","kind","company","person","email","phone","city","state","product","category","quantity","gstin","verification","status"])
    for x in rows: w.writerow([x.id,x.kind,csv_safe(x.company),csv_safe(x.person),csv_safe(x.email),csv_safe(x.phone),csv_safe(x.city),csv_safe(x.state),csv_safe(x.product),csv_safe(x.category),csv_safe(x.quantity),csv_safe(x.gstin),csv_safe(x.verification),csv_safe(x.status)])
    return StreamingResponse(iter([s.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=elephant_leads.csv"})
@app.get("/admin/matches/{buyer_id}",response_class=HTMLResponse)
def matches(buyer_id:int,request:Request,db:Session=Depends(get_db)):
    admin(request); b=db.get(Lead,buyer_id)
    if not b or b.kind!="buyer": raise HTTPException(404)
    ranked=score_matches(db,b)
    return templates.TemplateResponse("matches.html",ctx(request,title="Suggested Supplier Matches",buyer=b,matches=ranked))
@app.post("/admin/deal")
def create_deal(request:Request,csrf:str=Form(None),buyer_id:int=Form(...),supplier_id:int=Form(...),product:str=Form(...),deal_value:float=Form(...),commission_pct:float=Form(...),payment_terms:str=Form(...),jurisdiction:str=Form("Maharashtra, India"),db:Session=Depends(get_db)):
    admin(request); check_csrf(request,csrf)
    b=db.get(Lead,buyer_id); s=db.get(Lead,supplier_id)
    if not b or b.kind!="buyer" or not s or s.kind!="supplier" or s.verification!="Verified": raise HTTPException(400,"Only verified suppliers can be linked")
    if deal_value<0 or commission_pct<0 or commission_pct>30: raise HTTPException(422,"Invalid deal/commission amount")
    d=Deal(buyer_id=buyer_id,supplier_id=supplier_id,product=clean(product),deal_value=deal_value,commission_pct=commission_pct,expected_commission=deal_value*commission_pct/100,payment_terms=clean(payment_terms,2000),jurisdiction=clean(jurisdiction,120))
    db.add(d); db.commit(); return RedirectResponse("/admin",303)
@app.post("/admin/deal/{deal_id}/payment")
def payment(deal_id:int,request:Request,csrf:str=Form(None),received:float=Form(...),db:Session=Depends(get_db)):
    admin(request); check_csrf(request,csrf); d=db.get(Deal,deal_id)
    if not d or received<0: raise HTTPException(422)
    d.received_commission+=received; db.commit(); return RedirectResponse("/admin",303)
@app.get("/admin/agreement/{deal_id}")
def agreement(deal_id:int,request:Request,db:Session=Depends(get_db)):
    admin(request); d=db.get(Deal,deal_id)
    if not d: raise HTTPException(404)
    path=UPLOAD/f"agreement_{d.id}.pdf"
    make_agreement(path,"Buyer and Supplier","both",d.product,d.deal_value,d.commission_pct,d.payment_terms,d.jurisdiction)
    d.agreement_path=str(path); db.commit()
    return FileResponse(path,media_type="application/pdf",filename=f"Elephant_Commission_Agreement_{d.id}.pdf")
@app.post("/admin/smoke-cleanup")
def smoke_cleanup(request:Request,csrf:str=Form(None),run_id:str=Form(...),db:Session=Depends(get_db)):
    if os.getenv("SMOKE_CLEANUP_ENABLED","false").lower()!="true": raise HTTPException(404,"Smoke cleanup is disabled")
    admin(request); check_csrf(request,csrf)
    if not re.fullmatch(r"[A-Za-z0-9-]{8,80}",run_id): raise HTTPException(422,"Invalid smoke run id")
    from sqlalchemy import delete
    rows=db.scalars(select(Lead).where(Lead.email==f"smoke+{run_id}@invalid.test",Lead.company=="SMOKE-TEST")).all()
    ids=[x.id for x in rows]
    if ids:
        db.execute(delete(Activity).where(Activity.lead_id.in_(ids)))
        db.execute(delete(Followup).where(Followup.lead_id.in_(ids)))
        db.execute(delete(Lead).where(Lead.id.in_(ids)))
        db.commit()
    return {"deleted":len(ids),"remaining":db.scalar(select(Lead.id).where(Lead.email==f"smoke+{run_id}@invalid.test",Lead.company=="SMOKE-TEST").limit(1)) is not None}

@app.get("/admin/document/{lead_id}")
def document(lead_id:int,request:Request,db:Session=Depends(get_db)):
    admin(request)
    raise HTTPException(404,"Document uploads are disabled in v1.3")

@app.post("/privacy/request")
@rate_limit("5/hour")
async def privacy_request(request:Request,db:Session=Depends(get_db)):
    form=await request.form()
    check_csrf(request,form.get("csrf"))
    if form.get("website"): return {"status":"received"}
    email=clean(form.get("email"),180).lower()
    kind=clean(form.get("request_type"),40)
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email) or kind not in ["access","correction","erasure","grievance"]:
        raise HTTPException(422,"Valid email and request type required")
    # Do not put raw requester PII in free-text activity notes. The keyed
    # reference supports deduplication without exposing the email in dashboards.
    secret=os.getenv("SECRET_KEY", "")
    requester_ref=hmac.new(secret.encode(),email.encode(),hashlib.sha256).hexdigest()[:20]
    db.add(Activity(event="Privacy request",note=f"{kind} request received; requester_ref={requester_ref}; identity verification pending"))
    db.commit()
    return {"status":"received","message":"Request logged for manual identity verification and response. No data erased automatically."}

@app.get("/robots.txt")
def robots(): return PlainTextResponse("User-agent: *\nAllow: /\nDisallow: /admin\nSitemap: /sitemap.xml\n")
@app.get("/sitemap.xml")
def sitemap(request:Request):
    from xml.etree.ElementTree import Element,SubElement,tostring
    base=os.getenv("APP_BASE_URL",str(request.base_url)).rstrip("/")
    urls=["/","/how-it-works","/about","/contact","/privacy","/terms","/commission-terms","/buyer","/supplier"]
    slugs=["food-ingredients","dehydrated-products","spices-agro","millets-grains","natural-sweeteners","agri-commodities","packaging-materials","industrial-raw-materials"]
    urls += [f"/category/{slug}" for slug in slugs[:len(CATEGORIES)]]
    root=Element("urlset",{"xmlns":"http://www.sitemaps.org/schemas/sitemap/0.9"})
    for path in urls:
        node=SubElement(root,"url"); SubElement(node,"loc").text=base+path
        SubElement(node,"lastmod").text=datetime.now(timezone.utc).date().isoformat()
    return PlainTextResponse('<?xml version="1.0" encoding="UTF-8"?>'+tostring(root,encoding="unicode"),media_type="application/xml")
@app.get("/health")
def health():
    from sqlalchemy import text
    with engine.connect() as c: c.execute(text("SELECT 1"))
    return {"ok":True,"database":"reachable","app":"Elephant Trading"}

@app.post("/internal/run-followups")
async def run_followups(request:Request,db:Session=Depends(get_db)):
    if not secrets.compare_digest(request.headers.get("Authorization",""),"Bearer "+os.getenv("CRON_TOKEN","__unset__")) or not os.getenv("CRON_TOKEN"):
        raise HTTPException(401,"Unauthorized")
    if not allow(f"run_followups:{client_ip(request)}",10,60):
        raise HTTPException(429,"Rate limit exceeded; try later")
    # Frozen: no scheduler or delivery until opt-out enforcement, signed unsubscribe,
    # idempotent retries/backoff and customer email consent are implemented and audited.
    if os.getenv("FOLLOWUPS_ENABLED","false").lower()!="true":
        raise HTTPException(503,"Follow-up scheduler is disabled pending compliance controls")
    if os.getenv("CUSTOMER_EMAILS_ENABLED","false").lower()!="true":
        return {"processed":0,"reason":"customer-emails-disabled"}
    due=db.scalars(select(Followup).where(Followup.sent_at.is_(None),Followup.due_at<=datetime.now(timezone.utc),Followup.attempts<3).limit(100)).all()
    return {"processed":0,"due_records":len(due),"reason":"delivery-provider-worker-not-enabled"}
