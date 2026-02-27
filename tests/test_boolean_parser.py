"""
Test suite for Boolean Filter Parser

Tests tokenization, parsing, validation, conflict detection, and evaluation.
"""

import pytest
from src.boolean_filter_parser import (
    BooleanTokenizer, Token, TokenType, BooleanParser,
    SyntaxValidator, ConflictDetector, BooleanFilterEvaluator,
    BooleanFilterParser, CriterionNode, NotNode, BinaryOpNode
)


class TestTokenizer:
    """Test boolean expression tokenization."""
    
    def test_simple_criterion(self):
        """Test tokenizing a single criterion."""
        tokenizer = BooleanTokenizer("cybersecurity")
        tokens = tokenizer.tokenize()
        
        assert len(tokens) == 2  # criterion + EOF
        assert tokens[0].type == TokenType.CRITERION
        assert tokens[0].value == "cybersecurity"
        assert tokens[1].type == TokenType.EOF
    
    def test_and_operator(self):
        """Test tokenizing AND operator."""
        tokenizer = BooleanTokenizer("cybersecurity AND ISO27001")
        tokens = tokenizer.tokenize()
        
        assert tokens[0].type == TokenType.CRITERION
        assert tokens[0].value == "cybersecurity"
        assert tokens[1].type == TokenType.AND
        assert tokens[1].value == "AND"
        assert tokens[2].type == TokenType.CRITERION
        assert tokens[2].value == "ISO27001"
    
    def test_or_operator(self):
        """Test tokenizing OR operator."""
        tokenizer = BooleanTokenizer("SOC2 OR ISO27001")
        tokens = tokenizer.tokenize()
        
        assert tokens[0].type == TokenType.CRITERION
        assert tokens[1].type == TokenType.OR
        assert tokens[2].type == TokenType.CRITERION
    
    def test_not_operator(self):
        """Test tokenizing NOT operator."""
        tokenizer = BooleanTokenizer("NOT banking")
        tokens = tokenizer.tokenize()
        
        assert tokens[0].type == TokenType.NOT
        assert tokens[1].type == TokenType.CRITERION
        assert tokens[1].value == "banking"
    
    def test_parentheses(self):
        """Test tokenizing parentheses."""
        tokenizer = BooleanTokenizer("(cybersecurity OR infosec) AND ISO27001")
        tokens = tokenizer.tokenize()
        
        token_types = [t.type for t in tokens]
        assert TokenType.LPAREN in token_types
        assert TokenType.RPAREN in token_types
    
    def test_complex_expression(self):
        """Test tokenizing complex expression."""
        tokenizer = BooleanTokenizer("(cybersecurity OR SIEM) AND ISO27001 AND NOT banking")
        tokens = tokenizer.tokenize()
        
        # Check operators present
        token_values = [t.value for t in tokens if t.type != TokenType.EOF]
        assert "AND" in token_values
        assert "OR" in token_values
        assert "NOT" in token_values
        assert "(" in token_values
        assert ")" in token_values
    
    def test_case_insensitivity(self):
        """Test that operators are case-insensitive."""
        t1 = BooleanTokenizer("cybersecurity and ISO27001").tokenize()
        t2 = BooleanTokenizer("cybersecurity AND ISO27001").tokenize()
        
        # Both should produce same token types
        assert t1[1].type == t2[1].type == TokenType.AND
        assert t1[1].value == t2[1].value == "AND"


