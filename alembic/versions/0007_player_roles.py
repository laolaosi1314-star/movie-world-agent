"""Phase 6：用户角色体系 —— player_role 枚举 + players 表。

新增内容（不改动任何既有表/列，向后兼容）：
  - 枚举 player_role(audience/critic/investor/gm)；
  - 新表 players：world_id(外键,索引) / name / role / player_key(唯一索引) /
    critic_domains(jsonb) / bio / is_active / 时间戳。
  - 无状态鉴权载体 player_key 唯一且不可为空，由服务端在创建时一次性生成。

PostgreSQL 12+ 支持事务内创建枚举与表，故 upgrade/downgrade 均以单事务执行。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_player_roles"
down_revision = "0006_award_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- 枚举 ----------
    player_role = postgresql.ENUM(
        "audience", "critic", "investor", "gm", name="player_role"
    )
    player_role.create(op.get_bind(), checkfirst=True)

    # ---------- 表 ----------
    op.create_table(
        "players",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("audience", "critic", "investor", "gm", name="player_role"),
            nullable=False,
            server_default="audience",
        ),
        sa.Column("player_key", sa.String(length=64), nullable=False),
        sa.Column("critic_domains", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_players_world_id", "players", ["world_id"])
    op.create_index("ix_players_player_key", "players", ["player_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_players_player_key", table_name="players")
    op.drop_index("ix_players_world_id", table_name="players")
    op.drop_table("players")
    # PG 不支持从枚举移除值，但可整体删除（无其它表引用 player_role 时安全）。
    op.execute("DROP TYPE IF EXISTS player_role")
