from rapidfuzz import fuzz, process
from typing import List, Dict, Tuple, Optional
import json
import os
import re
try:
    from metaphone import doublemetaphone
except ImportError:
    doublemetaphone = None

# Load taxonomy
def _load_abbreviation_taxonomy():
    """Load abbreviations taxonomy."""
    try:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base_path, "data", "taxonomy", "abbreviations.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

ABBREVIATION_TAXONOMY = _load_abbreviation_taxonomy()

# Legacy normalization dictionary (for backward compatibility)
NORMALIZATION_DICT = {
    "iso 27k": "iso27001",
    "iso 27": "iso27001",
    "iso27k": "iso27001",
    "iso 9001": "iso9001",
    "iso9001": "iso9001",
    "cyber sec": "cybersecurity",
    "cyber security": "cybersecurity",
    "it services": "it services",
    "cloud": "cloud services",
}

def normalize_text(text: str) -> str:
    """
    Normalize text using taxonomy + legacy dictionary.
    Expands abbreviations from taxonomy first, then applies normalization dict.
    """
    text_lower = text.lower().strip()
    
    # Apply taxonomy-based expansions for abbreviations
    for abbr, data in ABBREVIATION_TAXONOMY.items():
        pattern = r'\b' + re.escape(abbr) + r'\b'
        if re.search(pattern, text_lower, re.IGNORECASE):
            full_forms = data.get("full_forms", [abbr])
            primary = full_forms[0] if full_forms else abbr
            text_lower = re.sub(pattern, primary, text_lower, flags=re.IGNORECASE)
    
    # Apply legacy normalization dictionary
    for key, value in NORMALIZATION_DICT.items():
        if key in text_lower:
            text_lower = text_lower.replace(key, value)
    
    return text_lower


def phonetic_similarity(text1: str, text2: str) -> float:
    """
    Calculate phonetic similarity using Metaphone algorithm.
    Falls back to direct comparison if metaphone unavailable.
    Returns score 0-100.
    """
    text1_clean = re.sub(r'[^a-z0-9]', '', text1.lower())
    text2_clean = re.sub(r'[^a-z0-9]', '', text2.lower())
    
    if doublemetaphone:
        try:
            metaphone1 = doublemetaphone(text1_clean)[0] or doublemetaphone(text1_clean)[1]
            metaphone2 = doublemetaphone(text2_clean)[0] or doublemetaphone(text2_clean)[1]
            
            if metaphone1 and metaphone2:
                # Exact phonetic match
                if metaphone1 == metaphone2:
                    return 100.0
                # Partial phonetic match
                if metaphone1 in metaphone2 or metaphone2 in metaphone1:
                    return 80.0
        except Exception:
            pass
    
    # Fallback: use string similarity
    ratio = fuzz.ratio(text1_clean, text2_clean)
    return float(ratio)


def embedding_similarity(text1: str, text2: str) -> float:
    """
    Calculate embedding-based similarity using local embedder.
    Falls back to 0 if embeddings unavailable.
    Returns score 0-100.
    """
    try:
        from src.local_embedder import embed_text
        
        emb1 = embed_text(text1)
        emb2 = embed_text(text2)
        
        if emb1 is None or emb2 is None:
            return 0.0
        
        # Calculate cosine similarity
        import numpy as np
        emb1_norm = np.array(emb1) / (np.linalg.norm(np.array(emb1)) + 1e-8)
        emb2_norm = np.array(emb2) / (np.linalg.norm(np.array(emb2)) + 1e-8)
        
        similarity = np.dot(emb1_norm, emb2_norm)
        # Scale from [-1, 1] to [0, 100]
        return max(0, min(100, (similarity + 1) * 50))
    except Exception:
        return 0.0


