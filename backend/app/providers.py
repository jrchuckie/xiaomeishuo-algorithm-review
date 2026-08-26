from __future__ import annotations

import base64
import io
import json
from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

import httpx
from fastapi import HTTPException
from PIL import Image, ImageOps

from .config import get_settings
from .models import (
    AestheticInsight,
    AestheticProfileResponse,
    EditChange,
    EditPlanResponse,
    Evidence,
    GenerationResponse,
    MedicalCandidate,
    MedicalPlanResponse,
    QualityVerdict,
    RevisionVerdict,
)
from .quality import run_generation_pipeline

ImageInput = tuple[bytes, str]
settings = get_settings()


def compile_revision_feedback(feedback: str | None) -> dict[str, Any]:
    text = (feedback or "").strip()
    normalized = text.lower()
    operations: list[str] = []
    keyword_groups = {
        "strengthen": ("加强", "更明显", "再清楚", "再小", "再窄", "more", "stronger"),
        "weaken": ("减弱", "弱一点", "自然一点", "不要这么", "less", "weaker", "subtle"),
        "restore": ("恢复", "还原", "回到原图", "撤销", "restore", "revert", "original"),
        "lock": ("不要动", "不动", "锁定", "保持不变", "keep", "lock", "unchanged"),
    }
    for operation, keywords in keyword_groups.items():
        if any(keyword in normalized for keyword in keywords):
            operations.append(operation)
    if text and not operations:
        operations.append("adjust")
    return {
        "raw_feedback": text,
        "operations": operations,
        "identity_baseline": "original",
        "previous_result_role": "diagnostic_reference_only",
        "unmentioned_regions": "locked_to_original",
    }


class AnalysisProvider(ABC):
    @abstractmethod
    async def create_profile(
        self,
        references: list[ImageInput],
        calibration_history: list[str] | None = None,
        locale: str = "zh-Hans",
    ) -> AestheticProfileResponse:
        raise NotImplementedError

    @abstractmethod
    async def create_edit_plan(
        self,
        profile: AestheticProfileResponse,
        intensity: str,
        source: ImageInput,
        locale: str = "zh-Hans",
    ) -> EditPlanResponse:
        raise NotImplementedError

    @abstractmethod
    async def create_medical_plan(
        self,
        profile: AestheticProfileResponse,
        preferences: dict[str, Any],
        selected_directions: list[str],
        front: ImageInput,
        side: ImageInput | None,
        intensity: str,
        locale: str = "zh-Hans",
    ) -> MedicalPlanResponse:
        raise NotImplementedError


class ImageProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        source: ImageInput,
        plan: EditPlanResponse,
        previous_image: ImageInput | None = None,
        feedback: str | None = None,
        locale: str = "zh-Hans",
    ) -> GenerationResponse:
        raise NotImplementedError

    @abstractmethod
    async def generate_medical(
        self,
        source: ImageInput,
        plan: MedicalPlanResponse,
        intensity: str,
        previous_image: ImageInput | None = None,
        feedback: str | None = None,
        locale: str = "zh-Hans",
    ) -> GenerationResponse:
        raise NotImplementedError


class MockAnalysisProvider(AnalysisProvider):
    async def create_profile(
        self,
        references: list[ImageInput],
        calibration_history: list[str] | None = None,
        locale: str = "zh-Hans",
    ) -> AestheticProfileResponse:
        reference_count = len(references)
        last_index = max(reference_count, 1)
        return AestheticProfileResponse(
            id=str(uuid4()),
            primary_direction="自然原生的结构感",
            secondary_direction="真实肤质 · 利落轮廓 · 健康气色",
            anti_targets=["模板脸", "过度磨皮", "无依据放大眼睛", "改变本人身份"],
            insights=[
                AestheticInsight(
                    region="整体气质",
                    title="自然、有辨识度",
                    summary="样本共同指向真实人物感，不追求千篇一律的精修模板。",
                    confidence="high",
                    evidence=Evidence(
                        reference_indexes=list(range(1, min(last_index, 3) + 1)),
                        note="来自多张参考图共同出现的真实肤质与自然光感。",
                    ),
                ),
                AestheticInsight(
                    region="轮廓",
                    title="边界清晰但不过度削窄",
                    summary="偏好更干净的外轮廓，同时保留本人原有骨相与面部量感。",
                    confidence="medium",
                    evidence=Evidence(
                        reference_indexes=[1, last_index] if last_index > 1 else [1],
                        note="参考图中清晰轮廓比瘦脸或尖下巴更稳定。",
                    ),
                ),
                AestheticInsight(
                    region="肤质",
                    title="保留纹理的通透感",
                    summary="更在意肤色与光线干净，而不是磨掉全部毛孔。",
                    confidence="medium",
                    evidence=Evidence(
                        reference_indexes=[min(2, last_index)],
                        note="自然光、轻修质感是可重复观察到的信号。",
                    ),
                ),
            ],
            source_count=reference_count,
            generated_by="Mock 多模态分析",
            prompt_version="profile-mvp-v1",
        )

    async def create_edit_plan(
        self,
        profile: AestheticProfileResponse,
        intensity: str,
        source: ImageInput,
        locale: str = "zh-Hans",
    ) -> EditPlanResponse:
        strength = "一眼可见" if intensity == "visible" else "自然克制"
        return EditPlanResponse(
            id=str(uuid4()),
            headline=f"按你的审美做一次{strength}的优化",
            summary=(
                f"以“{profile.primary_direction}”为基准，只处理光线、肤质和轮廓边界；"
                "眼睛、鼻子、嘴唇、身份、背景与构图全部锁定。"
            ),
            changes=[
                EditChange(
                    id="light",
                    area="光线",
                    title="恢复干净、自然的面部光线",
                    rationale="匹配审美档案中的真实感和健康气色。",
                    instruction="校正偏色和局部过曝，保留原始光位。",
                ),
                EditChange(
                    id="skin",
                    area="肤质",
                    title="匀净但保留真实纹理",
                    rationale="用户偏好通透感而不是重度磨皮。",
                    instruction="减弱油光与局部色差，保留毛孔和本人肤色。",
                ),
                EditChange(
                    id="contour",
                    area="轮廓",
                    title="让下颌与脸部边界更利落",
                    rationale="档案偏好清晰结构，但反对模板化瘦脸。",
                    instruction="增强轮廓边界，不放大颧骨，不做尖窄 V 脸。",
                ),
            ],
            locked_regions=["身份", "眼睛", "鼻子", "嘴唇", "发型", "服装", "背景", "构图"],
            prompt_version="edit-plan-mvp-v1",
            intensity=intensity,
        )

    async def create_medical_plan(
        self,
        profile: AestheticProfileResponse,
        preferences: dict[str, Any],
        selected_directions: list[str],
        front: ImageInput,
        side: ImageInput | None,
        intensity: str,
        locale: str = "zh-Hans",
    ) -> MedicalPlanResponse:
        areas = list(dict.fromkeys(selected_directions)) or ["下颌线", "下巴", "面中"]
        candidates = [
            MedicalCandidate(
                id=f"medical-{index}",
                area=area,
                goal=f"让{area}更接近已确认的个人审美方向",
                priority="now" if index < 2 else "later",
                method_category="先面诊评估结构与软组织，再决定是否需要非手术方案",
                material_category="由医生根据组织条件选择匹配的材料类别",
                discussion_range="仅在面诊后讨论个人用量与分阶段安排",
                rationale=f"来自审美档案“{profile.primary_direction}”与用户主动选择。",
                evidence="正面与 45° 照片用于本人映射；参考图仅表达审美方向。",
                consultation_questions=[
                    f"{area}的目标主要涉及骨性结构还是软组织？",
                    "有哪些可逆与不可逆路径，分别有什么风险？",
                ],
            )
            for index, area in enumerate(areas)
        ]
        return MedicalPlanResponse(
            id=str(uuid4()),
            headline="先确认目标效果，再把它变成面诊顺序",
            summary="这份方案把个人审美、本人照片和决策边界放在同一张地图里。",
            confirmed_direction=profile.primary_direction,
            preserve=["本人身份", "眼睛大小与眼型", "鼻部辨识度", "原生肤色"],
            candidates=candidates,
            locked_regions=["眼睛", "鼻子", "眉毛", "嘴唇", "发型", "背景", "构图"],
            consultation_questions=[
                "如果不做、保守做、分阶段做，三种路径的差异是什么？",
                "哪些变化可逆，哪些需要更长恢复期？",
                "如何避免模板化和过度治疗？",
            ],
            safety_disclosure="用于审美决策与面诊沟通，不构成诊断或处方。材料与用量以医生面诊为准。",
            prompt_version="medical-plan-mock-v1",
        )


