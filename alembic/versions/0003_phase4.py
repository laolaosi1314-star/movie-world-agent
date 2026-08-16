"""Phase 4: 媒体机构与新闻系统。

Revision ID: 0003_phase4
Revises: 0002_phase2_phase3
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_phase4"
down_revision = "0002_phase2_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- 枚举 ----------
    outlet_type = postgresql.ENUM(
        "serious", "tabloid", "industry", "fan",
        name="media_outlet_type", create_type=False)
    outlet_type.create(op.get_bind(), checkfirst=True)
    stance = postgresql.ENUM(
        "neutral", "positive", "critical", "hype", "skeptical",
        name="media_stance", create_type=False)
    stance.create(op.get_bind(), checkfirst=True)
    news_type = postgresql.ENUM(
        "bulletin", "review", "interview", "boxoffice",
        "award_prediction", "red_carpet", "controversy", "industry_news",
        name="news_type", create_type=False)
    news_type.create(op.get_bind(), checkfirst=True)
    render_engine = postgresql.ENUM(
        "template", "llm", name="render_engine", create_type=False)
    render_engine.create(op.get_bind(), checkfirst=True)

    # ---------- media_outlets ----------
    op.create_table(
        "media_outlets",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("world_id", sa.BigInteger, sa.ForeignKey("world.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("outlet_type", outlet_type, nullable=False, server_default="serious"),
        sa.Column("stance", stance, nullable=False, server_default="neutral"),
        sa.Column("credibility", sa.Integer, nullable=False, server_default="50"),
        sa.Column("preferred_categories", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("preferred_genres", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("founded_year", sa.Integer),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )
    op.create_index("ix_media_outlets_world", "media_outlets", ["world_id"])

    # ---------- news ----------
    op.create_table(
        "news",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("world_id", sa.BigInteger, sa.ForeignKey("world.id"), nullable=False),
        sa.Column("outlet_id", sa.BigInteger, sa.ForeignKey("media_outlets.id"), nullable=False),
        sa.Column("tick_id", sa.BigInteger, sa.ForeignKey("simulation_ticks.id")),
        sa.Column("primary_event_id", sa.BigInteger, sa.ForeignKey("events.id")),
        sa.Column("related_event_ids", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("news_type", news_type, nullable=False, server_default="bulletin"),
        sa.Column("headline", sa.Text, nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("fact_pack", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("render_engine", render_engine, nullable=False, server_default="template"),
        sa.Column("outlet_snapshot", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_news_world", "news", ["world_id"])
    op.create_index("ix_news_outlet", "news", ["outlet_id"])
    op.create_index("ix_news_tick", "news", ["tick_id"])


def downgrade() -> None:
    op.drop_index("ix_news_tick", table_name="news")
    op.drop_index("ix_news_outlet", table_name="news")
    op.drop_index("ix_news_world", table_name="news")
    op.drop_table("news")
    op.drop_index("ix_media_outlets_world", table_name="media_outlets")
    op.drop_table("media_outlets")
    sa.Enum(name="render_engine").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="news_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="media_stance").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="media_outlet_type").drop(op.get_bind(), checkfirst=True)
