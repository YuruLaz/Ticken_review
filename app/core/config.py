from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Empty default so the app and tests start without a key; only real LLM calls need it.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"


settings = Settings()
