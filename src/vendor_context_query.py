"""
Handle vendor context queries - queries about vendor performance, sourcing events, awards, etc.
"""
import re
from typing import Dict, Optional, Tuple
#from src.groq_client import groq_chat
from src.azure_llm import azure_chat as groq_chat
from src.vendor_context import get_vendor_context
import pandas as pd


CONTEXT_QUERY_SYSTEM = """You are a vendor context query analyzer. Determine if a user query is asking about a specific vendor's context (performance, transactions, sourcing events, etc.) rather than searching for vendors.

Return JSON with:
{
  "is_context_query": boolean,
  "vendor_identifier": string (vendor_id, vendor_name, or null),
  "context_type": string (one of: "performance", "sourcing_events", "awards", "invoices", "spend_history", "delivery_issues", "general", null),
  "query_intent": string (brief description of what user wants to know)
}

Context query indicators:
- Mentions specific vendor by name or ID (e.g., "V001", "SecureNet", "this vendor")
- Asks about vendor's history, performance, transactions, events
- Uses phrases like: "show performance", "what sourcing events", "awards won", "invoices", "spend history", "delivery issues"
- Uses "this vendor", "that vendor", "for vendor X"

Examples:
- "Show performance issues for V001" => is_context_query: true, vendor_identifier: "V001", context_type: "performance"
- "What sourcing events did SecureNet participate in?" => is_context_query: true, vendor_identifier: "SecureNet", context_type: "sourcing_events"
- "cybersecurity vendors in Malaysia" => is_context_query: false
- "Show me vendors with ISO27001" => is_context_query: false
"""


def detect_context_query(user_text: str, recent_vendor_ids: list = None) -> Dict:
    """Detect if a query is about vendor context and extract vendor identifier."""
    messages = [
        {"role": "system", "content": CONTEXT_QUERY_SYSTEM},
        {"role": "user", "content": f"User query: {user_text}\nRecent vendor IDs in context: {recent_vendor_ids or []}"}
    ]
    
    try:
        response = groq_chat(messages, temperature=0.1)
        # Parse JSON response
        import json
        # Remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        response = response.strip()
        
        result = json.loads(response)
        return result
    except Exception as e:
        # Fallback: simple pattern matching
        return _fallback_detect_context_query(user_text, recent_vendor_ids)


def _fallback_detect_context_query(user_text: str, recent_vendor_ids: list = None) -> Dict:
    """Fallback detection using pattern matching."""
    text_lower = user_text.lower()
    
    # Context query indicators
    context_phrases = [
        "performance issues", "performance problems", "show performance",
        "sourcing events", "what sourcing", "participated in",
        "awards won", "awards lost", "won awards", "lost awards",
        "invoices", "invoice submitted", "invoice history",
        "spend history", "transaction history", "spending",
        "delivery issues", "delivery problems", "delivery flags"
    ]
    
    is_context = any(phrase in text_lower for phrase in context_phrases)
    is_context = is_context or "this vendor" in text_lower or "that vendor" in text_lower
    
    # Extract vendor identifier
    vendor_id = None
    # Check for "this vendor", "that vendor", "the vendor"
    if re.search(r'\b(this|that|the)\s+vendor\b', text_lower):
        if recent_vendor_ids and len(recent_vendor_ids) > 0:
            vendor_id = recent_vendor_ids[0]
    # Pattern: V followed by digits
    elif re.search(r'\bV\d+\b', user_text, re.IGNORECASE):
        vendor_id_match = re.search(r'\bV\d+\b', user_text, re.IGNORECASE)
        vendor_id = vendor_id_match.group(0).upper()
    elif recent_vendor_ids and len(recent_vendor_ids) > 0:
        # Use most recent vendor if context suggests it
        if is_context:
            vendor_id = recent_vendor_ids[0]
    
    # Determine context type
    context_type = "general"
    if "performance" in text_lower:
        context_type = "performance"
    elif "sourcing" in text_lower or "events" in text_lower:
        context_type = "sourcing_events"
    elif "award" in text_lower:
        context_type = "awards"
    elif "invoice" in text_lower:
        context_type = "invoices"
    elif "spend" in text_lower or "transaction" in text_lower:
        context_type = "spend_history"
    elif "delivery" in text_lower:
        context_type = "delivery_issues"
    
    return {
        "is_context_query": is_context and vendor_id is not None,
        "vendor_identifier": vendor_id,
        "context_type": context_type if is_context else None,
        "query_intent": user_text
    }


