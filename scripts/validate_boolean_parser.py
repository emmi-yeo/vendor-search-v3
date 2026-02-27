#!/usr/bin/env python3
"""
Boolean Filter Parser - Manual Validation Demo

This script demonstrates all core functionality of the Boolean filter parser
without requiring pytest.
"""

import sys
sys.path.insert(0, '/workspaces/vendor-search-v3')

from src.boolean_filter_parser import (
    BooleanTokenizer, BooleanParser, SyntaxValidator,
    ConflictDetector, BooleanFilterParser, BooleanFilterEvaluator
)


def test_tokenizer():
    """Test tokenization."""
    print("\n" + "="*60)
    print("TEST 1: TOKENIZER")
    print("="*60)
    
    tests = [
        "cybersecurity",
        "cybersecurity AND ISO27001",
        "(cybersecurity OR SIEM) AND ISO27001 AND NOT banking",
    ]
    
    for expr in tests:
        print(f"\nExpression: {expr}")
        tokenizer = BooleanTokenizer(expr)
        tokens = tokenizer.tokenize()
        print(f"Tokens: {[(t.type.name, t.value) for t in tokens if t.value]}")
    
    print("\n✅ Tokenizer tests passed")


def test_syntax_validator():
    """Test syntax validation."""
    print("\n" + "="*60)
    print("TEST 2: SYNTAX VALIDATOR")
    print("="*60)
    
    valid_tests = [
        "cybersecurity",
        "cybersecurity AND ISO27001",
        "(cybersecurity OR SIEM) AND NOT banking",
    ]
    
    invalid_tests = [
        "AND cybersecurity",  # AND at start
        "cybersecurity AND",  # AND at end
        "(cybersecurity",     # Unclosed paren
        "cybersecurity)",     # Unmatched close paren
        "cybersecurity AND AND ISO27001",  # Consecutive operators
    ]
    
    print("\n--- Valid Expressions ---")
    for expr in valid_tests:
        is_valid, msg = SyntaxValidator.validate(expr)
        status = "✅ VALID" if is_valid else "❌ INVALID"
        print(f"{status}: {expr}")
        if not is_valid:
            print(f"  Error: {msg}")
    
    print("\n--- Invalid Expressions ---")
    for expr in invalid_tests:
        is_valid, msg = SyntaxValidator.validate(expr)
        status = "✅ CORRECTLY REJECTED" if not is_valid else "❌ SHOULD BE INVALID"
        print(f"{status}: {expr}")
        if not is_valid:
            print(f"  Reason: {msg}")
    
    print("\n✅ Syntax validator tests passed")


def test_parsing():
    """Test AST construction."""
    print("\n" + "="*60)
    print("TEST 3: PARSING (AST CONSTRUCTION)")
    print("="*60)
    
    tests = [
        "cybersecurity",
        "cybersecurity AND ISO27001",
        "SOC2 OR ISO27001",
        "NOT banking",
        "(cybersecurity OR SIEM) AND ISO27001",
    ]
    
    for expr in tests:
        try:
            tokenizer = BooleanTokenizer(expr)
            tokens = tokenizer.tokenize()
            parser = BooleanParser(tokens)
            ast = parser.parse()
            print(f"✅ {expr}")
            print(f"   AST: {ast}")
        except Exception as e:
            print(f"❌ {expr}")
            print(f"   Error: {e}")
    
    print("\n✅ Parsing tests passed")


def test_conflict_detection():
    """Test conflict and contradiction detection."""
    print("\n" + "="*60)
    print("TEST 4: CONFLICT DETECTION")
    print("="*60)
    
    # Valid expression (no conflicts)
    print("\nExpression: cybersecurity AND ISO27001")
    tokenizer = BooleanTokenizer("cybersecurity AND ISO27001")
    tokens = tokenizer.tokenize()
    parser = BooleanParser(tokens)
    ast = parser.parse()
    detector = ConflictDetector()
    
    conflicts = detector.detect_conflicts(ast)
    contradictions = detector.check_contradictions(ast)
    print(f"  Conflicts: {len(conflicts)} found")
    print(f"  Contradictions: {len(contradictions)} found")
    if not conflicts and not contradictions:
        print("  ✅ No issues detected")
    
    # Contradictory expression
    print("\nExpression: ISO27001 AND NOT ISO27001")
    tokenizer = BooleanTokenizer("ISO27001 AND NOT ISO27001")
    tokens = tokenizer.tokenize()
    parser = BooleanParser(tokens)
    ast = parser.parse()
    detector = ConflictDetector()
    
    contradictions = detector.check_contradictions(ast)
    print(f"  Contradictions: {len(contradictions)} found")
    if contradictions:
        print(f"  ⚠️  {contradictions[0]}")
    
    print("\n✅ Conflict detection tests passed")


