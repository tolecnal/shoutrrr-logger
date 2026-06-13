import re
from dataclasses import dataclass


class ASTNode:
    pass


@dataclass
class TermNode(ASTNode):
    value: str
    field: str | None = None
    exact: bool = False
    is_regex: bool = False


@dataclass
class AndNode(ASTNode):
    left: ASTNode
    right: ASTNode


@dataclass
class OrNode(ASTNode):
    left: ASTNode
    right: ASTNode


@dataclass
class NotNode(ASTNode):
    expr: ASTNode


class ParseError(Exception):
    pass


T_AND = "AND"
T_OR = "OR"
T_NOT = "NOT"
T_LPAREN = "LPAREN"
T_RPAREN = "RPAREN"
T_TERM = "TERM"


@dataclass
class Token:
    type: str
    value: str
    field: str | None = None
    exact: bool = False
    is_regex: bool = False


# Regex for tokens:
# AND, OR, NOT, (, )
# Field prefixes: \w+:
# Regex: /.../
# Double quote: "..."
# Single quote: '...'
# Unquoted: ...
TOKEN_REGEX = re.compile(
    r"(?P<LPAREN>\()|"
    r"(?P<RPAREN>\))|"
    r"(?P<AND>\bAND\b)|"
    r"(?P<OR>\bOR\b)|"
    r"(?P<NOT>\bNOT\b|-)|"
    r"(?P<TERM_EXPR>(?P<key>[a-zA-Z0-9_]+:)?(?:/(?P<regex>(?:\\/|[^/])+)/|\"(?P<dquote>(?:\\\"|[^\"])+)\"|'(?P<squote>(?:\\'|[^'])+)'|(?P<unquoted>(?!(?:title|message|sender|severity|tag|after|before):)[^\s\(\)\/\"'][^\s\(\)]*)))|"
    r"(?P<WS>\s+)",
    re.IGNORECASE,
)


def tokenize(query: str) -> list[Token]:
    tokens = []
    expected_index = 0
    for match in TOKEN_REGEX.finditer(query):
        if match.start() > expected_index:
            raise ParseError(f"Unexpected character '{query[expected_index : match.start()]}'")
        expected_index = match.end()

        kind = match.lastgroup
        if kind == "WS":
            continue

        value = match.group()
        if kind == "LPAREN":
            tokens.append(Token(T_LPAREN, value))
        elif kind == "RPAREN":
            tokens.append(Token(T_RPAREN, value))
        elif kind == "AND":
            tokens.append(Token(T_AND, "AND"))
        elif kind == "OR":
            tokens.append(Token(T_OR, "OR"))
        elif kind == "NOT":
            tokens.append(Token(T_NOT, "NOT"))
        elif kind == "TERM_EXPR":
            d = match.groupdict()
            key = d.get("key")
            field = key[:-1].lower() if key else None

            is_regex = False
            exact = False

            if d.get("regex") is not None:
                val = d["regex"].replace("\\/", "/")
                is_regex = True
            elif d.get("dquote") is not None:
                val = d["dquote"].replace('\\"', '"')
                exact = True
            elif d.get("squote") is not None:
                val = d["squote"].replace("\\'", "'")
                exact = True
            elif d.get("unquoted") is not None:
                val = d["unquoted"]
            else:
                continue

            tokens.append(Token(T_TERM, val, field=field, exact=exact, is_regex=is_regex))

    if expected_index < len(query):
        raise ParseError(f"Unexpected character '{query[expected_index:]}'")

    return tokens


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def parse(self) -> ASTNode | None:
        if not self.tokens:
            return None
        node = self.parse_or()
        if self.pos < len(self.tokens):
            raise ParseError(f"Unexpected token {self.tokens[self.pos].value}")
        return node

    def peek(self) -> Token | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse_or(self) -> ASTNode:
        node = self.parse_and()
        while self.peek() and self.peek().type == T_OR:
            self.consume()
            right = self.parse_and()
            node = OrNode(node, right)
        return node

    def parse_and(self) -> ASTNode:
        node = self.parse_not()
        while self.peek():
            tok = self.peek()
            if tok.type == T_AND:
                self.consume()
                right = self.parse_not()
                node = AndNode(node, right)
            elif tok.type in (T_TERM, T_LPAREN, T_NOT):
                right = self.parse_not()
                node = AndNode(node, right)
            else:
                break
        return node

    def parse_not(self) -> ASTNode:
        tok = self.peek()
        if tok and tok.type == T_NOT:
            self.consume()
            expr = self.parse_primary()
            return NotNode(expr)
        return self.parse_primary()

    def parse_primary(self) -> ASTNode:
        tok = self.peek()
        if not tok:
            raise ParseError("Unexpected end of input")

        if tok.type == T_LPAREN:
            self.consume()
            node = self.parse_or()
            tok = self.peek()
            if not tok or tok.type != T_RPAREN:
                raise ParseError("Expected ')'")
            self.consume()
            return node

        if tok.type == T_TERM:
            self.consume()
            return TermNode(tok.value, tok.field, tok.exact, tok.is_regex)

        raise ParseError(f"Unexpected token: {tok.value}")


def parse_query(query: str) -> ASTNode | None:
    if not query or not query.strip():
        return None
    try:
        tokens = tokenize(query)
        parser = Parser(tokens)
        return parser.parse()
    except Exception:
        # Fallback to simple term
        return TermNode(query, None, False, False)