def get_sourcing_events(vendor_txns: pd.DataFrame) -> list:
    """Extract sourcing events from transactions (Quoted = participated, Awarded = won)."""
    events = []
    for _, txn in vendor_txns.iterrows():
        event_type = "Won" if txn['status'] == 'Awarded' else "Participated"
        events.append({
            'txn_id': str(txn.get('txn_id', '')),
            'date': str(txn.get('date', '')),
            'category': str(txn.get('category', '')),
            'value': float(txn.get('value', 0)),
            'status': str(txn.get('status', '')),
            'buyer_dept': str(txn.get('buyer_dept', '')),
            'notes': str(txn.get('notes', '')),
            'event_type': event_type
        })
    # Sort by date descending
    events.sort(key=lambda x: x['date'], reverse=True)
    return events


def get_invoices(vendor_txns: pd.DataFrame) -> list:
    """Extract invoices from awarded transactions (awarded = invoiced)."""
    awarded_txns = vendor_txns[vendor_txns['status'] == 'Awarded'].copy()
    invoices = []
    for _, txn in awarded_txns.iterrows():
        invoices.append({
            'txn_id': str(txn.get('txn_id', '')),
            'invoice_date': str(txn.get('date', '')),
            'category': str(txn.get('category', '')),
            'amount': float(txn.get('value', 0)),
            'buyer_dept': str(txn.get('buyer_dept', '')),
            'description': str(txn.get('notes', ''))
        })
    # Sort by date descending
    invoices.sort(key=lambda x: x['invoice_date'], reverse=True)
    return invoices


def get_awards_won_lost(vendor_txns: pd.DataFrame) -> Dict:
    """Get detailed awards won and lost."""
    won = vendor_txns[vendor_txns['status'] == 'Awarded'].copy()
    lost = vendor_txns[vendor_txns['status'] == 'Quoted'].copy()
    
    awards_won = []
    for _, txn in won.iterrows():
        awards_won.append({
            'txn_id': str(txn.get('txn_id', '')),
            'date': str(txn.get('date', '')),
            'category': str(txn.get('category', '')),
            'value': float(txn.get('value', 0)),
            'buyer_dept': str(txn.get('buyer_dept', '')),
            'description': str(txn.get('notes', ''))
        })
    
    awards_lost = []
    for _, txn in lost.iterrows():
        awards_lost.append({
            'txn_id': str(txn.get('txn_id', '')),
            'date': str(txn.get('date', '')),
            'category': str(txn.get('category', '')),
            'value': float(txn.get('value', 0)),
            'buyer_dept': str(txn.get('buyer_dept', '')),
            'description': str(txn.get('notes', ''))
        })
    
    # Sort by date descending
    awards_won.sort(key=lambda x: x['date'], reverse=True)
    awards_lost.sort(key=lambda x: x['date'], reverse=True)
    
    return {
        'won': awards_won,
        'lost': awards_lost,
        'won_count': len(awards_won),
        'lost_count': len(awards_lost),
        'win_rate': len(awards_won) / len(vendor_txns) if len(vendor_txns) > 0 else 0.0
    }


def find_vendor_by_identifier(vendor_identifier: str, profiles: pd.DataFrame, recent_vendor_ids: list = None) -> Optional[str]:
    """Find vendor ID from identifier (ID, name, or "this vendor"/"that vendor")."""
    if not vendor_identifier:
        return None
    
    # Handle "this vendor" or "that vendor" - use most recent vendor
    if vendor_identifier.lower() in ["this vendor", "that vendor", "the vendor"]:
        if recent_vendor_ids and len(recent_vendor_ids) > 0:
            return recent_vendor_ids[0]
        return None
    
    # Direct vendor ID match (V001, V002, etc.)
    if vendor_identifier.upper().startswith('V') and len(vendor_identifier) > 1:
        vendor_id = vendor_identifier.upper()
        if vendor_id in profiles['vendor_id'].values:
            return vendor_id
    
    # Try to find by name (case-insensitive partial match)
    matching_vendors = profiles[profiles['vendor_name'].str.contains(vendor_identifier, case=False, na=False)]
    if not matching_vendors.empty:
        return matching_vendors.iloc[0]['vendor_id']
    
    return None


