from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class Evidence(BaseModel):
    reference_indexes: list[int] = Field(default_factory=list)
    note: str


class AestheticInsight(BaseModel):
    region: str
    title: str
    summary: str
    confidence: Literal["high", "medium", "low"]
    evidence: Evidence


class AestheticProfileResponse(BaseModel):
    id: str
    primary_direction: str
    secondary_direction: str
    anti_targets: list[str]
    insights: list[AestheticInsight]
    source_count: int
    generated_by: str
    prompt_version: str


class BoardPreviewRequest(BaseModel):
    url: HttpUrl


class BoardPreviewItem(BaseModel):
    id: str
    title: str
    thumbnail_url: str | None = None
    selected: bool = True


class BoardPreviewResponse(BaseModel):
    title: str
    source_url: str
    status: Literal["mock_ready", "ready", "limited"]
    message: str
    items: list[BoardPreviewItem]


class EditChange(BaseModel):
    id: str
    area: str
    title: str
    rationale: str
    instruction: str
    enabled: bool = True


class EditPlanResponse(BaseModel):
    id: str
    headline: str
    summary: str
    changes: list[EditChange]
    locked_regions: list[str]
    prompt_version: str
    intensity: Literal["natural", "visible"] = "natural"


class QualityVerdict(BaseModel):
    identity_score: int = Field(ge=0, le=100)
    framing_score: int = Field(ge=0, le=100)
    head_boundary_score: int = Field(ge=0, le=100)
    target_change_score: int = Field(ge=0, le=100)
    width_safety_score: int = Field(ge=0, le=100)
    cheek_safety_score: int = Field(ge=0, le=100)
    locked_region_score: int = Field(ge=0, le=100)
    hard_failures: list[str] = Field(default_factory=list)
    summary: str
    eligible: bool
    retry_instruction: str
    screening_stage: Literal["deterministic_precheck", "semantic_judge"] = "semantic_judge"


class RevisionVerdict(BaseModel):
    feedback_execution_score: int = Field(ge=0, le=100)
    identity_score: int = Field(ge=0, le=100)
    locked_region_score: int = Field(ge=0, le=100)
    original_baseline_score: int = Field(ge=0, le=100)
    hard_failures: list[
        Literal[
            "feedback_not_followed",
            "cumulative_identity_drift",
            "locked_region_changed",
            "original_baseline_lost",
            "change_overdone",
        ]
    ] = Field(default_factory=list)
    summary: str
    eligible: bool


class GenerationResponse(BaseModel):
    id: str
    status: Literal["completed"]
    result_mode: Literal["mock_original", "gemini_edit", "safe_original"]
    message: str
    quality_notes: list[str]
    result_image_base64: str | None = None
    result_mime_type: str | None = None
    quality_verdict: QualityVerdict | None = None
    candidate_count: int = 0
    correction_rounds: int = 0
    semantic_judge_count: int = 0
    deterministic_reject_count: int = 0
    stage_timings_ms: dict[str, int] = Field(default_factory=dict)
    generation_provider: Literal["mock", "gemini", "openai", "qwen", "unknown"] = "unknown"


class MedicalCandidate(BaseModel):
    id: str
    area: str
    goal: str
    priority: Literal["now", "later", "optional", "avoid"]
    method_category: str
    material_category: str
    discussion_range: str
    rationale: str
    evidence: str
    consultation_questions: list[str] = Field(default_factory=list)
    enabled: bool = True


class MedicalPlanResponse(BaseModel):
    id: str
    headline: str
    summary: str
    confirmed_direction: str
    preserve: list[str]
    candidates: list[MedicalCandidate]
    locked_regions: list[str]
    consultation_questions: list[str]
    safety_disclosure: str
    prompt_version: str


class ErrorResponse(BaseModel):
    detail: str
