"""Abstract syntax tree nodes for algebraic expressions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


class Expr:
    """Base class for AST expressions."""

    def size(self) -> int:
        raise NotImplementedError

    def variables(self) -> set[str]:
        raise NotImplementedError

    def substitute(self, mapping: dict[str, Expr]) -> Expr:
        raise NotImplementedError


@dataclass(frozen=True)
class Var(Expr):
    """A variable: x, y, z, ..."""

    name: str

    def size(self) -> int:
        return 1

    def variables(self) -> set[str]:
        return {self.name}

    def substitute(self, mapping: dict[str, Expr]) -> Expr:
        return mapping.get(self.name, self)

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Const(Expr):
    """A constant symbol: e (identity), 0, 1, ..."""

    name: str

    def size(self) -> int:
        return 1

    def variables(self) -> set[str]:
        return set()

    def substitute(self, mapping: dict[str, Expr]) -> Expr:
        return self

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class App(Expr):
    """Application of an operation to arguments: mul(x, y), inv(x), ..."""

    op_name: str
    args: tuple[Expr, ...]

    def __init__(self, op_name: str, args: Sequence[Expr]):
        object.__setattr__(self, "op_name", op_name)
        object.__setattr__(self, "args", tuple(args))

    def size(self) -> int:
        return 1 + sum(a.size() for a in self.args)

    def variables(self) -> set[str]:
        result: set[str] = set()
        for a in self.args:
            result |= a.variables()
        return result

    def substitute(self, mapping: dict[str, Expr]) -> Expr:
        return App(self.op_name, [a.substitute(mapping) for a in self.args])

    def __repr__(self) -> str:
        if len(self.args) == 2:
            return f"({self.args[0]} {self.op_name} {self.args[1]})"
        if len(self.args) == 1:
            return f"{self.op_name}({self.args[0]})"
        args_str = ", ".join(repr(a) for a in self.args)
        return f"{self.op_name}({args_str})"


@dataclass(frozen=True)
class Equation:
    """An equation: lhs = rhs."""

    lhs: Expr
    rhs: Expr

    def variables(self) -> set[str]:
        return self.lhs.variables() | self.rhs.variables()

    def size(self) -> int:
        return self.lhs.size() + self.rhs.size()

    def __repr__(self) -> str:
        return f"{self.lhs} = {self.rhs}"


# --- Parsing equation repr() strings back into AST objects ---

import re

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _tokenize(text: str) -> list[str]:
    """Tokenize an expression string into parentheses, commas, and identifiers."""
    tokens: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in " \t\n":
            i += 1
        elif ch in "(),":
            tokens.append(ch)
            i += 1
        else:
            m = _IDENT_RE.match(text, i)
            if m:
                tokens.append(m.group())
                i = m.end()
            else:
                raise ValueError(f"Unexpected character {ch!r} at position {i} in {text!r}")
    return tokens


def parse_expr(text: str, constants: set[str] | None = None, op_names: set[str] | None = None) -> Expr:
    """Parse an expression string back into an AST Expr.

    Grammar (covers all equation formats in discoveries):
        expr     := '(' expr IDENT expr ')'   -- binary op: (x mul y)
                  | IDENT '(' expr_list ')'    -- apply: inv(x), op(a, b)
                  | IDENT                      -- var or const
        expr_list := expr (',' expr)*

    Disambiguation: a bare IDENT is Const if in `constants`, else Var.
    """
    constants = constants or set()
    op_names = op_names or set()
    tokens = _tokenize(text)
    expr, pos = _parse_expr(tokens, 0, constants, op_names)
    if pos != len(tokens):
        raise ValueError(f"Unexpected tokens after position {pos}: {tokens[pos:]}")
    return expr


def _parse_expr(
    tokens: list[str], pos: int, constants: set[str], op_names: set[str]
) -> tuple[Expr, int]:
    """Recursive descent parser for expressions. Returns (expr, next_pos)."""
    if pos >= len(tokens):
        raise ValueError("Unexpected end of expression")

    tok = tokens[pos]

    # Parenthesized binary application: (expr OP expr)
    if tok == "(":
        pos += 1  # consume '('
        left, pos = _parse_expr(tokens, pos, constants, op_names)
        if pos >= len(tokens):
            raise ValueError("Unexpected end inside parenthesized expression")
        op_name = tokens[pos]
        pos += 1  # consume op name
        right, pos = _parse_expr(tokens, pos, constants, op_names)
        if pos >= len(tokens) or tokens[pos] != ")":
            raise ValueError(f"Expected ')' at position {pos}")
        pos += 1  # consume ')'
        return App(op_name, [left, right]), pos

    # Identifier — could be: IDENT(...) application, or bare var/const
    if _IDENT_RE.fullmatch(tok):
        name = tok
        pos += 1

        # Check for function application: IDENT '(' ...
        if pos < len(tokens) and tokens[pos] == "(":
            pos += 1  # consume '('
            args: list[Expr] = []
            if pos < len(tokens) and tokens[pos] != ")":
                arg, pos = _parse_expr(tokens, pos, constants, op_names)
                args.append(arg)
                while pos < len(tokens) and tokens[pos] == ",":
                    pos += 1  # consume ','
                    arg, pos = _parse_expr(tokens, pos, constants, op_names)
                    args.append(arg)
            if pos >= len(tokens) or tokens[pos] != ")":
                raise ValueError(f"Expected ')' at position {pos}")
            pos += 1  # consume ')'
            return App(name, args), pos

        # Bare identifier: constant or variable
        if name in constants:
            return Const(name), pos
        return Var(name), pos

    raise ValueError(f"Unexpected token {tok!r} at position {pos}")


def parse_equation(
    text: str, constants: set[str] | None = None, op_names: set[str] | None = None
) -> Equation:
    """Parse an equation string 'lhs = rhs' back into an Equation.

    The separator is ' = ' (space-equals-space).
    """
    parts = text.split(" = ", 1)
    if len(parts) != 2:
        raise ValueError(f"Expected 'lhs = rhs' format, got: {text!r}")
    lhs = parse_expr(parts[0], constants, op_names)
    rhs = parse_expr(parts[1], constants, op_names)
    return Equation(lhs, rhs)
