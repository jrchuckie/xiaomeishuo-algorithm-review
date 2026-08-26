import asyncio
import io
import json
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw

from app.models import MedicalCandidate, MedicalPlanResponse, QualityVerdict
from app.providers import (
    _ensure_medical_direction_integrity,
    _gemini_edit_prompt,
    _openai_image_size,
    _prepare_openai_mask,
    _quality_judge_prompt,
    _restore_source_aspect,
    _should_fallback_from_gemini,
)
from app.quality import (
    THRESHOLDS,
    deterministic_scores,
    finalize_verdict,
    retry_instruction,
    run_generation_pipeline,
)


def portrait(*, damaged_top: bool = False, damaged_corner: bool = False) -> bytes:
    image = Image.new("RGB", (768, 1024), "#cfb49f")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 767, 1023), outline="#315060", width=30)
    draw.ellipse((180, 100, 588, 590), fill="#6f4939")
    draw.ellipse((205, 150, 563, 650), fill="#c88e72")
    draw.ellipse((285, 330, 325, 355), fill="#201c1c")
    draw.ellipse((440, 330, 480, 355), fill="#201c1c")
    draw.line((370, 355, 355, 450, 395, 455), fill="#7a4539", width=8)
    draw.arc((315, 450, 450, 535), 10, 170, fill="#73392f", width=8)
    if damaged_top:
        draw.rectangle((0, 0, 767, 115), fill="#f4f4f4")
    if damaged_corner:
        draw.rectangle((0, 0, 150, 280), fill="#f4f4f4")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def semantic(
    *,
    target: int = 80,
    failures: list[str] | None = None,
    summary: str = "safe",
) -> QualityVerdict:
    return QualityVerdict(
        identity_score=96,
        framing_score=96,
        head_boundary_score=96,
        target_change_score=target,
        width_safety_score=96,
        cheek_safety_score=96,
        locked_region_score=96,
        hard_failures=failures or [],
        summary=summary,
        eligible=not failures,
        retry_instruction="",
    )


def medical_plan(candidates: list[MedicalCandidate]) -> MedicalPlanResponse:
    return MedicalPlanResponse(
        id=str(uuid4()),
        headline="plan",
        summary="summary",
        confirmed_direction="direction",
        preserve=["identity"],
        candidates=candidates,
        locked_regions=["eyes"],
        consultation_questions=[],
        safety_disclosure="not medical advice",
        prompt_version="test",
    )


def candidate(area: str, priority: str = "now") -> MedicalCandidate:
    return MedicalCandidate(
        id=str(uuid4()),
        area=area,
        goal=f"{area} goal",
        priority=priority,
        method_category="consultation",
        material_category="category",
        discussion_range="in person",
        rationale="confirmed",
        evidence="photo",
        consultation_questions=[],
    )


def test_golden_manifest_covers_all_required_scenarios() -> None:
    manifest = json.loads(
        (Path(__file__).parent / "golden" / "manifest.json").read_text()
    )
    assert len(manifest) == 14
    assert len({item["id"] for item in manifest}) == 14


def test_thresholds_are_centralized_and_strict_for_identity_and_locks() -> None:
    assert THRESHOLDS.identity >= 85
    assert THRESHOLDS.head_boundary >= 90
    assert THRESHOLDS.locked_region >= 90
    assert THRESHOLDS.target_visible > THRESHOLDS.target_natural


def test_safe_candidate_is_eligible() -> None:
    image = portrait()
    verdict = finalize_verdict(
        semantic(),
        deterministic_scores(image, image),
        intensity="visible",
    )
    assert verdict.eligible is True
    assert verdict.hard_failures == []


def test_top_and_hair_edge_pixel_change_is_diagnostic_until_semantic_judge() -> None:
    source = portrait()
    result = portrait(damaged_top=True)
    deterministic = deterministic_scores(source, result)
    assert deterministic["head_boundary_score"] < THRESHOLDS.head_boundary
    assert "head_or_hair_cropped" not in deterministic["hard_failures"]
    verdict = finalize_verdict(
        semantic(failures=["head_or_hair_cropped"]),
        deterministic,
        intensity="visible",
    )
    assert verdict.eligible is False


def test_hair_corner_pixel_change_is_diagnostic_until_semantic_judge() -> None:
    source = portrait()
    result = portrait(damaged_corner=True)
    deterministic = deterministic_scores(source, result)
    assert deterministic["head_boundary_score"] < THRESHOLDS.head_boundary
    assert "head_or_hair_cropped" not in deterministic["hard_failures"]


