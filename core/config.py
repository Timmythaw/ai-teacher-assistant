import os
from dotenv import load_dotenv

# ✅ Always load .env from project root
load_dotenv(override = True)

AI_ML_API_KEY = os.getenv("AI_ML_API_KEY")
AI_ML_BASE_URL = "https://api.aimlapi.com/v1"

if not AI_ML_API_KEY:
    raise ValueError("❌ Missing AI_ML_API_KEY. Please add it to your .env file")