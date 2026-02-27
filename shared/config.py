"""
AegisLab AI — Application Configuration
Loads settings from environment variables via pydantic-settings.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the AegisLab AI platform."""

    PROJECT_NAME: str = "AegisLab AI"
    GEMINI_API_KEY: str
    OPENAI_API_KEY: str
    TIDB_URL: str
    FIREBASE_CRED_PATH: str = r"C:\Users\Admin\Documents\aegislab-ai\AegisLab AI.json"

    model_config = {
        "env_file": ".env.example",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
