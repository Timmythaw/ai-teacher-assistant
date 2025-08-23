# core/config.py  (keep your .env loading at the top)
import os
from pathlib import Path

AI_ML_API_KEY = os.getenv("AI_ML_API_KEY")
AI_ML_BASE_URL = "https://api.aimlapi.com/v1"

if not AI_ML_API_KEY:
    raise ValueError("❌ Missing AI_ML_API_KEY. Please add it to your .env file")

class Config:
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "20")) * 1024 * 1024
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads")).resolve()
    ALLOWED_EXTENSIONS = {".pdf"}

    # Optional: surface these for access via current_app.config
    AI_ML_API_KEY = AI_ML_API_KEY
    AI_ML_BASE_URL = AI_ML_BASE_URL
