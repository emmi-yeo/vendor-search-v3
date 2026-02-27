from src.azure_llm import azure_chat
import json
import uuid
import datetime
import decimal

def generate_response(user_text: str, results: list[dict], aggregation=None, file_context: str = "") -> str:

    context = {
        "results": results,
        "aggregation": aggregation
    }

    file_section = ""
    if file_context:
        file_section = f"""

Uploaded file content (provided by user):
{file_context}

"""

    prompt = f"""
You are an AI vendor intelligence assistant.

User question:
"{user_text}"
{file_section}
Database results:
{json.dumps(context, indent=2, default=str)}

Rules:
- Use only provided data.
- Do NOT hallucinate.
- Be concise and professional.
- If many results exist, summarize.
- If the user uploaded a file, reference relevant details from it when explaining results.
"""

    return azure_chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
