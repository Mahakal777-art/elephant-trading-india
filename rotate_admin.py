import os
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Admin
from app.security import hash_password
username=os.getenv('ADMIN_USERNAME','').strip(); password=os.getenv('ADMIN_PASSWORD','')
if not username or len(password)<16: raise SystemExit('Set ADMIN_USERNAME and ADMIN_PASSWORD (minimum 16 chars).')
with SessionLocal() as db:
    row=db.scalar(select(Admin).where(Admin.username==username))
    if not row: raise SystemExit('Admin not found; use create_admin.py for first bootstrap.')
    row.password_hash=hash_password(password); row.failed_attempts=0; row.locked_until=None; row.active=True; db.commit()
print(f'Password rotated for {username!r}. Remove ADMIN_PASSWORD from environment.')
