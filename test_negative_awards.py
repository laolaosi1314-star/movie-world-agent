"""Phase 6 前置：负面奖项体系离线单测（不连接数据库）。

覆盖：
  - AwardType 枚举取值；
  - 负面判定算法 _badness（低分/烂口碑/高开低走 越"烂"分值越高）；
  - 新闻分类：类别含"负面" -> CONTROVERSY，普通"奖项" -> AWARD_PREDICTION（回归）；
  - 尖锐话题 fact_pack 构造与尖锐媒体挑选（TABLOID/毒舌优先）。
"""
import os
import sys
import types

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://u:p@localhost:5432/movie_world")

from app.sim.award_agent import AwardAgent, NEGATIVE_CATEGORY_DEFS, POSITIVE_CATEGORY_DEFS  # noqa: E402
from app.sim.media_agent import _classify_news_type, MediaAgent  # noqa: E402
from app.models.enums import NewsType, MediaOutletType, AwardType  # noqa: E402
from app.models.media import MediaOutlet  # noqa: E402

failures = []


def _ok(name):
    print(f"  ok: {name}")


def _check(cond, name):
    if cond:
        _ok(name)
    else:
        failures.append(name)
        print(f"  FAIL: {name}")


def _make_agent():
    world = types.SimpleNamespace(id=1, current_year=2033, total_ticks=5)
    tick = types.SimpleNamespace(id=1, tick_index=5,
                                 to_date=__import__("datetime").date(2033, 1, 1))
    return AwardAgent(None, world, tick)


def _entry(quality, market=None):
    return {"project": None, "quality": quality, "director": None,
            "actors": [], "writer": None, "market": market}


def test_enum():
    _check({e.value for e in AwardType} == {"positive", "negative"},
           "AwardType 枚举含 positive/negative")
    _check(any(c["name"] == "最差影片" for c in NEGATIVE_CATEGORY_DEFS),
           "NEGATIVE_CATEGORY_DEFS 含最差影片")
    _check(any(c["name"] == "最佳影片" for c in POSITIVE_CATEGORY_DEFS),
           "POSITIVE_CATEGORY_DEFS 含最佳影片")


def test_badness_ranking():
    agent = _make_agent()
    good = _entry(90, None)                                  # 高分无口碑
    mid = _entry(50, {"audience_score": 40})                 # 中分中口碑
    bad = _entry(30, {"audience_score": 20, "media_score": 30,
                      "trajectory": "high_open_low_close"})   # 低分烂口碑高开低走
    b_good, b_mid, b_bad = agent._badness(good), agent._badness(mid), agent._badness(bad)
    _check(b_bad > b_mid > b_good, "负面判定：越烂 badness 越大")
    _check(b_bad > b_good * 5, "烂片 badness 远高于佳作")
    # 同分下，高开低走额外拉高 badness
    same_quality = _entry(50, {"audience_score": 40})
    nosedive = _entry(50, {"audience_score": 40, "trajectory": "high_open_low_close"})
    _check(agent._badness(nosedive) > agent._badness(same_quality),
           "高开低走额外惩罚生效")


def test_classify_negative():
    neg = types.SimpleNamespace(category="负面奖项")
    pos = types.SimpleNamespace(category="奖项")
    _check(_classify_news_type(neg) == NewsType.CONTROVERSY,
           "类别'负面奖项' -> CONTROVERSY")
    _check(_classify_news_type(pos) == NewsType.AWARD_PREDICTION,
           "类别'奖项' -> AWARD_PREDICTION（回归，未被误判）")


def test_sharp_fact_pack_and_outlet():
    world = types.SimpleNamespace(id=1, current_year=2033, total_ticks=5)
    tick = types.SimpleNamespace(id=1, tick_index=5,
                                 to_date=__import__("datetime").datetime(2033, 1, 1))
    m = MediaAgent(None, world, tick)
    fp = m._build_sharp_fact_pack({"headline": "金酸梅第1届：最差影片→《烂片》"})
    _check(fp.get("category") == "负面奖项", "尖锐话题 fact_pack 类别为负面奖项")
    _check("金酸梅" in (fp.get("summary") or ""), "尖锐话题 fact_pack 含来源标题")

    tabloid = MediaOutlet(name="星闻周刊", outlet_type=MediaOutletType.TABLOID)
    serious = MediaOutlet(name="影艺日报", outlet_type=MediaOutletType.SERIOUS)
    outlet = m._pick_sharp_outlet([serious, tabloid])
    _check(outlet.outlet_type == MediaOutletType.TABLOID,
           "尖锐话题优先交给八卦/毒舌媒体")


if __name__ == "__main__":
    test_enum()
    test_badness_ranking()
    test_classify_negative()
    test_sharp_fact_pack_and_outlet()
    print()
    if failures:
        print("NEGATIVE_AWARD_TESTS_FAILED:", failures)
        sys.exit(1)
    print("ALL_NEGATIVE_AWARD_TESTS_GREEN")