class MockImageProvider(ImageProvider):
    async def generate(
        self,
        source: ImageInput,
        plan: EditPlanResponse,
        previous_image: ImageInput | None = None,
        feedback: str | None = None,
        locale: str = "zh-Hans",
    ) -> GenerationResponse:
        return GenerationResponse(
            id=str(uuid4()),
            status="completed",
            result_mode="mock_original",
            message="当前为 Mock 模式：结果页沿用原图，用于验证完整交互。",
            quality_notes=["本人身份锁定", "未选部位锁定", "真实模型可随时启用"],
            generation_provider="mock",
        )

    async def generate_medical(
        self,
        source: ImageInput,
        plan: MedicalPlanResponse,
        intensity: str,
        previous_image: ImageInput | None = None,
        feedback: str | None = None,
        locale: str = "zh-Hans",
    ) -> GenerationResponse:
        return GenerationResponse(
            id=str(uuid4()),
            status="completed",
            result_mode="mock_original",
            message="当前为 Mock 模式：沿用原图验证医美决策全流程。",
            quality_notes=["本人身份锁定", "未选部位锁定", "效果仅表达审美目标"],
            generation_provider="mock",
        )


class OpenAIAnalysisProvider(AnalysisProvider):
    async def create_profile(
        self,
        references: list[ImageInput],
        calibration_history: list[str] | None = None,
        locale: str = "zh-Hans",
    ) -> AestheticProfileResponse:
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": _profile_prompt(
                    len(references),
                    calibration_history=calibration_history,
                    locale=locale,
                ),
            }
        ]
        for data, mime_type in references:
            optimized, optimized_type = _optimize_image(data, mime_type, max_dimension=1024)
            content.append(
                {
                    "type": "input_image",
                    "image_url": _data_url(optimized, optimized_type),
                    "detail": "low",
                }
            )
        payload = await _openai_json_response(
            content=content,
            schema_name="aesthetic_profile",
            schema=_profile_schema(),
        )
        payload.update(
            id=str(uuid4()),
            source_count=len(references),
            generated_by=settings.openai_analysis_model,
            prompt_version="profile-live-v1",
        )
        try:
            return AestheticProfileResponse.model_validate(payload)
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="审美画像结构校验失败，请重试。") from exc

    async def create_edit_plan(
        self,
        profile: AestheticProfileResponse,
        intensity: str,
        source: ImageInput,
        locale: str = "zh-Hans",
    ) -> EditPlanResponse:
        data, mime_type = _optimize_image(*source, max_dimension=1280)
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": _edit_plan_prompt(profile, intensity, locale),
            },
            {
                "type": "input_image",
                "image_url": _data_url(data, mime_type),
                "detail": "high",
            },
        ]
        payload = await _openai_json_response(
            content=content,
            schema_name="edit_plan",
            schema=_edit_plan_schema(),
        )
        payload.update(
            id=str(uuid4()),
            prompt_version="edit-plan-live-v1",
            intensity=intensity,
        )
        try:
            plan = EditPlanResponse.model_validate(payload)
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="修图方案结构校验失败，请重试。") from exc
        plan.changes = [
            change
            for change in plan.changes
            if change.area.strip().lower()
            not in {
                "构图",
                "背景",
                "裁切",
                "发型",
                "发际线",
                "composition",
                "background",
                "hairstyle",
            }
        ]
        permanent_locks = ["背景", "构图", "画幅", "裁切", "发型", "发际线", "服装", "配饰"]
        plan.locked_regions = list(dict.fromkeys([*plan.locked_regions, *permanent_locks]))
        return plan

    async def create_medical_plan(
        self,
        profile: AestheticProfileResponse,
        preferences: dict[str, Any],
        selected_directions: list[str],
        front: ImageInput,
        side: ImageInput | None,
        intensity: str,
        locale: str = "zh-Hans",
    ) -> MedicalPlanResponse:
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": _medical_plan_prompt(
                    profile,
                    preferences,
                    selected_directions,
                    intensity,
                    locale,
                ),
            }
        ]
        for image in [front, side]:
            if image is None:
                continue
            data, mime_type = _optimize_image(*image, max_dimension=1536)
            content.append(
                {
                    "type": "input_image",
                    "image_url": _data_url(data, mime_type),
                    "detail": "high",
                }
            )
        payload = await _openai_json_response(
            content=content,
            schema_name="medical_decision_plan",
            schema=_medical_plan_schema(),
        )
        payload.update(
            id=str(uuid4()),
            prompt_version="medical-plan-live-v1",
        )
        try:
            plan = MedicalPlanResponse.model_validate(payload)
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="医美决策方案结构校验失败，请重试。") from exc
        permanent_locks = ["身份", "背景", "构图", "画幅", "发型", "发际线", "服装", "配饰"]
        plan.locked_regions = list(dict.fromkeys([*plan.locked_regions, *permanent_locks]))
        plan = _ensure_medical_direction_integrity(
            plan,
            selected_directions,
            locale=locale,
        )
        plan.safety_disclosure = (
            "For aesthetic decision support and consultation preparation only; not a diagnosis or prescription. "
            "Material choice and personal dosage require an in-person clinician assessment."
            if locale.lower().startswith("en")
            else "用于审美决策与面诊沟通，不构成诊断或处方。材料选择与个人用量必须由医生面诊决定。"
        )
        return plan


