import logging
import time
from functools import lru_cache
from typing import Any

from langchain.chat_models import init_chat_model

from ..config import settings

log = logging.getLogger(__name__)
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def _is_transient_error(error: BaseException) -> bool:
    current: BaseException | None = error
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        response = getattr(current, "response", None)
        code = (
            getattr(current, "code", None)
            or getattr(current, "status_code", None)
            or getattr(response, "status_code", None)
        )
        try:
            if int(code) in TRANSIENT_STATUS_CODES:
                return True
        except (TypeError, ValueError):
            pass
        current = current.__cause__ or current.__context__
    return False


def invoke_with_retry(runnable: Any, value: Any) -> Any:
    for attempt in range(3):
        try:
            return runnable.invoke(value)
        except Exception as error:
            if attempt == 2 or not _is_transient_error(error):
                raise
            log.warning(
                "Transient AI provider error; retrying request (%s/3)",
                attempt + 2,
            )
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError("AI provider retry loop exited unexpectedly")


@lru_cache
def structured(model: str, schema: type):
    """Model client for `schema`, built once and reused so documents share its HTTP connections."""
    return init_chat_model(model, temperature=0, api_key=settings.LLM_API_KEY or None, timeout=60,
                           max_retries=1, **settings.LLM_KWARGS).with_structured_output(schema)


@lru_cache
def chat_model(model: str):
    """Plain-text chat model shared by conversational features."""
    return init_chat_model(model, temperature=0, api_key=settings.LLM_API_KEY or None, timeout=60,
                           max_retries=1, **settings.LLM_KWARGS)
