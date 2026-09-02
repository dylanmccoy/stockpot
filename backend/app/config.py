from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RECIPE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./recipe.db"
    cors_origins: list[str] = ["http://localhost:5173"]
    # 0 is legal and meaningful: an instantly-expired token, which is how the
    # expiry branch is exercised in tests. A negative value is a ValidationError.
    session_ttl_days: int = Field(30, ge=0)
    allow_registration: bool = False
    registration_code: str | None = None


settings = Settings()