def test_harmless_border_rerender_defers_to_semantic_head_judge() -> None:
    image = portrait()
    verdict = finalize_verdict(
        semantic(),
        {
            "framing_score": 100,
            "head_boundary_score": 60,
            "hard_failures": [],
        },
        intensity="visible",
    )
    assert verdict.head_boundary_score == 96
    assert "head_boundary_below_threshold" not in verdict.hard_failures


def test_supported_model_ratio_quantization_does_not_false_fail_framing() -> None:
    source = Image.new("RGB", (1408, 768), "#ccb29f")
    result = Image.new("RGB", (1536, 864), "#ccb29f")
    source_buffer, result_buffer = io.BytesIO(), io.BytesIO()
    source.save(source_buffer, "PNG")
    result.save(result_buffer, "PNG")
    scores = deterministic_scores(source_buffer.getvalue(), result_buffer.getvalue())
    assert scores["framing_score"] >= THRESHOLDS.framing
    assert "framing_changed" not in scores["hard_failures"]


def test_openai_fallback_preserves_portrait_orientation() -> None:
    assert _openai_image_size(portrait()) == "1024x1536"

    provider_output = Image.new("RGB", (1024, 1536), "#aabbcc")
    output_buffer = io.BytesIO()
    provider_output.save(output_buffer, "JPEG")
    restored = _restore_source_aspect(output_buffer.getvalue(), portrait())
    with Image.open(io.BytesIO(restored)) as image:
        assert image.size == (768, 1024)


def test_openai_mask_is_rgba_and_matches_source_size() -> None:
    source = portrait()
    mask = Image.new("L", (384, 512), 255)
    ImageDraw.Draw(mask).ellipse((80, 200, 300, 480), fill=0)
    mask_buffer = io.BytesIO()
    mask.save(mask_buffer, "PNG")
    source_png, mask_png = _prepare_openai_mask(source, mask_buffer.getvalue())
    with Image.open(io.BytesIO(source_png)) as prepared_source:
        assert prepared_source.mode == "RGBA"
        assert prepared_source.size == (768, 1024)
    with Image.open(io.BytesIO(mask_png)) as prepared_mask:
        assert prepared_mask.mode == "RGBA"
        assert prepared_mask.size == (768, 1024)
        assert prepared_mask.getchannel("A").getextrema() == (0, 255)


def test_gemini_fallback_only_handles_provider_availability() -> None:
    assert _should_fallback_from_gemini(400, "Prepayment credits are depleted")
    assert _should_fallback_from_gemini(429, "rate limited")
    assert _should_fallback_from_gemini(503, "unavailable")
    assert not _should_fallback_from_gemini(400, "blocked by safety policy")


def test_every_semantic_incident_is_ineligible_and_gets_targeted_retry() -> None:
    cases = {
        "face_or_head_widened": "双颧",
        "cheekbone_expanded": "颧骨",
        "cheek_hollowed": "颧下",
        "locked_region_changed": "未选部位",
        "identity_drift": "身份",
    }
    image = portrait()
    deterministic = deterministic_scores(image, image)
    for code, expected_text in cases.items():
        verdict = finalize_verdict(
            semantic(failures=[code]),
            deterministic,
            intensity="visible",
        )
        assert verdict.eligible is False
        assert expected_text in verdict.retry_instruction


def test_visible_skin_only_cannot_pass_but_visible_structure_can() -> None:
    image = portrait()
    low = finalize_verdict(
        semantic(target=THRESHOLDS.target_visible - 1),
        deterministic_scores(image, image),
        intensity="visible",
    )
    high = finalize_verdict(
        semantic(target=THRESHOLDS.target_visible),
        deterministic_scores(image, image),
        intensity="visible",
    )
    assert "target_change_below_threshold" in low.hard_failures
    assert low.eligible is False
    assert high.eligible is True


def test_unknown_semantic_failure_code_cannot_block_release() -> None:
    image = portrait()
    verdict = finalize_verdict(
        semantic(failures=["targetChangeScore"]),
        deterministic_scores(image, image),
        intensity="visible",
    )

    assert verdict.eligible is True
    assert verdict.hard_failures == []


def test_medical_direction_set_is_preserved_exactly_and_avoid_explanation_remains() -> None:
    selected = ["下颌线", "下巴", "面中", "鼻基底", "太阳穴", "唇周"]
    plan = medical_plan([
        candidate("下颌线"),
        candidate("下巴"),
        candidate("眼睛", priority="avoid"),
    ])
    result = _ensure_medical_direction_integrity(plan, selected, locale="zh-Hans")
    enabled_areas = [item.area for item in result.candidates if item.priority != "avoid"]
    assert enabled_areas == selected
    assert all(item.enabled for item in result.candidates if item.area in selected)
    assert any(item.area == "眼睛" and item.priority == "avoid" for item in result.candidates)