class GeminiImageProvider(ImageProvider):
    def __init__(
        self,
        candidate_observer: Callable[[bytes, str, int], None] | None = None,
    ) -> None:
        self._candidate_observer = candidate_observer
        self._candidate_index = 0

    def _observe_candidate(self, result: tuple[bytes, str]) -> tuple[bytes, str]:
        self._candidate_index += 1
        if self._candidate_observer is not None:
            self._candidate_observer(result[0], result[1], self._candidate_index)
        return result

    async def generate(
        self,
        source: ImageInput,
        plan: EditPlanResponse,
        previous_image: ImageInput | None = None,
        feedback: str | None = None,
        locale: str = "zh-Hans",
    ) -> GenerationResponse:
        pipeline_started = perf_counter()
        enabled_changes = [change for change in plan.changes if change.enabled]
        if not enabled_changes:
            raise HTTPException(status_code=400, detail="请至少选择一个修图方向。")

        data, mime_type = _optimize_image(*source, max_dimension=3072, quality=96)
        requested_image_size = _gemini_output_size(data)
        prompt = _gemini_edit_prompt(
            enabled_changes,
            plan.locked_regions,
            feedback=feedback,
            has_previous_result=previous_image is not None,
        )
        providers_used: set[str] = set()
        stage_seconds = {"generation": 0.0, "quality_judge": 0.0}

        async def generate_candidate(correction: str | None) -> tuple[bytes, str]:
            attempt_prompt = prompt
            if correction:
                attempt_prompt += "\nQUALITY JUDGE CORRECTION — obey precisely:\n" + correction
            started = perf_counter()
            result = await _generate_live_image(
                    data=data,
                    mime_type=mime_type,
                    prompt=attempt_prompt,
                    previous_image=previous_image,
                    image_size=requested_image_size,
                    provider_trace=providers_used,
                )
            stage_seconds["generation"] += perf_counter() - started
            return self._observe_candidate(result)

        async def judge_candidates(
            original: bytes,
            candidates: list[tuple[bytes, str]],
        ) -> list[QualityVerdict]:
            started = perf_counter()
            result = await _openai_quality_judge(
                original,
                candidates,
                target_areas=[item.area for item in enabled_changes],
                locked_regions=plan.locked_regions,
                intensity=plan.intensity,
                locale=locale,
            )
            stage_seconds["quality_judge"] += perf_counter() - started
            return result

        verdicts: list[QualityVerdict] = []
        try:
            winner, candidate_count, correction_rounds, verdicts = await run_generation_pipeline(
                source=(data, mime_type),
                intensity=plan.intensity,
                initial_count=(
                    settings.judge_initial_visible_candidates
                    if plan.intensity == "visible"
                    else 1
                ),
                generate=generate_candidate,
                locale=locale,
                judge=judge_candidates,
            )
            if winner and winner.verdict:
                result_dimensions = _image_dimensions(winner.data)
                return GenerationResponse(
                    id=str(uuid4()),
                    status="completed",
                    result_mode="gemini_edit",
                    message=(
                        "Generated from your confirmed plan. The delivered image is stored only on this device."
                        if locale.lower().startswith("en")
                        else "已按确认方案生成。图片已返回 App，并只保存在本机。"
                    ),
                    quality_notes=[
                        (
                            "Only confirmed target areas were changed"
                            if locale.lower().startswith("en")
                            else "已按允许改动清单执行"
                        ),
                        (
                            "Unselected regions were locked"
                            if locale.lower().startswith("en")
                            else "未选部位已在生成提示中锁定"
                        ),
                        (
                            "Cheekbone expansion and unrequested eye enlargement were prohibited"
                            if locale.lower().startswith("en")
                            else "颧骨外扩与无依据放大眼睛已明确禁止"
                        ),
                        f"高清输出 {result_dimensions or requested_image_size}",
                        winner.verdict.summary,
                    ],
                    result_image_base64=base64.b64encode(winner.data).decode("ascii"),
                    result_mime_type=winner.mime_type,
                    quality_verdict=winner.verdict,
                    candidate_count=candidate_count,
                    correction_rounds=correction_rounds,
                    semantic_judge_count=sum(
                        item.screening_stage == "semantic_judge" for item in verdicts
                    ),
                    deterministic_reject_count=sum(
                        item.screening_stage == "deterministic_precheck" for item in verdicts
                    ),
                    stage_timings_ms=_stage_timings(stage_seconds, pipeline_started),
                    generation_provider=_generation_provider(providers_used),
                )
            last_verdict = verdicts[-1] if verdicts else None
        except (httpx.HTTPError, ValueError, HTTPException) as exc:
            candidate_count, correction_rounds, last_verdict = 0, 0, None
            last_error = str(exc)
        else:
            last_error = last_verdict.summary if last_verdict else "没有候选通过统一质量门槛"

        return GenerationResponse(
            id=str(uuid4()),
            status="completed",
            result_mode="safe_original",
            message=(
                "No candidate safely passed every quality gate, so the original photo was returned. Adjust the request and try again."
                if locale.lower().startswith("en")
                else "为保护本人身份与未选部位，本轮已安全保留原图；你可以直接调整要求并再次生成。"
            ),
            quality_notes=[
                (
                    "No ineligible candidate was shown"
                    if locale.lower().startswith("en")
                    else "未展示不可靠的生成结果"
                ),
                (
                    "Identity and the original photo were fully preserved"
                    if locale.lower().startswith("en")
                    else "本人身份与原图完整保留"
                ),
                (
                    f"Quality judge safe fallback: {last_error[:80]}"
                    if locale.lower().startswith("en")
                    else f"裁判系统已安全回退：{last_error[:80]}"
                ),
            ],
            result_image_base64=base64.b64encode(source[0]).decode("ascii"),
            result_mime_type=source[1],
            quality_verdict=last_verdict,
            candidate_count=candidate_count,
            correction_rounds=correction_rounds,
            semantic_judge_count=sum(
                item.screening_stage == "semantic_judge" for item in verdicts
            ),
            deterministic_reject_count=sum(
                item.screening_stage == "deterministic_precheck" for item in verdicts
            ),
            stage_timings_ms=_stage_timings(stage_seconds, pipeline_started),
            generation_provider=_generation_provider(providers_used),
        )

    async def generate_medical(
        self,
        source: ImageInput,
        plan: MedicalPlanResponse,
        intensity: str,
        previous_image: ImageInput | None = None,
        feedback: str | None = None,
        locale: str = "zh-Hans",
    ) -> GenerationResponse:
        pipeline_started = perf_counter()
        enabled = [item for item in plan.candidates if item.enabled and item.priority != "avoid"]
        if not enabled:
            raise HTTPException(status_code=400, detail="请至少确认一个目标方向。")
        data, mime_type = _optimize_image(*source, max_dimension=3072, quality=96)
        requested_image_size = _gemini_output_size(data)
        prompt = _gemini_medical_prompt(
            plan,
            enabled,
            intensity=intensity,
            feedback=feedback,
            has_previous_result=previous_image is not None,
        )
        providers_used: set[str] = set()
        stage_seconds = {"generation": 0.0, "quality_judge": 0.0}

        async def generate_candidate(correction: str | None) -> tuple[bytes, str]:
            attempt_prompt = prompt
            if correction:
                attempt_prompt += "\nQUALITY JUDGE CORRECTION — obey precisely:\n" + correction
            started = perf_counter()
            result = await _generate_live_image(
                    data=data,
                    mime_type=mime_type,
                    prompt=attempt_prompt,
                    previous_image=previous_image,
                    image_size=requested_image_size,
                    provider_trace=providers_used,
                )
            stage_seconds["generation"] += perf_counter() - started
            return self._observe_candidate(result)

        async def judge_candidates(
            original: bytes,
            candidates: list[tuple[bytes, str]],
        ) -> list[QualityVerdict]:
            started = perf_counter()
            result = await _openai_quality_judge(
                original,
                candidates,
                target_areas=[item.area for item in enabled],
                locked_regions=plan.locked_regions,
                intensity=intensity,
                locale=locale,
            )
            stage_seconds["quality_judge"] += perf_counter() - started
            return result

        verdicts: list[QualityVerdict] = []
        try:
            winner, candidate_count, correction_rounds, verdicts = await run_generation_pipeline(
                source=(data, mime_type),
                intensity=intensity,
                initial_count=settings.judge_initial_medical_candidates,
                generate=generate_candidate,
                locale=locale,
                judge=judge_candidates,
            )
            if winner and winner.verdict:
                return GenerationResponse(
                    id=str(uuid4()),
                    status="completed",
                    result_mode="gemini_edit",
                    message=(
                        "A combined aesthetic target preview was generated for consultation; it is not a treatment outcome promise."
                        if locale.lower().startswith("en")
                        else "已生成与你确认方向一致的审美目标图；它用于沟通目标，不是医学效果承诺。"
                    ),
                    quality_notes=[
                        "风险约束已前置到生成提示",
                        "未选部位与本人身份已锁定",
                        "眼睛未选时禁止放大，颧骨禁止外扩",
                        f"高清输出 {_image_dimensions(winner.data) or requested_image_size}",
                        winner.verdict.summary,
                    ],
                    result_image_base64=base64.b64encode(winner.data).decode("ascii"),
                    result_mime_type=winner.mime_type,
                    quality_verdict=winner.verdict,
                    candidate_count=candidate_count,
                    correction_rounds=correction_rounds,
                    semantic_judge_count=sum(
                        item.screening_stage == "semantic_judge" for item in verdicts
                    ),
                    deterministic_reject_count=sum(
                        item.screening_stage == "deterministic_precheck" for item in verdicts
                    ),
                    stage_timings_ms=_stage_timings(stage_seconds, pipeline_started),
                    generation_provider=_generation_provider(providers_used),
                )
            last_verdict = verdicts[-1] if verdicts else None
        except (httpx.HTTPError, ValueError, HTTPException) as exc:
            candidate_count, correction_rounds, last_verdict = 0, 0, None
            last_error = str(exc)
        else:
            last_error = last_verdict.summary if last_verdict else "没有候选通过统一质量门槛"
        return GenerationResponse(
            id=str(uuid4()),
            status="completed",
            result_mode="safe_original",
            message=(
                "No candidate safely met the identity and geometry constraints, so the original was returned."
                if locale.lower().startswith("en")
                else "这轮模型没有稳定满足身份与几何约束，因此已保留原图；可修改方向后继续生成。"
            ),
            quality_notes=[
                (
                    "No candidate failing identity or geometry checks was shown"
                    if locale.lower().startswith("en")
                    else "不展示未通过身份与几何约束的结果"
                ),
                (
                    "The original photo and identity were fully preserved"
                    if locale.lower().startswith("en")
                    else "原图与本人身份完整保留"
                ),
                (
                    f"Quality judge safe fallback: {last_error[:80]}"
                    if locale.lower().startswith("en")
                    else f"裁判系统已安全回退：{last_error[:80]}"
                ),
            ],
            result_image_base64=base64.b64encode(source[0]).decode("ascii"),
            result_mime_type=source[1],
            quality_verdict=last_verdict,
            candidate_count=candidate_count,
            correction_rounds=correction_rounds,
            semantic_judge_count=sum(
                item.screening_stage == "semantic_judge" for item in verdicts
            ),
            deterministic_reject_count=sum(
                item.screening_stage == "deterministic_precheck" for item in verdicts
            ),
            stage_timings_ms=_stage_timings(stage_seconds, pipeline_started),
            generation_provider=_generation_provider(providers_used),
        )


