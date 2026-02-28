"""
AegisLab AI — Application Configuration
Loads settings from environment variables via pydantic-settings.
"""

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the AegisLab AI platform."""

    PROJECT_NAME: str = "AegisLab AI"

    # Gemini keys (2 for redundancy)
    GEMINI_API_KEY_1: str = ""
    GEMINI_API_KEY_2: str = ""

    # OpenAI keys (2 for redundancy)
    OPENAI_API_KEY_1: str = ""
    OPENAI_API_KEY_2: str = ""

    # Legacy single-key support (mapped to slot 1 if present)
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    TIDB_URL: str
    FIREBASE_CRED_PATH: str = r"C:\Users\Admin\Documents\aegislab-ai\AegisLab AI.json"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @property
    def gemini_keys(self) -> list[str]:
        """Return all non-empty Gemini keys in order."""
        keys = []
        # Legacy single key takes slot 1 if slot 1 is empty
        k1 = self.GEMINI_API_KEY_1 or self.GEMINI_API_KEY or ""
        if k1:
            keys.append(k1)
        if self.GEMINI_API_KEY_2:
            keys.append(self.GEMINI_API_KEY_2)
        return keys

    @property
    def openai_keys(self) -> list[str]:
        """Return all non-empty OpenAI keys in order."""
        keys = []
        k1 = self.OPENAI_API_KEY_1 or self.OPENAI_API_KEY or ""
        if k1:
            keys.append(k1)
        if self.OPENAI_API_KEY_2:
            keys.append(self.OPENAI_API_KEY_2)
        return keys


settings = Settings()
