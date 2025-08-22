import requests 
from core.config import AI_ML_API_KEY, AI_ML_BASE_URL

def chat_completion(model: str, messages: list, max_tokens : int = None ,temperature: float = 0) -> str:
    # Wrapper for AI ML chat completions
    url = f"{AI_ML_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_ML_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        **({"max_tokens": max_tokens} if max_tokens is not None else {}),
        "response_format": {"type": "json_object"},
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]