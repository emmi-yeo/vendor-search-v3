#from src.groq_client import groq_chat
from src.azure_llm import azure_chat as groq_chat
import json

def parse_presentation_instructions(user_text: str) -> dict:
    """
    Extract presentation/layout instructions from user query.
    Returns a structured JSON instruction set.
    """

    system_prompt = """
You are a UI layout interpreter for a procurement search system.

Extract ONLY presentation instructions from the user request.

Return STRICT JSON with possible keys:
- fields: list of columns to show
- order: list defining column order
- limit: integer (max rows)
- format: "table" | "markdown" | "text"
- date_format: e.g. "YYYY-MM-DD", "DD/MM/YYYY"
- group_by: field name or null
- sort_by: field name or null
- sort_order: "asc" | "desc"

Rules:
- Do NOT invent fields
- Do NOT include search logic
- If instruction not mentioned, omit it
- Output JSON ONLY
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    raw = groq_chat(messages, temperature=0)

    try:
        return json.loads(raw)
    except Exception:
        return {}

