import yaml

from app.llm_logging import LLMInteractionLogger, llm_logging_context


def test_log_interaction_writes_yaml(tmp_path):
    log_path = tmp_path / "llm_interactions.yaml"
    logger = LLMInteractionLogger(log_path=log_path)

    logger.log_interaction(
        provider="openai",
        model="gpt-test",
        prompt={"messages": ["hello"]},
        response={"content": "world"},
        metadata={"stage": "unit"},
    )

    content = log_path.read_text(encoding="utf-8")
    documents = list(yaml.safe_load_all(content))
    assert len(documents) == 1
    entry = documents[0]
    assert entry["provider"] == "openai"
    assert entry["model"] == "gpt-test"
    assert entry["metadata"] == {"stage": "unit"}


def test_logging_context_injects_metadata(tmp_path):
    log_path = tmp_path / "llm_interactions.yaml"
    logger = LLMInteractionLogger(log_path=log_path)

    with llm_logging_context(component="script", stage="test"):
        logger.log_interaction(
            provider="openai",
            model="gpt-test",
            prompt="prompt",
            response="response",
        )

    documents = list(yaml.safe_load_all(log_path.read_text(encoding="utf-8")))
    assert documents[0]["context"] == {"component": "script", "stage": "test"}
