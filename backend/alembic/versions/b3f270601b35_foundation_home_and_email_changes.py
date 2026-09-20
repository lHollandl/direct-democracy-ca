"""Foundation — home changes and email changes (change/02, DATABASE.md §3.1, §3.12, §3.13).

Appended to the Foundation chain. `25035d5b7ff5` is never edited (CLAUDE.md
Law 2, DATABASE.md §6). Schema only: no INSERT, no UPDATE, no backfill.

Revision ID: b3f270601b35
Revises: 25035d5b7ff5
Create Date: 2026-09-20 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b3f270601b35'
down_revision: str | None = '25035d5b7ff5'
branch_labels: Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    # `city_id` becomes nullable: an unincorporated resident has a county but
    # no city (DEMOCRACY.md §2.3).
    op.alter_column('users', 'city_id', existing_type=sa.Integer(), nullable=True)

    op.create_table('user_home_changes',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('from_county_id', sa.Integer(), nullable=False),
    sa.Column('from_city_id', sa.Integer(), nullable=True),
    sa.Column('to_county_id', sa.Integer(), nullable=False),
    sa.Column('to_city_id', sa.Integer(), nullable=True),
    sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['from_city_id'], ['cities.id'], ),
    sa.ForeignKeyConstraint(['from_county_id'], ['counties.id'], ),
    sa.ForeignKeyConstraint(['to_city_id'], ['cities.id'], ),
    sa.ForeignKeyConstraint(['to_county_id'], ['counties.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_home_changes_user_changed', 'user_home_changes', ['user_id', 'changed_at'], unique=False)
    op.create_index('ix_user_home_changes_from_county_id', 'user_home_changes', ['from_county_id'], unique=False)
    op.create_index('ix_user_home_changes_from_city_id', 'user_home_changes', ['from_city_id'], unique=False)
    op.create_index('ix_user_home_changes_to_county_id', 'user_home_changes', ['to_county_id'], unique=False)
    op.create_index('ix_user_home_changes_to_city_id', 'user_home_changes', ['to_city_id'], unique=False)

    op.create_table('email_change_requests',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('new_email', postgresql.CITEXT(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash'),
    )
    op.create_index('ix_email_change_requests_user_id', 'email_change_requests', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_email_change_requests_user_id', table_name='email_change_requests')
    op.drop_table('email_change_requests')
    op.drop_index('ix_user_home_changes_to_city_id', table_name='user_home_changes')
    op.drop_index('ix_user_home_changes_to_county_id', table_name='user_home_changes')
    op.drop_index('ix_user_home_changes_from_city_id', table_name='user_home_changes')
    op.drop_index('ix_user_home_changes_from_county_id', table_name='user_home_changes')
    op.drop_index('ix_user_home_changes_user_changed', table_name='user_home_changes')
    op.drop_table('user_home_changes')
    op.alter_column('users', 'city_id', existing_type=sa.Integer(), nullable=False)
