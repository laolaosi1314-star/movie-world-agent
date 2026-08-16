"""§17.3 舆论与危机公关：黑料/丑闻 + 多阶段公关。

落地的数据模型变更（向后兼容、纯新增，不改动任何既有表/列）：
  - 新建枚举 scandal_type / scandal_stage / pr_strategy；
  - 新建表 scandals（黑料/丑闻全生命周期）与 crisis_pr（公关动作留痕+确定性结算）；
  - 向 intervention_type 枚举追加 'scandal' / 'crisis_pr'，使玩家（GM/运营）的
    舆论干预可经 Intervention 审计（PG16 支持事务内 ALTER TYPE ADD VALUE）。

不删除任何表/列/枚举值；旧世界升级后自动获得新能力。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_scandal_crisis"
down_revision = "0008_intervention_financing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- 枚举 ----------
    scandal_type = postgresql.ENUM(
        "affair", "drugs", "tax", "slip_of_tongue", "surrogacy",
        "plagiarism", "domestic_violence", "other", name="scandal_type",
    )
    scandal_type.create(op.get_bind(), checkfirst=True)

    scandal_stage = postgresql.ENUM(
        "latent", "spreading", "erupted", "resolving", "resolved", "collapsed",
        name="scandal_stage",
    )
    scandal_stage.create(op.get_bind(), checkfirst=True)

    pr_strategy = postgresql.ENUM(
        "cold_treatment", "lawyer_letter", "apology",
        "buy_trending", "counter_mkt", name="pr_strategy",
    )
    pr_strategy.create(op.get_bind(), checkfirst=True)

    # ---------- 表：scandals ----------
    op.create_table(
        "scandals",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("character_id", sa.BigInteger(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("related_project_id", sa.BigInteger(), sa.ForeignKey("projects.id")),
        sa.Column("scandal_type", scandal_type, nullable=False, server_default="other"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("evidence_strength", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stage", scandal_stage, nullable=False, server_default="latent"),
        sa.Column("heat", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("public_opinion", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("exposed_tick", sa.BigInteger()),
        sa.Column("erupted_tick", sa.BigInteger()),
        sa.Column("resolved_tick", sa.BigInteger()),
        sa.Column("created_by", sa.String(100), server_default="system"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )
    op.create_index("ix_scandals_world_stage", "scandals", ["world_id", "stage"])

    # ---------- 表：crisis_pr ----------
    op.create_table(
        "crisis_pr",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("scandal_id", sa.BigInteger(), sa.ForeignKey("scandals.id"), nullable=False),
        sa.Column("strategy", pr_strategy, nullable=False),
        sa.Column("by_player_id", sa.String(100)),
        sa.Column("impact", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---------- 扩展 intervention_type 枚举（审计舆论干预）----------
    op.execute("ALTER TYPE intervention_type ADD VALUE IF NOT EXISTS 'scandal'")
    op.execute("ALTER TYPE intervention_type ADD VALUE IF NOT EXISTS 'crisis_pr'")


def downgrade() -> None:
    op.drop_index("ix_scandals_world_stage", table_name="scandals")
    op.drop_table("crisis_pr")
    op.drop_table("scandals")

    # PG 不支持从既有枚举移除值（scandal/crisis_pr）；保留无害，不与任何约束冲突。
    sa.Enum(name="pr_strategy").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="scandal_stage").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="scandal_type").drop(op.get_bind(), checkfirst=True)
