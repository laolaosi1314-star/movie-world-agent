"""Phase 6 前置：负面奖项体系。

为奖项体系引入正/负面区分：
  - 新增枚举 award_type(positive/negative)
  - awards.award_type / award_categories.award_type 两列（默认 positive，兼容既有行）

既有正奖数据（无 award_type 列）会在升级时自动获得 'positive'，无需回填逻辑。
不删除任何表或列，向后兼容。

Revision ID: 0005_add_award_type
Revises: 0004_phase5
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_add_award_type"
down_revision = "0004_phase5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- 枚举 ----------
    award_type = postgresql.ENUM(
        "positive", "negative", name="award_type")
    award_type.create(op.get_bind(), checkfirst=True)

    # ---------- awards.award_type ----------
    op.add_column("awards", sa.Column(
        "award_type", award_type, nullable=False, server_default="positive"))
    # 历史行强制置为正奖（NULL 不可能，因有 server_default，仅保险）
    op.execute("UPDATE awards SET award_type = 'positive' WHERE award_type IS NULL")
    op.alter_column("awards", "award_type", server_default="positive")

    # ---------- award_categories.award_type ----------
    op.add_column("award_categories", sa.Column(
        "award_type", award_type, nullable=False, server_default="positive"))
    op.execute("UPDATE award_categories SET award_type = 'positive' WHERE award_type IS NULL")
    op.alter_column("award_categories", "award_type", server_default="positive")


def downgrade() -> None:
    op.drop_column("award_categories", "award_type")
    op.drop_column("awards", "award_type")
    sa.Enum(name="award_type").drop(op.get_bind(), checkfirst=True)
