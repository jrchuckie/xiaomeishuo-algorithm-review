import json
from time import perf_counter

from .config import get_settings
from .models import GenerationResponse

settings = get_settings()


def started_at() -> float:
    return perf_counter()


def record_generation(
    *,
    installation_id: str,
    workflow: str,
    prompt_version: str,
    response: GenerationResponse,
    started: float,
) -> None:
    verdict = response.quality_verdict
    # Deliberately bounded, structured metadata only. Never include images,
    # Base64, API keys, personal contact details or user free text.
    event = {
        "event": "generation_quality",
        "severity": "INFO",
        "installation_id": installation_id,
        "workflow": workflow,
        "model": settings.gemini_image_model,
        "judge_model": settings.openai_analysis_model,
        "prompt_version": prompt_version,
        "candidate_count": response.candidate_count,
        "semantic_judge_count": response.semantic_judge_count,
        "deterministic_reject_count": response.deterministic_reject_count,
        "correction_rounds": response.correction_rounds,
        "elapsed_ms": round((perf_counter() - started) * 1000),
        "result_mode": response.result_mode,
        "generation_provider": response.generation_provider,
        "scores": (
            {
                "identity": verdict.identity_score,
                "framing": verdict.framing_score,
                "head_boundary": verdict.head_boundary_score,
                "target_change": verdict.target_change_score,
                "width_safety": verdict.width_safety_score,
                "cheek_safety": verdict.cheek_safety_score,
                "locked_region": verdict.locked_region_score,
            }
            if verdict
            else None
        ),
        "failure_codes": verdict.hard_failures if verdict else [],
    }
    print(json.dumps(event, ensure_ascii=True, separators=(",", ":")), flush=True)
