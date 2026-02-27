import json
import os
import re
from typing import Dict, List, Tuple
from src.azure_llm import azure_chat as groq_chat

# Load taxonomy files on module initialization
def _load_taxonomy():
    """Load all taxonomy files into memory."""
    taxonomy = {}
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    taxonomy_path = os.path.join(base_path, "data", "taxonomy")
    
    try:
        with open(os.path.join(taxonomy_path, "abbreviations.json"), "r", encoding="utf-8") as f:
            taxonomy["abbreviations"] = json.load(f)
    except Exception as e:
        print(f"Warning: Could not load abbreviations.json: {e}")
        taxonomy["abbreviations"] = {}
    
    try:
        with open(os.path.join(taxonomy_path, "multilingual_terms.json"), "r", encoding="utf-8") as f:
            taxonomy["multilingual"] = json.load(f)
    except Exception as e:
        print(f"Warning: Could not load multilingual_terms.json: {e}")
        taxonomy["multilingual"] = {}
    
    try:
        with open(os.path.join(taxonomy_path, "industry_tree.json"), "r", encoding="utf-8") as f:
            taxonomy["industry"] = json.load(f)
    except Exception as e:
        print(f"Warning: Could not load industry_tree.json: {e}")
        taxonomy["industry"] = {}
    
    try:
        with open(os.path.join(taxonomy_path, "certification_aliases.json"), "r", encoding="utf-8") as f:
            taxonomy["certifications"] = json.load(f)
    except Exception as e:
        print(f"Warning: Could not load certification_aliases.json: {e}")
        taxonomy["certifications"] = {}
    
    return taxonomy

TAXONOMY = _load_taxonomy()


def detect_mixed_language(text: str) -> bool:
    """
    Detect if text contains mixed Malay and English.
    Returns True if mixed language detected.
    """
    # Common Malay words
    malay_keywords = [
        "dan", "atau", "dengan", "untuk", "dari", "ke", "di", "yang",
        "ini", "itu", "ada", "tidak", "ya", "boleh", "cari", "carilah",
        "keamanan", "kepatuhan", "manajemen", "layanan", "sistem",
        "vendor", "perusahaan", "solusi", "pemantauan"
    ]
    
    text_lower = text.lower()
    malay_count = sum(1 for word in malay_keywords if f" {word} " in f" {text_lower} " or text_lower.startswith(word + " "))
    
    # If has both Malay words and English (ISO, cybersecurity, etc.), it's mixed
    has_english_tech = any(term in text_lower for term in ["iso", "cybersecurity", "emc", "erp", "soc", "audit"])
    
    return malay_count > 0 and has_english_tech


def expand_abbreviations(text: str) -> str:
    """
    Expand common procurement abbreviations using taxonomy.
    Example: "BM software" -> "business management software"
    """
    if not TAXONOMY.get("abbreviations"):
        return text
    
    result = text
    abbreviations = TAXONOMY["abbreviations"]
    
    # Sort by length (longest first) to avoid partial replacements
    sorted_abbrs = sorted(abbreviations.items(), key=lambda x: len(x[0]), reverse=True)
    
    for abbr, data in sorted_abbrs:
        # Match whole words only (case-insensitive)
        pattern = r'\b' + re.escape(abbr) + r'\b'
        
        if re.search(pattern, result, re.IGNORECASE):
            # Get primary expansion (first full form)
            primary = data.get("full_forms", [abbr])[0] if data.get("full_forms") else abbr
            # Replace with expansion + original abbr for clarity
            replacement = f"{primary} ({abbr})"
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


def normalize_multilingual(text: str) -> str:
    """
    Normalize Malay technical terms to English using taxonomy.
    Example: "keamanan siber" -> "cybersecurity"
    """
    if not TAXONOMY.get("multilingual"):
        return text
    
    result = text
    multilingual_dict = TAXONOMY["multilingual"]
    
    # Sort by length (longest first) to avoid partial replacements
    sorted_terms = sorted(multilingual_dict.items(), key=lambda x: len(x[0]), reverse=True)
    
    for malay_term, data in sorted_terms:
        if malay_term.lower() in text.lower():
            english_term = data.get("english", "")
            if english_term:
                # Case-insensitive replacement
                pattern = r'\b' + re.escape(malay_term) + r'\b'
                result = re.sub(pattern, english_term, result, flags=re.IGNORECASE)
    
    return result


