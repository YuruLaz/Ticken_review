import langsmith
from langsmith.anonymizer import create_anonymizer

from app.ai.pii import mask_pii


def setup_tracing() -> None:
    """Makes LangChain's automatic tracing use a client that masks PII before uploading.

    Needed on top of the sanitize_input node: a trace also records the graph's raw input,
    before that node runs. The anonymizer sees every string in every input and output.
    """
    anonymizer = create_anonymizer(lambda text, path: mask_pii(text))
    langsmith.configure(client=langsmith.Client(anonymizer=anonymizer))
