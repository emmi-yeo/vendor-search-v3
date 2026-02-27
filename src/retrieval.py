import numpy as np
import faiss
from src.fuzzy_matching import (
    fuzzy_match_certification,
    fuzzy_match_vendor_name, 
    fuzzy_match_industry,
    normalize_text as fuzzy_normalize,
    match_with_fallback
)
from src.synonym_indexer import get_indexer as get_synonym_indexer
from src.boolean_filter_parser import BooleanFilterParser

CAPABILITY_KEYWORDS = {
    "SOC": ["soc", "siem", "security operations", "splunk", "qradar", "monitoring"],
    "OT_SECURITY": ["ot security", "operational technology", "critical infrastructure", "scada", "ics"],
    "AUDIT_COMPLIANCE": ["audit", "compliance", "risk assessment", "iso27001", "regulatory"]
}

# Score shaping weights (tune for your POC)
WEIGHTS = {
    "vec": 0.55,
    "lex": 0.18,
    "capability_boost": 0.15,
    "cert_boost": 0.10,
    "industry_match_boost": 0.15,
    "industry_mismatch_penalty": 0.35,
    "location_mismatch_penalty": 0.50,
    "cert_mismatch_penalty": 0.40,
    "performance_boost": 0.20,
    "compliance_boost": 0.15,
    "attachment_boost": 0.12,  # Boost when attachment content matches
}

MIN_DISPLAY_SCORE = 0.35   # hide super-weak matches
CLAMP_MIN = 0.0            # displayed scores never negative

def norm(s: str) -> str:
    return " ".join(str(s).lower().strip().split())

LOCATION_ALIASES = {
    "wp kuala lumpur": {"kuala lumpur", "wilayah persekutuan kuala lumpur", "wp kl", "kl"},
    "kuala lumpur": {"wp kuala lumpur", "wilayah persekutuan kuala lumpur", "wp kl", "kl"},
}


def apply_filters_with_logic(meta: list[dict], filters: dict, constraints: dict, logic_operators: dict) -> list[int]:
    """Apply filters with AND/OR logic operators."""
    inds = []
    inds_wanted_industry = set([x.lower() for x in filters.get("industry", []) if x])
    inds_wanted_certs = set([x.lower() for x in filters.get("certifications", []) if x])
    loc = filters.get("location", {}) or {}
    industry_strict = bool(constraints.get("industry_strict", False))
    location_strict = bool(constraints.get("location_strict", False))
    certs_strict = bool(constraints.get("certifications_strict", False))
    country = norm(loc.get("country") or "")
    states = set([norm(s) for s in (loc.get("state") or []) if s])
    cities = set([norm(c) for c in (loc.get("city") or []) if c])
    
    industry_op = logic_operators.get("industry", "AND")  # Default to AND
    location_op = logic_operators.get("location", "AND")
    certs_op = logic_operators.get("certifications", "AND")

    for i, m in enumerate(meta):
        ok = True

        # Industry with AND/OR logic
        if inds_wanted_industry and industry_strict:
            vendor_ind = m["industry"].lower()
            if industry_op == "OR":
                # Match if ANY industry matches
                ok = ok and any(t.strip() in vendor_ind for t in inds_wanted_industry)
            else:  # AND (default)
                # Match if ALL industries match (for multiple industries)
                ok = ok and all(t.strip() in vendor_ind for t in inds_wanted_industry) if len(inds_wanted_industry) > 1 else any(t.strip() in vendor_ind for t in inds_wanted_industry)

        # Location with AND/OR logic
        if location_strict:
            m_country = norm(m.get("country", ""))
            m_state = norm(m.get("state", ""))
            m_city = norm(m.get("city", ""))
            
            location_matches = []
            
            if country:
                location_matches.append(m_country == country)
            if states:
                ok_state = (m_state in states)
                if not ok_state:
                    vendor_aliases = LOCATION_ALIASES.get(m_state, set())
                    ok_state = any(s in vendor_aliases for s in states)
                location_matches.append(ok_state)
            if cities:
                ok_city = (m_city in cities)
                if not ok_city:
                    vendor_aliases = LOCATION_ALIASES.get(m_city, set())
                    ok_city = any(c in vendor_aliases for c in cities)
                location_matches.append(ok_city)
            
            if location_matches:
                if location_op == "OR":
                    ok = ok and any(location_matches)
                else:  # AND
                    ok = ok and all(location_matches)

        # Certifications with AND/OR logic
        if inds_wanted_certs and certs_strict:
            cert_blob = m["certifications"].lower()
            if certs_op == "OR":
                # Match if ANY certification matches
                ok = ok and any(c in cert_blob for c in inds_wanted_certs)
            else:  # AND (default)
                # Match if ALL certifications match
                ok = ok and all(c in cert_blob for c in inds_wanted_certs)

        if ok:
            inds.append(i)

    return inds

