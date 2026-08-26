from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["development", "staging", "production"] = "development"
    model_mode: Literal["mock", "live"] = "mock"
    openai_api_key: str = ""
    openai_analysis_model: str = ""
    openai_judge_model: str = ""
    openai_image_model: str = ""
    openai_image_quality: Literal["low", "medium", "high", "auto"] = "medium"
    gemini_api_key: str = ""
    gemini_image_model: str = ""
    max_upload_mb: int = 15
    allowed_origins: str = "http://localhost:3000"
    app_access_token: str = ""
    judge_max_correction_rounds: int = 2
    judge_initial_visible_candidates: int = Field(default=1, ge=1, le=4)
    judge_initial_medical_candidates: int = Field(default=1, ge=1, le=4)
    judge_identity_min: int = 86
    judge_framing_min: int = 88
    judge_head_boundary_min: int = 90
    judge_target_natural_min: int = 48
    # Calibrated against the product's accepted examples: a restrained but
    # clearly perceptible contour change scores around 65, while unchanged
    # output or cosmetic-only changes remain below this line.
    judge_target_visible_min: int = 65
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
