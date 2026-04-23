from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    tavily_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./data/agent.db"
    claude_model: str = "claude-haiku-4-5-20251001"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
