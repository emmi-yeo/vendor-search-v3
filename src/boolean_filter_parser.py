"""
Boolean Filter Parser Module

Parses complex multi-criteria filter queries with AND/OR/NOT operators,
nested conditions, syntax validation, and conflict detection.

Examples:
- "cybersecurity AND ISO27001"
- "(cybersecurity OR infosec) AND Malaysia"
- "compliance NOT banking"
- "ISO27001 AND (SOC2 OR PCI-DSS)"
"""

import re
from enum import Enum
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass


class TokenType(Enum):
    """Token types for boolean expressions."""
    CRITERION = "CRITERION"      # cybersecurity, ISO27001, Malaysia
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    LPAREN = "LPAREN"            # (
    RPAREN = "RPAREN"            # )
    EOF = "EOF"


@dataclass
class Token:
    """A single token in the boolean expression."""
    type: TokenType
    value: str
    position: int


class BooleanTokenizer:
    """Tokenizes boolean filter expressions."""
    
    OPERATORS = {"AND", "OR", "NOT"}
    
    def __init__(self, expression: str):
        self.expression = expression.strip()
        self.pos = 0
        self.tokens: List[Token] = []
    
    def tokenize(self) -> List[Token]:
        """Convert expression string into tokens."""
        while self.pos < len(self.expression):
            char = self.expression[self.pos]
            
            # Skip whitespace
            if char.isspace():
                self.pos += 1
                continue
            
            # Parentheses
            if char == "(":
                self.tokens.append(Token(TokenType.LPAREN, "(", self.pos))
                self.pos += 1
            elif char == ")":
                self.tokens.append(Token(TokenType.RPAREN, ")", self.pos))
                self.pos += 1
            
            # Operators and criteria
            else:
                # Try to match operator or criterion
                word = self._read_word()
                
                if word.upper() in self.OPERATORS:
                    token_type = TokenType[word.upper()]
                    self.tokens.append(Token(token_type, word.upper(), self.pos - len(word)))
                else:
                    # Regular criterion (e.g., "cybersecurity", "ISO27001", "Malaysia")
                    self.tokens.append(Token(TokenType.CRITERION, word, self.pos - len(word)))
        
        self.tokens.append(Token(TokenType.EOF, "", self.pos))
        return self.tokens
    
    def _read_word(self) -> str:
        """Read a word (criterion or operator) from current position."""
        start = self.pos
        
        # Read alphanumeric, hyphens, underscores, digits
        while self.pos < len(self.expression):
            char = self.expression[self.pos]
            if char.isalnum() or char in "-_":
                self.pos += 1
            else:
                break
        
        return self.expression[start:self.pos]


class ASTNode:
    """Abstract Syntax Tree node."""
    pass


class CriterionNode(ASTNode):
    """Leaf node: a single criterion."""
    
    def __init__(self, value: str):
        self.value = value.lower().strip()
    
    def __repr__(self):
        return f"Criterion({self.value})"


class NotNode(ASTNode):
    """NOT operator node."""
    
    def __init__(self, operand: ASTNode):
        self.operand = operand
    
    def __repr__(self):
        return f"NOT({self.operand})"


class BinaryOpNode(ASTNode):
    """Binary operator node (AND/OR)."""
    
    def __init__(self, op: str, left: ASTNode, right: ASTNode):
        self.op = op
        self.left = left
        self.right = right
    
    def __repr__(self):
        return f"({self.left} {self.op} {self.right})"


class BooleanParser:
    """Parses boolean filter expressions into AST."""
    
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.current_token = self.tokens[0] if tokens else Token(TokenType.EOF, "", 0)
    
    def parse(self) -> ASTNode:
        """Parse tokens into AST."""
        return self._parse_or()
    
    def _advance(self):
        """Move to next token."""
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
            self.current_token = self.tokens[self.pos]
    
    def _parse_or(self) -> ASTNode:
        """Parse OR expression (lowest precedence)."""
        left = self._parse_and()
        
        while self.current_token.type == TokenType.OR:
            self._advance()
            right = self._parse_and()
            left = BinaryOpNode("OR", left, right)
        
        return left
    
    def _parse_and(self) -> ASTNode:
        """Parse AND expression."""
        left = self._parse_not()
        
        while self.current_token.type == TokenType.AND:
            self._advance()
            right = self._parse_not()
            left = BinaryOpNode("AND", left, right)
        
        return left
    
    def _parse_not(self) -> ASTNode:
        """Parse NOT expression (highest precedence)."""
        if self.current_token.type == TokenType.NOT:
            self._advance()
            operand = self._parse_not()
            return NotNode(operand)
        
        return self._parse_primary()
    
    def _parse_primary(self) -> ASTNode:
        """Parse primary expression (criterion or parenthesized expression)."""
        if self.current_token.type == TokenType.CRITERION:
            criterion = CriterionNode(self.current_token.value)
            self._advance()
            return criterion
        
        elif self.current_token.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_or()
            
            if self.current_token.type != TokenType.RPAREN:
                raise SyntaxError(f"Expected ')', got {self.current_token.value}")
            
            self._advance()
            return expr
        
        else:
            raise SyntaxError(f"Unexpected token: {self.current_token.value}")


