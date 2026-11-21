from langchain_anthropic import ChatAnthropic
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import settings
from app.models.kb import EMBEDDING_DIM


# Nodes call this instead of creating the model themselves, so tests can swap in a fake LLM.
# No temperature: current Claude models reject sampling parameters.
def get_llm():
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        # The library defaults to the model's maximum (128K), which the SDK refuses for a
        # non-streaming call; 16K is plenty for the thinking plus a classification or reply.
        max_tokens=16000,
    )


def get_embeddings():
    return GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        google_api_key=settings.gemini_api_key,
        output_dimensionality=EMBEDDING_DIM,
    )
