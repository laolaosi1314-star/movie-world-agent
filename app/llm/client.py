"""LLM 适配层（解耦 AI 模型）。

设计原则（详见 BLUEPRINT §11 / §13）：
  - LLM 只允许在"表达层"：把已确定的 fact_pack 渲染成新闻文本，
    绝不参与任何判定（谁获奖 / 谁走红 / 票房多少）。判定由确定性的
    cause_model 完成，LLM 不可见、不可改。
  - render_narrative 返回 None 表示失败 —— 调用方（media_agent / news 重渲染）
    必须降级到模板渲染，绝不因模型不可用而影响世界演化或新闻落库。
  - 切换零成本：接入真实 LLM 只需在 get_llm_client() 返回真实实现；
    业务代码（FactPack / 渲染入口 / 路由）无需改动。可一键切回模板
    （LLM_ENABLED=false 或 LLM_FORCE_TEMPLATE=true）。

Provider：通过 httpx 直连 OpenAI 兼容的 /chat/completions 接口，
因此 OpenAI / DeepSeek / Moonshot / 智谱 / 本地 vLLM / Ollama(shim) 均可用，
无需额外 SDK 依赖。
"""
from __future__ import annotations

import os
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


# --------------------------------------------------------------------------- #
# 抽象接口
# --------------------------------------------------------------------------- #
class LLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> str:
        ...

    @abstractmethod
    def render_narrative(self, fact_pack: dict, outlet_style: dict, news_type: str) -> "str | None":
        """用自然语言把结构化事实包渲染成报道正文。

        返回 None 表示本实现不支持 / 失败 —— 调用方必须降级到模板渲染。
        这是"LLM 只允许在表达层"架构约束的核心容错机制。
        """
        ...


class RuleBasedClient(LLMClient):
    """占位/降级实现：不生成自然语言（render_narrative 返回 None）。

    当真实 LLM 未启用或不可用时使用，保证世界模拟与新闻落库不受影响。
    """
    def complete(self, prompt: str, **kwargs) -> str:
        return '{"decision": "pending", "reason": "rule-based placeholder"}'

    def render_narrative(self, fact_pack: dict, outlet_style: dict, news_type: str) -> "str | None":
        return None


# --------------------------------------------------------------------------- #
# 配置
# --------------------------------------------------------------------------- #
@dataclass
class LLMConfig:
    enabled: bool = False
    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 300
    top_p: float = 0.9
    timeout: float = 20.0
    max_retries: int = 1


