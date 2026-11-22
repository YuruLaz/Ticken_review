from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into os.environ for LangSmith.
load_dotenv()


class Settings(BaseSettings):
    # .env holds other libraries' variables too.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Tags every trace with this setup.
    environment: str = "dev"

    # Claude writes, Gemini embeds; keys optional.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"
    gemini_api_key: str = ""


settings = Settings()
