import json
import os
from datetime import datetime
from typing import Dict, List, Optional

FEEDBACK_FILE = os.getenv("FEEDBACK_FILE", "data/feedback.json")

def load_feedback() -> List[Dict]:
    """Load feedback from JSON file."""
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_feedback(feedback: List[Dict]):
    """Save feedback to JSON file."""
    os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)
    with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(feedback, f, indent=2, ensure_ascii=False)

def add_feedback(
    query: str,
    vendor_id: Optional[str] = None,
    vendor_name: Optional[str] = None,
    feedback_type: str = "helpful",  # "helpful", "not_helpful", "missing_vendor", "incorrect_ranking"
    comment: Optional[str] = None,
    result_score: Optional[float] = None
):
    """Add a feedback entry."""
    feedback_list = load_feedback()
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "vendor_id": vendor_id,
        "vendor_name": vendor_name,
        "feedback_type": feedback_type,
        "comment": comment,
        "result_score": result_score
    }
    
    feedback_list.append(entry)
    save_feedback(feedback_list)
    return entry

def get_feedback_summary() -> Dict:
    """Get summary statistics of feedback."""
    feedback_list = load_feedback()
    
    summary = {
        "total": len(feedback_list),
        "helpful": len([f for f in feedback_list if f.get("feedback_type") == "helpful"]),
        "not_helpful": len([f for f in feedback_list if f.get("feedback_type") == "not_helpful"]),
        "missing_vendor": len([f for f in feedback_list if f.get("feedback_type") == "missing_vendor"]),
        "incorrect_ranking": len([f for f in feedback_list if f.get("feedback_type") == "incorrect_ranking"])
    }
    
    return summary

