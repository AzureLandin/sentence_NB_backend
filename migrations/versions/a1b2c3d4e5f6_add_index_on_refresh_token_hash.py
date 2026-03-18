"""add index on refresh_token token_hash

Revision ID: a1b2c3d4e5f6
Revises: 95211421c454
Create Date: 2026-03-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '95211421c454'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_refresh_tokens_token_hash'),
            ['token_hash'],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_refresh_tokens_token_hash'))
