"""add last_message_sent tracking to groups

Revision ID: add_last_message_sent
Revises: 
Create Date: 2026-02-06 23:46:51

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_last_message_sent'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to groups table
    op.add_column('groups', sa.Column('last_message_sent_id', sa.Integer(), nullable=True))
    op.add_column('groups', sa.Column('last_sent_at', sa.DateTime(), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_groups_last_message_sent',
        'groups', 'messages',
        ['last_message_sent_id'], ['id']
    )


def downgrade():
    op.drop_constraint('fk_groups_last_message_sent', 'groups', type_='foreignkey')
    op.drop_column('groups', 'last_sent_at')
    op.drop_column('groups', 'last_message_sent_id')
