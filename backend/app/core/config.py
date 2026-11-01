"""
Application configuration — reads from .env via python-dotenv.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "aletheia_db"
    UPLOAD_DIR: str = "app/uploads"
    FRAMEWORK_VERSION: str = "1.0"
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
