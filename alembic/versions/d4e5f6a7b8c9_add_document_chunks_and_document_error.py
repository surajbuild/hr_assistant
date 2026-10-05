"""add document_chunks table and documents.error_message

Revision ID: d4e5f6a7b8c9
Revises: c0b131e5fbaa
Create Date: 2026-10-05 12:00:00.000000

Stores the RAG index: one row per text chunk of an uploaded HR document,
with its source page and a sparse term-frequency vector (JSON) used for
BM25 similarity search (see PROJECT_DECISIONS.md D-004).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c0b131e5fbaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('page', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('term_vector', sa.Text(length=16777215), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'])
    op.add_column('documents', sa.Column('error_message', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'error_message')
    op.drop_index('ix_document_chunks_document_id', table_name='document_chunks')
    op.drop_table('document_chunks')
