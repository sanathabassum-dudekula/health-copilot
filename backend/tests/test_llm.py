from langchain_core.runnables import RunnableLambda

from app.ingestion.llm import invoke_with_retry


def test_invoke_with_retry_retries_and_returns_result():
    attempts = 0

    def flaky_call(value):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary model failure")
        return value

    assert invoke_with_retry(RunnableLambda(flaky_call), "ok") == "ok"
    assert attempts == 2
