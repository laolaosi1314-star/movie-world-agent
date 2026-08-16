"""离线导入验证：不连接数据库，仅校验引用链路与元数据完整性。"""
import os
import sys

# 不连接数据库，仅构造 engine（create_engine 不会立即连接）
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg2://u:p@localhost:5432/movie_world"
)

from app.main import app  # noqa: E402  # 触发全量路由/模型/Schema 导入
from app.db.base import Base  # noqa: E402
from app.sim.memory import MemoryStore, MemoryAgent  # noqa: E402  # Phase 5 记忆引擎
from app.models.misc import Memory  # noqa: E402
from app.llm.client import (  # noqa: E402  # Phase 7 LLM 接入
    get_llm_client, get_llm_status, build_narrative_messages, RuleBasedClient,
)

print("IMPORT_OK")
print("routes:", len(app.routes))
print("tables:", len(Base.metadata.tables))


def _collect_paths(routes):
    """递归收集真实 APIRoute 路径（FastAPI 将 include_router 的路由包在
    _IncludedRouter 内，顶层无 path 属性，需下钻 original_router，详见 BLUEPRINT §10）。"""
    paths = []
    for r in routes:
        p = getattr(r, "path", None)
        if p:
            paths.append(p)
        # _IncludedRouter：真实路由在其 original_router.routes 中
        orig = getattr(r, "original_router", None)
        if orig is not None:
            paths.extend(_collect_paths(orig.routes))
        sub = getattr(r, "routes", None)
        if sub:
            paths.extend(_collect_paths(sub))
    return paths


all_paths = _collect_paths(app.routes)
mem_routes = [p for p in all_paths if "memories" in p]
print("memory_routes:", len(mem_routes), mem_routes)

# 校验 Memory 模型已含 Phase 5 衰减字段
mem_cols = {c.name for c in Memory.__table__.columns}
need = {"importance", "access_count", "last_accessed_tick", "expires_tick", "is_dormant"}
print("memory_columns_ok:", need.issubset(mem_cols))

# 校验所有业务路由都挂在 /worlds/{world_id} 命名空间下（多世界隔离约定）
bus_tags = ("/characters", "/projects", "/companies", "/markets", "/festivals",
            "/awards", "/sim", "/events", "/memories", "/media", "/news", "/reports")
bad = []
for p in all_paths:
    if any(tag in p for tag in bus_tags) and "/worlds/{world_id}" not in p:
        bad.append(p)
print("routes_without_world_id:", bad if bad else "none")

# ===== Phase 7 LLM 接线校验 =====
# 1) 全局 /llm/status 已注册（无 world_id，无密钥）
llm_status_routes = [p for p in all_paths if p.endswith("/llm/status") or p == "/llm/status"]
print("llm_status_route:", "yes" if llm_status_routes else "NO")

# 2) 未配置时默认降级模板（render_narrative 返回 None）
import os as _os
_os.environ.pop("LLM_ENABLED", None)
_os.environ.pop("LLM_API_KEY", None)
_os.environ.pop("LLM_BASE_URL", None)
client_mod = __import__("app.llm.client", fromlist=["_ENV_LOADED"])
client_mod._ENV_LOADED = False
default_client = get_llm_client()
print("default_client_is_template:", isinstance(default_client, RuleBasedClient))
print("default_render_is_none:", default_client.render_narrative({}, {}, "x") is None)

# 3) 提示词构建函数存在且返回 2 条消息（表达层合规检查见 test_phase7_llm.py）
msgs = build_narrative_messages({"event_id": 1}, {"name": "X", "stance": "neutral",
                              "outlet_type": "serious", "credibility": 80}, "boxoffice")
print("narrative_messages_ok:", len(msgs) == 2)
print("llm_status_shape:", sorted(get_llm_status().keys()))

# ===== Phase 6 前置：负面奖项体系校验 =====
from app.models.award import Award, AwardCategory  # noqa: E402
from app.models.market import ProjectMarket  # noqa: E402
from app.models.enums import AwardType, WorkDomain, CategoryKind, ProjectType, CharacterType  # noqa: E402

award_cols = {c.name for c in Award.__table__.columns}
cat_cols = {c.name for c in AwardCategory.__table__.columns}
market_cols = {c.name for c in ProjectMarket.__table__.columns}
print("award_award_type_col:", "award_type" in award_cols)
print("category_award_type_col:", "award_type" in cat_cols)
print("award_type_enum_values:", {e.value for e in AwardType} == {"positive", "negative"})

