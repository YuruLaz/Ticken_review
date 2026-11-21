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
    # Tagged on every LangSmith trace, so runs from different setups can be told apart.
    environment: str = "dev"

    # Empty defaults so the app and tests start without keys; only real LLM calls need them.
    # Claude writes (classify, draft); Gemini only embeds (Anthropic has no embedding model).
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"
    gemini_api_key: str = ""


settings = Settings()