def _stage_timings(stage_seconds: dict[str, float], started: float) -> dict[str, int]:
    total = perf_counter() - started
    measured = sum(stage_seconds.values())
    return {
        "generation": round(stage_seconds["generation"] * 1000),
        "quality_judge": round(stage_seconds["quality_judge"] * 1000),
        "preprocess_and_routing": round(max(0.0, total - measured) * 1000),
        "pipeline_total": round(total * 1000),
    }


def _generation_provider(providers_used: set[str]) -> str:
    if "qwen" in providers_used:
        return "qwen"
    if "openai" in providers_used:
        return "openai"
    if "gemini" in providers_used:
        return "gemini"
    return "unknown"


async def _generate_live_image(
    *,
    data: bytes,
    mime_type: str,
    prompt: str,
    previous_image: ImageInput | None = None,
    image_size: str = "2K",
    provider_trace: set[str] | None = None,
) -> tuple[bytes, str]:
    if settings.image_provider == "openai":
        result = await _openai_image_edit(
            data=data,
            mime_type=mime_type,
            prompt=prompt,
            previous_image=previous_image,
        )
        if provider_trace is not None:
            provider_trace.add("openai")
        return result
    if settings.image_provider == "qwen":
        result = await _qwen_image_edit(
            data=data,
            mime_type=mime_type,
            prompt=prompt,
            previous_image=previous_image,
        )
        if provider_trace is not None:
            provider_trace.add("qwen")
        return result
    return await _gemini_generate(
        data=data,
        mime_type=mime_type,
        prompt=prompt,
        previous_image=previous_image,
        image_size=image_size,
        provider_trace=provider_trace,
    )


async def _openai_json_response(
    *,
    content: list[dict[str, Any]],
    schema_name: str,
    schema: dict[str, Any],
    model: str | None = None,
) -> dict[str, Any]:
    request_body = {
        "model": model or settings.openai_analysis_model,
        "input": [{"role": "user", "content": content}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
        "max_output_tokens": 5000,
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            "https://api.openai.com/v1/responses",
            headers=headers,
            json=request_body,
        )
    if not response.is_success:
        message = response.json().get("error", {}).get("message", "OpenAI 请求失败")
        raise HTTPException(status_code=502, detail=f"审美分析暂未完成：{message[:160]}")
    output_text = _extract_output_text(response.json())
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="审美分析返回格式异常，请重试。") from exc


async def _openai_quality_judge(
    original: bytes,
    candidates: list[tuple[bytes, str]],
    *,
    target_areas: list[str],
    locked_regions: list[str],
    intensity: str,
    locale: str,
) -> list[QualityVerdict]:
    original_data, original_mime = _optimize_image(
        original,
        "image/jpeg",
        max_dimension=768,
        quality=78,
    )
    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": _quality_judge_prompt(
                target_areas,
                locked_regions,
                intensity,
                locale,
            ),
        },
        {
            "type": "input_text",
            "text": "ORIGINAL",
        },
        {
            "type": "input_image",
            "image_url": _data_url(original_data, original_mime),
            "detail": "high",
        },
    ]
    for index, (data, mime) in enumerate(candidates, start=1):
        optimized, optimized_mime = _optimize_image(data, mime, max_dimension=768, quality=78)
        content.extend([
            {"type": "input_text", "text": f"CANDIDATE_{index}"},
            {
                "type": "input_image",
                "image_url": _data_url(optimized, optimized_mime),
                "detail": "high",
            },
        ])
    payload = await _openai_json_response(
        content=content,
        schema_name="generation_quality_verdicts",
        schema=_quality_verdicts_schema(len(candidates)),
        model=settings.openai_judge_model or settings.openai_analysis_model,
    )
    verdicts = [
        QualityVerdict.model_validate(item)
        for item in payload.get("verdicts", [])
    ]
    if len(verdicts) != len(candidates):
        raise ValueError("裁判结果数量与候选数量不一致")
    return verdicts


async def _openai_revision_judge(
    original: ImageInput,
    previous: ImageInput,
    revision: ImageInput,
    *,
    feedback: str,
    locked_regions: list[str],
    locale: str = "zh-Hans",
) -> RevisionVerdict:
    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": _revision_judge_prompt(
                feedback=feedback,
                locked_regions=locked_regions,
                locale=locale,
            ),
        }
    ]
    for label, image in (
        ("ORIGINAL_IDENTITY_BASELINE", original),
        ("PREVIOUS_PROBLEM_REFERENCE", previous),
        ("NEW_REVISION_TO_JUDGE", revision),
    ):
        optimized, optimized_mime = _optimize_image(
            *image,
            max_dimension=768,
            quality=78,
        )
        content.extend(
            [
                {"type": "input_text", "text": label},
                {
                    "type": "input_image",
                    "image_url": _data_url(optimized, optimized_mime),
                    "detail": "high",
                },
            ]
        )
    payload = await _openai_json_response(
        content=content,
        schema_name="revision_quality_verdict",
        schema=_revision_verdict_schema(),
        model=settings.openai_judge_model or settings.openai_analysis_model,
    )
    verdict = RevisionVerdict.model_validate(payload)
    expected_eligible = bool(
        verdict.feedback_execution_score >= 90
        and verdict.identity_score >= 86
        and verdict.locked_region_score >= 90
        and verdict.original_baseline_score >= 90
        and not verdict.hard_failures
    )
    # Do not trust a model-authored boolean when it disagrees with product gates.
    return verdict.model_copy(update={"eligible": expected_eligible})


