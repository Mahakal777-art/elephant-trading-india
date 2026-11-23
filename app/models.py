from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, Float, ForeignKey, Integer, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from .db import Base

class Admin(Base):
    __tablename__="admins"
    id:Mapped[int]=mapped_column(primary_key=True)
    username:Mapped[str]=mapped_column(String(80),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    failed_attempts:Mapped[int]=mapped_column(Integer,default=0)
    locked_until:Mapped[str|None]=mapped_column(String(40),nullable=True)

class Lead(Base):
    __tablename__="leads"
    id:Mapped[int]=mapped_column(primary_key=True)
    kind:Mapped[str]=mapped_column(String(20),index=True)
    company:Mapped[str]=mapped_column(String(180)); person:Mapped[str]=mapped_column(String(120))
    email:Mapped[str]=mapped_column(String(180),index=True); phone:Mapped[str]=mapped_column(String(30))
    city:Mapped[str]=mapped_column(String(100)); state:Mapped[str]=mapped_column(String(100))
    product:Mapped[str]=mapped_column(String(180),index=True); category:Mapped[str]=mapped_column(String(100),index=True)
    quantity:Mapped[str]=mapped_column(String(100),default=""); details:Mapped[str]=mapped_column(Text,default="")
    gstin:Mapped[str]=mapped_column(String(15),default=""); capacity:Mapped[str]=mapped_column(String(100),default="")
    moq:Mapped[str]=mapped_column(String(100),default=""); indicative_price:Mapped[str]=mapped_column(String(100),default="")
    website:Mapped[str]=mapped_column(String(500),default=""); document_path:Mapped[str]=mapped_column(String(400),default="")
    verification:Mapped[str]=mapped_column(String(30),default="Pending"); status:Mapped[str]=mapped_column(String(40),default="New",index=True)
    consent:Mapped[bool]=mapped_column(Boolean,default=False); honeypot:Mapped[str]=mapped_column(String(200),default="")
    followup_optout:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    __table_args__ = (Index("uq_leads_active_kind_email_product", "kind", "email", "product", unique=True,
                            postgresql_where=text("status <> 'Closed-Lost'"),
                            sqlite_where=text("status <> 'Closed-Lost'")),)

class Deal(Base):
    __tablename__="deals"
    id:Mapped[int]=mapped_column(primary_key=True)
    buyer_id:Mapped[int]=mapped_column(ForeignKey("leads.id")); supplier_id:Mapped[int]=mapped_column(ForeignKey("leads.id"))
    product:Mapped[str]=mapped_column(String(180)); deal_value:Mapped[float]=mapped_column(Float,default=0)
    commission_pct:Mapped[float]=mapped_column(Float,default=0); expected_commission:Mapped[float]=mapped_column(Float,default=0)
    received_commission:Mapped[float]=mapped_column(Float,default=0); payment_terms:Mapped[str]=mapped_column(Text,default="")
    jurisdiction:Mapped[str]=mapped_column(String(120),default="India"); status:Mapped[str]=mapped_column(String(40),default="Matched")
    agreement_path:Mapped[str]=mapped_column(String(400),default=""); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class Activity(Base):
    __tablename__="activities"
    id:Mapped[int]=mapped_column(primary_key=True); lead_id:Mapped[int|None]=mapped_column(ForeignKey("leads.id"),nullable=True)
    deal_id:Mapped[int|None]=mapped_column(ForeignKey("deals.id"),nullable=True); event:Mapped[str]=mapped_column(String(100))
    note:Mapped[str]=mapped_column(Text,default=""); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class RateLimit(Base):
    __tablename__="rate_limits"
    key:Mapped[str]=mapped_column(String(255),primary_key=True); window_start:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    hits:Mapped[int]=mapped_column(Integer,nullable=False,default=0)

class Followup(Base):
    __tablename__="followups"
    id:Mapped[int]=mapped_column(primary_key=True); lead_id:Mapped[int]=mapped_column(ForeignKey("leads.id"),index=True)
    day_offset:Mapped[int]=mapped_column(Integer); due_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    sent_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); attempts:Mapped[int]=mapped_column(Integer,default=0)
    last_error:Mapped[str]=mapped_column(Text,default=""); __table_args__=(UniqueConstraint("lead_id","day_offset",name="uq_followup_lead_offset"),)
