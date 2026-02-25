import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os
import base64

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

# @router.get("/files")
# def list_all_files():

#     uploads = []
#     outputs = []

#     # -------------------------
#     # uploads -> only filenames
#     # -------------------------
#     if os.path.exists(UPLOAD_DIR):
#         for name in os.listdir(UPLOAD_DIR):
#             path = os.path.join(UPLOAD_DIR, name)
#             if os.path.isfile(path):
#                 uploads.append(name)

#     if os.path.exists(OUTPUT_DIR):
#         for name in os.listdir(OUTPUT_DIR):
#             path = os.path.join(OUTPUT_DIR, name)
#             if os.path.isfile(path):

#                 with open(path, "rb") as f:
#                     encoded = base64.b64encode(f.read()).decode("utf-8")

#                 outputs.append({
#                     "filename": name,
#                     "content_type": "image/png",
#                     "data": encoded
#                 })

#     return {
#         "uploads": uploads,
#         "outputs": outputs
#     }

# @router.get("/file/{filename}")
# def get_file(filename: str):

#     upload_path = os.path.join(UPLOAD_DIR, filename)
#     output_path = os.path.join(OUTPUT_DIR, filename)

#     if os.path.exists(upload_path) and os.path.isfile(upload_path):
#         return FileResponse(upload_path)

#     if os.path.exists(output_path) and os.path.isfile(output_path):
#         return FileResponse(output_path)

#     raise HTTPException(status_code=404, detail="File not found")