def normalize_certification(text: str) -> str:
    """
    Normalize certification names to standard formats using taxonomy.
    Example: "ISO 27001" -> "ISO27001", "ISO-27001" -> "ISO27001"
    """
    if not TAXONOMY.get("certifications"):
        return text
    
    result = text
    certifications = TAXONOMY.get("certifications", {}).get("certifications", {})
    
    for cert_key, cert_data in certifications.items():
        primary = cert_data.get("primary", "")
        formats = cert_data.get("formats", [])
        
        # Replace all format variations with primary format
        for fmt in formats:
            if fmt != primary:
                pattern = r'\b' + re.escape(fmt) + r'\b'
                result = re.sub(pattern, primary, result, flags=re.IGNORECASE)
    
    return result


def get_abbreviation_suggestions(text: str) -> List[str]:
    """
    Find all abbreviations in text that could be expanded.
    Returns list of found abbreviations with their expansions.
    """
    if not TAXONOMY.get("abbreviations"):
        return []
    
    suggestions = []
    abbreviations = TAXONOMY["abbreviations"]
    text_upper = text.upper()
    
    for abbr, data in abbreviations.items():
        if abbr in text_upper:
            primary = data.get("full_forms", [abbr])[0]
            suggestions.append(f"{abbr} → {primary}")
    
    return suggestions


def translate_query_to_english(user_text: str) -> str:
    """
    Translate Malay / mixed-language procurement queries into clear English,
    preserving vendor names, certifications, acronyms, and intent.
    
    Pipeline:
    1. Detect mixed language
    2. Normalize Malay terms to English
    3. Expand abbreviations
    4. Normalize certifications
    5. Use LLM as final pass if needed
    """
    
    # Step 1: Detect if mixed language
    is_mixed = detect_mixed_language(user_text)
    
    # Step 2-4: Apply preprocessing
    result = user_text
    
    # Normalize multilingual terms
    if is_mixed or any(term in user_text.lower() for term in TAXONOMY.get("multilingual", {}).keys()):
        result = normalize_multilingual(result)
    
    # Expand abbreviations
    result = expand_abbreviations(result)
    
    # Normalize certifications
    result = normalize_certification(result)
    
    # Step 5: LLM translation as final pass (to fix grammar, add context)
    if result != user_text or is_mixed:
        system_prompt = (
            "You are a procurement search assistant.\n"
            "Polish the provided query into clear, natural English while preserving all technical terms.\n\n"
            "Rules:\n"
            "- Preserve vendor names exactly\n"
            "- Preserve certifications (ISO27001, SOC2, PCI-DSS, etc.)\n"
            "- Preserve acronyms and technical terms\n"
            "- Do NOT add new constraints\n"
            "- Do NOT explain\n"
            "- Output ONLY the polished query\n"
            "- If already in good English, return as-is\n"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": result},
        ]
        
        try:
            translated = groq_chat(messages, temperature=0)
            result = translated.strip()
        except Exception as e:
            print(f"LLM translation warning: {e}")
            # Fallback: return the preprocessed text
            pass
    
    return result


def get_query_preprocessing_info(text: str) -> Dict:
    """
    Return preprocessing information for debugging/transparency.
    Shows what was expanded/normalized in the query.
    """
    info = {
        "original": text,
        "is_mixed_language": detect_mixed_language(text),
        "abbreviations_found": [],
        "multilingual_found": [],
        "certifications_normalized": False
    }
    
    # Find abbreviations
    abbreviations = TAXONOMY.get("abbreviations", {})
    text_upper = text.upper()
    for abbr in abbreviations.keys():
        if abbr in text_upper:
            info["abbreviations_found"].append(abbr)
    
    # Find multilingual terms
    multilingual = TAXONOMY.get("multilingual", {})
    text_lower = text.lower()
    for term in multilingual.keys():
        if term in text_lower:
            info["multilingual_found"].append(term)
    
    # Check if certifications were normalized
    certifications = TAXONOMY.get("certifications", {}).get("certifications", {})
    text_check = text.lower()
    for cert_key, cert_data in certifications.items():
        formats = cert_data.get("formats", [])
        if any(fmt.lower() in text_check for fmt in formats):
            info["certifications_normalized"] = True
            break
    
    return info
