MIN_EXTRACTED_TEXT_CHARS = 40
INSUFFICIENT_TEXT_ERROR = (
    "Could not extract enough text from this file. Try a text-based PDF, DOCX, "
    "PPTX, or a clearer scan."
)


def _compact_length(text: str | None) -> int:
    return len(" ".join((text or "").split()))


def is_usable_extracted_text(text: str | None) -> bool:
    return _compact_length(text) >= MIN_EXTRACTED_TEXT_CHARS


def require_usable_extracted_text(text: str | None) -> str:
    stripped = (text or "").strip()
    if not is_usable_extracted_text(stripped):
        raise ValueError(INSUFFICIENT_TEXT_ERROR)
    return stripped
