# Follow-up scheduler: deploy as a daily cron job after Gmail OAuth is configured.
# This first iteration prints due reminders; sending is deliberately disabled until recipient consent and OAuth are configured.
from datetime import datetime,timezone,timedelta
from app.db import SessionLocal
from app.models import Lead
db=SessionLocal()
for lead in db.query(Lead).filter_by(kind="buyer").all():
 age=(datetime.now(timezone.utc)-lead.created_at.replace(tzinfo=timezone.utc)).days if lead.created_at else 0
 if age in (3,7,14) and lead.status not in ("Closed-Won","Closed-Lost"):
  print(f"FOLLOW-UP DUE day {age}: lead #{lead.id} {lead.company} {lead.email} — manual review/send")
db.close()
