import langsmith
from langchain_core.tracers.langchain import get_client

from app.ai.tracing import setup_tracing


def test_traces_are_masked_before_upload():
    setup_tracing()
    try:
        # The client LangChain's automatic tracing will use, and the hook it applies to run inputs.
        masked = get_client()._anonymizer({"body": "Card 5167 4401 2233 1234, call +995 599 12 34 56"})
    finally:
        langsmith.configure(client=None)  # don't leak the global client into other tests

    assert masked == {"body": "Card 5167 **** **** 1234, call [phone number]"}
