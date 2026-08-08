from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from typing import Awaitable, Callable

from PIL import Image, ImageChops, ImageStat

from .config import get_settings
from .models import QualityVerdict

settings = get_settings()

# Centralized release thresholds. Identity/locks/head boundary are deliberately
# stricter than target strength because a subtle safe result can be retried,
# while an identity or crop failure must never be shown.
HARD_FAILURE_CODES = {
    "identity_drift",
    "head_or_hair_cropped",
    "framing_changed",
    "face_or_head_widened",
    "cheekbone_expanded",
    "cheek_hollowed",
    "locked_region_changed",
}


@dataclass(frozen=True)
class QualityThresholds:
    identity: int = settings.judge_identity_min
    framing: int = settings.judge_framing_min
    head_boundary: int = settings.judge_head_boundary_min
    target_natural: int = settings.judge_target_natural_min
    target_visible: int = settings.judge_target_visible_min
    width_safety: int = settings.judge_width_safety_min
    cheek_safety: int = settings.judge_cheek_safety_min
    locked_region: int = settings.judge_locked_region_min


THRESHOLDS = QualityThresholds()


@dataclass
class Candidate:
    data: bytes
    mime_type: str
    verdict: QualityVerdict | None = None


def _normalized_rgb(data: bytes, size: tuple[int, int] = (256, 256)) -> Image.Image:
    with Image.open(io.BytesIO(data)) as image:
        return image.convert("RGB").resize(size)


