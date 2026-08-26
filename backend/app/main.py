import json
import re
from urllib.parse import urlparse

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .models import (
    AestheticProfileResponse,
    BoardPreviewItem,
    BoardPreviewRequest,
    BoardPreviewResponse,
    EditPlanResponse,
    GenerationResponse,
    MedicalPlanResponse,
)
from .providers import get_analysis_provider, get_image_provider
from .security import require_installation_id
from .telemetry import record_generation, started_at
from .uploads import read_image

settings = get_settings()

if settings.model_mode == "live":
    required = [
        ("OPENAI_API_KEY", settings.openai_api_key),
        ("OPENAI_ANALYSIS_MODEL", settings.openai_analysis_model),
    ]
    if settings.image_provider == "gemini":
        required.extend([
            ("GEMINI_API_KEY", settings.gemini_api_key),
            ("GEMINI_IMAGE_MODEL", settings.gemini_image_model),
        ])
    elif settings.image_provider == "openai":
        required.append(("OPENAI_IMAGE_MODEL", settings.openai_image_model))
    else:
        required.extend([
            ("QWEN_API_KEY", settings.qwen_api_key),
            ("QWEN_IMAGE_ENDPOINT", settings.qwen_image_endpoint),
            ("QWEN_IMAGE_MODEL", settings.qwen_image_model),
        ])
    missing = [
        name
        for name, value in required
        if not value
    ]
    if missing:
        raise RuntimeError(f"live model mode requires: {', '.join(missing)}")

app = FastAPI(
    title="小美说 API",
    version="0.1.0",
    description="无登录、无用户数据库的 iOS MVP 模型网关。",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",")],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Installation-ID", "X-App-Token", "Accept-Language"],
)


def preferred_locale(accept_language: str | None = Header(None)) -> str:
    return "en" if (accept_language or "").lower().startswith("en") else "zh-Hans"


@app.get("/api/v1/status")
async def service_status() -> dict:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "model_mode": settings.model_mode,
        "stores_user_data": False,
    }


@app.post("/api/v1/boards/preview", response_model=BoardPreviewResponse)
async def preview_board(
    payload: BoardPreviewRequest,
    _: str = Depends(require_installation_id),
) -> BoardPreviewResponse:
    parsed = urlparse(str(payload.url))
    host = (parsed.hostname or "").lower()
    if host not in {"xiaohongshu.com", "www.xiaohongshu.com"} or not parsed.path.startswith("/board/"):
        raise HTTPException(status_code=400, detail="only public Xiaohongshu board links are supported")
    try:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1"
                )
            },
        ) as client:
            response = await client.get(str(payload.url))
        response.raise_for_status()
        match = re.search(
            r"window\.__SETUP_SERVER_STATE__=(.*?)</script>",
            response.text,
            re.DOTALL,
        )
        if not match:
            raise ValueError("public board data not present")
        state = json.loads(match.group(1))
        board = state.get("board") or {}
        board_info = board.get("boardInfo") or {}
        items: list[BoardPreviewItem] = []
        for note in board.get("notes") or []:
            images = note.get("imagesList") or []
            if not images:
                continue
            image = images[0]
            thumbnail = image.get("urlSizeLarge") or image.get("url") or image.get("original")
            if isinstance(thumbnail, str) and thumbnail.startswith("http://"):
                thumbnail = "https://" + thumbnail.removeprefix("http://")
            items.append(
                BoardPreviewItem(
                    id=str(note.get("id") or f"note-{len(items) + 1}"),
                    title=str(note.get("title") or f"收藏样本 {len(items) + 1}"),
                    thumbnail_url=thumbnail,
                )
            )
        if not items:
            raise ValueError("no public images")
        return BoardPreviewResponse(
            title=str(board_info.get("name") or "公开收藏夹"),
            source_url=str(payload.url),
            status="ready",
            message=f"已读取 {len(items)} 张公开收藏封面；请选择后保存到本机审美库。",
            items=items[:15],
        )
    except (httpx.HTTPError, json.JSONDecodeError, ValueError):
        return BoardPreviewResponse(
            title="公开收藏夹",
            source_url=str(payload.url),
            status="limited",
            message="链接有效，但小红书本次没有返回公开图片。你仍可直接从相册添加参考图。",
            items=[],
        )


@app.post("/api/v1/aesthetic/profile", response_model=AestheticProfileResponse)
async def create_aesthetic_profile(
    references: list[UploadFile] = File(...),
    calibration_json: str = Form("[]"),
    locale: str = Depends(preferred_locale),
    _: str = Depends(require_installation_id),
) -> AestheticProfileResponse:
    if not 3 <= len(references) <= 15:
        raise HTTPException(status_code=400, detail="upload 3 to 15 reference images")
    images: list[tuple[bytes, str]] = []
    for reference in references:
        images.append(
            (
                await read_image(reference, settings.max_upload_bytes),
                reference.content_type or "image/jpeg",
            )
        )
    try:
        calibration_history = json.loads(calibration_json)
        if not isinstance(calibration_history, list) or not all(
            isinstance(item, str) for item in calibration_history
        ):
            raise ValueError
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid calibration history") from exc
    return await get_analysis_provider().create_profile(
        images,
        calibration_history=calibration_history[-12:],
        locale=locale,
    )