def _revision_judge_prompt(
    *,
    feedback: str,
    locked_regions: list[str],
    locale: str,
) -> str:
    contract = compile_revision_feedback(feedback)
    output_language = (
        "Write the summary in concise natural English."
        if locale.lower().startswith("en")
        else "请用简洁的简体中文写 summary。"
    )
    return f"""
You are a strict V2/V3 portrait revision judge. Compare all three images.
The ORIGINAL is the only identity, composition and unmentioned-region baseline.
The PREVIOUS image is only evidence of the problem the user wants corrected.
Judge whether NEW_REVISION executes the compiled feedback without accumulating drift.

Compiled feedback contract: {json.dumps(contract, ensure_ascii=False)}
Locked regions: {json.dumps(locked_regions, ensure_ascii=False)}

Hard failures use only: feedback_not_followed, cumulative_identity_drift,
locked_region_changed, original_baseline_lost, change_overdone.

Use integer scores from 0 to 100. feedbackExecutionScore must be at least 90 only
when the requested strengthen/weaken/restore/lock action is visibly and correctly
executed. originalBaselineScore must be at least 90 only when identity, composition
and all unmentioned regions remain anchored to ORIGINAL rather than drifting from
PREVIOUS. A hard failure can never be offset by another high score.
Set eligible true only when feedbackExecutionScore >= 90, identityScore >= 86,
lockedRegionScore >= 90, originalBaselineScore >= 90 and hardFailures is empty.
{output_language}
""".strip()


def _revision_verdict_schema() -> dict[str, Any]:
    score = {"type": "integer", "minimum": 0, "maximum": 100}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "feedback_execution_score",
            "identity_score",
            "locked_region_score",
            "original_baseline_score",
            "hard_failures",
            "summary",
            "eligible",
        ],
        "properties": {
            "feedback_execution_score": score,
            "identity_score": score,
            "locked_region_score": score,
            "original_baseline_score": score,
            "hard_failures": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "feedback_not_followed",
                        "cumulative_identity_drift",
                        "locked_region_changed",
                        "original_baseline_lost",
                        "change_overdone",
                    ],
                },
            },
            "summary": {"type": "string"},
            "eligible": {"type": "boolean"},
        },
    }


def _quality_judge_prompt(
    target_areas: list[str],
    locked_regions: list[str],
    intensity: str,
    locale: str,
) -> str:
    output_language = (
        "Write summary and retryInstruction in concise natural English."
        if locale.lower().startswith("en")
        else "Write summary and retryInstruction in concise Simplified Chinese."
    )
    return f"""
You are a strict portrait generation quality judge. Image 1 is the immutable original.
The remaining images are candidates. Do not judge beauty. Compare each candidate to the original.

Requested target areas: {json.dumps(target_areas, ensure_ascii=False)}
Locked regions: {json.dumps(locked_regions, ensure_ascii=False)}
Requested intensity: {intensity}

Hard failures use only these codes when applicable:
identity_drift, head_or_hair_cropped, framing_changed, face_or_head_widened,
cheekbone_expanded, cheek_hollowed, locked_region_changed, unreadable_candidate.

Rules:
- Every score is an integer on a 0–100 scale. Never use a 0–5 or 0–10 scale.
- 95–100 means visually indistinguishable compliance; 90–94 means strong compliance with
  only tiny harmless rendering differences; 80–89 means noticeable risk or drift;
  below 80 means clear failure. Scores and written summary must agree.
- identityScore: 90+ only when this is unmistakably the same person; score below 86 for
  any meaningful change to face shape, feature proportions, age impression, expression or gaze.
- framingScore/headBoundaryScore/lockedRegionScore: minor generative pixel differences are
  acceptable; penalize composition, geometry or semantic changes, not harmless compression or texture noise.
- targetChangeScore: 65+ for a restrained but clearly perceptible and coherent requested
  structural change; below 65 when the result is unchanged or relies only on lighting,
  skin, makeup or sharpening. Do not require an exaggerated or identity-changing edit.
- Same person, age impression, ethnicity, expression and gaze must remain.
- Head top, hair crown, hair corners and original four-edge content must remain.
- No horizontal enlargement of head, face, cheekbones, midface or jaw.
- No cheekbone/zygomatic expansion and no new sub-cheek hollow or tired appearance.
- Eyes, nose, lips, brows, hairstyle and all locked regions must not change.
- Every requested target area must visibly contribute to the result.
- For visible/balanced intensity, lighting, smoothing, makeup, sharpening or lip color alone
  cannot pass targetChangeScore.
- A hard failure can never be offset by another high score.
- retryInstruction must precisely correct only the actual failures.
- {output_language}
""".strip()


def _quality_verdicts_schema(candidate_count: int) -> dict[str, Any]:
    score = {"type": "integer", "minimum": 0, "maximum": 100}
    verdict = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "identity_score",
            "framing_score",
            "head_boundary_score",
            "target_change_score",
            "width_safety_score",
            "cheek_safety_score",
            "locked_region_score",
            "hard_failures",
            "summary",
            "eligible",
            "retry_instruction",
        ],
        "properties": {
            "identity_score": score,
            "framing_score": score,
            "head_boundary_score": score,
            "target_change_score": score,
            "width_safety_score": score,
            "cheek_safety_score": score,
            "locked_region_score": score,
            "hard_failures": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "identity_drift",
                        "head_or_hair_cropped",
                        "framing_changed",
                        "face_or_head_widened",
                        "cheekbone_expanded",
                        "cheek_hollowed",
                        "locked_region_changed",
                        "unreadable_candidate",
                    ],
                },
            },
            "summary": {"type": "string"},
            "eligible": {"type": "boolean"},
            "retry_instruction": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["verdicts"],
        "properties": {
            "verdicts": {
                "type": "array",
                "minItems": candidate_count,
                "maxItems": candidate_count,
                "items": verdict,
            }
        },
    }


async def _gemini_generate(
    *,
    data: bytes,
    mime_type: str,
    prompt: str,
    previous_image: ImageInput | None = None,
    image_size: str = "2K",
    provider_trace: set[str] | None = None,
) -> tuple[bytes, str]:
    parts: list[dict[str, Any]] = [
        {"text": prompt},
        {
            "inlineData": {
                "mimeType": mime_type,
                "data": base64.b64encode(data).decode("ascii"),
            }
        },
    ]
    if previous_image is not None:
        previous_data, previous_mime = _optimize_image(
            *previous_image,
            max_dimension=3072,
            quality=96,
        )
        parts.extend(
            [
                {
                    "text": (
                        "上面第一张是必须保留身份和构图的原始照片；"
                        "下面第二张是用户正在评价的上一版结果。"
                    )
                },
                {
                    "inlineData": {
                        "mimeType": previous_mime,
                        "data": base64.b64encode(previous_data).decode("ascii"),
                    }
                },
            ]
        )
    request_body = {
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {
                "aspectRatio": _closest_aspect_ratio(data),
                "imageSize": image_size,
            },
        },
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_image_model}:generateContent"
    )
    async with httpx.AsyncClient(timeout=240) as client:
        response = await client.post(
            url,
            headers={
                "x-goog-api-key": settings.gemini_api_key,
                "Content-Type": "application/json",
            },
            json=request_body,
        )
    if not response.is_success:
        message = response.json().get("error", {}).get("message", "Gemini 请求失败")
        if settings.openai_image_model and _should_fallback_from_gemini(
            response.status_code, message
        ):
            result = await _openai_image_edit(
                data=data,
                mime_type=mime_type,
                prompt=prompt,
                previous_image=previous_image,
            )
            if provider_trace is not None:
                provider_trace.add("openai")
            return result
        raise ValueError(message[:160])
    for candidate in response.json().get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                if provider_trace is not None:
                    provider_trace.add("gemini")
                return (
                    base64.b64decode(inline["data"]),
                    inline.get("mimeType") or inline.get("mime_type") or "image/png",
                )
    raise ValueError("Gemini 没有返回图片")


def _should_fallback_from_gemini(status_code: int, message: str) -> bool:
    normalized = message.lower()
    availability_markers = (
        "billing",
        "credit",
        "quota",
        "rate limit",
        "resource_exhausted",
        "temporarily unavailable",
        "overloaded",
    )
    return status_code == 429 or status_code >= 500 or any(
        marker in normalized for marker in availability_markers
    )


def _openai_image_size(data: bytes) -> str:
    dimensions = _image_dimensions(data)
    if not dimensions:
        return "1024x1024"
    width, height = dimensions
    if width / height < 0.9:
        return "1024x1536"
    if width / height > 1.1:
        return "1536x1024"
    return "1024x1024"


