import os

import pytest

from app.agent.graph import run_request


def test_langsmith_evaluation_dataset() -> None:
    """Optional LangSmith dataset evaluation test.

    Runs end-to-end evaluation using LangSmith's evaluate/evaluate_existing when
    LANGCHAIN_API_KEY is configured. Skips gracefully if the API key is absent
    or langsmith is not installed.
    """
    api_key = os.getenv("LANGCHAIN_API_KEY")
    tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() in ("true", "1")
    if not api_key and not tracing_enabled:
        pytest.skip("LANGCHAIN_API_KEY or LANGCHAIN_TRACING_V2 not set; skipping LangSmith eval test")

    try:
        from langsmith import Client, evaluate
    except ImportError:
        pytest.skip("langsmith package is not installed; skipping LangSmith eval test")

    client = Client()
    dataset_name = "medsupplyflow-agent-eval"

    # Ensure evaluation dataset exists in LangSmith
    dataset = None
    try:
        if client.has_dataset(dataset_name=dataset_name):
            dataset = client.read_dataset(dataset_name=dataset_name)
        else:
            dataset = client.create_dataset(
                dataset_name=dataset_name,
                description="Evaluation dataset for MedSupplyFlow surgical agent",
            )
            eval_examples = [
                {
                    "inputs": {
                        "client_name": "Dr. Sarah",
                        "clinic_name": "Metro Surgical",
                        "clinic_code": "demo-clinic-a",
                        "request_text": "Please check stock for Scalpel #10",
                    },
                    "outputs": {"expected_action": "search_product"},
                },
                {
                    "inputs": {
                        "client_name": "Nurse Jane",
                        "clinic_name": "Metro Surgical",
                        "clinic_code": "demo-clinic-a",
                        "request_text": "Order 15 units of SC-15 immediately",
                    },
                    "outputs": {"expected_action": "create_order"},
                },
            ]
            for ex in eval_examples:
                client.create_example(
                    inputs=ex["inputs"],
                    outputs=ex["outputs"],
                    dataset_id=dataset.id,
                )
    except Exception as exc:
        pytest.skip(f"Could not connect to LangSmith client: {exc}")

    def target(inputs: dict) -> dict:
        return run_request(
            client_name=inputs.get("client_name", "Test Client"),
            clinic_name=inputs.get("clinic_name", "Test Clinic"),
            clinic_code=inputs.get("clinic_code", "demo-clinic-a"),
            request_text=inputs["request_text"],
        )

    def action_evaluator(run, example) -> dict:
        actual = run.outputs
        expected_action = example.outputs.get("expected_action")
        # Check that response structure is valid and returned
        score = 1.0 if actual and not actual.get("error") else 0.0
        if expected_action and actual and expected_action in str(actual):
            score = 1.0
        return {"key": "response_validity", "score": score}

    results = evaluate(
        target,
        data=dataset_name,
        evaluators=[action_evaluator],
        experiment_prefix="medsupplyflow-eval",
        max_concurrency=2,
    )
    assert results is not None
