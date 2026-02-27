import os
from typing import List, Dict
from groq import Groq

_client = None

def _get_api_key():
    """Get GROQ_API_KEY from environment, reading it fresh each time."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable is not set. Please add it to your .env file.")
    return api_key

def _get_chat_model():
    """Get GROQ_CHAT_MODEL from environment, reading it fresh each time."""
    return os.getenv("GROQ_CHAT_MODEL", "llama-3.1-8b-instant")

def _get_client():
    """Lazy initialization of Groq client."""
    global _client
    if _client is None:
        api_key = _get_api_key()
        _client = Groq(api_key=api_key)
    return _client

def groq_chat(messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 512) -> str:
    """
    Chat completion via Groq API.
    messages format matches OpenAI-style: [{"role":"system|user|assistant","content":"..."}]
    """
    try:
        client = _get_client()
        model = _get_chat_model()
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        model = _get_chat_model()
        raise RuntimeError(
            f"Groq chat failed. GROQ_CHAT_MODEL={model}. "
            f"Check GROQ_API_KEY and model availability. Error: {e}"
        )