async def _openai_image_edit(
    *,
    data: bytes,
    mime_type: str,
    prompt: str,
    previous_image: ImageInput | None = None,
    edit_mask: ImageInput | None = None,
) -> tuple[bytes, str]:
    prompt = f"""
You are a precision portrait-retouching engine. Execute the allowed structural edit; do not return a near-copy.
Pixel movement or percentage instructions in the allowed-change list are hard targets. The difference must be
clearly visible when the app later compares before and after, while preserving identity. Output exactly one edited
photograph: never create a split view, before/after panel, collage, border, caption or text. Never substitute lighting,
smoothing, makeup, color grading or sharpening for the requested geometry. All locked regions and the original
composition remain immutable.

{prompt}
""".strip()
    if edit_mask is not None:
        source_upload, mask_upload = _prepare_openai_mask(data, edit_mask[0])
        files: list[tuple[str, tuple[str, bytes, str]]] = [
            ("image[]", ("original.png", source_upload, "image/png")),
            ("mask", ("mask.png", mask_upload, "image/png")),
        ]
    else:
        files = [("image[]", ("original.jpg", data, mime_type))]
    if previous_image is not None:
        previous_data, previous_mime = _optimize_image(
            *previous_image,
            max_dimension=2048,
            quality=92,
        )
        files.append(("image[]", ("previous.jpg", previous_data, previous_mime)))
    form = {
        "model": settings.openai_image_model,
        "prompt": prompt,
        "quality": settings.openai_image_quality,
        "size": _openai_image_size(data),
        "output_format": "jpeg",
        "output_compression": "92",
        "n": "1",
    }
    if settings.openai_image_model in {"gpt-image-1", "gpt-image-1.5"}:
        form["input_fidelity"] = "high"
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            "https://api.openai.com/v1/images/edits",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            data=form,
            files=files,
        )
    if not response.is_success:
        message = response.json().get("error", {}).get("message", "OpenAI 图片编辑请求失败")
        raise ValueError(message[:240])
    images = response.json().get("data") or []
    if not images or not images[0].get("b64_json"):
        raise ValueError("OpenAI 图片编辑没有返回图片")
    generated = base64.b64decode(images[0]["b64_json"])
    return _restore_source_aspect(generated, data), "image/jpeg"


def _qwen_image_size(data: bytes) -> str:
    dimensions = _image_dimensions(data)
    if not dimensions:
        return "1024*1024"
    width, height = dimensions
    scale = min(1.0, 2048 / max(width, height))
    width = max(512, round(width * scale / 16) * 16)
    height = max(512, round(height * scale / 16) * 16)
    if width * height > 2048 * 2048:
        scale = (2048 * 2048 / (width * height)) ** 0.5
        width = max(512, round(width * scale / 16) * 16)
        height = max(512, round(height * scale / 16) * 16)
    return f"{width}*{height}"


def _qwen_image_request(
    *,
    data: bytes,
    mime_type: str,
    prompt: str,
    previous_image: ImageInput | None,
) -> dict[str, Any]:
    content: list[dict[str, str]] = [{"image": _data_url(data, mime_type)}]
    if previous_image is not None:
        previous_data, previous_mime = _optimize_image(
            *previous_image,
            max_dimension=2048,
            quality=92,
        )
        content.append({"image": _data_url(previous_data, previous_mime)})
    content.append({"text": prompt})
    return {
        "model": settings.qwen_image_model,
        "input": {"messages": [{"role": "user", "content": content}]},
        "parameters": {
            "n": 1,
            "negative_prompt": (
                "identity drift, enlarged eyes, widened face, expanded cheekbones, "
                "cropped hair, changed background, collage, text, watermark, low quality"
            ),
            "prompt_extend": False,
            "watermark": False,
            "size": _qwen_image_size(data),
        },
    }


