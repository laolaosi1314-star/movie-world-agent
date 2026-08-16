"""影视世界 Agent — 本地闭环冒烟测试（零额外依赖，使用标准库 urllib）。

用法：
    1) 先启动服务： uvicorn app.main:app --port 8000
    2) 另开终端运行： python run_smoke_test.py

链路： 创建世界 -> 创建人物 -> 创建作品 -> 推进时间(Tick) -> 查看事件
最后做一组断言，全部通过即代表 MW + Phase1 最小闭环可运行。
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}


def _request(method: str, path: str, payload: dict | None = None):
    url = f"{BASE}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {method} {path}: {body}") from e


def step(label: str, fn):
    print(f"\n=== {label} ===")
    result = fn()
    print(json.dumps(result, ensure_ascii=False, indent=2) if isinstance(result, (dict, list)) else result)
    return result


def main() -> int:
    # (1) 创建世界
    world = step("1) 创建世界", lambda: _request(
        "POST", "/worlds",
        {"name": "冒烟测试世界", "description": "run_smoke_test 自动创建"},
    )[1])
    wid = world["id"]
    print(f"-> world_id = {wid}")

    # (2) 创建人物（演员）
    step("2) 创建人物(演员)", lambda: _request(
        "POST", f"/worlds/{wid}/characters",
        {"type": "actor", "name": "林夏", "birth_year": 2000,
         "nationality": "中国", "career_stage": "debut",
         "attributes": {"演技": 80, "人气": 60}},
    )[1])

    # (3) 创建作品（电影）
    step("3) 创建作品(电影)", lambda: _request(
        "POST", f"/worlds/{wid}/projects",
        {"type": "film", "title": "星河彼端", "status": "concept",
         "quality_metrics": {"剧本": 90, "导演": 85, "表演": 88}},
    )[1])

    # (4) 推进时间 1 个月
    tick = step("4) 推进时间(month)", lambda: _request(
        "POST", f"/worlds/{wid}/sim/advance", {"unit": "month"},
    )[1])

    # (5) 查看事件流
    events = step("5) 查看事件流", lambda: _request(
        "GET", f"/worlds/{wid}/events?limit=20",
    )[1])

    # ===== 断言 =====
    print("\n=== 断言 ===")
    ok = True

    def check(cond, msg):
        nonlocal ok
        mark = "OK " if cond else "FAIL"
        if not cond:
            ok = False
        print(f"  [{mark}] {msg}")

    check(world.get("current_year") == 2032 and world.get("current_month") == 6,
          f"世界初始时间默认为 2032-06（实际 {world.get('current_year')}-{world.get('current_month')}）")
    check(tick.get("unit") == "month" and tick.get("tick_index") == 1,
          f"Tick 生成且索引=1（实际 unit={tick.get('unit')}, idx={tick.get('tick_index')}）")

    # 推进后世界时间应前进到 2032-07（需要重新拉取世界）
    _, world_after = _request("GET", f"/worlds/{wid}")
    check(world_after.get("current_month") == 7,
          f"推进后月份为 07（实际 {world_after.get('current_year')}-{world_after.get('current_month')}）")

    check(isinstance(events, list) and len(events) >= 1,
          f"事件流非空（条数={len(events) if isinstance(events, list) else 'N/A'}）")

    # ===== Phase 5：记忆系统闭环验证 =====
    # 推进后，CharacterAgent 应已写入"世界记忆(行业气候)"与"人物长期记忆(人气动量)"
    mems = step("6) 查看记忆（Phase 5）", lambda: _request(
        "GET", f"/worlds/{wid}/memories", None)[1])
    mem_map = {m["key"]: m for m in mems} if isinstance(mems, list) else {}
    print(f"    记忆条数={len(mems) if isinstance(mems, list) else 'N/A'}，"
          f"keys={list(mem_map.keys())[:8]}")

    # 上帝模式写入一条世界记忆，验证写入/读取闭环
    step("7) 上帝写入世界记忆", lambda: _request(
        "POST", f"/worlds/{wid}/memories",
        {"agent": "world", "scope": "world", "key": "smoke_note",
         "value": {"text": "冒烟测试注入的世界记忆"}, "importance": 0.9})[1])

    mems2 = step("8) 复核记忆含注入项", lambda: _request(
        "GET", f"/worlds/{wid}/memories?key=smoke_note", None)[1])
    check(isinstance(mems2, list) and any(m.get("key") == "smoke_note" for m in mems2),
          "上帝写入的世界记忆可被检索到")

    # 手动触发巩固，验证记忆维护端点可用
    step("9) 触发记忆巩固/遗忘", lambda: _request(
        "POST", f"/worlds/{wid}/memories/consolidate", None)[1])

    check(isinstance(mems, list) and len(mems) >= 1,
          f"记忆系统已产生记忆（条数={len(mems) if isinstance(mems, list) else 'N/A'}）")

    # 额外：列出应能看到刚才创建的人物/作品
    _, chars = _request("GET", f"/worlds/{wid}/characters")
    _, projs = _request("GET", f"/worlds/{wid}/projects")
    check(len(chars) >= 1, f"人物已落库（条数={len(chars)}）")
    check(len(projs) >= 1, f"作品已落库（条数={len(projs)}）")

    # ===== Phase 7：LLM 诊断端点 + 新闻重渲染（表达层插槽）=====
    status = step("10) LLM 状态诊断", lambda: _request(
        "GET", "/llm/status", None)[1])
    check(isinstance(status, dict) and status.get("engine") in ("llm", "template"),
          f"/llm/status 返回 engine∈{{llm,template}}（实际 {status.get('engine') if isinstance(status, dict) else 'N/A'}）")

    # 拉一条由本 tick 产生的新闻，验证重渲染插槽可用（仅改文本，不改 fact_pack）
    news_list = step("11) 查看新闻", lambda: _request(
        "GET", f"/worlds/{wid}/news?limit=5", None)[1])
    if isinstance(news_list, dict) and news_list.get("items"):
        nid = news_list["items"][0]["id"]
        re = step("12) 重渲染首条新闻(force_template)", lambda: _request(
            "POST", f"/worlds/{wid}/news/{nid}/rerender?force_template=true", None)[1])
        check(isinstance(re, dict) and re.get("render_engine") == "template",
              f"重渲染后 render_engine=template（实际 {re.get('render_engine') if isinstance(re, dict) else 'N/A'}）")
    else:
        print("  [SKIP] 本 tick 无新闻可重渲染（事件量级不足），跳过 12")

    print("\n" + ("✅ 全部断言通过：MW + Phase1 最小闭环可运行（含 Phase5 记忆 / Phase7 LLM 插槽）。" if ok
                  else "❌ 存在失败项，请检查上面 FAIL 项与服务日志。"))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        print(f"\n❌ 请求失败：{e}")
        print("请确认服务已启动（uvicorn app.main:app --port 8000）且 DATABASE_URL 已配置。")
        sys.exit(2)