# ===== Phase 3.x：多领域 / 跨界奖项体系校验 =====
print("award_domain_col:", "domain" in award_cols)
print("category_domain_col:", "domain" in cat_cols)
print("category_kind_col:", "kind" in cat_cols)
print("market_domain_col:", "domain" in market_cols)
print("market_tv_music_cols:",
      {"rating", "sales", "streams", "chart_position"}.issubset(market_cols))
print("work_domain_enum_values:", {e.value for e in WorkDomain} == {"film", "tv", "music"})
print("category_kind_enum_values:",
      {e.value for e in CategoryKind} == {"project", "director", "actor_male",
                                          "actor_female", "writer", "album", "single",
                                          "singer_male", "singer_female", "lyricist", "composer"})
print("project_type_has_music:", {"album", "single"}.issubset({e.value for e in ProjectType}))
print("character_type_has_singer:", "singer" in {e.value for e in CharacterType})


# ===== Phase 6：用户角色体系校验 =====
from app.models.player import Player  # noqa: E402
from app.models.enums import PlayerRole  # noqa: E402
from app.auth.roles import (  # noqa: E402
    PERM_WORLD_INTERVENE, PERM_AWARD_CREATE, PERM_PLAYER_ADMIN, PERM_PROJECT_INVEST,
    PERM_REVIEW_WRITE, PERM_RATING_WRITE, PERM_SIM_ADVANCE, PERM_WORLD_READ,
    role_has_permission, critic_can_create_award, WRITE_PERMISSIONS,
)

player_cols = {c.name for c in Player.__table__.columns}
print("player_table_cols:",
      {"world_id", "name", "role", "player_key", "critic_domains",
       "bio", "is_active", "created_at", "updated_at"}.issubset(player_cols))
print("player_role_enum_values:",
      {e.value for e in PlayerRole} == {"audience", "critic", "investor", "gm"})
# GM 为全权限超集
_gm_perms = {PERM_WORLD_READ, PERM_SIM_ADVANCE, PERM_RATING_WRITE, PERM_REVIEW_WRITE,
             PERM_AWARD_CREATE, PERM_PROJECT_INVEST, PERM_PLAYER_ADMIN, PERM_WORLD_INTERVENE}
print("gm_is_superset:", all(role_has_permission(PlayerRole.GM, p) for p in _gm_perms))
# 边界：观众不能干预/创建奖项；投资人不能写评论；影评人不能干预世界
print("audience_no_intervene:", not role_has_permission(PlayerRole.AUDIENCE, PERM_WORLD_INTERVENE))
print("audience_no_award_create:", not role_has_permission(PlayerRole.AUDIENCE, PERM_AWARD_CREATE))
print("investor_no_review:", not role_has_permission(PlayerRole.INVESTOR, PERM_REVIEW_WRITE))
print("critic_no_intervene:", not role_has_permission(PlayerRole.CRITIC, PERM_WORLD_INTERVENE))
# 影评人领域限定
print("critic_domain_ok:", critic_can_create_award(PlayerRole.CRITIC, ["film", "tv"], "tv"))
print("critic_domain_denied:", not critic_can_create_award(PlayerRole.CRITIC, ["film"], "music"))
print("critic_outside_domains_denied:", not critic_can_create_award(PlayerRole.CRITIC, None, "film"))
print("gm_domain_any:", critic_can_create_award(PlayerRole.GM, None, "music"))
print("write_perms_has_intervene:", PERM_WORLD_INTERVENE in WRITE_PERMISSIONS)

# ===== Phase 6（二）：业务动作绑定校验 =====
from app.auth.roles import ACTION_CATALOG, capabilities_of  # noqa: E402
from app.schemas.player import PlayerMeOut, PlayerPortalOut, PlayerCapability  # noqa: E402
from app.schemas.project import ProjectFinancingIn  # noqa: E402
from app.models.enums import InterventionType  # noqa: E402

print("action_catalog_nonempty:", len(ACTION_CATALOG) >= 8)
_gm_caps = capabilities_of(PlayerRole.GM)
print("gm_sees_all_actions:", len(_gm_caps) == len(ACTION_CATALOG))
_aud_caps = {a["key"] for a in capabilities_of(PlayerRole.AUDIENCE)}
print("audience_no_intervene_action:", "world:intervene" not in _aud_caps)
print("audience_has_advance_action:", "sim:advance" in _aud_caps)
print("player_me_out_import:",
      PlayerMeOut is not None and PlayerPortalOut is not None and PlayerCapability is not None)