async def _qwen_image_edit(
    *,
    data: bytes,
    mime_type: str,
    prompt: str,
    previous_image: ImageInput | None = None,
) -> tuple[bytes, str]:
    payload = _qwen_image_request(
        data=data,
        mime_type=mime_type,
        prompt=prompt,
        previous_image=previous_image,
    )
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            settings.qwen_image_endpoint,
            headers={
                "Authorization": f"Bearer {settings.qwen_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if not response.is_success:
            try:
                message = response.json().get("message", "Qwen 图片编辑请求失败")
            except ValueError:
                message = "Qwen 图片编辑请求失败"
            raise ValueError(str(message)[:240])
        choices = response.json().get("output", {}).get("choices", [])
        image_url = None
        if choices:
            for item in choices[0].get("message", {}).get("content", []):
                if item.get("image"):
                    image_url = item["image"]
                    break
        if not image_url:
            raise ValueError("Qwen 图片编辑没有返回图片")
        parsed = httpx.URL(image_url)
        host = parsed.host.decode() if isinstance(parsed.host, bytes) else parsed.host
        if parsed.scheme != "https" or not host or not host.endswith(".aliyuncs.com"):
            raise ValueError("Qwen 返回了不受信任的图片地址")
        image_response = await client.get(image_url)
        image_response.raise_for_status()
    return _restore_source_aspect(image_response.content, data), "image/jpeg"


def _prepare_openai_mask(source_data: bytes, mask_data: bytes) -> tuple[bytes, bytes]:
    with Image.open(io.BytesIO(source_data)) as source_original:
        source = ImageOps.exif_transpose(source_original).convert("RGBA")
    with Image.open(io.BytesIO(mask_data)) as mask_original:
        normalized_mask = ImageOps.exif_transpose(mask_original)
        if "A" in normalized_mask.getbands():
            mask = normalized_mask.convert("RGBA")
        else:
            alpha = normalized_mask.convert("L")
            mask = Image.new("RGBA", normalized_mask.size, (255, 255, 255, 255))
            mask.putalpha(alpha)
        if mask.size != source.size:
            mask = mask.resize(source.size, Image.Resampling.NEAREST)
    source_output, mask_output = io.BytesIO(), io.BytesIO()
    source.save(source_output, format="PNG", optimize=True)
    mask.save(mask_output, format="PNG", optimize=True)
    return source_output.getvalue(), mask_output.getvalue()


def _restore_source_aspect(result_data: bytes, source_data: bytes) -> bytes:
    """Center-crop fixed-ratio provider output back to the source canvas."""
    with Image.open(io.BytesIO(source_data)) as source:
        source_size = source.size
        source_ratio = source.width / source.height
    with Image.open(io.BytesIO(result_data)) as result_original:
        result = ImageOps.exif_transpose(result_original).convert("RGB")
        result_ratio = result.width / result.height
        if result_ratio > source_ratio:
            target_width = max(1, round(result.height * source_ratio))
            left = (result.width - target_width) // 2
            result = result.crop((left, 0, left + target_width, result.height))
        elif result_ratio < source_ratio:
            target_height = max(1, round(result.width / source_ratio))
            top = (result.height - target_height) // 2
            result = result.crop((0, top, result.width, top + target_height))
        result = result.resize(source_size, Image.Resampling.LANCZOS)
        output = io.BytesIO()
        result.save(output, format="JPEG", quality=94, optimize=True)
        return output.getvalue()


def _language_rule(locale: str) -> str:
    if locale.lower().startswith("en"):
        return "Write every reader-facing field in natural, concise English."
    return "所有面向用户的字段使用自然、具体的简体中文。"


def _profile_prompt(
    reference_count: int,
    calibration_history: list[str] | None = None,
    locale: str = "zh-Hans",
) -> str:
    useful_history = [
        item.strip()
        for item in (calibration_history or [])
        if isinstance(item, str) and item.strip()
    ][-12:]
    history_block = (
        json.dumps(useful_history, ensure_ascii=False, indent=2)
        if useful_history
        else "暂无历史校准。"
    )
    return f"""
你是“小美说”的审美研究员。下面依次提供 {reference_count} 张用户主动选择的审美参考图，
编号从 1 开始。你的任务仅是总结“用户偏好的美”，不是修图方案，也不是要求用户保持原貌。
{_language_rule(locale)}

用户过往对本人修图结果的校准反馈（这是高权重信号；只用于理解方向，不能凌驾于本轮图片证据）：
{history_block}

分析要求：
1. 识别可跨多张样本复现的偏好：整体气质、头脸比例、脸型轮廓、五官表现、肤质、妆发、
   光线与画面氛围。不要把某一张的偶然特征当成结论。
2. 允许总结用户喜欢的明显改变方向，例如更小的头脸比例、更利落的下颌、更舒展的五官；
   不要默认“自然”或“保持原貌”一定是目标。
3. 每条结论必须标明证据图片编号；证据不足时 confidence 必须是 low。
4. anti_targets 是这些样本共同排斥或明显不支持的方向，不得无依据编造。
5. 若历史反馈反复出现同一偏好，应在有本轮图片证据时吸收到结论中；不得照抄互相冲突的反馈。
6. 输出 4–7 条具体、可用于之后修图决策的 insights；不要输出医美、品牌、剂量或诊断。
""".strip()


def _edit_plan_prompt(
    profile: AestheticProfileResponse,
    intensity: str,
    locale: str = "zh-Hans",
) -> str:
    intensity_text = (
        "明显改变：第一眼能看出比例和状态更好，允许有审美依据的头脸比例或轮廓改变，但仍是本人。"
        if intensity == "visible"
        else "自然优化：像状态很好的一天，变化克制。"
    )
    return f"""
你是专业人像修图导演。请同时阅读这张待修照片和用户审美档案，生成用户确认后才会执行的修图方案。
{_language_rule(locale)}

变化强度：{intensity_text}
审美档案：
{profile.model_dump_json(indent=2)}

规则：
1. 输出 3–6 个真正有价值、能在图片编辑模型中执行的 changes。
2. 如果审美证据支持且照片适合，明显改变模式可以提出头脸比例优化、视觉缩头、下颌线或脸型调整；
   不要只给光线和磨皮这种无惊喜方案。
3. 不得自动放大眼睛。只有方案 change 明确包含眼睛且审美档案有直接证据时才允许改眼睛。
4. 禁止颧骨外扩、颧弓变宽、脸部异常膨胀、尖窄模板 V 脸和身份漂移。
5. 本 MVP 永远不允许改变背景、构图、画幅、裁切、发型或发际线；不要为这些区域生成 change。
6. locked_regions 必须列出所有没有被 change 选中的重要区域，至少考虑：
   身份、眼睛、眉毛、鼻子、嘴唇、牙齿、颧骨、发型、服装、配饰、背景、构图。
7. instruction 写成可直接交给图片编辑模型的明确指令；不要输出医美、材料、剂量或诊断。
""".strip()


def _medical_plan_prompt(
    profile: AestheticProfileResponse,
    preferences: dict[str, Any],
    selected_directions: list[str],
    intensity: str,
    locale: str,
) -> str:
    return f"""
你是“小美说”的医美审美决策助手。你要把审美偏好、本人正面/45°照片与用户主动选择的目标对撞，
形成面诊沟通顺序。你不是医生，不做诊断，也不承诺治疗结果。
{_language_rule(locale)}

个人审美档案：
{profile.model_dump_json(indent=2)}

用户决策边界：
{json.dumps(preferences, ensure_ascii=False, indent=2)}

用户主动选择的目标部位：
{json.dumps(selected_directions, ensure_ascii=False)}

目标变化强度：{intensity}

规则：
1. 用户主动确认的每一个目标部位都必须创建 candidate，输入 N 个方向，输出必须保留 N 个方向。
   照片证据不足只能将 priority 调整为 later、optional 或 avoid，并明确“需面诊分层”，不得删除。
2. 每个 candidate 必须解释审美依据与本人照片依据，不能把参考图身份复制到本人。
3. priority 只能是 now、later、optional、avoid。先可逆、后不可逆；支持分阶段验证。
4. method_category 与 material_category 只写类别和决策逻辑，不写具体品牌。
5. discussion_range 允许写“面诊讨论区间”，但不得声称是个人处方；照片不能决定个人剂量、针点或层次。
6. 未选择眼睛时，locked_regions 必须含眼睛；未选择鼻子、嘴唇等同理。
7. preserve 写清本人辨识度、明确不改项和用户底线。
8. 输出必须完整覆盖上述 N 个用户目标方向；可另加 avoid 解释项，并给出 3–6 个真正有用的面诊问题。
""".strip()


def _normalized_area(value: str) -> str:
    return "".join(value.lower().split()).replace("部", "").replace("区域", "")


def _ensure_medical_direction_integrity(
    plan: MedicalPlanResponse,
    selected_directions: list[str],
    *,
    locale: str,
) -> MedicalPlanResponse:
    existing = {_normalized_area(item.area): item for item in plan.candidates}
    output: list[MedicalCandidate] = []
    for index, direction in enumerate(dict.fromkeys(selected_directions)):
        key = _normalized_area(direction)
        candidate = existing.get(key)
        if candidate is None:
            candidate = MedicalCandidate(
                id=f"retained-{index}-{uuid4()}",
                area=direction,
                goal=(
                    f"Keep {direction} in the combined aesthetic target pending in-person assessment."
                    if locale.lower().startswith("en")
                    else f"保留“{direction}”作为整体审美目标，具体路径需面诊分层。"
                ),
                priority="later",
                method_category=(
                    "In-person structural and soft-tissue assessment first"
                    if locale.lower().startswith("en")
                    else "先面诊核对结构与软组织，再决定路径"
                ),
                material_category=(
                    "Category determined only after assessment"
                    if locale.lower().startswith("en")
                    else "材料类别需在面诊后判断"
                ),
                discussion_range=(
                    "Direction retained; no photo-based personal prescription"
                    if locale.lower().startswith("en")
                    else "保留目标方向，不根据照片给出个人处方"
                ),
                rationale=(
                    "The user explicitly confirmed this direction; weak photo evidence changes confidence, not scope."
                    if locale.lower().startswith("en")
                    else "这是用户已确认方向；照片证据强弱只改变置信状态，不改变目标集合。"
                ),
                evidence=(
                    "Limited photo evidence; requires layered in-person assessment."
                    if locale.lower().startswith("en")
                    else "照片证据有限，需面诊分层确认。"
                ),
                consultation_questions=[
                    (
                        f"What anatomical or soft-tissue factors determine the path for {direction}?"
                        if locale.lower().startswith("en")
                        else f"{direction}主要由哪些结构或软组织因素决定？"
                    )
                ],
                enabled=True,
            )
        output.append(candidate)
    avoid_explanations = [
        item
        for item in plan.candidates
        if item.priority == "avoid" and _normalized_area(item.area) not in {
            _normalized_area(direction) for direction in selected_directions
        }
    ]
    plan.candidates = [*output, *avoid_explanations]
    return plan


def _gemini_medical_prompt(
    plan: MedicalPlanResponse,
    candidates: list[MedicalCandidate],
    *,
    intensity: str,
    feedback: str | None,
    has_previous_result: bool,
) -> str:
    allowed = "\n".join(
        f"- {item.area}: {item.goal}. Visual direction only; {item.rationale}"
        for item in candidates
    )
    locked = "、".join(plan.locked_regions)
    revision = ""
    if feedback and feedback.strip():
        contract = compile_revision_feedback(feedback)
        revision = (
            "\nRevision feedback from the user:\n"
            f"{json.dumps(contract, ensure_ascii=False)}\n"
            "Execute only this compiled contract. The original photo remains the identity and locked-region reference."
        )
    elif has_previous_result:
        revision = "\nThis is a revision. Use the original photo as the identity and locked-region source of truth."
    strength = {
        "conservative": "subtle but visible",
        "balanced": "clear, realistic and harmonious",
        "visible": "visibly improved but anatomically coherent",
    }.get(intensity, "clear, realistic and harmonious")
    return f"""
Edit the attached portrait into ONE realistic aesthetic-target preview. This is not a post-treatment prediction.
Change intensity: {strength}.

Allowed target changes only:
{allowed}

Locked regions: {locked}

Pre-generation hard constraints:
- Same person, age impression, ethnicity, skin tone, expression, gaze and identity.
- If eyes are not explicitly allowed above: keep exact eye size, shape, spacing, iris and gaze. Never enlarge eyes.
- Never expand cheekbones or zygomatic arches, never widen the midface, and never create facial swelling.
- Any jaw or chin change must be visible enough to match the selected goal, yet keep anatomical continuity.
- Preserve every unselected facial region. No accidental nose, lips, brows or hair changes.
- Preserve original background, crop, camera, pose, clothing, accessories, lighting direction and aspect ratio.
- Output a single high-resolution photograph with real skin and hair detail. No collage, labels, watermark or text.
- If a requested target conflicts with identity or anatomy, reduce only that target instead of changing another region.
{revision}
""".strip()


def _gemini_edit_prompt(
    changes: list[EditChange],
    locked_regions: list[str],
    *,
    feedback: str | None = None,
    has_previous_result: bool = False,
) -> str:
    allowed = "\n".join(
        f"- {change.area}｜{change.title}：{change.instruction}"
        for change in changes
    )
    locked = "、".join(locked_regions)
    revision = ""
    if feedback and feedback.strip():
        contract = compile_revision_feedback(feedback)
        revision = f"""

用户对上一版反馈的结构化执行合同：
{json.dumps(contract, ensure_ascii=False, indent=2)}

这是一次迭代修图。请以原始照片为身份、构图和未选区域的唯一基准，结合上一版观察问题；
只修正用户指出的不满意之处，不要在上一版基础上继续累积无关变化。
""".rstrip()
    elif has_previous_result:
        revision = (
            "\n这是一次迭代修图。原始照片是身份和未选区域的唯一基准，"
            "上一版仅用于识别需要修正的问题。"
        )
    return f"""
编辑所附的同一张人物照片。必须输出一张完成编辑后的照片，不要输出拼图、文字、水印或说明。

只允许执行以下确认过的改变：
{allowed}

强制保持不变：{locked}

最高优先级约束：
- 必须保持同一个人的身份、年龄感、肤色与可识别特征。
- 未列入“允许改变”的部位像素和几何关系尽量保持原图。
- 如果眼睛未被允许改变：严禁放大眼睛、改变眼距、眼型、虹膜或视线。
- 无论方案如何，严禁颧骨或颧弓外扩、面中变宽、脸部异常膨胀。
- 保持原背景、构图、画幅、服装、配饰、发型与光线方向，除非它们明确出现在允许清单。
- 输出图片必须保持与输入图片完全相同的宽高比和取景范围；禁止缩放、裁切、扩图或改变镜头视角。
- 输出必须使用请求的高清分辨率，保留皮肤、毛发、衣物、配饰和背景的真实细节；禁止模糊、降采样或低清重绘。
- 改变要清晰可见但真实连贯，不生成塑料皮肤、模板脸、畸变边缘或额外物体。
{revision}
""".strip()


def _profile_schema() -> dict[str, Any]:
    insight = {
        "type": "object",
        "additionalProperties": False,
        "required": ["region", "title", "summary", "confidence", "evidence"],
        "properties": {
            "region": {"type": "string"},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "evidence": {
                "type": "object",
                "additionalProperties": False,
                "required": ["reference_indexes", "note"],
                "properties": {
                    "reference_indexes": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "note": {"type": "string"},
                },
            },
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["primary_direction", "secondary_direction", "anti_targets", "insights"],
        "properties": {
            "primary_direction": {"type": "string"},
            "secondary_direction": {"type": "string"},
            "anti_targets": {"type": "array", "items": {"type": "string"}},
            "insights": {"type": "array", "items": insight},
        },
    }


def _edit_plan_schema() -> dict[str, Any]:
    change = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "area", "title", "rationale", "instruction", "enabled"],
        "properties": {
            "id": {"type": "string"},
            "area": {"type": "string"},
            "title": {"type": "string"},
            "rationale": {"type": "string"},
            "instruction": {"type": "string"},
            "enabled": {"type": "boolean"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["headline", "summary", "changes", "locked_regions"],
        "properties": {
            "headline": {"type": "string"},
            "summary": {"type": "string"},
            "changes": {"type": "array", "items": change},
            "locked_regions": {"type": "array", "items": {"type": "string"}},
        },
    }


def _medical_plan_schema() -> dict[str, Any]:
    candidate = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "area",
            "goal",
            "priority",
            "method_category",
            "material_category",
            "discussion_range",
            "rationale",
            "evidence",
            "consultation_questions",
            "enabled",
        ],
        "properties": {
            "id": {"type": "string"},
            "area": {"type": "string"},
            "goal": {"type": "string"},
            "priority": {
                "type": "string",
                "enum": ["now", "later", "optional", "avoid"],
            },
            "method_category": {"type": "string"},
            "material_category": {"type": "string"},
            "discussion_range": {"type": "string"},
            "rationale": {"type": "string"},
            "evidence": {"type": "string"},
            "consultation_questions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "enabled": {"type": "boolean"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "headline",
            "summary",
            "confirmed_direction",
            "preserve",
            "candidates",
            "locked_regions",
            "consultation_questions",
            "safety_disclosure",
        ],
        "properties": {
            "headline": {"type": "string"},
            "summary": {"type": "string"},
            "confirmed_direction": {"type": "string"},
            "preserve": {"type": "array", "items": {"type": "string"}},
            "candidates": {"type": "array", "items": candidate},
            "locked_regions": {"type": "array", "items": {"type": "string"}},
            "consultation_questions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "safety_disclosure": {"type": "string"},
        },
    }


