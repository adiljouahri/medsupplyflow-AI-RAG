import os

import pytest

try:
    from deepeval.metrics import AnswerCorrectness
    from deepeval.test_case import LLMTestCase
except ImportError:
    AnswerCorrectness = None
    LLMTestCase = None

DEEPEVAL_MODEL = os.getenv("DEEPEVAL_MODEL", "gpt-4o-mini")
DEEPEVAL_API_KEY = os.getenv("DEEPEVAL_API_KEY")


def test_deepeval_ai_quality() -> None:
    """Optional DeepEval unit test for LLM answer quality."""
    if not DEEPEVAL_API_KEY:
        pytest.skip("Set DEEPEVAL_API_KEY to run the optional DeepEval AI test")
    if AnswerCorrectness is None or LLMTestCase is None:
        pytest.skip("deepeval is not installed")

    metric = AnswerCorrectness(
        threshold=0.8,
        model=DEEPEVAL_MODEL,
        api_key=DEEPEVAL_API_KEY,
    )

    cases = [
        LLMTestCase(
            input="What is the stock quantity for SKU SC-15?",
            actual_output="SC-15 has 10 units available.",
            expected_output="SC-15 has 10 units available.",
        ),
        LLMTestCase(
            input="Is SKU SC-15 approved for ordering?",
            actual_output="SC-15 is approved and has 10 units available.",
            expected_output="SC-15 is approved and has 10 units available.",
        ),
    ]

    for case in cases:
        metric.measure(case)
        assert metric.score >= metric.threshold, (
            f"DeepEval score below threshold: {metric.score} "
            f"(reason: {metric.reason})"
        )
