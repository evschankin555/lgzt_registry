"""Updated fields for User, added blocked_at, added father_name

Revision ID: e9eaeaa46eed
Revises: 86b9c6c30861
Create Date: 2025-10-22 12:52:17.950234

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9eaeaa46eed'
down_revision: Union[str, Sequence[str], None] = '86b9c6c30861'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('father_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('blocked_at', sa.DateTime(), nullable=True))
        batch_op.alter_column(
            'status',
            existing_type=sa.VARCHAR(length=14),
            nullable=True,
            existing_server_default=sa.text("'not registered'")
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column(
            'status',
            existing_type=sa.VARCHAR(length=14),
            nullable=False,
            existing_server_default=sa.text("'not registered'")
        )
        batch_op.drop_column('blocked_at')
        batch_op.drop_column('father_name')
