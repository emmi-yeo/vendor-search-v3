import json
#from src.groq_client import groq_chat
from src.azure_llm import azure_chat as groq_chat

PARSER_SYSTEM = """You are a procurement vendor search query parser.
Return ONLY valid JSON (no markdown).

Schema:
{
  "search_text": string,
  "filters": {
    "industry": [string],
    "location": {"country": string, "state": [string], "city": [string]},
    "certifications": [string]
  },
  "logic_operators": {
    "industry": string (one of: "AND", "OR", null),
    "location": string (one of: "AND", "OR", null),
    "certifications": string (one of: "AND", "OR", null)
  },
  "capabilities": [string],
  "constraints": {
    "industry_strict": boolean,
    "location_strict": boolean,
    "certifications_strict": boolean,
    "capabilities_strict": boolean
  },
  "sort_preference": [string],
  "layout_instructions": {
    "fields": [string] (e.g., ["vendor_name", "country", "certifications"]),
    "group_by": string (e.g., "industry", null),
    "date_format": string (e.g., "DD/MM/YYYY", null)
  },
  "performance_query": {
    "type": string (one of: "top_by_spend", "by_transaction_volume", "by_date_range", "by_status", null),
    "limit": number (e.g., 10 for "top 10"),
    "date_range": {"start": string, "end": string} or null,
    "status": string (e.g., "Awarded", "Quoted") or null
  },
  "compliance_query": {
    "check_tax_registration": boolean,
    "check_statutory_filings": boolean,
    "required_certifications": [string]
  },
  "needs_clarification": boolean,
  "clarifying_question": string
}

Rules:
- If the user explicitly specifies an industry (e.g. "cybersecurity vendors"), set industry_strict=true.
- If the user explicitly specifies a location (e.g. "in Selangor"), set location_strict=true.
- If the user explicitly specifies certifications (e.g. "with ISO27001"), set certifications_strict=true.
- If the user explicitly specifies a capability (e.g. "SOC experience", "OT security", "audit"), set capabilities_strict=true.
- Extract capabilities from phrases like:
  - "SOC monitoring" => "SOC"
  - "OT security", "critical infrastructure" => "OT_SECURITY"
  - "audit", "compliance" => "AUDIT_COMPLIANCE"
- Performance queries: Detect phrases like "top 10 by spend", "Q4 transactions", "vendors with most transactions", "highest spend"
- Compliance queries: Detect phrases like "tax registration", "statutory filings", "missing certifications"
- Logic operators: Detect AND/OR intent from natural language:
  - "vendors with ISO27001 AND SOC experience" => industry: null, certifications: "AND"
  - "vendors in Malaysia OR Singapore" => location: "OR"
  - "vendors with ISO certification AND (IT OR Cybersecurity)" => certifications: "AND", industry: "OR"
  - Default to "AND" if multiple values in same category and no explicit OR
- If query is too vague (no clear industry/capability), set needs_clarification=true and ask 1–2 focused questions.
- Always produce a reasonable search_text even if vague.
- UI filters are authoritative; do not override them.
"""


