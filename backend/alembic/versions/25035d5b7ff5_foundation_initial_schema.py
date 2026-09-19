"""Foundation initial schema — DATABASE.md §3.

Every Foundation table, created once. This migration is immutable from the
moment it is applied to any real database (CLAUDE.md Law 2, DATABASE.md §6).
Schema only: no INSERT, no UPDATE, no backfill.

Revision ID: 25035d5b7ff5
Revises: 
Create Date: 2026-09-13 17:36:10.809462

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '25035d5b7ff5'
down_revision: str | None = None
branch_labels: Sequence[str] | None = ('foundation',)
depends_on: str | None = None

#: Every PostgreSQL enum type the Foundation tables use. The two shared enums
#: (`community_level_enum`, `verification_level_enum`) are created here because
#: Foundation is applied first; the Iteration chain finds them already present.
_ENUMS: dict[str, tuple[str, ...]] = {
    "ai_actions_action_type_enum": ('label', 'similarity', 'reference_recommend'),
    "ai_actions_human_outcome_enum": ('unreviewed', 'confirmed', 'corrected', 'accepted', 'rejected'),
    "community_level_enum": ('city', 'county', 'state', 'federal'),
    "officials_source_enum": ('seed', 'user_correction'),
    "user_display_settings_public_name_mode_enum": ('real_name', 'display_name', 'anonymous'),
    "users_gender_enum": ('woman', 'man', 'nonbinary', 'other', 'prefer_not_to_say'),
    "users_political_party_enum": ('democratic', 'republican', 'green', 'libertarian', 'american_independent', 'peace_and_freedom', 'no_party_preference', 'other', 'prefer_not_to_say'),
    "verification_level_enum": ('unverified', 'phone', 'address', 'voter'),
}


def upgrade() -> None:
    # citext gives `users.email` case-insensitive uniqueness (DATABASE.md §3.1).
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # Enum types are created explicitly, in one place, so that the shared enums
    # (DATABASE.md §1) exist before either chain's tables reference them and are
    # never created twice. Adding a value later is a migration; removing one is
    # forbidden (CLAUDE.md Law 3).
    for name, values in _ENUMS.items():
        labels = ", ".join(f"'{v}'" for v in values)
        op.execute(
            f"DO $$ BEGIN "
            f"IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN "
            f"CREATE TYPE {name} AS ENUM ({labels}); "
            f"END IF; END $$"
        )

    op.create_table('officials',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('community_level', postgresql.ENUM('city', 'county', 'state', 'federal', name='community_level_enum', create_type=False), nullable=False),
    sa.Column('community_entity_id', sa.Integer(), nullable=False),
    sa.Column('office', sa.Text(), nullable=False),
    sa.Column('holder_name', sa.Text(), nullable=True),
    sa.Column('email', sa.Text(), nullable=False),
    sa.Column('source', postgresql.ENUM('seed', 'user_correction', name='officials_source_enum', create_type=False), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('community_level', 'community_entity_id', 'office', name='uq_officials_community_office')
    )
    op.create_index('ix_officials_community', 'officials', ['community_level', 'community_entity_id'], unique=False)
    op.create_table('states',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('abbreviation', sa.String(length=2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('abbreviation')
    )
    op.create_table('terms_versions',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('version', sa.Text(), nullable=False),
    sa.Column('privacy_policy_md', sa.Text(), nullable=False),
    sa.Column('terms_of_service_md', sa.Text(), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('version')
    )
    op.create_table('counties',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('state_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('fips', sa.String(length=5), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['state_id'], ['states.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('fips'),
    sa.UniqueConstraint('state_id', 'name', name='uq_counties_state_id_name')
    )
    op.create_index('ix_counties_state_id', 'counties', ['state_id'], unique=False)
    op.create_table('cities',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('county_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('incorporated', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('fips', sa.String(length=7), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['county_id'], ['counties.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('county_id', 'name', name='uq_cities_county_id_name'),
    sa.UniqueConstraint('fips')
    )
    op.create_index('ix_cities_county_id', 'cities', ['county_id'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('email', postgresql.CITEXT(), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('real_name', sa.Text(), nullable=False),
    sa.Column('display_name', sa.Text(), nullable=False),
    sa.Column('date_of_birth', sa.Date(), nullable=False),
    sa.Column('gender', postgresql.ENUM('woman', 'man', 'nonbinary', 'other', 'prefer_not_to_say', name='users_gender_enum', create_type=False), nullable=False),
    sa.Column('political_party', postgresql.ENUM('democratic', 'republican', 'green', 'libertarian', 'american_independent', 'peace_and_freedom', 'no_party_preference', 'other', 'prefer_not_to_say', name='users_political_party_enum', create_type=False), nullable=False),
    sa.Column('county_id', sa.Integer(), nullable=False),
    sa.Column('city_id', sa.Integer(), nullable=False),
    sa.Column('verification_level', postgresql.ENUM('unverified', 'phone', 'address', 'voter', name='verification_level_enum', create_type=False), server_default=sa.text("'unverified'"), nullable=False),
    sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_admin', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('influence_score', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['city_id'], ['cities.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['county_id'], ['counties.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_city_id', 'users', ['city_id'], unique=False)
    op.create_index('ix_users_city_last_active', 'users', ['city_id', 'last_active_at'], unique=False)
    op.create_index('ix_users_county_id', 'users', ['county_id'], unique=False)
    op.create_index('ix_users_county_last_active', 'users', ['county_id', 'last_active_at'], unique=False)
    op.create_index('ix_users_email', 'users', ['email'], unique=False)
    op.create_index('ix_users_last_active_at', 'users', ['last_active_at'], unique=False)
    op.create_index('uq_users_display_name', 'users', ['display_name'], unique=True, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_table('admin_actions',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('admin_user_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.Text(), nullable=False),
    sa.Column('subject_type', sa.Text(), nullable=False),
    sa.Column('subject_id', sa.Integer(), nullable=True),
    sa.Column('old_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['admin_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_admin_actions_admin_user_id', 'admin_actions', ['admin_user_id'], unique=False)
    op.create_index('ix_admin_actions_created_at', 'admin_actions', ['created_at'], unique=False)
    op.create_index('ix_admin_actions_subject', 'admin_actions', ['subject_type', 'subject_id'], unique=False)
    op.create_table('ai_actions',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('action_type', postgresql.ENUM('label', 'similarity', 'reference_recommend', name='ai_actions_action_type_enum', create_type=False), nullable=False),
    sa.Column('subject_type', sa.Text(), nullable=False),
    sa.Column('subject_id', sa.Integer(), nullable=False),
    sa.Column('demo_build', sa.Text(), nullable=False),
    sa.Column('model', sa.Text(), nullable=False),
    sa.Column('prompt_file', sa.Text(), nullable=False),
    sa.Column('prompt_hash', sa.String(length=64), nullable=False),
    sa.Column('input_hash', sa.String(length=64), nullable=False),
    sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=True),
    sa.Column('human_outcome', postgresql.ENUM('unreviewed', 'confirmed', 'corrected', 'accepted', 'rejected', name='ai_actions_human_outcome_enum', create_type=False), server_default=sa.text("'unreviewed'"), nullable=False),
    sa.Column('human_outcome_by', sa.Integer(), nullable=True),
    sa.Column('human_outcome_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['human_outcome_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_actions_created_at', 'ai_actions', ['created_at'], unique=False)
    op.create_index('ix_ai_actions_human_outcome_by', 'ai_actions', ['human_outcome_by'], unique=False)
    op.create_index('ix_ai_actions_subject', 'ai_actions', ['subject_type', 'subject_id'], unique=False)
    op.create_table('data_exports',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('file_path', sa.Text(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_data_exports_expires_at', 'data_exports', ['expires_at'], unique=False)
    op.create_index('ix_data_exports_user_id', 'data_exports', ['user_id'], unique=False)
    op.create_table('email_verifications',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index('ix_email_verifications_user_id', 'email_verifications', ['user_id'], unique=False)
    op.create_table('password_resets',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index('ix_password_resets_user_id', 'password_resets', ['user_id'], unique=False)
    op.create_table('refresh_tokens',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('replaced_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['replaced_by_id'], ['refresh_tokens.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index('ix_refresh_tokens_expires_at', 'refresh_tokens', ['expires_at'], unique=False)
    op.create_index('ix_refresh_tokens_replaced_by_id', 'refresh_tokens', ['replaced_by_id'], unique=False)
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'], unique=False)
    op.create_table('settings',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('key', sa.Text(), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('effective_from', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('changed_by', sa.Integer(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_settings_changed_by', 'settings', ['changed_by'], unique=False)
    op.create_index('ix_settings_key_effective_from', 'settings', ['key', sa.literal_column('effective_from DESC')], unique=False)
    op.create_table('terms_acceptances',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('terms_version_id', sa.Integer(), nullable=False),
    sa.Column('accepted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('ip_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['terms_version_id'], ['terms_versions.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_terms_acceptances_terms_version_id', 'terms_acceptances', ['terms_version_id'], unique=False)
    op.create_index('ix_terms_acceptances_user_id', 'terms_acceptances', ['user_id'], unique=False)
    op.create_table('user_display_settings',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('public_name_mode', postgresql.ENUM('real_name', 'display_name', 'anonymous', name='user_display_settings_public_name_mode_enum', create_type=False), server_default=sa.text("'display_name'"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('user_display_settings')
    op.drop_index('ix_terms_acceptances_user_id', table_name='terms_acceptances')
    op.drop_index('ix_terms_acceptances_terms_version_id', table_name='terms_acceptances')
    op.drop_table('terms_acceptances')
    op.drop_index('ix_settings_key_effective_from', table_name='settings')
    op.drop_index('ix_settings_changed_by', table_name='settings')
    op.drop_table('settings')
    op.drop_index('ix_refresh_tokens_user_id', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_replaced_by_id', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_expires_at', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index('ix_password_resets_user_id', table_name='password_resets')
    op.drop_table('password_resets')
    op.drop_index('ix_email_verifications_user_id', table_name='email_verifications')
    op.drop_table('email_verifications')
    op.drop_index('ix_data_exports_user_id', table_name='data_exports')
    op.drop_index('ix_data_exports_expires_at', table_name='data_exports')
    op.drop_table('data_exports')
    op.drop_index('ix_ai_actions_subject', table_name='ai_actions')
    op.drop_index('ix_ai_actions_human_outcome_by', table_name='ai_actions')
    op.drop_index('ix_ai_actions_created_at', table_name='ai_actions')
    op.drop_table('ai_actions')
    op.drop_index('ix_admin_actions_subject', table_name='admin_actions')
    op.drop_index('ix_admin_actions_created_at', table_name='admin_actions')
    op.drop_index('ix_admin_actions_admin_user_id', table_name='admin_actions')
    op.drop_table('admin_actions')
    op.drop_index('uq_users_display_name', table_name='users', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('ix_users_last_active_at', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_county_last_active', table_name='users')
    op.drop_index('ix_users_county_id', table_name='users')
    op.drop_index('ix_users_city_last_active', table_name='users')
    op.drop_index('ix_users_city_id', table_name='users')
    op.drop_table('users')
    op.drop_index('ix_cities_county_id', table_name='cities')
    op.drop_table('cities')
    op.drop_index('ix_counties_state_id', table_name='counties')
    op.drop_table('counties')
    op.drop_table('terms_versions')
    op.drop_table('states')
    op.drop_index('ix_officials_community', table_name='officials')
    op.drop_table('officials')
    for name in _ENUMS:
        op.execute(f"DROP TYPE IF EXISTS {name}")
