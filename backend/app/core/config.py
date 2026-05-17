from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    database_url: str = "postgresql+asyncpg://youyuan:youyuan@localhost:5432/youyuan"
    redis_url: str = "redis://localhost:6379"
    cors_origins: list[str] = ["http://localhost:5173"]

    claude_model: str = "claude-sonnet-4-6"
    session_ttl_seconds: int = 86400  # 24 hours
    waittime_cache_ttl_seconds: int = 300  # 5 minutes


settings = Settings()
