from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv(override = True)

def create_client():
    open_ai_key = os.getenv("OPENAI_API_KEY")
    if not open_ai_key:
        raise ValueError("OPENAI_API_KEY is not set")

    else:
        client = OpenAI(
            base_url="https://api.aimlapi.com/v1",
            api_key= open_ai_key,    
        )
        return client

