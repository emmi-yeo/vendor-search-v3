import pandas as pd
import numpy as np
import faiss
from rank_bm25 import BM25Okapi
from src.local_embedder import embed_text


def normalize_text(s: str) -> str:
    return " ".join(str(s).replace("\n", " ").split())


def build_vendor_documents(profiles, attachments, txns=None):
    """
    Build documents for FAISS + BM25.
    Transactions are optional.
    Safe for production use.
    """

    # -----------------------------------
    # Attachment grouping (SAFE VERSION)
    # -----------------------------------
    att_g = {}
    att_meta = {}

    if attachments is not None and not attachments.empty:

        # Use correct Azure SQL column names
        # We selected:
        # VendorProfileId AS vendor_id
        # FileName
        # DocumentCategory
        # DocumentType

        att_groups = attachments.groupby("vendor_id")

        for vid, group in att_groups:
            att_texts = []
            att_info = []

            for _, att in group.iterrows():
                att_name = str(att.get("FileName", ""))
                att_category = str(att.get("DocumentCategory", ""))
                att_type = str(att.get("DocumentType", ""))

                combined_text = f"[{att_name} | {att_category} | {att_type}]"
                att_texts.append(combined_text)

                att_info.append({
                    "name": att_name,
                    "category": att_category,
                    "type": att_type
                })

            att_g[vid] = "\n".join(att_texts)
            att_meta[vid] = att_info

    # -----------------------------------
    # No Transaction Logic (for now)
    # -----------------------------------

    docs = []
    meta = []

    for _, v in profiles.iterrows():
        vid = v["vendor_id"]

        doc = f"""
Vendor: {v.get('vendor_name','')} (ID: {vid})
Industry: {v.get('industry','')}
Location: {v.get('state','')} {v.get('city','')}
Certifications: {v.get('certifications','')}
Status: {v.get('Status','')}

Attachments:
{att_g.get(vid, '')}
"""

        docs.append(normalize_text(doc))

        meta.append({
            "vendor_id": vid,
            "vendor_name": str(v.get("vendor_name", "")),
            "industry": str(v.get("industry", "")),
            "country": str(v.get("country", "")),
            "state": str(v.get("state", "")),
            "city": str(v.get("city", "")),
            "certifications": str(v.get("certifications", "")),
            "total_spend": 0.0,
            "avg_transaction_value": 0.0,
            "transaction_count": 0,
            "awarded_count": 0,
            "latest_transaction_date": None,
            "attachments": att_meta.get(vid, [])
        })

    return docs, meta


def build_faiss_and_bm25(docs: list[str], embed_model: str):

    vectors = []
    for d in docs:
        vectors.append(embed_text(d))

    X = np.array(vectors, dtype="float32")

    # Normalize for cosine similarity
    faiss.normalize_L2(X)

    index = faiss.IndexFlatIP(X.shape[1])
    index.add(X)

    tokenized = [d.lower().split() for d in docs]
    bm25 = BM25Okapi(tokenized)

    return index, bm25, X.shape[1]