def _extract_output_text(payload: dict[str, Any]) -> str:
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return content["text"]
    raise HTTPException(status_code=502, detail="OpenAI 未返回可读取的分析结果。")


def _data_url(data: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _optimize_image(
    data: bytes,
    mime_type: str,
    *,
    max_dimension: int,
    quality: int = 86,
) -> ImageInput:
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True)
        return output.getvalue(), "image/jpeg"
    except Exception:
        return data, mime_type


def _closest_aspect_ratio(data: bytes) -> str:
    supported = {
        "1:1": 1.0,
        "3:4": 3 / 4,
        "4:3": 4 / 3,
        "9:16": 9 / 16,
        "16:9": 16 / 9,
    }
    try:
        with Image.open(io.BytesIO(data)) as image:
            ratio = image.width / image.height
        return min(supported, key=lambda name: abs(supported[name] - ratio))
    except Exception:
        return "1:1"


def _gemini_output_size(data: bytes) -> str:
    dimensions = _image_dimensions(data)
    if dimensions and max(dimensions) >= 1800:
        return "4K"
    return "2K"


def _image_dimensions(data: bytes) -> tuple[int, int] | None:
    try:
        with Image.open(io.BytesIO(data)) as image:
            return image.size
    except Exception:
        return None


def _validate_generated_image(source: bytes, result: bytes) -> None:
    try:
        with Image.open(io.BytesIO(source)) as source_image:
            source_ratio = source_image.width / source_image.height
        with Image.open(io.BytesIO(result)) as result_image:
            result_ratio = result_image.width / result_image.height
            if min(result_image.size) < 512:
                raise ValueError("生成图片分辨率过低")
        if abs(source_ratio - result_ratio) / source_ratio > 0.08:
            raise ValueError("生成图片画幅与原图不一致")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("生成图片无法读取") from exc


def get_analysis_provider() -> AnalysisProvider:
    if settings.model_mode == "live":
        return OpenAIAnalysisProvider()
    return MockAnalysisProvider()


def get_image_provider() -> ImageProvider:
    if settings.model_mode == "live":
        return GeminiImageProvider()
    return MockImageProvider()
