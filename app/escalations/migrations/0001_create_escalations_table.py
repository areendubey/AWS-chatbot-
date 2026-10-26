"""create escalations table

Revision ID: 0001_escalations
Revises: None
Create Date: 2026-10-23
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001_escalations'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'escalations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('reference_id', sa.String(length=32), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('email_status', sa.String(length=32), nullable=False),
        sa.Column('email_error', sa.Text(), nullable=True),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('wants_followup', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('contact', sa.String(length=255), nullable=True),
        sa.Column('is_personal', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('approved_for_faq', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_escalations_reference_id'), 'escalations', ['reference_id'], unique=True)
    op.create_index(op.f('ix_escalations_created_at'), 'escalations', ['created_at'], unique=False)
    op.create_index(op.f('ix_escalations_status'), 'escalations', ['status'], unique=False)
    op.create_index(op.f('ix_escalations_email_status'), 'escalations', ['email_status'], unique=False)
    op.create_index('ix_escalations_status_email', 'escalations', ['status', 'email_status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_escalations_status_email', table_name='escalations')
    op.drop_index(op.f('ix_escalations_email_status'), table_name='escalations')
    op.drop_index(op.f('ix_escalations_status'), table_name='escalations')
    op.drop_index(op.f('ix_escalations_created_at'), table_name='escalations')
    op.drop_index(op.f('ix_escalations_reference_id'), table_name='escalations')
    op.drop_table('escalations')