class SyntaxValidator:
    """Validates boolean expression syntax."""
    
    @staticmethod
    def validate(expression: str) -> Tuple[bool, str]:
        """
        Validate expression syntax.
        
        Returns:
            (is_valid: bool, error_message: str)
        """
        # Check balanced parentheses
        paren_count = 0
        for i, char in enumerate(expression):
            if char == "(":
                paren_count += 1
            elif char == ")":
                paren_count -= 1
                if paren_count < 0:
                    return False, f"Unmatched ')' at position {i}"
        
        if paren_count != 0:
            return False, "Unmatched parentheses"
        
        # Check for isolated operators
        tokens_str = " ".join(re.split(r'[\(\)]', expression))
        token_list = tokens_str.split()
        
        if not token_list:
            return False, "Empty expression"
        
        # Check for operator placement
        for i, token in enumerate(token_list):
            token_upper = token.upper()
            
            # AND/OR should not be first or last
            if token_upper in ["AND", "OR"]:
                if i == 0 or i == len(token_list) - 1:
                    return False, f"'{token}' cannot be first or last"
                
                # AND/OR should not follow each other directly
                if i > 0 and token_list[i - 1].upper() in ["AND", "OR"]:
                    return False, f"'{token}' cannot follow '{token_list[i - 1]}'"
            
            # NOT should not be followed by AND/OR
            if token_upper == "NOT":
                if i == len(token_list) - 1:
                    return False, "NOT must be followed by criterion"
                next_token = token_list[i + 1].upper()
                if next_token in ["AND", "OR"]:
                    return False, f"NOT cannot be followed by '{next_token}'"
        
        return True, ""


class ConflictDetector:
    """Detects logical conflicts in filter expressions."""
    
    def __init__(self, taxonomy: Dict = None):
        """
        Initialize detector with optional taxonomy for semantic analysis.
        
        Args:
            taxonomy: Dict with industry_tree for conflict checking
        """
        self.taxonomy = taxonomy or {}
        self.industry_tree = self.taxonomy.get("industries", {})
    
    def detect_conflicts(self, ast: ASTNode) -> List[str]:
        """
        Detect conflicts in AST.
        
        Returns:
            List of conflict messages (empty if no conflicts)
        """
        conflicts = []
        
        # Collect all criteria in AND branches
        and_groups = self._collect_and_criteria(ast)
        
        for group in and_groups:
            # Check for mutually exclusive criteria
            group_conflicts = self._check_mutual_exclusion(group)
            conflicts.extend(group_conflicts)
        
        return conflicts
    
    def _collect_and_criteria(self, node: ASTNode, in_or: bool = False) -> List[List[str]]:
        """
        Collect criteria in AND branches.
        Returns list of criterion groups connected by AND.
        """
        if isinstance(node, CriterionNode):
            return [[node.value]]
        
        elif isinstance(node, NotNode):
            return self._collect_and_criteria(node.operand, in_or)
        
        elif isinstance(node, BinaryOpNode):
            left_groups = self._collect_and_criteria(node.left, in_or)
            right_groups = self._collect_and_criteria(node.right, in_or)
            
            if node.op == "AND":
                # Combine criteria in same group
                combined = []
                for left in left_groups:
                    for right in right_groups:
                        combined.append(left + right)
                return combined
            else:  # OR
                # Separate groups
                return left_groups + right_groups
        
        return [[]]
    
    def _check_mutual_exclusion(self, criteria: List[str]) -> List[str]:
        """Check for mutually exclusive criteria."""
        conflicts = []
        criteria_set = set(c.lower() for c in criteria)
        
        # List of mutually exclusive criterion pairs
        exclusions = [
            ("cybersecurity", "banking"),
            ("cybersecurity", "retail"),
            ("banking", "manufacturing"),
            ("iso27001", "iso9001"),  # Usually not both needed
        ]
        
        for criterion1, criterion2 in exclusions:
            if criterion1 in criteria_set and criterion2 in criteria_set:
                conflicts.append(
                    f"Conflicting criteria: '{criterion1}' AND '{criterion2}' (usually mutually exclusive)"
                )
        
        return conflicts
    
    def check_contradictions(self, ast: ASTNode) -> List[str]:
        """
        Check for logical contradictions (e.g., "ISO27001 AND NOT ISO27001").
        
        Returns:
            List of contradiction messages
        """
        contradictions = []
        criteria = self._extract_all_criteria(ast)
        positive_criteria = criteria[0]
        negative_criteria = criteria[1]
        
        for crit in positive_criteria:
            if crit in negative_criteria:
                contradictions.append(
                    f"Contradiction: '{crit}' appears as both required and excluded"
                )
        
        return contradictions
    
    def _extract_all_criteria(self, node: ASTNode) -> Tuple[Set[str], Set[str]]:
        """
        Extract positive and negative criteria from AST.
        
        Returns:
            (positive_criteria, negative_criteria)
        """
        positive = set()
        negative = set()
        
        def traverse(n: ASTNode, is_negated: bool = False):
            if isinstance(n, CriterionNode):
                if is_negated:
                    negative.add(n.value)
                else:
                    positive.add(n.value)
            
            elif isinstance(n, NotNode):
                traverse(n.operand, not is_negated)
            
            elif isinstance(n, BinaryOpNode):
                traverse(n.left, is_negated)
                traverse(n.right, is_negated)
        
        traverse(node)
        return positive, negative


