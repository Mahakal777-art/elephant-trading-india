"""Print all administrative/internal routes for security review."""
import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SECRET_KEY", "route-audit-only-secret-key-012345678901234567890123456789")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/route_audit.db")
from app.main import app
for route in app.routes:
    path=getattr(route,"path","")
    if path.startswith(("/admin", "/internal")):
        methods=sorted((getattr(route,"methods",set()) or set())-{"HEAD","OPTIONS"})
        print(",".join(methods),path)
