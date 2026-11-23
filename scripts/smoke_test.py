"""Read-only production smoke: health, public pages, fail-closed, login/logout."""
import os, re, requests
base=os.environ.get("SMOKE_BASE_URL", "").rstrip("/")
username=os.environ.get("SMOKE_ADMIN_USERNAME", "")
password=os.environ.get("SMOKE_ADMIN_PASSWORD", "")
if not base.startswith("https://"): raise SystemExit("SMOKE_BASE_URL must be HTTPS")
if not username or not password: raise SystemExit("SMOKE_ADMIN_USERNAME and SMOKE_ADMIN_PASSWORD are mandatory")
s=requests.Session()
def check(resp, expected, label):
    print(f"{resp.status_code} expected={expected} {label}")
    if resp.status_code != expected: raise SystemExit(f"FAIL {label}: {resp.text[:250]}")
paths=["/health","/","/how-it-works","/about","/contact","/privacy","/terms","/commission-terms","/buyer","/supplier"]
paths += ["/category/"+slug for slug in ["food-ingredients","dehydrated-products","spices-agro","millets-grains","natural-sweeteners","agri-commodities","packaging-materials","industrial-raw-materials"]]
for path in paths: check(s.get(base+path,timeout=25),200,path)
page=s.get(base+"/buyer",timeout=25); csrf=re.search(r'name="csrf" value="([^"]+)"',page.text)
if not csrf: raise SystemExit("Buyer CSRF missing")
payload={"csrf":csrf.group(1),"company":"SMOKE-TEST","person":"CI Runner","email":"smoke+production-failclosed@invalid.test","phone":"9999999999","city":"Pune","state":"Maharashtra","product":"Smoke Product","category":"Food Ingredients","quantity":"1 MT","details":"fail-closed probe","consent":"yes"}
check(s.post(base+"/submit/buyer",data=payload,allow_redirects=False,timeout=25),400,"turnstile-fail-closed")
page=s.get(base+"/admin/login",timeout=25); token=re.search(r'name="csrf" value="([^"]+)"',page.text)
if not token: raise SystemExit("Admin login CSRF missing")
check(s.post(base+"/admin/login",data={"username":username,"password":password,"csrf":token.group(1)},allow_redirects=False,timeout=25),303,"admin-login")
check(s.get(base+"/admin",timeout=25),200,"admin-dashboard")
page=s.get(base+"/admin",timeout=25); token=re.search(r'name="csrf" value="([^"]+)"',page.text)
if not token: raise SystemExit("Dashboard CSRF missing")
check(s.post(base+"/admin/logout",data={"csrf":token.group(1)},allow_redirects=False,timeout=25),303,"admin-logout")
print("PRODUCTION SMOKE PASS")
