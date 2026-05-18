from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AIInternalProfile(BaseModel):
    code: str
    api_mode: str = "anthropic"
    base_url: str = ""
    api_key: str = ""
    model_id: str = ""
    name: str = ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    database_url: str = "postgresql+asyncpg://youyuan:youyuan@localhost:5432/youyuan"
    redis_url: str = "redis://localhost:6379"
    cors_origins: list[str] = ["http://localhost:5173"]

    claude_model: str = "claude-sonnet-4-6"
    session_ttl_seconds: int = 86400  # 24 hours
    waittime_cache_ttl_seconds: int = 300  # 5 minutes
    ai_debug_logging: bool = False
    ai_distill_profile_code: str = ""
    ai_internal_profiles: list[AIInternalProfile] = Field(default_factory=list)


settings = Settings()
