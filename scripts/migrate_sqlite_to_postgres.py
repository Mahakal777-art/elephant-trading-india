# One-time migration of the prior v1 SQLite leads into the new PostgreSQL schema.
# Set OLD_SQLITE_PATH and DATABASE_URL. This migrates buyer/supplier leads only.
import os,sqlite3
from app.db import Base,engine,SessionLocal
from app.models import Lead
Base.metadata.create_all(engine)
old=sqlite3.connect(os.getenv("OLD_SQLITE_PATH","./data/elephant_trading.db")); old.row_factory=sqlite3.Row
db=SessionLocal()
for table,kind in [("enquiries","buyer"),("supplier_leads","supplier")]:
 try: rows=old.execute(f"SELECT * FROM {table}").fetchall()
 except sqlite3.OperationalError: continue
 for r in rows:
  x=dict(r)
  lead=Lead(kind=kind,company=x.get("company",""),person=x.get("contact_person",x.get("person","")),email=x.get("email",""),phone=x.get("phone",""),city=x.get("city",""),state=x.get("state",""),product=x.get("product",""),category=x.get("category",""),quantity=x.get("quantity",""),details=x.get("requirement",x.get("details","")),gstin=x.get("gstin",""),capacity=x.get("capacity",""),moq=x.get("moq",""),indicative_price=x.get("indicative_price",x.get("price","")),verification="Pending",status="New",consent=bool(x.get("consent",1)))
  if not db.query(Lead).filter_by(kind=kind,email=lead.email,product=lead.product).first(): db.add(lead)
db.commit(); db.close(); old.close(); print("Migration complete; source SQLite left unchanged.")
