from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv(override = True)

def create_client(openai_key : str):
    open_ai_key = openai_key

    client = OpenAI(
        base_url="https://api.aimlapi.com/v1",
        api_key= open_ai_key,    
    )
    return client

