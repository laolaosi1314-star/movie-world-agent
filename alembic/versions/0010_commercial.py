"""§17.1 商业时尚与塌房违约金：品牌代言 + 杂志封面 + 人物商业价值。

落地的数据模型变更（向后兼容、纯新增，不改动任何既有表/列）：
  - 新建枚举 endorsement_tier / contract_status / magazine_tier；
  - 新建表 endorsements（品牌代言合约）与 magazine_covers（杂志封面）；
  - 向 characters 表追加 commercial_value（Numeric，可空）列，承载人物商业价值；
  - 不删除任何表/列/枚举值；旧世界升级后自动获得商业生态能力。

contract_status 为代言与封面共用的状态机（active/terminated/breached/expired）。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_commercial"
down_revision = "0009_scandal_crisis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- 枚举 ----------
    endorsement_tier = postgresql.ENUM(
        "top_luxury", "high_luxury", "mass", "brand_friend", name="endorsement_tier",
    )
    endorsement_tier.create(op.get_bind(), checkfirst=True)

    contract_status = postgresql.ENUM(
        "active", "terminated", "breached", "expired", name="contract_status",
    )
    contract_status.create(op.get_bind(), checkfirst=True)

    magazine_tier = postgresql.ENUM(
        "top5", "second_tier", name="magazine_tier",
    )
    magazine_tier.create(op.get_bind(), checkfirst=True)

    # ---------- 表：endorsements ----------
    op.create_table(
        "endorsements",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("character_id", sa.BigInteger(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("brand_name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("tier", endorsement_tier, nullable=False, server_default="mass"),
        sa.Column("annual_fee", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("penalty_rate", sa.Numeric(), nullable=False, server_default="0.5"),
        sa.Column("has_morals_clause", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("signed_tick", sa.BigInteger(), nullable=False),
        sa.Column("duration_ticks", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("status", contract_status, nullable=False, server_default="active"),
        sa.Column("terminated_tick", sa.BigInteger()),
        sa.Column("penalty_amount", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )
    op.create_index("ix_endorsements_world_char", "endorsements",
                    ["world_id", "character_id"])
    op.create_index("ix_endorsements_world_status", "endorsements",
                    ["world_id", "status"])

    # ---------- 表：magazine_covers ----------
    op.create_table(
        "magazine_covers",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("character_id", sa.BigInteger(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("magazine_name", sa.String(200), nullable=False),
        sa.Column("tier", magazine_tier, nullable=False, server_default="second_tier"),
        sa.Column("issue_tick", sa.BigInteger(), nullable=False),
        sa.Column("theme", sa.String(200)),
        sa.Column("fee", sa.Integer()),
        sa.Column("prestige", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", contract_status, nullable=False, server_default="active"),
        sa.Column("cancelled_tick", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )
    op.create_index("ix_magazine_covers_world_char", "magazine_covers",
                    ["world_id", "character_id"])

    # ---------- 人物商业价值列 ----------
    op.add_column("characters",
                  sa.Column("commercial_value", sa.Numeric(), nullable=True))


def downgrade() -> None:
    op.drop_index("ix_magazine_covers_world_char", table_name="magazine_covers")
    op.drop_table("magazine_covers")
    op.drop_index("ix_endorsements_world_status", table_name="endorsements")
    op.drop_index("ix_endorsements_world_char", table_name="endorsements")
    op.drop_table("endorsements")
    op.drop_column("characters", "commercial_value")

    # PG 不支持从既有枚举移除值；以下枚举随表删除而弃用，保留无害。
    sa.Enum(name="magazine_tier").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="contract_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="endorsement_tier").drop(op.get_bind(), checkfirst=True)