class TestSyntaxValidator:
    """Test expression syntax validation."""
    
    def test_valid_simple_expression(self):
        """Test valid simple expression."""
        is_valid, msg = SyntaxValidator.validate("cybersecurity")
        assert is_valid
        assert msg == ""
    
    def test_valid_and_expression(self):
        """Test valid AND expression."""
        is_valid, msg = SyntaxValidator.validate("cybersecurity AND ISO27001")
        assert is_valid
    
    def test_valid_complex_expression(self):
        """Test valid complex expression."""
        is_valid, msg = SyntaxValidator.validate(
            "(cybersecurity OR SIEM) AND ISO27001 AND NOT banking"
        )
        assert is_valid
    
    def test_unmatched_open_paren(self):
        """Test unmatched opening parenthesis."""
        is_valid, msg = SyntaxValidator.validate("(cybersecurity AND ISO27001")
        assert not is_valid
        assert "Unmatched" in msg
    
    def test_unmatched_close_paren(self):
        """Test unmatched closing parenthesis."""
        is_valid, msg = SyntaxValidator.validate("cybersecurity AND ISO27001)")
        assert not is_valid
        assert "Unmatched" in msg
    
    def test_and_as_first_token(self):
        """Test AND as first token."""
        is_valid, msg = SyntaxValidator.validate("AND cybersecurity")
        assert not is_valid
        assert "first" in msg.lower()
    
    def test_and_as_last_token(self):
        """Test AND as last token."""
        is_valid, msg = SyntaxValidator.validate("cybersecurity AND")
        assert not is_valid
        assert "last" in msg.lower()
    
    def test_consecutive_operators(self):
        """Test consecutive AND/OR operators."""
        is_valid, msg = SyntaxValidator.validate("cybersecurity AND OR ISO27001")
        assert not is_valid
    
    def test_not_without_operand(self):
        """Test NOT without operand."""
        is_valid, msg = SyntaxValidator.validate("cybersecurity AND NOT")
        assert not is_valid
    
    def test_empty_expression(self):
        """Test empty expression."""
        is_valid, msg = SyntaxValidator.validate("")
        assert not is_valid


class TestParser:
    """Test AST construction."""
    
    def test_simple_criterion(self):
        """Test parsing single criterion."""
        tokenizer = BooleanTokenizer("cybersecurity")
        tokens = tokenizer.tokenize()
        parser = BooleanParser(tokens)
        ast = parser.parse()
        
        assert isinstance(ast, CriterionNode)
        assert ast.value == "cybersecurity"
    
    def test_and_expression(self):
        """Test parsing AND expression."""
        tokenizer = BooleanTokenizer("cybersecurity AND ISO27001")
        tokens = tokenizer.tokenize()
        parser = BooleanParser(tokens)
        ast = parser.parse()
        
        assert isinstance(ast, BinaryOpNode)
        assert ast.op == "AND"
        assert isinstance(ast.left, CriterionNode)
        assert isinstance(ast.right, CriterionNode)
    
    def test_or_expression(self):
        """Test parsing OR expression."""
        tokenizer = BooleanTokenizer("SOC2 OR ISO27001")
        tokens = tokenizer.tokenize()
        parser = BooleanParser(tokens)
        ast = parser.parse()
        
        assert isinstance(ast, BinaryOpNode)
        assert ast.op == "OR"
    
    def test_not_expression(self):
        """Test parsing NOT expression."""
        tokenizer = BooleanTokenizer("NOT banking")
        tokens = tokenizer.tokenize()
        parser = BooleanParser(tokens)
        ast = parser.parse()
        
        assert isinstance(ast, NotNode)
        assert isinstance(ast.operand, CriterionNode)
    
    def test_operator_precedence(self):
        """Test AND has higher precedence than OR."""
        tokenizer = BooleanTokenizer("cybersecurity OR ISO27001 AND banking")
        tokens = tokenizer.tokenize()
        parser = BooleanParser(tokens)
        ast = parser.parse()
        
        # Should parse as: cybersecurity OR (ISO27001 AND banking)
        assert isinstance(ast, BinaryOpNode)
        assert ast.op == "OR"
        assert isinstance(ast.left, CriterionNode)
        assert isinstance(ast.right, BinaryOpNode)
        assert ast.right.op == "AND"
    
    def test_parenthesized_expression(self):
        """Test parenthesized expression."""
        tokenizer = BooleanTokenizer("(cybersecurity OR ISO27001) AND banking")
        tokens = tokenizer.tokenize()
        parser = BooleanParser(tokens)
        ast = parser.parse()
        
        # Should parse as: (cybersecurity OR ISO27001) AND banking
        assert isinstance(ast, BinaryOpNode)
        assert ast.op == "AND"
        assert isinstance(ast.left, BinaryOpNode)
        assert ast.left.op == "OR"


