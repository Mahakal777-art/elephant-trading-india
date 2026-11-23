"""Create initial Elephant Trading schema."""
from alembic import op
revision="0001_initial"; down_revision=None; branch_labels=None; depends_on=None
def upgrade():
    from app.db import Base
    from app import models
    Base.metadata.create_all(bind=op.get_bind())
def downgrade():
    from app.db import Base
    from app import models
    Base.metadata.drop_all(bind=op.get_bind())
