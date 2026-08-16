"""集中导入所有模型，确保 Base.metadata 被完整注册（供 Alembic / create_all 使用）。"""
from app.models.enums import (  # noqa: F401
    WorldStatus, CharacterType, CharacterStatus, CareerStage,
    ProjectType, ProjectStatus, EventLevel, InterventionType, MemoryScope,
    CompanyType, CompanyStatus, CompanyStyle, MarketOutcome,
    FestivalLevel, FestivalSection, EditionStatus, AwardNarrativeTag,
    MediaOutletType, MediaStance, NewsType, ReportType, RenderEngine,
)
from app.models.world import World, SimulationTick  # noqa: F401
from app.models.character import (  # noqa: F401
    Character, CharacterAttributeLog, CharacterCareerHistory, Relationship,
)
from app.models.project import Project, ProjectCast  # noqa: F401
from app.models.event import Event  # noqa: F401
from app.models.misc import Intervention, Memory  # noqa: F401
from app.models.company import Company, CompanyHistory  # noqa: F401
from app.models.market import MarketSnapshot, ProjectMarket  # noqa: F401
from app.models.festival import (  # noqa: F401
    Festival, FestivalEdition, FestivalSelection, FestivalAward,
)
from app.models.award import (  # noqa: F401
    Award, AwardSeason, AwardCategory, Nomination, Winner,
    AwardSeasonStat, AwardAchievement,
)
from app.models.crisis import Scandal, CrisisPR  # noqa: F401  # §17.3 舆论与危机公关
from app.models.commerce import Endorsement, MagazineCover  # noqa: F401  # §17.1 商业时尚
from app.models.romance import Romance  # noqa: F401  # §17.2 人际情感网络
from app.models.media import MediaOutlet  # noqa: F401
from app.models.news import News  # noqa: F401