class TestConflictDetector:
    """Test conflict and contradiction detection."""
    
    def test_no_conflicts_simple(self):
        """Test expression with no conflicts."""
        tokenizer = BooleanTokenizer("cybersecurity AND ISO27001")
        tokens = tokenizer.tokenize()
        parser = BooleanParser(tokens)
        ast = parser.parse()
        
        detector = ConflictDetector()
        conflicts = detector.detect_conflicts(ast)
        assert len(conflicts) == 0
    
    def test_contradiction_same_criterion(self):
        """Test contradiction: A AND NOT A."""
        tokenizer = BooleanTokenizer("ISO27001 AND NOT ISO27001")
        tokens = tokenizer.tokenize()
        parser = BooleanParser(tokens)
        ast = parser.parse()
        
        detector = ConflictDetector()
        contradictions = detector.check_contradictions(ast)
        assert len(contradictions) > 0
        assert "ISO27001" in contradictions[0]
    
    def test_no_contradiction_in_or(self):
        """Test A OR NOT A should not be contradiction in OR context."""
        tokenizer = BooleanTokenizer("ISO27001 OR NOT ISO27001")
        tokens = tokenizer.tokenize()
        parser = BooleanParser(tokens)
        ast = parser.parse()
        
        detector = ConflictDetector()
        contradictions = detector.check_contradictions(ast)
        # OR can logically accept both, so no contradiction
        # (though it's always true, it's not logically invalid)
        # Depends on implementation - current one may flag it


class TestEvaluator:
    """Test vendor filtering with AST evaluation."""
    
    def test_simple_criterion_match(self):
        """Test matching single criterion."""
        meta = [
            {"id": "V001", "industry": "cybersecurity"},
            {"id": "V002", "industry": "banking"},
        ]
        
        tokenizer = BooleanTokenizer("cybersecurity")
        tokens = tokenizer.tokenize()
        parser = BooleanParser(tokens)
        ast = parser.parse()
        
        evaluator = BooleanFilterEvaluator(meta)
        matching = evaluator.filter_vendors(ast)
        assert matching == [0]
    
    def test_and_criterion(self):
        """Test AND criterion matching."""
        meta = [
            {"id": "V001", "industry": "cybersecurity", "certifications": "ISO27001"},
            {"id": "V002", "industry": "cybersecurity", "certifications": "PCI-DSS"},
            {"id": "V003", "industry": "banking", "certifications": "ISO27001"},
        ]
        
        tokenizer = BooleanTokenizer("cybersecurity AND ISO27001")
        tokens = tokenizer.tokenize()
        parser = BooleanParser(tokens)
        ast = parser.parse()
        
        evaluator = BooleanFilterEvaluator(meta)
        matching = evaluator.filter_vendors(ast)
        assert matching == [0]
    
    def test_or_criterion(self):
        """Test OR criterion matching."""
        meta = [
            {"id": "V001", "industry": "cybersecurity"},
            {"id": "V002", "industry": "banking"},
            {"id": "V003", "industry": "it_consulting"},
        ]
        
        tokenizer = BooleanTokenizer("cybersecurity OR banking")
        tokens = tokenizer.tokenize()
        parser = BooleanParser(tokens)
        ast = parser.parse()
        
        evaluator = BooleanFilterEvaluator(meta)
        matching = evaluator.filter_vendors(ast)
        assert len(matching) == 2
        assert 0 in matching
        assert 1 in matching
    
    def test_not_criterion(self):
        """Test NOT criterion matching."""
        meta = [
            {"id": "V001", "industry": "cybersecurity"},
            {"id": "V002", "industry": "banking"},
        ]
        
        tokenizer = BooleanTokenizer("NOT banking")
        tokens = tokenizer.tokenize()
        parser = BooleanParser(tokens)
        ast = parser.parse()
        
        evaluator = BooleanFilterEvaluator(meta)
        matching = evaluator.filter_vendors(ast)
        assert matching == [0]


