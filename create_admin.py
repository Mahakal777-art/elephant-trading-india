import os,sys
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Admin
from app.security import hash_password
username=os.getenv('ADMIN_USERNAME','').strip(); password=os.getenv('ADMIN_PASSWORD','')
if not username or len(password)<14: raise SystemExit('Set ADMIN_USERNAME and ADMIN_PASSWORD (minimum 14 chars) in the environment; no defaults.')
with SessionLocal() as db:
    row=db.scalar(select(Admin).where(Admin.username==username))
    if row: row.password_hash=hash_password(password); row.failed_attempts=0; row.locked_until=None; row.active=True
    else: db.add(Admin(username=username,password_hash=hash_password(password)))
    db.commit()
print(f'Admin {username!r} created/rotated. Remove ADMIN_PASSWORD from environment now.')
