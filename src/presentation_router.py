import json
#from src.groq_client import groq_chat
from src.azure_llm import azure_chat as groq_chat

PRESENTATION_SYSTEM_PROMPT = """
You decide how search results should be presented.

Return JSON:
{
  "mode": "table" | "narrative",
  "reason": "short explanation"
}

Use TABLE when:
- User is searching for vendors
- User wants a list, comparison, ranking, or discovery
- Multiple vendors are returned

Use NARRATIVE when:
- User asks why / explain / reason
- User asks about a specific vendor
- Context or performance explanation is needed
"""

def decide_presentation(user_query: str, result_count: int):
    messages = [
        {"role": "system", "content": PRESENTATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""
User query: {user_query}
Number of results: {result_count}
"""
        }
    ]

    try:
        resp = groq_chat(messages, temperature=0)
        resp = resp.strip()
        if resp.startswith("```"):
            resp = resp.split("```")[1]
            if resp.startswith("json"):
                resp = resp[4:]
        return json.loads(resp)
    except Exception:
        # Safe fallback
        return {"mode": "table", "reason": "default"}