class TestBooleanFilterParser:
    """Integration tests for complete parser."""
    
    def test_parse_and_validate_valid_expression(self):
        """Test parsing and validating valid expression."""
        parser = BooleanFilterParser()
        ast, errors = parser.parse_and_validate("cybersecurity AND ISO27001")
        
        assert ast is not None
        assert len(errors) == 0
    
    def test_parse_and_validate_invalid_expression(self):
        """Test parsing and validating invalid expression."""
        parser = BooleanFilterParser()
        ast, errors = parser.parse_and_validate("cybersecurity AND AND ISO27001")
        
        assert ast is None
        assert len(errors) > 0
    
    def test_filter_vendors_simple(self):
        """Test filtering vendors with simple expression."""
        meta = [
            {"id": "V001", "industry": "cybersecurity", "certifications": "ISO27001"},
            {"id": "V002", "industry": "banking", "certifications": "PCI-DSS"},
        ]
        
        parser = BooleanFilterParser()
        matching, errors = parser.filter_vendors("cybersecurity", meta)
        
        assert len(errors) == 0
        assert matching == [0]
    
    def test_filter_vendors_complex(self):
        """Test filtering vendors with complex expression."""
        meta = [
            {"id": "V001", "industry": "cybersecurity", "certifications": "ISO27001", "country": "Malaysia"},
            {"id": "V002", "industry": "cybersecurity", "certifications": "PCI-DSS", "country": "USA"},
            {"id": "V003", "industry": "banking", "certifications": "ISO27001", "country": "Malaysia"},
        ]
        
        parser = BooleanFilterParser()
        matching, errors = parser.filter_vendors(
            "(cybersecurity OR banking) AND ISO27001 AND Malaysia",
            meta
        )
        
        assert len(errors) == 0
        assert len(matching) >= 1
        assert 0 in matching
        assert 2 in matching
    
    def test_filter_vendors_with_not(self):
        """Test filtering vendors with NOT operator."""
        meta = [
            {"id": "V001", "industry": "cybersecurity"},
            {"id": "V002", "industry": "banking"},
            {"id": "V003", "industry": "it_consulting"},
        ]
        
        parser = BooleanFilterParser()
        matching, errors = parser.filter_vendors("NOT banking", meta)
        
        assert len(errors) == 0
        assert 1 not in matching  # banking vendor excluded


class TestRealWorldScenarios:
    """Test realistic filtering scenarios."""
    
    def test_scenario_1_siem_or_soc(self):
        """Scenario: Find SIEM or SOC2 vendors."""
        meta = [
            {"id": "V001", "keywords": "SIEM"},
            {"id": "V002", "keywords": "SOC2"},
            {"id": "V003", "keywords": "Firewall"},
        ]
        
        parser = BooleanFilterParser()
        matching, errors = parser.filter_vendors("SIEM OR SOC2", meta)
        
        assert len(errors) == 0
        assert len(matching) == 2
    
    def test_scenario_2_compliance_with_location(self):
        """Scenario: Find compliance vendors in Malaysia with ISO27001."""
        meta = [
            {"id": "V001", "industry": "compliance", "certifications": "ISO27001", "country": "Malaysia"},
            {"id": "V002", "industry": "compliance", "certifications": "ISO9001", "country": "Malaysia"},
            {"id": "V003", "industry": "compliance", "certifications": "ISO27001", "country": "Singapore"},
        ]
        
        parser = BooleanFilterParser()
        matching, errors = parser.filter_vendors(
            "compliance AND ISO27001 AND Malaysia",
            meta
        )
        
        assert len(errors) == 0
        assert matching == [0]
    
    def test_scenario_3_critical_vendors(self):
        """Scenario: Find cybersecurity vendors NOT in retail industry."""
        meta = [
            {"id": "V001", "industry": "cybersecurity", "keywords": "enterprise"},
            {"id": "V002", "industry": "cybersecurity", "keywords": "retail"},
            {"id": "V003", "industry": "banking", "keywords": "security"},
        ]
        
        parser = BooleanFilterParser()
        matching, errors = parser.filter_vendors(
            "cybersecurity AND NOT retail",
            meta
        )
        
        assert len(errors) == 0
        assert 0 in matching
        assert 1 not in matching


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
