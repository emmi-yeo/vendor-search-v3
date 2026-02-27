from src.azure_llm import azure_chat
import json
import uuid
import datetime
import decimal

def generate_response(user_text: str, results: list[dict], aggregation=None) -> str:

    context = {
        "results": results,
        "aggregation": aggregation
    }

    prompt = f"""
You are an AI vendor intelligence assistant.

User question:
"{user_text}"

Database results:
{json.dumps(context, indent=2, default=str)}

Rules:
- Use only provided data.
- Do NOT hallucinate.
- Be concise and professional.
- If many results exist, summarize.
- If the user's question references uploaded file content, use that context when explaining results.
"""

    return azure_chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
