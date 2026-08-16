"""Phase 6 身份模型与角色边界 —— 离线单测（不连库）。

覆盖：枚举取值 / 模型列 / 权限矩阵边界 / 影评人领域限定 /
      require_permission 工厂的 401/403/423 路由 / deps 令牌解析逻辑。
"""
import sys
import types
from datetime import datetime

import pytest
from fastapi import HTTPException, status

from app.models.enums import PlayerRole, WorkDomain, WorldStatus
from app.models.player import Player
from app.auth import roles as R
from app.api import deps


# ---------- 1. 枚举与模型 ----------
def test_player_role_values():
    assert {e.value for e in PlayerRole} == {"audience", "critic", "investor", "gm"}


def test_player_model_columns():
    cols = {c.name for c in Player.__table__.columns}
    for need in ("world_id", "name", "role", "player_key", "critic_domains",
                 "bio", "is_active", "created_at", "updated_at"):
        assert need in cols


def test_player_key_unique_index():
    pk = Player.__table__.c.player_key
    assert pk.unique is True
    assert pk.nullable is False


# ---------- 2. 权限矩阵边界 ----------
def test_gm_is_superset():
    for perm in R._ROLE_PERMISSIONS[PlayerRole.GM]:
        assert R.role_has_permission(PlayerRole.GM, perm)
    # GM 拥有所有写权限
    assert R.role_has_permission(PlayerRole.GM, R.PERM_WORLD_INTERVENE)
    assert R.role_has_permission(PlayerRole.GM, R.PERM_PLAYER_ADMIN)


def test_audience_cannot_intervene_or_create_award():
    assert not R.role_has_permission(PlayerRole.AUDIENCE, R.PERM_WORLD_INTERVENE)
    assert not R.role_has_permission(PlayerRole.AUDIENCE, R.PERM_AWARD_CREATE)
    assert not R.role_has_permission(PlayerRole.AUDIENCE, R.PERM_PROJECT_INVEST)
    assert not R.role_has_permission(PlayerRole.AUDIENCE, R.PERM_REVIEW_WRITE)
    # 观众可读、可推进、可打分
    assert R.role_has_permission(PlayerRole.AUDIENCE, R.PERM_WORLD_READ)
    assert R.role_has_permission(PlayerRole.AUDIENCE, R.PERM_SIM_ADVANCE)
    assert R.role_has_permission(PlayerRole.AUDIENCE, R.PERM_RATING_WRITE)


def test_investor_cannot_review():
    assert R.role_has_permission(PlayerRole.INVESTOR, R.PERM_PROJECT_INVEST)
    assert not R.role_has_permission(PlayerRole.INVESTOR, R.PERM_REVIEW_WRITE)
    assert not R.role_has_permission(PlayerRole.INVESTOR, R.PERM_AWARD_CREATE)


def test_critic_cannot_intervene():
    assert R.role_has_permission(PlayerRole.CRITIC, R.PERM_REVIEW_WRITE)
    assert R.role_has_permission(PlayerRole.CRITIC, R.PERM_AWARD_CREATE)
    assert not R.role_has_permission(PlayerRole.CRITIC, R.PERM_WORLD_INTERVENE)
    assert not R.role_has_permission(PlayerRole.CRITIC, R.PERM_PLAYER_ADMIN)


# ---------- 3. 影评人领域限定 ----------
def test_critic_domain_scoping():
    assert R.critic_can_create_award(PlayerRole.CRITIC, ["film", "tv"], "tv")
    assert R.critic_can_create_award(PlayerRole.CRITIC, ["music"], "music")
    assert not R.critic_can_create_award(PlayerRole.CRITIC, ["film"], "music")
    assert not R.critic_can_create_award(PlayerRole.CRITIC, None, "film")
    assert not R.critic_can_create_award(PlayerRole.AUDIENCE, ["film"], "film")
    # GM 不受领域限制
    assert R.critic_can_create_award(PlayerRole.GM, None, "music")


# ---------- 4. deps 令牌解析逻辑 ----------
class _FakeQuery:
    def __init__(self, by_key):
        self._by_key = by_key

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._by_key


def _make_player(role=PlayerRole.AUDIENCE, world_id=1, active=True, key="k"):
    return Player(id=1, world_id=world_id, name="p", role=role, player_key=key,
                  is_active=active, created_at=datetime(2032, 1, 1))


def test_resolve_missing_header():
    assert deps._resolve_player(1, None, None) is None
    assert deps._resolve_player(1, "Basic abc", None) is None  # 非 Bearer
    assert deps._resolve_player(1, "Bearer ", None) is None    # 空 token


def test_resolve_wrong_world_rejected():
    p = _make_player(role=PlayerRole.GM, world_id=1, key="tok")
    fake_db = types.SimpleNamespace(query=lambda *a: _FakeQuery(p))
    # 请求 world_id=2，玩家属于 world_id=1 → 拒绝
    assert deps._resolve_player(2, "Bearer tok", fake_db) is None
    # 同 world → 通过
    assert deps._resolve_player(1, "Bearer tok", fake_db) is p


def test_resolve_inactive_rejected():
    p = _make_player(role=PlayerRole.GM, world_id=1, active=False, key="tok")
    fake_db = types.SimpleNamespace(query=lambda *a: _FakeQuery(p))
    assert deps._resolve_player(1, "Bearer tok", fake_db) is None


def test_resolve_unknown_key_rejected():
    fake_db = types.SimpleNamespace(query=lambda *a: _FakeQuery(None))
    assert deps._resolve_player(1, "Bearer nope", fake_db) is None


# ---------- 5. require_permission 工厂路由（401/403/423） ----------
def _call_guard(permission, *, world_status=WorldStatus.ACTIVE, player=None, expect=None):
    """直接驱动 require_permission 返回的 _dep，断言抛出的 HTTPException 状态码。"""
    guard = deps.require_permission(permission)

    class _World:
        status = world_status

    fake_world = _World()
    try:
        result = guard(fake_world, player)
    except HTTPException as e:
        assert e.status_code == expect, f"expected {expect}, got {e.status_code}: {e.detail}"
        return
    # 未抛异常则不应期望错误
    assert expect is None, f"expected HTTPException {expect} but none raised"
    assert result is not None


def test_guard_no_token_401():
    _call_guard(R.PERM_PLAYER_ADMIN, player=None, expect=status.HTTP_401_UNAUTHORIZED)


def test_guard_forbidden_role_403():
    p = _make_player(role=PlayerRole.AUDIENCE, world_id=1, key="k")
    _call_guard(R.PERM_WORLD_INTERVENE, player=p, expect=status.HTTP_403_FORBIDDEN)


def test_guard_gm_ok():
    p = _make_player(role=PlayerRole.GM, world_id=1, key="k")
    _call_guard(R.PERM_WORLD_INTERVENE, player=p, expect=None)


def test_guard_write_on_archived_423():
    p = _make_player(role=PlayerRole.GM, world_id=1, key="k")
    _call_guard(R.PERM_WORLD_INTERVENE, world_status=WorldStatus.ARCHIVED, player=p,
                expect=status.HTTP_423_LOCKED)


def test_guard_critic_award_ok():
    p = _make_player(role=PlayerRole.CRITIC, world_id=1, key="k")
    _call_guard(R.PERM_AWARD_CREATE, player=p, expect=None)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
