import os
import uuid
import shutil
import asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse

from app.core.config import UPLOAD_DIR, OUTPUT_DIR
from app.services.bg_remove_service import BackgroundRemoveService

router = APIRouter()

@router.post("/remove-background")
async def remove_background(
    file: UploadFile = File(...),
    process_image: bool = Form(True),
):
    ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/webp", "image/png"}
    ALLOWED_EXTENSIONS = {".jpeg", ".jpg", ".webp", ".png"}

    file_ext = os.path.splitext(file.filename)[1].lower()

    if file.content_type not in ALLOWED_TYPES or file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only JPEG, JPG, WEBP, and PNG images are allowed")

    filename = f"{uuid.uuid4().hex}{file_ext}"
    upload_path = os.path.join(UPLOAD_DIR, filename)

    with open(upload_path, "wb") as f:
        f.write(await file.read())

    if process_image:
        output_path = await asyncio.to_thread(
            BackgroundRemoveService.remove_background_and_add_watermark, upload_path
        )
        output_filename = os.path.basename(output_path)
    else:
        output_filename = f"{uuid.uuid4().hex}{file_ext}"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        shutil.copy2(upload_path, output_path)

    if not os.path.exists(output_path):
        raise HTTPException(status_code=500, detail="Output file was not created")

    file_ext_out = os.path.splitext(output_filename)[1].lower()
    media_type_map = {
        ".webp": "image/webp",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    media_type = media_type_map.get(file_ext_out, "application/octet-stream")

    return FileResponse(
        output_path,
        media_type=media_type,
        filename=output_filename,
        headers={"Content-Disposition": f"attachment; filename={output_filename}"},
    )


@router.get("/download/{filename}")
async def download_image(filename: str):
    output_path = os.path.join(OUTPUT_DIR, filename)

    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="File not found")

    file_ext = os.path.splitext(filename)[1].lower()
    media_type_map = {
        ".webp": "image/webp",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    media_type = media_type_map.get(file_ext, "application/octet-stream")

    return FileResponse(
        output_path,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
