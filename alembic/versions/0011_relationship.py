"""§17.2 人际情感网络：情感关系模型（恋情/绯闻/结婚生子 + 粉丝蝴蝶效应）。

落地的数据模型变更（向后兼容、纯新增，不改动任何既有表/列）：
  - 新建枚举 romance_type / romance_status；
  - 新建表 romances（人物 a/b 的情感关系，含公开度/子女/状态机/各 tick 锚点）；
  - 不删除任何表/列/枚举值；旧世界升级后自动获得情感网络能力。

人生档案馆（LifeArchive）为只读聚合接口，不新建任何表。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_relationship"
down_revision = "0010_commercial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- 枚举 ----------
    romance_type = postgresql.ENUM(
        "dating", "rumor", "married", "cohabit", name="romance_type",
    )
    romance_type.create(op.get_bind(), checkfirst=True)

    romance_status = postgresql.ENUM(
        "active", "ended", name="romance_status",
    )
    romance_status.create(op.get_bind(), checkfirst=True)

    # ---------- 表：romances ----------
    op.create_table(
        "romances",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("character_a_id", sa.BigInteger(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("character_b_id", sa.BigInteger(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("romance_type", romance_type, nullable=False, server_default="dating"),
        sa.Column("status", romance_status, nullable=False, server_default="active"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("publicness", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reacted_tick", sa.BigInteger()),
        sa.Column("child_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_tick", sa.BigInteger(), nullable=False),
        sa.Column("ended_tick", sa.BigInteger()),
        sa.Column("ended_reason", sa.Text()),
        sa.Column("created_by", sa.String(100)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )
    op.create_index("ix_romances_world", "romances", ["world_id"])
    op.create_index("ix_romances_world_char", "romances",
                    ["world_id", "character_a_id", "character_b_id"])


def downgrade() -> None:
    op.drop_index("ix_romances_world_char", table_name="romances")
    op.drop_index("ix_romances_world", table_name="romances")
    op.drop_table("romances")

    # PG 不支持从既有枚举移除值；以下枚举随表删除而弃用，保留无害。
    sa.Enum(name="romance_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="romance_type").drop(op.get_bind(), checkfirst=True)
