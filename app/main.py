import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.routes import router
from app.core.config import OUTPUT_DIR, BASE_DIR

STATIC_DIR = os.path.join(BASE_DIR, "app", "static")

app = FastAPI(title="Common Service API", version="1.0.0")

app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
app.include_router(router, prefix="/api")

@app.get("/")
async def ui():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))