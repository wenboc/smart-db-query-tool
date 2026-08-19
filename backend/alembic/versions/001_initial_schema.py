"""初始数据库结构。

修订版本：001
上一版本：
创建日期：2025-11-16

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# Alembic 使用的修订版本标识
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建初始数据库结构。"""
    # 数据库连接表
    op.create_table(
        'databaseconnections',
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_connected_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint('name'),
    )
    op.create_index(op.f('ix_databaseconnections_url'), 'databaseconnections', ['url'], unique=False)

    # 数据库元数据表
    op.create_table(
        'databasemetadata',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('database_name', sa.String(length=50), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.Column('table_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['database_name'], ['databaseconnections.name'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_databasemetadata_database_name'), 'databasemetadata', ['database_name'], unique=False)

    # 查询历史表
    op.create_table(
        'queryhistory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('database_name', sa.String(length=50), nullable=False),
        sa.Column('sql_text', sa.Text(), nullable=False),
        sa.Column('executed_at', sa.DateTime(), nullable=False),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('query_source', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['database_name'], ['databaseconnections.name'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_query_history_executed_at', 'queryhistory', ['executed_at'], unique=False)


def downgrade() -> None:
    """删除初始数据库结构。"""
    op.drop_index('idx_query_history_executed_at', table_name='queryhistory')
    op.drop_table('queryhistory')
    op.drop_index(op.f('ix_databasemetadata_database_name'), table_name='databasemetadata')
    op.drop_table('databasemetadata')
    op.drop_index(op.f('ix_databaseconnections_url'), table_name='databaseconnections')
    op.drop_table('databaseconnections')
