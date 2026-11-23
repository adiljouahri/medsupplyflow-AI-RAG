from langdetect import detect, LangDetectException, DetectorFactory

DetectorFactory.seed = 0

SUPPORTED_LANGUAGE_CODES = {"en", "es", "de"}


def detect_supported_language(text: str) -> str | None:
    """Return a supported language code, or None for unknown/ambiguous text."""
    try:
        code = detect(text)
    except LangDetectException:
        return None

    return code if code in SUPPORTED_LANGUAGE_CODES else None