print("project_financing_in_import:", ProjectFinancingIn is not None)
print("financing_enum_value:", InterventionType.FINANCING.value == "financing")
print("project_invest_is_write_perm:", PERM_PROJECT_INVEST in WRITE_PERMISSIONS)
print("player_admin_not_world_write:", PERM_PLAYER_ADMIN not in WRITE_PERMISSIONS)


# ===== §17.3 舆论与危机公关校验 =====
from app.models.crisis import Scandal, CrisisPR  # noqa: E402
from app.models.enums import ScandalType, ScandalStage, PRStrategy  # noqa: E402
from app.auth.roles import PERM_CRISIS_MANAGE, capabilities_of  # noqa: E402
from app.schemas.crisis import (  # noqa: E402
    ScandalCreate, ScandalOut, PRStrategyIn, CrisisPROut,
)
from app.sim.crisis_agent import (  # noqa: E402
    evaluate_pr, compute_eruption_drop, natural_recovery_target,
)

_crisis_cols = {c.name for c in Scandal.__table__.columns}
print("scandal_table_cols:",
      {"world_id", "character_id", "scandal_type", "title", "severity",
       "evidence_strength", "is_confirmed", "stage", "heat", "public_opinion",
       "exposed_tick", "erupted_tick", "resolved_tick"}.issubset(_crisis_cols))
_pr_cols = {c.name for c in CrisisPR.__table__.columns}
print("crisis_pr_table_cols:",
      {"world_id", "scandal_id", "strategy", "by_player_id", "impact"}.issubset(_pr_cols))
print("scandal_type_enum_values:",
      {e.value for e in ScandalType} == {"affair", "drugs", "tax", "slip_of_tongue",
                                          "surrogacy", "plagiarism", "domestic_violence", "other"})
print("scandal_stage_enum_values:",
      {e.value for e in ScandalStage} == {"latent", "spreading", "erupted",
                                          "resolving", "resolved", "collapsed"})
print("pr_strategy_enum_values:",
      {e.value for e in PRStrategy} == {"cold_treatment", "lawyer_letter", "apology",
                                        "buy_trending", "counter_mkt"})
_gm_perms = {a["permission"] for a in capabilities_of(PlayerRole.GM)}
print("gm_has_crisis_perm:", PERM_CRISIS_MANAGE in _gm_perms)
print("audience_no_crisis_perm:",
      PERM_CRISIS_MANAGE not in {a["permission"] for a in capabilities_of(PlayerRole.AUDIENCE)})
print("crisis_in_write_perms:", PERM_CRISIS_MANAGE in WRITE_PERMISSIONS)
# 公关确定性结算 sanity（纯函数）
_r1 = evaluate_pr(PRStrategy.COUNTER_MKT, 8, 2, False, ScandalStage.ERUPTED)
print("pr_counter_mkt_weak_positive:", _r1["delta_opinion"] > 0)
_r2 = evaluate_pr(PRStrategy.COUNTER_MKT, 8, 9, True, ScandalStage.ERUPTED)
print("pr_counter_mkt_confirmed_negative:", _r2["delta_opinion"] < 0)
print("eruption_drop_capped:", compute_eruption_drop(10, 10, True) <= 60)
print("recovery_target_bounded:", 8 <= natural_recovery_target(10) <= 50)
print("crisis_schemas_import:",
      all([ScandalCreate, ScandalOut, PRStrategyIn, CrisisPROut]))


# ===== §17.1 商业时尚与塌房违约金校验 =====
from app.models.commerce import Endorsement, MagazineCover  # noqa: E402
from app.models.character import Character  # noqa: E402
from app.models.enums import (  # noqa: E402
    EndorsementTier, ContractStatus, MagazineTier,
)
from app.auth.roles import PERM_COMMERCE_MANAGE  # noqa: E402
from app.schemas.commerce import (  # noqa: E402
    EndorsementCreate, EndorsementOut, MagazineCoverCreate, MagazineCoverOut,
    CommercialSummary,
)
from app.sim.commerce_agent import (  # noqa: E402
    compute_penalty, commercial_crash_factor, BRAND_CATALOG, MAGAZINE_CATALOG,
)

_end_cols = {c.name for c in Endorsement.__table__.columns}
print("endorsement_table_cols:",
      {"world_id", "character_id", "brand_name", "category", "tier", "annual_fee",
       "penalty_rate", "has_morals_clause", "signed_tick", "duration_ticks",
       "status", "terminated_tick", "penalty_amount"}.issubset(_end_cols))
_cov_cols = {c.name for c in MagazineCover.__table__.columns}
print("magazine_cover_table_cols:",
      {"world_id", "character_id", "magazine_name", "tier", "issue_tick",
       "theme", "fee", "prestige", "status", "cancelled_tick"}.issubset(_cov_cols))
