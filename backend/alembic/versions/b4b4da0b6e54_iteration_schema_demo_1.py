"""Iteration schema — Demo 1 (DATABASE.md §4).

One fresh migration for the whole Iteration half. It is regenerated from the
documents for each demo until the director declares a keeper build, and is
immutable from that build onward (DATABASE.md §6). Foreign keys may point at
Foundation tables; nothing here touches one. Schema only.

Revision ID: b4b4da0b6e54
Revises: 
Create Date: 2026-09-13 18:10:45.408957

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b4b4da0b6e54'
down_revision: str | None = None
branch_labels: Sequence[str] | None = ('iteration',)
depends_on: str | None = None

#: Enum types used only by Iteration tables. The two shared enums
#: (`community_level_enum`, `verification_level_enum`) belong to the Foundation
#: chain and are never created or dropped here (DATABASE.md §1, §2).
_ENUMS: dict[str, tuple[str, ...]] = {
    "amendment_similarity_decision_enum": ('pending', 'same', 'different'),
    "amendment_similarity_votes_choice_enum": ('same', 'different'),
    "amendments_status_enum": ('proposed', 'absorbed', 'superseded', 'merged_into', 'withdrawn'),
    "ballot_items_result_enum": ('passed', 'failed', 'held_back'),
    "ballot_votes_choice_enum": ('yes', 'no'),
    "comments_target_type_enum": ('umbrella', 'solution'),
    "cycles_state_enum": ('workshop', 'prepared', 'jury_review', 'open', 'closed', 'published'),
    "jurors_status_enum": ('drawn', 'accepted', 'declined', 'replaced', 'no_response'),
    "jury_holdbacks_reason_category_enum": ('duplicate', 'not_actionable', 'incomplete', 'outside_governance_level', 'other'),
    "labels_outcome_enum": ('unreviewed', 'confirmed_by_author', 'corrected_by_author', 'author_selected'),
    "posts_category_choice_enum": ('ai', 'author_selected'),
    "posts_label_status_enum": ('pending', 'labeled', 'needs_review', 'unlabeled'),
    "solutions_last_ballot_result_enum": ('passed', 'failed', 'held_back'),
    "umbrella_references_source_enum": ('user', 'ai'),
    "umbrella_references_status_enum": ('active', 'rejected'),
    "umbrellas_source_enum": ('seed', 'proposal'),
    "umbrellas_status_enum": ('active', 'retired'),
    "votes_target_type_enum": ('solution', 'amendment', 'comment'),
}


def upgrade() -> None:
    for name, values in _ENUMS.items():
        labels = ", ".join(f"'{v}'" for v in values)
        op.execute(
            f"DO $$ BEGIN "
            f"IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN "
            f"CREATE TYPE {name} AS ENUM ({labels}); "
            f"END IF; END $$"
        )

    op.create_table('cycles',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('community_level', postgresql.ENUM('city', 'county', 'state', 'federal', name='community_level_enum', create_type=False), nullable=False),
    sa.Column('community_entity_id', sa.Integer(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('state', postgresql.ENUM('workshop', 'prepared', 'jury_review', 'open', 'closed', 'published', name='cycles_state_enum', create_type=False), nullable=False),
    sa.Column('settings_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('active_users_at_prepare', sa.Integer(), nullable=True),
    sa.Column('prepared_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('jury_review_started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('transitioned_by', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('community_level', 'community_entity_id', 'number', name='uq_cycles_community_number')
    )
    op.create_index('ix_cycles_community', 'cycles', ['community_level', 'community_entity_id'], unique=False)
    op.create_index('uq_cycles_one_open_per_community', 'cycles', ['community_level', 'community_entity_id'], unique=True, postgresql_where=sa.text("state <> 'published'"))
    op.create_table('main_categories',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('slug', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('juries',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('cycle_id', sa.Integer(), nullable=False),
    sa.Column('size_requested', sa.Integer(), nullable=False),
    sa.Column('eligible_pool', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('random_bytes', sa.String(length=64), nullable=False),
    sa.Column('drawn_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('redrawn_reason', sa.Text(), nullable=True),
    sa.Column('seated_count', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['cycle_id'], ['cycles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('cycle_id')
    )
    op.create_table('summaries',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('cycle_id', sa.Integer(), nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('summary_hash', sa.String(length=64), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('pdf_path', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['cycle_id'], ['cycles.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('cycle_id')
    )
    op.create_index('ix_summaries_published_at', 'summaries', ['published_at'], unique=False)
    op.create_table('umbrellas',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('main_category_id', sa.Integer(), nullable=False),
    sa.Column('community_level', postgresql.ENUM('city', 'county', 'state', 'federal', name='community_level_enum', create_type=False), nullable=False),
    sa.Column('community_entity_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('statement', sa.Text(), nullable=False),
    sa.Column('status', postgresql.ENUM('active', 'retired', name='umbrellas_status_enum', create_type=False), server_default=sa.text("'active'"), nullable=False),
    sa.Column('source', postgresql.ENUM('seed', 'proposal', name='umbrellas_source_enum', create_type=False), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['main_category_id'], ['main_categories.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('community_level', 'community_entity_id', 'main_category_id', 'name', name='uq_umbrellas_community_category_name')
    )
    op.create_index('ix_umbrellas_community', 'umbrellas', ['community_level', 'community_entity_id'], unique=False)
    op.create_index('ix_umbrellas_main_category_id', 'umbrellas', ['main_category_id'], unique=False)
    op.create_table('comments',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('target_type', postgresql.ENUM('umbrella', 'solution', name='comments_target_type_enum', create_type=False), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('depth', sa.SmallInteger(), nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('net_score', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('ai_contribution_percentage', sa.SmallInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['parent_id'], ['comments.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_comments_author_id', 'comments', ['author_id'], unique=False)
    op.create_index('ix_comments_parent_id', 'comments', ['parent_id'], unique=False)
    op.create_index('ix_comments_target', 'comments', ['target_type', 'target_id', 'parent_id'], unique=False)
    op.create_table('jurors',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('jury_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('seat', sa.SmallInteger(), nullable=False),
    sa.Column('status', postgresql.ENUM('drawn', 'accepted', 'declined', 'replaced', 'no_response', name='jurors_status_enum', create_type=False), server_default=sa.text("'drawn'"), nullable=False),
    sa.Column('replaced_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['jury_id'], ['juries.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['replaced_by_id'], ['jurors.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('jury_id', 'user_id', name='uq_jurors_jury_user')
    )
    op.create_index('ix_jurors_jury_id', 'jurors', ['jury_id'], unique=False)
    op.create_index('ix_jurors_replaced_by_id', 'jurors', ['replaced_by_id'], unique=False)
    op.create_index('ix_jurors_user_id', 'jurors', ['user_id'], unique=False)
    op.create_table('posts',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('problem_text', sa.Text(), nullable=False),
    sa.Column('category_choice', postgresql.ENUM('ai', 'author_selected', name='posts_category_choice_enum', create_type=False), nullable=False),
    sa.Column('label_status', postgresql.ENUM('pending', 'labeled', 'needs_review', 'unlabeled', name='posts_label_status_enum', create_type=False), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('ai_contribution_percentage', sa.SmallInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_posts_author_id', 'posts', ['author_id'], unique=False)
    op.create_index('ix_posts_created_at', 'posts', ['created_at'], unique=False)
    op.create_index('ix_posts_label_status', 'posts', ['label_status'], unique=False)
    op.create_table('votes',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('target_type', postgresql.ENUM('solution', 'amendment', 'comment', name='votes_target_type_enum', create_type=False), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=False),
    sa.Column('direction', sa.SmallInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('direction IN (1, -1)', name='ck_votes_direction'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'target_type', 'target_id', name='uq_votes_user_target')
    )
    op.create_index('ix_votes_target', 'votes', ['target_type', 'target_id'], unique=False)
    op.create_index('ix_votes_user_id', 'votes', ['user_id'], unique=False)
    op.create_table('labels',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('community_level', postgresql.ENUM('city', 'county', 'state', 'federal', name='community_level_enum', create_type=False), nullable=False),
    sa.Column('community_entity_id', sa.Integer(), nullable=False),
    sa.Column('ai_action_id', sa.Integer(), nullable=True),
    sa.Column('main_category_id', sa.Integer(), nullable=True),
    sa.Column('umbrella_id', sa.Integer(), nullable=True),
    sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=True),
    sa.Column('outcome', postgresql.ENUM('unreviewed', 'confirmed_by_author', 'corrected_by_author', 'author_selected', name='labels_outcome_enum', create_type=False), server_default=sa.text("'unreviewed'"), nullable=False),
    sa.Column('corrected_umbrella_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['ai_action_id'], ['ai_actions.id'], ),
    sa.ForeignKeyConstraint(['corrected_umbrella_id'], ['umbrellas.id'], ),
    sa.ForeignKeyConstraint(['main_category_id'], ['main_categories.id'], ),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['umbrella_id'], ['umbrellas.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_labels_ai_action_id', 'labels', ['ai_action_id'], unique=False)
    op.create_index('ix_labels_corrected_umbrella_id', 'labels', ['corrected_umbrella_id'], unique=False)
    op.create_index('ix_labels_main_category_id', 'labels', ['main_category_id'], unique=False)
    op.create_index('ix_labels_post_id', 'labels', ['post_id'], unique=False)
    op.create_index('ix_labels_umbrella_id', 'labels', ['umbrella_id'], unique=False)
    op.create_table('post_communities',
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('community_level', postgresql.ENUM('city', 'county', 'state', 'federal', name='community_level_enum', create_type=False), nullable=False),
    sa.Column('community_entity_id', sa.Integer(), nullable=False),
    sa.Column('umbrella_id', sa.Integer(), nullable=True),
    sa.Column('main_category_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['main_category_id'], ['main_categories.id'], ),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['umbrella_id'], ['umbrellas.id'], ),
    sa.PrimaryKeyConstraint('post_id', 'community_level', 'community_entity_id')
    )
    op.create_index('ix_post_communities_community', 'post_communities', ['community_level', 'community_entity_id'], unique=False)
    op.create_index('ix_post_communities_main_category_id', 'post_communities', ['main_category_id'], unique=False)
    op.create_index('ix_post_communities_umbrella_id', 'post_communities', ['umbrella_id'], unique=False)
    op.create_table('post_solutions',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.SmallInteger(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('ai_contribution_percentage', sa.SmallInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id', 'position', name='uq_post_solutions_post_position')
    )
    op.create_index('ix_post_solutions_post_id', 'post_solutions', ['post_id'], unique=False)
    op.create_table('umbrella_references',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('umbrella_id', sa.Integer(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('source', postgresql.ENUM('user', 'ai', name='umbrella_references_source_enum', create_type=False), nullable=False),
    sa.Column('added_by', sa.Integer(), nullable=True),
    sa.Column('ai_action_id', sa.Integer(), nullable=True),
    sa.Column('status', postgresql.ENUM('active', 'rejected', name='umbrella_references_status_enum', create_type=False), server_default=sa.text("'active'"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['added_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['ai_action_id'], ['ai_actions.id'], ),
    sa.ForeignKeyConstraint(['umbrella_id'], ['umbrellas.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_umbrella_references_added_by', 'umbrella_references', ['added_by'], unique=False)
    op.create_index('ix_umbrella_references_ai_action_id', 'umbrella_references', ['ai_action_id'], unique=False)
    op.create_index('ix_umbrella_references_umbrella_id', 'umbrella_references', ['umbrella_id'], unique=False)
    op.create_table('reference_feedback',
    sa.Column('reference_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('useful', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['reference_id'], ['umbrella_references.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('reference_id', 'user_id')
    )
    op.create_index('ix_reference_feedback_user_id', 'reference_feedback', ['user_id'], unique=False)
    op.create_table('solutions',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('umbrella_id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=True),
    sa.Column('post_solution_id', sa.Integer(), nullable=True),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('current_version', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('net_score', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('is_dominant', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('dominant_since', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_ballot_cycle_id', sa.Integer(), nullable=True),
    sa.Column('last_ballot_result', postgresql.ENUM('passed', 'failed', 'held_back', name='solutions_last_ballot_result_enum', create_type=False), nullable=True),
    sa.Column('last_ballot_version', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['last_ballot_cycle_id'], ['cycles.id'], ),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ),
    sa.ForeignKeyConstraint(['post_solution_id'], ['post_solutions.id'], ),
    sa.ForeignKeyConstraint(['umbrella_id'], ['umbrellas.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_solutions_author_id', 'solutions', ['author_id'], unique=False)
    op.create_index('ix_solutions_last_ballot_cycle_id', 'solutions', ['last_ballot_cycle_id'], unique=False)
    op.create_index('ix_solutions_post_id', 'solutions', ['post_id'], unique=False)
    op.create_index('ix_solutions_post_solution_id', 'solutions', ['post_solution_id'], unique=False)
    op.create_index('ix_solutions_umbrella_id', 'solutions', ['umbrella_id'], unique=False)
    op.create_index('ix_solutions_umbrella_rank', 'solutions', ['umbrella_id', sa.literal_column('net_score DESC'), 'created_at'], unique=False)
    op.create_index('uq_solutions_post_solution_umbrella', 'solutions', ['post_solution_id', 'umbrella_id'], unique=True, postgresql_where=sa.text('post_solution_id IS NOT NULL'))
    op.create_table('amendments',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('solution_id', sa.Integer(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('proposed_text', sa.Text(), nullable=False),
    sa.Column('rationale', sa.Text(), nullable=False),
    sa.Column('status', postgresql.ENUM('proposed', 'absorbed', 'superseded', 'merged_into', 'withdrawn', name='amendments_status_enum', create_type=False), server_default=sa.text("'proposed'"), nullable=False),
    sa.Column('absorbed_as_version', sa.Integer(), nullable=True),
    sa.Column('merged_into_id', sa.Integer(), nullable=True),
    sa.Column('net_score', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('ai_contribution_percentage', sa.SmallInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['merged_into_id'], ['amendments.id'], ),
    sa.ForeignKeyConstraint(['solution_id'], ['solutions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_amendments_author_id', 'amendments', ['author_id'], unique=False)
    op.create_index('ix_amendments_merged_into_id', 'amendments', ['merged_into_id'], unique=False)
    op.create_index('ix_amendments_solution_id', 'amendments', ['solution_id'], unique=False)
    op.create_index('ix_amendments_solution_status', 'amendments', ['solution_id', 'status'], unique=False)
    op.create_table('ballot_items',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('cycle_id', sa.Integer(), nullable=False),
    sa.Column('solution_id', sa.Integer(), nullable=False),
    sa.Column('solution_version', sa.Integer(), nullable=False),
    sa.Column('umbrella_id', sa.Integer(), nullable=False),
    sa.Column('net_score_at_snapshot', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('held_back', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('yes_count', sa.Integer(), nullable=True),
    sa.Column('no_count', sa.Integer(), nullable=True),
    sa.Column('result', postgresql.ENUM('passed', 'failed', 'held_back', name='ballot_items_result_enum', create_type=False), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['cycle_id'], ['cycles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['solution_id'], ['solutions.id'], ),
    sa.ForeignKeyConstraint(['umbrella_id'], ['umbrellas.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('cycle_id', 'position', name='uq_ballot_items_cycle_position'),
    sa.UniqueConstraint('cycle_id', 'solution_id', name='uq_ballot_items_cycle_solution')
    )
    op.create_index('ix_ballot_items_cycle_id', 'ballot_items', ['cycle_id'], unique=False)
    op.create_index('ix_ballot_items_solution_id', 'ballot_items', ['solution_id'], unique=False)
    op.create_index('ix_ballot_items_umbrella_id', 'ballot_items', ['umbrella_id'], unique=False)
    op.create_table('amendment_similarity',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('amendment_a_id', sa.Integer(), nullable=False),
    sa.Column('amendment_b_id', sa.Integer(), nullable=False),
    sa.Column('score', sa.Numeric(precision=4, scale=3), nullable=False),
    sa.Column('ai_action_id', sa.Integer(), nullable=True),
    sa.Column('decision', postgresql.ENUM('pending', 'same', 'different', name='amendment_similarity_decision_enum', create_type=False), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('amendment_a_id < amendment_b_id', name='ck_amendment_similarity_ordered'),
    sa.ForeignKeyConstraint(['ai_action_id'], ['ai_actions.id'], ),
    sa.ForeignKeyConstraint(['amendment_a_id'], ['amendments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['amendment_b_id'], ['amendments.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('amendment_a_id', 'amendment_b_id', name='uq_amendment_similarity_pair')
    )
    op.create_index('ix_amendment_similarity_a', 'amendment_similarity', ['amendment_a_id'], unique=False)
    op.create_index('ix_amendment_similarity_ai_action_id', 'amendment_similarity', ['ai_action_id'], unique=False)
    op.create_index('ix_amendment_similarity_b', 'amendment_similarity', ['amendment_b_id'], unique=False)
    op.create_table('ballot_votes',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('ballot_item_id', sa.Integer(), nullable=False),
    sa.Column('voter_id', sa.Integer(), nullable=False),
    sa.Column('choice', postgresql.ENUM('yes', 'no', name='ballot_votes_choice_enum', create_type=False), nullable=False),
    sa.Column('voter_verification_level', postgresql.ENUM('unverified', 'phone', 'address', 'voter', name='verification_level_enum', create_type=False), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['ballot_item_id'], ['ballot_items.id'], ),
    sa.ForeignKeyConstraint(['voter_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('ballot_item_id', 'voter_id', name='uq_ballot_votes_item_voter')
    )
    op.create_index('ix_ballot_votes_ballot_item_id', 'ballot_votes', ['ballot_item_id'], unique=False)
    op.create_index('ix_ballot_votes_voter_id', 'ballot_votes', ['voter_id'], unique=False)
    op.create_table('jury_holdbacks',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('jury_id', sa.Integer(), nullable=False),
    sa.Column('juror_id', sa.Integer(), nullable=False),
    sa.Column('ballot_item_id', sa.Integer(), nullable=False),
    sa.Column('reason_category', postgresql.ENUM('duplicate', 'not_actionable', 'incomplete', 'outside_governance_level', 'other', name='jury_holdbacks_reason_category_enum', create_type=False), nullable=False),
    sa.Column('reason_text', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['ballot_item_id'], ['ballot_items.id'], ),
    sa.ForeignKeyConstraint(['juror_id'], ['jurors.id'], ),
    sa.ForeignKeyConstraint(['jury_id'], ['juries.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('juror_id', 'ballot_item_id', name='uq_jury_holdbacks_juror_item')
    )
    op.create_index('ix_jury_holdbacks_ballot_item_id', 'jury_holdbacks', ['ballot_item_id'], unique=False)
    op.create_index('ix_jury_holdbacks_juror_id', 'jury_holdbacks', ['juror_id'], unique=False)
    op.create_index('ix_jury_holdbacks_jury_id', 'jury_holdbacks', ['jury_id'], unique=False)
    op.create_table('solution_versions',
    sa.Column('id', sa.Integer(), sa.Identity(always=True), nullable=False),
    sa.Column('solution_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('amendment_id', sa.Integer(), nullable=True),
    sa.Column('ai_contribution_percentage', sa.SmallInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['amendment_id'], ['amendments.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['solution_id'], ['solutions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('solution_id', 'version', name='uq_solution_versions_solution_version')
    )
    op.create_index('ix_solution_versions_amendment_id', 'solution_versions', ['amendment_id'], unique=False)
    op.create_index('ix_solution_versions_created_by', 'solution_versions', ['created_by'], unique=False)
    op.create_index('ix_solution_versions_solution_id', 'solution_versions', ['solution_id'], unique=False)
    op.create_table('amendment_similarity_votes',
    sa.Column('similarity_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('choice', postgresql.ENUM('same', 'different', name='amendment_similarity_votes_choice_enum', create_type=False), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['similarity_id'], ['amendment_similarity.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('similarity_id', 'user_id')
    )
    op.create_index('ix_amendment_similarity_votes_user_id', 'amendment_similarity_votes', ['user_id'], unique=False)


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_amendment_similarity_votes_user_id', table_name='amendment_similarity_votes')
    op.drop_table('amendment_similarity_votes')
    op.drop_index('ix_solution_versions_solution_id', table_name='solution_versions')
    op.drop_index('ix_solution_versions_created_by', table_name='solution_versions')
    op.drop_index('ix_solution_versions_amendment_id', table_name='solution_versions')
    op.drop_table('solution_versions')
    op.drop_index('ix_jury_holdbacks_jury_id', table_name='jury_holdbacks')
    op.drop_index('ix_jury_holdbacks_juror_id', table_name='jury_holdbacks')
    op.drop_index('ix_jury_holdbacks_ballot_item_id', table_name='jury_holdbacks')
    op.drop_table('jury_holdbacks')
    op.drop_index('ix_ballot_votes_voter_id', table_name='ballot_votes')
    op.drop_index('ix_ballot_votes_ballot_item_id', table_name='ballot_votes')
    op.drop_table('ballot_votes')
    op.drop_index('ix_amendment_similarity_b', table_name='amendment_similarity')
    op.drop_index('ix_amendment_similarity_ai_action_id', table_name='amendment_similarity')
    op.drop_index('ix_amendment_similarity_a', table_name='amendment_similarity')
    op.drop_table('amendment_similarity')
    op.drop_index('ix_ballot_items_umbrella_id', table_name='ballot_items')
    op.drop_index('ix_ballot_items_solution_id', table_name='ballot_items')
    op.drop_index('ix_ballot_items_cycle_id', table_name='ballot_items')
    op.drop_table('ballot_items')
    op.drop_index('ix_amendments_solution_status', table_name='amendments')
    op.drop_index('ix_amendments_solution_id', table_name='amendments')
    op.drop_index('ix_amendments_merged_into_id', table_name='amendments')
    op.drop_index('ix_amendments_author_id', table_name='amendments')
    op.drop_table('amendments')
    op.drop_index('uq_solutions_post_solution_umbrella', table_name='solutions', postgresql_where=sa.text('post_solution_id IS NOT NULL'))
    op.drop_index('ix_solutions_umbrella_rank', table_name='solutions')
    op.drop_index('ix_solutions_umbrella_id', table_name='solutions')
    op.drop_index('ix_solutions_post_solution_id', table_name='solutions')
    op.drop_index('ix_solutions_post_id', table_name='solutions')
    op.drop_index('ix_solutions_last_ballot_cycle_id', table_name='solutions')
    op.drop_index('ix_solutions_author_id', table_name='solutions')
    op.drop_table('solutions')
    op.drop_index('ix_reference_feedback_user_id', table_name='reference_feedback')
    op.drop_table('reference_feedback')
    op.drop_index('ix_umbrella_references_umbrella_id', table_name='umbrella_references')
    op.drop_index('ix_umbrella_references_ai_action_id', table_name='umbrella_references')
    op.drop_index('ix_umbrella_references_added_by', table_name='umbrella_references')
    op.drop_table('umbrella_references')
    op.drop_index('ix_post_solutions_post_id', table_name='post_solutions')
    op.drop_table('post_solutions')
    op.drop_index('ix_post_communities_umbrella_id', table_name='post_communities')
    op.drop_index('ix_post_communities_main_category_id', table_name='post_communities')
    op.drop_index('ix_post_communities_community', table_name='post_communities')
    op.drop_table('post_communities')
    op.drop_index('ix_labels_umbrella_id', table_name='labels')
    op.drop_index('ix_labels_post_id', table_name='labels')
    op.drop_index('ix_labels_main_category_id', table_name='labels')
    op.drop_index('ix_labels_corrected_umbrella_id', table_name='labels')
    op.drop_index('ix_labels_ai_action_id', table_name='labels')
    op.drop_table('labels')
    op.drop_index('ix_votes_user_id', table_name='votes')
    op.drop_index('ix_votes_target', table_name='votes')
    op.drop_table('votes')
    op.drop_index('ix_posts_label_status', table_name='posts')
    op.drop_index('ix_posts_created_at', table_name='posts')
    op.drop_index('ix_posts_author_id', table_name='posts')
    op.drop_table('posts')
    op.drop_index('ix_jurors_user_id', table_name='jurors')
    op.drop_index('ix_jurors_replaced_by_id', table_name='jurors')
    op.drop_index('ix_jurors_jury_id', table_name='jurors')
    op.drop_table('jurors')
    op.drop_index('ix_comments_target', table_name='comments')
    op.drop_index('ix_comments_parent_id', table_name='comments')
    op.drop_index('ix_comments_author_id', table_name='comments')
    op.drop_table('comments')
    op.drop_index('ix_umbrellas_main_category_id', table_name='umbrellas')
    op.drop_index('ix_umbrellas_community', table_name='umbrellas')
    op.drop_table('umbrellas')
    op.drop_index('ix_summaries_published_at', table_name='summaries')
    op.drop_table('summaries')
    op.drop_table('juries')
    op.drop_table('main_categories')
    op.drop_index('uq_cycles_one_open_per_community', table_name='cycles', postgresql_where=sa.text("state <> 'published'"))
    op.drop_index('ix_cycles_community', table_name='cycles')
    op.drop_table('cycles')
    for name in _ENUMS:
        op.execute(f"DROP TYPE IF EXISTS {name}")
