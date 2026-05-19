"""LLM factory — Foundation Model API on Databricks, or a fake model for tests."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from agent_memory.config import Settings


def build_chat_model(settings: Settings | None = None) -> BaseChatModel:
    """Return a chat model backed by FM API when credentials exist."""
    cfg = settings or Settings.from_env()
    if not cfg.databricks_configured:
        msg = (
            "DATABRICKS_HOST and DATABRICKS_TOKEN must be set to call the Foundation Model API. "
            "Use build_chat_model_for_tests() in unit tests."
        )
        raise RuntimeError(msg)

    from langchain_community.chat_models import ChatDatabricks

    return ChatDatabricks(
        endpoint=cfg.fm_api_endpoint,
        target_uri="databricks",
    )


def build_chat_model_for_tests() -> BaseChatModel:
    """Deterministic model for CI without workspace credentials."""
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    return FakeListChatModel(
        responses=[
            "Based on the client's stated goals, I recommend reviewing allocation "
            "against their moderate risk profile before any changes."
        ]
    )