def match_with_fallback(
    query_term: str,
    candidates: List[str],
    threshold: float = 75,
    phonetic_threshold: float = 70,
    embedding_threshold: float = 60
) -> Tuple[Optional[str], float, str]:
    """
    Match query term against candidates with multi-level fallback.
    
    Levels:
    1. Exact match (100 score)
    2. Fuzzy string match (rapidfuzz, >=threshold)
    3. Phonetic match (metaphone, >=phonetic_threshold)
    4. Embedding match (semantic, >=embedding_threshold)
    
    Returns: (best_match, score, method_used)
    """
    query_norm = normalize_text(query_term)
    
    # Level 1: Exact match
    for candidate in candidates:
        if normalize_text(candidate).lower() == query_norm.lower():
            return candidate, 100.0, "exact"
    
    # Level 2: Fuzzy string match
    best_match = process.extractOne(
        query_norm,
        [normalize_text(c) for c in candidates],
        scorer=fuzz.ratio
    )
    if best_match and best_match[1] >= threshold:
        return candidates[candidates.index(best_match[0])], float(best_match[1]), "fuzzy"
    
    # Level 3: Phonetic match
    best_phonetic_score = 0
    best_phonetic_match = None
    for candidate in candidates:
        score = phonetic_similarity(query_norm, normalize_text(candidate))
        if score > best_phonetic_score:
            best_phonetic_score = score
            best_phonetic_match = candidate
    
    if best_phonetic_match and best_phonetic_score >= phonetic_threshold:
        return best_phonetic_match, best_phonetic_score, "phonetic"
    
    # Level 4: Embedding match (as last resort)
    best_embedding_score = 0
    best_embedding_match = None
    for candidate in candidates:
        score = embedding_similarity(query_term, candidate)
        if score > best_embedding_score:
            best_embedding_score = score
            best_embedding_match = candidate
    
    if best_embedding_match and best_embedding_score >= embedding_threshold:
        return best_embedding_match, best_embedding_score, "embedding"
    
    # No match found at any level
    return None, 0.0, "no_match"


def fuzzy_match_certification(query_cert: str, vendor_certs: str, threshold: int = 75) -> Tuple[bool, float, str]:
    """
    Enhanced fuzzy match certification with multilevel fallback.
    Returns: (is_match: bool, score: float, method: str)
    
    Lowered threshold from 80 to 75 for better matching.
    """
    if not vendor_certs:
        return False, 0.0, "no_certs"
    
    # Parse vendor certifications
    certs_list = [c.strip() for c in vendor_certs.split("|") if c.strip()]
    
    # Try match_with_fallback
    match, score, method = match_with_fallback(
        query_cert,
        certs_list,
        threshold=threshold,
        phonetic_threshold=70,
        embedding_threshold=60
    )
    
    is_match = match is not None
    return is_match, score, method


def fuzzy_match_vendor_name(query_name: str, vendor_name: str, threshold: int = 80) -> Tuple[bool, float, str]:
    """
    Enhanced fuzzy match vendor name with phonetic fallback.
    Lowered threshold from 85 to 80 for better matching.
    Returns: (is_match: bool, score: float, method: str)
    """
    if not vendor_name:
        return False, 0.0, "no_name"
    
    # Try exact match first
    if query_name.lower().strip() == vendor_name.lower().strip():
        return True, 100.0, "exact"
    
    # Try fuzzy match
    ratio = fuzz.ratio(query_name.lower(), vendor_name.lower())
    if ratio >= threshold:
        return True, float(ratio), "fuzzy"
    
    # Try phonetic match
    phonetic_score = phonetic_similarity(query_name, vendor_name)
    if phonetic_score >= 75:
        return True, phonetic_score, "phonetic"
    
    # Try embedding match
    embedding_score = embedding_similarity(query_name, vendor_name)
    if embedding_score >= 65:
        return True, embedding_score, "embedding"
    
    return False, max(ratio, phonetic_score, embedding_score), "no_match"


def fuzzy_match_industry(query_industry: str, vendor_industry: str, threshold: int = 75) -> Tuple[bool, float, str]:
    """
    Enhanced fuzzy match industry with phonetic fallback.
    Returns: (is_match: bool, score: float, method: str)
    """
    if not vendor_industry:
        return False, 0.0, "no_industry"
    
    query_norm = normalize_text(query_industry)
    vendor_norm = normalize_text(vendor_industry)
    
    # Exact match
    if query_norm.lower() == vendor_norm.lower():
        return True, 100.0, "exact"
    
    # Fuzzy match (partial ratio for industry variations)
    ratio = fuzz.partial_ratio(query_norm, vendor_norm)
    if ratio >= threshold:
        return True, float(ratio), "fuzzy"
    
    # Phonetic match
    phonetic_score = phonetic_similarity(query_norm, vendor_norm)
    if phonetic_score >= 70:
        return True, phonetic_score, "phonetic"
    
    # Embedding match
    embedding_score = embedding_similarity(query_industry, vendor_industry)
    if embedding_score >= 60:
        return True, embedding_score, "embedding"
    
    return False, max(ratio, phonetic_score, embedding_score), "no_match"

