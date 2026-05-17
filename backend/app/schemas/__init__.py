from pydantic import BaseModel
from typing import Literal


ParkId = Literal["shanghai_disney", "hongkong_disney"]
AttractionCategory = Literal[
    "thrill_ride", "family_ride", "show", "character_meet", "dining", "shopping", "parade"
]
PreferenceTag = Literal[
    "thrill_rides", "family_rides", "shows", "character_meet", "photography", "dining", "parades"
]
ExperienceLevel = Literal["first_time", "visited_before", "frequent"]
FitnessLevel = Literal[1, 2, 3, 4, 5]


class PartyMember(BaseModel):
    type: Literal["adult", "child", "elderly"]
    age: int | None = None


class PlanningInfo(BaseModel):
    park_id: ParkId
    visit_date: str
    entry_time: str
    exit_time: str
    party: list[PartyMember]
    preferences: list[PreferenceTag] = []
    must_do_attractions: list[str] = []
    fitness_level: FitnessLevel = 3
    experience_level: ExperienceLevel = "first_time"
    special_notes: str = ""
    special_needs: list[str] = []


class RouteItem(BaseModel):
    time: str
    attraction_id: str
    attraction_name: str
    estimated_wait: int
    note: str | None = None
    type: Literal["attraction", "dining", "show", "break"] = "attraction"


class AIConfig(BaseModel):
    """用户自定义 AI 配置，每次请求携带，后端不存储"""
    auth_token: str
    base_url: str = "https://api.anthropic.com"
    model: str = "claude-sonnet-4-6"


class CreateSessionRequest(PlanningInfo):
    ai_config: AIConfig | None = None
    user_id: str | None = None  # 关联用户，可选（匿名用户不传）


class CreateSessionResponse(BaseModel):
    session_id: str
    initial_plan: str
    route: list[RouteItem]


class ChatRequest(BaseModel):
    session_id: str
    message: str
    current_location: dict | None = None
    ai_config: AIConfig | None = None


class UpdateSessionRequest(BaseModel):
    completed_attractions: list[str] | None = None
    current_location: dict | None = None


class UpdateSessionResponse(BaseModel):
    session_id: str
    completed_attractions: list[str]


class ShareSessionResponse(BaseModel):
    code: str
    expires_in_seconds: int


class ResumeSessionResponse(BaseModel):
    session_id: str
    planning: PlanningInfo
    completed_attractions: list[str]
    current_location: dict | None


# ── User / Visit schemas ──────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    user_id: str  # 用户自填的唯一标识（昵称/口令）


class LoginResponse(BaseModel):
    user_id: str
    is_new: bool  # True = 新用户刚注册，False = 老用户登录


class VisitSummary(BaseModel):
    visit_id: str
    park_id: str
    visit_date: str
    status: str  # active | archived
    completed_count: int
    created_at: str
    planning_snapshot: dict | None = None  # 入园前规划信息，用于前端恢复 session


class VisitListResponse(BaseModel):
    user_id: str
    visits: list[VisitSummary]


class ArchiveVisitResponse(BaseModel):
    visit_id: str
    status: str


class WaitTimeItem(BaseModel):
    attraction_id: str
    attraction_name: str | None = None
    wait_minutes: int | None
    status: Literal["open", "closed", "down", "unknown"]
    last_updated: str


class WaitTimesResponse(BaseModel):
    park_id: str
    last_updated: str
    attractions: list[WaitTimeItem]
