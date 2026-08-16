"""初始迁移：MW + Phase 1 全部核心表。

包含：世界(存档)/tick、人物系统、作品系统、事件日志、上帝模式审计、Agent 记忆。
（Phase 2 公司/市场、Phase 3 电影节/奖项的表将在后续迁移中追加。）

Revision ID: 0001_initial
Revises: 
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- 枚举 ----------
    op.create_table(
        "world",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, server_default="影视世界"),
        sa.Column("current_year", sa.Integer(), nullable=False, server_default="2032"),
        sa.Column("current_month", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("industry_status", sa.String(50), nullable=False, server_default="繁荣"),
        sa.Column("rng_seed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_ticks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", postgresql.ENUM("active", "archived", name="world_status"),
                  nullable=False, server_default="active"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("seed_config", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "simulation_ticks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("tick_index", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("from_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("to_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rng_seed_used", sa.BigInteger(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tick_world", "simulation_ticks", ["world_id", "tick_index"])

    # ---------- 人物系统 ----------
    op.create_table(
        "characters",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("type", postgresql.ENUM(
            "actor", "director", "writer", "producer", "cinematographer",
            "editor", "composer", "agent", "executive", name="character_type"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("nationality", sa.String(100), nullable=True),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.Column("agent_id", sa.BigInteger(), nullable=True),
        sa.Column("status", postgresql.ENUM(
            "active", "retired", "deceased", "archived", name="character_status"),
            nullable=False, server_default="active"),
        sa.Column("career_stage", postgresql.ENUM(
            "debut", "rising", "established", "peak", "veteran", "legacy", name="career_stage"),
            nullable=False, server_default="debut"),
        sa.Column("is_in_hall_of_fame", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("archived_at", sa.Date(), nullable=True),
        sa.Column("attributes", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_char_world", "characters", ["world_id", "type"])
    op.create_index("ix_char_status", "characters", ["status"])

    op.create_table(
        "character_attribute_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("character_id", sa.BigInteger(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("tick_id", sa.BigInteger(), sa.ForeignKey("simulation_ticks.id"), nullable=True),
        sa.Column("field", sa.String(100), nullable=False),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("event_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_attrlog_char", "character_attribute_log", ["character_id", "created_at"])

    op.create_table(
        "character_career_history",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("character_id", sa.BigInteger(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_career_char", "character_career_history", ["character_id", "year"])

    op.create_table(
        "relationships",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=True),
        sa.Column("from_type", sa.String(50), nullable=False),
        sa.Column("from_id", sa.BigInteger(), nullable=False),
        sa.Column("to_type", sa.String(50), nullable=False),
        sa.Column("to_id", sa.BigInteger(), nullable=False),
        sa.Column("relation", sa.String(100), nullable=False),
        sa.Column("weight", sa.Numeric(), nullable=True),
        sa.Column("started_year", sa.Integer(), nullable=True),
        sa.Column("ended_year", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_rel_world", "relationships", ["world_id"])
    op.create_index("ix_rel_from", "relationships", ["from_type", "from_id"])
    op.create_index("ix_rel_to", "relationships", ["to_type", "to_id"])

    # ---------- 作品系统 ----------
    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("type", postgresql.ENUM(
            "film", "tv", "webseries", "variety", "animation", "documentary", "short",
            name="project_type"), nullable=False, server_default="film"),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("status", postgresql.ENUM(
            "concept", "approved", "financing", "casting", "scripting",
            "production", "postproduction", "festival", "released", "archived",
            name="project_status"), nullable=False, server_default="concept"),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.Column("release_year", sa.Integer(), nullable=True),
        sa.Column("release_month", sa.Integer(), nullable=True),
        sa.Column("quality_metrics", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("composite_quality", sa.Numeric(), nullable=True),
        sa.Column("box_office", sa.Numeric(), nullable=True),
        sa.Column("audience_score", sa.Numeric(), nullable=True),
        sa.Column("media_score", sa.Numeric(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_proj_world", "projects", ["world_id", "type"])
    op.create_index("ix_proj_status", "projects", ["status"])

    op.create_table(
        "project_cast",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("character_id", sa.BigInteger(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("role", sa.String(200), nullable=True),
        sa.Column("billing", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cast_proj", "project_cast", ["project_id"])
    op.create_index("ix_cast_char", "project_cast", ["character_id"])

    # ---------- 事件日志 ----------
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("tick_id", sa.BigInteger(), sa.ForeignKey("simulation_ticks.id"), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("level", postgresql.ENUM(
            "normal", "important", "major", "historic", name="event_level"),
            nullable=False, server_default="normal"),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("causal_chain", postgresql.JSONB(), nullable=True),
        sa.Column("affected_entities", postgresql.JSONB(), nullable=True),
        sa.Column("is_historic", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_event_world", "events", ["world_id", "event_date"])
    op.create_index("ix_event_level", "events", ["level"])

    # ---------- 上帝模式审计 ----------
    op.create_table(
        "interventions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=True),
        sa.Column("tick_id", sa.BigInteger(), sa.ForeignKey("simulation_ticks.id"), nullable=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=True),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("intervention_type", postgresql.ENUM(
            "attribute", "create", "award", "status", "relation", name="intervention_type"),
            nullable=False),
        sa.Column("field", sa.String(100), nullable=True),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_interv_world", "interventions", ["world_id"])
    op.create_index("ix_interv_target", "interventions", ["target_type", "target_id"])

    # ---------- Agent 记忆 ----------
    op.create_table(
        "memories",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("world_id", sa.BigInteger(), sa.ForeignKey("world.id"), nullable=False),
        sa.Column("agent", sa.String(100), nullable=False),
        sa.Column("scope", postgresql.ENUM(
            "short", "long", "world", name="memory_scope"), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_mem_world", "memories", ["world_id", "agent", "scope"])


def downgrade() -> None:
    op.drop_table("memories")
    op.drop_table("interventions")
    op.drop_table("events")
    op.drop_table("project_cast")
    op.drop_table("projects")
    op.drop_table("relationships")
    op.drop_table("character_career_history")
    op.drop_table("character_attribute_log")
    op.drop_table("characters")
    op.drop_table("simulation_ticks")
    op.drop_table("world")

    op.execute("DROP TYPE IF EXISTS memory_scope")
    op.execute("DROP TYPE IF EXISTS intervention_type")
    op.execute("DROP TYPE IF EXISTS event_level")
    op.execute("DROP TYPE IF EXISTS project_status")
    op.execute("DROP TYPE IF EXISTS project_type")
    op.execute("DROP TYPE IF EXISTS career_stage")
    op.execute("DROP TYPE IF EXISTS character_status")
    op.execute("DROP TYPE IF EXISTS character_type")
    op.execute("DROP TYPE IF EXISTS world_status")
