"""
Synonym Indexer Module

Builds an inverted index from taxonomy data for query expansion.
Used before BM25 tokenization to expand search queries with synonyms.

Example:
    "Find SOC vendors" + synonym_indexer
    → "Find security operations center vendors soc monitoring security operations"
"""

import json
import os
from typing import Dict, List, Set


class SynonymIndexer:
    """Build and query synonym/capability index from taxonomy."""
    
    def __init__(self):
        """Initialize indexer and load taxonomy files."""
        self.abbreviations = {}
        self.multilingual = {}
        self.industry_synonyms = {}
        self.certification_synonyms = {}
        self.capability_index = {}
        
        self._load_taxonomies()
        self._build_capability_index()
    
    def _load_taxonomies(self):
        """Load all taxonomy files."""
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        taxonomy_path = os.path.join(base_path, "data", "taxonomy")
        
        # Load abbreviations
        try:
            with open(os.path.join(taxonomy_path, "abbreviations.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
                for abbr, info in data.items():
                    self.abbreviations[abbr.lower()] = {
                        "full_forms": info.get("full_forms", []),
                        "synonyms": info.get("synonyms", []),
                        "domain": info.get("domain", "")
                    }
        except Exception as e:
            print(f"Warning: Could not load abbreviations: {e}")
        
        # Load multilingual terms
        try:
            with open(os.path.join(taxonomy_path, "multilingual_terms.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
                self.multilingual = data
        except Exception as e:
            print(f"Warning: Could not load multilingual terms: {e}")
        
        # Load industry tree
        try:
            with open(os.path.join(taxonomy_path, "industry_tree.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
                for industry, info in data.get("industries", {}).items():
                    self.industry_synonyms[industry.lower()] = {
                        "synonyms": info.get("synonyms", []),
                        "related": info.get("related", [])
                    }
        except Exception as e:
            print(f"Warning: Could not load industry tree: {e}")
        
        # Load certifications
        try:
            with open(os.path.join(taxonomy_path, "certification_aliases.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
                for cert_key, cert_info in data.get("certifications", {}).items():
                    self.certification_synonyms[cert_key.lower()] = {
                        "primary": cert_info.get("primary", ""),
                        "formats": cert_info.get("formats", []),
                        "synonyms": cert_info.get("synonyms", [])
                    }
        except Exception as e:
            print(f"Warning: Could not load certifications: {e}")
    
    def _build_capability_index(self):
        """Build capability index from abbreviations and hardcoded capabilities."""
        # From retrieval.py CAPABILITY_KEYWORDS
        hardcoded_capabilities = {
            "SOC": ["soc", "siem", "security operations", "splunk", "qradar", "monitoring"],
            "OT_SECURITY": ["ot security", "operational technology", "critical infrastructure"],
            "AUDIT_COMPLIANCE": ["audit", "compliance", "risk assessment", "iso27001"]
        }
        
        # Add capability keywords
        for capability, keywords in hardcoded_capabilities.items():
            self.capability_index[capability.lower()] = {
                "keywords": keywords,
                "type": "capability"
            }
        
        # Add abbreviations from taxonomy as capabilities
        for abbr, info in self.abbreviations.items():
            if info.get("domain") in ["cybersecurity", "compliance", "business"]:
                full_forms = info.get("full_forms", [])
                if full_forms:
                    self.capability_index[abbr] = {
                        "keywords": full_forms + info.get("synonyms", []),
                        "type": "abbreviation"
                    }
    
    def expand_query(self, query: str) -> str:
        """
        Expand query with synonyms and related terms.
        
        Args:
            query: Original user query
        
        Returns:
            Expanded query with additional search terms
        """
        expanded_terms = set(query.lower().split())
        
        # Expand abbreviations
        for abbr, info in self.abbreviations.items():
            if abbr in query.lower():
                expanded_terms.update(info.get("full_forms", []))
                expanded_terms.update(info.get("synonyms", []))
        
        # Expand multilingual terms
        for malay_term, info in self.multilingual.items():
            if malay_term.lower() in query.lower():
                expanded_terms.add(info.get("english", ""))
                expanded_terms.update(info.get("variants", []))
        
        # Expand industry synonyms
        for industry, info in self.industry_synonyms.items():
            if industry in query.lower():
                expanded_terms.update(info.get("synonyms", []))
                expanded_terms.update(info.get("related", []))
        
        # Expand certification synonyms
        for cert, info in self.certification_synonyms.items():
            if cert in query.lower():
                expanded_terms.add(info.get("primary", ""))
                expanded_terms.update(info.get("formats", []))
                expanded_terms.update(info.get("synonyms", []))
        
        # Expand hardware keywords
        for capability, info in self.capability_index.items():
            if capability in query.lower():
                expanded_terms.update(info.get("keywords", []))
        
        # Build expanded query (remove empty strings and duplicates)
        expanded_list = [
            term.strip() for term in expanded_terms
            if term.strip() and len(term.strip()) > 1
        ]
        
        # Return original query + expanded terms
        return query + " " + " ".join(sorted(set(expanded_list)))
    
    def get_related_terms(self, term: str, expand_type: str = "all") -> List[str]:
        """
        Get related terms for a given search term.
        
        Args:
            term: Search term
            expand_type: "abbr", "industry", "cert", "multilingual", or "all"
        
        Returns:
            List of related terms
        """
        term_lower = term.lower()
        related = []
        
        if expand_type in ["abbr", "all"]:
            if term_lower in self.abbreviations:
                info = self.abbreviations[term_lower]
                related.extend(info.get("full_forms", []))
                related.extend(info.get("synonyms", []))
        
        if expand_type in ["industry", "all"]:
            if term_lower in self.industry_synonyms:
                info = self.industry_synonyms[term_lower]
                related.extend(info.get("synonyms", []))
                related.extend(info.get("related", []))
        
        if expand_type in ["cert", "all"]:
            if term_lower in self.certification_synonyms:
                info = self.certification_synonyms[term_lower]
                related.extend(info.get("formats", []))
                related.extend(info.get("synonyms", []))
        
        if expand_type in ["multilingual", "all"]:
            if term_lower in self.multilingual:
                info = self.multilingual[term_lower]
                related.append(info.get("english", ""))
                related.extend(info.get("variants", []))
        
        # Remove duplicates and empty strings
        return list(set([r.strip() for r in related if r.strip()]))
    
    def get_capability_keywords(self, capability: str) -> List[str]:
        """Get all keywords associated with a capability."""
        capability_lower = capability.lower()
        if capability_lower in self.capability_index:
            return self.capability_index[capability_lower].get("keywords", [])
        return []
    
    def build_inverted_index(self) -> Dict[str, List[str]]:
        """
        Build complete inverted index: term → [synonyms, related].
        Useful for pre-building search optimizations.
        
        Returns:
            Dictionary mapping terms to list of synonyms/related
        """
        index = {}
        
        # Add abbreviations
        for abbr, info in self.abbreviations.items():
            if abbr not in index:
                index[abbr] = []
            index[abbr].extend(info.get("full_forms", []))
            index[abbr].extend(info.get("synonyms", []))
        
        # Add industries
        for industry, info in self.industry_synonyms.items():
            if industry not in index:
                index[industry] = []
            index[industry].extend(info.get("synonyms", []))
            index[industry].extend(info.get("related", []))
        
        # Add certifications
        for cert, info in self.certification_synonyms.items():
            if cert not in index:
                index[cert] = []
            index[cert].extend(info.get("formats", []))
            index[cert].extend(info.get("synonyms", []))
        
        # Remove duplicates
        for key in index:
            index[key] = list(set(index[key]))
        
        return index


# Global singleton instance
_indexer_instance = None

def get_indexer() -> SynonymIndexer:
    """Get or create global synonym indexer instance."""
    global _indexer_instance
    if _indexer_instance is None:
        _indexer_instance = SynonymIndexer()
    return _indexer_instance
