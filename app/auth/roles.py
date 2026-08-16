"""Phase 6 用户角色体系：权限矩阵与无状态边界判定。

设计原则（与 API_CONTRACT §1 无状态一致）：
  - 服务端不保存会话；玩家身份由每个请求的 Bearer token 解析（见 app/api/deps.py）。
  - 权限以「角色 → 权限集合」声明式建模，与既有「只读存档锁(423)」「上帝模式审计(interventions)」
    同层；所有校验均为请求级、确定性、可重放，不影响 tick 可重放性。
  - 影评人(critic)的奖项创建权限按其 critic_domains（WorkDomain 子集）作用域限定，
    与 §15 多领域奖项正交。
"""
from app.models.enums import PlayerRole

# ===== 权限标识（resource:action） =====
PERM_WORLD_READ = "world:read"            # 读取世界/时间线/事件/新闻/角色/作品/奖项/报告
PERM_SIM_ADVANCE = "sim:advance"          # 推进模拟 tick（观察/游玩核心动作）
PERM_RATING_WRITE = "rating:write"        # 观众打分（影响 audience_score 噪声项）
PERM_REVIEW_WRITE = "review:write"        # 影评人正式评论（进入媒体 Agent 的 review 新闻）
PERM_AWARD_CREATE = "award:create"        # 创建奖项/奖季（critic 按 domain 受限，gm 全开）
PERM_PROJECT_INVEST = "project:invest"    # 投资/融资（investor, gm）
PERM_ENTITY_CREATE = "entity:create"      # 直接生成世界内实体（等价于 InterventionType.CREATE）
PERM_WORLD_INTERVENE = "world:intervene"  # 上帝模式：修改属性/状态/关系，留痕 interventions
PERM_CRISIS_MANAGE = "crisis:manage"      # 舆论与危机公关：黑料爆料/曝光/多阶段公关（GM/运营角色）
PERM_COMMERCE_MANAGE = "commerce:manage"  # 商业时尚：代言/封面签约解约、塌房违约金结算（GM/运营角色）
PERM_RELATIONSHIP_MANAGE = "relationship:manage"  # 人际情感网络：编排恋情/绯闻/婚育、粉丝蝴蝶效应（GM/运营角色）
PERM_PLAYER_ADMIN = "player:admin"        # 玩家管理（停用/启用/改角色）

# 写类权限：触发前需经 423 只读锁校验（与 require_writable_world 对齐）。
# 注：PERM_PLAYER_ADMIN（玩家管理）属账号级操作，与「世界内容冻结」无关，
#     故不纳入世界 423 锁；即使存档只读，GM 仍可停用/启用玩家。
WRITE_PERMISSIONS = {
    PERM_SIM_ADVANCE,
    PERM_RATING_WRITE,
    PERM_REVIEW_WRITE,
    PERM_AWARD_CREATE,
    PERM_PROJECT_INVEST,
    PERM_ENTITY_CREATE,
    PERM_WORLD_INTERVENE,
    PERM_CRISIS_MANAGE,
    PERM_COMMERCE_MANAGE,
    PERM_RELATIONSHIP_MANAGE,
}

# ===== 角色 → 权限集合 =====
_ROLE_PERMISSIONS: dict[PlayerRole, set] = {
    PlayerRole.AUDIENCE: {
        PERM_WORLD_READ,
        PERM_SIM_ADVANCE,
        PERM_RATING_WRITE,
    },
    PlayerRole.CRITIC: {
        PERM_WORLD_READ,
        PERM_SIM_ADVANCE,
        PERM_RATING_WRITE,
        PERM_REVIEW_WRITE,
        PERM_AWARD_CREATE,
    },
    PlayerRole.INVESTOR: {
        PERM_WORLD_READ,
        PERM_SIM_ADVANCE,
        PERM_RATING_WRITE,
        PERM_PROJECT_INVEST,
    },
    PlayerRole.GM: {
        PERM_WORLD_READ,
        PERM_SIM_ADVANCE,
        PERM_RATING_WRITE,
        PERM_REVIEW_WRITE,
        PERM_AWARD_CREATE,
        PERM_PROJECT_INVEST,
        PERM_ENTITY_CREATE,
        PERM_WORLD_INTERVENE,
        PERM_CRISIS_MANAGE,
        PERM_COMMERCE_MANAGE,
        PERM_RELATIONSHIP_MANAGE,
        PERM_PLAYER_ADMIN,
    },
}


def role_has_permission(role: PlayerRole, permission: str) -> bool:
    """判定某角色是否拥有某权限（GM 为全权限超集）。"""
    return permission in _ROLE_PERMISSIONS.get(role, set())


def permissions_of(role: PlayerRole) -> set:
    """返回角色拥有的全部权限（用于 /me 或 UI 能力探测）。"""
    return set(_ROLE_PERMISSIONS.get(role, set()))


def critic_can_create_award(role: PlayerRole, critic_domains, domain: str) -> bool:
    """影评人仅可在其专长领域内创建奖项；gm 不受限；其余角色不可。"""
    if role == PlayerRole.GM:
        return True
    if role != PlayerRole.CRITIC:
        return False
    if not critic_domains:
        return False
    return domain in critic_domains


# ===== 客户端动作目录（供 App/H5 渲染按钮 / 能力探测） =====
# 每个条目对应一个「玩家可在客户端发起的动作」：
#   key                      : 前端动作标识（稳定字符串，UI 用它做路由/按钮 id）
#   label                    : 人类可读文案
#   permission               : 触发该动作所需的权限标识
#   requires_world_writable  : 该动作是否受「只读存档锁(423)」约束
ACTION_CATALOG: list[dict] = [
    {"key": "world:read", "label": "浏览世界 / 时间线", "permission": PERM_WORLD_READ,
     "requires_world_writable": False},
    {"key": "sim:advance", "label": "推进时间（游玩核心）", "permission": PERM_SIM_ADVANCE,
     "requires_world_writable": True},
    {"key": "rating:write", "label": "为作品打分", "permission": PERM_RATING_WRITE,
     "requires_world_writable": True},
    {"key": "review:write", "label": "发表影评", "permission": PERM_REVIEW_WRITE,
     "requires_world_writable": True},
    {"key": "award:create", "label": "创建奖项 / 奖季", "permission": PERM_AWARD_CREATE,
     "requires_world_writable": True},
    {"key": "project:invest", "label": "投资 / 融资项目", "permission": PERM_PROJECT_INVEST,
     "requires_world_writable": True},
    {"key": "world:intervene", "label": "上帝模式干预", "permission": PERM_WORLD_INTERVENE,
     "requires_world_writable": True},
    {"key": "crisis:manage", "label": "舆论与危机公关", "permission": PERM_CRISIS_MANAGE,
     "requires_world_writable": True},
    {"key": "commerce:manage", "label": "商业时尚与代言管理", "permission": PERM_COMMERCE_MANAGE,
     "requires_world_writable": True},
    {"key": "relationship:manage", "label": "人际情感网络编排", "permission": PERM_RELATIONSHIP_MANAGE,
     "requires_world_writable": True},
    {"key": "player:admin", "label": "玩家管理", "permission": PERM_PLAYER_ADMIN,
     "requires_world_writable": False},
]


def capabilities_of(role: PlayerRole) -> list[dict]:
    """返回该角色在客户端可见/可发起的全部动作（已按 ACTION_CATALOG 过滤）。"""
    perms = permissions_of(role)
    return [a for a in ACTION_CATALOG if a["permission"] in perms]
