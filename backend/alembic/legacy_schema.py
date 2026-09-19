"""Frozen legacy schema snapshot for additive adoption; never import application models."""
from alembic import op
import sqlalchemy as sa


def upgrade_legacy():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if 'schools' not in existing:
        op.create_table('schools',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
        )
    if 'schools' not in existing:
        op.create_index(op.f('ix_schools_id'), 'schools', ['id'], unique=False)
    if 'users' not in existing:
        op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('token_version', sa.Integer(), server_default='0', nullable=False),
        sa.Column('email_verified', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('must_change_password', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('school_id', sa.Integer(), nullable=True),
        sa.Column('oauth_provider', sa.String(length=50), nullable=True),
        sa.Column('oauth_id', sa.String(length=255), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'users' not in existing:
        op.create_index(op.f('ix_users_deleted_at'), 'users', ['deleted_at'], unique=False)
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
        op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
        op.create_index(op.f('ix_users_school_id'), 'users', ['school_id'], unique=False)
    if 'account_tokens' not in existing:
        op.create_table('account_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('purpose', sa.String(length=40), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'account_tokens' not in existing:
        op.create_index(op.f('ix_account_tokens_expires_at'), 'account_tokens', ['expires_at'], unique=False)
        op.create_index(op.f('ix_account_tokens_purpose'), 'account_tokens', ['purpose'], unique=False)
        op.create_index(op.f('ix_account_tokens_token_hash'), 'account_tokens', ['token_hash'], unique=True)
        op.create_index(op.f('ix_account_tokens_user_id'), 'account_tokens', ['user_id'], unique=False)
    if 'audit_logs' not in existing:
        op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('school_id', sa.Integer(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'audit_logs' not in existing:
        op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
        op.create_index(op.f('ix_audit_logs_actor_user_id'), 'audit_logs', ['actor_user_id'], unique=False)
        op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
        op.create_index(op.f('ix_audit_logs_school_id'), 'audit_logs', ['school_id'], unique=False)
        op.create_index(op.f('ix_audit_logs_target_id'), 'audit_logs', ['target_id'], unique=False)
        op.create_index(op.f('ix_audit_logs_target_type'), 'audit_logs', ['target_type'], unique=False)
    if 'bank_questions' not in existing:
        op.create_table('bank_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_user_id', sa.Integer(), nullable=True),
        sa.Column('school_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('difficulty', sa.String(), nullable=False),
        sa.Column('topic', sa.String(), nullable=True),
        sa.Column('grade', sa.Integer(), nullable=True),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('statements', sa.JSON(), nullable=True),
        sa.Column('sub_questions', sa.JSON(), nullable=True),
        sa.Column('answer', sa.JSON(), nullable=True),
        sa.Column('source', sa.JSON(), nullable=True),
        sa.Column('rich_content', sa.JSON(), nullable=True),
        sa.Column('content_metadata', sa.JSON(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'bank_questions' not in existing:
        op.create_index(op.f('ix_bank_questions_id'), 'bank_questions', ['id'], unique=False)
        op.create_index(op.f('ix_bank_questions_owner_user_id'), 'bank_questions', ['owner_user_id'], unique=False)
        op.create_index(op.f('ix_bank_questions_school_id'), 'bank_questions', ['school_id'], unique=False)
    if 'community_topics' not in existing:
        op.create_table('community_topics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('grade', sa.Integer(), nullable=True),
        sa.Column('type', sa.String(length=32), nullable=False),
        sa.Column('difficulty', sa.String(length=32), nullable=False),
        sa.Column('question', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'community_topics' not in existing:
        op.create_index(op.f('ix_community_topics_author_id'), 'community_topics', ['author_id'], unique=False)
        op.create_index(op.f('ix_community_topics_created_at'), 'community_topics', ['created_at'], unique=False)
        op.create_index(op.f('ix_community_topics_deleted_at'), 'community_topics', ['deleted_at'], unique=False)
        op.create_index(op.f('ix_community_topics_grade'), 'community_topics', ['grade'], unique=False)
        op.create_index(op.f('ix_community_topics_type'), 'community_topics', ['type'], unique=False)
    if 'exams' not in existing:
        op.create_table('exams',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_user_id', sa.Integer(), nullable=True),
        sa.Column('school_id', sa.Integer(), nullable=True),
        sa.Column('school', sa.String(), nullable=False),
        sa.Column('grade', sa.Integer(), nullable=False),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('exam_type', sa.String(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('school_year', sa.String(), nullable=False),
        sa.Column('total_score', sa.Float(), nullable=True),
        sa.Column('matrix', sa.JSON(), nullable=False),
        sa.Column('summary', sa.JSON(), nullable=False),
        sa.Column('specification', sa.JSON(), nullable=False),
        sa.Column('questions', sa.JSON(), nullable=False),
        sa.Column('answer_key', sa.JSON(), nullable=False),
        sa.Column('rubric', sa.JSON(), nullable=False),
        sa.Column('validation', sa.JSON(), nullable=False),
        sa.Column('resource_package', sa.JSON(), nullable=True),
        sa.Column('review_status', sa.JSON(), nullable=False),
        sa.Column('publication_status', sa.String(), server_default='verified', nullable=False),
        sa.Column('version_id', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'exams' not in existing:
        op.create_index(op.f('ix_exams_id'), 'exams', ['id'], unique=False)
        op.create_index(op.f('ix_exams_owner_user_id'), 'exams', ['owner_user_id'], unique=False)
        op.create_index(op.f('ix_exams_publication_status'), 'exams', ['publication_status'], unique=False)
        op.create_index(op.f('ix_exams_school_id'), 'exams', ['school_id'], unique=False)
    if 'uploaded_documents' not in existing:
        op.create_table('uploaded_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_user_id', sa.Integer(), nullable=True),
        sa.Column('school_id', sa.Integer(), nullable=True),
        sa.Column('sharing_scope', sa.String(length=16), server_default='private', nullable=False),
        sa.Column('sharing_status', sa.String(length=16), server_default='none', nullable=False),
        sa.Column('reviewed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_note', sa.String(length=1000), server_default='', nullable=False),
        sa.Column('version_id', sa.Integer(), server_default='1', nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('stored_filename', sa.String(), nullable=False),
        sa.Column('file_type', sa.String(), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('extracted_text', sa.Text(), nullable=False),
        sa.Column('parsed_data', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('grade', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'uploaded_documents' not in existing:
        op.create_index(op.f('ix_uploaded_documents_id'), 'uploaded_documents', ['id'], unique=False)
        op.create_index(op.f('ix_uploaded_documents_owner_user_id'), 'uploaded_documents', ['owner_user_id'], unique=False)
        op.create_index(op.f('ix_uploaded_documents_school_id'), 'uploaded_documents', ['school_id'], unique=False)
        op.create_index(op.f('ix_uploaded_documents_sharing_scope'), 'uploaded_documents', ['sharing_scope'], unique=False)
        op.create_index(op.f('ix_uploaded_documents_sharing_status'), 'uploaded_documents', ['sharing_status'], unique=False)
    if 'community_comments' not in existing:
        op.create_table('community_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['parent_id'], ['community_comments.id'], ),
        sa.ForeignKeyConstraint(['topic_id'], ['community_topics.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'community_comments' not in existing:
        op.create_index(op.f('ix_community_comments_topic_id'), 'community_comments', ['topic_id'], unique=False)

    is_postgresql = op.get_bind().dialect.name == 'postgresql'
    boolean_true = 'BOOLEAN NOT NULL DEFAULT TRUE' if is_postgresql else 'BOOLEAN NOT NULL DEFAULT 1'
    boolean_false = 'BOOLEAN NOT NULL DEFAULT FALSE' if is_postgresql else 'BOOLEAN NOT NULL DEFAULT 0'
    timestamp_type = 'TIMESTAMP WITH TIME ZONE' if is_postgresql else 'TIMESTAMP'
    required_by_table = {
        "exams": {
            "owner_user_id": "INTEGER",
            "school_id": "INTEGER",
            "publication_status": "VARCHAR(32) NOT NULL DEFAULT 'verified'",
            "version_id": "INTEGER NOT NULL DEFAULT 1",
        },
        "uploaded_documents": {
            "owner_user_id": "INTEGER", "school_id": "INTEGER",
            "sharing_scope": "VARCHAR(16) NOT NULL DEFAULT 'private'",
            "sharing_status": "VARCHAR(16) NOT NULL DEFAULT 'none'",
            "reviewed_by_user_id": "INTEGER",
            "reviewed_at": timestamp_type,
            "review_note": "VARCHAR(1000) NOT NULL DEFAULT ''",
            "version_id": "INTEGER NOT NULL DEFAULT 1",
        },
        "bank_questions": {"owner_user_id": "INTEGER", "school_id": "INTEGER", "rich_content": "JSON", "content_metadata": "JSON"},
        "users": {
            "token_version": "INTEGER NOT NULL DEFAULT 0",
            "email_verified": boolean_true,
            "must_change_password": boolean_false,
            "deleted_at": timestamp_type,
        },
    }

    for table_name, required in required_by_table.items():
        columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table_name)}
        for name, definition in required.items():
            if name not in columns:
                op.execute(sa.text(f'ALTER TABLE {table_name} ADD COLUMN {name} {definition}'))
