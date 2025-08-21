from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv(override = True)

def create_client(openai_key : str = None):
    if openai_key is None:
        open_ai_key = os.getenv("OPENAI_API_KEY")
        if not open_ai_key:
            raise ValueError("OPENAI_API_KEY is not set")
    else:
        open_ai_key = openai_key

    client = OpenAI(
        base_url="https://api.aimlapi.com/v1",
        api_key= open_ai_key,    
    )
    return client

