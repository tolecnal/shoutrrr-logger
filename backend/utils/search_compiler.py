from typing import Any

from backend.utils.search_parser import (
    AndNode,
    ASTNode,
    NotNode,
    OrNode,
    TermNode,
)
from sqlalchemy import ColumnElement, and_, not_, or_
from sqlalchemy.orm import InstrumentedAttribute


def compile_search_ast(node: ASTNode, model: Any) -> ColumnElement[bool]:
    """
    Compiles an AST into SQLAlchemy filter expressions for a given model.
    """
    if isinstance(node, TermNode):
        val = node.value

        # If specific field is requested
        if node.field:
            col = getattr(model, node.field, None)
            if col is not None and isinstance(col, InstrumentedAttribute):
                if node.exact:
                    return col == val
                else:
                    return col.ilike(f"%{val}%")

        # Free-text search fallback (no field, or unknown field)
        # Search across title, message, and sender_name
        if node.exact:
            return or_(
                model.title == val,
                model.message == val,
                model.sender_name == val,
            )
        else:
            return or_(
                model.title.ilike(f"%{val}%"),
                model.message.ilike(f"%{val}%"),
                model.sender_name.ilike(f"%{val}%"),
            )

    elif isinstance(node, AndNode):
        return and_(compile_search_ast(node.left, model), compile_search_ast(node.right, model))

    elif isinstance(node, OrNode):
        return or_(compile_search_ast(node.left, model), compile_search_ast(node.right, model))

    elif isinstance(node, NotNode):
        return not_(compile_search_ast(node.expr, model))

    raise ValueError(f"Unknown AST node type: {type(node)}")