def apply_filters(meta: list[dict], filters: dict, constraints: dict) -> list[int]:
    inds = []
    inds_wanted_industry = set([x.lower() for x in filters.get("industry", []) if x])
    inds_wanted_certs = set([x.lower() for x in filters.get("certifications", []) if x])
    loc = filters.get("location", {}) or {}
    industry_strict = bool(constraints.get("industry_strict", False))
    location_strict = bool(constraints.get("location_strict", False))
    certs_strict = bool(constraints.get("certifications_strict", False))
    country = norm(loc.get("country") or "")
    states = set([norm(s) for s in (loc.get("state") or []) if s])
    cities = set([norm(c) for c in (loc.get("city") or []) if c])

    # 🆕 Boolean filter support: Check if there's a Boolean expression in query
    boolean_expr = filters.get("boolean_expression", "")
    if boolean_expr:
        try:
            parser = BooleanFilterParser()
            matching_indices, errors = parser.filter_vendors(boolean_expr, meta)
            if errors:
                # Log errors but still attempt to filter with fallback logic
                pass
            return matching_indices
        except Exception as e:
            # Fallback to traditional filtering if Boolean parsing fails
            pass

    for i, m in enumerate(meta):
        ok = True

        # Industry (strict means must match; non-strict means we allow but will rank-penalize later)
        if inds_wanted_industry and industry_strict:
            ok = ok and any(t.strip() in m["industry"].lower() for t in inds_wanted_industry)

        # Location (strict means must match)
        if location_strict:
            m_country = norm(m.get("country", ""))
            m_state = norm(m.get("state", ""))
            m_city = norm(m.get("city", ""))

            # country strict
            if country:
                ok = ok and (m_country == country)

            # state strict with alias support
            if states:
                ok_state = (m_state in states)
                if not ok_state:
                    # alias match: if vendor state has aliases intersecting query states
                    vendor_aliases = LOCATION_ALIASES.get(m_state, set())
                    ok_state = any(s in vendor_aliases for s in states)
                ok = ok and ok_state

            # city strict with alias support
            if cities:
                ok_city = (m_city in cities)
                if not ok_city:
                    vendor_aliases = LOCATION_ALIASES.get(m_city, set())
                    ok_city = any(c in vendor_aliases for c in cities)
                ok = ok and ok_city

            # Extra: if user provided "Kuala Lumpur" but it landed in state,
            # allow it to match vendor city/state interchangeably
            if states and not cities:
                # treat state query as possibly city query too
                ok = ok and (m_state in states or m_city in states or any(s in LOCATION_ALIASES.get(m_state, set()) for s in states))


        # Certifications (strict means must include all) - with fuzzy matching fallback
        if inds_wanted_certs and certs_strict:
            cert_blob = m["certifications"].lower()
            cert_list = [c.strip() for c in m["certifications"].split("|") if c.strip()]
            
            # Check if all wanted certs match (using fuzzy matching with fallback)
            all_match = True
            for wanted_cert in inds_wanted_certs:
                # Try fuzzy match with fallback
                match, score, method = match_with_fallback(
                    wanted_cert,
                    cert_list,
                    threshold=75,
                    phonetic_threshold=70,
                    embedding_threshold=60
                )
                
                if match is None:
                    # No match found even with fallback, fail the filter
                    all_match = False
                    break
            
            ok = ok and all_match

        if ok:
            inds.append(i)

    return inds

def get_allowed_with_relaxation(meta, filters, constraints, logic_operators=None):
    """
    Try strict constraints first.
    If empty, relax in this order:
      1) capabilities strict (not used in filter, but included for reporting consistency)
      2) certifications strict
      3) location strict
      4) industry strict
    Return (allowed_indices, used_constraints, did_relax)
    """
    # Start with full constraints
    c = dict(constraints or {})
    if logic_operators:
        allowed = apply_filters_with_logic(meta, filters, c, logic_operators)
    else:
        allowed = apply_filters(meta, filters, c)
    if allowed:
        return allowed, c, False

    # Relax certs -> location -> industry (capability strict doesn't affect apply_filters)
    for key in ["certifications_strict", "location_strict", "industry_strict"]:
        if c.get(key, False):
            c[key] = False
            if logic_operators:
                allowed = apply_filters_with_logic(meta, filters, c, logic_operators)
            else:
                allowed = apply_filters(meta, filters, c)
            if allowed:
                return allowed, c, True

    return [], c, False

