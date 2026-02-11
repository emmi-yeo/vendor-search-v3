from rapidfuzz import fuzz, process
from typing import List, Dict, Tuple

# Normalization dictionary for common abbreviations and variations
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
    """Normalize text using the normalization dictionary."""
    text_lower = text.lower().strip()
    for key, value in NORMALIZATION_DICT.items():
        if key in text_lower:
            text_lower = text_lower.replace(key, value)
    return text_lower

def fuzzy_match_certification(query_cert: str, vendor_certs: str, threshold: int = 80) -> Tuple[bool, float]:
    """Fuzzy match certification query against vendor certifications."""
    if not vendor_certs:
        return False, 0.0
    
    vendor_certs_lower = vendor_certs.lower()
    query_normalized = normalize_text(query_cert)
    
    # Try exact match first
    if query_normalized in vendor_certs_lower:
        return True, 100.0
    
    # Try fuzzy match
    certs_list = [c.strip() for c in vendor_certs.split("|") if c.strip()]
    best_match = process.extractOne(query_normalized, certs_list, scorer=fuzz.partial_ratio)
    
    if best_match and best_match[1] >= threshold:
        return True, best_match[1]
    
    return False, 0.0

def fuzzy_match_vendor_name(query_name: str, vendor_name: str, threshold: int = 85) -> Tuple[bool, float]:
    """Fuzzy match vendor name."""
    if not vendor_name:
        return False, 0.0
    
    ratio = fuzz.ratio(query_name.lower(), vendor_name.lower())
    return ratio >= threshold, ratio

def fuzzy_match_industry(query_industry: str, vendor_industry: str, threshold: int = 80) -> Tuple[bool, float]:
    """Fuzzy match industry."""
    if not vendor_industry:
        return False, 0.0
    
    query_norm = normalize_text(query_industry)
    vendor_norm = normalize_text(vendor_industry)
    
    ratio = fuzz.partial_ratio(query_norm, vendor_norm)
    return ratio >= threshold, ratio

