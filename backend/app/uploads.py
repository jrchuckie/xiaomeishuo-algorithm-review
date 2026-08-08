from fastapi import HTTPException, UploadFile

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/heic", "image/heif", "image/webp"}


async def read_image(upload: UploadFile, max_bytes: int) -> bytes:
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="unsupported image type")
    content = await upload.read(max_bytes + 1)
    if not content:
        raise HTTPException(status_code=400, detail="empty image")
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="image is too large")
    return content

