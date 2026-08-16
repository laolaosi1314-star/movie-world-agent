"""全局枚举定义。
使用 str 枚举，便于 JSON 序列化与数据库存储。
"""
import enum


class WorldStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"  # 只读存档


class CharacterType(str, enum.Enum):
    ACTOR = "actor"
    DIRECTOR = "director"
    WRITER = "writer"
    PRODUCER = "producer"
    CINEMATOGRAPHER = "cinematographer"
    EDITOR = "editor"
    COMPOSER = "composer"
    SINGER = "singer"    # 音乐人（Phase 3.x 多领域奖项）
    AGENT = "agent"
    EXECUTIVE = "executive"


class CharacterStatus(str, enum.Enum):
    ACTIVE = "active"
    RETIRED = "retired"
    DECEASED = "deceased"
    ARCHIVED = "archived"  # 进入名人堂/娱乐库


class CareerStage(str, enum.Enum):
    DEBUT = "debut"
    RISING = "rising"
    ESTABLISHED = "established"
    PEAK = "peak"
    VETERAN = "veteran"
    LEGACY = "legacy"


class ProjectType(str, enum.Enum):
    FILM = "film"
    TV = "tv"
    WEBSERIES = "webseries"
    VARIETY = "variety"
    ANIMATION = "animation"
    DOCUMENTARY = "documentary"
    SHORT = "short"
    ALBUM = "album"      # 音乐：专辑（Phase 3.x 多领域奖项）
    SINGLE = "single"    # 音乐：单曲（Phase 3.x 多领域奖项）


class ProjectStatus(str, enum.Enum):
    CONCEPT = "concept"
    APPROVED = "approved"
    FINANCING = "financing"
    CASTING = "casting"
    SCRIPTING = "scripting"
    PRODUCTION = "production"
    POSTPRODUCTION = "postproduction"
    FESTIVAL = "festival"
    RELEASED = "released"
    ARCHIVED = "archived"


class EventLevel(str, enum.Enum):
    NORMAL = "normal"
    IMPORTANT = "important"
    MAJOR = "major"
    HISTORIC = "historic"


class InterventionType(str, enum.Enum):
    ATTRIBUTE = "attribute"
    CREATE = "create"
    AWARD = "award"
    STATUS = "status"
    RELATION = "relation"
    FINANCING = "financing"      # 项目融资（投资人注资，留痕审计）


class MemoryScope(str, enum.Enum):
    SHORT = "short"
    LONG = "long"
    WORLD = "world"


# ===== Phase 2: 公司系统 =====
class CompanyType(str, enum.Enum):
    PRODUCTION = "production"      # 制作公司
    DISTRIBUTION = "distribution"  # 发行公司
    AGENCY = "agency"              # 经纪公司
    STREAMING = "streaming"        # 流媒体平台
    CAPITAL = "capital"            # 资本/投资方


class CompanyStatus(str, enum.Enum):
    ACTIVE = "active"
    DORMANT = "dormant"    # 休眠
    MERGING = "merging"    # 并购中
    BANKRUPT = "bankrupt"  # 破产


class CompanyStyle(str, enum.Enum):
    COMMERCIAL_BLOCKBUSTER = "commercial_blockbuster"  # 商业大片
    ARTHOUSE = "arthouse"                              # 艺术电影
    NEWCOMER_DIRECTOR = "newcomer_director"            # 新人导演
    TV_FOCUSED = "tv_focused"                          # 电视剧向
    VARIETY = "variety"                                # 综艺向


class MarketOutcome(str, enum.Enum):
    BLOCKBUSTER = "blockbuster"                    # 爆冷/爆款
    SLEEPER_HIT = "sleeper_hit"                    # 黑马
    WORD_OF_MOUTH_REVERSAL = "word_of_mouth_reversal"  # 口碑逆袭
    HIGH_OPEN_LOW_CLOSE = "high_open_low_close"    # 高开低走
    FLOP_BUT_AWARDED = "flop_but_awarded"          # 票房惨败但奖项成功
    HIT_BUT_NO_AWARD = "hit_but_no_award"          # 票房成功但奖项失败
    CULT_CLASSIC = "cult_classic"                  # 小成本成经典
    NORMAL = "normal"                              # 正常


