import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from app.core.config import UPLOAD_DIR, OUTPUT_DIR
from app.services.bg_remove_service import BackgroundRemoveService

router = APIRouter()

@router.post("/remove-background")
async def remove_background(file: UploadFile = File(...)):

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    file_ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{file_ext}"
    upload_path = os.path.join(UPLOAD_DIR, filename)

    with open(upload_path, "wb") as f:
        f.write(await file.read())

    output_path = BackgroundRemoveService.remove_background_and_add_watermark(upload_path)

    return FileResponse(output_path, media_type="image/png",filename="bg_removed.png")