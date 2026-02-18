"""add volunteer_id to user

Revision ID: 9e38cee59d4c
Revises: dde77c43507c
Create Date: 2026-02-18 19:08:08.878602

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e38cee59d4c'
down_revision: Union[str, Sequence[str], None] = 'dde77c43507c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user', sa.Column('volunteer_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'volunteer_id')
