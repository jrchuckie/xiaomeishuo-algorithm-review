from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["development", "staging", "production"] = "development"
    model_mode: Literal["mock", "live"] = "mock"
    openai_api_key: str = ""
    openai_analysis_model: str = ""
    gemini_api_key: str = ""
    gemini_image_model: str = ""
    max_upload_mb: int = 15
    allowed_origins: str = "http://localhost:3000"
    app_access_token: str = ""
    judge_max_correction_rounds: int = 2
    judge_identity_min: int = 86
    judge_framing_min: int = 88
    judge_head_boundary_min: int = 90
    judge_target_natural_min: int = 48
    judge_target_visible_min: int = 68
    judge_width_safety_min: int = 88
    judge_cheek_safety_min: int = 88
    judge_locked_region_min: int = 90

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
