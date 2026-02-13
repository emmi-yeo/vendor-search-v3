import json
from src.azure_llm import azure_chat

def generate_search_plan(user_text: str) -> dict:
    prompt = f"""
You are a search planner for a vendor database.

Extract structured search filters.

Return JSON only in this format:

{{
  "filters": {{
    "industry": [],
    "location": {{
      "country": "",
      "state": [],
      "city": []
    }},
    "certifications": []
  }},
  "limit": 10,
  "aggregation": null
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
        return {
            "filters": {
                "industry": [],
                "location": {"country": "", "state": [], "city": []},
                "certifications": []
            },
            "limit": 10,
            "aggregation": None
        }