def test_pipeline_never_returns_failed_candidate_and_stops_after_two_corrections() -> None:
    image = portrait()
    generated_count = 0

    async def generate(_: str | None) -> tuple[bytes, str]:
        nonlocal generated_count
        generated_count += 1
        return image, "image/png"

    async def judge(_: bytes, candidates: list[tuple[bytes, str]]) -> list[QualityVerdict]:
        return [
            semantic(failures=["identity_drift"], summary="failed")
            for _ in candidates
        ]

    winner, count, rounds, verdicts = asyncio.run(
        run_generation_pipeline(
            source=(image, "image/png"),
            intensity="visible",
            initial_count=2,
            generate=generate,
            judge=judge,
        )
    )
    assert winner is None
    assert rounds == 2
    assert generated_count == 4
    assert count == 4
    assert all(not item.eligible for item in verdicts)


def test_pipeline_uses_targeted_correction_and_returns_only_passing_retry() -> None:
    image = portrait()
    corrections: list[str | None] = []
    judge_calls = 0

    async def generate(correction: str | None) -> tuple[bytes, str]:
        corrections.append(correction)
        return image, "image/png"

    async def judge(_: bytes, candidates: list[tuple[bytes, str]]) -> list[QualityVerdict]:
        nonlocal judge_calls
        judge_calls += 1
        if judge_calls == 1:
            return [semantic(target=10) for _ in candidates]
        return [semantic(target=90) for _ in candidates]

    winner, _, rounds, _ = asyncio.run(
        run_generation_pipeline(
            source=(image, "image/png"),
            intensity="visible",
            initial_count=2,
            generate=generate,
            judge=judge,
        )
    )
    assert winner is not None
    assert winner.verdict is not None and winner.verdict.eligible
    assert rounds == 1
    assert corrections[-1] is not None
    assert "结构变化再增强一个受控档位" in corrections[-1]


def test_quality_judge_prompt_localizes_explanation() -> None:
    zh = _quality_judge_prompt(["下巴"], ["眼睛"], "visible", "zh-Hans")
    en = _quality_judge_prompt(["chin"], ["eyes"], "visible", "en")
    assert "Simplified Chinese" in zh
    assert "natural English" in en
    assert "0–100 scale" in zh
    assert "Never use a 0–5" in zh
    assert "confirmed target" in retry_instruction(
        ["target_change_below_threshold"],
        locale="en",
    )


def test_revision_prompt_keeps_original_as_immutable_baseline() -> None:
    prompt = _gemini_edit_prompt(
        [],
        ["眼睛", "鼻子", "嘴唇"],
        feedback="下巴再明显一点",
        has_previous_result=True,
    )
    assert "原始照片" in prompt
    assert "上一版" in prompt
    assert "身份" in prompt
    assert "唯一基准" in prompt


def test_retry_instruction_for_unselected_eyes_restores_eye_identity() -> None:
    instruction = retry_instruction(["locked_region_changed"])
    for term in ["眼型", "眼距", "虹膜", "视线"]:
        assert term in instruction


def test_pipeline_skips_semantic_judge_for_deterministic_hard_failure() -> None:
    source = portrait()
    tiny = io.BytesIO()
    Image.new("RGB", (128, 128), "#ccb29f").save(tiny, "PNG")
    generated = [tiny.getvalue(), source]
    judge_calls = 0

    async def generate(_: str | None) -> tuple[bytes, str]:
        return generated.pop(0), "image/png"

    async def judge(_: bytes, candidates: list[tuple[bytes, str]]) -> list[QualityVerdict]:
        nonlocal judge_calls
        judge_calls += 1
        return [semantic() for _ in candidates]

    winner, count, rounds, verdicts = asyncio.run(
        run_generation_pipeline(
            source=(source, "image/png"),
            intensity="visible",
            initial_count=1,
            generate=generate,
            judge=judge,
        )
    )

    assert winner is not None
    assert count == 2
    assert rounds == 1
    assert judge_calls == 1
    assert verdicts[0].screening_stage == "deterministic_precheck"
    assert verdicts[-1].screening_stage == "semantic_judge"


def test_pipeline_surfaces_initial_generation_error() -> None:
    image = portrait()

    async def generate(_: str | None) -> tuple[bytes, str]:
        raise ValueError("provider credits depleted")

    async def judge(_: bytes, candidates: list[tuple[bytes, str]]) -> list[QualityVerdict]:
        return [semantic() for _ in candidates]

    try:
        asyncio.run(
            run_generation_pipeline(
                source=(image, "image/png"),
                intensity="visible",
                initial_count=1,
                generate=generate,
                judge=judge,
            )
        )
    except ValueError as exc:
        assert "credits depleted" in str(exc)
    else:
        raise AssertionError("initial provider failure must be visible to the caller")