def answer_context_query(
    vendor_id: str,
    context_type: str,
    query_intent: str,
    profiles: pd.DataFrame,
    transactions: pd.DataFrame,
    attachments: pd.DataFrame,
    enrichment: Optional[Dict] = None,
) -> str:
    """Generate a detailed answer to a vendor context query."""
    # Get vendor context
    context = get_vendor_context(vendor_id, profiles, transactions, attachments)
    
    if not context:
        return f"Vendor {vendor_id} not found."
    
    vendor_name = context.get('vendor_name', vendor_id)
    vendor_txns = transactions[transactions['vendor_id'] == vendor_id].copy()
    vendor_txns['value'] = pd.to_numeric(vendor_txns['value'], errors='coerce').fillna(0)
    vendor_txns['date'] = pd.to_datetime(vendor_txns['date'], errors='coerce')
    
    # Build answer based on context type
    answer_parts = [f"## Vendor Context: {vendor_name} ({vendor_id})\n"]
    
    if context_type == "performance":
        answer_parts.append("### Performance Summary\n")
        txn_summary = context['transaction_summary']
        answer_parts.append(f"- **Total Spend:** ${txn_summary['total_spend']:,.0f}")
        answer_parts.append(f"- **Transaction Count:** {txn_summary['transaction_count']}")
        answer_parts.append(f"- **Award Rate:** {txn_summary['award_rate']:.1%}")
        answer_parts.append(f"- **Average Transaction Value:** ${txn_summary['avg_transaction_value']:,.0f}")
        
        if context.get('delivery_issues'):
            answer_parts.append("\n### ⚠️ Performance Issues\n")
            for issue in context['delivery_issues']:
                answer_parts.append(f"- **{issue['date']}:** {issue['notes']}")
        else:
            answer_parts.append("\n✅ No delivery issues detected.")
    
    elif context_type == "sourcing_events":
        answer_parts.append("### Sourcing Events\n")
        events = get_sourcing_events(vendor_txns)
        if events:
            for event in events:
                answer_parts.append(f"- **{event['date']}** - {event['event_type']}: {event['category']} (${event['value']:,.0f})")
                answer_parts.append(f"  - Department: {event['buyer_dept']}")
                answer_parts.append(f"  - Details: {event['notes']}")
        else:
            answer_parts.append("No sourcing events found.")
    
    elif context_type == "awards":
        answer_parts.append("### Awards Won and Lost\n")
        awards = get_awards_won_lost(vendor_txns)
        answer_parts.append(f"- **Win Rate:** {awards['win_rate']:.1%}")
        answer_parts.append(f"- **Awards Won:** {awards['won_count']}")
        answer_parts.append(f"- **Awards Lost:** {awards['lost_count']}")
        
        if awards['won']:
            answer_parts.append("\n#### Awards Won:")
            for award in awards['won'][:10]:  # Top 10
                answer_parts.append(f"- **{award['date']}:** {award['category']} - ${award['value']:,.0f}")
                answer_parts.append(f"  - {award['description']}")
        
        if awards['lost']:
            answer_parts.append("\n#### Awards Lost (Quoted but not awarded):")
            for award in awards['lost'][:10]:  # Top 10
                answer_parts.append(f"- **{award['date']}:** {award['category']} - ${award['value']:,.0f}")
                answer_parts.append(f"  - {award['description']}")
    
    elif context_type == "invoices":
        answer_parts.append("### Invoices Submitted\n")
        invoices = get_invoices(vendor_txns)
        if invoices:
            total_invoiced = sum(inv['amount'] for inv in invoices)
            answer_parts.append(f"- **Total Invoiced:** ${total_invoiced:,.0f}")
            answer_parts.append(f"- **Invoice Count:** {len(invoices)}")
            answer_parts.append("\n#### Recent Invoices:")
            for invoice in invoices[:10]:  # Top 10
                answer_parts.append(f"- **{invoice['invoice_date']}:** ${invoice['amount']:,.0f} - {invoice['category']}")
                answer_parts.append(f"  - Department: {invoice['buyer_dept']}")
                answer_parts.append(f"  - Description: {invoice['description']}")
        else:
            answer_parts.append("No invoices found.")
    
    elif context_type == "spend_history":
        answer_parts.append("### Spend History\n")
        txn_summary = context['transaction_summary']
        answer_parts.append(f"- **Total Spend:** ${txn_summary['total_spend']:,.0f}")
        answer_parts.append(f"- **Transaction Count:** {txn_summary['transaction_count']}")
        answer_parts.append(f"- **Average Transaction:** ${txn_summary['avg_transaction_value']:,.0f}")
        
        if context.get('recent_transactions'):
            answer_parts.append("\n#### Recent Transactions:")
            for txn in context['recent_transactions']:
                answer_parts.append(f"- **{txn['date']}:** ${txn['value']:,.0f} - {txn['status']} - {txn['category']}")
                if txn.get('notes'):
                    answer_parts.append(f"  - {txn['notes']}")
    
    elif context_type == "delivery_issues":
        answer_parts.append("### Delivery Issues and Flags\n")
        if context.get('delivery_issues'):
            for issue in context['delivery_issues']:
                answer_parts.append(f"- **{issue['date']}** (Transaction {issue['txn_id']}):")
                answer_parts.append(f"  - {issue['notes']}")
        else:
            answer_parts.append("✅ No delivery issues detected.")
    
    else:  # general context
        answer_parts.append("### Complete Vendor Context\n")
        txn_summary = context['transaction_summary']
        answer_parts.append(f"**Transaction Summary:**")
        answer_parts.append(f"- Total Spend: ${txn_summary['total_spend']:,.0f}")
        answer_parts.append(f"- Transactions: {txn_summary['transaction_count']}")
        answer_parts.append(f"- Award Rate: {txn_summary['award_rate']:.1%}")
        answer_parts.append(f"- Avg Transaction: ${txn_summary['avg_transaction_value']:,.0f}")
        
        if context.get('recent_transactions'):
            answer_parts.append("\n**Recent Transactions:**")
            for txn in context['recent_transactions'][:5]:
                answer_parts.append(f"- {txn['date']}: ${txn['value']:,.0f} ({txn['status']}) - {txn['category']}")
        
        if context.get('delivery_issues'):
            answer_parts.append("\n**⚠️ Delivery Issues:**")
            for issue in context['delivery_issues']:
                answer_parts.append(f"- {issue['date']}: {issue['notes']}")

    # Optional external enrichment section
    if enrichment:
        rep = enrichment.get("reputation", {})
        fin = enrichment.get("financial_flags", {})
        comp = enrichment.get("compliance_flags", {})
        registry = enrichment.get("registry", {})

        answer_parts.append("\n### External Reputation & Compliance (best-effort)\n")

        sentiment = rep.get("summary", "unknown").title()
        answer_parts.append(f"- Overall external sentiment: **{sentiment}**")

        neg = rep.get("negative_signals") or []
        if neg:
            answer_parts.append(f"- Negative signals (keywords): {', '.join(neg)}")

        fin_red = fin.get("red_flags") or []
        if fin_red:
            answer_parts.append(f"- Financial red flags (keywords): {', '.join(fin_red)}")

        if comp.get("sanctioned"):
            answer_parts.append("- ⚠️ Potential sanctions match detected (verify against official lists).")

        reg_status = registry.get("company_status")
        if reg_status:
            answer_parts.append(f"- Company registry status (heuristic): {reg_status}")

        news_items = rep.get("news") or []
        if news_items:
            answer_parts.append("\nRecent external news (subset):")
            for item in news_items[:3]:
                headline = item.get("headline", "")
                source = item.get("source", "")
                url = item.get("url", "")
                if url:
                    answer_parts.append(f"- [{headline}]({url}) ({source})")
                else:
                    answer_parts.append(f"- {headline} ({source})")

    return "\n".join(answer_parts)