class BooleanFilterEvaluator:
    """Evaluates boolean AST against vendor metadata."""
    
    def __init__(self, meta: List[Dict], fuzzy_matcher=None):
        """
        Initialize evaluator.
        
        Args:
            meta: List of vendor metadata dicts
            fuzzy_matcher: Optional fuzzy matching function for approximate matching
        """
        self.meta = meta
        self.fuzzy_matcher = fuzzy_matcher
    
    def evaluate(self, ast: ASTNode, vendor_meta: Dict) -> bool:
        """
        Evaluate AST against a single vendor's metadata.
        
        Args:
            ast: Abstract Syntax Tree
            vendor_meta: Vendor metadata dict
        
        Returns:
            True if vendor matches the criteria, False otherwise
        """
        return self._eval_node(ast, vendor_meta)
    
    def filter_vendors(self, ast: ASTNode) -> List[int]:
        """
        Filter vendor indices matching the AST.
        
        Returns:
            List of matching vendor indices
        """
        matching_indices = []
        
        for i, vendor in enumerate(self.meta):
            if self.evaluate(ast, vendor):
                matching_indices.append(i)
        
        return matching_indices
    
    def _eval_node(self, node: ASTNode, vendor: Dict) -> bool:
        """Recursively evaluate AST node."""
        if isinstance(node, CriterionNode):
            return self._match_criterion(node.value, vendor)
        
        elif isinstance(node, NotNode):
            return not self._eval_node(node.operand, vendor)
        
        elif isinstance(node, BinaryOpNode):
            left = self._eval_node(node.left, vendor)
            right = self._eval_node(node.right, vendor)
            
            if node.op == "AND":
                return left and right
            elif node.op == "OR":
                return left or right
        
        return False
    
    def _match_criterion(self, criterion: str, vendor: Dict) -> bool:
        """Check if criterion matches vendor metadata."""
        criterion_lower = criterion.lower()
        
        # Check industry
        if criterion_lower in (vendor.get("industry", "").lower()):
            return True
        
        # Check certifications
        certs = vendor.get("certifications", "").lower()
        if criterion_lower in certs:
            return True
        
        # Check keywords
        keywords = vendor.get("keywords", "").lower()
        if criterion_lower in keywords:
            return True
        
        # Check location (country, state, city)
        if criterion_lower in (vendor.get("country", "").lower()):
            return True
        if criterion_lower in (vendor.get("state", "").lower()):
            return True
        if criterion_lower in (vendor.get("city", "").lower()):
            return True
        
        # Use fuzzy matcher if available
        if self.fuzzy_matcher:
            # Try fuzzy match on industry
            try:
                match, score, _ = self.fuzzy_matcher(
                    criterion_lower,
                    vendor.get("industry", "")
                )
                if match and score >= 75:
                    return True
            except:
                pass
        
        return False


class BooleanFilterParser:
    """Main parser class combining all components."""
    
    def __init__(self, taxonomy: Dict = None):
        """
        Initialize parser.
        
        Args:
            taxonomy: Optional taxonomy dict for conflict detection
        """
        self.taxonomy = taxonomy or {}
        self.validator = SyntaxValidator()
        self.conflict_detector = ConflictDetector(taxonomy)
    
    def parse_and_validate(self, expression: str) -> Tuple[Optional[ASTNode], List[str]]:
        """
        Parse expression and return AST with validation errors.
        
        Returns:
            (ast: Optional[ASTNode], errors: List[str])
        """
        errors = []
        
        # Syntax validation
        is_valid, error_msg = self.validator.validate(expression)
        if not is_valid:
            return None, [error_msg]
        
        # Tokenize
        try:
            tokenizer = BooleanTokenizer(expression)
            tokens = tokenizer.tokenize()
        except Exception as e:
            return None, [f"Tokenization error: {str(e)}"]
        
        # Parse
        try:
            parser = BooleanParser(tokens)
            ast = parser.parse()
        except SyntaxError as e:
            return None, [str(e)]
        
        # Check for conflicts
        conflicts = self.conflict_detector.detect_conflicts(ast)
        contradictions = self.conflict_detector.check_contradictions(ast)
        
        errors.extend(conflicts)
        errors.extend(contradictions)
        
        return ast, errors
    
    def filter_vendors(self, expression: str, meta: List[Dict]) -> Tuple[List[int], List[str]]:
        """
        Parse expression and filter vendors.
        
        Args:
            expression: Boolean filter expression
            meta: List of vendor metadata
        
        Returns:
            (matching_indices: List[int], errors: List[str])
        """
        ast, errors = self.parse_and_validate(expression)
        
        if ast is None:
            return [], errors
        
        # Evaluate
        evaluator = BooleanFilterEvaluator(meta)
        matching_indices = evaluator.filter_vendors(ast)
        
        return matching_indices, errors
