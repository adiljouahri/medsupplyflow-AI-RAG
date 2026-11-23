import re

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

PII_PATTERNS = (
    re.compile(r"\b[\w.-]+@[\w.-]+\.\w+\b"),
    re.compile(r"\+?\d[\d\s().-]{6,}\d"),
    re.compile(r"\b(?:patient|record|client|id|ref)[\s:=]+[A-Z0-9-]{4,}\b", re.IGNORECASE),
)

INJECTION_PATTERNS = (
    re.compile(r"ignore (all|the|your|previous) instructions", re.IGNORECASE),
    re.compile(r"system prompt|developer message|jailbreak", re.IGNORECASE),
    re.compile(r"act as (?:a|an|the) .*", re.IGNORECASE),
    re.compile(r"you are now .*", re.IGNORECASE),
    re.compile(r"reveal (?:the|your) (?:secret|instruction|prompt)", re.IGNORECASE),
    re.compile(r"do not follow (?:the|my|these) instructions", re.IGNORECASE),
)


class UnsafeRequest(ValueError):
    """Raised when a request contains prompt-injection content."""


def _mask_phone(match: re.Match[str]) -> str:
    value = match.group(0)
    if ISO_DATE.fullmatch(value):
        return value
    return "[PHONE_NUMBER]"


def mask_pii(text: str) -> str:
    """Mask phone numbers, emails, and identifiers before any LLM call."""
    masked = text
    masked = PII_PATTERNS[0].sub("[EMAIL]", masked)
    masked = PII_PATTERNS[1].sub(_mask_phone, masked)
    masked = PII_PATTERNS[2].sub("[IDENTIFIER]", masked)
    return masked


def detect_prompt_injection(text: str) -> bool:
    return any(pattern.search(text) for pattern in INJECTION_PATTERNS)


def validate_request(text: str) -> str:
    if detect_prompt_injection(text):
        raise UnsafeRequest("prompt injection detected; request escalated to human review")
    return mask_pii(text)
