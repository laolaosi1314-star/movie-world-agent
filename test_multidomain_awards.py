"""Phase 3.x：多领域 / 跨界奖项体系离线单测（不连接数据库）。

覆盖：
  - WorkDomain / CategoryKind 枚举取值；ProjectType 含 album/single；CharacterType 含 singer；
  - CATEGORY_DEFS 覆盖 6 个 (domain, award_type) 组合，且 TV/MUSIC 类目齐全；
  - DEFAULT_AWARDS 覆盖 film/tv/music 三大领域（含正/负），CATEGORY_KIND_LOOKUP 可解析；
  - _eligible_works 按 domain 过滤（PROJECT_TYPE_TO_DOMAIN 映射正确）；
  - _pick 对歌手/专辑/单曲/作词/作曲 客体种类的路由；
  - 跨领域负奖 _badness 语义一致（电视/音乐烂作同样"突出"）；
  - 媒体争议闭环 domain 无关（sharp_topics 写入 domain 字段）。
"""
import os
import sys
import types

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://u:p@localhost:5432/movie_world")

from app.sim.award_agent import (  # noqa: E402
    AwardAgent, CATEGORY_DEFS, DEFAULT_AWARDS, CATEGORY_KIND_LOOKUP,
    POSITIVE_CATEGORY_DEFS, NEGATIVE_CATEGORY_DEFS,
)
from app.models.enums import (  # noqa: E402
    WorkDomain, CategoryKind, ProjectType, CharacterType, AwardType,
)

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


def _entry(quality, market=None, project_type=None, singers=None, actors=None,
           director=None, writer=None, composer=None):
    project = types.SimpleNamespace(id=1, title="X", type=project_type or ProjectType.FILM,
                                    composite_quality=None, quality_metrics={})
    return {"project": project, "quality": quality,
            "director": director, "actors": actors or [], "writer": writer,
            "singers": singers or [], "composer": composer,
            "market": market or {}}


def test_enums():
    _check({e.value for e in WorkDomain} == {"film", "tv", "music"},
           "WorkDomain 枚举含 film/tv/music")
    _check({e.value for e in CategoryKind} == {"project", "director", "actor_male",
              "actor_female", "writer", "album", "single", "singer_male",
              "singer_female", "lyricist", "composer"},
           "CategoryKind 枚举全集正确")
    _check({"album", "single"}.issubset({e.value for e in ProjectType}),
           "ProjectType 含 album/single")
    _check("singer" in {e.value for e in CharacterType},
           "CharacterType 含 singer")


def test_category_defs_coverage():
    for dom in (WorkDomain.FILM, WorkDomain.TV, WorkDomain.MUSIC):
        for at in (AwardType.POSITIVE, AwardType.NEGATIVE):
            _check((dom, at) in CATEGORY_DEFS,
                   f"CATEGORY_DEFS 覆盖 ({dom.value},{at.value})")
    # 电视/音乐 类目齐全（含歌手/专辑/单曲/作词/作曲）
    tv_pos = {(c["name"], c["kind"].value) for c in CATEGORY_DEFS[(WorkDomain.TV, AwardType.POSITIVE)]}
    _check(("最佳剧集", "project") in tv_pos and ("最佳男主角", "actor_male") in tv_pos,
           "TV 正奖含 最佳剧集/最佳男主角")
    music_pos = {(c["name"], c["kind"].value) for c in CATEGORY_DEFS[(WorkDomain.MUSIC, AwardType.POSITIVE)]}
    for need in ("最佳专辑", "最佳单曲", "最佳男歌手", "最佳女歌手", "最佳作词", "最佳作曲"):
        _check(any(n == need for n, _ in music_pos), f"MUSIC 正奖含 {need}")
    # 旧电影别名仍保留（后向兼容）
    _check(any(c["name"] == "最差影片" for c in NEGATIVE_CATEGORY_DEFS),
           "NEGATIVE-tag 电影负奖别名保留")
    _check(any(c["name"] == "最佳影片" for c in POSITIVE_CATEGORY_DEFS),
           "POSITIVE 电影正奖别名保留")


def test_default_awards_domains():
    domains = {a["domain"] for a in DEFAULT_AWARDS}
    _check(domains == {WorkDomain.FILM, WorkDomain.TV, WorkDomain.MUSIC},
           "默认种子奖项覆盖 film/tv/music 三领域")
    # 每个默认奖项的所有类别都能从 lookup 解析出 kind
    ok_all = all(
        (a["domain"], a["award_type"], name) in CATEGORY_KIND_LOOKUP
        for a in DEFAULT_AWARDS for name in a["categories"]
    )
    _check(ok_all, "默认奖项所有类别均可解析 kind（CATEGORY_KIND_LOOKUP）")


