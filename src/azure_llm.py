import os
from typing import List, Dict
from openai import AzureOpenAI

_client = None


def _get_api_key():
    """Get AZURE_OPENAI_KEY from environment."""
    api_key = os.getenv("AZURE_OPENAI_KEY", "")
    if not api_key:
        raise RuntimeError(
            "AZURE_OPENAI_KEY environment variable is not set."
        )
    return api_key


def _get_endpoint():
    """Get AZURE_OPENAI_ENDPOINT from environment."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    if not endpoint:
        raise RuntimeError(
            "AZURE_OPENAI_ENDPOINT environment variable is not set."
        )
    return endpoint


def _get_chat_model():
    """
    Get Azure deployment name.
    IMPORTANT: This must match the Deployment Name
    you created in Azure, NOT the base model name.
    """
    return os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-nano")


def _get_client():
    """Lazy initialization of Azure OpenAI client."""
    global _client
    if _client is None:
        _client = AzureOpenAI(
            api_key=_get_api_key(),
            api_version="2024-02-15-preview",
            azure_endpoint=_get_endpoint(),
        )
    return _client


def azure_chat(
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 512,
) -> str:
    """
    Chat completion via Azure OpenAI.
    Compatible with existing Groq message format:
    [{"role":"system|user|assistant","content":"..."}]
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
            f"Azure OpenAI chat failed. "
            f"AZURE_OPENAI_DEPLOYMENT={model}. "
            f"Check AZURE_OPENAI_KEY, endpoint, and deployment name. "
            f"Error: {e}"
        )
