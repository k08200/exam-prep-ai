from app.core.config import settings


def get_claude_service():
    """Return real or mock Claude service based on USE_MOCK_CLAUDE setting."""
    if settings.USE_MOCK_CLAUDE:
        from app.services.mock_claude_service import MockClaudeService
        return MockClaudeService()
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is required when USE_MOCK_CLAUDE is false."
        )
    from app.services.claude_service import ClaudeService
    return ClaudeService()
