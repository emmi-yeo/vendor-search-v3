import pandas as pd
from typing import Dict, List
from datetime import datetime

def get_vendor_context(vendor_id: str, profiles: pd.DataFrame, transactions: pd.DataFrame, attachments: pd.DataFrame) -> Dict:
    """Get comprehensive context for a vendor."""
    vendor_profile = profiles[profiles['vendor_id'] == vendor_id]
    
    if vendor_profile.empty:
        return {}
    
    vendor = vendor_profile.iloc[0]
    
    # Transaction context
    vendor_txns = transactions[transactions['vendor_id'] == vendor_id].copy()
    vendor_txns['value'] = pd.to_numeric(vendor_txns['value'], errors='coerce').fillna(0)
    vendor_txns['date'] = pd.to_datetime(vendor_txns['date'], errors='coerce')
    
    total_spend = vendor_txns['value'].sum()
    transaction_count = len(vendor_txns)
    avg_transaction = vendor_txns['value'].mean() if transaction_count > 0 else 0
    awarded_count = len(vendor_txns[vendor_txns['status'] == 'Awarded'])
    quoted_count = len(vendor_txns[vendor_txns['status'] == 'Quoted'])
    
    # Recent transactions
    recent_txns = vendor_txns.nlargest(5, 'date') if 'date' in vendor_txns.columns else vendor_txns.head(5)
    
    # Performance indicators
    delivery_issues = []
    if 'notes' in vendor_txns.columns:
        issue_keywords = ['delay', 'issue', 'problem', 'late', 'failed']
        for _, txn in vendor_txns.iterrows():
            notes = str(txn.get('notes', '')).lower()
            if any(kw in notes for kw in issue_keywords):
                delivery_issues.append({
                    'txn_id': txn.get('txn_id', ''),
                    'date': str(txn.get('date', '')),
                    'notes': txn.get('notes', '')
                })
    
    # Attachment summary
    vendor_attachments = attachments[attachments['vendor_id'] == vendor_id]
    attachment_count = len(vendor_attachments)
    attachment_types = vendor_attachments['attachment_type'].value_counts().to_dict() if 'attachment_type' in vendor_attachments.columns else {}
    
    context = {
        'vendor_id': vendor_id,
        'vendor_name': vendor.get('vendor_name', ''),
        'profile': {
            'industry': vendor.get('industry', ''),
            'location': f"{vendor.get('country', '')}, {vendor.get('state', '')}, {vendor.get('city', '')}",
            'certifications': vendor.get('certifications', ''),
            'capabilities': vendor.get('capabilities', ''),
            'last_updated': vendor.get('last_updated', '')
        },
        'transaction_summary': {
            'total_spend': float(total_spend),
            'transaction_count': int(transaction_count),
            'avg_transaction_value': float(avg_transaction),
            'awarded_count': int(awarded_count),
            'quoted_count': int(quoted_count),
            'award_rate': float(awarded_count / transaction_count) if transaction_count > 0 else 0.0
        },
        'recent_transactions': [
            {
                'txn_id': str(txn.get('txn_id', '')),
                'date': str(txn.get('date', '')),
                'value': float(txn.get('value', 0)),
                'status': str(txn.get('status', '')),
                'category': str(txn.get('category', '')),
                'notes': str(txn.get('notes', ''))
            }
            for _, txn in recent_txns.iterrows()
        ],
        'delivery_issues': delivery_issues[:5],  # Top 5 issues
        'attachments': {
            'count': int(attachment_count),
            'types': attachment_types
        }
    }
    
    return context

def get_vendor_fact(
    vendor_identifier: str,
    field: str,
    profiles: pd.DataFrame
) -> str:
    """
    Return a single factual field for a vendor.
    """
    vendor = profiles[
        (profiles["vendor_id"].astype(str).str.lower() == vendor_identifier.lower()) |
        (profiles["vendor_name"].astype(str).str.lower().str.contains(vendor_identifier.lower()))
    ]

    if vendor.empty:
        return f"❌ I couldn't find a vendor matching '{vendor_identifier}'."

    v = vendor.iloc[0]

    field_map = {
        "certification": "certifications",
        "certifications": "certifications",
        "location": ["country", "state", "city"],
        "industry": "industry",
        "capabilities": "capabilities",
        "spend": "total_spend"
    }

    key = field_map.get(field.lower())

    if key is None:
        return f"⚠️ I can’t retrieve '{field}' yet."

    if isinstance(key, list):
        value = ", ".join([str(v.get(k, "")) for k in key if v.get(k)])
    else:
        value = v.get(key, "")

    if not value:
        return f"ℹ️ No {field} information available for {v['vendor_name']}."

    return f"**{v['vendor_name']} – {field.title()}**: {value}"
