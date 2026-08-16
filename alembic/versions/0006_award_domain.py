"""Phase 3.x：多领域 / 跨界奖项体系（电视·音乐）扩展。

落地的数据模型变更（向后兼容、不新增表）：
  - 新建枚举 work_domain(film/tv/music)、category_kind(11 个客体种类)；
  - awards.domain / award_categories.domain（默认 film，既有电影奖行零冲击）；
  - award_categories.kind（默认 project，并按类别名回填既有行）；
  - project_market 加 domain / rating / sales / streams / chart_position（全部 nullable）；
  - ProjectType 扩展 ALBUM/SINGLE、CharacterType 扩展 SINGER（ALTER TYPE ADD VALUE）。

既有电影奖/类别数据（无 domain/kind 列）升级时自动获得 'film'/'project'，
类别名 -> kind 的映射在 upgrade 内回填。不删除任何表或列。
PostgreSQL 12+ 支持在事务块内 ALTER TYPE ADD VALUE（本工程目标 PG 16），可安全执行。

Revision ID: 0006_award_domain
Revises: 0005_add_award_type
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_award_domain"
down_revision = "0005_add_award_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- 枚举 ----------
    work_domain = postgresql.ENUM("film", "tv", "music", name="work_domain")
    work_domain.create(op.get_bind(), checkfirst=True)

    category_kind = postgresql.ENUM(
        "project", "director", "actor_male", "actor_female", "writer",
        "album", "single", "singer_male", "singer_female", "lyricist", "composer",
        name="category_kind",
    )
    category_kind.create(op.get_bind(), checkfirst=True)

    # ---------- awards.domain ----------
    op.add_column("awards", sa.Column(
        "domain", work_domain, nullable=False, server_default="film"))
    op.execute("UPDATE awards SET domain = 'film' WHERE domain IS NULL")
    op.alter_column("awards", "domain", server_default="film")

    # ---------- award_categories.domain ----------
    op.add_column("award_categories", sa.Column(
        "domain", work_domain, nullable=False, server_default="film"))
    op.execute("UPDATE award_categories SET domain = 'film' WHERE domain IS NULL")
    op.alter_column("award_categories", "domain", server_default="film")

    # ---------- award_categories.kind ----------
    op.add_column("award_categories", sa.Column(
        "kind", category_kind, nullable=False, server_default="project"))
    op.execute("UPDATE award_categories SET kind = 'project' WHERE kind IS NULL")
    # 既有（电影）类别按名回填 kind
    op.execute("UPDATE award_categories SET kind = 'director'   WHERE name IN ('最佳导演','最差导演')")
    op.execute("UPDATE award_categories SET kind = 'actor_male' WHERE name IN ('最佳男演员','最差男演员')")
    op.execute("UPDATE award_categories SET kind = 'actor_female' WHERE name IN ('最佳女演员','最差女演员')")
    op.execute("UPDATE award_categories SET kind = 'writer'     WHERE name IN ('最佳编剧','最差编剧')")
    op.alter_column("award_categories", "kind", server_default="project")

    # ---------- project_market 领域指标（全部 nullable，film 行留 NULL）----------
    op.add_column("project_market", sa.Column("domain", work_domain))
    op.add_column("project_market", sa.Column("rating", sa.Numeric()))
    op.add_column("project_market", sa.Column("sales", sa.Numeric()))
    op.add_column("project_market", sa.Column("streams", sa.Numeric()))
    op.add_column("project_market", sa.Column("chart_position", sa.Integer()))

    # ---------- 扩展既有枚举值（PG 12+ 支持事务内 ADD VALUE）----------
    op.execute("ALTER TYPE project_type ADD VALUE IF NOT EXISTS 'album'")
    op.execute("ALTER TYPE project_type ADD VALUE IF NOT EXISTS 'single'")
    op.execute("ALTER TYPE character_type ADD VALUE IF NOT EXISTS 'singer'")


def downgrade() -> None:
    # 回退顺序：先丢弃引用新枚举的列，再丢弃枚举类型本身。
    # 注：PG 不支持从既有枚举移除值（album/single/singer），保留无害；
    #     此处仅回退本迁移新增的列与枚举类型，使 schema 回到 0005 形态。
    op.drop_column("project_market", "chart_position")
    op.drop_column("project_market", "streams")
    op.drop_column("project_market", "sales")
    op.drop_column("project_market", "rating")
    op.drop_column("project_market", "domain")

    op.drop_column("award_categories", "kind")
    op.drop_column("award_categories", "domain")
    op.drop_column("awards", "domain")

    sa.Enum(name="category_kind").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="work_domain").drop(op.get_bind(), checkfirst=True)
