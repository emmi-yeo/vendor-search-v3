import pandas as pd
import numpy as np
import faiss
from rank_bm25 import BM25Okapi
from src.local_embedder import embed_text

def normalize_text(s: str) -> str:
    return " ".join(str(s).replace("\n"," ").split())

def build_vendor_documents(profiles, attachments, txns):
    # group attachments + txns by vendor with better structure
    # Store attachment metadata separately for matching
    att_groups = attachments.groupby("vendor_id")
    att_g = {}
    att_meta = {}  # Store attachment names and types for display
    
    for vid, group in att_groups:
        # Combine all attachment texts with better structure
        att_texts = []
        att_info = []
        for _, att in group.iterrows():
            att_name = str(att.get('attachment_name', ''))
            att_type = str(att.get('attachment_type', ''))
            att_text = str(att.get('attachment_text', ''))
            att_texts.append(f"[{att_name} ({att_type})]: {att_text}")
            att_info.append({"name": att_name, "type": att_type, "text": att_text})
        att_g[vid] = "\n".join(att_texts)
        att_meta[vid] = att_info
    
    tx_g = txns.groupby("vendor_id").apply(
        lambda df: f"Recent transactions: {len(df)} | Latest: {df['date'].max()} | Categories: {', '.join(df['category'].astype(str).head(5))}"
    ).to_dict()
    
    # Calculate transaction aggregates for performance scoring
    txns_numeric = txns.copy()
    txns_numeric['value'] = pd.to_numeric(txns_numeric['value'], errors='coerce').fillna(0)
    txns_numeric['date'] = pd.to_datetime(txns_numeric['date'], errors='coerce')
    
    txn_stats = txns_numeric.groupby("vendor_id").agg({
        'value': ['sum', 'mean', 'count'],
        'date': 'max'
    }).to_dict(orient='index')
    
    # Flatten the multi-level dict
    txn_agg = {}
    for vid, stats in txn_stats.items():
        txn_agg[vid] = {
            'total_spend': float(stats[('value', 'sum')]) if ('value', 'sum') in stats else 0.0,
            'avg_transaction_value': float(stats[('value', 'mean')]) if ('value', 'mean') in stats else 0.0,
            'transaction_count': int(stats[('value', 'count')]) if ('value', 'count') in stats else 0,
            'latest_transaction_date': str(stats[('date', 'max')]) if ('date', 'max') in stats else None
        }
    
    # Get awarded transactions count
    awarded_txns = txns_numeric[txns_numeric['status'] == 'Awarded'].groupby('vendor_id').size().to_dict()

    docs = []
    meta = []
    for _, v in profiles.iterrows():
        vid = v["vendor_id"]
        doc = f"""
Vendor: {v['vendor_name']} (ID: {vid})
Industry: {v.get('industry','')}
Location: {v.get('country','')} {v.get('state','')} {v.get('city','')}
Certifications: {v.get('certifications','')}
Capabilities: {v.get('capabilities','')}
Keywords: {v.get('keywords','')}

Attachments:
{att_g.get(vid,'')}

Transactions:
{tx_g.get(vid,'')}
"""
        docs.append(normalize_text(doc))
        stats = txn_agg.get(vid, {
            'total_spend': 0.0,
            'avg_transaction_value': 0.0,
            'transaction_count': 0,
            'latest_transaction_date': None
        })
        meta.append({
            "vendor_id": vid,
            "vendor_name": v["vendor_name"],
            "industry": str(v.get("industry","")),
            "country": str(v.get("country","")),
            "state": str(v.get("state","")),
            "city": str(v.get("city","")),
            "certifications": str(v.get("certifications","")),
            "total_spend": stats['total_spend'],
            "avg_transaction_value": stats['avg_transaction_value'],
            "transaction_count": stats['transaction_count'],
            "awarded_count": awarded_txns.get(vid, 0),
            "latest_transaction_date": stats['latest_transaction_date'],
            "attachments": att_meta.get(vid, [])  # Store attachment metadata
        })
    return docs, meta

def build_faiss_and_bm25(docs: list[str], embed_model: str):
    vectors = []
    for d in docs:
        vectors.append(embed_text(d))

    X = np.array(vectors, dtype="float32")

    # cosine similarity via inner product on normalized vectors
    faiss.normalize_L2(X)
    index = faiss.IndexFlatIP(X.shape[1])
    index.add(X)

    tokenized = [d.lower().split() for d in docs]
    bm25 = BM25Okapi(tokenized)

    return index, bm25, X.shape[1]