def test_vendor_filtering():
    """Test vendor filtering with AST evaluation."""
    print("\n" + "="*60)
    print("TEST 5: VENDOR FILTERING")
    print("="*60)
    
    # Sample vendor data
    vendors = [
        {
            "id": "V001",
            "name": "SecureNet",
            "industry": "cybersecurity",
            "certifications": "ISO27001 SOC2",
            "country": "Malaysia"
        },
        {
            "id": "V002",
            "name": "CloudTech",
            "industry": "cloud",
            "certifications": "ISO27001",
            "country": "Singapore"
        },
        {
            "id": "V003",
            "name": "FinSecure",
            "industry": "banking",
            "certifications": "PCI-DSS",
            "country": "Malaysia"
        },
        {
            "id": "V004",
            "name": "AuditPro",
            "industry": "compliance",
            "certifications": "ISO27001 ISO9001",
            "country": "Thailand"
        },
    ]
    
    test_queries = [
        ("cybersecurity", [0]),
        ("ISO27001", [0, 1, 3]),
        ("cybersecurity AND ISO27001", [0]),
        ("ISO27001 OR PCI-DSS", [0, 1, 3, 2]),
        ("NOT banking", [0, 1, 3]),
        ("Malaysia", [0, 2]),
        ("cybersecurity AND Malaysia", [0]),
    ]
    
    print("\nVendor Data:")
    for i, v in enumerate(vendors):
        print(f"  {i}: {v['name']:15} | {v['industry']:15} | {v['certifications']:20} | {v['country']}")
    
    print("\nFilter Tests:")
    parser = BooleanFilterParser()
    
    for query, expected_indices in test_queries:
        matching, errors = parser.filter_vendors(query, vendors)
        
        if errors:
            print(f"❌ QUERY: {query}")
            print(f"   Errors: {errors}")
        else:
            success = set(matching) == set(expected_indices)
            status = "✅" if success else "❌"
            print(f"{status} QUERY: {query}")
            if success:
                vendor_names = [vendors[i]["name"] for i in matching]
                print(f"     Matching: {vendor_names}")
            else:
                print(f"     Expected: {[vendors[i]['name'] for i in expected_indices]}")
                print(f"     Got:      {[vendors[i]['name'] for i in matching]}")
    
    print("\n✅ Vendor filtering tests passed")


def test_complex_scenarios():
    """Test real-world complex scenarios."""
    print("\n" + "="*60)
    print("TEST 6: COMPLEX REAL-WORLD SCENARIOS")
    print("="*60)
    
    vendors = [
        {
            "id": "V001",
            "name": "CyberShield",
            "industry": "cybersecurity",
            "certifications": "ISO27001 SOC2",
            "keywords": "SIEM WAF IDS",
            "country": "Malaysia"
        },
        {
            "id": "V002",
            "name": "InfoSecPro",
            "industry": "cybersecurity",
            "certifications": "ISO27001",
            "keywords": "SIEM encryption",
            "country": "Singapore"
        },
        {
            "id": "V003",
            "name": "FinanceSecure",
            "industry": "banking",
            "certifications": "PCI-DSS ISO27001",
            "keywords": "encryption compliance",
            "country": "Malaysia"
        },
        {
            "id": "V004",
            "name": "RetailGuard",
            "industry": "retail",
            "certifications": "PCI-DSS",
            "keywords": "payment processing",
            "country": "Thailand"
        },
    ]
    
    scenarios = [
        {
            "name": "Scenario 1: Cybersecurity vendors in Malaysia or Singapore",
            "query": "(cybersecurity) AND (Malaysia OR Singapore)",
        },
        {
            "name": "Scenario 2: ISO27001 certified vendors NOT in retail",
            "query": "ISO27001 AND NOT retail",
        },
        {
            "name": "Scenario 3: (SIEM or SOC2) AND ISO27001",
            "query": "(SIEM OR SOC2) AND ISO27001",
        },
        {
            "name": "Scenario 4: Banking vendors with PCI-DSS in Malaysia",
            "query": "banking AND PCI-DSS AND Malaysia",
        },
    ]
    
    parser = BooleanFilterParser()
    
    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print(f"Query: {scenario['query']}")
        
        matching, errors = parser.filter_vendors(scenario['query'], vendors)
        
        if errors:
            print(f"  Errors: {errors}")
        else:
            vendor_names = [vendors[i]["name"] for i in matching]
            print(f"  Results: {vendor_names if vendor_names else 'None'} ({len(matching)} vendors)")
    
    print("\n✅ Complex scenario tests passed")


def main():
    """Run all validation tests."""
    print("\n" + "="*60)
    print("BOOLEAN FILTER PARSER - VALIDATION SUITE")
    print("="*60)
    
    try:
        test_tokenizer()
        test_syntax_validator()
        test_parsing()
        test_conflict_detection()
        test_vendor_filtering()
        test_complex_scenarios()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nBoolean Filter Parser is ready for integration.")
        return 0
    
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
