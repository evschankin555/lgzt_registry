from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

"""Updated the status field for User"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "86b9c6c30861"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.alter_column(
            'registered_at',
            existing_type=sa.DateTime(),
            nullable=True
        )
        batch.alter_column(
            'status',
            existing_type=sa.Enum(
                'registered',
                'not registered',
                'registered and blocked',
                name='user_status'
            ),
            nullable=False,
            server_default=text("'not registered'")
        )

def downgrade():
    with op.batch_alter_table('user') as batch:
        batch.alter_column(
            'status',
            existing_type=sa.Enum(
                'registered',
                'not registered',
                'registered and blocked',
                name='user_status'
            ),
            nullable=True,
            server_default=None
        )
        batch.alter_column(
            'registered_at',
            existing_type=sa.DateTime(),
            nullable=False
        )