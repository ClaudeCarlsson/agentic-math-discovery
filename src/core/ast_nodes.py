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
