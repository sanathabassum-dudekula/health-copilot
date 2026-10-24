from functools import lru_cache
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable

from ..config import settings


@lru_cache
def chat_model(model: str):
    return init_chat_model(model, temperature=0, api_key=settings.LLM_API_KEY or None, timeout=60,
                           max_retries=1, **settings.LLM_KWARGS)


@lru_cache
def structured(model: str, schema: type):
    """Return a cached model client with structured output for `schema`."""
    return chat_model(model).with_structured_output(schema)


def invoke_with_retry(model: Runnable[Any, Any], input_value: Any) -> Any:
    return model.with_retry(stop_after_attempt=2).invoke(input_value)
