import inspect

from app.agent.tools import hybrid_search


def test_hybrid_search_requires_clinic_code() -> None:
    parameters = inspect.signature(hybrid_search).parameters
    assert "clinic_code" in parameters
    assert "session" in parameters
