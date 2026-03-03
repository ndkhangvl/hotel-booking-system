from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    COCKROACH_URL: str = "postgresql+psycopg://user:pass@localhost:26257/defaultdb?sslmode=disable"

    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB: str = "mydb"

settings = Settings()