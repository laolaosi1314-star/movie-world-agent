"""Phase 2 & Phase 3 迁移：公司系统 + 市场票房模型 + 电影节 + 奖项体系。

包含：
  - 新增枚举：company_type/company_status/company_style/market_outcome/
    festival_level/festival_section/edition_status/award_narrative_tag
  - 新建表：companies/company_history/market_snapshots/project_market
    festivals/festival_editions/festival_selections/festival_awards
    awards/award_seasons/award_categories/nominations/winners/
    award_season_stats/award_achievements
  - 修改既有表：characters.company_id、projects.company_id 补为正式 FK；
    projects 新增 distribution_company_id（发行公司 FK）。

注意：设计文档称 awards/nominations/winners 等"已在 Phase 1 建表"，但 0001_initial
实际未创建，故此处正式建表（见 BLUEPRINT.md【返工点】）。

Revision ID: 0002_phase2_phase3
Revises: 0001_initial
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_phase2_phase3"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- 枚举 ----------
    company_type = postgresql.ENUM(
        "production", "distribution", "agency", "streaming", "capital", name="company_type")
    company_type.create(op.get_bind(), checkfirst=True)
    company_status = postgresql.ENUM(
        "active", "dormant", "merging", "bankrupt", name="company_status")
    company_status.create(op.get_bind(), checkfirst=True)
    company_style = postgresql.ENUM(
        "commercial_blockbuster", "arthouse", "newcomer_director",
        "tv_focused", "variety", name="company_style")
    company_style.create(op.get_bind(), checkfirst=True)
    market_outcome = postgresql.ENUM(
        "blockbuster", "sleeper_hit", "word_of_mouth_reversal", "high_open_low_close",
        "flop_but_awarded", "hit_but_no_award", "cult_classic", "normal", name="market_outcome")
    market_outcome.create(op.get_bind(), checkfirst=True)
    festival_level = postgresql.ENUM(
        "international_a", "international_b", "national_a", "national_b", "regional",
        name="festival_level")
    festival_level.create(op.get_bind(), checkfirst=True)
    festival_section = postgresql.ENUM(
        "main_competition", "special_screening", "newcomer", "documentary", "short",
        name="festival_section")
    festival_section.create(op.get_bind(), checkfirst=True)
    edition_status = postgresql.ENUM(
        "upcoming", "ongoing", "completed", name="edition_status")
    edition_status.create(op.get_bind(), checkfirst=True)
    award_narrative_tag = postgresql.ENUM(
        "biggest_winner", "biggest_snub", "biggest_upset", "youngest_winner", "oldest_winner",
        "consecutive_noms", "back_to_back", "sweep", "double_nom", "double_win",
        "most_controversial", name="award_narrative_tag")
    award_narrative_tag.create(op.get_bind(), checkfirst=True)

    # ---------- 公司系统 ----------
    op.create_table(
        "companies",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", company_type, nullable=False, server_default="production"),
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("status", company_status, nullable=False, server_default="active"),
        sa.Column("style_tag", company_style, nullable=True),
        sa.Column("capital", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("cash", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("market_share", sa.Numeric(), nullable=True),
        sa.Column("talent_resources", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("production_capability", sa.Numeric(), nullable=True),
        sa.Column("distribution_capability", sa.Numeric(), nullable=True),
        sa.Column("art_reputation", sa.Numeric(), nullable=True),
        sa.Column("commercial_reputation", sa.Numeric(), nullable=True),
        sa.Column("industry_position", sa.String(50), nullable=True),
        sa.Column("attributes", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_comp_world", "companies", ["world_id", "type"])

    op.create_table(
        "company_history",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_comphist", "company_history", ["company_id", "year"])

    # ---------- 市场系统 ----------
    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("tick_id", sa.BigInteger(), sa.ForeignKey("simulation_ticks.id"), nullable=True),
        sa.Column("snapshot_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("environment", sa.String(50), nullable=True),
        sa.Column("heat", sa.Numeric(), nullable=True),
        sa.Column("total_box_office", sa.Numeric(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_msnap_world", "market_snapshots", ["world_id", "snapshot_date"])

    op.create_table(
        "project_market",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("tick_id", sa.BigInteger(), sa.ForeignKey("simulation_ticks.id"), nullable=True),
        sa.Column("release_slot", sa.String(50), nullable=True),
        sa.Column("box_office", sa.Numeric(), nullable=True),
        sa.Column("audience_score", sa.Numeric(), nullable=True),
        sa.Column("media_score", sa.Numeric(), nullable=True),
        sa.Column("factors", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("word_of_mouth_trajectory", sa.String(50), nullable=True),
        sa.Column("outcome", market_outcome, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pmk_project", "project_market", ["project_id"])

    # ---------- 电影节系统 ----------
    op.create_table(
        "festivals",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(100), nullable=True),
        sa.Column("level", festival_level, nullable=True),
        sa.Column("positioning", sa.Text(), nullable=True),
        sa.Column("selection_rules", postgresql.JSONB(), nullable=True),
        sa.Column("jury", postgresql.JSONB(), nullable=True),
        sa.Column("units", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "festival_editions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("festival_id", sa.BigInteger(), sa.ForeignKey("festivals.id"), nullable=False),
        sa.Column("edition_number", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("status", edition_status, nullable=False, server_default="upcoming"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_fested", "festival_editions", ["festival_id", "year"])

    op.create_table(
        "festival_selections",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("edition_id", sa.BigInteger(), sa.ForeignKey("festival_editions.id"), nullable=False),
        sa.Column("section", festival_section, nullable=False),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("selection_type", sa.String(20), nullable=False, server_default="selected"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_festsel", "festival_selections", ["edition_id", "section"])

    op.create_table(
        "festival_awards",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("edition_id", sa.BigInteger(), sa.ForeignKey("festival_editions.id"), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("winner_project_id", sa.BigInteger(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("winner_character_id", sa.BigInteger(), sa.ForeignKey("characters.id"), nullable=True),
        sa.Column("is_user_override", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_festaw", "festival_awards", ["edition_id"])

    # ---------- 奖项体系（正式建表） ----------
    op.create_table(
        "awards",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.Column("organizer", sa.String(200), nullable=True),
        sa.Column("positioning", sa.Text(), nullable=True),
        sa.Column("level", sa.String(50), nullable=True),
        sa.Column("rules", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "award_seasons",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("award_id", sa.BigInteger(), sa.ForeignKey("awards.id"), nullable=False),
        sa.Column("season_number", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="upcoming"),
        sa.Column("ceremony_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "award_categories",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("award_id", sa.BigInteger(), sa.ForeignKey("awards.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("rules", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_awcat", "award_categories", ["award_id"])

    op.create_table(
        "nominations",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("season_id", sa.BigInteger(), sa.ForeignKey("award_seasons.id"), nullable=False),
        sa.Column("category_id", sa.BigInteger(), sa.ForeignKey("award_categories.id"), nullable=False),
        sa.Column("category_name", sa.String(100), nullable=False),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("character_id", sa.BigInteger(), sa.ForeignKey("characters.id"), nullable=True),
        sa.Column("is_user_override", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "winners",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("season_id", sa.BigInteger(), sa.ForeignKey("award_seasons.id"), nullable=False),
        sa.Column("category_id", sa.BigInteger(), sa.ForeignKey("award_categories.id"), nullable=False),
        sa.Column("category_name", sa.String(100), nullable=False),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("character_id", sa.BigInteger(), sa.ForeignKey("characters.id"), nullable=True),
        sa.Column("is_user_override", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "award_season_stats",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("season_id", sa.BigInteger(), sa.ForeignKey("award_seasons.id"), nullable=False),
        sa.Column("tag", award_narrative_tag, nullable=False),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_awstat", "award_season_stats", ["season_id"])

    op.create_table(
        "award_achievements",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("award_id", sa.BigInteger(), sa.ForeignKey("awards.id"), nullable=False),
        sa.Column("character_id", sa.BigInteger(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("nominations_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("award_id", "character_id", name="uq_achv_award_char"),
    )

    # ---------- 收口既有表的 FK ----------
    op.create_foreign_key("fk_char_company", "characters", "companies",
                          ["company_id"], ["id"])
    op.create_foreign_key("fk_proj_prod_co", "projects", "companies",
                          ["company_id"], ["id"])
    op.add_column("projects", sa.Column("distribution_company_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_proj_dist_co", "projects", "companies",
                          ["distribution_company_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_proj_dist_co", "projects", type_="foreignkey")
    op.drop_column("projects", "distribution_company_id")
    op.drop_constraint("fk_proj_prod_co", "projects", type_="foreignkey")
    op.drop_constraint("fk_char_company", "characters", type_="foreignkey")

    op.drop_table("award_achievements")
    op.drop_index("ix_awstat", "award_season_stats")
    op.drop_table("award_season_stats")
    op.drop_table("winners")
    op.drop_table("nominations")
    op.drop_index("ix_awcat", "award_categories")
    op.drop_table("award_categories")
    op.drop_table("award_seasons")
    op.drop_table("awards")

    op.drop_index("ix_festaw", "festival_awards")
    op.drop_table("festival_awards")
    op.drop_index("ix_festsel", "festival_selections")
    op.drop_table("festival_selections")
    op.drop_index("ix_fested", "festival_editions")
    op.drop_table("festival_editions")
    op.drop_table("festivals")

    op.drop_index("ix_pmk_project", "project_market")
    op.drop_table("project_market")
    op.drop_index("ix_msnap_world", "market_snapshots")
    op.drop_table("market_snapshots")

    op.drop_index("ix_comphist", "company_history")
    op.drop_table("company_history")
    op.drop_index("ix_comp_world", "companies")
    op.drop_table("companies")

    op.execute("DROP TYPE IF EXISTS award_narrative_tag")
    op.execute("DROP TYPE IF EXISTS edition_status")
    op.execute("DROP TYPE IF EXISTS festival_section")
    op.execute("DROP TYPE IF EXISTS festival_level")
    op.execute("DROP TYPE IF EXISTS market_outcome")
    op.execute("DROP TYPE IF EXISTS company_style")
    op.execute("DROP TYPE IF EXISTS company_status")
    op.execute("DROP TYPE IF EXISTS company_type")
