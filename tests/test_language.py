from app.agent.language import detect_supported_language


def test_spanish_language_detection() -> None:
    assert detect_supported_language(
        "Enviando 5 unidades de producto para Demo Clinic B antes 2026-06-30"
    ) == "es"


def test_german_language_detection() -> None:
    assert detect_supported_language(
        "Senden 5 Einheiten zum Demo Clinic C bis 2026-06-30"
    ) == "de"


def test_english_language_detection() -> None:
    assert detect_supported_language(
        "Send 5 units to Demo Clinic A by 2026-06-30"
    ) == "en"


def test_unsupported_language_returns_none() -> None:
    assert detect_supported_language("") is None