def parse_query(model: str, user_text: str, ui_filters: dict, file_context: str = "") -> dict:
    # ui_filters lets you blend sidebar selections with LLM extraction
    # LLM should not overwrite explicit UI filters; it can add missing ones.
    
    # Build user message with file context if available
    user_message = f"User query: {user_text}\nUI filters (authoritative if set): {json.dumps(ui_filters)}"
    
    if file_context:
        user_message += f"\n\n--- Uploaded File Content ---\n{file_context}\n--- End File Content ---\n\n"
        user_message += "Please analyze the uploaded file(s) content above and incorporate relevant information into the vendor search query. Extract requirements, specifications, or criteria mentioned in the files."
    
    messages = [
        {"role": "system", "content": PARSER_SYSTEM},
        {"role": "user", "content": user_message}
    ]
    raw = groq_chat(messages, temperature=0.1)

    try:
        q = json.loads(raw)
    except Exception:
        # fallback: minimal safe structure
        q = {
            "search_text": user_text.strip(),
            "filters": {"industry": [], "location": {"country": "", "state": [], "city": []}, "certifications": []},
            "capabilities": [],
            "constraints": {
                "industry_strict": False,
                "location_strict": False,
                "certifications_strict": False,
                "capabilities_strict": False
            },
            "sort_preference": ["relevance"],
            "logic_operators": {"industry": None, "location": None, "certifications": None},
            "performance_query": {"type": None, "limit": None, "date_range": None, "status": None},
            "compliance_query": {"check_tax_registration": False, "check_statutory_filings": False, "required_certifications": []},
            "needs_clarification": True,
            "clarifying_question": "Which industry/category and location should I prioritize?"
        }


    # Merge: UI filters override
    q.setdefault("capabilities", [])
    q.setdefault("constraints", {})
    q["constraints"].setdefault("industry_strict", False)
    q["constraints"].setdefault("location_strict", False)
    q["constraints"].setdefault("certifications_strict", False)
    q["constraints"].setdefault("capabilities_strict", False)
    q.setdefault("logic_operators", {"industry": None, "location": None, "certifications": None})
    q.setdefault("performance_query", {"type": None, "limit": None, "date_range": None, "status": None})
    q.setdefault("compliance_query", {"check_tax_registration": False, "check_statutory_filings": False, "required_certifications": []})
    
    # Detect AND/OR logic from natural language
    ut = user_text.lower()
    if " and " in ut or " with " in ut:
        # Default to AND if multiple items mentioned
        if len(q.get("filters", {}).get("industry", [])) > 1:
            q["logic_operators"]["industry"] = q["logic_operators"].get("industry") or "AND"
        if len(q.get("filters", {}).get("certifications", [])) > 1:
            q["logic_operators"]["certifications"] = q["logic_operators"].get("certifications") or "AND"
    if " or " in ut:
        # Explicit OR detected
        if "industry" in ut or any(ind in ut for ind in q.get("filters", {}).get("industry", [])):
            q["logic_operators"]["industry"] = "OR"
        if "location" in ut or "country" in ut or "state" in ut:
            q["logic_operators"]["location"] = "OR"
        if "certification" in ut or "cert" in ut:
            q["logic_operators"]["certifications"] = "OR"
    
    # Detect performance queries
    ut = user_text.lower()
    if any(k in ut for k in ["top", "highest", "most", "by spend", "by transaction"]):
        if "top" in ut:
            import re
            top_match = re.search(r"top\s+(\d+)", ut)
            if top_match:
                q["performance_query"]["limit"] = int(top_match.group(1))
        if any(k in ut for k in ["by spend", "spend", "highest spend"]):
            q["performance_query"]["type"] = "top_by_spend"
        elif any(k in ut for k in ["by transaction", "most transactions", "transaction volume"]):
            q["performance_query"]["type"] = "by_transaction_volume"
    
    # Detect date range queries
    if any(k in ut for k in ["q4", "q1", "q2", "q3", "quarter", "2024", "2025"]):
        q["performance_query"]["type"] = "by_date_range"
        # Simple detection - can be enhanced
        if "q4" in ut or "quarter 4" in ut:
            q["performance_query"]["date_range"] = {"start": "2024-10-01", "end": "2024-12-31"}
    
    # Detect compliance queries
    if any(k in ut for k in ["tax registration", "tax reg"]):
        q["compliance_query"]["check_tax_registration"] = True
    if any(k in ut for k in ["statutory", "filing", "compliance flag"]):
        q["compliance_query"]["check_statutory_filings"] = True
    
    # Detect layout instructions
    q.setdefault("layout_instructions", {"fields": None, "group_by": None, "date_format": None})
    if any(k in ut for k in ["show only", "display only", "only show"]):
        # Extract field names (basic detection)
        if "name" in ut and "country" in ut:
            q["layout_instructions"]["fields"] = ["vendor_name", "country"]
        elif "name" in ut:
            q["layout_instructions"]["fields"] = ["vendor_name"]
    if "group by" in ut or "grouped by" in ut:
        if "industry" in ut:
            q["layout_instructions"]["group_by"] = "industry"
    # ---- Deterministic strictness overrides (don't rely purely on LLM) ----
    # ut already defined above

    # Industry strict if user says "vendors" + an industry keyword
    if any(k in ut for k in ["cybersecurity", "cloud vendor", "healthcare it", "analytics vendors", "data analytics"]):
        if q["filters"].get("industry") or "cybersecurity" in ut or "healthcare it" in ut or "cloud vendor" in ut:
            q["constraints"]["industry_strict"] = True

    # Location strict if user explicitly names a place "in X"
    if " in " in ut:
        q["constraints"]["location_strict"] = True

    # Certifications strict if "with ISO" / "ISO27001" etc appears
    if "iso" in ut:
        q["constraints"]["certifications_strict"] = True

    # Capabilities strict if they request experience explicitly
    if any(k in ut for k in ["soc", "ot", "critical infrastructure", "audit", "compliance"]):
        q["constraints"]["capabilities_strict"] = True

    # Capability extraction (ensure at least deterministic tags)
    caps = set([c.upper() for c in q.get("capabilities", []) if c])
    if "soc" in ut:
        caps.add("SOC")
    if "ot" in ut or "critical infrastructure" in ut:
        caps.add("OT_SECURITY")
    if "audit" in ut or "compliance" in ut:
        caps.add("AUDIT_COMPLIANCE")
    q["capabilities"] = sorted(list(caps))

    # UI override logic
    if ui_filters.get("industry"):
        q["filters"]["industry"] = ui_filters["industry"]
    if ui_filters.get("certifications"):
        q["filters"]["certifications"] = ui_filters["certifications"]
    if ui_filters.get("country"):
        q["filters"]["location"]["country"] = ui_filters["country"]
    if ui_filters.get("state"):
        q["filters"]["location"]["state"] = ui_filters["state"]
    if ui_filters.get("city"):
        q["filters"]["location"]["city"] = ui_filters["city"]

    return q

