from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Argus"
    database_url: str = "postgresql+psycopg://argus:argus@localhost:5432/argus"
    # A service is DOWN once this many heartbeat intervals pass without a beat.
    missed_beats_before_down: int = 2
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
