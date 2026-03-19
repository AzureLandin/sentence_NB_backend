"""initial tables

Revision ID: 000000000000
Revises: 
Create Date: 2026-03-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '000000000000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
    sa.Column('id', sa.String(36), primary_key=True),
    sa.Column('email', sa.String(255), unique=True, nullable=True),
    sa.Column('password_hash', sa.String(255), nullable=True),
    sa.Column('display_name', sa.String(100), nullable=True),
    sa.Column('status', sa.String(20), nullable=True, server_default='active'),
    sa.Column('wechat_openid', sa.String(64), unique=True, nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_wechat_openid'), ['wechat_openid'], unique=False)

    op.create_table('refresh_tokens',
    sa.Column('id', sa.String(36), primary_key=True),
    sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
    sa.Column('token_hash', sa.String(255), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True)
    )
    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_refresh_tokens_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_refresh_tokens_token_hash'), ['token_hash'], unique=False)

    op.create_table('user_settings',
    sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), primary_key=True),
    sa.Column('use_mode', sa.String(20), nullable=True, server_default='simple'),
    sa.Column('text_api', sa.JSON, nullable=True),
    sa.Column('vision_api', sa.JSON, nullable=True),
    sa.Column('ui', sa.JSON, nullable=True),
    sa.Column('version', sa.BigInteger, nullable=True, server_default='1'),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
    )

    op.create_table('sentences',
    sa.Column('id', sa.String(36), primary_key=True),
    sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
    sa.Column('content', sa.Text, nullable=False),
    sa.Column('source', sa.String(20), nullable=True, server_default='text'),
    sa.Column('analysis', sa.JSON, nullable=True),
    sa.Column('tags', sa.JSON, nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('version', sa.BigInteger, nullable=True, server_default='1')
    )
    with op.batch_alter_table('sentences', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sentences_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_sentences_updated_at'), ['updated_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_sentences_deleted_at'), ['deleted_at'], unique=False)
        batch_op.create_index('ix_sentences_user_updated', ['user_id', 'updated_at'], unique=False)

    op.create_table('sync_idempotency_records',
    sa.Column('id', sa.String(36), primary_key=True),
    sa.Column('user_id', sa.String(36), nullable=False),
    sa.Column('device_id', sa.String(100), nullable=False),
    sa.Column('op_id', sa.String(100), nullable=False),
    sa.Column('request_hash', sa.String(64), nullable=False),
    sa.Column('result_snapshot', sa.JSON, nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False)
    )
    with op.batch_alter_table('sync_idempotency_records', schema=None) as batch_op:
        batch_op.create_index('ix_idempotency_user_device_op', ['user_id', 'device_id', 'op_id'], unique=False)


def downgrade():
    op.drop_table('sync_idempotency_records')
    op.drop_table('sentences')
    op.drop_table('user_settings')
    op.drop_table('refresh_tokens')
    op.drop_table('users')