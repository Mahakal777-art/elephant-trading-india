"""v1.2 supplier URL, follow-up ledger and shared limiter"""
from alembic import op
from sqlalchemy import inspect, Column, String, Boolean, Integer, DateTime, Text, ForeignKey, UniqueConstraint
revision='0002_v12_hardening'; down_revision='0001_initial'; branch_labels=None; depends_on=None

def upgrade():
    bind=op.get_bind()
    if bind.dialect.name == "sqlite":
        inspector=inspect(bind)
        cols={c["name"] for c in inspector.get_columns("leads")}
        if "website" not in cols: op.add_column("leads",Column("website",String(500),nullable=False,server_default=""))
        if "followup_optout" not in cols: op.add_column("leads",Column("followup_optout",Boolean(),nullable=False,server_default="0"))
        tables=set(inspect(bind).get_table_names())
        if "rate_limits" not in tables:
            op.create_table("rate_limits",Column("key",String(255),primary_key=True),Column("window_start",DateTime(timezone=True),nullable=False),Column("hits",Integer(),nullable=False,server_default="0"))
        if "followups" not in tables:
            op.create_table("followups",Column("id",Integer(),primary_key=True),Column("lead_id",Integer(),ForeignKey("leads.id"),nullable=False),Column("day_offset",Integer(),nullable=False),Column("due_at",DateTime(timezone=True),nullable=False),Column("sent_at",DateTime(timezone=True)),Column("attempts",Integer(),nullable=False,server_default="0"),Column("last_error",Text(),nullable=False,server_default=""),UniqueConstraint("lead_id","day_offset",name="uq_followup_lead_offset"))
        inspector=inspect(bind)
        idx={i["name"] for i in inspector.get_indexes("followups")} if "followups" in inspect(bind).get_table_names() else set()
        if "ix_followups_lead_id" not in idx: op.create_index("ix_followups_lead_id","followups",["lead_id"])
        if "ix_followups_due_at" not in idx: op.create_index("ix_followups_due_at","followups",["due_at"])
        return
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS website VARCHAR(500) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_optout BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("CREATE TABLE IF NOT EXISTS rate_limits (key VARCHAR(255) PRIMARY KEY, window_start TIMESTAMP WITH TIME ZONE NOT NULL, hits INTEGER NOT NULL DEFAULT 0)")
    op.execute("CREATE TABLE IF NOT EXISTS followups (id SERIAL PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id), day_offset INTEGER NOT NULL, due_at TIMESTAMP WITH TIME ZONE NOT NULL, sent_at TIMESTAMP WITH TIME ZONE NULL, attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '', CONSTRAINT uq_followup_lead_offset UNIQUE (lead_id, day_offset))")
    op.execute("CREATE INDEX IF NOT EXISTS ix_followups_lead_id ON followups(lead_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_followups_due_at ON followups(due_at)")

def downgrade():
    op.execute('DROP TABLE IF EXISTS followups')
    op.execute('DROP TABLE IF EXISTS rate_limits')
    if op.get_bind().dialect.name == "sqlite":
        cols={c["name"] for c in inspect(op.get_bind()).get_columns("leads")}
        if "website" in cols: op.drop_column("leads","website")
        if "followup_optout" in cols: op.drop_column("leads","followup_optout")
    else:
        op.execute('ALTER TABLE leads DROP COLUMN IF EXISTS website')
        op.execute('ALTER TABLE leads DROP COLUMN IF EXISTS followup_optout')
