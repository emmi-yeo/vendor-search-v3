import json
import numpy as np
import faiss
import pandas as pd
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

# Load data
profiles = pd.read_csv("data/vendor_profiles.csv")
attachments = pd.read_csv("data/vendor_attachments.csv")
txns = pd.read_csv("data/vendor_transactions.csv")

def normalize_text(s: str) -> str:
    return " ".join(str(s).replace("\n"," ").split())

# Build vendor docs (same logic as your app)
docs = []
meta = []

att_g = attachments.groupby("vendor_id")["attachment_text"].apply(lambda x: "\n".join(x.astype(str))).to_dict()
tx_g = txns.groupby("vendor_id").apply(
    lambda df: f"Recent transactions: {len(df)} | Categories: {', '.join(df['category'].astype(str).head(5))}"
).to_dict()

for _, v in profiles.iterrows():
    vid = v["vendor_id"]
    doc = f"""
Vendor: {v['vendor_name']} (ID: {vid})
Industry: {v.get('industry','')}
Location: {v.get('country','')} {v.get('state','')} {v.get('city','')}
Certifications: {v.get('certifications','')}
Capabilities: {v.get('capabilities','')}
Attachments:
{att_g.get(vid,'')}
Transactions:
{tx_g.get(vid,'')}
"""
    docs.append(normalize_text(doc))
    meta.append(v.to_dict())

# Embed locally
model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode(docs, convert_to_numpy=True, normalize_embeddings=True)

# Save FAISS index
index = faiss.IndexFlatIP(embeddings.shape[1])
index.add(embeddings)
faiss.write_index(index, "data/vendor.faiss")

# Save metadata
with open("data/vendor_docs.json", "w") as f:
    json.dump(docs, f)

with open("data/vendor_meta.json", "w") as f:
    json.dump(meta, f)

print("✅ Index precomputed and saved.")
