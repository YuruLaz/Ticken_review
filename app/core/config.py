from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Settings only reads .env into its own fields. LangSmith reads LANGSMITH_* straight from the
# environment, so .env is loaded into it too. Variables already set (e.g. by tests) win.
load_dotenv()


class Settings(BaseSettings):
    # ignore: .env also holds variables for other libraries (LANGSMITH_*), not just these fields.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Empty default so the app and tests start without a key; only real LLM calls need it.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"


settings = Settings()
