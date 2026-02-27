import json
from src.azure_llm import azure_chat

def generate_search_plan(user_text: str, file_context: str = "") -> dict:
    file_section = ""
    if file_context:
        file_section = f"""

--- Uploaded File Content ---
{file_context}
--- End File Content ---

Also analyze the uploaded file(s) above and incorporate any relevant requirements, specifications, industries, certifications, or locations into the search filters.
"""

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
{file_section}"""

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
