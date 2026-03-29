from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .services.nyc_open_data import find_nearest_aps
from .services.vision import analyze_image_bytes

print("GOOGLE_APPLICATION_CREDENTIALS =", os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))


class LocationRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


app = FastAPI(title="NYSee API", version="0.1.0")

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5500")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        frontend_origin,
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze-image")
async def analyze_image(image: UploadFile = File(...)) -> dict:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")

    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    try:
        result = analyze_image_bytes(content)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Vision API request failed: {exc}") from exc

    return result


@app.post("/api/find-nearest-aps")
async def nearest_aps(payload: LocationRequest) -> dict:
    try:
        result = await find_nearest_aps(payload.latitude, payload.longitude)
    except Exception as exc:
        print("APS ERROR:", repr(exc))
        raise HTTPException(status_code=502, detail=f"NYC Open Data request failed: {exc}") from exc

    return result