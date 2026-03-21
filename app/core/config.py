from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    COCKROACH_URL: str = "postgresql+psycopg://user:pass@localhost:26257/defaultdb?sslmode=disable"

    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB: str = "mydb"

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Aurora Hotel"
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    EMAIL_QUEUE_BATCH_SIZE: int = 10
    EMAIL_QUEUE_BATCH_DELAY_SECONDS: float = 0.5

settings = Settings()