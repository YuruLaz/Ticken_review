import langsmith
from langchain_core.tracers.langchain import get_client

from app.ai.llm.tracing import setup_tracing


def test_traces_are_masked_before_upload():
    setup_tracing()
    try:
        masked = get_client()._anonymizer({"body": "Card 5167 4401 2233 1234, call +995 599 12 34 56"})
    finally:
        langsmith.configure(client=None)

    assert masked == {"body": "Card 5167 **** **** 1234, call [phone number]"}
