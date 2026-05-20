from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Set


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

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
    MAX_UPLOAD_FILES: int = 10
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
    MATERIAL_PROCESSING_STALE_MINUTES: int = 30

    # Set to true to use mock responses (no API key required)
    USE_MOCK_CLAUDE: bool = False
    AUTO_CREATE_TABLES: bool = True
    RUN_MIGRATIONS: bool = True
    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:3003,"
        "http://127.0.0.1:3003,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:8080,"
        "http://127.0.0.1:8080,"
        "tauri://localhost,"
        "http://tauri.localhost"
    )

    # Claude model config
    CLAUDE_MODEL: str = "claude-opus-4-1-20250805"
    # Extended thinking budgets (tokens).
    # NOTE: The API does not support thinking.type = "adaptive".
    # We use {"type": "enabled", "budget_tokens": N} for explicit control.
    THINKING_BUDGET_ANALYSIS: int = 30000  # for professor style analysis (deep)
    THINKING_BUDGET_GENERATION: int = 10000  # for exam question generation

    @property
    def cors_origins(self) -> list[str]:
        """Return configured CORS origins from a comma-separated env value."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
