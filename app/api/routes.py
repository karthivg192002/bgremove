import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from app.core.config import UPLOAD_DIR, OUTPUT_DIR
from app.services.bg_remove_service import BackgroundRemoveService

router = APIRouter()

@router.post("/remove-background")
async def remove_background(file: UploadFile = File(...)):

    ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/webp", "image/png"}
    ALLOWED_EXTENSIONS = {".jpeg", ".jpg", ".webp", ".png"}

    file_ext = os.path.splitext(file.filename)[1].lower()

    if file.content_type not in ALLOWED_TYPES or file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only JPEG, JPG, WEBP, and PNG images are allowed")

    filename = f"{uuid.uuid4().hex}{file_ext}"
    upload_path = os.path.join(UPLOAD_DIR, filename)

    with open(upload_path, "wb") as f:
        f.write(await file.read())

    output_path = BackgroundRemoveService.remove_background_and_add_watermark(upload_path)

    return FileResponse(output_path, media_type="image/png",filename="bg_removed.png")