def _load_dotenv(path: str) -> None:
    """极简 .env 读取：仅注入 LLM_* 变量（若环境变量中尚无），无外部依赖。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k.startswith("LLM_") and k not in os.environ:
                    os.environ[k] = v
    except FileNotFoundError:
        pass


_ENV_LOADED = False


def _ensure_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    # app/llm/client.py -> app/llm -> app -> project root
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.dirname(app_dir)
    for cand in (os.path.join(os.getcwd(), ".env"), os.path.join(root, ".env")):
        _load_dotenv(cand)
    _ENV_LOADED = True


def _str(name: str, default: str) -> str:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


def _bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on", "enabled")


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def load_llm_config() -> LLMConfig:
    _ensure_env()
    return LLMConfig(
        enabled=_bool("LLM_ENABLED", False),
        provider=_str("LLM_PROVIDER", "openai"),
        base_url=_str("LLM_BASE_URL", "https://api.openai.com/v1"),
        api_key=_str("LLM_API_KEY", ""),
        model=_str("LLM_MODEL", "gpt-4o-mini"),
        temperature=_float("LLM_TEMPERATURE", 0.7),
        max_tokens=_int("LLM_MAX_TOKENS", 300),
        top_p=_float("LLM_TOP_P", 0.9),
        timeout=_float("LLM_TIMEOUT", 20.0),
        max_retries=_int("LLM_MAX_RETRIES", 1),
    )


# --------------------------------------------------------------------------- #
# 提示词构建（§11 合规：只渲染、不判定、不编造）
# --------------------------------------------------------------------------- #
_STANCE_LABEL = {
    "neutral": "中立客观",
    "positive": "积极正面",
    "critical": "审慎批评",
    "hype": "煽动吸睛",
    "skeptical": "冷静克制",
}
_OUTLET_LABEL = {
    "serious": "严肃媒体（重事实与深度）",
    "tabloid": "八卦小报（重噱头与情绪）",
    "industry": "行业媒体（重数据与市场）",
}


def build_narrative_messages(fact_pack: dict, outlet_style: dict, news_type: str) -> List[Dict[str, str]]:
    """构造 [system, user] 消息。纯函数、可单测、无 IO。

    §11 约束已写进 system prompt：只允许复述 fact_pack 中的事实，
    严禁编造人名/数字/奖项/引语/事件，严禁做判定或预测。
    """
    stance = (outlet_style or {}).get("stance", "neutral")
    otype = (outlet_style or {}).get("outlet_type", "serious")
    name = (outlet_style or {}).get("name", "某媒体")
    cred = (outlet_style or {}).get("credibility", 50)

    system = (
        "你是一位资深娱乐记者，正在为媒体《{name}》撰写快讯。\n"
        "你的任务只有一个：把下方【事实包 FACT_PACK】里的已核实事实，"
        "用该媒体的口吻改写成 1~3 句话的新闻正文（中文）。\n\n"
        "【硬性约束】\n"
        "1. 只能使用 FACT_PACK 中明确给出的信息，严禁编造人名、数字、奖项、引语或事件。\n"
        "2. 不得做任何判定、预测或决策（例如在预测类事件中，只能复述事实包中已列出的候选，"
        "不能自行宣布结果；不能声称某人'将'获奖或'必定'走红）。\n"
        "3. 配合该媒体立场：{stance}；媒体类型：{otype}（公信力约 {cred}）。\n"
        "4. 直接输出新闻正文，不要包含标题、JSON、解释或任何前缀。"
    ).format(name=name, stance=_STANCE_LABEL.get(stance, "中立客观"),
             otype=_OUTLET_LABEL.get(otype, "严肃媒体"), cred=cred)

    user = (
        "新闻类型：{nt}\n"
        "事实包（JSON）：\n{fp}\n\n"
        "请基于上述事实包撰写《{name}》风格的新闻正文。"
    ).format(nt=news_type, fp=json.dumps(fact_pack, ensure_ascii=False, indent=2), name=name)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# --------------------------------------------------------------------------- #
# 真实 provider（OpenAI 兼容）
# --------------------------------------------------------------------------- #
class OpenAICompatibleClient(LLMClient):
    """通过 httpx 直连 OpenAI 兼容的 /chat/completions 接口。"""

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    def _post(self, messages: List[Dict[str, str]], **kwargs) -> "str | None":
        import httpx  # 仅在启用真实 LLM 时才导入，降级路径零依赖

        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature,
            "max_tokens": self.cfg.max_tokens,
            "top_p": self.cfg.top_p,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        headers = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"

        last_err: Any = None
        for _ in range(max(1, self.cfg.max_retries)):
            try:
                with httpx.Client(timeout=self.cfg.timeout) as client:
                    r = client.post(url, json=payload, headers=headers)
                    if r.status_code >= 500:
                        last_err = f"HTTP {r.status_code}"
                        continue
                    r.raise_for_status()
                    data = r.json()
                    content = data["choices"][0]["message"]["content"]
                    return content.strip() if isinstance(content, str) else None
            except Exception as e:  # 网络/超时/鉴权/解析任一失败都返回 None -> 降级
                last_err = e
        return None

    def complete(self, prompt: str, **kwargs) -> str:
        text = self._post([{"role": "user", "content": prompt}], **kwargs)
        return text if text else '{"decision": "pending", "reason": "llm unavailable"}'

    def render_narrative(self, fact_pack: dict, outlet_style: dict, news_type: str) -> "str | None":
        try:
            messages = build_narrative_messages(fact_pack, outlet_style, news_type)
            text = self._post(messages)
        except Exception:
            return None
        if not text or not text.strip():
            return None
        return text.strip()


# --------------------------------------------------------------------------- #
# 工厂 / 诊断
# --------------------------------------------------------------------------- #
def get_llm_client(force_template: bool = False) -> LLMClient:
    """返回当前生效的 LLM 客户端。

    force_template=True 或 (未启用 / 缺密钥 / 缺 base_url) 时返回 RuleBasedClient
    （表达层自动降级到模板）。可一键切回模板：LLM_ENABLED=false 或
    LLM_FORCE_TEMPLATE=true。
    """
    if force_template or _bool("LLM_FORCE_TEMPLATE", False):
        return RuleBasedClient()
    cfg = load_llm_config()
    if not cfg.enabled or not cfg.api_key or not cfg.base_url:
        return RuleBasedClient()
    return OpenAICompatibleClient(cfg)


def get_llm_status(force_template: bool = False) -> dict:
    """诊断信息（不含密钥）。engine=llm|template 表示实际生效的渲染引擎。"""
    cfg = load_llm_config()
    engine = "template"
    if not force_template and not _bool("LLM_FORCE_TEMPLATE", False) \
            and cfg.enabled and cfg.api_key and cfg.base_url:
        engine = "llm"
    return {
        "enabled": cfg.enabled,
        "provider": cfg.provider,
        "model": cfg.model,
        "base_url": cfg.base_url,
        "engine": engine,
        "note": "LLM 仅用于表达层（render_narrative），不参与任何判定；"
                "不可用时自动降级模板（render_engine 记为 template）。",
    }
