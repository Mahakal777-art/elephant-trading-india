"""Full disposable buyer flow against docker-compose app + PostgreSQL."""
import os,re,uuid,requests
base=os.getenv("SMOKE_BASE_URL","http://127.0.0.1:8000").rstrip("/")
username=os.environ["SMOKE_ADMIN_USERNAME"]; password=os.environ["SMOKE_ADMIN_PASSWORD"]
s=requests.Session()
def check(resp,expected,label):
 print(f"{resp.status_code} expected={expected} {label}")
 if resp.status_code!=expected: raise SystemExit(f"FAIL {label}: {resp.text[:300]}")
check(s.get(base+"/health"),200,"health")
run_id=str(uuid.uuid4()); email=f"smoke+{run_id}@invalid.test"
page=s.get(base+"/buyer"); csrf=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
payload={"csrf":csrf,"company":"SMOKE-TEST","person":"CI Runner","email":email,"phone":"9999999999","city":"Pune","state":"Maharashtra","product":"Smoke Product","category":"Food Ingredients","quantity":"1 MT","details":"Disposable CI smoke enquiry","consent":"yes","cf-turnstile-response":"XXXX.DUMMY.TOKEN.XXXX"}
check(s.post(base+"/submit/buyer",data=payload),200,"buyer-submit")
page=s.get(base+"/admin/login"); csrf=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
check(s.post(base+"/admin/login",data={"username":username,"password":password,"csrf":csrf},allow_redirects=False),303,"admin-login")
dash=s.get(base+"/admin"); check(dash,200,"dashboard")
if email not in dash.text: raise SystemExit("FAIL lead missing from admin dashboard")
check(s.post(base+"/submit/buyer",data=payload),409,"duplicate-409")
# cleanup endpoint requires authenticated admin + CSRF and deletes only exact run marker.
csrf=re.search(r'name="csrf" value="([^"]+)"',dash.text).group(1)
cleanup=s.post(base+"/admin/smoke-cleanup",data={"csrf":csrf,"run_id":run_id})
check(cleanup,200,"cleanup")
if cleanup.json()!={"deleted":1,"remaining":False}: raise SystemExit(f"FAIL cleanup proof: {cleanup.text}")
# Verify deletion from dashboard and DB-backed search result.
if email in s.get(base+"/admin").text: raise SystemExit("FAIL smoke row still visible after cleanup")
# Fail-closed: missing Turnstile token cannot create another row.
page=s.get(base+"/buyer"); csrf=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
payload.update({"csrf":csrf,"email":f"smoke+{uuid.uuid4()}@invalid.test"}); payload.pop("cf-turnstile-response",None)
check(s.post(base+"/submit/buyer",data=payload),400,"turnstile-fail-closed")
# Nonexistent username must still be throttled by IP+username limiter.
for i in range(5):
 page=s.get(base+"/admin/login"); token=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
 check(s.post(base+"/admin/login",data={"username":"nonexistent-smoke-user","password":"not-a-password","csrf":token},allow_redirects=False),401,f"nonexistent-login-{i+1}")
page=s.get(base+"/admin/login"); token=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
check(s.post(base+"/admin/login",data={"username":"nonexistent-smoke-user","password":"not-a-password","csrf":token},allow_redirects=False),429,"ip-username-lockout")
# Fresh session login and logout lifecycle.
t=requests.Session(); page=t.get(base+"/admin/login"); token=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
check(t.post(base+"/admin/login",data={"username":username,"password":password,"csrf":token},allow_redirects=False),303,"admin-login-after-lockout")
dash=t.get(base+"/admin"); token=re.search(r'name="csrf" value="([^"]+)"',dash.text).group(1)
check(t.post(base+"/admin/logout",data={"csrf":token},allow_redirects=False),303,"admin-logout")
print("DOCKER-COMPOSE E2E PASS: buyer row, dashboard, duplicate 409, marker cleanup, fail-closed, IP+username lockout, login/logout")
