from app.core.config import settings


class AIServiceProxy:
    """Resolve the configured provider only when an AI operation starts."""

    def __getattr__(self, name: str):
        return getattr(get_claude_service(), name)


def get_claude_service():
    """Return the configured real provider, or deterministic mock AI locally."""
    if settings.USE_MOCK_CLAUDE:
        from app.services.mock_claude_service import MockClaudeService
        return MockClaudeService()

    if settings.active_ai_provider == "openrouter":
        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY is required when AI_PROVIDER=openrouter "
                "and USE_MOCK_CLAUDE is false."
            )
        from app.services.openrouter_service import OpenRouterService
        return OpenRouterService()

    if settings.active_ai_provider != "anthropic":
        raise RuntimeError(
            "AI_PROVIDER must be either 'anthropic' or 'openrouter' when "
            "USE_MOCK_CLAUDE is false."
        )

    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is required when AI_PROVIDER=anthropic "
            "and USE_MOCK_CLAUDE is false."
        )

    from app.services.claude_service import ClaudeService
    return ClaudeService()
