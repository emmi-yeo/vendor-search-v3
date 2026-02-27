import json
from typing import Dict, List
#from src.groq_client import groq_chat
from src.azure_llm import azure_chat as groq_chat

INTENT_SYSTEM_PROMPT = """
You are an intent classifier for a procurement vendor AI assistant.

Classify the user's message into ONE of the following intents:

1. greeting
- Greetings, small talk, or onboarding messages
- Examples: "hi", "hello", "good morning", "how does this work"

2. vendor_fact
- Asking about a SPECIFIC vendor and a FACTUAL attribute
- Examples:
  - "What certifications does SecureNet have?"
  - "Where is ABC Sdn Bhd located?"
  - "Does V001 have ISO27001?"

3. vendor_search
- Looking for vendors that match criteria
- Examples:
  - "Cybersecurity vendors in Malaysia"
  - "Vendors with ISO27001 and SOC experience"
  - "Top 10 vendors by spend"

Return ONLY valid JSON:
{
  "intent": "greeting" | "vendor_fact" | "vendor_search",
  "vendor_name_or_id": string | null,
  "requested_field": string | null
}

Rules:
- vendor_name_or_id should be filled ONLY for vendor_fact
- requested_field examples:
  certifications, location, industry, capabilities, contact, spend
- If unsure, default to vendor_search
"""

def route_intent(user_text: str, recent_vendor_ids: List[str] = None) -> Dict:
    messages = [
        {"role": "system", "content": INTENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"User message: {user_text}\nRecent vendors: {recent_vendor_ids or []}"
        }
    ]

    try:
        response = groq_chat(messages, temperature=0.0)
        response = response.strip()

        # Strip markdown if any
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        response = response.strip()

        result = json.loads(response)
        return result
    except Exception:
        # Safe fallback
        return {
            "intent": "vendor_search",
            "vendor_name_or_id": None,
            "requested_field": None
        }

