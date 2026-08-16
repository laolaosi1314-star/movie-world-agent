"""Phase 6（二）业务动作绑定 —— 离线单测（不连库）。

覆盖：客户端动作目录（capabilities）/ 四个核心动作的权限网关路由
      （sim:advance / award:create / world:intervene / project:invest） /
      玩家视角 + 能力集 Schema 装配 / 融资 Schema 与 FINANCING 枚举。
"""
import sys
import types
from datetime import datetime

import pytest
from fastapi import HTTPException, status

from app.models.enums import PlayerRole, WorkDomain, WorldStatus, InterventionType
from app.models.player import Player
from app.auth import roles as R
from app.api import deps
from app.schemas.player import PlayerOut, PlayerMeOut, PlayerCapability, PlayerPortalOut
from app.schemas.project import ProjectFinancingIn


# ---------- 1. 客户端动作目录（capabilities） ----------
def test_action_catalog_integrity():
    assert len(R.ACTION_CATALOG) >= 8
    perms = {a["permission"] for a in R.ACTION_CATALOG}
    # 所有目录项引用的权限必须真实存在
    for p in (R.PERM_WORLD_READ, R.PERM_SIM_ADVANCE, R.PERM_RATING_WRITE,
              R.PERM_REVIEW_WRITE, R.PERM_AWARD_CREATE, R.PERM_PROJECT_INVEST,
              R.PERM_WORLD_INTERVENE, R.PERM_PLAYER_ADMIN):
        assert p in perms
    # 写类动作的 requires_world_writable 必须为真
    for a in R.ACTION_CATALOG:
        if a["permission"] in R.WRITE_PERMISSIONS:
            assert a["requires_world_writable"] is True


def test_capabilities_of_per_role():
    gm = R.capabilities_of(PlayerRole.GM)
    assert len(gm) == len(R.ACTION_CATALOG)  # GM 可见全部动作

    audience = R.capabilities_of(PlayerRole.AUDIENCE)
    keys = {a["key"] for a in audience}
    assert "sim:advance" in keys and "world:read" in keys
    assert "world:intervene" not in keys
    assert "award:create" not in keys
    assert "project:invest" not in keys

    critic = {a["key"] for a in R.capabilities_of(PlayerRole.CRITIC)}
    assert "award:create" in critic and "review:write" in critic
    assert "world:intervene" not in critic and "project:invest" not in critic

    investor = {a["key"] for a in R.capabilities_of(PlayerRole.INVESTOR)}
    assert "project:invest" in investor
    assert "award:create" not in investor and "review:write" not in investor


# ---------- 2. 四个核心动作的权限网关路由 ----------
def _call_guard(permission, *, world_status=WorldStatus.ACTIVE, player=None, expect=None):
    guard = deps.require_permission(permission)

    class _World:
        status = world_status

    try:
        result = guard(_World(), player)
    except HTTPException as e:
        assert e.status_code == expect, f"expected {expect}, got {e.status_code}: {e.detail}"
        return
    assert expect is None, f"expected HTTPException {expect} but none raised"
    assert result is not None


def _make_player(role, world_id=1, key="k"):
    return Player(id=1, world_id=world_id, name="p", role=role, player_key=key,
                  is_active=True, created_at=datetime(2032, 1, 1))


def test_sim_advance_allowed_for_any_role():
    for role in (PlayerRole.AUDIENCE, PlayerRole.CRITIC, PlayerRole.INVESTOR, PlayerRole.GM):
        _call_guard(R.PERM_SIM_ADVANCE, player=_make_player(role), expect=None)


def test_sim_advance_requires_token_401():
    _call_guard(R.PERM_SIM_ADVANCE, player=None, expect=status.HTTP_401_UNAUTHORIZED)


def test_award_create_forbidden_for_audience():
    _call_guard(R.PERM_AWARD_CREATE, player=_make_player(PlayerRole.AUDIENCE),
                expect=status.HTTP_403_FORBIDDEN)
    _call_guard(R.PERM_AWARD_CREATE, player=_make_player(PlayerRole.INVESTOR),
                expect=status.HTTP_403_FORBIDDEN)


def test_award_create_ok_for_critic_and_gm():
    _call_guard(R.PERM_AWARD_CREATE, player=_make_player(PlayerRole.CRITIC), expect=None)
    _call_guard(R.PERM_AWARD_CREATE, player=_make_player(PlayerRole.GM), expect=None)


def test_intervene_only_gm():
    for role in (PlayerRole.AUDIENCE, PlayerRole.CRITIC, PlayerRole.INVESTOR):
        _call_guard(R.PERM_WORLD_INTERVENE, player=_make_player(role),
                    expect=status.HTTP_403_FORBIDDEN)
    _call_guard(R.PERM_WORLD_INTERVENE, player=_make_player(PlayerRole.GM), expect=None)


def test_intervene_archived_423():
    _call_guard(R.PERM_WORLD_INTERVENE, world_status=WorldStatus.ARCHIVED,
                player=_make_player(PlayerRole.GM), expect=status.HTTP_423_LOCKED)


def test_invest_only_investor_and_gm():
    _call_guard(R.PERM_PROJECT_INVEST, player=_make_player(PlayerRole.AUDIENCE),
                expect=status.HTTP_403_FORBIDDEN)
    _call_guard(R.PERM_PROJECT_INVEST, player=_make_player(PlayerRole.CRITIC),
                expect=status.HTTP_403_FORBIDDEN)
    _call_guard(R.PERM_PROJECT_INVEST, player=_make_player(PlayerRole.INVESTOR), expect=None)
    _call_guard(R.PERM_PROJECT_INVEST, player=_make_player(PlayerRole.GM), expect=None)


def test_financing_archived_423():
    _call_guard(R.PERM_PROJECT_INVEST, world_status=WorldStatus.ARCHIVED,
                player=_make_player(PlayerRole.INVESTOR), expect=status.HTTP_423_LOCKED)


# ---------- 3. 玩家视角 + 能力集 Schema 装配 ----------
def test_player_me_out_builds():
    p = _make_player(PlayerRole.INVESTOR, world_id=7)
    base = PlayerOut.model_validate(p).model_dump()
    acts = [PlayerCapability(**a) for a in R.capabilities_of(p.role)]
    me = PlayerMeOut(**base, capabilities=sorted(R.permissions_of(p.role)), actions=acts)
    assert me.role == "investor"
    assert me.world_id == 7
    assert "project:invest" in me.capabilities
    assert any(a.key == "project:invest" for a in me.actions)


def test_player_portal_out_builds():
    p = _make_player(PlayerRole.GM, world_id=3)
    me = PlayerMeOut(**PlayerOut.model_validate(p).model_dump(),
                     capabilities=sorted(R.permissions_of(p.role)),
                     actions=[PlayerCapability(**a) for a in R.capabilities_of(p.role)])
    portal = PlayerPortalOut(
        player=me,
        world={"id": 3, "name": "测试世界", "current_year": 2032, "status": "active"},
        recent_events=[],
    )
    assert portal.player.role == "gm"
    assert portal.world["name"] == "测试世界"
    assert portal.recent_events == []


# ---------- 4. 融资 Schema 与 FINANCING 枚举 ----------
def test_financing_schema_and_enum():
    fin = ProjectFinancingIn(amount=1.2, investor_name="星海影业", note="A轮")
    assert fin.amount == 1.2 and fin.investor_name == "星海影业"
    assert InterventionType.FINANCING.value == "financing"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