def _strip_difference(source: Image.Image, result: Image.Image) -> float:
    width, height = source.size
    strip_x, strip_y = max(8, width // 14), max(8, height // 14)
    boxes = [
        (0, 0, width, strip_y),
        (0, height - strip_y, width, height),
        (0, 0, strip_x, height),
        (width - strip_x, 0, width, height),
        (0, 0, width // 4, height // 4),
        (width - width // 4, 0, width, height // 4),
        (0, height - height // 4, width // 4, height),
        (width - width // 4, height - height // 4, width, height),
    ]
    values = []
    for box in boxes:
        diff = ImageChops.difference(source.crop(box), result.crop(box))
        values.append(sum(ImageStat.Stat(diff).mean) / (3 * 255))
    # A crop can damage only one edge (most often the crown/top edge), so the
    # worst edge is the safety signal. Averaging four edges hid that incident.
    return max(values)


def deterministic_scores(source_data: bytes, result_data: bytes) -> dict[str, int | list[str]]:
    failures: list[str] = []
    try:
        with Image.open(io.BytesIO(source_data)) as source_original:
            source_size = source_original.size
        with Image.open(io.BytesIO(result_data)) as result_original:
            result_size = result_original.size
        source_ratio = source_size[0] / source_size[1]
        result_ratio = result_size[0] / result_size[1]
        ratio_delta = abs(source_ratio - result_ratio) / source_ratio
        # Gemini exposes a finite aspect-ratio set. A <= 3.5% ratio delta can
        # therefore be model quantization rather than reframing, and remains
        # acceptable only if the semantic judge also confirms four-edge
        # content/person placement are stable. Larger deltas degrade quickly.
        framing = max(0, round(100 - ratio_delta * 300))
        if ratio_delta > 0.08:
            failures.append("framing_changed")
        if min(result_size) < 512:
            failures.append("resolution_too_low")
            framing = min(framing, 40)
        source = _normalized_rgb(source_data)
        result = _normalized_rgb(result_data)
        border_delta = _strip_difference(source, result)
        head_boundary = max(0, round(100 - border_delta * 210))
        if border_delta > 0.24:
            failures.append("head_or_hair_cropped")
        return {
            "framing_score": framing,
            "head_boundary_score": head_boundary,
            "hard_failures": failures,
        }
    except Exception:
        return {
            "framing_score": 0,
            "head_boundary_score": 0,
            "hard_failures": ["unreadable_candidate"],
        }


def finalize_verdict(
    semantic: QualityVerdict,
    deterministic: dict[str, int | list[str]],
    *,
    intensity: str,
    locale: str = "zh-Hans",
) -> QualityVerdict:
    target_min = (
        THRESHOLDS.target_visible
        if intensity in {"visible", "balanced"}
        else THRESHOLDS.target_natural
    )
    failures = list(dict.fromkeys([
        *semantic.hard_failures,
        *list(deterministic["hard_failures"]),
    ]))
    framing = min(semantic.framing_score, int(deterministic["framing_score"]))
    head = min(semantic.head_boundary_score, int(deterministic["head_boundary_score"]))
    checks = {
        "identity_below_threshold": semantic.identity_score >= THRESHOLDS.identity,
        "framing_below_threshold": framing >= THRESHOLDS.framing,
        "head_boundary_below_threshold": head >= THRESHOLDS.head_boundary,
        "target_change_below_threshold": semantic.target_change_score >= target_min,
        "width_safety_below_threshold": semantic.width_safety_score >= THRESHOLDS.width_safety,
        "cheek_safety_below_threshold": semantic.cheek_safety_score >= THRESHOLDS.cheek_safety,
        "locked_region_below_threshold": semantic.locked_region_score >= THRESHOLDS.locked_region,
    }
    failures.extend(code for code, passed in checks.items() if not passed)
    failures = list(dict.fromkeys(failures))
    retry = retry_instruction(failures, locale=locale)
    return semantic.model_copy(update={
        "framing_score": framing,
        "head_boundary_score": head,
        "hard_failures": failures,
        "eligible": not failures,
        "retry_instruction": retry,
    })


def retry_instruction(failures: list[str], *, locale: str = "zh-Hans") -> str:
    chinese = {
        "head_or_hair_cropped": "锁定原图画幅、头顶、发冠和头发四角外接边界，完整恢复原图四边内容。",
        "head_boundary_below_threshold": "完整保留原图头顶、发冠、发际线与头发边角，不得裁切或移位。",
        "framing_changed": "恢复原图画幅、镜头位置、人物位置、背景四边与取景范围。",
        "framing_below_threshold": "严格匹配原图构图、宽高比、人物大小和四边内容。",
        "face_or_head_widened": "锁定双颧最宽点、面宽、头宽与下颌宽度，禁止横向放大。",
        "width_safety_below_threshold": "收回任何面部、双颧、面中、下颌和头部横向扩张。",
        "identity_drift": "降低结构变化，只保留用户已确认的主要方向，恢复本人身份特征。",
        "identity_below_threshold": "以原图为唯一身份基准，恢复本人五官比例、年龄感、表情与视线。",
        "target_change_below_threshold": "只加强用户已经选择的目标部位；不得新增或顺带修改其他部位。",
        "locked_region_changed": "恢复所有未选部位；尤其锁定原图眼型、眼距、虹膜、视线、鼻口和眉形。",
        "locked_region_below_threshold": "未选部位必须逐像义恢复到原图，不得用妆感或锐化掩盖变化。",
        "cheekbone_expanded": "恢复原图颧骨和颧弓宽度，禁止外扩、肿胀或面中变宽。",
        "cheek_hollowed": "恢复原图颧下与面颊饱满度，禁止凹陷、阴影加深和疲惫感。",
        "cheek_safety_below_threshold": "恢复原图双颊、颧下和颧骨体积关系。",
    }
    english = {
        "head_or_hair_cropped": "Lock the original frame, head top, crown and all hair corners; restore all four original edges.",
        "head_boundary_below_threshold": "Fully preserve the original head top, crown, hairline and hair corners without cropping or shifting.",
        "framing_changed": "Restore the original framing, camera position, subject placement, background edges and field of view.",
        "framing_below_threshold": "Strictly match the original composition, aspect ratio, subject size and four-edge content.",
        "face_or_head_widened": "Lock the widest cheek points, face width, head width and jaw width; do not expand horizontally.",
        "width_safety_below_threshold": "Remove any horizontal expansion of the face, cheeks, midface, jaw or head.",
        "identity_drift": "Reduce structural change, keep only confirmed targets and restore the person's identity.",
        "identity_below_threshold": "Use the original as the sole identity baseline; restore facial proportions, age impression, expression and gaze.",
        "target_change_below_threshold": "Strengthen only the user's confirmed target areas; do not add or alter any other area.",
        "locked_region_changed": "Restore every unselected area, especially the original eye shape, spacing, irises, gaze, nose, mouth and brows.",
        "locked_region_below_threshold": "Restore unselected regions to the original; do not hide changes with makeup or sharpening.",
        "cheekbone_expanded": "Restore original cheekbone and zygomatic width; remove expansion, swelling and midface widening.",
        "cheek_hollowed": "Restore original cheek and sub-cheek fullness; remove new hollows, deeper shadows and tiredness.",
        "cheek_safety_below_threshold": "Restore the original volume relationship among cheeks, sub-cheek area and cheekbones.",
    }
    instructions = english if locale.lower().startswith("en") else chinese
    selected = [instructions[code] for code in failures if code in instructions]
    fallback = (
        "Reduce the change and strictly restore original identity, framing and unselected regions."
        if locale.lower().startswith("en")
        else "降低变化幅度并严格恢复原图身份、画幅和未选区域。"
    )
    return "\n".join(dict.fromkeys(selected)) or fallback


def rank(candidate: Candidate) -> float:
    assert candidate.verdict is not None
    verdict = candidate.verdict
    return (
        verdict.identity_score * 0.24
        + verdict.framing_score * 0.14
        + verdict.head_boundary_score * 0.14
        + verdict.target_change_score * 0.16
        + verdict.width_safety_score * 0.11
        + verdict.cheek_safety_score * 0.10
        + verdict.locked_region_score * 0.11
    )


async def run_generation_pipeline(
    *,
    source: tuple[bytes, str],
    intensity: str,
    initial_count: int,
    generate: Callable[[str | None], Awaitable[tuple[bytes, str]]],
    judge: Callable[[bytes, list[tuple[bytes, str]]], Awaitable[list[QualityVerdict]]],
    locale: str = "zh-Hans",
) -> tuple[Candidate | None, int, int, list[QualityVerdict]]:
    generated = await asyncio.gather(
        *(generate(None) for _ in range(initial_count)),
        return_exceptions=True,
    )
    candidates = [
        Candidate(data=item[0], mime_type=item[1])
        for item in generated
        if not isinstance(item, BaseException)
    ]
    if not candidates:
        return None, 0, 0, []
    correction_rounds = 0
    all_verdicts: list[QualityVerdict] = []
    while True:
        raw = await judge(source[0], [(item.data, item.mime_type) for item in candidates])
        for item, semantic in zip(candidates, raw, strict=True):
            item.verdict = finalize_verdict(
                semantic,
                deterministic_scores(source[0], item.data),
                intensity=intensity,
                locale=locale,
            )
        all_verdicts.extend(item.verdict for item in candidates if item.verdict)
        eligible = [item for item in candidates if item.verdict and item.verdict.eligible]
        if eligible:
            return max(eligible, key=rank), len(all_verdicts), correction_rounds, all_verdicts
        if correction_rounds >= settings.judge_max_correction_rounds:
            return None, len(all_verdicts), correction_rounds, all_verdicts
        correction_rounds += 1
        retry = "\n".join(
            dict.fromkeys(item.verdict.retry_instruction for item in candidates if item.verdict)
        )
        try:
            data, mime = await generate(retry)
        except Exception:
            if correction_rounds >= settings.judge_max_correction_rounds:
                return None, len(all_verdicts), correction_rounds, all_verdicts
            continue
        candidates = [Candidate(data=data, mime_type=mime)]