# ===== Phase 3: 电影节系统 =====
class FestivalLevel(str, enum.Enum):
    INTERNATIONAL_A = "international_a"
    INTERNATIONAL_B = "international_b"
    NATIONAL_A = "national_a"
    NATIONAL_B = "national_b"
    REGIONAL = "regional"


class FestivalSection(str, enum.Enum):
    MAIN_COMPETITION = "main_competition"  # 主竞赛
    SPECIAL_SCREENING = "special_screening"  # 特别展映
    NEWCOMER = "newcomer"                  # 新人单元
    DOCUMENTARY = "documentary"            # 纪录片单元
    SHORT = "short"                        # 短片单元


class EditionStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    COMPLETED = "completed"


# ===== Phase 3: 奖项叙事标签 =====
class AwardNarrativeTag(str, enum.Enum):
    BIGGEST_WINNER = "biggest_winner"      # 最大赢家
    BIGGEST_SNUB = "biggest_snub"          # 最大遗珠
    BIGGEST_UPSET = "biggest_upset"        # 最大冷门
    YOUNGEST_WINNER = "youngest_winner"    # 最年轻获奖者
    OLDEST_WINNER = "oldest_winner"        # 最年长获奖者
    CONSECUTIVE_NOMS = "consecutive_noms"  # 连续提名
    BACK_TO_BACK = "back_to_back"          # 连庄
    SWEEP = "sweep"                        # 横扫
    DOUBLE_NOM = "double_nom"              # 双提
    DOUBLE_WIN = "double_win"              # 双冠
    MOST_CONTROVERSIAL = "most_controversial"  # 最具争议一届


# ===== Phase 6 前置：负面奖项体系 =====
class AwardType(str, enum.Enum):
    POSITIVE = "positive"    # 正奖（金屏奖等，表彰优秀）
    NEGATIVE = "negative"    # 负奖（金酸梅奖等，吐槽烂片/烂表演）


# ===== Phase 3.x：多领域 / 跨界奖项体系（电视·音乐） =====
class WorkDomain(str, enum.Enum):
    """被评作品的领域轴，与 award_type(正/负)、kind(类目客体) 正交。"""
    FILM = "film"
    TV = "tv"
    MUSIC = "music"


class CategoryKind(str, enum.Enum):
    """奖项类别所评判的客体种类，分领域给出全集（§15.3）。"""
    PROJECT = "project"            # 作品本身（最佳影片 / 最佳剧集）
    DIRECTOR = "director"          # 导演
    ACTOR_MALE = "actor_male"      # 男演员 / 男主角
    ACTOR_FEMALE = "actor_female"  # 女演员 / 女主角
    WRITER = "writer"              # 编剧（影视）/ 作词（音乐，见 LYRICIST）
    ALBUM = "album"                # 最佳专辑（music）
    SINGLE = "single"              # 最佳单曲（music）
    SINGER_MALE = "singer_male"    # 最佳男歌手（music）
    SINGER_FEMALE = "singer_female"  # 最佳女歌手（music）
    LYRICIST = "lyricist"          # 最佳作词（music）
    COMPOSER = "composer"          # 最佳作曲（music）


# ===== Phase 6：用户角色体系 =====
class PlayerRole(str, enum.Enum):
    """玩家在影视世界中的身份类别（无状态契约下的角色建模）。

    - AUDIENCE 观众：观察/游玩，可打分、推进模拟；
    - CRITIC   影评人：可含剧评人/音乐评论人（critic_domains 限定专长领域），
                可写正式评论、按 domain 创建奖项；
    - INVESTOR 投资人：可为作品融资/投资；
    - GM       上帝模式：全权限，含干预世界（留痕 interventions）与玩家管理。
    """
    AUDIENCE = "audience"
    CRITIC = "critic"
    INVESTOR = "investor"
    GM = "gm"


# ===== Phase 后续（§17.3 舆论与危机公关） =====
class ScandalType(str, enum.Enum):
    """黑料/丑闻类型（领域无关，电影/电视/音乐人物通用）。"""
    AFFAIR = "affair"                      # 出轨
    DRUGS = "drugs"                        # 吸毒
    TAX = "tax"                            # 税务问题
    SLIP_OF_TONGUE = "slip_of_tongue"      # 言论翻车
    SURROGACY = "surrogacy"                # 代孕
    PLAGIARISM = "plagiarism"              # 抄袭
    DOMESTIC_VIOLENCE = "domestic_violence"  # 家暴
    OTHER = "other"                        # 其它