def calculate_performance_score(vendor_meta: dict, performance_query: dict, all_vendors_meta: list):
    """Calculate performance score and return (score, reasons)."""
    if not performance_query or not performance_query.get("type"):
        return 0.0, []
    
    reasons = []
    score = 0.0
    
    if performance_query["type"] == "top_by_spend":
        # Normalize by max spend across all vendors
        max_spend = max([m.get("total_spend", 0) for m in all_vendors_meta], default=1.0)
        if max_spend > 0:
            normalized_spend = vendor_meta.get("total_spend", 0) / max_spend
            score = normalized_spend * WEIGHTS["performance_boost"]
            if normalized_spend > 0.5:
                reasons.append(f"High total spend: ${vendor_meta.get('total_spend', 0):,.0f}")
    
    elif performance_query["type"] == "by_transaction_volume":
        max_count = max([m.get("transaction_count", 0) for m in all_vendors_meta], default=1.0)
        if max_count > 0:
            normalized_count = vendor_meta.get("transaction_count", 0) / max_count
            score = normalized_count * WEIGHTS["performance_boost"]
            if normalized_count > 0.5:
                reasons.append(f"High transaction volume: {vendor_meta.get('transaction_count', 0)} transactions")
    
    elif performance_query["type"] == "by_date_range":
        # Boost if has recent transactions
        if vendor_meta.get("latest_transaction_date"):
            reasons.append(f"Recent activity: {vendor_meta.get('latest_transaction_date', '')}")
            score = WEIGHTS["performance_boost"] * 0.5
    
    return score, reasons

def calculate_compliance_score(vendor_meta: dict, compliance_query: dict):
    """Calculate compliance score and return (score, reasons)."""
    if not compliance_query:
        return 0.0, []
    
    reasons = []
    score = 0.0
    certs = (vendor_meta.get("certifications", "") or "").lower()
    
    # Check for required certifications
    required = compliance_query.get("required_certifications", [])
    if required:
        found = [c for c in required if c.lower() in certs]
        if found:
            score += WEIGHTS["compliance_boost"] * (len(found) / len(required))
            reasons.append(f"Has required certifications: {', '.join(found)}")
    
    # General certification boost
    if certs and ("iso" in certs or "cert" in certs):
        cert_count = len([x for x in certs.split("|") if x.strip()])
        if cert_count > 0:
            score += WEIGHTS["cert_boost"]
            reasons.append(f"Certified: {cert_count} certification(s)")
    
    return score, reasons

def calculate_standalone_scores(vendor_meta: dict, all_vendors_meta: list) -> dict:
    """Calculate standalone compliance, risk, and performance scores (0-1 scale)."""
    scores = {
        "compliance_score": 0.0,
        "risk_score": 0.0,
        "performance_score": 0.0
    }
    
    # Compliance score: based on certifications
    certs = (vendor_meta.get("certifications", "") or "").lower()
    if certs:
        cert_count = len([x for x in certs.split("|") if x.strip()])
        # Normalize: assume max 5 certs = 1.0
        scores["compliance_score"] = min(1.0, cert_count / 5.0)
    
    # Risk score: inverse of compliance (higher compliance = lower risk)
    scores["risk_score"] = 1.0 - scores["compliance_score"]
    
    # Performance score: based on transaction metrics
    max_spend = max([m.get("total_spend", 0) for m in all_vendors_meta], default=1.0)
    max_count = max([m.get("transaction_count", 0) for m in all_vendors_meta], default=1.0)
    
    if max_spend > 0:
        spend_norm = min(1.0, vendor_meta.get("total_spend", 0) / max_spend)
    else:
        spend_norm = 0.0
    
    if max_count > 0:
        count_norm = min(1.0, vendor_meta.get("transaction_count", 0) / max_count)
    else:
        count_norm = 0.0
    
    # Combine spend and transaction count (weighted average)
    scores["performance_score"] = (spend_norm * 0.6 + count_norm * 0.4)
    
    return scores

