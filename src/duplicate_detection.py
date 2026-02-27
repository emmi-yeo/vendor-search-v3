import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from src.local_embedder import embed_text
from rapidfuzz import fuzz

def find_duplicate_vendors(profiles: pd.DataFrame, similarity_threshold: float = 0.85) -> List[Dict]:
    """Find potential duplicate vendor records using embeddings and fuzzy matching."""
    duplicates = []
    
    # Get embeddings for vendor names
    vendor_names = profiles['vendor_name'].tolist()
    vendor_ids = profiles['vendor_id'].tolist()
    
    # Calculate embeddings
    embeddings = []
    for name in vendor_names:
        emb = embed_text(name)
        embeddings.append(emb)
    
    embeddings = np.array(embeddings)
    
    # Normalize for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1  # Avoid division by zero
    embeddings_norm = embeddings / norms
    
    # Calculate pairwise similarities
    similarity_matrix = np.dot(embeddings_norm, embeddings_norm.T)
    
    # Find pairs above threshold
    for i in range(len(vendor_names)):
        for j in range(i + 1, len(vendor_names)):
            sim_score = similarity_matrix[i][j]
            
            if sim_score >= similarity_threshold:
                # Additional checks
                name_sim = fuzz.ratio(vendor_names[i].lower(), vendor_names[j].lower())
                address_sim = 0.0
                
                # Compare addresses if available
                if 'city' in profiles.columns and 'state' in profiles.columns:
                    addr1 = f"{profiles.iloc[i].get('city', '')} {profiles.iloc[i].get('state', '')}"
                    addr2 = f"{profiles.iloc[j].get('city', '')} {profiles.iloc[j].get('state', '')}"
                    if addr1 and addr2:
                        address_sim = fuzz.ratio(addr1.lower(), addr2.lower())
                
                # Calculate confidence
                confidence = (sim_score * 0.5 + name_sim / 100 * 0.3 + address_sim / 100 * 0.2)
                
                if confidence >= similarity_threshold:
                    reason_parts = []
                    if sim_score > 0.9:
                        reason_parts.append("Very similar embeddings")
                    if name_sim > 80:
                        reason_parts.append(f"Name similarity: {name_sim}%")
                    if address_sim > 70:
                        reason_parts.append(f"Address similarity: {address_sim}%")
                    
                    duplicates.append({
                        'vendor1_id': vendor_ids[i],
                        'vendor1_name': vendor_names[i],
                        'vendor2_id': vendor_ids[j],
                        'vendor2_name': vendor_names[j],
                        'confidence_score': round(confidence, 3),
                        'embedding_similarity': round(sim_score, 3),
                        'name_similarity': name_sim,
                        'address_similarity': address_sim,
                        'reason': "; ".join(reason_parts) if reason_parts else "Similar vendor profiles"
                    })
    
    # Sort by confidence
    duplicates.sort(key=lambda x: x['confidence_score'], reverse=True)
    
    return duplicates

