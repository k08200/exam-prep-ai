from pydantic_settings import BaseSettings
from typing import Set


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/exam_prep_ai"

    # JWT Auth
    SECRET_KEY: str = "change-this-secret-key-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # File uploads
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS: Set[str] = {
        ".pdf",
        ".pptx",
        ".ppt",
        ".docx",
        ".doc",
        ".png",
        ".jpg",
        ".jpeg",
    }
    UPLOAD_DIR: str = "./uploads"

    # Claude model config
    CLAUDE_MODEL: str = "claude-opus-4-7"
    # Extended thinking budgets (tokens).
    # NOTE: The API does not support thinking.type = "adaptive".
    # We use {"type": "enabled", "budget_tokens": N} for explicit control.
    THINKING_BUDGET_ANALYSIS: int = 30000  # for professor style analysis (deep)
    THINKING_BUDGET_GENERATION: int = 10000  # for exam question generation

    class Config:
        env_file = ".env"


settings = Settings()