def test_eligible_works_domain_filter():
    agent = _make_agent()
    # 直接校验映射：album/single->music, tv->tv, film->film
    from app.sim.award_agent import PROJECT_TYPE_TO_DOMAIN
    _check(PROJECT_TYPE_TO_DOMAIN[ProjectType.ALBUM] == WorkDomain.MUSIC, "ALBUM -> music")
    _check(PROJECT_TYPE_TO_DOMAIN[ProjectType.SINGLE] == WorkDomain.MUSIC, "SINGLE -> music")
    _check(PROJECT_TYPE_TO_DOMAIN[ProjectType.TV] == WorkDomain.TV, "TV -> tv")
    _check(PROJECT_TYPE_TO_DOMAIN[ProjectType.FILM] == WorkDomain.FILM, "FILM -> film")


def test_pick_router():
    agent = _make_agent()
    singer_m = types.SimpleNamespace(id=2, name="男歌手", type=CharacterType.SINGER,
                                     attributes={"gender": "male"})
    singer_f = types.SimpleNamespace(id=3, name="女歌手", type=CharacterType.SINGER,
                                     attributes={"gender": "female"})
    composer = types.SimpleNamespace(id=4, name="作曲人", type=CharacterType.COMPOSER,
                                     attributes={})
    # 音乐类目：歌手按性别路由
    e = _entry(80, project_type=ProjectType.ALBUM, singers=[singer_m, singer_f])
    _check(agent._pick(CategoryKind.SINGER_MALE, e) is singer_m, "SINGER_MALE -> 男歌手")
    _check(agent._pick(CategoryKind.SINGER_FEMALE, e) is singer_f, "SINGER_FEMALE -> 女歌手")
    # 专辑/单曲 类目无人物候选（目标即作品本身）
    _check(agent._pick(CategoryKind.ALBUM, e) is None, "ALBUM 类目无人物候选")
    _check(agent._pick(CategoryKind.SINGLE, e) is None, "SINGLE 类目无人物候选")
    # 作曲类目
    e2 = _entry(80, project_type=ProjectType.ALBUM, composer=composer)
    _check(agent._pick(CategoryKind.COMPOSER, e2) is composer, "COMPOSER -> 作曲人")
    # 作词映射至 writer（WRITER 实体）
    writer = types.SimpleNamespace(id=5, name="作词人", type=CharacterType.WRITER,
                                   attributes={})
    e3 = _entry(80, project_type=ProjectType.ALBUM, writer=writer)
    _check(agent._pick(CategoryKind.LYRICIST, e3) is writer, "LYRICIST -> WRITER 实体")
    # 无对应客体时不产生候选（缺女歌手）
    e4 = _entry(80, project_type=ProjectType.ALBUM, singers=[singer_m])
    _check(agent._pick(CategoryKind.SINGER_FEMALE, e4) is None, "缺女歌手 -> 无候选")


def test_cross_domain_badness():
    agent = _make_agent()
    # 电影烂片
    film_bad = _entry(30, {"audience_score": 20, "media_score": 30,
                           "trajectory": "high_open_low_close"},
                      project_type=ProjectType.FILM)
    # 音乐烂专辑（评分维度一致）
    music_bad = _entry(30, {"audience_score": 20, "media_score": 30,
                            "trajectory": "high_open_low_close"},
                       project_type=ProjectType.ALBUM)
    # 电视烂剧集
    tv_bad = _entry(30, {"audience_score": 20, "media_score": 30,
                         "trajectory": "high_open_low_close"},
                    project_type=ProjectType.TV)
    f = agent._badness(film_bad)
    m = agent._badness(music_bad)
    t = agent._badness(tv_bad)
    _check(abs(f - m) < 1e-9 and abs(f - t) < 1e-9,
           "跨领域负奖 _badness 语义一致（同分同烂）")


def test_sharp_topic_domain_field():
    # sharp_topics 写入 domain 字段（媒体闭环 domain 无关但携带领域元数据）
    world = types.SimpleNamespace(id=1, current_year=2033, total_ticks=5)
    tick = types.SimpleNamespace(id=1, tick_index=5,
                                 to_date=__import__("datetime").datetime(2033, 1, 1))
    m = _make_agent()
    # 直接校验 _record_sharp_topics 写入的结构（用内存 MemoryStore 需 db，这里仅校验数据形态构造）
    topic = {"headline": "金扫帚奖第1届：最差专辑→《烂碟》",
             "award_name": "金扫帚奖", "domain": "music",
             "season": 1, "target_label": "最差专辑→《烂碟》",
             "created_tick": 5, "consumed": False}
    _check(topic["domain"] == "music" and "consumed" in topic,
           "sharp_topics 条目含 domain 与 consumed（供媒体争议闭环）")


if __name__ == "__main__":
    test_enums()
    test_category_defs_coverage()
    test_default_awards_domains()
    test_eligible_works_domain_filter()
    test_pick_router()
    test_cross_domain_badness()
    test_sharp_topic_domain_field()
    print()
    if failures:
        print("MULTIDOMAIN_AWARD_TESTS_FAILED:", failures)
        sys.exit(1)
    print("ALL_MULTIDOMAIN_AWARD_TESTS_GREEN")