class ScandalStage(str, enum.Enum):
    """丑闻演化状态机（确定性、可重放）。"""
    LATENT = "latent"        # 潜伏期：黑料已埋，尚未公开引爆
    SPREADING = "spreading"  # 发酵中：已爆料，正在传播
    ERUPTED = "erupted"      # 爆发：实锤/大面积传播，舆情重创
    RESOLVING = "resolving"  # 公关处理中：已采取公关动作
    RESOLVED = "resolved"    # 已平息（冷处理/洗白成功）
    COLLAPSED = "collapsed"  # 塌房：身败名裂，不可逆


class PRStrategy(str, enum.Enum):
    """多阶段公关动作（确定性舆论恢复曲线建模）。"""
    COLD_TREATMENT = "cold_treatment"  # 冷处理：不回应，让热度自然冷却
    LAWYER_LETTER = "lawyer_letter"    # 发律师函：威慑降温，但"捂嘴"风险
    APOLOGY = "apology"                # 公开道歉：实锤时认错加分，未实锤时"变相认锤"
    BUY_TRENDING = "buy_trending"      # 买热搜：仅短期压热度，口碑略负
    COUNTER_MKT = "counter_mkt"        # 反向营销/洗白反转：证据弱可大翻盘，实锤遭嘲


# ===== §17.1 商业时尚与塌房违约金 =====
class EndorsementTier(str, enum.Enum):
    """代言层级（决定代言费基准与塌房贬值权重）。"""
    TOP_LUXURY = "top_luxury"      # 顶奢
    HIGH_LUXURY = "high_luxury"    # 高奢
    MASS = "mass"                  # 大众 / 快消
    BRAND_FRIEND = "brand_friend"  # 品牌挚友 / 推广


class ContractStatus(str, enum.Enum):
    """代言 / 封面合约状态机（确定性）。"""
    ACTIVE = "active"          # 生效中
    TERMINATED = "terminated"  # 协商解约（无违约金）
    BREACHED = "breached"      # 塌房违约（触发违约金）
    EXPIRED = "expired"        # 到期自然结束


class MagazineTier(str, enum.Enum):
    """杂志封面层级。"""
    TOP5 = "top5"                # 五大刊（顶刊）
    SECOND_TIER = "second_tier"  # 二线刊


# ===== §17.2 人际情感网络（恋情/绯闻/结婚生子 + 粉丝蝴蝶效应） =====
class RomanceType(str, enum.Enum):
    """情感关系性质（发生在两个人物之间，领域无关）。"""
    DATING = "dating"        # 恋情（公开交往）
    RUMOR = "rumor"          # 绯闻 / 疑似（未官宣）
    MARRIED = "married"      # 结婚
    COHABIT = "cohabit"      # 同居 / 隐婚


class RomanceStatus(str, enum.Enum):
    """情感关系状态机（确定性）。"""
    ACTIVE = "active"        # 交往中（可公开 is_public 或地下）
    ENDED = "ended"          # 已结束（分手 / 离婚）


# ===== Phase 4: 媒体 / 新闻系统 =====
class MediaOutletType(str, enum.Enum):
    SERIOUS = "serious"      # 严肃媒体（如权威日报/电影杂志）
    TABLOID = "tabloid"      # 八卦/娱乐媒体
    INDUSTRY = "industry"    # 行业媒体（垂直专业）
    FAN = "fan"              # 影迷社区/自媒体


class MediaStance(str, enum.Enum):
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    CRITICAL = "critical"
    HYPE = "hype"            # 过度吹捧
    SKEPTICAL = "skeptical"  # 质疑/毒舌


class NewsType(str, enum.Enum):
    BULLETIN = "bulletin"            # 快讯
    REVIEW = "review"                # 评论
    INTERVIEW = "interview"          # 专访
    BOXOFFICE = "boxoffice"          # 票房报道
    AWARD_PREDICTION = "award_prediction"  # 奖项预测
    RED_CARPET = "red_carpet"        # 红毯报道
    CONTROVERSY = "controversy"      # 争议
    INDUSTRY_NEWS = "industry_news"  # 行业新闻


class ReportType(str, enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class RenderEngine(str, enum.Enum):
    """新闻/报道的文本渲染来源。LLM 仅允许在表达层（详见 BLUEPRINT 架构约束）。"""
    TEMPLATE = "template"
    LLM = "llm"
