import os
from typing import List, Dict
from openai import AzureOpenAI

_client = None


def _get_api_key():
    api_key = os.getenv("AZURE_OPENAI_KEY", "")
    if not api_key:
        raise RuntimeError("AZURE_OPENAI_KEY is not set.")
    return api_key


def _get_endpoint():
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    if not endpoint:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT is not set.")
    return endpoint


def _get_chat_model():
    # Must match Deployment Name in Foundry
    return os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-nano")


def _get_client():
    global _client
    if _client is None:
        _client = AzureOpenAI(
            api_version="2024-12-01-preview",
            azure_endpoint=_get_endpoint(),
            api_key=_get_api_key(),
        )
    return _client


def azure_chat(
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 512,
) -> str:
    """
    Compatible with your existing groq_chat signature.
    """

    try:
        client = _get_client()
        deployment = _get_chat_model()

        response = client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_completion_tokens=max_tokens,
        )

        return response.choices[0].message.content

    except Exception as e:
        raise RuntimeError(
            f"Azure OpenAI chat failed. "
            f"Deployment={_get_chat_model()}. "
            f"Error: {e}"
        )
