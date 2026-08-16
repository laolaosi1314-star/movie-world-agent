"""Phase 6（二）：为 intervention_type 枚举新增 financing 值。

项目融资（投资人注资）需以 Intervention(FINANCING) 留痕审计，
故向既有枚举追加 'financing'。PG16 支持在事务内 ALTER TYPE ADD VALUE。
向后兼容：不新增表、不新增列；旧干预记录不受影响。
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_intervention_financing"
down_revision = "0007_player_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE intervention_type ADD VALUE IF NOT EXISTS 'financing'")


def downgrade() -> None:
    # PG 不支持从枚举移除值；该值仅被融资留痕使用，移除枚举值代价过高且无必要，
    # 故 downgrade 保留枚举值（无害，不与任何约束冲突）。
    pass
