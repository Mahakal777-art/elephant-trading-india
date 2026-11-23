from datetime import datetime,timezone,timedelta
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert as pg_insert
from .db import SessionLocal
from .models import RateLimit

def allow(key,limit,seconds):
    now=datetime.now(timezone.utc); cutoff=now-timedelta(seconds=seconds)
    with SessionLocal() as db:
        if db.bind.dialect.name=='postgresql':
            ins=pg_insert(RateLimit).values(key=key,window_start=now,hits=1)
            stmt=ins.on_conflict_do_update(index_elements=['key'],set_={
                'hits':case((RateLimit.window_start < cutoff,1),else_=RateLimit.hits+1),
                'window_start':case((RateLimit.window_start < cutoff,now),else_=RateLimit.window_start)
            }).returning(RateLimit.hits)
            hits=db.execute(stmt).scalar_one(); db.commit(); return hits<=limit
        row=db.get(RateLimit,key)
        row_start=row.window_start.replace(tzinfo=timezone.utc) if row and row.window_start.tzinfo is None else (row.window_start if row else None)
        if not row or row_start<cutoff:
            if row: row.window_start=now; row.hits=1
            else: db.add(RateLimit(key=key,window_start=now,hits=1))
            hits=1
        else: row.hits+=1; hits=row.hits
        db.commit(); return hits<=limit