def search(index, bm25, docs, meta, query_text: str, filters: dict, constraints: dict, capabilities: list[str], embed_model: str, top_k: int = 8, performance_query: dict = None, compliance_query: dict = None, logic_operators: dict = None):
    allowed, used_constraints, did_relax = get_allowed_with_relaxation(meta, filters, constraints, logic_operators)

    has_any_strict = any(bool((constraints or {}).get(k, False)) for k in [
        "industry_strict", "location_strict", "certifications_strict", "capabilities_strict"
    ])

    # Only global fallback if we truly have ZERO candidates even after relaxation.
    if not allowed:
        return [], True, False
    else:
        # If we found candidates under strict or relaxed constraints, DO NOT global fallback.
        filter_warning = did_relax
        constraints = used_constraints

    from src.local_embedder import embed_text
    vec = embed_text(query_text)
    qv = np.array([vec], dtype="float32")

    faiss.normalize_L2(qv)

    # search more broadly then prune to allowed
    D, I = index.search(qv, min(len(meta), 50))
    candidates = []
    for score, idx in zip(D[0], I[0]):
        if int(idx) in allowed:
            candidates.append((int(idx), float(score)))

    # 🔄 Synonym expansion for BM25 (before tokenization)
    # Expand query with related synonyms to improve lexical matching
    try:
        indexer = get_synonym_indexer()
        expanded_query = indexer.expand_query(query_text)
        bm25_query_tokens = expanded_query.lower().split()
    except Exception:
        # Fallback to original query if expansion fails
        bm25_query_tokens = query_text.lower().split()

    # lexical boost with expanded query
    bm25_scores = bm25.get_scores(bm25_query_tokens)
    bm25_max = max(bm25_scores) if len(bm25_scores) else 1.0

    # Prepare requested constraints for scoring signals (soft if not strict)
    req_industries = set([x.lower() for x in (filters.get("industry") or []) if x])
    req_certs = set([x.lower() for x in (filters.get("certifications") or []) if x])

    loc = filters.get("location", {}) or {}
    req_country = (loc.get("country") or "").lower().strip()
    req_states = set([s.lower() for s in (loc.get("state") or [])])
    req_cities = set([c.lower() for c in (loc.get("city") or [])])

    cap_set = set([c.strip().upper() for c in (capabilities or [])])

    results = []
    for idx, vec_score in candidates[: top_k * 5]:
        doc_text = docs[idx].lower()
        m = meta[idx]

        lex = float(bm25_scores[idx] / (bm25_max + 1e-9))
        final = WEIGHTS["vec"] * vec_score + WEIGHTS["lex"] * lex
        ranking_reasons = []

        # --- Capability boost (SOC / OT_SECURITY / AUDIT_COMPLIANCE) ---
        cap_hits = 0
        for cap in cap_set:
            for kw in CAPABILITY_KEYWORDS.get(cap, []):
                if kw in doc_text:
                    cap_hits += 1
                    break
        if cap_set and cap_hits > 0:
            boost = WEIGHTS["capability_boost"] * min(1.0, cap_hits / max(1, len(cap_set)))
            final += boost
            ranking_reasons.append(f"Matches {cap_hits}/{len(cap_set)} requested capabilities")

        # --- Industry match/mismatch (soft scoring) ---
        if req_industries:
            vendor_ind = (m.get("industry","") or "").lower()
            if any(ri in vendor_ind for ri in req_industries):
                final += WEIGHTS["industry_match_boost"]
                ranking_reasons.append(f"Industry match: {m.get('industry', '')}")
            else:
                # penalize mismatch heavily if user asked explicitly (strict or not)
                final -= WEIGHTS["industry_mismatch_penalty"]

        # --- Certifications soft scoring / penalty (with fuzzy matching) ---
        if req_certs:
            cert_blob = m.get("certifications", "") or ""
            cert_ok = True
            fuzzy_matches = []
            for rc in req_certs:
                matched, score = fuzzy_match_certification(rc, cert_blob)
                if not matched:
                    cert_ok = False
                else:
                    fuzzy_matches.append((rc, score))
            
            if cert_ok:
                final += WEIGHTS["cert_boost"]
                if fuzzy_matches and any(score < 100 for _, score in fuzzy_matches):
                    ranking_reasons.append("Has requested certifications (fuzzy matched)")
                else:
                    ranking_reasons.append("Has requested certifications")
            else:
                # if certifications were explicitly strict, punish harder
                if constraints.get("certifications_strict", False):
                    final -= WEIGHTS["cert_mismatch_penalty"] * 1.2
                else:
                    final -= WEIGHTS["cert_mismatch_penalty"] * 0.6

        # --- Location soft penalty if user explicitly set location ---
        if constraints.get("location_strict", False):
            # strict should already filter, but if fallback happened, penalize mismatches
            if req_country and (m.get("country","").lower().strip() != req_country):
                final -= WEIGHTS["location_mismatch_penalty"]
            if req_states and (m.get("state","").lower().strip() not in req_states):
                final -= WEIGHTS["location_mismatch_penalty"] * 0.7
            if req_cities and (m.get("city","").lower().strip() not in req_cities):
                final -= WEIGHTS["location_mismatch_penalty"] * 0.5
            else:
                ranking_reasons.append(f"Location match: {m.get('city', '')}, {m.get('state', '')}")

        # --- Performance scoring ---
        perf_score, perf_reasons = calculate_performance_score(m, performance_query or {}, meta)
        final += perf_score
        ranking_reasons.extend(perf_reasons)

        # --- Compliance scoring ---
        comp_score, comp_reasons = calculate_compliance_score(m, compliance_query or {})
        final += comp_score
        ranking_reasons.extend(comp_reasons)

        # --- Attachment matching boost ---
        matched_attachments = []
        attachments = m.get("attachments", [])
        query_lower = query_text.lower()
        for att in attachments:
            att_text = (att.get("text", "") or "").lower()
            att_name = (att.get("name", "") or "").lower()
            # Check if query keywords appear in attachment
            query_words = set(query_lower.split())
            att_words = set((att_text + " " + att_name).split())
            if query_words.intersection(att_words):
                matched_attachments.append(att.get("name", "Unknown"))
                final += WEIGHTS["attachment_boost"] * 0.5  # Partial boost per match
        
        if matched_attachments:
            ranking_reasons.append(f"Matches in attachments: {', '.join(matched_attachments[:2])}")

        results.append((final, vec_score, lex, idx, cap_hits, ranking_reasons, matched_attachments))


        results.sort(reverse=True, key=lambda x: x[0])

        payload = []
        for result_item in results:
            if len(result_item) >= 7:
                final, vec_score, lex, idx, cap_hits, ranking_reasons, matched_attachments = result_item[:7]
            elif len(result_item) == 6:
                final, vec_score, lex, idx, cap_hits, ranking_reasons = result_item
                matched_attachments = []
            else:
                # Backward compatibility
                final, vec_score, lex, idx, cap_hits = result_item[:5]
                ranking_reasons = []
                matched_attachments = []
            # clamp displayed score
            display_score = max(CLAMP_MIN, final)
            display_score = min(1.0, display_score)

            # hide weak matches
            if display_score < MIN_DISPLAY_SCORE:
                continue

            m = meta[idx]
            # determine exactness (based on STRICT constraints only)
            is_exact = True

            # Industry strict
            if constraints.get("industry_strict", False) and req_industries:
                vendor_ind = (m.get("industry","") or "").lower()
                is_exact = is_exact and any(ri in vendor_ind for ri in req_industries)

            # Location strict
            if constraints.get("location_strict", False):
                if req_country and norm(m.get("country","")) != req_country:
                    is_exact = False
                if req_states and norm(m.get("state","")) not in req_states:
                    is_exact = False
                if req_cities and norm(m.get("city","")) not in req_cities:
                    is_exact = False

            # Certifications strict
            if constraints.get("certifications_strict", False) and req_certs:
                cert_blob = (m.get("certifications","") or "").lower()
                is_exact = is_exact and all(rc in cert_blob for rc in req_certs)

            # Calculate standalone scores
            standalone_scores = calculate_standalone_scores(m, meta)
            
            payload.append({
                "vendor_id": m["vendor_id"],
                "vendor_name": m["vendor_name"],
                "final_score": round(display_score, 4),
                "vector": round(vec_score, 4),
                "lexical": round(lex, 4),
                "cap_hits": int(cap_hits),
                "industry": m["industry"],
                "location": f"{m['country']} / {m['state']} / {m['city']}",
                "certifications": m["certifications"],
                "is_exact_match": bool(is_exact),
                "evidence_preview": docs[idx][:260] + "...",
                "ranking_reasons": ranking_reasons[:3] if ranking_reasons else [],  # Top 3 reasons
                "total_spend": m.get("total_spend", 0),
                "transaction_count": m.get("transaction_count", 0),
                "matched_attachments": matched_attachments[:3] if matched_attachments else [],  # Top 3 matched attachments
                "compliance_score": round(standalone_scores["compliance_score"], 3),
                "risk_score": round(standalone_scores["risk_score"], 3),
                "performance_score": round(standalone_scores["performance_score"], 3)
            })

            if len(payload) >= top_k:
                break


    # Confidence control: if top score is strong, reduce noise
    # You can tune these thresholds.
    show_only_top = False
    if payload:
        top = payload[0]["final_score"]
        if top >= 0.85 and len(payload) >= 1:
            show_only_top = True
            payload = payload[:3]

    return payload, filter_warning, show_only_top

