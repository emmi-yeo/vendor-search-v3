import json
from src.azure_llm import azure_chat

def classify_intent(user_text: str) -> dict:
    prompt = f"""
You are an intent classifier for a vendor intelligence system.

Classify the user request into ONE of:
- search_vendors
- aggregate
- database_info
- presentation_only
- other

Return JSON only:
{{
  "intent": "..."
}}

User request:
"{user_text}"
"""

    response = azure_chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    try:
        return json.loads(response)
    except:
        return {"intent": "search_vendors"}
