from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings


# Nodes call this instead of creating the model themselves, so tests can swap in a fake LLM.
def get_llm():
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,  # classification and routing should be repeatable, not creative
    )