@app.post("/api/v1/edits/plan", response_model=EditPlanResponse)
async def create_edit_plan(
    source: UploadFile = File(...),
    profile_json: str = Form(...),
    intensity: str = Form("natural"),
    locale: str = Depends(preferred_locale),
    _: str = Depends(require_installation_id),
) -> EditPlanResponse:
    source_image = await read_image(source, settings.max_upload_bytes)
    if intensity not in {"natural", "visible"}:
        raise HTTPException(status_code=400, detail="invalid intensity")
    try:
        profile = AestheticProfileResponse.model_validate(json.loads(profile_json))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid profile") from exc
    return await get_analysis_provider().create_edit_plan(
        profile,
        intensity,
        (source_image, source.content_type or "image/jpeg"),
        locale=locale,
    )


@app.post("/api/v1/edits/generate", response_model=GenerationResponse)
async def generate_edit(
    source: UploadFile = File(...),
    plan_json: str = Form(...),
    previous_result: UploadFile | None = File(None),
    feedback: str | None = Form(None),
    locale: str = Depends(preferred_locale),
    installation_id: str = Depends(require_installation_id),
) -> GenerationResponse:
    started = started_at()
    source_image = await read_image(source, settings.max_upload_bytes)
    previous_image = None
    if previous_result is not None:
        previous_image = (
            await read_image(previous_result, settings.max_upload_bytes),
            previous_result.content_type or "image/jpeg",
        )
    try:
        plan = EditPlanResponse.model_validate(json.loads(plan_json))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid edit plan") from exc
    response = await get_image_provider().generate(
        (source_image, source.content_type or "image/jpeg"),
        plan,
        previous_image=previous_image,
        feedback=feedback,
        locale=locale,
    )
    record_generation(
        installation_id=installation_id,
        workflow="edit",
        prompt_version=plan.prompt_version,
        response=response,
        started=started,
    )
    return response


@app.post("/api/v1/medical/plan", response_model=MedicalPlanResponse)
async def create_medical_plan(
    front: UploadFile = File(...),
    side: UploadFile | None = File(None),
    profile_json: str = Form(...),
    preferences_json: str = Form("{}"),
    selected_directions_json: str = Form("[]"),
    intensity: str = Form("balanced"),
    locale: str = Depends(preferred_locale),
    _: str = Depends(require_installation_id),
) -> MedicalPlanResponse:
    if intensity not in {"conservative", "balanced", "visible"}:
        raise HTTPException(status_code=400, detail="invalid medical intensity")
    try:
        profile = AestheticProfileResponse.model_validate(json.loads(profile_json))
        preferences = json.loads(preferences_json)
        selected_directions = json.loads(selected_directions_json)
        if not isinstance(preferences, dict) or not isinstance(selected_directions, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid medical plan input") from exc
    front_image = (
        await read_image(front, settings.max_upload_bytes),
        front.content_type or "image/jpeg",
    )
    side_image = None
    if side is not None:
        side_image = (
            await read_image(side, settings.max_upload_bytes),
            side.content_type or "image/jpeg",
        )
    return await get_analysis_provider().create_medical_plan(
        profile,
        preferences,
        [str(value) for value in selected_directions],
        front_image,
        side_image,
        intensity,
        locale=locale,
    )


@app.post("/api/v1/medical/generate", response_model=GenerationResponse)
async def generate_medical_effect(
    source: UploadFile = File(...),
    plan_json: str = Form(...),
    intensity: str = Form("balanced"),
    previous_result: UploadFile | None = File(None),
    feedback: str | None = Form(None),
    locale: str = Depends(preferred_locale),
    installation_id: str = Depends(require_installation_id),
) -> GenerationResponse:
    started = started_at()
    if intensity not in {"conservative", "balanced", "visible"}:
        raise HTTPException(status_code=400, detail="invalid medical intensity")
    try:
        plan = MedicalPlanResponse.model_validate(json.loads(plan_json))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid medical plan") from exc
    source_image = (
        await read_image(source, settings.max_upload_bytes),
        source.content_type or "image/jpeg",
    )
    previous_image = None
    if previous_result is not None:
        previous_image = (
            await read_image(previous_result, settings.max_upload_bytes),
            previous_result.content_type or "image/jpeg",
        )
    response = await get_image_provider().generate_medical(
        source_image,
        plan,
        intensity,
        previous_image=previous_image,
        feedback=feedback,
        locale=locale,
    )
    record_generation(
        installation_id=installation_id,
        workflow="medical",
        prompt_version=plan.prompt_version,
        response=response,
        started=started,
    )
    return response
