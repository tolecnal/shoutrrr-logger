import pytest

from utils.search_parser import MAX_TOKENS, AndNode, NotNode, OrNode, TermNode, parse_query


def test_parse_simple_term():
    ast = parse_query("hello")
    assert isinstance(ast, TermNode)
    assert ast.value == "hello"


def test_parse_field_term():
    ast = parse_query("severity:error")
    assert isinstance(ast, TermNode)
    assert ast.field == "severity"
    assert ast.value == "error"
    assert not ast.exact


def test_parse_exact_phrase():
    ast = parse_query('message:"db error"')
    assert isinstance(ast, TermNode)
    assert ast.field == "message"
    assert ast.value == "db error"
    assert ast.exact


def test_parse_regex():
    ast = parse_query("tag:/^prod-[a-z]+$/")
    assert isinstance(ast, TermNode)
    assert ast.field == "tag"
    assert ast.value == "^prod-[a-z]+$"
    assert ast.is_regex


def test_parse_and():
    ast = parse_query("a AND b")
    assert isinstance(ast, AndNode)
    assert isinstance(ast.left, TermNode)
    assert isinstance(ast.right, TermNode)
    assert ast.left.value == "a"
    assert ast.right.value == "b"


def test_parse_implicit_and():
    ast = parse_query("a b")
    assert isinstance(ast, AndNode)
    assert ast.left.value == "a"
    assert ast.right.value == "b"


def test_parse_or():
    ast = parse_query("a OR b")
    assert isinstance(ast, OrNode)
    assert ast.left.value == "a"
    assert ast.right.value == "b"


def test_parse_not():
    ast = parse_query("NOT a")
    assert isinstance(ast, NotNode)
    assert ast.expr.value == "a"


def test_parse_dash_not():
    ast = parse_query("-a")
    assert isinstance(ast, NotNode)
    assert ast.expr.value == "a"


def test_parse_precedence():
    # AND should bind tighter than OR
    ast = parse_query("a OR b AND c")
    assert isinstance(ast, OrNode)
    assert ast.left.value == "a"
    assert isinstance(ast.right, AndNode)
    assert ast.right.left.value == "b"
    assert ast.right.right.value == "c"


def test_parse_parens():
    ast = parse_query("(a OR b) AND c")
    assert isinstance(ast, AndNode)
    assert isinstance(ast.left, OrNode)
    assert ast.left.left.value == "a"
    assert ast.left.right.value == "b"
    assert ast.right.value == "c"


def test_parse_complex():
    ast = parse_query('severity:error AND (message:"db down" OR tag:/urgent/) NOT prod')

    assert isinstance(ast, AndNode)
    assert isinstance(ast.right, NotNode)
    assert ast.right.expr.value == "prod"

    left_and = ast.left
    assert isinstance(left_and, AndNode)
    assert left_and.left.value == "error"
    assert left_and.left.field == "severity"

    or_node = left_and.right
    assert isinstance(or_node, OrNode)
    assert or_node.left.field == "message"
    assert or_node.left.value == "db down"
    assert or_node.right.field == "tag"
    assert or_node.right.value == "urgent"


def test_unmatched_paren_raises():
    # Invalid syntax must surface as an error (ValueError -> HTTP 422),
    # not silently degrade to a literal search.
    with pytest.raises(ValueError, match="Invalid search query"):
        parse_query("(")


def test_invalid_operator_sequence_raises():
    with pytest.raises(ValueError, match="Invalid search query"):
        parse_query("a AND OR b")


def test_empty_query_returns_none():
    assert parse_query("") is None
    assert parse_query("   ") is None


def test_too_many_tokens_raises():
    # Bounds AST depth so compiling can't blow the recursion limit.
    with pytest.raises(ValueError, match="too complex"):
        parse_query(" ".join(["x"] * (MAX_TOKENS + 1)))


def test_deep_query_at_limit_parses_without_error():
    # A query right at the cap must parse cleanly (no RecursionError).
    ast = parse_query(" ".join(["x"] * MAX_TOKENS))
    assert ast is not None


def test_quoted_phrase_marked_exact_unquoted_not():
    assert parse_query('"db error"').exact is True
    assert parse_query("dberror").exact is False
