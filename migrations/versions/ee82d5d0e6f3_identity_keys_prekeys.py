"""Add identity keys, device signatures, and pre-key table

Revision ID: ee82d5d0e6f3
Revises: d9908132c70a
Create Date: 2026-06-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee82d5d0e6f3'
down_revision: Union[str, None] = 'd9908132c70a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add signing_public_key to users
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('signing_public_key', sa.JSON(), nullable=True))

    # Add device_signature to devices
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('device_signature', sa.Text(), nullable=True))

    # Create new pre_keys table
    op.create_table('pre_keys',
        sa.Column('id', sa.String(length=80), nullable=False),
        sa.Column('user_id', sa.String(length=32), nullable=False),
        sa.Column('device_id', sa.String(length=80), nullable=False),
        sa.Column('key_id', sa.String(length=32), nullable=False),
        sa.Column('public_key_jwk', sa.JSON(), nullable=False),
        sa.Column('fingerprint', sa.String(length=128), nullable=False),
        sa.Column('signature', sa.Text(), nullable=False),
        sa.Column('is_otp', sa.Boolean(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('pre_keys', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pre_keys_fingerprint'), ['fingerprint'], unique=False)
        batch_op.create_index(batch_op.f('ix_pre_keys_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('pre_keys', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pre_keys_user_id'))
        batch_op.drop_index(batch_op.f('ix_pre_keys_fingerprint'))
    op.drop_table('pre_keys')

    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.drop_column('device_signature')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('signing_public_key')
