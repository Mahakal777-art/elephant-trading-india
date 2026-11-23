"""Enforce active lead deduplication at the database level."""
from alembic import op
revision = "0003_active_lead_dedup"
down_revision = "0002_v12_hardening"
branch_labels = None
depends_on = None

def upgrade():
    # Existing duplicate active leads are deliberately not deleted or merged.
    # If any exist, this migration fails safely and requires manual reconciliation.
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_leads_active_kind_email_product ON leads (kind, email, product) WHERE status <> 'Closed-Lost'")

def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_leads_active_kind_email_product")