_char_cols = {c.name for c in Character.__table__.columns}
print("character_commercial_value_col:", "commercial_value" in _char_cols)
print("endorsement_tier_enum_values:",
      {e.value for e in EndorsementTier} == {"top_luxury", "high_luxury", "mass", "brand_friend"})
print("contract_status_enum_values:",
      {e.value for e in ContractStatus} == {"active", "terminated", "breached", "expired"})
print("magazine_tier_enum_values:",
      {e.value for e in MagazineTier} == {"top5", "second_tier"})
_gm_perms = {a["permission"] for a in capabilities_of(PlayerRole.GM)}
print("gm_has_commerce_perm:", PERM_COMMERCE_MANAGE in _gm_perms)
print("audience_no_commerce_perm:",
      PERM_COMMERCE_MANAGE not in {a["permission"] for a in capabilities_of(PlayerRole.AUDIENCE)})
print("commerce_in_write_perms:", PERM_COMMERCE_MANAGE in WRITE_PERMISSIONS)
# 纯函数 sanity（确定性）
print("penalty_full_several_years:",
      compute_penalty(1000, 0.8, 12, 12) == 800)
print("penalty_half_term:", compute_penalty(1000, 0.8, 6, 12) == 400)
print("crash_factor_bounded:", 0.05 <= commercial_crash_factor(5) <= 1.0)
print("crash_factor_severe_lower:", commercial_crash_factor(9) < commercial_crash_factor(5))
print("commerce_schemas_import:",
      all([EndorsementCreate, EndorsementOut, MagazineCoverCreate,
           MagazineCoverOut, CommercialSummary]))


# ===== §17.2 人际情感网络 + 人生档案馆校验 =====
from app.models.romance import Romance  # noqa: E402
from app.models.enums import RomanceType, RomanceStatus  # noqa: E402
from app.auth.roles import PERM_RELATIONSHIP_MANAGE  # noqa: E402
from app.schemas.relationship import (  # noqa: E402
    RomanceCreate, RomanceReveal, RomanceEnd, RomanceAddChild, RomanceOut, LifeArchiveOut,
)
from app.sim.romance_agent import (  # noqa: E402
    fan_profile, compute_fan_reaction,
)
from app.sim.life_archive import build_archive  # noqa: E402

_rom_cols = {c.name for c in Romance.__table__.columns}
print("romance_table_cols:",
      {"world_id", "character_a_id", "character_b_id", "romance_type", "status",
       "is_public", "publicness", "reacted_tick", "child_count", "started_tick",
       "ended_tick", "ended_reason"}.issubset(_rom_cols))
print("romance_type_enum_values:",
      {e.value for e in RomanceType} == {"dating", "rumor", "married", "cohabit"})
print("romance_status_enum_values:",
      {e.value for e in RomanceStatus} == {"active", "ended"})
_gm_perms = {a["permission"] for a in capabilities_of(PlayerRole.GM)}
print("gm_has_relationship_perm:", PERM_RELATIONSHIP_MANAGE in _gm_perms)
print("audience_no_relationship_perm:",
      PERM_RELATIONSHIP_MANAGE not in {a["permission"] for a in capabilities_of(PlayerRole.AUDIENCE)})
print("relationship_in_write_perms:", PERM_RELATIONSHIP_MANAGE in WRITE_PERMISSIONS)
# 确定性纯函数 sanity
class _FakeChar:
    def __init__(self, ctype, attrs=None):
        self.type = ctype
        self.attributes = attrs or {}
_idol = fan_profile(_FakeChar(CharacterType.SINGER))
_mature = fan_profile(_FakeChar(CharacterType.ACTOR))
print("idol_appeal_higher_than_actor:",
      _idol["idol_appeal"] > _mature["idol_appeal"])
_r_idol = compute_fan_reaction(_idol, "married", True, True)
_r_mature = compute_fan_reaction(_mature, "married", True, True)
print("idol_marriage_defect_higher:", _r_idol["defect"] > _r_mature["defect"])
print("idol_marriage_backstab:", _r_idol["backstab"] is True)
_rumor = compute_fan_reaction(_idol, "rumor", False, False)
print("rumor_unconfirmed_no_defect:", _rumor["defect"] == 0 and _rumor["heat_delta"] > 0)
print("relationship_schemas_import:",
      all([RomanceCreate, RomanceReveal, RomanceEnd, RomanceAddChild,
           RomanceOut, LifeArchiveOut]))
print("archive_callable:", callable(build_archive))
