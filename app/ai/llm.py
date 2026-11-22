from langchain_anthropic import ChatAnthropic
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import settings
from app.models.kb import EMBEDDING_DIM


# Swappable in tests; Claude rejects temperature.
def get_llm():
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        # Default 128K is refused without streaming.
        max_tokens=16000,
        # SDK retries timeouts, 429s and 5xx.
        max_retries=3,
        default_request_timeout=60,
    )


def get_embeddings():
    return GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        google_api_key=settings.gemini_api_key,
        output_dimensionality=EMBEDDING_DIM,
    )
