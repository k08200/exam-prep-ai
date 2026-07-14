from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Set


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    ENVIRONMENT: str = "development"

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
    MAX_USER_STORAGE_BYTES: int = 2 * 1024 * 1024 * 1024  # 2GB per account
    MAX_ANALYSIS_INPUT_CHARS: int = 600_000
    ALLOWED_EXTENSIONS: Set[str] = {
        ".pdf",
        ".pptx",
        ".docx",
        ".png",
        ".jpg",
        ".jpeg",
    }
    UPLOAD_DIR: str = "./uploads"
    MATERIAL_PROCESSING_STALE_MINUTES: int = 30
    EXAM_GENERATION_STALE_MINUTES: int = 30
    REQUEST_TIMEOUT_SECONDS: float = 60.0
    AUTH_RATE_LIMIT_MAX_FAILURES: int = 5
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 300
    AI_STREAM_HEARTBEAT_SECONDS: float = 15.0
    AI_STREAM_EVENT_TIMEOUT_SECONDS: float = 180.0

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
    CLAUDE_MODEL: str = "claude-opus-4-8"
    # Extended thinking budgets (tokens) for legacy model snapshots.
    # Current model families use adaptive thinking with CLAUDE_THINKING_EFFORT.
    THINKING_BUDGET_ANALYSIS: int = 30000  # for professor style analysis (deep)
    THINKING_BUDGET_GENERATION: int = 10000  # for exam question generation
    CLAUDE_THINKING_EFFORT: str = "high"

    @property
    def cors_origins(self) -> list[str]:
        """Return configured CORS origins from a comma-separated env value."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"prod", "production"}

    def validate_runtime_settings(self) -> None:
        """Fail fast on unsafe production configuration."""
        if not self.is_production:
            return

        default_secret = "change-this-secret-key-in-production-use-openssl-rand-hex-32"
        if self.SECRET_KEY == default_secret or len(self.SECRET_KEY) < 32:
            raise RuntimeError("Production SECRET_KEY must be at least 32 random characters.")
        if self.USE_MOCK_CLAUDE:
            raise RuntimeError("Production must set USE_MOCK_CLAUDE=false.")
        if not self.ANTHROPIC_API_KEY:
            raise RuntimeError("Production Claude mode requires ANTHROPIC_API_KEY.")
        if self.AUTO_CREATE_TABLES:
            raise RuntimeError("Production must set AUTO_CREATE_TABLES=false and use migrations.")
        if not self.cors_origins:
            raise RuntimeError("Production CORS_ORIGINS must include the frontend origin.")
        if self.REQUEST_TIMEOUT_SECONDS <= 0:
            raise RuntimeError("Production REQUEST_TIMEOUT_SECONDS must be positive.")
        if self.AUTH_RATE_LIMIT_MAX_FAILURES <= 0:
            raise RuntimeError("Production AUTH_RATE_LIMIT_MAX_FAILURES must be positive.")
        if self.AUTH_RATE_LIMIT_WINDOW_SECONDS <= 0:
            raise RuntimeError("Production AUTH_RATE_LIMIT_WINDOW_SECONDS must be positive.")
        if self.AI_STREAM_HEARTBEAT_SECONDS <= 0:
            raise RuntimeError("Production AI_STREAM_HEARTBEAT_SECONDS must be positive.")
        if self.AI_STREAM_EVENT_TIMEOUT_SECONDS <= 0:
            raise RuntimeError("Production AI_STREAM_EVENT_TIMEOUT_SECONDS must be positive.")
        if self.MAX_ANALYSIS_INPUT_CHARS <= 0:
            raise RuntimeError("Production MAX_ANALYSIS_INPUT_CHARS must be positive.")
        if self.MAX_USER_STORAGE_BYTES <= 0:
            raise RuntimeError("Production MAX_USER_STORAGE_BYTES must be positive.")
        if self.EXAM_GENERATION_STALE_MINUTES <= 0:
            raise RuntimeError("Production EXAM_GENERATION_STALE_MINUTES must be positive.")


settings = Settings()
