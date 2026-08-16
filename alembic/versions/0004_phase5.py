"""Phase 5: 长期记忆三层落地 —— 扩展 memories 表。

在既有 memories 表（world_id/agent/scope/key/value/expires_at/created_at）上
新增支撑"写入/检索/衰减"机制的字段：
  - importance         记忆重要度 0~1，决定检索权重与是否巩固为长期
  - access_count       被召回次数，强化检索权重（频率因子）
  - last_accessed_tick 最近一次被召回/写入的 tick 索引，用于确定性遗忘曲线
  - expires_tick       短期记忆的物理过期 tick（配合 expires_at），到点清理
  - is_dormant         长期记忆被遗忘曲线判定为"休眠"的标记（仍保留，可被强线索唤回）

迁移对已有行安全（全部带 server_default / nullable）。
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_phase5"
down_revision = "0003_phase4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 重要度（0~1），默认 0.5
    op.add_column(
        "memories",
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
    )
    # 被召回次数，默认 0
    op.add_column(
        "memories",
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
    )
    # 最近访问 tick（用于遗忘曲线），可为空（写入时再填）
    op.add_column(
        "memories",
        sa.Column("last_accessed_tick", sa.BigInteger(), nullable=True),
    )
    # 短期记忆物理过期的 tick 边界
    op.add_column(
        "memories",
        sa.Column("expires_tick", sa.BigInteger(), nullable=True),
    )
    # 长期记忆休眠标记，默认未休眠
    op.add_column(
        "memories",
        sa.Column("is_dormant", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("memories", "is_dormant")
    op.drop_column("memories", "expires_tick")
    op.drop_column("memories", "last_accessed_tick")
    op.drop_column("memories", "access_count")
    op.drop_column("memories", "importance")
