from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RECIPE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./recipe.db"
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
